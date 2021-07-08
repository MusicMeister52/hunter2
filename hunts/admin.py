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

from functools import partialmethod

from django import forms
from django.contrib import admin
from django.utils.html import format_html
from django.urls import path, reverse
from django.db.models import Count, Sum
from nested_admin import NestedModelAdmin, NestedModelAdminMixin, NestedStackedInline, NestedTabularInline
from ordered_model.admin import OrderedModelAdmin
from rules.contrib.admin import ObjectPermissionsModelAdmin, ObjectPermissionsModelAdminMixin, ObjectPermissionsInlineModelAdminMixin
from webpack_loader.utils import get_files

from . import models
from .forms import AnswerForm


def make_textinput(field, db_field, kwdict):
    if db_field.attname == field:
        kwdict['widget'] = forms.Textarea(attrs={'rows': 1})


@admin.register(models.Answer)
class AnswerAdmin(ObjectPermissionsModelAdminMixin, NestedModelAdmin):
    form = AnswerForm

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('answer', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)

    # Do not show this on the admin index for any user
    def has_module_permission(self, request):
        return False


class AnswerInline(ObjectPermissionsInlineModelAdminMixin, NestedTabularInline):
    model = models.Answer
    fields = ('alter_progress', 'answer', 'runtime', 'options')
    extra = 0
    form = AnswerForm
    alter_progress = False

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('answer', db_field, kwargs)
        make_textinput('options', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class PuzzleFileInline(ObjectPermissionsInlineModelAdminMixin, NestedTabularInline):
    model = models.PuzzleFile
    extra = 0


class SolutionFileInline(ObjectPermissionsInlineModelAdminMixin, NestedTabularInline):
    model = models.SolutionFile
    extra = 0


class HintInline(ObjectPermissionsInlineModelAdminMixin, NestedTabularInline):
    model = models.Hint
    extra = 0

    def get_formset(self, request, obj=None, **kwargs):
        self.parent = obj
        return super().get_formset(request, obj, **kwargs)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(Count('start_after')).order_by('start_after__count', 'start_after', 'time')
        return qs

    @staticmethod
    def start_after_label_from_instance(instance):
        truncated = instance.text[:50] + '…' if len(instance.text) > 50 else instance.text
        return truncated

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('text', db_field, kwargs)
        make_textinput('options', db_field, kwargs)
        formfield = super().formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'start_after':
            # We set the parent property when getting the formset above. It will be None when adding
            # a new puzzle, in which case there will be no unlocks available yet to be selected.
            if self.parent:
                formfield.queryset = self.parent.unlock_set
                formfield.label_from_instance = self.start_after_label_from_instance
            else:
                formfield.queryset = models.Unlock.objects.none()

        return formfield


class UnlockAnswerInline(ObjectPermissionsInlineModelAdminMixin, NestedTabularInline):
    class Form(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['runtime'].widget.attrs['class'] = 'advanced_field'
            self.fields['options'].widget.attrs['class'] = 'advanced_field'

    model = models.UnlockAnswer
    fields = ('guess', 'runtime', 'options')
    readonly_fields = ('unlock',)
    form = Form
    extra = 0

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('guess', db_field, kwargs)
        make_textinput('options', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)


class NewUnlockAnswerInline(UnlockAnswerInline):
    model = models.UnlockAnswer
    extra = 1  # Must be one to support the new_guess param below

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('guess', db_field, kwargs)
        make_textinput('options', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)

    # Extract new_guess parameter and add it to the initial formset data
    def get_formset(self, request, obj=None, **kwargs):
        initial = []
        if request.method == 'GET' and 'new_guess' in request.GET:
            initial.append({
                'guess': request.GET['new_guess']
            })
        formset = super().get_formset(request, obj, **kwargs)
        formset.__init__ = partialmethod(formset.__init__, initial=initial)
        return formset


@admin.register(models.Unlock)
class UnlockAdmin(ObjectPermissionsModelAdminMixin, NestedModelAdmin):
    inlines = [
        NewUnlockAnswerInline,
    ]

    def formfield_for_dbfield(self, db_field, **kwargs):
        make_textinput('text', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)

    # Do not show this on the admin index for any user
    def has_module_permission(self, request):
        return False


class UnlockInline(ObjectPermissionsInlineModelAdminMixin, NestedStackedInline):
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
class PuzzleAdmin(ObjectPermissionsModelAdminMixin, NestedModelAdminMixin, OrderedModelAdmin):
    class Form(forms.ModelForm):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            for field in ('runtime', 'options', 'cb_content', 'cb_runtime', 'cb_options', 'soln_runtime', 'soln_options'):
                if field in self.fields:  # If we're rendering a pop-up, these fields may not be present
                    self.fields[field].widget.attrs['class'] = 'advanced_field'

    form = Form
    change_form_template = 'hunts/admin/change_puzzle.html'
    inlines = [
        PuzzleFileInline,
        SolutionFileInline,
        AnswerInline,
        HintInline,
        UnlockInline,
    ]
    # TODO: once episode is a ForeignKey make it editable
    list_display = (
        'episode', 'title', 'start_date', 'headstart_granted',
        'check_flavour', 'check_solution', 'answers', 'hints', 'unlocks',
        'move_up_down_links'
    )
    list_editable = ('episode', 'start_date', 'headstart_granted')
    list_display_links = ('title',)
    popup = False

    @property
    def media(self):
        parent_media = super().media
        return parent_media + forms.Media(
            css={
                "all": [f['url'] for f in get_files('hunts_admin_crud_puzzle', extension='css')],
            },
            js=[f['url'] for f in get_files('hunts_admin_crud_puzzle', extension='js')],
        )

    def view_on_site(self, obj):
        if obj.episode:
            return obj.get_absolute_url()

        return None

    def get_urls(self):
        info = self.model._meta.app_label, self.model._meta.model_name
        # Expose three extra views for editing answers, hints and unlocks without anything else
        urls = super().get_urls()
        urls = [
            path('<str:puzzle_id>/answers/', self.onlyinlines_view(AnswerInline), name='{}_{}_change_answers'.format(*info)),
            path('<str:puzzle_id>/hints/', self.onlyinlines_view(HintInline), name='{}_{}_change_hints'.format(*info)),
            path('<str:puzzle_id>/unlocks/', self.onlyinlines_view(UnlockInline), name='{}_{}_change_unlocks'.format(*info))
        ] + urls
        return urls

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.attname == 'headstart_granted':
            kwargs['widget'] = forms.TextInput(attrs={'size': '8'})
        make_textinput('options', db_field, kwargs)
        make_textinput('cb_options', db_field, kwargs)
        make_textinput('soln_options', db_field, kwargs)
        return super().formfield_for_dbfield(db_field, **kwargs)

    def onlyinlines_view(self, inline):
        """Construct a view that only shows the given inline"""
        def the_view(self, request, puzzle_id):
            # We use this flag to see if we should hide other stuff
            self.popup = True

            try:
                # Only display the given inline
                old_inlines = self.inlines
                self.inlines = (inline,)

                return self.change_view(request, puzzle_id)

            finally:
                # Reset
                self.popup = False
                self.inlines = old_inlines

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

    check_flavour.short_description = 'flavour?'
    check_flavour.boolean = True

    def check_solution(self, obj):
        return bool(obj.soln_content)

    check_solution.short_description = 'solution?'
    check_solution.boolean = True

    def answers(self, obj):
        return format_html('<a href="{}/answers/">{}</a>', obj.pk, obj.answer_count)

    def hints(self, obj):
        return format_html('<a href="{}/hints/">{}</a>', obj.pk, obj.hint_num)

    def unlocks(self, obj):
        return format_html('<a href="{}/unlocks/">{}</a>', obj.pk, obj.unlock_count)


@admin.register(models.Episode)
class EpisodeAdmin(ObjectPermissionsModelAdminMixin, NestedModelAdmin):
    class Form(forms.ModelForm):
        prequels = forms.ModelMultipleChoiceField(
            queryset=models.Episode.objects.all(),
            required=False,
        )

        class Meta:
            model = models.Episode
            fields = ['name', 'flavour', 'start_date', 'parallel', 'headstart_from', 'winning']

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fields['headstart_from'].queryset = models.Episode.objects.exclude(id__exact=self.instance.id)
            self.fields['prequels'].queryset = models.Episode.objects.exclude(id__exact=self.instance.id)
            if self.instance.pk:
                self.fields['prequels'].initial = self.instance.prequels.values_list('id', flat=True)

        def _save_m2m(self):
            for e in self.cleaned_data['prequels']:
                self.instance.add_parent(e)
            super()._save_m2m()

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

    check_flavour.short_description = 'flavour?'
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
class AnnoucementAdmin(ObjectPermissionsModelAdminMixin, admin.ModelAdmin):
    ordering = ['event', 'puzzle__start_date', 'pk']
    list_display = ('event', 'puzzle', 'type', 'title', 'message', 'posted')
    list_display_links = ('title', )


@admin.register(models.Headstart)
class HeadstartAdmin(ObjectPermissionsModelAdmin):
    pass


admin.site.register(models.TeamPuzzleData)
admin.site.register(models.TeamData)
admin.site.register(models.UserData)
