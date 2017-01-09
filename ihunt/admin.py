from django.contrib import admin
from ihunt import models
from nested_admin import NestedModelAdmin, NestedStackedInline


class AnswerInline(admin.TabularInline):
    model = models.Answer
    fields = ('answer',)
    extra = 0


class HintInline(admin.TabularInline):
    model = models.Hint
    extra = 0


class UnlockGuessInline(NestedStackedInline):
    model = models.UnlockGuess
    extra = 0


class UnlockInline(NestedStackedInline):
    model = models.Unlock
    inlines = [
        UnlockGuessInline,
    ]
    extra = 0


class GuessAdmin(admin.ModelAdmin):
    pass


class PuzzleAdmin(NestedModelAdmin):
    inlines = [
        AnswerInline,
        HintInline,
        UnlockInline,
    ]


class PuzzleSetAdmin(admin.ModelAdmin):
    pass


admin.site.register(models.Guess, GuessAdmin)
admin.site.register(models.Puzzle, PuzzleAdmin)
admin.site.register(models.PuzzleSet, PuzzleSetAdmin)
