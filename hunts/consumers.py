# Copyright (C) 2018-2021 The Hunter2 Contributors.
#
# This file is part of Hunter2.
#
# Hunter2 is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any later version.
#
# Hunter2 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License along with Hunter2.  If not, see <http://www.gnu.org/licenses/>.

import asyncio
from datetime import datetime

from asgiref.sync import async_to_sync, sync_to_async
from channels.generic.websocket import JsonWebsocketConsumer
from channels.layers import get_channel_layer
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models.signals import pre_save, post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from events.consumers import EventMixin
from teams.models import Team
from teams.consumers import TeamMixin
from .models import Guess, TeamPuzzleProgress
from . import models, utils


def pre_save_handler(func):
    """The purpose of this decorator is to connect signal handlers to consumer class methods.

    Before the normal signature of the signal handler, func is passed the class (as a normal classmethod) and "old",
    the instance in the database before save was called (or None). func will then be called after the current
    transaction has been successfully committed, ensuring that the instance argument is stored in the database and
    accessible via database connections in other threads, and that data is ready to be sent to clients."""
    def inner(cls, sender, instance, *args, **kwargs):
        try:
            old = type(instance).objects.get(pk=instance.pk)
        except ObjectDoesNotExist:
            old = None

        def after_commit():
            func(cls, old, sender, instance, *args, **kwargs)

        if transaction.get_autocommit():
            # in this case we want to wait until *post* save so the new object is in the db, which on_commit
            # will not do. Instead, do nothing but set an attribute on the instance to the callback, and
            # call it later in a post_save receiver.
            instance._hybrid_save_cb = after_commit
        else:  # nocover
            transaction.on_commit(after_commit)

    return classmethod(inner)


@receiver(post_save)
def hybrid_save_signal_dispatcher(sender, instance, **kwargs):
    # This checks for the attribute set by the above signal handler and calls it if it exists.
    hybrid_cb = getattr(instance, '_hybrid_save_cb', None)
    if hybrid_cb:
        # No need to pass args because this will always be a closure with the args from pre_save
        instance._hybrid_save_cb = None
        hybrid_cb()


class HuntWebsocket(EventMixin, TeamMixin, JsonWebsocketConsumer):
    def connect(self):
        async_to_sync(self.channel_layer.group_add)(
           self._announcement_groupname(self.scope['tenant']), self.channel_name
        )
        self.connected = True
        self.accept()

    def disconnect(self, close_code):
        if not self.connected:
            return
        async_to_sync(self.channel_layer.group_discard)(
            self._announcement_groupname(self.scope['tenant']), self.channel_name
        )

    @classmethod
    def _announcement_groupname(cls, event, puzzle=None):
        if puzzle:
            return f'event-{event.id}.puzzle-{puzzle.id}.announcements'
        else:
            return f'event-{event.id}.announcements'

    @classmethod
    def _send_message(cls, group, message):
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(group, {'type': 'send_json_msg', 'content': message})

    def send_json_msg(self, content, close=False):
        # For some reason consumer dispatch doesn't strip off the outer dictionary with 'type': 'send_json'
        # (or whatever method name) so we override and do it here. This saves us having to define a separate
        # method which just calls send_json for each type of message.
        super().send_json(content['content'])

    @classmethod
    def send_announcement_msg(cls, event, puzzle, announcement):
        cls._send_message(cls._announcement_groupname(event, puzzle), {
            'type': 'announcement',
            'content': {
                'announcement_id': announcement.id,
                'title': announcement.title,
                'message': announcement.message,
                'variant': announcement.type.variant
            }
        })

    @classmethod
    def send_delete_announcement_msg(cls, event, puzzle, announcement):
        cls._send_message(cls._announcement_groupname(event, puzzle), {
            'type': 'delete_announcement',
            'content': {
                'announcement_id': announcement.id
            }
        })

    @pre_save_handler
    def _saved_announcement(cls, old, sender, announcement, raw, *args, **kwargs):
        if raw:  # nocover
            return

        cls.send_announcement_msg(announcement.event, announcement.puzzle, announcement)

    @classmethod
    def _deleted_announcement(cls, sender, instance, *args, **kwargs):
        cls.send_delete_announcement_msg(instance.event, instance.puzzle, instance)


pre_save.connect(HuntWebsocket._saved_announcement, sender=models.Announcement)
pre_delete.connect(HuntWebsocket._deleted_announcement, sender=models.Announcement)


class PuzzleEventWebsocket(HuntWebsocket):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connected = False

    @classmethod
    def _puzzle_groupname(cls, puzzle, team_id=None):
        event_id = puzzle.episode.event_id
        if team_id:
            return f'event-{event_id}.puzzle-{puzzle.id}.events.team-{team_id}'
        else:
            return f'event-{event_id}.puzzle-{puzzle.id}.events'

    def connect(self):
        keywords = self.scope['url_route']['kwargs']
        episode_number = keywords['episode_number']
        puzzle_number = keywords['puzzle_number']
        self.episode, self.puzzle = utils.event_episode_puzzle(self.scope['tenant'], episode_number, puzzle_number)
        async_to_sync(self.channel_layer.group_add)(
            self._puzzle_groupname(self.puzzle, self.team.id), self.channel_name
        )
        async_to_sync(self.channel_layer.group_add)(
            self._announcement_groupname(self.episode.event, self.puzzle), self.channel_name
        )
        self.setup_hint_timers()

        super().connect()

    def disconnect(self, close_code):
        super().disconnect(close_code)
        if not self.connected:
            return
        for e in self.hint_events.values():
            e.cancel()
        async_to_sync(self.channel_layer.group_discard)(
            self._puzzle_groupname(self.puzzle, self.team.id), self.channel_name
        )

    def receive_json(self, content):
        if 'type' not in content:
            self._error('no type in message')
            return

        if content['type'] == 'guesses-plz':
            if 'from' not in content:
                self._error('required field "from" is missing')
                return
            self.send_old_guesses(content['from'])
        elif content['type'] == 'unlocks-plz':
            self.send_old_unlocks()
        elif content['type'] == 'hints-plz':
            if 'from' not in content:
                self._error('required field "from" is missing')
                return
            self.send_old_hints(content['from'])
        else:
            self._error('invalid request type')

    def _error(self, message):
        self.send_json({'type': 'error', 'content': {'error': message}})

    def setup_hint_timers(self):
        self.hint_events = {}
        hints = self.puzzle.hint_set.all().select_related('start_after')
        for hint in hints:
            self.schedule_hint(hint)

    def schedule_hint_msg(self, message):
        try:
            # select_related is needed not for performance but so no queries are necessary in the
            # event loop, which is not allowed
            hint = models.Hint.objects.select_related('start_after').get(id=message['hint_uid'])
        except (TypeError, KeyError):
            raise ValueError('Cannot schedule a hint without either a hint instance or a dictionary with `hint_uid` key.')
        send_expired = message.get('send_expired', False)
        self.schedule_hint(hint, send_expired)

    def schedule_hint(self, hint, send_expired=False):
        try:
            self.hint_events[hint.id].cancel()
        except KeyError:
            pass

        progress, _ = models.TeamPuzzleProgress.objects.get_or_create(puzzle=self.puzzle, team=self.team)
        delay = hint.delay_for_team(self.team, progress)
        if delay is None:
            return
        delay = delay.total_seconds()
        if not send_expired and delay < 0:
            return
        loop = sync_to_async.threadlocal.main_event_loop
        # run the hint sender function on the asyncio event loop so we don't have to bother writing scheduler stuff
        task = loop.create_task(self.send_new_hint(self.team, hint, delay))
        self.hint_events[hint.id] = task

    def cancel_scheduled_hint(self, content):
        hint = models.Hint.objects.get(id=content['hint_uid'])

        try:
            self.hint_events[hint.id].cancel()
            del self.hint_events[hint.id]
        except KeyError:
            pass

    #
    # These class methods define the JS server -> client protocol of the websocket
    #

    @classmethod
    def _new_unlock_json(cls, teamunlock):
        return {
            'guess': teamunlock.unlocked_by.guess,
            'unlock': teamunlock.unlockanswer.unlock.text,
            'unlock_uid': teamunlock.unlockanswer.unlock.compact_id
        }

    @classmethod
    def send_new_unlock(cls, teamunlock):
        cls._send_message(cls._puzzle_groupname(teamunlock.team_puzzle_progress.puzzle, teamunlock.team_puzzle_progress.team_id), {
            'type': 'new_unlock',
            'content': cls._new_unlock_json(teamunlock)
        })

    @classmethod
    def _new_guess_json(cls, guess):
        correct = guess.get_correct_for() is not None
        content = {
            'timestamp': str(guess.given),
            'guess': guess.guess,
            'guess_uid': guess.compact_id,
            'correct': correct,
            'by': guess.by.username,
        }
        return content

    @classmethod
    def send_new_guess(cls, guess):
        content = cls._new_guess_json(guess)

        cls._send_message(cls._puzzle_groupname(guess.for_puzzle, guess.by_team_id), {
            'type': 'new_guesses',
            'content': [content]
        })

    @classmethod
    def _solved_json(cls, progress):
        content = {
            'time': (progress.solved_by.given - progress.start_time).total_seconds(),
            'guess': progress.solved_by.guess,
            'by': progress.solved_by.by.username
        }
        episode = progress.solved_by.for_puzzle.episode
        next = episode.next_puzzle(progress.solved_by.by_team)
        if next:
            next = episode.get_puzzle(next)
            content['text'] = f'to the next puzzle'
            content['redirect'] = next.get_absolute_url()
        else:
            content['text'] = f'back to {episode.name}'
            content['redirect'] = episode.get_absolute_url()

        return content

    @classmethod
    def send_solved(cls, progress):
        content = cls._solved_json(progress)

        cls._send_message(cls._puzzle_groupname(progress.puzzle, progress.team_id), {
            'type': 'solved',
            'content': content
        })

    @classmethod
    def send_change_unlock(cls, unlock, team_id):
        cls._send_message(cls._puzzle_groupname(unlock.puzzle, team_id), {
            'type': 'change_unlock',
            'content': {
                'unlock': unlock.text,
                'unlock_uid': unlock.compact_id,
            }
        })

    @classmethod
    def send_delete_unlockguess(cls, teamunlock):
        layer = get_channel_layer()
        unlock = teamunlock.unlockanswer.unlock
        guess = teamunlock.unlocked_by
        groupname = cls._puzzle_groupname(guess.for_puzzle, guess.by_team_id)
        for hint in unlock.hint_set.all():
            async_to_sync(layer.group_send)(groupname, {
                'type': 'cancel_scheduled_hint',
                'hint_uid': str(hint.id)
            })
        cls._send_message(cls._puzzle_groupname(unlock.puzzle, guess.by_team_id), {
            'type': 'delete_unlockguess',
            'content': {
                'guess': guess.guess,
                'unlock_uid': unlock.compact_id,
            }
        })

    @classmethod
    def _new_hint_json(cls, hint):
        return {
            'type': 'new_hint',
            'content': {
                'hint': hint.text,
                'hint_uid': hint.compact_id,
                'time': str(hint.time),
                'depends_on_unlock_uid': hint.start_after.compact_id if hint.start_after else None
            }
        }

    @classmethod
    def send_new_hint_to_team(cls, team_id, hint):
        cls._send_message(cls._puzzle_groupname(hint.puzzle, team_id), cls._new_hint_json(hint))

    async def send_new_hint(self, team, hint, delay, **kwargs):
        # We can't have a sync function (added to the event loop via call_later) because it would have to call back
        # ultimately to SyncConsumer's send method, which is wrapped in async_to_sync, which refuses to run in a thread
        # with a running asyncio event loop.
        # See https://github.com/django/asgiref/issues/56
        await asyncio.sleep(delay)

        # AsyncConsumer replaces its own base_send attribute with an async_to_sync wrapped version if the instance is (a
        # subclass of) SyncConsumer. While bizarre, the original async function is available as AsyncToSync.awaitable.
        # We also have to reproduce the functionality of JsonWebsocketConsumer and WebsocketConsumer here (they don't
        # have async versions.)
        await self.base_send.awaitable({'type': 'websocket.send', 'text': self.encode_json(self._new_hint_json(hint))})
        del self.hint_events[hint.id]

    @classmethod
    def send_delete_hint(cls, team_id, hint):
        cls._send_message(cls._puzzle_groupname(hint.puzzle, team_id), {
            'type': 'delete_hint',
            'content': {
                'hint_uid': hint.compact_id,
                'depends_on_unlock_uid': hint.start_after.compact_id if hint.start_after else None
            }
        })

    @pre_save_handler
    def _saved_teampuzzleprogress(cls, old, sender, progress, raw, *args, **kwargs):
        if raw:  # nocover
            return

        if progress.solved_by and (not old or not old.solved_by):
            cls.send_solved(progress)

    # handler: Guess.pre_save
    @pre_save_handler
    def _saved_guess(cls, old, sender, guess, raw, *args, **kwargs):
        # Do not trigger unless this was a newly created guess.
        # Note this means an admin modifying a guess will not trigger anything.
        if raw:  # nocover
            return
        if old:
            return

        cls.send_new_guess(guess)

    def send_old_guesses(self, start):
        guesses = Guess.objects.filter(for_puzzle=self.puzzle, by_team=self.team).order_by('given')
        if start != 'all':
            start = datetime.fromtimestamp(int(start) // 1000, timezone.utc)
            # TODO: `start` is given by the client and is the timestamp of the most recently received guess.
            # the following could miss guesses if guesses get the same timestamp, though this is very unlikely.
            guesses = guesses.filter(given__gt=start)
            # The client requested guesses from a certain point in time, i.e. it already has some.
            # Even though these are "old" they're "new" in the sense that the user will never have
            # seen them before so should trigger the same UI effect.
            msg_type = 'new_guesses'
        else:
            msg_type = 'old_guesses'

        guesses = guesses.select_related('by', 'correct_for').seal()

        self.send_json({
            'type': msg_type,
            'content': [self._new_guess_json(g) for g in guesses]
        })

    def send_old_hints(self, start):
        hints = models.Hint.objects.filter(puzzle=self.puzzle).order_by('time')
        progress = self.puzzle.teampuzzleprogress_set.get(team=self.team)
        hints = [h for h in hints if h.unlocked_by(self.team, progress)]
        if start != 'all':
            start = datetime.fromtimestamp(int(start) // 1000, timezone.utc)
            # The following finds the hints which were *not* unlocked at the start time given.
            # combined with the existing filter this gives the ones the client might have missed.
            hints = [h for h in hints if progress.start_time + h.time > start]
            msg_type = 'new_hint'
        else:
            msg_type = 'old_hint'

        for h in hints:
            content = self._new_hint_json(h)
            content['type'] = msg_type
            self.send_json(content)

    def send_old_unlocks(self):
        # TODO: something better for sorting unlocks? The View sorts them as in the admin, but this is not alterable,
        # even though it is often meaningful. Currently JS sorts them alphabetically.
        for tu in models.TeamUnlock.objects.filter(
            team_puzzle_progress__puzzle=self.puzzle
        ).order_by('unlockanswer__unlock__text'):
            self.send_json({
                'type': 'old_unlock',
                'content': self._new_unlock_json(tu)
            })

    @pre_save_handler
    def _saved_teamunlock(cls, old, sender, teamunlock, raw, *args, **kwargs):
        if raw:  # nocover:
            return

        cls.send_new_unlock(teamunlock)

        for hint in teamunlock.unlockanswer.unlock.hint_set.all():
            layer = get_channel_layer()
            async_to_sync(layer.group_send)(cls._puzzle_groupname(
                teamunlock.team_puzzle_progress.puzzle,
                teamunlock.team_puzzle_progress.team_id
            ), {
                'type': 'schedule_hint_msg',
                'hint_uid': str(hint.id),
                'send_expired': True
            })

    @classmethod
    def _deleted_teamunlock(cls, sender, instance, *args, **kwargs):
        teamunlock = instance
        # TODO: this incurs at least one query each time this handler runs, which runs many times in some situations
        # like if the unlock itself is deleted, and/or teams had several guesses unlocking it multiple times

        # to avoid doing more than necessary, we don't check if the unlock is still unlocked.
        # the client will just hide the unlock if there's no longer anything unlocking it.
        # This could result in some unlocks remaining visible incorrectly if there is a network interruption,
        # where doing these checks would mean we can always send a "delete unlock" event to the client.
        # Since this is rare and we assume the team has usually seen the unlock and gained any benefit
        # or confusion (if it's being changed because it was wrong!) from it, this is probably OK.
        cls.send_delete_unlockguess(teamunlock)

    # handler: Unlock.pre_save
    @pre_save_handler
    def _saved_unlock(cls, old, sender, unlock, raw, *args, **kwargs):
        if raw:  # nocover
            return
        if not old:
            return

        if unlock.puzzle != old.puzzle:
            raise ValueError("Cannot move unlocks between puzzles")
        # Get list of teams which can see this unlock
        team_ids = models.TeamUnlock.objects.filter(
            unlockanswer__unlock=unlock
        ).values_list(
            'team_puzzle_progress__team__id'
        ).distinct()

        for t in team_ids:
            cls.send_change_unlock(unlock, t[0])

    # handler: Hint.pre_save
    @pre_save_handler
    def _saved_hint(cls, old, sender, instance, raw, *args, **kwargs):
        if raw:  # nocover
            return
        hint = instance
        if old and hint.puzzle != old.puzzle:
            raise NotImplementedError

        for progress in TeamPuzzleProgress.objects.filter(puzzle=hint.puzzle):
            layer = get_channel_layer()
            if hint.unlocked_by(progress.team, progress):
                async_to_sync(layer.group_send)(
                    cls._puzzle_groupname(hint.puzzle, progress.team_id),
                    {'type': 'cancel_scheduled_hint', 'hint_uid': str(hint.id)}
                )
                cls.send_new_hint_to_team(progress.team_id, hint)
            else:
                if old and old.unlocked_by(progress.team, progress):
                    cls.send_delete_hint(progress.team_id, hint)
                async_to_sync(layer.group_send)(
                    cls._puzzle_groupname(hint.puzzle, progress.team_id),
                    {'type': 'schedule_hint_msg', 'hint_uid': str(hint.id), 'send_expired': True}
                )

    # handler: Hint.pre_delete
    @classmethod
    def _deleted_hint(cls, sender, instance, *arg, **kwargs):
        hint = instance

        for team in Team.objects.all():
            progress = hint.puzzle.teampuzzleprogress_set.get(team=team)
            if hint.unlocked_by(team, progress):
                cls.send_delete_hint(team.id, hint)


pre_save.connect(PuzzleEventWebsocket._saved_teampuzzleprogress, sender=models.TeamPuzzleProgress)
pre_save.connect(PuzzleEventWebsocket._saved_teamunlock, sender=models.TeamUnlock)
pre_save.connect(PuzzleEventWebsocket._saved_guess, sender=models.Guess)
pre_save.connect(PuzzleEventWebsocket._saved_unlock, sender=models.Unlock)
pre_save.connect(PuzzleEventWebsocket._saved_hint, sender=models.Hint)

pre_delete.connect(PuzzleEventWebsocket._deleted_teamunlock, sender=models.TeamUnlock)
pre_delete.connect(PuzzleEventWebsocket._deleted_hint, sender=models.Hint)
