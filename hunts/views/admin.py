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

from os import path
from urllib.parse import quote_plus
import itertools
import tarfile

from collections import defaultdict
from datetime import timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Subquery, Q, F
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
            'for_puzzle', 'for_puzzle__episode', 'by_team', 'by__user', 'correct_for', 'progress',
        ).only(
            'given', 'guess', 'correct_current',
            'for_puzzle__id', 'for_puzzle__title',
            'for_puzzle__episode__id', 'for_puzzle__episode__name',
            'for_puzzle__episode__event__id',
            'by_team__id', 'by_team__name',
            'by__user__id', 'by__user__username',
            'correct_for__id', 'progress__start_time',
        ).annotate(
            byseat=Subquery(
                Attendance.objects.filter(user_info__user__profile=OuterRef('by'), event=self.request.tenant).values('seat')
            ),
            unlocked=Exists(models.TeamUnlock.objects.filter(unlocked_by=OuterRef('id')).only('id')),
        ).prefetch_related(
            Prefetch(
                'for_puzzle__episode',
                queryset=models.Episode.objects.only('id', 'name').all()
            ),
            Prefetch(
                'for_puzzle__episode__event__episode_set',
            ),
            Prefetch(
                'for_puzzle__episode__puzzle_set',
            ),
        ).seal()

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
                'unlocked': g.unlocked,
            } for g in guesses
        ]

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
        ).seal()

        # Sort teams according to how urgently we expect them to need help
        # Current implementation: number of unsolved, looked-at puzzles.
        # for linear episodes, that would be be always be 1, so sort secondarily by number
        # of solved puzzles to discriminate.
        teams = Team.objects.filter(
            at_event=request.tenant
        ).annotate(
            num_solved_puzzles=Count('teampuzzleprogress', filter=Q(teampuzzleprogress__solved_by__isnull=False)),
            num_started_puzzles=Count('teampuzzleprogress', filter=Q(teampuzzleprogress__start_time__isnull=False))
        ).order_by(
            F('num_solved_puzzles') - F('num_started_puzzles'), 'num_solved_puzzles'
        ).prefetch_related('members').seal()

        all_puzzle_progress = models.TeamPuzzleProgress.objects.filter(
            team__at_event=request.tenant
        ).annotate(
            guess_count=Count('guesses'),
            latest_guess_time=Max('guesses__given'),
        ).prefetch_related(
            Prefetch(
                'teamunlock_set',
                queryset=models.TeamUnlock.objects.select_related(
                    'unlockanswer',
                    'unlocked_by',
                )
            )
        ).seal()
        puzzle_progress = defaultdict(dict)
        for progress in all_puzzle_progress:
            puzzle_progress[progress.team_id][progress.puzzle_id] = progress

        def team_puzzle_state(team, puzzle):
            hints_scheduled = None
            guesses = None
            latest_guess = None
            progress = puzzle_progress[team.id].get(puzzle.id)

            if not progress or not progress.start_time:
                state = 'not_opened'
            elif progress.solved_by_id:
                state = 'solved'
                guesses = progress.guess_count
            else:
                state = 'open'
                guesses = progress.guess_count
                latest_guess = progress.latest_guess_time
                unlocked_unlocks = {
                    tu.unlockanswer.unlock_id: tu.unlocked_by.given
                    for tu in progress.teamunlock_set.all()
                }
                hints_scheduled = any([
                    True
                    for h in puzzle.hint_set.all()
                    if (
                        not h.start_after_id
                        or h.start_after_id in unlocked_unlocks
                    ) and not h.unlocked_by(team, progress, unlocked_unlocks=unlocked_unlocks)
                ])
            return {
                'puzzle_id': puzzle.id,
                'episode_number': puzzle.episode.get_relative_id(),
                'state': state,
                'guesses': guesses,
                'latest_guess': latest_guess,
                'hints_scheduled': hints_scheduled,
            }

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
        tp_progresses = models.TeamPuzzleProgress.objects.filter(
            team=team,
            start_time__isnull=False,
        ).annotate(
            num_guesses=Count('guesses'),
        ).filter(
            num_guesses__gt=0,
        ).select_related(
            'puzzle',
            'puzzle__episode',
            'team',
            'solved_by',
        ).only(
            'puzzle__title',
            'puzzle__episode__name',
            'solved_by__given',
            'start_time',
            'team__id',
        ).prefetch_related(
            Prefetch(
                'teamunlock_set',
                queryset=models.TeamUnlock.objects.select_related(
                    'unlockanswer',
                    'unlockanswer__unlock',
                    'unlocked_by',
                ).only(
                    'team_puzzle_progress__id',
                    'unlockanswer__unlock__text',
                    'unlocked_by__given',
                )
            ),
            # Only prefetch guesses by the requested team; puzzle.guess_set.all()
            # will not be all, which means we don't need to filter again.
            Prefetch(
                'guesses',
                queryset=models.Guess.objects.order_by(
                    '-given',
                ).select_related(
                    'by', 'by__user',
                ).only(
                    'by__user__username',
                    'by_team_id',
                    'for_puzzle_id',
                    'given',
                    'guess',
                )
            ),
            Prefetch(
                'puzzle__hint_set',
                queryset=models.Hint.objects.select_related(
                    'start_after', 'start_after__puzzle'
                ).only(
                    'puzzle__id',
                    'start_after_id',
                    'text',
                    'time',
                ).prefetch_related(
                    'start_after__unlockanswer_set'
                )
            ),
        ).seal()

        solved_puzzles = []
        unsolved_puzzles = []

        # Unsolved puzzles from last year's hunts haven't been "on" for a year :)
        latest = min(timezone.now(), event.end_date)

        for tp_progress in tp_progresses:
            puzzle_info = {
                'title': tp_progress.puzzle.title,
                'id': tp_progress.puzzle.id,
                'num_guesses': tp_progress.num_guesses,
            }
            if tp_progress.solved_by:
                solved_puzzles.append({
                    **puzzle_info,
                    'time_finished': tp_progress.solved_by.given,
                    'time_taken': tp_progress.solved_by.given - tp_progress.start_time,
                })
            else:
                # Collate visible hints and unlocks
                clues_visible = [
                    {
                        'type': 'Unlock',
                        'text': tu.unlockanswer.unlock.text,
                        'received_at': tu.unlocked_by.given
                    }
                    for tu in tp_progress.teamunlock_set.all()
                ] + [
                    {
                        'type': 'Hint',
                        'text': h.text,
                        'received_at': h.unlocks_at(team, tp_progress)
                    }
                    for h in itertools.chain(*tp_progress.hints().values())
                ]

                # Hints which depend on not-unlocked unlocks are not included
                unlocked_unlocks = {
                    tu.unlockanswer.unlock.id: tu.unlocked_by.given
                    for tu in tp_progress.teamunlock_set.all()
                }
                hints_scheduled = sorted(
                    [
                        {
                            'text': h.text,
                            'time': h.unlocks_at(team, tp_progress)
                        }
                        for h in tp_progress.puzzle.hint_set.all()
                        if (
                            h.unlocks_at(team, tp_progress, possible_guesses=tp_progress.guesses.all(), unlocked_unlocks=unlocked_unlocks)
                            and not h.unlocked_by(team, tp_progress, possible_guesses=tp_progress.guesses.all(), unlocked_unlocks=unlocked_unlocks)
                        )
                    ],
                    key=lambda x: x['time'],
                )

                unsolved_puzzles.append({
                    **puzzle_info,
                    'episode_name': tp_progress.puzzle.episode.name,
                    'time_started': tp_progress.start_time,
                    'time_on': latest - tp_progress.start_time,
                    'guesses': [{
                        'user': guess.by.username,
                        'guess': guess.guess,
                        'given': guess.given}
                        for guess in tp_progress.guesses.all()[:5]
                    ],
                    'clues_visible': clues_visible,
                    'hints_scheduled': hints_scheduled,
                })

        response = {
            'puzzles': unsolved_puzzles,
            'solved_puzzles': solved_puzzles,
        }

        return JsonResponse(response)
