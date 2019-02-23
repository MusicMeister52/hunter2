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


from django.urls import include, path
from django.views.generic import TemplateView

from . import views

eventadminpatterns = [
    path('bulk_upload/<int:puzzle_id>', views.BulkUpload.as_view(), name='bulk_upload'),
    path('episode_list', views.EpisodeList.as_view(), name='episode_list'),
    path('guesses', views.Guesses.as_view(), name='guesses'),
    path('guesses_content', views.GuessesContent.as_view(), name='guesses_content'),
    path('stats', views.Stats.as_view(), name='stats'),
    path('stats_content/', views.StatsContent.as_view(), name='stats_content'),
    path('stats_content/<int:episode_id>', views.StatsContent.as_view(), name='stats_content'),
]

puzzlepatterns = [
    path('', views.Puzzle.as_view(), name='puzzle'),
    path('an', views.Answer.as_view(), name='answer'),
    path('cb', views.Callback.as_view(), name='callback'),
    path('media/<path:file_path>', views.PuzzleFile.as_view(), name='puzzle_file'),
    path('soln', views.SolutionContent.as_view(), name='solution_content'),
    path('soln/media/<path:file_path>', views.SolutionFile.as_view(), name='solution_file'),
]

episodepatterns = [
    path('', views.EpisodeIndex.as_view(), name='episode_index'),
    path('content', views.EpisodeContent.as_view(), name='episode_content'),
    path('pz/<int:puzzle_number>/', include(puzzlepatterns)),
]

eventpatterns = [
    path('', views.EventIndex.as_view(), name='event'),
    path('about', views.AboutView.as_view(), name='about'),
    path('rules', views.RulesView.as_view(), name='rules'),
    path('help', views.HelpView.as_view(), name='help'),
    path('examples', views.ExamplesView.as_view(), name='examples'),
    path('ep/<int:episode_number>/', include(episodepatterns)),
]

urlpatterns = [
    path(
        r'',
        views.Index.as_view(),
        name='index'
    ),
    path(
        r'faq',
        TemplateView.as_view(template_name='hunts/faq.html'),
        name='faq'
    ),
    path(
        r'help',
        TemplateView.as_view(template_name='hunts/help.html'),
        name='help'
    ),
    path('hunt/', include(eventpatterns)),
    path('huntadmin/', include(eventadminpatterns)),
    path('puzzle_info', views.PuzzleInfo.as_view(), name='puzzle_info'),
]
