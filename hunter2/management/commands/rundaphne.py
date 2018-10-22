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


from django.core.management.base import BaseCommand
from daphne.cli import CommandLineInterface


class Command(BaseCommand):
    help = "Runs this project as an ASGI module in Daphne."

    def add_arguments(self, parser):
        parser.add_argument('-b', '--bind', dest='bind', help='Address to bind to')

    def handle(self, *args, **options):
        CommandLineInterface().run(['--bind', options['bind'], '--verbosity', str(options['verbosity']), '--proxy-headers', 'hunter2.asgi:application'])
