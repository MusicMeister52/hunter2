# Copyright (C) 2020 The Hunter2 Contributors.
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


import abc
import inspect
from enum import Enum
from typing import Mapping, Sequence, Tuple, Any

from django.core.cache import caches
from django.template.loader import render_to_string

cache = caches['stats']


class AbstractGenerator(abc.ABC):
    """
    Abstract base class for statistic generators. Generators each provide a fragment of content to be included in the stats page(s).
    """

    @property
    def id(self):
        """
        Default to using the name of the module containing the generator as the generator's ID
        """
        return inspect.getmodule(self.__class__).__name__.split('.')[-1]

    @property
    @abc.abstractmethod
    def title(self):
        """
        Subclasses should override this method to specify the title for the section in the stats page.
        """
        raise NotImplementedError("Abstract Generator does not define a title property")

    @property
    @abc.abstractmethod
    def version(self):
        """
        Subclasses should override this method to specify the version of the generator, used to determine validity of cached data.
        """
        raise NotImplementedError("Abstract Generator does not define a version property")

    @property
    def template(self):
        return f'hunts/stats/{self.id}.html'

    @property
    @abc.abstractmethod
    def schema(self):
        """
        Subclasses should override this method to specify the schema for the data returned by the generator.
        While this schema is not validated at runtime it's highly encouraged to use this to write tests for the generator.
        At some point in the future we may add tests which iterate all the generators with some real-looking data and test the schemas.
        """
        raise NotImplementedError("Abstract Generator does not define a schema property")

    def __init__(self, event, episode=None):
        self.event = event
        self.episode = episode

    @abc.abstractmethod
    def generate(self):
        """
        Subclasses should override this method to define any preprocessing that should be performed once for this statistic.
        This data is cached forever in the stats cache to allow for quick page loads in the future.
        """
        raise NotImplementedError("Abstract Generator does not define a generate method")

    @staticmethod
    def _add_extra(
        data_map: Mapping[str, Mapping[str, Any]],
        data_list: Sequence[Tuple[int, str, Any]],
        identity: Any, datum_key: str
    ) -> Sequence[Tuple[int, str, Any]]:
        """
        Returns the provided data list with extra data relevant to the viewer appended.

        Keyword arguments:
            data_map  -- Data for all entities in a mapping indexed by their ID. Each entry is a mapping containing, at least, 'position' and datum_key
            data_list -- Data which will be rendered as a sequence of tuples of the form (position, name, datum).
            identity  -- The entity relating to the viewer which should be included if there is data for it. It must implement the `get_display_name` method.
            datum_key -- The key for the element within the indexed data to be copied into the list.
        """
        if identity is not None:
            try:
                identity_data = data_map[identity.id]
                if identity_data['position'] not in (d[0] for d in data_list):
                    data_list += [
                        (identity_data['position'], identity.get_display_name(), identity_data[datum_key]),
                    ]
            except KeyError:
                pass
        return data_list

    def cache_key(self):
        class KeyType(Enum):
            EPISODE = 'E'

        key_parts = [
            self.__class__.__name__,
            str(self.event.id),
        ]
        if self.episode:
            key_parts.append(KeyType.EPISODE, self.episode.id)
        # Key separated by % since this is invalid in lots of identifiers including Python class names
        return '%'.join(key_parts)

    def data(self):
        key = self.cache_key()
        data = cache.get(key, version=self.version)
        if data is None:
            try:
                data = self.generate()
                cache.set(key, data)
            except ValueError:
                cache.set(key, False)
        return data

    def render_data(self, data, team=None, user=None):
        return render_to_string(self.template, context=data)

    def render(self, team=None, user=None):
        data = self.data()
        return self.render_data(data, team=team, user=user) if data else None
