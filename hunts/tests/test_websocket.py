# Copyright (C) 2022 The Hunter2 Contributors.
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

import datetime
import time

import freezegun
from channels.testing import WebsocketCommunicator
from django.utils import timezone

from accounts.factories import UserFactory
from events.test import AsyncEventTestCase, ScopeOverrideCommunicator
from hunter2.routing import application as websocket_app
from teams.factories import TeamFactory, TeamMemberFactory
from ..factories import (
    AnnouncementFactory,
    GuessFactory,
    HintFactory,
    PuzzleFactory,
    TeamPuzzleProgressFactory,
    UnlockAnswerFactory,
    UnlockFactory,
)
from ..models import PuzzleData
from ..utils import encode_uuid


class AnnouncementWebsocketTests(AsyncEventTestCase):
    def setUp(self):
        super().setUp()
        self.pz = PuzzleFactory()
        self.ep = self.pz.episode
        self.url = 'ws/hunt/'

    def test_receive_announcement(self):
        user = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        announcement = AnnouncementFactory(puzzle=None)

        output = self.receive_json(comm, 'Websocket did not send new announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], announcement.message)
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        announcement.message = 'different'
        announcement.save()

        output = self.receive_json(comm, 'Websocket did not send changed announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], 'different')
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        self.run_async(comm.disconnect)()

    def test_receive_delete_announcement(self):
        user = TeamMemberFactory()
        announcement = AnnouncementFactory(puzzle=None)

        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        id = announcement.id
        announcement.delete()

        output = self.receive_json(comm, 'Websocket did not send deleted announcement')
        self.assertEqual(output['type'], 'delete_announcement')
        self.assertEqual(output['content']['announcement_id'], id)

        self.run_async(comm.disconnect)()

    def test_dont_receive_puzzle_specific_announcements(self):
        user = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        AnnouncementFactory(puzzle=self.pz)

        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect)()


class PuzzleWebsocketTests(AsyncEventTestCase):
    # Missing:
    # disconnect with hints scheduled
    # moving unlock to a different puzzle
    # moving hint to a different puzzle (also not implemented)
    def setUp(self):
        super().setUp()
        self.pz = PuzzleFactory()
        self.ep = self.pz.episode
        self.url = 'ws/hunt/ep/%d/pz/%d/' % (self.ep.get_relative_id(), self.pz.get_relative_id())

    def test_anonymous_access_fails(self):
        comm = WebsocketCommunicator(websocket_app, self.url, headers=self.headers)
        connected, subprotocol = self.run_async(comm.connect)()

        self.assertFalse(connected)

    def test_bad_domain(self):
        user = TeamMemberFactory()
        headers = dict(self.headers)
        headers[b'host'] = b'__BAD__.hunter2.local'
        comm = ScopeOverrideCommunicator(websocket_app, self.url, {'user': user}, headers=tuple(headers.items()))
        connected, _ = self.run_async(comm.connect)()

        self.assertFalse(connected)

    def test_bad_requests(self):
        user = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        self.run_async(comm.send_json_to)({'naughty__request!': True})
        output = self.receive_json(comm, 'Websocket did not respond to a bad request')
        self.assertEqual(output['type'], 'error')

        self.run_async(comm.send_json_to)({'type': 'still__bad'})
        output = self.receive_json(comm, 'Websocket did not respond to a bad request')
        self.assertEqual(output['type'], 'error')

        self.run_async(comm.send_json_to)({'type': 'guesses-plz'})
        output = self.receive_json(comm, 'Websocket did not respond to a bad request')
        self.assertEqual(output['type'], 'error')

        self.assertTrue(self.run_async(comm.receive_nothing)())
        self.run_async(comm.disconnect)()

    def test_initial_connection(self):
        ua1 = UnlockAnswerFactory(unlock__puzzle=self.pz)
        UnlockAnswerFactory(unlock__puzzle=self.pz, guess=ua1.guess + '_different')
        h1 = HintFactory(puzzle=self.pz, time=datetime.timedelta(0))
        user = TeamMemberFactory()
        TeamPuzzleProgressFactory(puzzle=self.pz, team=user.team_at(self.tenant), start_time=timezone.now())
        g1 = GuessFactory(for_puzzle=self.pz, by=user)
        g1.given = timezone.now() - datetime.timedelta(days=1)
        g1.save()
        g2 = GuessFactory(for_puzzle=self.pz, guess=ua1.guess, by=user)
        g2.given = timezone.now()
        g2.save()

        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)
        self.run_async(comm.send_json_to)({'type': 'guesses-plz', 'from': 'all'})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for old guesses')

        self.assertEqual(output['type'], 'old_guesses')
        self.assertEqual(len(output['content']), 2, 'Websocket did not send the correct number of old guesses')
        self.assertEqual(output['content'][0]['guess'], g1.guess)
        self.assertEqual(output['content'][0]['by'], user.username)
        self.assertEqual(output['content'][1]['guess'], g2.guess)
        self.assertEqual(output['content'][1]['by'], user.username)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Use utcnow() because the JS uses Date.now() which uses UTC - hence the consumer code also uses UTC.
        dt = (datetime.datetime.utcnow() - datetime.timedelta(hours=1))
        # Multiply by 1000 because Date.now() uses ms not seconds
        self.run_async(comm.send_json_to)({'type': 'guesses-plz', 'from': dt.timestamp() * 1000})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for old guesses')
        self.assertTrue(self.run_async(comm.receive_nothing)(), 'Websocket sent guess from before requested cutoff')

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1, 'Websocket did not send the correct number of old guesses')
        self.assertEqual(output['content'][0]['guess'], g2.guess)
        self.assertEqual(output['content'][0]['by'], user.username)

        self.run_async(comm.send_json_to)({'type': 'unlocks-plz'})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for unlocks')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'old_unlock')
        self.assertEqual(output['content']['unlock'], ua1.unlock.text)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.send_json_to)({'type': 'hints-plz', 'from': dt.timestamp() * 1000})
        output = self.receive_json(comm, 'Websocket did nothing in response to request for hints')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], h1.text)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect)()

    def test_same_team_sees_guesses(self):
        team = TeamFactory()
        u1 = UserFactory()
        u2 = UserFactory()
        team.members.add(u1)
        team.members.add(u2)
        team.save()

        comm1 = self.get_communicator(websocket_app, self.url, {'user': u1})
        comm2 = self.get_communicator(websocket_app, self.url, {'user': u2})

        connected, _ = self.run_async(comm1.connect)()
        self.assertTrue(connected)
        connected, _ = self.run_async(comm2.connect)()
        self.assertTrue(connected)

        g = GuessFactory(for_puzzle=self.pz, correct=False, by=u1)
        g.save()

        output = self.receive_json(comm1, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm1.receive_nothing)())

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['correct'], False)
        self.assertEqual(output['content'][0]['by'], u1.username)

        output = self.receive_json(comm2, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm2.receive_nothing)())

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['correct'], False)
        self.assertEqual(output['content'][0]['by'], u1.username)

        self.run_async(comm1.disconnect)()
        self.run_async(comm2.disconnect)()

    def test_other_team_sees_no_guesses(self):
        u1 = TeamMemberFactory()
        u2 = TeamMemberFactory()

        comm1 = self.get_communicator(websocket_app, self.url, {'user': u1})
        comm2 = self.get_communicator(websocket_app, self.url, {'user': u2})

        connected, _ = self.run_async(comm1.connect)()
        self.assertTrue(connected)
        connected, _ = self.run_async(comm2.connect)()
        self.assertTrue(connected)

        g = GuessFactory(for_puzzle=self.pz, correct=False, by=u1)
        g.save()

        self.assertTrue(self.run_async(comm2.receive_nothing)())
        self.run_async(comm1.disconnect)()
        self.run_async(comm2.disconnect)()

    def test_correct_answer_forwards(self):
        user = TeamMemberFactory()
        g = GuessFactory(for_puzzle=self.pz, correct=False, by=user)
        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        g = GuessFactory(for_puzzle=self.pz, correct=True, by=user)

        self.assertTrue(self.pz.answered_by(user.team_at(self.tenant)))

        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        # We should be notified that we solved the puzzle. Since the episode had just one puzzle,
        # we are now done with that episode and should be redirected back to the episode.
        self.assertEqual(output['type'], 'solved')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['by'], user.username)
        self.assertLessEqual(output['content']['time'], 1)
        self.assertEqual(output['content']['redirect'], self.ep.get_absolute_url(), 'Websocket did not redirect to the episode after completing that episode')
        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # We should be notified of the correct guess. Since the episode had just one puzzle,
        # we are now done with that episode and should be redirected back to the episode.
        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['correct'], True)
        self.assertEqual(output['content'][0]['by'], user.username)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Request guesses again (as if we had reconnected) and check we get the forwarding message
        self.run_async(comm.send_json_to)({'type': 'guesses-plz', 'from': g.given.astimezone(timezone.utc).timestamp() * 1000})
        output = self.receive_json(comm, 'Websocket did not send notification of having solved the puzzle while disconnected')
        self.assertEqual(output['type'], 'solved')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['by'], user.username)
        output = self.receive_json(comm, 'Websocket did nothing in response to requesting guesses again')
        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(output['content'][0]['guess'], g.guess)
        self.assertEqual(output['content'][0]['by'], user.username)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Now add another puzzle. We should be redirected to that puzzle, since it is the
        # unique unfinished puzzle on the episode.
        pz2 = PuzzleFactory(episode=self.ep)
        g.delete()
        g.save()

        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.assertEqual(output['type'], 'solved')
        self.assertEqual(output['content']['guess'], g.guess)
        self.assertEqual(output['content']['by'], user.username)
        self.assertLessEqual(output['content']['time'], 1)
        self.assertEqual(output['content']['redirect'], pz2.get_absolute_url(),
                         'Websocket did not redirect to the next available puzzle when completing'
                         'one of two puzzles on an episode')

        output = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'new_guesses')
        self.assertEqual(len(output['content']), 1)
        received = output['content'][0]
        self.assertEqual(received['guess'], g.guess)
        self.assertEqual(received['correct'], True)
        self.assertEqual(received['by'], user.username)

        self.run_async(comm.disconnect)()

    def test_websocket_receives_unlocks_on_reconnect(self):
        user1 = TeamMemberFactory()
        user2 = TeamMemberFactory()
        ua1 = UnlockAnswerFactory(unlock__puzzle=self.pz, unlock__text='unlock_1', guess='unlock_guess_1')
        ua2 = UnlockAnswerFactory(unlock__puzzle=self.pz, unlock__text='unlock_2', guess='unlock_guess_2')

        comm = self.get_communicator(websocket_app, self.url, {'user': user1})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        GuessFactory(for_puzzle=self.pz, by=user1, guess=ua1.guess)
        self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        self.receive_json(comm, 'Websocket didn\'t do enough in response to an unlocking guess')
        GuessFactory(for_puzzle=self.pz, by=user2, guess=ua2.guess)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.send_json_to)({'type': 'unlocks-plz'})
        output = self.receive_json(comm, 'Websocket did nothing in response to requesting unlocks again')
        self.assertEqual(output['type'], 'old_unlock')
        self.assertEqual(output['content']['guess'], 'unlock_guess_1')
        self.assertEqual(output['content']['unlock'], 'unlock_1')
        self.assertEqual(output['content']['unlock_uid'], ua1.unlock.compact_id)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect())

    def test_websocket_receives_guess_updates(self):
        user = TeamMemberFactory()
        eve = TeamMemberFactory()
        ua = UnlockAnswerFactory(unlock__puzzle=self.pz, unlock__text='unlock_text', guess='unlock_guess')
        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        comm_eve = self.get_communicator(websocket_app, self.url, {'user': eve})

        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)
        connected, subprotocol = self.run_async(comm_eve.connect)()
        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())
        self.assertTrue(self.run_async(comm_eve.receive_nothing)())

        g1 = GuessFactory(for_puzzle=self.pz, by=user, guess=ua.guess)
        output1 = self.receive_json(comm, 'Websocket did nothing in response to a submitted guess')
        output2 = self.receive_json(comm, 'Websocket didn\'t do enough in response to a submitted guess')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        try:
            if output1['type'] == 'new_unlock' and output2['type'] == 'new_guesses':
                new_unlock = output1
            elif output2['type'] == 'new_unlock' and output1['type'] == 'new_guesses':
                new_unlock = output2
            else:
                self.fail('Websocket did not receive exactly one each of new_guesses and new_unlock')
        except KeyError:
            self.fail('Websocket did not receive exactly one each of new_guesses and new_unlock')

        self.assertEqual(new_unlock['content']['unlock'], ua.unlock.text)
        self.assertEqual(new_unlock['content']['unlock_uid'], ua.unlock.compact_id)
        self.assertEqual(new_unlock['content']['guess'], g1.guess)

        g2 = GuessFactory(for_puzzle=self.pz, by=user, guess='different_unlock_guess')
        # discard new_guess notification
        self.run_async(comm.receive_json_from)()
        self.assertTrue(self.run_async(comm.receive_nothing)())

        # Change the unlockanswer so the other guess validates it, check they are switched over
        ua.guess = g2.guess
        ua.save()
        output1 = self.receive_json(comm, 'Websocket did nothing in response to a changed, unlocked unlockanswer')
        output2 = self.receive_json(comm, 'Websocket did not send the expected two replies in response to unlock guess validation changing')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        try:
            if output1['type'] == 'new_unlock' and output2['type'] == 'delete_unlockguess':
                new_unlock = output1
                delete_unlockguess = output2
            elif output2['type'] == 'new_unlock' and output1['type'] == 'delete_unlockguess':
                new_unlock = output2
                delete_unlockguess = output1
            else:
                self.fail('Websocket did not receive exactly one each of new_guess and delete_unlockguess')
        except KeyError:
            self.fail('Websocket did not receive exactly one each of new_guess and delete_unlockguess')

        self.assertEqual(delete_unlockguess['content']['guess'], g1.guess)
        self.assertEqual(delete_unlockguess['content']['unlock_uid'], ua.unlock.compact_id)
        self.assertEqual(new_unlock['content']['unlock'], ua.unlock.text)
        self.assertEqual(new_unlock['content']['unlock_uid'], ua.unlock.compact_id)
        self.assertEqual(new_unlock['content']['guess'], g2.guess)

        # Change the unlock and check we're told about it
        ua.unlock.text = 'different_unlock_text'
        ua.unlock.save()
        output = self.receive_json(comm, 'Websocket did nothing in response to a changed, unlocked unlock')
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.assertEqual(output['type'], 'change_unlock')
        self.assertEqual(output['content']['unlock'], ua.unlock.text)
        self.assertEqual(output['content']['unlock_uid'], ua.unlock.compact_id)

        # Delete unlockanswer, check we are told
        ua.delete()
        output = self.receive_json(comm, 'Websocket did nothing in response to a deleted, unlocked unlockanswer')
        self.assertEqual(output['type'], 'delete_unlockguess')
        self.assertEqual(output['content']['guess'], g2.guess)
        self.assertEqual(output['content']['unlock_uid'], ua.unlock.compact_id)

        # Re-add, check we are told
        ua.save()
        output = self.receive_json(comm, 'Websocket did nothing in response to a new, unlocked unlockanswer')
        self.assertEqual(output['type'], 'new_unlock')
        self.assertEqual(output['content']['guess'], g2.guess)
        self.assertEqual(output['content']['unlock'], ua.unlock.text)
        self.assertEqual(output['content']['unlock_uid'], ua.unlock.compact_id)

        # Delete the entire unlock, check we are told
        old_id = ua.unlock.id
        ua.unlock.delete()
        output = self.receive_json(comm, 'Websocket did nothing in response to a deleted, unlocked unlock')

        self.assertEqual(output['type'], 'delete_unlockguess')
        self.assertEqual(output['content']['guess'], 'different_unlock_guess')
        self.assertEqual(output['content']['unlock_uid'], encode_uuid(old_id))

        # Everything is done, check member of another team didn't overhear anything
        self.assertTrue(self.run_async(comm_eve.receive_nothing)(), 'Websocket sent user updates they should not have received')

        self.run_async(comm.disconnect)()
        self.run_async(comm_eve.disconnect)()

    def test_websocket_receives_hints(self):
        # It would be better to mock the asyncio event loop in order to fake advancing time
        # but that's too much effort (and freezegun doesn't support it yet) so just use
        # short delays and hope.
        delay = 0.2

        user = TeamMemberFactory()
        team = user.team_at(self.tenant)
        data = PuzzleData(self.pz, team, user)
        progress = TeamPuzzleProgressFactory(puzzle=self.pz, team=team, start_time=timezone.now())
        data.save()
        hint = HintFactory(puzzle=self.pz, time=datetime.timedelta(seconds=delay))

        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        # account for delays getting started
        remaining = hint.delay_for_team(team, progress).total_seconds()
        if remaining < 0:
            raise Exception('Websocket hint scheduling test took too long to start up')

        # wait for half the remaining time for output
        self.assertTrue(self.run_async(comm.receive_nothing)(remaining / 2))

        # advance time by all the remaining time
        time.sleep(remaining / 2)
        self.assertTrue(hint.unlocked_by(team, progress))

        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)

        self.run_async(comm.disconnect)()

    def test_websocket_dependent_hints(self):
        delay = 0.3

        user = TeamMemberFactory()
        team = user.team_at(self.tenant)
        progress = TeamPuzzleProgressFactory(puzzle=self.pz, team=team, start_time=timezone.now())
        unlock = UnlockFactory(puzzle=self.pz)
        unlockanswer = unlock.unlockanswer_set.get()
        hint = HintFactory(puzzle=self.pz, time=datetime.timedelta(seconds=delay), start_after=unlock)

        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        # wait for the remaining time for output
        self.assertTrue(self.run_async(comm.receive_nothing)(delay))

        guess = GuessFactory(for_puzzle=self.pz, by=user, guess=unlockanswer.guess)
        self.receive_json(comm, 'Websocket did not send unlock')
        self.receive_json(comm, 'Websocket did not send guess')
        remaining = hint.delay_for_team(team, progress).total_seconds()
        self.assertFalse(hint.unlocked_by(team, progress))
        self.assertTrue(self.run_async(comm.receive_nothing)(remaining / 2))

        # advance time by all the remaining time
        time.sleep(remaining / 2)
        self.assertTrue(hint.unlocked_by(team, progress))

        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)
        self.assertEqual(output['content']['depends_on_unlock_uid'], unlock.compact_id)

        # alter the unlockanswer to an already-made gss, check hint re-appears
        GuessFactory(for_puzzle=self.pz, by=user, guess='__DIFFERENT__')
        self.receive_json(comm, 'Websocket did not receive new guess')
        unlockanswer.guess = '__DIFFERENT__'
        unlockanswer.save()
        output = self.receive_json(comm, 'Websocket did not delete unlock')
        self.assertEqual(output['type'], 'delete_unlockguess')
        output = self.receive_json(comm, 'Websocket did not resend unlock')
        self.assertEqual(output['type'], 'new_unlock')
        output = self.receive_json(comm, 'Websocket did not resend hint')
        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint_uid'], hint.compact_id)

        # delete the unlockanswer, check for notification
        unlockanswer.delete()

        output = self.receive_json(comm, 'Websocket did not delete unlockanswer')
        self.assertEqual(output['type'], 'delete_unlockguess')

        # guesses are write-only - no notification
        guess.delete()

        # create a new unlockanswer for this unlock
        unlockanswer = UnlockAnswerFactory(unlock=unlock)
        guess = GuessFactory(for_puzzle=self.pz, by=user, guess='__INITIALLY_WRONG__')
        self.receive_json(comm, 'Websocket did not send guess')
        # update the unlockanswer to match the given guess, and check that the dependent
        # hint is scheduled and arrives correctly
        unlockanswer.guess = guess.guess
        unlockanswer.save()
        self.receive_json(comm, 'Websocket did not send unlock')
        self.assertFalse(hint.unlocked_by(team, progress))
        self.assertTrue(self.run_async(comm.receive_nothing)(delay / 2))
        time.sleep(delay / 2)
        self.assertTrue(hint.unlocked_by(team, progress))
        output = self.receive_json(comm, 'Websocket did not send unlocked hint')

        self.assertEqual(output['type'], 'new_hint')
        self.assertEqual(output['content']['hint'], hint.text)
        self.assertEqual(output['content']['depends_on_unlock_uid'], unlock.compact_id)
        self.run_async(comm.disconnect)()

    def test_websocket_receives_hint_updates(self):
        with freezegun.freeze_time() as frozen_datetime:
            user = TeamMemberFactory()
            team = user.team_at(self.tenant)
            progress = TeamPuzzleProgressFactory(puzzle=self.pz, team=team, start_time=timezone.now())

            hint = HintFactory(text='hint_text', puzzle=self.pz, time=datetime.timedelta(seconds=1))
            frozen_datetime.tick(delta=datetime.timedelta(seconds=2))
            self.assertTrue(hint.unlocked_by(team, progress))

            comm = self.get_communicator(websocket_app, self.url, {'user': user})
            connected, subprotocol = self.run_async(comm.connect)()
            self.assertTrue(connected)
            self.assertTrue(self.run_async(comm.receive_nothing)())

            hint.text = 'different_hint_text'
            hint.save()

            output = self.receive_json(comm, 'Websocket did not update changed hint text')
            self.assertEqual(output['type'], 'new_hint')
            self.assertEqual(output['content']['hint'], hint.text)
            old_id = output['content']['hint_uid']
            self.assertTrue(self.run_async(comm.receive_nothing)())

            delay = 0.3
            hint.time = datetime.timedelta(seconds=2 + delay)
            hint.save()
            output = self.receive_json(comm, 'Websocket did not remove hint which went into the future')
            self.assertEqual(output['type'], 'delete_hint')
            self.assertEqual(output['content']['hint_uid'], old_id)
            self.assertTrue(self.run_async(comm.receive_nothing)())

            hint.time = datetime.timedelta(seconds=1)
            hint.save()
            output = self.receive_json(comm, 'Websocket did not announce hint which moved into the past')
            self.assertEqual(output['type'], 'new_hint')
            self.assertEqual(output['content']['hint'], hint.text)
            old_id = output['content']['hint_uid']
            self.assertTrue(self.run_async(comm.receive_nothing)())

            hint.delete()
            output = self.receive_json(comm, 'Websocket did not remove hint which was deleted')
            self.assertEqual(output['type'], 'delete_hint')
            self.assertEqual(output['content']['hint_uid'], old_id)
            self.assertTrue(self.run_async(comm.receive_nothing)())

            # Wait for (at most) the delay before the longer hint event would have arrived to check
            # it was correctly cancelled
            self.assertTrue(self.run_async(comm.receive_nothing)(delay))

            self.run_async(comm.disconnect)()

    def test_receive_global_announcement(self):
        user = TeamMemberFactory()
        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        announcement = AnnouncementFactory(puzzle=None)

        output = self.receive_json(comm, 'Websocket did not send new announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], announcement.message)
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        announcement.message = 'different'
        announcement.save()

        output = self.receive_json(comm, 'Websocket did not send changed announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], announcement.id)
        self.assertEqual(output['content']['title'], announcement.title)
        self.assertEqual(output['content']['message'], 'different')
        self.assertEqual(output['content']['variant'], announcement.type.variant)

        self.run_async(comm.disconnect)()

    def test_receives_puzzle_announcements(self):
        user = TeamMemberFactory()

        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, subprotocol = self.run_async(comm.connect)()
        self.assertTrue(connected)

        # Create an announcement for this puzzle and check we receive updates for it
        ann = AnnouncementFactory(puzzle=self.pz)
        output = self.receive_json(comm, 'Websocket did not send new puzzle announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], ann.id)
        self.assertEqual(output['content']['title'], ann.title)
        self.assertEqual(output['content']['message'], ann.message)
        self.assertEqual(output['content']['variant'], ann.type.variant)

        ann.message = 'different'
        ann.save()

        output = self.receive_json(comm, 'Websocket did not send changed announcement')
        self.assertEqual(output['type'], 'announcement')
        self.assertEqual(output['content']['announcement_id'], ann.id)
        self.assertEqual(output['content']['title'], ann.title)
        self.assertEqual(output['content']['message'], 'different')
        self.assertEqual(output['content']['variant'], ann.type.variant)

        # Create an announcement for another puzzle and check we don't hear about it
        pz2 = PuzzleFactory()
        ann2 = AnnouncementFactory(puzzle=pz2)
        self.assertTrue(self.run_async(comm.receive_nothing)())
        ann2.message = 'different'
        self.assertTrue(self.run_async(comm.receive_nothing)())
        ann2.delete()
        self.assertTrue(self.run_async(comm.receive_nothing)())

        self.run_async(comm.disconnect)()

    def test_receives_delete_announcement(self):
        user = TeamMemberFactory()
        announcement = AnnouncementFactory(puzzle=self.pz)

        comm = self.get_communicator(websocket_app, self.url, {'user': user})
        connected, _ = self.run_async(comm.connect)()

        self.assertTrue(connected)
        self.assertTrue(self.run_async(comm.receive_nothing)())

        id = announcement.id
        announcement.delete()

        output = self.receive_json(comm, 'Websocket did not send deleted announcement')
        self.assertEqual(output['type'], 'delete_announcement')
        self.assertEqual(output['content']['announcement_id'], id)

        self.run_async(comm.disconnect)()
