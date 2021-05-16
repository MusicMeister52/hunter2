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

import uuid

from django.db import models
from solo.models import SingletonModel


def file_path(instance, filename):
    return f'site/{filename}'


class APIToken(models.Model):
    token = models.UUIDField(default=uuid.uuid4, editable=False)

    def __str__(self):
        return str(self.token)


class File(models.Model):
    slug = models.SlugField(unique=True)
    file = models.FileField(
        upload_to=file_path,
        help_text='The extension of the uploaded file will determine the Content-Type of the file when served',
    )


class Icon(models.Model):
    file = models.ForeignKey(File, on_delete=models.CASCADE)
    size = models.PositiveSmallIntegerField(help_text='The size of the icon (width and height). 0 should be used for scalable (eg. SVG) icons.', unique=True)

    def url(self):
        return self.file.file.url


class Configuration(SingletonModel):
    index_content = models.TextField()
    privacy_policy = models.TextField(blank=True)
    script = models.TextField(blank=True)
    script_file = models.ForeignKey(File, blank=True, null=True, on_delete=models.PROTECT, related_name='+')
    style = models.TextField(blank=True)
    style_file = models.ForeignKey(File, blank=True, null=True, on_delete=models.PROTECT, related_name='+')

    def files_map(self, request):
        if not hasattr(request, 'site_files'):
            request.site_files = {
                f.slug: f.file.url
                for f in File.objects.filter(slug__isnull=False)
            }
        return request.site_files
