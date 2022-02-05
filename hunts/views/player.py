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

from string import Template

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, RedirectView
from django_sendfile import sendfile

from events.utils import annotate_user_queryset_with_seat
from teams.models import Team, TeamRole
from teams.permissions import is_admin_for_event
from .mixins import EpisodeUnlockedMixin, EventMustBeOverMixin, PuzzleUnlockedMixin
from .. import models, utils
from ..stats import __all__ as stats_generators


class Index(TemplateView):
    template_name = 'hunts/index.html'

    def get_context_data(self, **kwargs):
        return {
            'content': self.request.tenant.index_text,
        }


class EpisodeIndex(LoginRequiredMixin, EpisodeUnlockedMixin, View):
    def get(self, request, episode_number):
        return redirect(request.episode.get_absolute_url(), permanent=True)


class EpisodeContent(LoginRequiredMixin, EpisodeUnlockedMixin, View):
    def get(self, request, episode_number):
        now = timezone.now()
        headstart = request.episode.headstart_applied(request.team)

        puzzles = request.episode.puzzle_set.all().annotate_solved_by(request.team).seal()
        if request.episode.parallel or request.episode.event.end_date < now:
            started_puzzles = [pz for pz in puzzles if pz.started_for(request.team, headstart=headstart, now=now)]
            available = started_puzzles
            try:
                upcoming_puzzle = puzzles[len(started_puzzles)]
            except IndexError:
                upcoming_puzzle = None
        else:
            available = []
            upcoming_puzzle = None
            # Every started puzzle is available until the first unsolved puzzle is encountered.
            # that puzzle is also available. If the last available puzzle is solved, then, if there
            # is another unstarted puzzle, that is the *upcoming* puzzle.
            for p in puzzles:
                if p.started_for(request.team, headstart=headstart, now=now):
                    available.append(p)
                elif not p.solved:
                    upcoming_puzzle = p
                if not p.solved:
                    break
        upcoming_time = upcoming_puzzle.start_date - headstart if upcoming_puzzle and upcoming_puzzle.start_date else None

        positions = request.episode.finished_positions()
        if request.team in positions:
            position = positions.index(request.team)
            position, position_text = utils.position_for_display(position)
        else:
            position = None
            position_text = None

        files = request.tenant.files_map(request)
        flavour = Template(request.episode.flavour).safe_substitute(**files)

        return TemplateResponse(
            request,
            'hunts/episode.html',
            context={
                'episode': request.episode.name,
                'flavour': flavour,
                'position': position,
                'position_text': position_text,
                'episode_number': episode_number,
                'puzzles': available,
                'headstart': headstart,
                'upcoming_time': upcoming_time,
                'upcoming_under_1_minute': upcoming_time is not None and (
                    timedelta(0) < upcoming_time - now < timedelta(minutes=1)
                ),
                'upcoming_in_next_day': upcoming_time is not None and (
                    timedelta(0) < upcoming_time - now < timedelta(hours=24)
                ),
            }
        )


class EventDirect(LoginRequiredMixin, View):
    def get(self, request):
        return redirect('event')


class EventIndex(LoginRequiredMixin, View):
    def get(self, request):

        event = request.tenant

        positions = utils.finishing_positions(event)
        if request.team in positions:
            position = positions.index(request.team)
            position, position_text = utils.position_for_display(position)
        else:
            position = None
            position_text = None

        episodes = [
            e for e in
            models.Episode.objects.filter(event=event.id).order_by('start_date')
            if e.started_for(request.team)
        ]

        # Annotate the episodes with their position in the event.
        for episode in episodes:
            episode.index = episode.get_relative_id()

        return TemplateResponse(
            request,
            'hunts/event.html',
            context={
                'event_title':   event.name,
                'episodes':      list(episodes),
                'position':      position,
                'position_text': position_text
            }
        )


class Puzzle(LoginRequiredMixin, PuzzleUnlockedMixin, View):
    def get(self, request, episode_number, puzzle_number):
        puzzle = request.puzzle

        data = models.PuzzleData(puzzle, request.team, request.user.profile)

        progress, _ = request.puzzle.teampuzzleprogress_set.select_related(
            'solved_by',
            'solved_by__by',
            'team',
        ).prefetch_related(
            'guesses',
            'puzzle__hint_set__start_after__unlockanswer_set',
            Prefetch(
                'teamunlock_set',
                queryset=models.TeamUnlock.objects.select_related(
                    'unlocked_by',
                    'unlockanswer',
                    'unlockanswer__unlock',
                )
            ),
        ).seal().get_or_create(puzzle=request.puzzle, team=request.team)

        now = timezone.now()

        if not progress.start_time:
            progress.start_time = now
            progress.save()

        correct_guess = progress.solved_by
        hints = progress.hints()

        unlocks = []
        unlocks_to_guesses = progress.unlocks_to_guesses()

        for u in unlocks_to_guesses:
            guesses = [g.guess for g in unlocks_to_guesses[u]]
            # Get rid of duplicates but preserve order
            duplicates = set()
            guesses = [g for g in guesses if not (g in duplicates or duplicates.add(g))]
            unlock_text = mark_safe(u.text)  # nosec unlock text is provided by puzzle admins, we consider this safe
            unlocks.append({
                'compact_id': u.compact_id,
                'guesses': guesses,
                'text': unlock_text,
                'hints': hints[u.id],
            })

        files = puzzle.files_map(request)
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
                'answered': correct_guess,
                'admin': request.admin,
                'ended': ended,
                'episode_name': request.episode.name,
                'episode_number': episode_number,
                'hints': hints[None],
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


class AbsolutePuzzleView(RedirectView):
    def get_redirect_url(self, puzzle_url_id, path=None):
        try:
            puzzle = models.Puzzle.objects.get(url_id=puzzle_url_id)
        except models.Puzzle.DoesNotExist as e:
            raise Http404 from e

        if puzzle.episode is None:
            raise Http404

        if path is None:
            return puzzle.get_absolute_url()
        else:
            return puzzle.get_absolute_url() + path


class SolutionContent(LoginRequiredMixin, PuzzleUnlockedMixin, View):
    def get(self, request, episode_number, puzzle_number):
        episode, puzzle = utils.event_episode_puzzle(request.tenant, episode_number, puzzle_number)
        admin = is_admin_for_event.test(request.user, request.tenant)

        if request.tenant.end_date > timezone.now() and not admin:
            raise PermissionDenied

        data = models.PuzzleData(request.puzzle, request.team, request.user.profile)

        puzzle_files = puzzle.files_map(request)
        solution_files = {f.slug: reverse(
            'solution_file',
            kwargs={
                'episode_number': episode_number,
                'puzzle_number': puzzle_number,
                'file_path': f.url_path,
            }) for f in puzzle.solutionfile_set.filter(slug__isnull=False)
        }
        files = {  # Solution files override puzzle files, which override event files.
            **puzzle_files,
            **solution_files,
        }

        text = Template(request.puzzle.soln_runtime.create(request.puzzle.soln_options).evaluate(
            request.puzzle.soln_content,
            data.tp_data,
            data.up_data,
            data.t_data,
            data.u_data,
        )).safe_substitute(**files)

        return HttpResponse(text)


class PuzzleFile(LoginRequiredMixin, PuzzleUnlockedMixin, View):
    def get(self, request, episode_number, puzzle_number, file_path):
        puzzle_file = get_object_or_404(request.puzzle.puzzlefile_set, url_path=file_path)
        return sendfile(request, puzzle_file.file.path, attachment_filename=False)


class SolutionFile(View):
    def get(self, request, episode_number, puzzle_number, file_path):
        episode, puzzle = utils.event_episode_puzzle(request.tenant, episode_number, puzzle_number)
        admin = is_admin_for_event.test(request.user, request.tenant)

        if request.tenant.end_date > timezone.now() and not admin:
            raise Http404

        solution_file = get_object_or_404(puzzle.solutionfile_set, url_path=file_path)
        return sendfile(request, solution_file.file.path, attachment_filename=False)


class Answer(LoginRequiredMixin, PuzzleUnlockedMixin, View):
    def post(self, request, episode_number, puzzle_number):
        if not request.admin and request.puzzle.answered_by(request.team):
            return JsonResponse({'error': 'already answered'}, status=422)

        now = timezone.now()

        minimum_time = timedelta(seconds=5)
        if models.Guess.objects.filter(
            for_puzzle=request.puzzle,
            by=request.user.profile,
            given__gt=now - minimum_time
        ).exists():
            return JsonResponse({'error': 'too fast'}, status=429)

        given_answer = request.POST.get('answer', '')
        if given_answer == '':
            return JsonResponse({'error': 'no answer given'}, status=400)

        if len(given_answer) > 512:
            return JsonResponse({'error': 'answer too long'}, status=400)

        if request.tenant.end_date < now:
            return JsonResponse({'error': 'event is over'}, status=400)

        # Put answer in DB
        guess = models.Guess(
            guess=given_answer,
            for_puzzle=request.puzzle,
            by=request.user.profile
        )
        guess.save()

        # progress record is updated by signals on save - get that info now.
        try:
            correct = guess.is_correct
        except AttributeError:
            correct = False

        # Build the response JSON depending on whether the answer was correct
        response = {}
        if not correct:
            response['guess'] = given_answer
            response['timeout_length'] = minimum_time.total_seconds() * 1000
            response['timeout_end'] = str(now + minimum_time)
        response['correct'] = str(correct).lower()
        response['by'] = request.user.username

        return JsonResponse(response)


class Callback(LoginRequiredMixin, PuzzleUnlockedMixin, View):
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
        author_team = None
        try:
            author_team = self.request.tenant.teams.get(role=TeamRole.AUTHOR)
        except Team.DoesNotExist:
            pass

        files = self.request.tenant.files_map(self.request)
        content = Template(self.request.tenant.about_text).safe_substitute(**files)

        author_members = []
        if author_team is not None:
            User = get_user_model()
            author_members = User.objects.filter(profile__in=author_team.members.all())
            author_members = annotate_user_queryset_with_seat(author_members, self.request.tenant)

        author_verb = 'was' if self.request.tenant.end_date < timezone.now() else 'is'

        context.update({
            'authors': author_members,
            'author_verb': author_verb,
            'content': content,
            'end_date': self.request.tenant.end_date,
            'event_name': self.request.tenant.name,
        })
        return context


class RulesView(TemplateView):
    template_name = 'hunts/rules.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        files = self.request.tenant.files_map(self.request)
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

        files = self.request.tenant.files_map(self.request)
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

        files = self.request.tenant.files_map(self.request)
        content = Template(self.request.tenant.examples_text).safe_substitute(**files)

        context.update({
            'content': content,
            'event_name': self.request.tenant.name,
        })
        return context


class StatsView(EventMustBeOverMixin, TemplateView):
    template_name = 'hunts/stats.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        generators = [Generator(event=self.request.tenant) for Generator in stats_generators]

        profile = self.request.user.profile if self.request.user.is_authenticated else None
        renders = {
            g.id: g.render(self.request.team, user=profile)
            for g in generators
        }

        context['stats'] = (
            (g.id, g.title, renders[g.id])
            for g in generators
            if renders[g.id] is not None
        )
        return context
