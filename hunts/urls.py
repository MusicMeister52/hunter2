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

# The consumers module registers some class methods as signal handlers on import
# Import this explicitly here to ensure this still happens when running under WSGI rather than ASGI
from hunts import consumers as _  # noqa: F401

from . import views

eventadminpatterns = [
    path('', views.admin.AdminIndex.as_view(), name='admin_index'),
    path('bulk_upload/<int:puzzle_id>', views.admin.BulkUpload.as_view(), name='bulk_upload'),
    path('episode_list', views.admin.EpisodeList.as_view(), name='episode_list'),
    path('guesses', views.admin.Guesses.as_view(), name='admin_guesses'),
    path('guesses/list', views.admin.GuessesList.as_view(), name='admin_guesses_list'),
    path('stats', views.admin.Stats.as_view(), name='admin_stats'),
    path('stats_content/', views.admin.StatsContent.as_view(), name='admin_stats_content'),
    path('stats_content/<int:episode_id>', views.admin.StatsContent.as_view(), name='admin_stats_content'),
    path('progress', views.admin.Progress.as_view(), name='admin_progress'),
    path('progress_content', views.admin.ProgressContent.as_view(), name='admin_progress_content'),
    path('teams', views.admin.TeamAdmin.as_view(), name='admin_team'),
    path('teams/<int:team_id>', views.admin.TeamAdminDetail.as_view(), name='admin_team_detail'),
    path('teams/<int:team_id>/content', views.admin.TeamAdminDetailContent.as_view(), name='admin_team_detail_content'),
    path('reset_progress', views.admin.ResetProgress.as_view(), name='reset_progress'),
]

puzzlepatterns = [
    path('', views.player.Puzzle.as_view(), name='puzzle'),
    path('an', views.player.Answer.as_view(), name='answer'),
    path('cb', views.player.Callback.as_view(), name='callback'),
    path('media/<path:file_path>', views.player.PuzzleFile.as_view(), name='puzzle_file'),
    path('soln', views.player.SolutionContent.as_view(), name='solution_content'),
    path('soln/media/<path:file_path>', views.player.SolutionFile.as_view(), name='solution_file'),
]

episodepatterns = [
    path('', views.player.EpisodeIndex.as_view(), name='episode_index'),
    path('content', views.player.EpisodeContent.as_view(), name='episode_content'),
    path('pz/<int:puzzle_number>/', include(puzzlepatterns)),
]

eventpatterns = [
    path('', views.player.EventIndex.as_view(), name='event'),
    path('about', views.player.AboutView.as_view(), name='about'),
    path('examples', views.player.ExamplesView.as_view(), name='examples'),
    path('help', views.player.HelpView.as_view(), name='help'),
    path('rules', views.player.RulesView.as_view(), name='rules'),
    path('stats', views.player.StatsView.as_view(), name='player_stats'),
    path('ep/<int:episode_number>/', include(episodepatterns)),
    path('puzzle/<puzzle_url_id>/', views.player.AbsolutePuzzleView.as_view(), name='puzzle_permalink'),
    path('puzzle/<puzzle_url_id>/<path:path>', views.player.AbsolutePuzzleView.as_view()),
]

urlpatterns = [
    path(
        r'',
        views.player.Index.as_view(),
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
    path('admin/', include(eventadminpatterns)),
    path('puzzle_info', views.player.PuzzleInfo.as_view(), name='puzzle_info'),
]
