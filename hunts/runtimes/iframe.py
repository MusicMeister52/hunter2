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


from urllib.parse import parse_qs, urlencode, urlparse

from .abstract import AbstractRuntime


class IFrameRuntime(AbstractRuntime):
    def check_script(self, url):
        urlparse(url)

    def evaluate(self, url, team_puzzle_data, user_puzzle_data, team_data, user_data):
        url_parts = urlparse(url)
        query_params = parse_qs(url_parts.query)
        query_params['token'] = user_puzzle_data.token
        url_parts = url_parts._replace(query=urlencode(query_params, doseq=True))
        url = url_parts.geturl()
        return f'<iframe id="runtime" src="{url}"></iframe>'

    def validate_guess(self, validator, guess):
        raise NotImplementedError("IFrameRuntime can not be used for guess validation")
