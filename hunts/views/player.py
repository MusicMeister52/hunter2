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
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, RedirectView
from sendfile import sendfile

from accounts.models import UserInfo
from events.utils import annotate_userinfo_queryset_with_seat
from teams.models import TeamRole
from teams.mixins import TeamMixin
from .mixins import EpisodeUnlockedMixin, PuzzleUnlockedMixin
from ..rules import is_admin_for_episode_child
from .. import models, utils

import hunter2


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
            h for h in puzzle.hint_set.filter(start_after=None).order_by('time') if h.unlocked_by(request.team, data)
        ]

        unlocks = []
        for u in puzzle.unlock_set.order_by('text'):
            guesses = u.unlocked_by(request.team)
            if not guesses:
                continue

            guesses = [g.guess for g in guesses]
            # Get rid of duplicates but preserve order
            duplicates = set()
            guesses = [g for g in guesses if not (g in duplicates or duplicates.add(g))]
            unlock_text = mark_safe(u.text)  # nosec unlock text is provided by puzzle admins, we consider this safe
            unlocks.append({
                'compact_id': u.compact_id,
                'guesses': guesses,
                'text': unlock_text,
                'hints': [h for h in u.hint_set.all() if h.unlocked_by(request.team, data)]
            })

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


class SolutionContent(LoginRequiredMixin, TeamMixin, PuzzleUnlockedMixin, View):
    def get(self, request, episode_number, puzzle_number):
        episode, puzzle = utils.event_episode_puzzle(request.tenant, episode_number, puzzle_number)
        admin = is_admin_for_episode_child.test(request.user, puzzle)

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
        admin = is_admin_for_episode_child.test(request.user, puzzle)

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
        if not correct:
            response['guess'] = given_answer
            response['timeout_length'] = minimum_time.total_seconds() * 1000
            response['timeout_end'] = str(now + minimum_time)
        response['correct'] = str(correct).lower()
        response['by'] = request.user.username

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
        author_team = self.request.tenant.teams.get(role=TeamRole.AUTHOR)

        files = {f.slug: f.file.url for f in self.request.tenant.eventfile_set.filter(slug__isnull=False)}
        content = Template(self.request.tenant.about_text).safe_substitute(**files)

        author_members = UserInfo.objects.filter(user__profile__in=author_team.members.all())
        author_members = annotate_userinfo_queryset_with_seat(author_members, self.request.tenant)

        author_verb = 'was' if self.request.tenant.end_date < timezone.now() else 'is'

        context.update({
            'authors': author_members,
            'author_verb': author_verb,
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
