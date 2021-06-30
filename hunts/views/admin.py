# Copyright (C) 2019 The Hunter2 Contributors.
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

from distutils.util import strtobool
from os import path
from urllib.parse import quote_plus
import tarfile

from collections import defaultdict
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Max, OuterRef, Prefetch, Subquery
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.urls import reverse
from django.views import View
from django.views.generic.edit import FormView

from events.models import Attendance
from events.utils import annotate_userprofile_queryset_with_seat
from teams.models import Team, TeamRole
from teams.rules import is_admin_for_event
from .mixins import PuzzleAdminMixin
from ..forms import BulkUploadForm
from .. import models


class BulkUpload(LoginRequiredMixin, PuzzleAdminMixin, FormView):
    template_name = 'hunts/bulk_upload.html'
    form_class = BulkUploadForm

    def form_valid(self, form):
        FileModel = models.SolutionFile if form.cleaned_data['solution'] else models.PuzzleFile
        try:
            archive = tarfile.open(fileobj=form.cleaned_data['archive'])
            base_path = form.cleaned_data['base_path']
            members = [m for m in archive.getmembers() if m.isfile()]
            url_paths = [path.join(base_path, m.name) for m in members]
            if not form.cleaned_data['overwrite']:
                qs = FileModel.objects.filter(puzzle=self.request.puzzle, url_path__in=url_paths)
                if qs.exists():
                    return self.upload_error(form, 'Files would be overwritten by the upload.')
            for member, url_path in zip(members, url_paths):
                content = archive.extractfile(member)
                try:
                    pf = FileModel.objects.get(puzzle=self.request.puzzle, url_path=url_path)
                except FileModel.DoesNotExist:
                    pf = FileModel(puzzle=self.request.puzzle, url_path=url_path)
                try:
                    pf.file.save(path.basename(member.name), File(content))
                except ValidationError as e:
                    return self.upload_error(form, e)
        except tarfile.ReadError as e:
            return self.upload_error(form, e)
        return HttpResponseRedirect(reverse('admin:hunts_puzzle_change', kwargs={'object_id': self.request.puzzle.pk}))

    def upload_error(self, form, error):
        context = self.get_context_data(form=form)
        context['upload_error'] = f'Unable to process provided archive: {error}'
        return self.render_to_response(context)


class AdminIndex(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return TemplateResponse(
            request,
            'hunts/admin/index.html',
        )


class Guesses(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return TemplateResponse(
            request,
            'hunts/admin/guesses.html',
            {'wide': True},
        )


class GuessesList(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            return JsonResponse({
                'result': 'Forbidden',
                'message': 'Must be an admin to list guesses',
            }, status=403)

        episode = request.GET.get('episode')
        puzzle = request.GET.get('puzzle')
        team = request.GET.get('team')
        user = request.GET.get('user')

        puzzles = models.Puzzle.objects.all()
        if puzzle:
            puzzles = puzzles.filter(id=puzzle)
        if episode:
            puzzles = puzzles.filter(episode_id=episode)

        # The following query is heavily optimised. We only retrieve the fields we will use here and
        # in the template, and we select and prefetch related objects so as not to perform any extra
        # queries.
        all_guesses = models.Guess.objects.filter(
            for_puzzle__in=puzzles,
        ).order_by(
            '-given'
        ).select_related(
            'for_puzzle', 'by_team', 'by__user', 'correct_for'
        ).only(
            'given', 'guess', 'correct_current',
            'for_puzzle__id', 'for_puzzle__title',
            'by_team__id', 'by_team__name',
            'by__user__id', 'by__user__username',
            'correct_for__id'
        ).annotate(
            byseat=Subquery(
                Attendance.objects.filter(user_info__user__profile=OuterRef('by'), event=self.request.tenant).values('seat')
            )
        ).prefetch_related(
            Prefetch(
                'for_puzzle__episode',
                queryset=models.Episode.objects.only('id', 'name').all()
            )
        )

        if team:
            all_guesses = all_guesses.filter(by_team_id=team)
        if user:
            all_guesses = all_guesses.filter(by_id=user)

        guess_pages = Paginator(all_guesses, 50)
        page = request.GET.get('page')
        try:
            guesses = guess_pages.page(page)
        except PageNotAnInteger:
            guesses = guess_pages.page(1)
        except EmptyPage:
            guesses = guess_pages.page(guess_pages.num_pages)

        guesses_list = [
            {
                'add_answer_url': f'{reverse("admin:hunts_answer_add")}?for_puzzle={g.for_puzzle.id}&answer={quote_plus(g.guess)}',
                'add_unlock_url': f'{reverse("admin:hunts_unlock_add")}?puzzle={g.for_puzzle.id}&new_guess={quote_plus(g.guess)}',
                'correct': bool(g.get_correct_for()),
                'episode': {
                    'id': g.for_puzzle.episode.id,
                    'name': g.for_puzzle.episode.name,
                },
                'given': g.given,
                'guess': g.guess,
                'puzzle': {
                    'id': g.for_puzzle.id,
                    'title': g.for_puzzle.title,
                    'admin_url': reverse('admin:hunts_puzzle_change', kwargs={'object_id': g.for_puzzle.id}),
                    'site_url': g.for_puzzle.get_absolute_url(),
                },
                'team': {
                    'id': g.by_team.id,
                    'name': g.by_team.name,
                },
                'time_on_puzzle': g.time_on_puzzle(),
                'user': {
                    'id': g.by.id,
                    'name': g.by.username,
                    'seat': g.byseat,
                },
                'unlocked': False,
            } for g in guesses
        ]

        highlight_unlocks = request.GET.get('highlight_unlocks')
        if highlight_unlocks is not None and strtobool(highlight_unlocks):
            for g, gl in zip(guesses, guesses_list):
                unlockanswers = models.UnlockAnswer.objects.filter(unlock__puzzle=g.for_puzzle)
                gl['unlocked'] = any([a.validate_guess(g) for a in unlockanswers])

        return JsonResponse({
            'guesses': guesses_list,
            'rows': all_guesses.count(),
        })


class Stats(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return TemplateResponse(
            request,
            'hunts/admin/stats.html',
            {'wide': True},
        )


class StatsContent(LoginRequiredMixin, View):
    def get(self, request, episode_id=None):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        now = timezone.now()
        end_time = min(now, request.tenant.end_date) + timedelta(minutes=10)

        # TODO select and prefetch all the things
        episodes = models.Episode.objects.filter(event=request.tenant).order_by('start_date')
        if episode_id is not None:
            episodes = episodes.filter(pk=episode_id)
        if not episodes.exists():
            raise Http404

        puzzles = models.Puzzle.objects.filter(episode__in=episodes)

        all_teams = Team.objects.annotate(
            num_members=Count('members')
        ).filter(
            at_event=request.tenant,
            role=TeamRole.PLAYER,
            num_members__gte=1,
        ).prefetch_related('members', 'members__user')

        # Get the first correct guess for each team on each puzzle.
        # We use Guess.correct_for (i.e. the cache) because otherwise we perform a query for every
        # (team, puzzle) pair i.e. a butt-ton. This comes at the cost of possibly seeing
        # a team doing worse than it really is.
        all_guesses = models.Guess.objects.filter(
            correct_for__isnull=False,
        ).select_related('for_puzzle', 'by_team')
        correct_guesses = defaultdict(dict)
        for guess in all_guesses:
            team_guesses = correct_guesses[guess.for_puzzle]
            if guess.by_team not in team_guesses or guess.given < team_guesses[guess.by_team].given:
                team_guesses[guess.by_team] = guess

        # Get when each team started each puzzle, and in how much time they solved each puzzle if they did.
        puzzle_progresses = models.TeamPuzzleProgress.objects.filter(puzzle__in=puzzles, team__in=all_teams).select_related('puzzle', 'team')
        start_times = defaultdict(lambda: defaultdict(dict))
        solved_times = defaultdict(list)
        for progress in puzzle_progresses:
            if progress.team in correct_guesses[progress.puzzle] and progress.start_time:
                start_times[progress.team][progress.puzzle] = None
                solved_times[progress.puzzle].append(correct_guesses[progress.puzzle][progress.team].given - progress.start_time)
            else:
                start_times[progress.team][progress.puzzle] = progress.start_time

        # How long a team has been on a puzzle.
        stuckness = {
            team: [
                now - start for start in start_times[team].values() if start
            ] for team in all_teams
        }
        # How many teams have been active on each puzzle
        num_active_teams = {
            puzzle: len([1 for t in all_teams if start_times[t][puzzle]])
            for puzzle in puzzles
        }

        # Now assemble all the stats ready for giving back to the user
        puzzle_progress = [
            {
                'team': t.get_verbose_name(),
                'progress': [{
                    'puzzle': p.title,
                    'time': correct_guesses[p][t].given
                } for p in puzzles if t in correct_guesses[p]]
            } for t in all_teams]
        puzzle_completion = [
            {
                'puzzle': p.title,
                'completion': len(correct_guesses[p])
            } for p in puzzles]
        team_puzzle_stuckness = [
            {
                'team': t.get_verbose_name(),
                'puzzleStuckness': [{
                    'puzzle': p.title,
                    'stuckness': (now - start_times[t][p]).total_seconds()
                } for p in puzzles if start_times[t][p]]
            } for t in all_teams]
        team_total_stuckness = [
            {
                'team': t.get_verbose_name(),
                'stuckness': sum(stuckness[t], timedelta()).total_seconds(),
            } for t in all_teams]
        puzzle_average_stuckness = [
            {
                'puzzle': p.title,
                'stuckness': sum([
                    now - start_times[t][p] for t in all_teams if start_times[t][p]
                ], timedelta()).total_seconds() / num_active_teams[p]
            } for p in puzzles if num_active_teams[p] > 0]
        puzzle_difficulty = [
            {
                'puzzle': p.title,
                'average_time': sum(solved_times[p], timedelta()).total_seconds() / len(solved_times[p])
            } for p in puzzles if solved_times[p]]

        data = {
            'teams': [t.get_verbose_name() for t in all_teams],
            'numTeams': all_teams.count(),
            'startTime': min([e.start_date for e in episodes]),
            'endTime': end_time,
            'puzzles': [p.title for p in puzzles],
            'puzzleCompletion': puzzle_completion,
            'puzzleProgress': puzzle_progress,
            'teamTotalStuckness': team_total_stuckness,
            'teamPuzzleStuckness': team_puzzle_stuckness,
            'puzzleAverageStuckness': puzzle_average_stuckness,
            'puzzleDifficulty': puzzle_difficulty
        }
        return JsonResponse(data)


class EpisodeList(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return JsonResponse([{
            'id': episode.pk,
            'name': episode.name
        } for episode in models.Episode.objects.filter(event=request.tenant)], safe=False)


class Progress(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return TemplateResponse(
            request,
            'hunts/admin/progress.html',
            {'wide': True},
        )


class ProgressContent(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        puzzles = models.Puzzle.objects.filter(
            episode_id__isnull=False
        ).select_related(
            'episode',
            'episode__event',
        ).prefetch_related(
            'episode__event__episode_set',
            'episode__puzzle_set',
            'hint_set',
        )

        # TODO only teams which have opened a puzzle/guessed/some other criterion
        teams = Team.objects.filter(at_event=request.tenant).prefetch_related('members').seal()

        all_guesses = models.Guess.objects.filter(
            for_puzzle__episode__event=request.tenant
        ).select_related(
            'by_team', 'for_puzzle', 'correct_for'
        ).seal()

        team_guessed_on_puzzle = defaultdict(dict)
        puzzle_activity = all_guesses.values('by_team', 'for_puzzle').annotate(
            latest=Max('given'),
            guesses=Count('id')
        ).order_by()
        for pz_team in puzzle_activity:
            team_guessed_on_puzzle[pz_team['by_team']][pz_team['for_puzzle']] = {
                'latest': pz_team['latest'],
                'guesses': pz_team['guesses'],
            }

        all_puzzle_progress = models.TeamPuzzleProgress.objects.filter(
            team__at_event=request.tenant
        ).select_related(
            'team', 'puzzle'
        ).prefetch_related(
            Prefetch(
                'puzzle__guess_set',
                queryset=models.Guess.objects.order_by(
                    'given'
                ).select_related('by', 'by__user')
            ),
            Prefetch(
                'puzzle__hint_set',
                queryset=models.Hint.objects.select_related(
                    'start_after', 'start_after__puzzle'
                ).prefetch_related('start_after__unlockanswer_set')
            ),
            'puzzle__unlock_set__unlockanswer_set',
        ).seal()
        puzzle_progress = defaultdict(dict)
        for progress in all_puzzle_progress:
            puzzle_progress[progress.team.id][progress.puzzle.id] = progress

        def team_puzzle_state(team, puzzle):
            hints_scheduled = None
            guesses = None
            latest_guess = None

            if any(g.get_correct_for() for g in all_guesses if g.for_puzzle == puzzle and g.by_team == team):
                state = 'solved'
                guesses = team_guessed_on_puzzle[team.id].get(puzzle.id, {}).get('guesses', 0)
            elif not puzzle_progress[team.id].get(puzzle.id) or not puzzle_progress[team.id][puzzle.id].start_time:
                state = 'not_opened'
            else:
                state = 'open'
                guesses = team_guessed_on_puzzle[team.id].get(puzzle.id, {}).get('guesses', 0)
                latest_guess = team_guessed_on_puzzle[team.id].get(puzzle.id, {}).get('latest', None)
                hints_scheduled = any([
                    True
                    for h in puzzle.hint_set.all()
                    if h.unlocks_at(team, puzzle_progress[team.id][puzzle.id])
                    and not h.unlocked_by(team, puzzle_progress[team.id][puzzle.id], puzzle.guess_set.all())
                ])
            return {
                'puzzle_id': puzzle.id,
                'episode_number': puzzle.episode.get_relative_id(),
                'state': state,
                'guesses': guesses,
                'latest_guess': latest_guess,
                'hints_scheduled': hints_scheduled,
            }

        def team_help_needed_rating(team):
            """Rate how much admins should be trying to assist this team relative to others"""
            # Current implementation: number of unsolved, looked-at puzzles.
            solved = len([1 for pz in puzzles
                          if any(g.get_correct_for() for g in all_guesses
                                 if g.for_puzzle == pz and g.by_team == team)
                          ])
            looked_at = len([1 for pz in puzzles
                             if puzzle_progress[team.id].get(pz.id) and puzzle_progress[team.id][pz.id].start_time])
            # for linear episodes, that would be be always be 1, so add in the number of solved puzzles
            # to discriminate.
            return looked_at - solved, -solved

        teams = sorted(teams, key=team_help_needed_rating, reverse=True)

        data = {
            'puzzles': [{
                'short_name': pz.abbr,
                'title': pz.title,
                'episode': pz.episode.get_relative_id(),
            } for pz in puzzles],
            'team_progress': [{
                'id': t.id,
                'url': reverse('admin_team_detail', kwargs={'team_id': t.id}),
                'name': t.get_verbose_name(),
                'progress': [
                    team_puzzle_state(t, pz)
                    for pz in puzzles
                ]
            } for t in teams],
        }
        return JsonResponse(data)


class TeamAdmin(LoginRequiredMixin, View):
    def get(self, request):
        admin = is_admin_for_event.test(request.user, request.tenant)
        event = request.tenant

        if not admin:
            raise PermissionDenied

        context = {
            'teams': Team.objects.filter(at_event=event)
        }

        return TemplateResponse(
            request,
            'hunts/admin/admin_teams.html',
            context
        )


class TeamAdminDetail(LoginRequiredMixin, View):
    def get(self, request, team_id):
        admin = is_admin_for_event.test(request.user, request.tenant)
        event = request.tenant

        if not admin:
            raise PermissionDenied

        team = get_object_or_404(Team, pk=team_id)
        members = annotate_userprofile_queryset_with_seat(team.members, event)

        context = {
            'team': team,
            'members': members,
        }

        return TemplateResponse(
            request,
            'hunts/admin/admin_teams_detail.html',
            context
        )


class TeamAdminDetailContent(LoginRequiredMixin, View):
    def get(self, request, team_id):
        admin = is_admin_for_event.test(request.user, request.tenant)
        event = request.tenant

        if not admin:
            raise PermissionDenied

        team = get_object_or_404(Team, pk=team_id)

        # All the data is keyed off puzzles. Only return puzzles which
        # are unsolved but have a guess.
        puzzles = models.Puzzle.objects.filter(
            guess__by_team=team_id
        ).distinct().annotate(
            num_guesses=Count('guess')
        ).prefetch_related(
            # Only prefetch guesses by the requested team; puzzle.guess_set.all()
            # will not be all, which means we don't need to filter again.
            Prefetch(
                'guess_set',
                queryset=models.Guess.objects.filter(
                    by_team_id=team_id
                ).order_by(
                    '-given'
                ).select_related('by', 'by__user')
            ),
            Prefetch(
                'hint_set',
                queryset=models.Hint.objects.select_related(
                    'start_after', 'start_after__puzzle'
                ).prefetch_related('start_after__unlockanswer_set')
            ),
            'unlock_set',
            'unlock_set__unlockanswer_set',
        )

        # Most info is only needed for un-solved puzzles; find which are solved
        # now so we can save some work
        solved_puzzles = {}
        for pz in puzzles:
            correct = [g for g in pz.guess_set.all() if g.correct_for]
            if correct:
                solved_puzzles[pz.id] = correct[0]

        # Grab the TeamPuzzleProgress necessary to calculate hint timings
        tp_progresses = models.TeamPuzzleProgress.objects.filter(
            puzzle__in=puzzles,
            team_id=team_id
        )
        tp_progresses = {tp_progress.puzzle_id: tp_progress for tp_progress in tp_progresses}

        # Collate visible hints and unlocks
        clues_visible = {
            puzzle.id: [{
                'type': 'Unlock',
                'text': u.text,
                'received_at': u.unlocked_by(team, puzzle.guess_set.all())[0].given}
                for u in puzzle.unlock_set.all()
                if u.unlocked_by(team, puzzle.guess_set.all())
            ] + [{
                'type': 'Hint',
                'text': h.text,
                'received_at': h.unlocks_at(team, tp_progresses[puzzle.id], puzzle.guess_set.all())}
                for h in puzzle.hint_set.all()
                if h.unlocked_by(team, tp_progresses[puzzle.id], puzzle.guess_set.all())
            ]
            for puzzle in puzzles
        }

        # Hints which depend on not-unlocked unlocks are not included
        hints_scheduled = {
            puzzle.id: sorted([
                {
                    'text': h.text,
                    'time': h.unlocks_at(team, tp_progresses[puzzle.id])
                }
                for h in puzzle.hint_set.all()
                if h.unlocks_at(team, tp_progresses[puzzle.id]) and not h.unlocked_by(team, tp_progresses[puzzle.id], puzzle.guess_set.all())
            ], key=lambda x: x['time'])
            for puzzle in puzzles
        }

        # Unsolved puzzles from last year's hunts haven't been "on" for a year :)
        latest = min(timezone.now(), event.end_date)

        response = {
            'puzzles': [{
                'title': puzzle.title,
                'episode_name': puzzle.episode.name,
                'id': puzzle.id,
                'time_started': tp_progresses[puzzle.id].start_time,
                'time_on': latest - tp_progresses[puzzle.id].start_time,
                'num_guesses': puzzle.num_guesses,
                'guesses': [{
                    'user': guess.by.username,
                    'guess': guess.guess,
                    'given': guess.given}
                    for guess in puzzle.guess_set.all()[:5]
                ],
                'clues_visible': clues_visible[puzzle.id],
                'hints_scheduled': hints_scheduled[puzzle.id]}
                for puzzle in puzzles
                if puzzle.id not in solved_puzzles
            ],
            'solved_puzzles': [{
                'title': puzzle.title,
                'id': puzzle.id,
                'time_finished': solved_puzzles[puzzle.id].given,
                'time_taken': solved_puzzles[puzzle.id].given - tp_progresses[puzzle.id].start_time,
                'num_guesses': puzzle.num_guesses}
                for puzzle in puzzles
                if puzzle.id in solved_puzzles
            ],
        }

        return JsonResponse(response)
