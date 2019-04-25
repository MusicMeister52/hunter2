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

from distutils.util import strtobool
from os import path
from string import Template
from urllib.parse import quote_plus
import tarfile

from collections import defaultdict
from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files import File
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Count, OuterRef, Prefetch, Subquery
from django.http import Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from sendfile import sendfile
from teams.mixins import TeamMixin

from . import models, rules, utils
from .forms import BulkUploadForm
from .mixins import EpisodeUnlockedMixin, PuzzleAdminMixin, PuzzleUnlockedMixin
from accounts.models import UserInfo
from events.models import Attendance
from events.utils import annotate_userinfo_queryset_with_seat

import hunter2
import teams


class Index(TemplateView):
    template_name = 'hunts/index.html'

    def get_context_data(self, **kwargs):
        config = hunter2.models.Configuration.get_solo()
        return {
            # TODO: Real content from DB
            'content': config.index_content,
        }


class EpisodeIndex(LoginRequiredMixin, TeamMixin, EpisodeUnlockedMixin, View):
    def get(self, request, episode_number):
        return redirect(request.episode.get_absolute_url(), permanent=True)


class EpisodeContent(LoginRequiredMixin, TeamMixin, EpisodeUnlockedMixin, View):
    def get(self, request, episode_number):
        puzzles = request.episode.unlocked_puzzles(request.team)
        for puzzle in puzzles:
            puzzle.done = puzzle.answered_by(request.team)

        positions = request.episode.finished_positions()
        if request.team in positions:
            position = positions.index(request.team)
            if position < 3:
                position = {0: 'first', 1: 'second', 2: 'third'}[position]
            else:
                position += 1
                position = f'in position {position}'
        else:
            position = None

        files = {f.slug: f.file.url for f in request.tenant.eventfile_set.filter(slug__isnull=False)}
        flavour = Template(request.episode.flavour).safe_substitute(**files)

        return TemplateResponse(
            request,
            'hunts/episode.html',
            context={
                'episode': request.episode.name,
                'flavour': flavour,
                'position': position,
                'episode_number': episode_number,
                'puzzles': puzzles,
            }
        )


class EpisodeList(LoginRequiredMixin, View):
    def get(self, request):
        admin = rules.is_admin_for_event(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return JsonResponse([{
            'id': episode.pk,
            'name': episode.name
        } for episode in models.Episode.objects.filter(event=request.tenant)], safe=False)


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
                pf.file.save(path.basename(member.name), File(content))
        except tarfile.ReadError as e:
            return self.upload_error(form, e)
        return HttpResponseRedirect(reverse('admin:hunts_puzzle_change', kwargs={'object_id': self.request.puzzle.pk}))

    def upload_error(self, form, error):
        context = self.get_context_data(form=form)
        context['upload_error'] = f'Unable to process provided archive: {error}'
        return self.render_to_response(context)


class Guesses(LoginRequiredMixin, View):
    def get(self, request):
        admin = rules.is_admin_for_event(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return TemplateResponse(
            request,
            'hunts/guesses.html',
            {'wide': True},
        )


class GuessesList(LoginRequiredMixin, View):
    def get(self, request):
        admin = rules.is_admin_for_event(request.user, request.tenant)

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
        admin = rules.is_admin_for_event(request.user, request.tenant)

        if not admin:
            raise PermissionDenied

        return TemplateResponse(
            request,
            'hunts/stats.html',
            {'wide': True},
        )


class StatsContent(LoginRequiredMixin, View):
    def get(self, request, episode_id=None):
        admin = rules.is_admin_for_event(request.user, request.tenant)

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

        puzzles = models.Puzzle.objects.all()

        all_teams = teams.models.Team.objects.annotate(
            num_members=Count('members')
        ).filter(
            at_event=request.tenant,
            is_admin=False,
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
        puzzle_datas = models.TeamPuzzleData.objects.filter(puzzle__in=puzzles, team__in=all_teams).select_related('puzzle', 'team')
        start_times = defaultdict(lambda: defaultdict(dict))
        solved_times = defaultdict(list)
        for data in puzzle_datas:
            if data.team in correct_guesses[data.puzzle] and data.start_time:
                start_times[data.team][data.puzzle] = None
                solved_times[data.puzzle].append(correct_guesses[data.puzzle][data.team].given - data.start_time)
            else:
                start_times[data.team][data.puzzle] = data.start_time

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


class EventDirect(LoginRequiredMixin, View):
    def get(self, request):
        return redirect('event')


class EventIndex(LoginRequiredMixin, View):
    def get(self, request):

        event = request.tenant

        positions = utils.finishing_positions(event)
        if request.team in positions:
            position = positions.index(request.team)
            if position < 3:
                position = {0: 'first', 1: 'second', 2: 'third'}[position]
            else:
                position += 1
                position = f'in position {position}'
        else:
            position = None

        episodes = [
            e for e in
            models.Episode.objects.filter(event=event.id).order_by('start_date')
            if e.started(request.team)
        ]

        # Annotate the episodes with their position in the event.
        for episode in episodes:
            episode.index = episode.get_relative_id()

        return TemplateResponse(
            request,
            'hunts/event.html',
            context={
                'event_title':  event.name,
                'episodes':     list(episodes),
                'position':     position,
            }
        )


class Puzzle(LoginRequiredMixin, TeamMixin, PuzzleUnlockedMixin, View):
    def get(self, request, episode_number, puzzle_number):
        puzzle = request.puzzle

        data = models.PuzzleData(puzzle, request.team, request.user.profile)

        now = timezone.now()

        if not data.tp_data.start_time:
            data.tp_data.start_time = now

        answered = puzzle.answered_by(request.team)
        hints = [
            h for h in puzzle.hint_set.all().order_by('time') if h.unlocked_by(request.team, data)
        ]
        unlocks = []
        for u in puzzle.unlock_set.all():
            guesses = u.unlocked_by(request.team)
            if not guesses:
                continue

            guesses = [g.guess for g in guesses]
            # Get rid of duplicates but preserve order
            duplicates = set()
            guesses = [g for g in guesses if not (g in duplicates or duplicates.add(g))]
            unlock_text = mark_safe(u.text)  # nosec unlock text is provided by puzzle admins, we consider this safe
            unlocks.append({'guesses': guesses, 'text': unlock_text})

        event_files = {f.slug: f.file.url for f in request.tenant.eventfile_set.filter(slug__isnull=False)}
        puzzle_files = {f.slug: reverse(
            'puzzle_file',
            kwargs={
                'episode_number': episode_number,
                'puzzle_number': puzzle_number,
                'file_path': f.url_path,
            }) for f in puzzle.puzzlefile_set.filter(slug__isnull=False)
        }
        files = {**event_files, **puzzle_files}  # Puzzle files with matching slugs override hunt counterparts

        text = Template(puzzle.runtime.create(puzzle.options).evaluate(
            puzzle.content,
            data.tp_data,
            data.up_data,
            data.t_data,
            data.u_data,
        )).safe_substitute(**files)

        flavour = Template(puzzle.flavour).safe_substitute(**files)

        ended = request.tenant.end_date < now

        response = TemplateResponse(
            request,
            'hunts/puzzle.html',
            context={
                'answered': answered,
                'admin': request.admin,
                'ended': ended,
                'episode_number': episode_number,
                'hints': hints,
                'puzzle_number': puzzle_number,
                'grow_section': puzzle.runtime.grow_section,
                'title': puzzle.title,
                'flavour': flavour,
                'text': text,
                'unlocks': unlocks,
            }
        )

        data.save()

        return response


class SolutionContent(LoginRequiredMixin, TeamMixin, PuzzleUnlockedMixin, View):
    def get(self, request, episode_number, puzzle_number):
        episode, puzzle = utils.event_episode_puzzle(request.tenant, episode_number, puzzle_number)
        admin = rules.is_admin_for_puzzle(request.user, puzzle)

        if request.tenant.end_date > timezone.now() and not admin:
            raise PermissionDenied

        data = models.PuzzleData(request.puzzle, request.team, request.user.profile)

        event_files = {f.slug: f.file.url for f in request.tenant.eventfile_set.filter(slug__isnull=False)}
        puzzle_files = {f.slug: reverse(
            'puzzle_file',
            kwargs={
                'episode_number': episode_number,
                'puzzle_number': puzzle_number,
                'file_path': f.url_path,
            }) for f in puzzle.puzzlefile_set.filter(slug__isnull=False)
        }
        solution_files = {f.slug: reverse(
            'solution_file',
            kwargs={
                'episode_number': episode_number,
                'puzzle_number': puzzle_number,
                'file_path': f.url_path,
            }) for f in puzzle.solutionfile_set.filter(slug__isnull=False)
        }
        files = {**event_files, **puzzle_files, **solution_files}  # Solution files override puzzle files, which override event files.

        text = Template(request.puzzle.soln_runtime.create(request.puzzle.soln_options).evaluate(
            request.puzzle.soln_content,
            data.tp_data,
            data.up_data,
            data.t_data,
            data.u_data,
        )).safe_substitute(**files)

        return HttpResponse(text)


class PuzzleFile(LoginRequiredMixin, TeamMixin, PuzzleUnlockedMixin, View):
    def get(self, request, episode_number, puzzle_number, file_path):
        puzzle_file = get_object_or_404(request.puzzle.puzzlefile_set, url_path=file_path)
        return sendfile(request, puzzle_file.file.path)


class SolutionFile(View):
    def get(self, request, episode_number, puzzle_number, file_path):
        episode, puzzle = utils.event_episode_puzzle(request.tenant, episode_number, puzzle_number)
        admin = rules.is_admin_for_puzzle(request.user, puzzle)

        if request.tenant.end_date > timezone.now() and not admin:
            raise Http404

        solution_file = get_object_or_404(puzzle.solutionfile_set, url_path=file_path)
        return sendfile(request, solution_file.file.path)


class Answer(LoginRequiredMixin, TeamMixin, PuzzleUnlockedMixin, View):
    def post(self, request, episode_number, puzzle_number):
        if not request.admin and request.puzzle.answered_by(request.team):
            return JsonResponse({'error': 'already answered'}, status=422)

        now = timezone.now()

        minimum_time = timedelta(seconds=5)
        try:
            latest_guess = models.Guess.objects.filter(
                for_puzzle=request.puzzle,
                by=request.user.profile
            ).order_by(
                '-given'
            )[0]
        except IndexError:
            pass
        else:
            if latest_guess.given + minimum_time > now:
                return JsonResponse({'error': 'too fast'}, status=429)

        given_answer = request.POST.get('answer', '')
        if given_answer == '':
            return JsonResponse({'error': 'no answer given'}, status=400)

        if request.tenant.end_date < now:
            return JsonResponse({'error': 'event is over'}, status=400)

        data = models.PuzzleData(request.puzzle, request.team)

        last_updated = request.POST.get('last_updated')
        if last_updated and data.tp_data.start_time:
            last_updated = datetime.fromtimestamp(int(last_updated) // 1000, timezone.utc)
            new_hints = request.puzzle.hint_set.filter(
                time__gt=(last_updated - data.tp_data.start_time),
                time__lt=(now - data.tp_data.start_time),
            )
            new_hints = [{'time': str(hint.time), 'text': hint.text} for hint in new_hints]
        else:
            new_hints = []

        # Put answer in DB
        guess = models.Guess(
            guess=given_answer,
            for_puzzle=request.puzzle,
            by=request.user.profile
        )
        guess.save()

        correct = any([a.validate_guess(guess) for a in request.puzzle.answer_set.all()])

        # Build the response JSON depending on whether the answer was correct
        response = {}
        if correct:
            next = request.episode.next_puzzle(request.team)
            if next:
                response['text'] = f'to the next puzzle'
                response['url'] = reverse('puzzle', kwargs={'episode_number': episode_number, 'puzzle_number': next})
            else:
                response['text'] = f'back to {request.episode.name}'
                response['url'] = request.episode.get_absolute_url()
        else:
            all_unlocks = models.Unlock.objects.filter(
                puzzle=request.puzzle
            ).select_related(
                'puzzle'
            ).prefetch_related(
                'unlockanswer_set'
            )

            unlocks = []
            for u in all_unlocks:
                correct_guesses = u.unlocked_by(request.team)
                if not correct_guesses:
                    continue

                guesses = [g.guess for g in correct_guesses]
                # Get rid of duplicates but preserve order
                duplicates = set()
                guesses = [g for g in guesses if not (g in duplicates or duplicates.add(g))]
                unlocks.append({'guesses': guesses,
                                'text': u.text,
                                'new': guess in correct_guesses})

            response['guess'] = given_answer
            response['timeout_length'] = minimum_time.total_seconds() * 1000
            response['timeout_end'] = str(now + minimum_time)
            response['new_hints'] = new_hints
            response['unlocks'] = unlocks
        response['correct'] = str(correct).lower()

        return JsonResponse(response)


class Callback(LoginRequiredMixin, TeamMixin, PuzzleUnlockedMixin, View):
    def post(self, request, episode_number, puzzle_number):
        if request.content_type != 'application/json':
            return HttpResponse(status=415)
        if 'application/json' not in request.META['HTTP_ACCEPT']:
            return HttpResponse(status=406)

        if request.tenant.end_date < timezone.now():
            return JsonResponse({'error': 'event is over'}, status=400)

        data = models.PuzzleData(request.puzzle, request.team, request.user.profile)

        response = HttpResponse(
            request.puzzle.cb_runtime.create(request.puzzle.cb_options).evaluate(
                request.puzzle.cb_content,
                data.tp_data,
                data.up_data,
                data.t_data,
                data.u_data,
            )
        )

        data.save()

        return response


class PuzzleInfo(View):
    """View for translating a UUID "token" into information about a user's puzzle attempt"""
    def get(self, request):
        token = request.GET.get('token')
        if token is None:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Must provide token',
            }, status=400)
        try:
            up_data = models.UserPuzzleData.objects.get(token=token)
        except ValidationError:
            return JsonResponse({
                'result': 'Bad Request',
                'message': 'Token must be a UUID',
            }, status=400)
        except models.UserPuzzleData.DoesNotExist:
            return JsonResponse({
                'result': 'Not Found',
                'message': 'No such token',
            }, status=404)
        user = up_data.user
        team = up_data.team()
        return JsonResponse({
            'result': 'Success',
            'team_id': team.pk,
            'user_id': user.pk,
        })


class AboutView(TemplateView):
    template_name = 'hunts/about.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        admin_team = self.request.tenant.teams.get(is_admin=True)

        files = {f.slug: f.file.url for f in self.request.tenant.eventfile_set.filter(slug__isnull=False)}
        content = Template(self.request.tenant.about_text).safe_substitute(**files)

        admin_members = UserInfo.objects.filter(user__profile__in=admin_team.members.all())
        admin_members = annotate_userinfo_queryset_with_seat(admin_members, self.request.tenant)

        context.update({
            'admins': admin_members,
            'content': content,
            'event_name': self.request.tenant.name,
        })
        return context


class RulesView(TemplateView):
    template_name = 'hunts/rules.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        files = {f.slug: f.file.url for f in self.request.tenant.eventfile_set.filter(slug__isnull=False)}
        content = Template(self.request.tenant.rules_text).safe_substitute(**files)

        context.update({
            'content': content,
            'event_name': self.request.tenant.name,
        })
        return context


class HelpView(TemplateView):
    template_name = 'hunts/help.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        files = {f.slug: f.file.url for f in self.request.tenant.eventfile_set.filter(slug__isnull=False)}
        content = Template(self.request.tenant.help_text).safe_substitute(**files)

        context.update({
            'content': content,
            'event_name': self.request.tenant.name,
        })
        return context


class ExamplesView(TemplateView):
    template_name = 'hunts/examples.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        files = {f.slug: f.file.url for f in self.request.tenant.eventfile_set.filter(slug__isnull=False)}
        content = Template(self.request.tenant.examples_text).safe_substitute(**files)

        context.update({
            'content': content,
            'event_name': self.request.tenant.name,
        })
        return context
