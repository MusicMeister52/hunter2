from django.db import models
from django.core.validators import MinValueValidator
from django.apps import apps

from .fields import SingleTrueBooleanField


class Theme(models.Model):
    name = models.CharField(max_length=255, unique=True)
    script = models.TextField(blank=True)
    style = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Event(models.Model):
    name = models.CharField(max_length=255, unique=True)
    theme = models.ForeignKey(Theme, on_delete=models.CASCADE, related_name='theme')
    current = SingleTrueBooleanField()
    about_text = models.TextField(help_text='Content for the event about page', blank=True)
    rules_text = models.TextField(help_text='Content for the event rules page', blank=True)
    help_text = models.TextField(help_text='Content for the event help page', blank=True)
    examples_text = models.TextField(help_text='Content for the example puzzles for this event', blank=True)
    max_team_size = models.IntegerField(default=0, help_text="Maximum size for a team at this event, or 0 for no limit.", validators=[MinValueValidator(0)])

    def __str__(self):
        return self.name

    def finishing_positions(self):
        Episode = apps.get_model('hunts.Episode')
        winning_episodes = Episode.objects.filter(event=self, winning=True)
        team_times = []
        for ep in winning_episodes:
            team_times += ep.finished_times()
        return team_times

    def team_finishing_position(self, team):
        """Returns the position the team came in, or None if they haven't finished"""
        raise NotImplemented


def event_file_path(instance, filename):
    return 'events/{0}/{1}'.format(instance.event.id, filename)


class EventFile(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    slug = models.SlugField()
    file = models.FileField(upload_to=event_file_path)

    class Meta:
        unique_together = (('event', 'slug'), )
