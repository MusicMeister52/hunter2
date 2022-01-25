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
import dateutil
from django.core.management import BaseCommand, CommandError

import dateparser

from accounts.models import User


class Command(BaseCommand):
    help = "Anonymise data for users who haven't logged in recently"

    def add_arguments(self, parser):
        parser.add_argument(
            'last_login_before',
            nargs='+',
            type=str,
            help='Users who have logged in after this will not be anonymised. Accepts any format accepted by '
                 'the dateparser library.',
        )
        parser.add_argument(
            '-y', '--yes',
            dest='yes',
            action='store_true',
            help="Don't prompt for confirmation",
        )
        parser.add_argument(
            '--dry-run',
            dest='dryrun',
            action='store_true',
            help="Don't do anything, but print what would be done in a real run"
        )

    def handle(self, *args, **options):
        dryrun = options['dryrun']
        yes = dryrun or options['yes']
        last_login = ' '.join(options['last_login_before'])
        until = self.parse_date(last_login)

        users = User.objects.filter(last_login__lte=until)
        proceed = self.get_confirmation(yes, users, until)
        if dryrun:
            self.stdout.write('Dry run: nothing to do.')
            return

        if proceed:
            users.anonymise()
            self.stdout.write('Done.')
        else:
            self.stdout.write('Aborting.')

    @staticmethod
    def parse_date(last_login):
        try:
            # try to parse the value as an ISO8601 datetime first
            return dateutil.parser.isoparse(last_login)
        except ValueError:
            pass

        # If that fails, try dateparser, which supports many date formats including relative dates
        # By default it will try MDY if the language is not clearly something other than English - bypass that
        until = dateparser.parse(last_login, settings={
            'DATE_ORDER': 'DMY',
            'PREFER_LOCALE_DATE_ORDER': False,
            'RETURN_AS_TIMEZONE_AWARE': True,
        })
        if until is None:
            raise CommandError(f'"{until}" is not a valid date')
        return until

    def get_confirmation(self, yes, users, until):
        until_str = until.isoformat(' ', 'seconds')
        if yes:
            self.stdout.write(f'Anonymising {len(users)} users who last logged in before {until_str}...')
            return True

        while True:
            proceed = input(f'Anonymise {len(users)} users who last logged in before {until_str}? (yes/no) ')
            try:
                return {'yes': True, 'no': False}[proceed.lower()]
            except KeyError:
                continue
