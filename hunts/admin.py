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


from django import forms
from django.contrib import admin
from django.utils.functional import curry
from django.utils.html import format_html
from django.urls import path, reverse
from django.db.models import Count, Sum
from nested_admin import NestedModelAdmin, NestedModelAdminMixin, NestedStackedInline, NestedTabularInline
from ordered_model.admin import OrderedModelAdmin

from . import models
from .forms import AnswerForm


def make_textinput(field, db_field, kwdict):
    if db_field.attname == field:
        kwdict['widget'] = forms.Textarea(attrs={'rows': 1})


@admin.register(models.Answer)
class AnswerAdmin(NestedModelAdmin):
    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('answer', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)

    # Do not show this on the admin index for any user
    def has_module_permission(self, request):
        return False


class AnswerInline(NestedStackedInline):
    model = models.Answer
    fields = ('alter_progress', 'answer', 'runtime')
    extra = 0
    form = AnswerForm

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('answer', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class PuzzleFileInline(NestedTabularInline):
    model = models.PuzzleFile
    extra = 0


class SolutionFileInline(NestedTabularInline):
    model = models.SolutionFile
    extra = 0


class HintInline(NestedTabularInline):
    model = models.Hint
    ordering = ('time',)
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('text', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class UnlockAnswerInline(NestedTabularInline):
    model = models.UnlockAnswer
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('guess', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class NewUnlockAnswerInline(UnlockAnswerInline):
    model = models.UnlockAnswer
    extra = 1  # Must be one to support the new_guess param below

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('guess', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)

    # Extract new_guess parameter and add it to the initial formset data
    def get_formset(self, request, obj=None, **kwargs):
        initial = []
        if request.method == 'GET' and 'new_guess' in request.GET:
            initial.append({
                'guess': request.GET['new_guess']
            })
        formset = super().get_formset(request, obj, **kwargs)
        formset.__init__ = curry(formset.__init__, initial=initial)
        return formset


@admin.register(models.Unlock)
class UnlockAdmin(NestedModelAdmin):
    inlines = [
        NewUnlockAnswerInline,
    ]

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('text', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)

    # Do not show this on the admin index for any user
    def has_module_permission(self, request):
        return False


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
    list_display = ('for_puzzle', 'guess', 'by_team', 'by', 'given')
    list_display_links = ('guess',)


@admin.register(models.Puzzle)
class PuzzleAdmin(NestedModelAdminMixin, OrderedModelAdmin):
    change_form_template = 'hunts/admin/change_puzzle.html'
    inlines = [
        PuzzleFileInline,
        SolutionFileInline,
        AnswerInline,
        HintInline,
        UnlockInline,
    ]
    # TODO: once episode is a ForeignKey make it editable
    list_display = ('episode', 'title', 'start_date', 'check_flavour', 'headstart_granted', 'answers', 'hints', 'unlocks', 'move_up_down_links')
    list_editable = ('episode', 'start_date', 'headstart_granted')
    list_display_links = ('title',)
    popup = False

    def view_on_site(self, obj):
        try:
            return obj.get_absolute_url()
        except models.Episode.DoesNotExist:
            return None

    def get_urls(self):
        # Expose three extra views for editing answers, hints and unlocks without anything else
        urls = super().get_urls()
        urls = [
            path('<int:puzzle_id>/answers/', self.onlyinlines_view(AnswerInline)),
            path('<int:puzzle_id>/hints/', self.onlyinlines_view(HintInline)),
            path('<int:puzzle_id>/unlocks/', self.onlyinlines_view(UnlockInline))
        ] + urls
        return urls

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.attname == 'headstart_granted':
            kwargs['widget'] = forms.TextInput(attrs={'size': '8'})
        return super().formfield_for_dbfield(db_field, **kwargs)

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
        qs = qs.annotate(
            answer_count=Count('answer', distinct=True),
            hint_num=Count('hint', distinct=True),
            unlock_count=Count('unlock', distinct=True)
        )
        return qs

    # The following three methods do nothing if popup is True. This removes everything else from
    # the form except the inline.

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

    def check_flavour(self, obj):
        return bool(obj.flavour)

    check_flavour.short_description = 'tasty?'
    check_flavour.boolean = True

    def answers(self, obj):
        return format_html('<a href="{}/answers/">{}</a>', obj.pk, obj.answer_count)

    def hints(self, obj):
        return format_html('<a href="{}/hints/">{}</a>', obj.pk, obj.hint_num)

    def unlocks(self, obj):
        return format_html('<a href="{}/unlocks/">{}</a>', obj.pk, obj.unlock_count)


@admin.register(models.Episode)
class EpisodeAdmin(NestedModelAdmin):
    class Form(forms.ModelForm):
        class Meta:
            model = models.Episode
            exclude = ['event']

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['prequels'].queryset = models.Episode.objects.exclude(id__exact=self.instance.id)
            self.fields['headstart_from'].queryset = models.Episode.objects.exclude(id__exact=self.instance.id)

    form = Form
    ordering = ['start_date', 'pk']
    list_display = ('event_change', 'name', 'start_date', 'check_flavour', 'num_puzzles', 'total_headstart')
    list_editable = ('start_date',)
    list_display_links = ('name',)

    def save_model(self, request, obj, form, change):
        obj.event = request.tenant
        super().save_model(request, obj, form, change)

    def view_on_site(self, obj):
        return obj.get_absolute_url()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            puzzles_count=Count('puzzle', distinct=True),
            headstart_sum=Sum('puzzle__headstart_granted'),
        )

    def event_change(self, obj):
        return format_html(
            '<a href="{}">{}</a>',
            reverse('admin:events_event_change', args=(obj.event.pk, )),
            obj.event.name
        )

    event_change.short_descrption = 'event'

    def check_flavour(self, obj):
        return bool(obj.flavour)

    check_flavour.short_description = 'tasty?'
    check_flavour.boolean = True

    def num_puzzles(self, obj):
        return obj.puzzles_count

    num_puzzles.short_description = 'puzzles'

    def total_headstart(self, obj):
        return obj.headstart_sum

    total_headstart.short_description = 'headstart granted'


@admin.register(models.UserPuzzleData)
class UserPuzzleDataAdmin(admin.ModelAdmin):
    readonly_fields = ('token', )


@admin.register(models.Announcement)
class AnnoucementAdmin(admin.ModelAdmin):
    ordering = ['event', 'puzzle__start_date', 'pk']
    list_display = ('event', 'puzzle', 'type', 'title', 'message', 'posted')
    list_display_links = ('title', )


admin.site.register(models.Headstart)
admin.site.register(models.TeamPuzzleData)
