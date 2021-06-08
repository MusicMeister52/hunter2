# Copyright (C) 2021 The Hunter2 Contributors.
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

from django.db.models.signals import pre_save, post_save, pre_delete, m2m_changed
from django.db.models import Q
from django.dispatch import receiver

from teams.models import Team
from accounts.models import UserProfile
from .. import models


def pre_save_handler(sender):
    def pre_save_decorator(func):
        pre_save.connect(func, sender=sender)
        return func

    return pre_save_decorator


def post_save_handler(sender):
    def post_save_decorator(func):
        post_save.connect(func, sender=sender)
        return func

    return post_save_decorator


def pre_delete_handler(sender):
    def pre_delete_decorator(func):
        pre_delete.connect(func, sender=sender)
        return func

    return pre_delete_decorator


@pre_save_handler(models.Guess)
def save_guess(sender, instance, raw, *args, **kwargs):
    if raw:
        return  # nocover
    guess = instance
    answers = guess.for_puzzle.answer_set.all()

    guess.correct_for = None
    guess.correct_current = True

    for answer in answers:
        if answer.validate_guess(guess):
            guess.correct_for = answer
            break


@post_save_handler(models.Guess)
def saved_guess(sender, instance, raw, created, *args, **kwargs):
    # Progress-related stuff happens post-save so that we can update FKs to the guess
    if raw:
        return  # nocover
    # This should never happen in ordinary use
    # TODO: enforce (after removing `get_correct_for`?)
    if not created:
        return  # nocover
    guess = instance
    answers = guess.for_puzzle.answer_set.all()
    progress, _ = models.TeamPuzzleProgress.objects.get_or_create(
        team=guess.by_team, puzzle=guess.for_puzzle
    )
    unlocks = guess.for_puzzle.unlock_set.all().prefetch_related('unlockanswer_set').seal()

    if not progress.solved_by_id:
        for answer in answers:
            if answer.validate_guess(guess):
                progress.solved_by = guess
                progress.save()
                break

    for unlock in unlocks:
        for unlockanswer in unlock.unlockanswer_set.all():
            if unlockanswer.validate_guess(guess):
                models.TeamUnlock(
                    team_puzzle_progress=progress, unlockanswer=unlockanswer, unlocked_by=guess
                ).save()


@post_save_handler(models.Answer)
def saved_answer(sender, instance, raw, created, *args, **kwargs):
    if raw:
        return  # nocover
    answer = instance
    puzzle = answer.for_puzzle
    puzzle_answers = list(puzzle.answer_set.exclude(pk=answer.pk))
    puzzle_answers.append(answer)

    guesses = models.Guess.objects.filter(
        Q(for_puzzle=puzzle),
        Q(correct_for__isnull=True) | Q(correct_for=answer)
    )
    guesses.update(correct_for=None)
    guesses.evaluate_correctness(puzzle_answers)
    models.TeamPuzzleProgress.objects.filter(puzzle=puzzle).reevaluate()


@pre_delete_handler(models.Answer)
def deleted_answer(sender, instance, *args, **kwargs):
    answer = instance
    puzzle = answer.for_puzzle
    puzzle_answers = list(puzzle.answer_set.exclude(pk=answer.pk))
    guesses = models.Guess.objects.filter(
        for_puzzle=puzzle,
        correct_for=answer
    ).order_by('given').seal()
    guesses.update(correct_current=False)
    guesses.evaluate_correctness(puzzle_answers)

    models.TeamPuzzleProgress.objects.filter(puzzle=puzzle).reevaluate()


@post_save_handler(models.UnlockAnswer)
def saved_unlockanswer(sender, instance, raw, *args, **kwargs):
    if raw:
        return  # nocover
    unlockanswer = instance
    unlock = unlockanswer.unlock
    puzzle = unlock.puzzle

    progresses = {tpp.team_id: tpp for tpp in models.TeamPuzzleProgress.objects.filter(puzzle=puzzle).seal()}
    guesses = models.Guess.objects.filter(for_puzzle=puzzle).seal()
    models.TeamUnlock.objects.filter(unlockanswer=unlockanswer).delete()
    for guess in guesses:
        if unlockanswer.validate_guess(guess):
            tpp = progresses[guess.by_team_id]
            models.TeamUnlock(team_puzzle_progress=tpp, unlockanswer=unlockanswer, unlocked_by=guess).save()


# Invalidate the cache of a guess's team when the team members change.
@receiver(m2m_changed, sender=Team.members.through)
def members_changed(sender, instance, action, pk_set, **kwargs):
    if action == 'post_add':
        users = UserProfile.objects.filter(pk__in=pk_set)
        guesses = models.Guess.objects.filter(by__in=users)
        guesses.update(by_team=instance, correct_current=False)
