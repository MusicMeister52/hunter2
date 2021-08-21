# Copyright (C) 2018 The Hunter2 Contributors.
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
from collections import defaultdict
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
    def _puzzle_groupname(cls, puzzle, team=None):
        event = puzzle.episode.event
        if team:
            return f'event-{event.id}.puzzle-{puzzle.id}.events.team-{team.id}'
        else:
            return f'event-{event.id}.puzzle-{puzzle.id}.events'

    def connect(self):
        keywords = self.scope['url_route']['kwargs']
        episode_number = keywords['episode_number']
        puzzle_number = keywords['puzzle_number']
        self.episode, self.puzzle = utils.event_episode_puzzle(self.scope['tenant'], episode_number, puzzle_number)
        async_to_sync(self.channel_layer.group_add)(
            self._puzzle_groupname(self.puzzle, self.team), self.channel_name
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
            self._puzzle_groupname(self.puzzle, self.team), self.channel_name
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
            hint = models.Hint.objects.get(id=message['hint_uid'])
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
    def _new_unlock_json(cls, guess, unlock):
        return {
            'guess': guess.guess,
            'unlock': unlock.text,
            'unlock_uid': unlock.compact_id
        }

    @classmethod
    def send_new_unlock(cls, guess, unlock):
        cls._send_message(cls._puzzle_groupname(guess.for_puzzle, guess.by_team), {
            'type': 'new_unlock',
            'content': cls._new_unlock_json(guess, unlock)
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
        if correct:
            episode = guess.for_puzzle.episode
            next = episode.next_puzzle(guess.by_team)
            if next:
                next = episode.get_puzzle(next)
                content['text'] = f'to the next puzzle'
                content['redirect'] = next.get_absolute_url()
            else:
                content['text'] = f'back to {episode.name}'
                content['redirect'] = episode.get_absolute_url()

        return content

    @classmethod
    def send_new_guess(cls, guess):
        content = cls._new_guess_json(guess)

        cls._send_message(cls._puzzle_groupname(guess.for_puzzle, guess.by_team), {
            'type': 'new_guess',
            'content': content
        })

    @classmethod
    def send_change_unlock(cls, old_unlock, new_unlock, guess):
        cls._send_message(cls._puzzle_groupname(old_unlock.puzzle, guess.by_team), {
            'type': 'change_unlock',
            'content': {
                'unlock': new_unlock.text,
                'unlock_uid': old_unlock.compact_id,
            }
        })

    @classmethod
    def send_delete_unlock(cls, unlock, guess):
        cls._send_message(cls._puzzle_groupname(unlock.puzzle, guess.by_team), {
            'type': 'delete_unlock',
            'content': {
                'unlock_uid': unlock.compact_id,
            }
        })

    @classmethod
    def send_delete_unlockguess(cls, unlock, guess):
        # First get any hints dependent on the unlock and "schedule" them - which will cancel them
        layer = get_channel_layer()
        groupname = cls._puzzle_groupname(guess.for_puzzle, guess.by_team)
        for hint in unlock.hint_set.all():
            async_to_sync(layer.group_send)(groupname, {
                'type': 'schedule_hint_msg',
                'hint_uid': str(hint.id)
            })
        cls._send_message(cls._puzzle_groupname(unlock.puzzle, guess.by_team), {
            'type': 'delete_unlockguess',
            'content': {
                'guess': guess.guess,
                'unlock_uid': unlock.compact_id,
            }
        })

    @classmethod
    def _new_hint_json(self, hint):
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
    def send_new_hint_to_team(cls, team, hint):
        cls._send_message(cls._puzzle_groupname(hint.puzzle, team), cls._new_hint_json(hint))

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
    def send_delete_hint(cls, team, hint):
        cls._send_message(cls._puzzle_groupname(hint.puzzle, team), {
            'type': 'delete_hint',
            'content': {
                'hint_uid': hint.compact_id,
                'depends_on_unlock_uid': hint.start_after.compact_id if hint.start_after else None
            }
        })

    # handler: Guess.pre_save
    @pre_save_handler
    def _saved_guess(cls, old, sender, guess, raw, *args, **kwargs):
        # Do not trigger unless this was a newly created guess.
        # Note this means an admin modifying a guess will not trigger anything.
        if raw:  # nocover
            return
        if old:
            return

        # required info:
        # guess, correctness, new unlocks, timestamp, whodunnit
        all_unlocks = models.Unlock.objects.filter(
            puzzle=guess.for_puzzle
        ).select_related(
            'puzzle'
        ).prefetch_related(
            'unlockanswer_set',
            'hint_set'
        )
        for u in all_unlocks:
            if any([a.validate_guess(guess) for a in u.unlockanswer_set.all()]):
                cls.send_new_unlock(guess, u)
            for hint in u.hint_set.all():
                layer = get_channel_layer()
                # It is impossible for a hint to already be unlocked if it's dependent on what we just entered,
                # so we just schedule it here rather than checking if it's unlocked and perhaps sending straight away.
                async_to_sync(layer.group_send)(cls._puzzle_groupname(guess.for_puzzle, guess.by_team), {
                    'type': 'schedule_hint_msg',
                    'hint_uid': str(hint.id)
                })

        cls.send_new_guess(guess)

    def send_old_guesses(self, start):
        guesses = Guess.objects.filter(for_puzzle=self.puzzle, by_team=self.team).select_related('by', 'by_team').order_by('given')
        if start != 'all':
            start = datetime.fromtimestamp(int(start) // 1000, timezone.utc)
            # TODO: `start` is given by the client and is the timestamp of the most recently received guess.
            # the following could miss guesses if guesses get the same timestamp, though this is very unlikely.
            guesses = guesses.filter(given__gt=start)
            # The client requested guesses from a certain point in time, i.e. it already has some.
            # Even though these are "old" they're "new" in the sense that the user will never have
            # seen them before so should trigger the same UI effect.
            msg_type = 'new_guess'
        else:
            msg_type = 'old_guess'

        for g in guesses:
            content = self._new_guess_json(g)
            self.send_json({
                'type': msg_type,
                'content': content
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
        guesses = Guess.objects.filter(for_puzzle=self.puzzle, by_team=self.team)

        all_unlocks = models.Unlock.objects.filter(puzzle=self.puzzle).order_by('text')
        unlocks = defaultdict(list)
        for u in all_unlocks:
            # Performance note: 1 query per unlock
            correct_guesses = u.unlocked_by(self.team)
            if not correct_guesses:
                continue

            correct_guesses = set(correct_guesses)
            for g in correct_guesses:
                unlocks[g].append(u)

        # TODO: something for sorting unlocks? The View sorts them as in the admin, but this is not alterable,
        # even though it is often meaningful. Currently JS sorts them alphabetically.
        for g in guesses:
            for u in unlocks[g]:
                self.send_json({
                    'type': 'old_unlock',
                    'content': self._new_unlock_json(g, u)
                })

    # handler: Unlockanswer.pre_save
    @pre_save_handler
    def _saved_unlockanswer(cls, old_unlockanswer, sender, instance, raw, *args, **kwargs):
        if raw:  # nocover
            return

        unlockanswer = instance
        unlock = unlockanswer.unlock
        puzzle = unlock.puzzle

        # Performance note:
        # This means that whenever an unlock is added or changed, every single guess on
        # that puzzle is going to be tested against that guess immediately.
        # If there comes a point where we are using very complex lua runtimes and/or have
        # huge numbers of teams, with >> 10,000 guesses in total on a puzzle, we could
        # do this asynchronously.
        guesses = models.Guess.objects.filter(
            for_puzzle=puzzle
        ).select_related(
            'by_team'
        )
        if old_unlockanswer:
            others = unlock.unlockanswer_set.exclude(id=unlockanswer.id)
            for g in guesses:
                if old_unlockanswer.validate_guess(g) and not any(a.validate_guess(g) for a in others):
                    # The unlockanswer was the only one giving us this and it no longer does
                    cls.send_delete_unlockguess(unlock, g)
                    # No need to do anything for hints, as the client will delete them if the unlock disappears

        layer = get_channel_layer()
        for g in guesses:
            if unlockanswer.validate_guess(g):
                # Just notify about all guesses that match this answer. Some may already have done so but that's OK.
                cls.send_new_unlock(g, unlock)
                # Send out hints unlocked by this. Again, we may send already-sent hints but the client will ignore it.
                for h in unlock.hint_set.all():
                    if h.unlocked_by(g.by_team, None):
                        cls.send_new_hint_to_team(g.by_team, h)
                    else:
                        async_to_sync(layer.group_send)(
                            cls._puzzle_groupname(h.puzzle, g.by_team),
                            {'type': 'schedule_hint_msg', 'hint_uid': str(h.id), 'send_expired': True}
                        )

    # handler: Unlock.pre_save
    @pre_save_handler
    def _saved_unlock(cls, old, sender, instance, raw, *args, **kwargs):
        if raw:  # nocover
            return
        if not old:
            # New unlocks are boring; we will then notify via the unlockanswer hook
            return

        unlock = instance
        puzzle = unlock.puzzle
        guesses = models.Guess.objects.filter(
            for_puzzle=puzzle
        ).select_related(
            'by_team'
        )

        # This could conceivably be different if someone adds an unlock to the wrong puzzle! Probably never going
        # to happen. Better safe than sorry.
        if puzzle == old.puzzle:
            done_teams = []
            for g in guesses:
                if g.by_team in done_teams:
                    continue
                if any([u.validate_guess(g) for u in old.unlockanswer_set.all()]):
                    done_teams.append(g.by_team)
                    cls.send_change_unlock(old, unlock, g)
        else:
            for g in guesses:
                if any([u.validate_guess(g) for u in old.unlockanswer_set.all()]):
                    # If the puzzles are different we send *one* message to delete that unlock to the
                    # old puzzle websocket, then add the unlock to the new puzzle, one guess at a time.
                    if g.by_team not in done_teams:
                        cls.send_delete_unlock(unlock, g)
                    done_teams.append(g.by_team)
                    cls.send_new_unlock(g, old)

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
                async_to_sync(layer.group_send)(cls._puzzle_groupname(hint.puzzle, progress.team), {'type': 'cancel_scheduled_hint', 'hint_uid': str(hint.id)})
                cls.send_new_hint_to_team(progress.team, hint)
            else:
                if old and old.unlocked_by(progress.team, progress):
                    cls.send_delete_hint(progress.team, hint)
                async_to_sync(layer.group_send)(
                    cls._puzzle_groupname(hint.puzzle, progress.team),
                    {'type': 'schedule_hint_msg', 'hint_uid': str(hint.id), 'send_expired': True}
                )

    # handler: UnlockAnswer.pre_delete
    @classmethod
    def _deleted_unlockanswer(cls, sender, instance, *args, **kwargs):
        # TODO if the Unlock is being deleted it will cascade to the answers. In that case
        # we don't actually need to send events for them.
        unlockanswer = instance
        try:
            unlock = unlockanswer.unlock
        except models.Unlock.DoesNotExist:
            return

        puzzle = unlock.puzzle

        guesses = models.Guess.objects.filter(
            for_puzzle=puzzle,
        ).select_related(
            'by_team',
        )

        others = unlock.unlockanswer_set.exclude(id=unlockanswer.id)

        done_teams = []

        for g in guesses:
            if g.by_team in done_teams:
                continue
            if unlockanswer.validate_guess(g) and not any(a.validate_guess(g) for a in others):
                cls.send_delete_unlockguess(unlock, g)
                done_teams.append(g.by_team)

    # handler: Unlock.pre_delete
    @classmethod
    def _deleted_unlock(cls, sender, instance, *args, **kwargs):
        unlock = instance
        puzzle = unlock.puzzle

        guesses = models.Guess.objects.filter(
            for_puzzle=puzzle
        ).select_related(
            'by_team',
        )

        done_teams = []

        for g in guesses:
            if g.by_team in done_teams:
                continue
            if any([u.validate_guess(g) for u in instance.unlockanswer_set.all()]):
                done_teams.append(g.by_team)
                cls.send_delete_unlock(unlock, g)

    # handler: Hint.pre_delete
    @classmethod
    def _deleted_hint(cls, sender, instance, *arg, **kwargs):
        hint = instance

        for team in Team.objects.all():
            progress = hint.puzzle.teampuzzleprogress_set.get(team=team)
            if hint.unlocked_by(team, progress):
                cls.send_delete_hint(team, hint)


pre_save.connect(PuzzleEventWebsocket._saved_guess, sender=models.Guess)
pre_save.connect(PuzzleEventWebsocket._saved_unlockanswer, sender=models.UnlockAnswer)
pre_save.connect(PuzzleEventWebsocket._saved_unlock, sender=models.Unlock)
pre_save.connect(PuzzleEventWebsocket._saved_hint, sender=models.Hint)

pre_delete.connect(PuzzleEventWebsocket._deleted_unlockanswer, sender=models.UnlockAnswer)
pre_delete.connect(PuzzleEventWebsocket._deleted_unlock, sender=models.Unlock)
pre_delete.connect(PuzzleEventWebsocket._deleted_hint, sender=models.Hint)
