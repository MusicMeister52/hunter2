# Copyright (C) 2021 The Hunter2 Contributors.
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

import inspect
import re
from importlib import import_module
from pathlib import Path

from docutils import nodes
import django


def setup(app):
    django.setup()
    app.add_config_value('sourcelink_base_url', None, True)
    app.add_role('tree', sourcelink)


linkre = re.compile(r'(?P<text>.*) <(?P<ref>[^:]+(:.+)?)>')


def sourcelink(name, rawtext, text, lineno, inliner, options={}, content=[]):
    """Find a source reference for the input text and return it.

    Syntax supported:
        module.submodule[:object.attribute]
        link text <module.submodule[:object.attribute]>
    """

    # The root directory of the project is the parent of the docs dir
    base_file_path = Path(inliner.document.settings.env.app.srcdir).parent
    base_url = inliner.document.settings.env.app.config.sourcelink_base_url

    match = linkre.match(text)
    if match:
        link_text = match.group('text')
        text = match.group('ref')
    else:
        link_text = text

    if ':' in text:
        module_name, object_name = text.split(':')
        module = import_module(module_name)
        obj = module
        # If we are given module:Class.SubClass.method, we want a reference to method
        for part in object_name.split('.'):
            obj = getattr(obj, part)

        fn = inspect.getsourcefile(obj)
        fn = Path(fn).relative_to(base_file_path)
        source, lineno = inspect.getsourcelines(obj)
        url = base_url + f'{fn}#L{lineno}-{lineno + len(source) - 1}'

        # If there was no explicit label, use the text with . instead of :
        if not match:
            link_text = text.replace(":", ".")
    else:
        module = import_module(text)
        fn = module.__file__
        url = base_url + fn

    node = nodes.reference(rawtext, link_text, refuri=url, **options)
    return [node], []
