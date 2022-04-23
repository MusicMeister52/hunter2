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
from datetime import timedelta
from urllib.parse import urlsplit, urlunsplit

from django.contrib.sites.models import Site
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic.base import RedirectView
from django.views.generic import TemplateView
from django.utils.safestring import mark_safe
from formtools.wizard.views import NamedUrlSessionWizardView

from events.models import Domain, Event, Theme
from .forms import EventForm, SiteForm
from .models import Configuration
from .utils import wwwize

SETUP_FORMS = [
    ('site', SiteForm),
    ('event', EventForm),
    # ('subdomain', SubdomainForm),
]

# SETUP_TEMPLATES = {
#     'site':  'setup/site.html',
#     'event': 'setup/event.html',
# }


class SetupWizardView(NamedUrlSessionWizardView):
    template_name = 'setup/setup.html'

    def get_form_instance(self, step):
        if step == 'site':
            # We should just be updating the "example.com" default site so pass the instance to update.
            return Site.objects.get()
        else:
            return super().get_form_instance(step)

    # def get_template_names(self):
    #     return [SETUP_TEMPLATES[self.steps.current]]

    def done(self, form_list, form_dict, **kwargs):

        site = form_dict['site'].save()

        # Just create a default theme
        theme = Theme(name="Default Theme")
        theme.save()

        # Save the event that was created
        event_form = form_dict['event']
        event_name = event_form.cleaned_data["name"]
        event_subdomain = event_form.cleaned_data["subdomain"]
        event = Event(
            name=event_name,
            schema_name=event_subdomain,
            theme=theme,
            end_date=str(timezone.now() + timedelta(days=5)),
            current=True
        )
        event.save()

        domain = Domain(domain='.'.join([event_subdomain, site.domain]), tenant=event)
        domain.save()

        return redirect("/")


class DefaultEventView(RedirectView):
    def get_redirect_url(self, *args, **kwargs):
        try:
            event = Event.objects.get(current=True)
            domain = event.domains.first()
            uri = self.request.build_absolute_uri(self.uri)
            components = urlsplit(uri)
            try:
                port = components.netloc.split(':')[1]
                netloc = f'{domain.domain}:{port}'
            except IndexError:
                netloc = domain.domain
            return urlunsplit(components[:1] + (netloc,) + components[2:])
        except Event.DoesNotExist as e:
            # Before we indicate there is no current event, check the site has been setup correctly.
            # if not, we want to indicate that error first (as it's a pain to catch elsewhere).
            site = Site.objects.get()
            if site.domain == "example.com" and site.name == "example.com":
                return wwwize("/setup", self.request)
                #raise ImproperlyConfigured("Site setup has not been performed (see README.md)")

            # Indicate that the event does not exist.
            raise Event.DoesNotExist("Event has not been created (see README.md)") from e


class DefaultIndexView(DefaultEventView):
    uri = '/'


class DefaultAdminView(DefaultEventView):
    uri = '/admin'


class PrivacyView(TemplateView):
    template_name = "privacy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['privacy_policy'] = mark_safe(Configuration.get_solo().privacy_policy)
        return context
