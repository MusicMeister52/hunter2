# Copyright (C) 2021-2022 The Hunter2 Contributors.
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


from django.http import JsonResponse

from hunter2.models import APIToken


class APITokenRequiredMixin():
    """
    API clients must pass their API token via the Authorization header using the format:
        Authorization: Bearer 12345678-1234-5678-1234-567812345678
    """
    def dispatch(self, request, *args, **kwargs):
        try:
            authorization = request.headers['Authorization']
        except KeyError:
            return JsonResponse({
                'result': 'Unauthorized',
                'message': 'No Authorization header',
            }, status=401)
        try:
            (bearer, token) = authorization.split(' ')
        except ValueError:
            return JsonResponse({
                'result': 'Unauthorized',
                'message': 'Malformed Authorization header',
            }, status=401)
        if bearer != "Bearer":
            return JsonResponse({
                'result': 'Unauthorized',
                'message': 'Malformed Authorization header',
            }, status=401)
        try:
            APIToken.objects.get(token=token)
        except APIToken.DoesNotExist:
            return JsonResponse({
                'result': 'Unauthorized',
                'message': 'Invalid Bearer token',
            }, status=401)
        return super().dispatch(request, *args, **kwargs)
