from datetime import datetime, timedelta
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.utils import timezone
from django.views import View
from subdomains.utils import reverse
from string import Template
from teams.mixins import TeamMixin

from . import models
from . import rules
from . import utils
from .mixins import LazyLoginMixin
from .runtimes.registry import RuntimesRegistry as rr

import events
import teams


class Index(View):
    def get(self, request):
        return TemplateResponse(
            request,
            'hunts/index.html',
        )


class Episode(LazyLoginMixin, TeamMixin, View):
    def get(self, request, episode_number):
        episode = utils.event_episode(request.event, episode_number)
        admin = rules.is_admin_for_episode(request.user, episode)

        if not episode.started(request.team) and not admin:
            return TemplateResponse(
                request,
                'hunts/episodenotstarted.html',
                context={
                    'episode': episode.name,
                    'startdate': episode.start_date - episode.headstart_applied(request.team),
                    'headstart': episode.headstart_applied(request.team),
                }
            )

        # TODO: May need caching of progress to avoid DB load
        if not episode.unlocked_by(request.team):
            return TemplateResponse(
                request, 'hunts/episodelocked.html', status=403
            )

        puzzles = episode.unlocked_puzzles(request.team)

        positions = episode.finished_positions()
        if request.team in positions:
            position = positions.index(request.team)
            if position < 3:
                position = {0: 'first', 1: 'second', 2: 'third'}[position]
            else:
                position += 1
                position = f'in position {position}'
        else:
            position = None

        return TemplateResponse(
            request,
            'hunts/episode.html',
            context={
                'admin': admin,
                'episode': episode.name,
                'flavour': episode.flavour,
                'position': position,
                'episode_number': episode_number,
                'event_id': request.event.pk,
                'puzzles': puzzles,
            }
        )


class Guesses(LoginRequiredMixin, View):
    def get(self, request):
        admin = rules.is_admin_for_event(request.user, request.event)

        if not admin:
            raise PermissionDenied

        return TemplateResponse(
            request,
            'hunts/guesses.html',
        )


class GuessesContent(LoginRequiredMixin, View):
    def get(self, request):
        admin = rules.is_admin_for_event(request.user, request.event)

        if not admin:
            return HttpResponseForbidden()

        episode = request.GET.get('episode')
        puzzle = request.GET.get('puzzle')
        team = request.GET.get('team')

        puzzles = models.Puzzle.objects.filter(episode__event=request.event)
        if puzzle:
            puzzles = puzzles.filter(id=puzzle)
        if episode:
            puzzles = puzzles.filter(episode=episode)

        all_guesses = models.Guess.objects.filter(
            for_puzzle__in=puzzles
        ).order_by(
            '-given'
        )

        if team:
            team = teams.models.Team.objects.get(id=team)
            all_guesses = all_guesses.filter(by__in=team.members.all())

        guess_pages = Paginator(all_guesses, 50)
        page = request.GET.get('page')
        try:
            guesses = guess_pages.page(page)
        except PageNotAnInteger:
            guesses = guess_pages.page(1)
        except EmptyPage:
            guesses = guess_pages.page(guess_pages.num_pages)

        if request.GET.get('highlight_unlocks'):
            for g in guesses:
                unlockanswers = models.UnlockAnswer.objects.filter(unlock__puzzle=g.for_puzzle)
                if any([a.validate_guess(g) for a in unlockanswers]):
                    g.unlocked = True

        return TemplateResponse(
            request,
            'hunts/guesses_content.html',
            context={
                'event_id': request.event.pk,
                'guesses': guesses,
            }
        )


class EventDirect(LoginRequiredMixin, View):
    def get(self, request):
        event = events.models.Event.objects.filter(current=True).get()

        return redirect(
            'event',
            event_id=event.id,
        )


class EventIndex(LoginRequiredMixin, View):
    def get(self, request):

        event = request.event

        episodes = models.Episode.objects \
                                 .filter(event=event.id) \
                                 .filter(start_date__lte=timezone.now()) \

        return TemplateResponse(
            request,
            'events/index.html',
            context={
                'event_title':  event.name,
                'event_id':     event.id,
                'episodes':     list(episodes),
            }
        )


class Puzzle(LoginRequiredMixin, TeamMixin, View):
    def get(self, request, episode_number, puzzle_number):
        episode, puzzle = utils.event_episode_puzzle(
            request.event, episode_number, puzzle_number
        )
        admin = rules.is_admin_for_puzzle(request.user, puzzle)

        # Make the puzzle available on the request object
        request.puzzle = puzzle

        # If episode has not started redirect to episode holding page
        if episode.start_date > timezone.now() and not admin:
            if request.event:
                return redirect(
                    'episode',
                    event_id=request.event.pk,
                    episode_number=episode_number,
                )
            else:
                return redirect('episode', episode_number=episode_number)

        # TODO: May need caching of progress to avoid DB load
        if not puzzle.unlocked_by(request.team):
            return TemplateResponse(
                request, 'hunts/puzzlelocked.html', status=403
            )

        data = models.PuzzleData(puzzle, request.team, request.user.profile)

        if not data.tp_data.start_time:
            data.tp_data.start_time = timezone.now()

        answered = bool(puzzle.answered_by(request.team))
        hints = [
            h for h in puzzle.hint_set.all() if h.unlocked_by(request.team, data)
        ]
        unlocks = [
            {
                'guesses': u.unlocked_by(request.team),
                'text': u.text
            }
            for u in puzzle.unlock_set.all()
        ]
        unlocks = [u for u in unlocks if len(u['guesses'])]

        files = {f.slug: f.file.url for f in puzzle.puzzlefile_set.all()}

        text = Template(rr.evaluate(
            runtime=puzzle.runtime,
            script=puzzle.content,
            team_puzzle_data=data.tp_data,
            user_puzzle_data=data.up_data,
            team_data=data.t_data,
            user_data=data.u_data,
        )).safe_substitute(**files)

        response = TemplateResponse(
            request,
            'hunts/puzzle.html',
            context={
                'answered': answered,
                'admin': admin,
                'hints': hints,
                'title': puzzle.title,
                'flavour': puzzle.flavour,
                'text': text,
                'unlocks': unlocks,
            }
        )

        data.save()

        return response


class Answer(LoginRequiredMixin, TeamMixin, View):
    def post(self, request, episode_number, puzzle_number):
        episode, puzzle = utils.event_episode_puzzle(
            request.event, episode_number, puzzle_number
        )

        minimum_time = timedelta(seconds=5)
        try:
            latest_guess = models.Guess.objects.filter(
                for_puzzle=puzzle,
                by=request.user.profile
            ).order_by(
                '-given'
            )[0]
        except IndexError:
            pass
        else:
            if latest_guess.given + minimum_time > timezone.now():
                return JsonResponse({'error': 'too fast'}, status=429)

        data = models.PuzzleData(puzzle, request.team)

        last_updated = request.POST.get('last_updated')
        if last_updated and data.tp_data.start_time:
            last_updated = datetime.fromtimestamp(int(last_updated) // 1000, timezone.utc)
            new_hints = puzzle.hint_set.filter(
                time__gt=(last_updated - data.tp_data.start_time),
                time__lt=(timezone.now() - data.tp_data.start_time),
            )
            new_hints = [{'time': str(hint.time), 'text': hint.text} for hint in new_hints]
        else:
            new_hints = []

        # Gather together unlocks. Need to separate new and old ones for display.
        all_unlocks = models.Unlock.objects.filter(puzzle=puzzle)
        locked_unlocks = []
        unlocked_unlocks = []
        for u in all_unlocks:
            correct_guesses = u.unlocked_by(request.team)
            if correct_guesses:
                unlocked_unlocks.append(
                    {
                        'guesses': [g.guess for g in correct_guesses],
                        'text': u.text
                    })
            else:
                locked_unlocks.append(u)

        # Put answer in DB
        given_answer = request.POST['answer']
        guess = models.Guess(
            guess=given_answer,
            for_puzzle=puzzle,
            by=request.user.profile
        )
        guess.save()

        correct = any([a.validate_guess(guess) for a in puzzle.answer_set.all()])

        # Build the response JSON depending on whether the answer was correct
        response = {}
        if correct:
            next = episode.next_puzzle(request.team)
            if next:
                response['url'] = reverse('puzzle', subdomain=request.META['HTTP_HOST'],
                                          kwargs={'event_id': request.event.pk,
                                                  'episode_number': episode_number,
                                                  'puzzle_number': next})
            else:
                response['url'] = reverse('episode', subdomain=request.META['HTTP_HOST'],
                                          kwargs={'event_id': request.event.pk,
                                                  'episode_number': episode_number}, )
        else:
            response['guess'] = given_answer
            response['timeout'] = str(timezone.now() + minimum_time)
            response['new_hints'] = new_hints
            response['old_unlocks'] = unlocked_unlocks
            unlocks = [u for u in locked_unlocks if any([a.validate_guess(guess) for a in u.unlockanswer_set.all()])]
            response['new_unlocks'] = [u.text for u in unlocks]
        response['correct'] = str(correct).lower()

        return JsonResponse(response)


class Callback(LoginRequiredMixin, TeamMixin, View):
    def post(self, request, episode_number, puzzle_number):
        if request.content_type != 'application/json':
            return HttpResponse(status=415)
        if 'application/json' not in request.META['HTTP_ACCEPT']:
            return HttpResponse(status=406)

        episode, puzzle = utils.event_episode_puzzle(
            request.event, episode_number, puzzle_number
        )

        data = models.PuzzleData(puzzle, request.team, request.user)

        response = HttpResponse(
            rr.evaluate(
                runtime=puzzle.cb_runtime,
                script=puzzle.cb_content,
                team_puzzle_data=data.tp_data,
                user_puzzle_data=data.up_data,
                team_data=data.t_data,
                user_data=data.u_data,
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
