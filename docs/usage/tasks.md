# Other Tasks

## Testing

It is a good idea to put puzzles into hunter2 ahead of time to have them tested, so that people can receive hints and
unlocks as they would during the real event. Admin and author teams can always see the puzzle page for any puzzle -
before the event and regardless of what other puzzles they have solved (note that they will not all be visible through
the player site.)

While iterating on a puzzle design you may want to get more people from the admin team to test it, in which case you
will want to ensure they do not see any old hints, unlocks or guesses from the previous test. To reset their progress,
go to the team page where you will see reset buttons against each puzzle the team has started, and another to reset
their progress on all puzzles:

```{figure} img/admin_team_reset.png
:width: 1200
:alt: Admin team page showing reset buttons

Buttons for resetting progress
```

On clicking a reset button you will be taken to a page like the following:

```{figure} img/admin_team_reset_confirm.png
:width: 1200
:alt: Reset progress page

Confirming whether to reset a team's progress
```

Resetting progress carelessly could cause irreversible data loss and, in the worst case, ruin an event! To discourage
such eventualities, the button is only displayed for non-player teams (note, however, that the feature is still
available - just in case - from the Django admin.) Dire warnings will be displayed if you try to reset progress in
riskier circumstances, but ultimately since there may be a legitimate reason, the decision is left to the admin.

## Anonymisation

You may have a requirement to anonymise user data after a certain time period. This can be achieved with the
`anonymise` management command. It takes as a mandatory argument a date (and optionally time): users who have not logged
in since before that point will be anonymised.

```{note}

Team names and guesses are not anonymised.
```

Example:
```shell-session
$ docker-compose run --rm app anonymise 1 year ago
Starting hunter2_redis_1 ... done
Waiting for database connection...
Anonymise 10 users who last logged in before 2020-11-11 01:20:24+00:00? (yes/no) yes
Done.
```

```{note}

Many date formats are accepted; use ISO8601 if in doubt. Ad-hoc formats will prefer DMY over MDY, even in en-US
locales, due to a limitation of the dateparser library.
```