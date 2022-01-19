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
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, Exists, Max, OuterRef, Prefetch, Subquery, Q, F, Min
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.utils import timezone
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators import cache
from django.views.generic.edit import FormView

from events.models import Attendance
from events.utils import annotate_userprofile_queryset_with_seat
from teams.models import Team, TeamRole
from .mixins import PuzzleAdminMixin, EventAdminMixin, EventAdminJSONMixin
from ..forms import BulkUploadForm, ResetProgressForm
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


class AdminIndex(EventAdminMixin, View):
    def get(self, request):
        return TemplateResponse(
            request,
            'hunts/admin/index.html',
        )


class Guesses(EventAdminMixin, View):
    def get(self, request):
        return TemplateResponse(
            request,
            'hunts/admin/guesses.html',
            {'wide': True},
        )


# The cache timeout of 5 seconds is set equal to the refresh interval used on the page. A single user
# will see virtually no difference, but multiple people observing the page will not cause additional
# load (but will potentially be out of date by up to 10 instead of up to 5 seconds)
@method_decorator(cache.cache_page(5), name='dispatch')
class GuessesList(EventAdminJSONMixin, View):
    def get(self, request):
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
                Attendance.objects.filter(user__profile=OuterRef('by'), event=self.request.tenant).values('seat')
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


class Stats(EventAdminMixin, View):
    def get(self, request):
        return TemplateResponse(
            request,
            'hunts/admin/stats.html',
            {'wide': True},
        )


# 5 seconds is the default refresh interval on the page
@method_decorator(cache.cache_page(5), name='dispatch')
class StatsContent(EventAdminJSONMixin, View):
    def get(self, request, episode_id=None):
        now = timezone.now()
        end_time = min(now, request.tenant.end_date) + timedelta(minutes=10)

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
        ).select_related('at_event').prefetch_related('members', 'members__user').seal()

        now = timezone.now()
        puzzle_progresses = models.TeamPuzzleProgress.objects.filter(
            puzzle__in=puzzles, team__in=all_teams
        ).annotate(
            time_on=now - F('start_time'),
            solved_time=F('solved_by__given') - F('start_time')
        ).select_related('puzzle', 'team', 'solved_by').seal()
        tpp_dict = defaultdict(dict)
        num_solved = defaultdict(int)
        for progress in puzzle_progresses:
            tpp_dict[progress.puzzle][progress.team] = progress
            if progress.solved_by:
                num_solved[progress.puzzle] += 1

        # Now assemble all the stats ready for giving back to the user
        puzzle_progress = [
            {
                'team': t.get_verbose_name(),
                'progress': [{
                    'puzzle': p.title,
                    'time': tpp_dict[p][t].solved_by.given
                } for p in puzzles if t in tpp_dict[p] and tpp_dict[p][t].solved_by]
            } for t in all_teams]
        puzzle_completion = [
            {
                'puzzle': p.title,
                'completion': num_solved[p]
            } for p in puzzles]
        team_puzzle_stuckness = [
            {
                'team': t.get_verbose_name(),
                'puzzleStuckness': [{
                    'puzzle': p.title,
                    'stuckness': (tpp_dict[p][t].time_on).total_seconds()
                } for p in puzzles if t in tpp_dict[p] and not tpp_dict[p][t].solved_by and tpp_dict[p][t].time_on is not None]
            } for t in all_teams]
        puzzle_difficulty = [
            {
                'puzzle': p.title,
                'average_time': sum([tpp.solved_time for tpp in tpp_dict[p].values() if tpp.solved_time], timedelta()).total_seconds() / num_solved[p]
            } for p in puzzles if num_solved[p]]

        data = {
            'teams': [t.get_verbose_name() for t in all_teams],
            'numTeams': all_teams.count(),
            'startTime': min([e.start_date for e in episodes]),
            'endTime': end_time,
            'puzzles': [p.title for p in puzzles],
            'puzzleCompletion': puzzle_completion,
            'puzzleProgress': puzzle_progress,
            'teamPuzzleStuckness': team_puzzle_stuckness,
            'puzzleDifficulty': puzzle_difficulty
        }
        return JsonResponse(data)


class EpisodeList(EventAdminJSONMixin, View):
    def get(self, request):
        return JsonResponse([{
            'id': episode.pk,
            'name': episode.name
        } for episode in models.Episode.objects.filter(event=request.tenant)], safe=False)


class Progress(EventAdminMixin, View):
    def get(self, request):
        return TemplateResponse(
            request,
            'hunts/admin/progress.html',
            {'wide': True},
        )


# The cache timeout of 5 seconds is set equal to the refresh interval used on the page.
@method_decorator(cache.cache_page(5), name='dispatch')
class ProgressContent(EventAdminJSONMixin, View):
    def get(self, request):
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
            at_event=request.tenant,
            role=TeamRole.PLAYER,
        ).annotate(
            num_solved_puzzles=Count('teampuzzleprogress', filter=Q(teampuzzleprogress__solved_by__isnull=False)),
            num_started_puzzles=Count('teampuzzleprogress', filter=Q(teampuzzleprogress__start_time__isnull=False)),
            teampuzzleprogress_exists=Exists(models.TeamPuzzleProgress.objects.filter(team_id=OuterRef('id'))),
        ).filter(
            teampuzzleprogress_exists=True
        ).order_by(
            F('num_solved_puzzles') - F('num_started_puzzles'),
            'num_solved_puzzles'
        ).prefetch_related('members').seal()

        all_puzzle_progress = models.TeamPuzzleProgress.objects.filter(
            team__in=teams,
        ).annotate(
            guess_count=Count('guesses'),
            latest_guess_time=Max('guesses__given'),
        ).select_related(
            'solved_by'
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

        now = timezone.now()

        def team_puzzle_state(team, puzzle):
            hints_scheduled = None
            guesses = None
            latest_guess = None
            progress = puzzle_progress[team.id].get(puzzle.id)
            time_on = None

            if not progress or not progress.start_time:
                state = 'not_opened'
            elif progress.solved_by_id:
                state = 'solved'
                guesses = progress.guess_count
                time_on = (progress.solved_by.given - progress.start_time).total_seconds()
            else:
                state = 'open'
                guesses = progress.guess_count
                time_on = (now - progress.start_time).total_seconds()
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
                'time_on': time_on,
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


class TeamAdmin(EventAdminMixin, View):
    def get(self, request):
        context = {
            'teams': Team.objects.filter(at_event=request.tenant)
        }

        return TemplateResponse(
            request,
            'hunts/admin/admin_teams.html',
            context
        )


class TeamAdminDetail(EventAdminMixin, View):
    def get(self, request, team_id):
        team = get_object_or_404(Team, pk=team_id)
        members = annotate_userprofile_queryset_with_seat(team.members, request.tenant)

        context = {
            'team': team,
            'player_role': TeamRole.PLAYER,
            'members': members,
        }

        return TemplateResponse(
            request,
            'hunts/admin/admin_teams_detail.html',
            context
        )


class TeamAdminDetailContent(EventAdminJSONMixin, View):
    def get(self, request, team_id):
        event = request.tenant

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
        ).order_by(
            'puzzle'
        ).select_related(
            'puzzle',
            'puzzle__episode',
            'team',
            'solved_by',
        ).only(
            'puzzle__title',
            'puzzle__url_id',
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
            if team.role != TeamRole.PLAYER:
                puzzle_info['reset_url'] = reverse('reset_progress') + f'?team={team.id}&puzzle={tp_progress.puzzle.id}'

            if tp_progress.solved_by:
                solved_puzzles.append({
                    **puzzle_info,
                    'time_finished': tp_progress.solved_by.given,
                    'time_taken': tp_progress.solved_by.given - tp_progress.start_time,
                })
            else:
                # Collate visible hints and unlocks
                unlocked_unlocks = {
                    tu['unlockanswer__unlock_id']: tu
                    for tu in tp_progress.teamunlock_set.all().values(
                        'unlockanswer__unlock_id', 'unlockanswer__unlock__text'
                    ).annotate(
                        min_given=Min('unlocked_by__given')
                    )
                }
                clues_visible = [
                    {
                        'type': 'Unlock',
                        'text': tu['unlockanswer__unlock__text'],
                        'received_at': tu['min_given']
                    }
                    for tu in unlocked_unlocks.values()
                ] + [
                    {
                        'type': 'Hint',
                        'text': h.text,
                        'received_at': h.unlocks_at(team, tp_progress)
                    }
                    for h in itertools.chain(*tp_progress.hints().values())
                ]

                unlocked_unlock_times = {
                    k: tu['min_given']
                    for k, tu in unlocked_unlocks.items()
                }
                # Hints which depend on not-unlocked unlocks are not included
                hints_scheduled = sorted(
                    [
                        {
                            'text': h.text,
                            'time': h.unlocks_at(team, tp_progress, unlocked_unlocks=unlocked_unlock_times)
                        }
                        for h in tp_progress.puzzle.hint_set.all()
                        if (
                            h.unlocks_at(team, tp_progress, possible_guesses=tp_progress.guesses.all(), unlocked_unlocks=unlocked_unlock_times)
                            and not h.unlocked_by(team, tp_progress, possible_guesses=tp_progress.guesses.all(), unlocked_unlocks=unlocked_unlock_times)
                        )
                    ],
                    key=lambda x: x['time'],
                )

                unsolved_puzzles.append({
                    **puzzle_info,
                    'url': reverse('puzzle_permalink', kwargs={'puzzle_url_id': tp_progress.puzzle.url_id}),
                    'edit_url': reverse('admin:hunts_puzzle_change', kwargs={'object_id': tp_progress.puzzle.pk}),
                    'guesses_url': reverse('admin_guesses') + f'?team={tp_progress.team.pk}&puzzle={tp_progress.puzzle.pk}',
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


class ResetProgress(EventAdminMixin, View):
    def _setup(self):
        try:
            team_id = self.request.GET['team']
        except KeyError:
            raise Http404

        self.team = get_object_or_404(Team, pk=team_id)
        puzzle_id = self.request.GET.get('puzzle')
        if puzzle_id:
            self.puzzle = get_object_or_404(models.Puzzle, pk=puzzle_id)
        else:
            self.puzzle = None

        self.event = self.team.at_event

    def _get_warnings(self):
        # Create some warnings for situations admins probably shouldn't be using this
        is_player_team = self.team.role == TeamRole.PLAYER
        event_over = self.event.is_over()
        event_in_progress = (
            self.event.episode_set.aggregate(start_date=Min('start_date'))['start_date'] < timezone.now() and
            not self.event.is_over()
        )
        return {
            'is_player_team': is_player_team,
            'event_over': event_over,
            'event_in_progress': event_in_progress,
        }

    def get(self, request):
        self._setup()
        form = ResetProgressForm(warnings=self._get_warnings())
        return self.common_response(form)

    def post(self, request):
        self._setup()
        form = ResetProgressForm(request.POST, warnings=self._get_warnings())
        if form.is_valid():
            self.reset_progress()
            return HttpResponseRedirect(reverse('admin_team_detail', kwargs={'team_id': self.team.id}))
        return self.common_response(form)

    def common_response(self, form):
        # Gather some information for the admin to sanity check
        guesses = models.Guess.objects.filter(by_team=self.team)
        if self.puzzle:
            tpp, _ = models.TeamPuzzleProgress.objects.get_or_create(team=self.team, puzzle=self.puzzle)
            info = {
                'guesses': guesses.filter(for_puzzle=self.puzzle).count(),
                'solved': tpp.solved_by_id is not None,
                'opened': tpp.start_time is not None,
            }
        else:
            info = {
                'guesses': guesses.count(),
                'solved_puzzles': models.TeamPuzzleProgress.objects.filter(
                    team=self.team, solved_by__isnull=False
                ).count(),
                'in_progress_puzzles': models.TeamPuzzleProgress.objects.filter(
                    team=self.team, start_time__isnull=False, solved_by__isnull=True
                ).count(),
                'guessed_puzzles': models.Puzzle.objects.filter(
                    guess__by_team=self.team
                ).order_by().values('id').distinct().count(),
            }

        context = {
            'form': form,
            'team': self.team,
            'puzzle': self.puzzle,
            **info,
            **self._get_warnings()
        }
        return TemplateResponse(
            self.request,
            'hunts/admin/reset_progress_confirm.html',
            context
        )

    def reset_progress(self):
        if self.puzzle:
            puzzle_filter = Q(puzzle=self.puzzle)
            guess_puzzle_filter = Q(for_puzzle=self.puzzle)
        else:
            puzzle_filter = Q()
            guess_puzzle_filter = Q()
        models.Guess.objects.filter(guess_puzzle_filter, by_team=self.team).delete()
        models.TeamPuzzleProgress.objects.filter(puzzle_filter, team=self.team).delete()
        models.TeamPuzzleData.objects.filter(puzzle_filter, team=self.team).delete()
        models.UserPuzzleData.objects.filter(puzzle_filter, user__in=self.team.members.all()).delete()
