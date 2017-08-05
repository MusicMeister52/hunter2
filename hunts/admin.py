from django import forms
from django.contrib import admin
from django.conf.urls import url
from django.utils.html import format_html
from django.db.models import Count
from nested_admin import \
    NestedModelAdmin, \
    NestedStackedInline, \
    NestedTabularInline
from . import models


def make_textinput(field, db_field, kwdict):
    if db_field.attname == field:
        kwdict['widget'] = forms.Textarea(attrs={'rows': 1})


class AnswerInline(NestedTabularInline):
    model = models.Answer
    fields = ('answer', 'runtime')
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('answer', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class FileInline(NestedTabularInline):
    model = models.PuzzleFile
    extra = 0


class HintInline(NestedTabularInline):
    model = models.Hint
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('text', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class UnlockAnswerInline(NestedStackedInline):
    model = models.UnlockAnswer
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('guess', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class UnlockInline(NestedStackedInline):
    model = models.Unlock
    inlines = [
        UnlockAnswerInline,
    ]
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('text', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


@admin.register(models.Guess)
class GuessAdmin(admin.ModelAdmin):
    read_only_fields = ('correct_current', 'correct_for')


@admin.register(models.Puzzle)
class PuzzleAdmin(NestedModelAdmin):
    ordering = ('episode', 'pk')
    inlines = [
        FileInline,
        AnswerInline,
        HintInline,
        UnlockInline,
    ]
    # TODO: once episode is a ForeignKey make it editable
    list_display = ('the_episode', 'title', 'start_date', 'answers', 'hints', 'unlocks')
    list_display_links = ('title',)
    popup = False

    def get_urls(self):
        # Expose three extra views for editing answers, hints and unlocks without anything else
        urls = super().get_urls()
        urls = [
            url(r'^(?P<puzzle_id>[1-9]\d*)/answers/$', self.onlyinlines_view(AnswerInline)),
            url(r'^(?P<puzzle_id>[1-9]\d*)/hints/$', self.onlyinlines_view(HintInline)),
            url(r'^(?P<puzzle_id>[1-9]\d*)/unlocks/$', self.onlyinlines_view(UnlockInline))
        ] + urls
        return urls

    def onlyinlines_view(self, inline):
        """Construct a view that only shows the given inline"""
        def the_view(self, request, puzzle_id):
            # We use this flag to see if we should hide other stuff
            self.popup = True
            # Only display the given inline
            old_inlines = self.inlines
            self.inlines = (inline,)

            response = self.change_view(request, puzzle_id)

            # Reset
            self.popup = False
            self.inlines = old_inlines

            return response

        # Bind the above function as a method of this class so that it gets self.
        return self.admin_site.admin_view(the_view.__get__(self, self.__class__))

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # TODO prefetch_related?
        # Optimisation: add the counts so that we don't have to perform extra queries for them
        return qs.annotate(
            answer_count=Count('answer', distinct=True),
            hint_num=Count('hint', distinct=True),
            unlock_count=Count('unlock', distinct=True)
        )

    ### The following three methods do nothing if popup is True. This removes everything else from
    ### the form except the inline.
    def get_fields(self, request, obj=None):
        if self.popup:
            return ()

        return super().get_fields(request, obj)

    def has_delete_permission(self, request, obj=None):
        if self.popup:
            return False

        return super().has_delete_permission(request, obj)

    def has_add_permission(self, request):
        if self.popup:
            return False

        return super().has_add_permission(request)

    # Who knows why we can't call this 'episode' but it causes an AttributeError...
    def the_episode(self, obj):
        episode_qs = obj.episode_set
        if episode_qs:
            return episode_qs.get().name

        return '[no episode set]'

    the_episode.short_description = 'episode'

    def answers(self, obj):
        return format_html('<a href="{}/answers/">{}</a>', obj.pk, obj.answer_count)

    def hints(self, obj):
        return format_html('<a href="{}/hints/">{}</a>', obj.pk, obj.hint_num)

    def unlocks(self, obj):
        return format_html('<a href="{}/unlocks/">{}</a>', obj.pk, obj.unlock_count)


@admin.register(models.UserPuzzleData)
class UserPuzzleDataAdmin(admin.ModelAdmin):
    readonly_fields = ('token', )


admin.site.register(models.Annoucement)
admin.site.register(models.Episode)
admin.site.register(models.TeamPuzzleData)
