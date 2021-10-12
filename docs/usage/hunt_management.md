# Running a Hunt

Hunter 2 offers an array of tools to help monitor the progress of teams during the hunt in order to check for
issues and render assistance if required.

This guide assumes you are an admin (that is, your Django user is *staff* and you are on a team whose role is "Admin" or
"Author") and have navigated to the admin site by clicking the button or going directly to the `/admin/` URL.

## Create/Edit

The *Create/Edit* link takes you to the Django admin, which is introduced in the [Getting Started](Creating your First Hunt)
guide.
Most objects that feature in the hunt can be edited here, though it should be rare you need to do anything outside the
Event, Episode, Puzzle and Announcement sections.

### Announcements

Of these objects, the getting started tutorial covers the first three, but there may be times when you need to
send an announcement to everyone taking part, or everyone on a particular puzzle - to announce a winner,
link a stream or point out an error.

Choose the type of announcement (which affects the style) and a title. Optionally you can choose a puzzle, in which
case the announcement will only appear on that puzzle. The title and message will be displayed at the top
of the page. HTML may be used in the title and message body, but be aware they are going to be wrapped in
a `<h2>` and a `<p>` tag respectively.

## Progress

```{figure} img/admin_progress.png
:width: 1200
:alt: Progress page featuring several teams' progress

The Progress Page
```

The Progress Page gives you an overview of the progress of the whole hunt. Each team's progress on each puzzle is
visible here, though there are filters to help cut this down.

### Interpretation

Open the "Filters & Help" section at the top and have a look at the key on the right-hand side. Each combination of
team and puzzle will have an icon resembling one in the key. While the team is working on the puzzle, the red pie-chart
will fill up as they enter guesses and fade out if they stop guessing. When a team solves a puzzle, the icon changes
to indicate this. Hovering the mouse over an icon gives some more information.

### Usage

```{figure} img/admin_progress_filters.png
:width: 1200
:alt: Progress page featuring a sensible set of filters

The Progress Page: Filters and Help
```

The aim of the Progress Page, beyond letting admins see how things are going, is to make it possible to select a
segment of the teams working on the hunt to prioritise for help. You might want to focus on everyone who has solved
fewer than four puzzles, everyone who hasn't made a guess between one and two hours ago, or everyone who's got between
two and five puzzles open who has no hints scheduled on their open puzzles and who haven't guessed more than 100 times.

The list is sorted in order to try and place teams which need more help at the top, therefore teams who have solved
more puzzles are ordered later, and teams who have more unsolved, open puzzles are ordered earlier. Within this ordering
you can also set filters: some experimentation may be necessary to find a filter which works for you, but a good starting
point is to filter to:
1. at least one open puzzle,
2. no scheduled hints,
3. at most a few hours since the latest guess,
4. at least a few minutes since the latest guess.

You can start at the top of the list and enable more until the list has a manageable length. The idea would then be to
investigate each team's situation and use whatever means you wish to help them: finding them in real life and talking
to them, messaging them outside of hunter2, looking at their guesses and adding unlocks for things they've already
entered, or adding timed hints which everyone will see.

To facilitate this, clicking the team's name will take you to their Team Page, covered in the next section.

## Teams

This is simply a list of teams and their members to allow you to search them. Clicking a team name takes you to the
admin page for that team.

Below a list of the team's members is a list of expandable cards containing detailed information about the team's
progress on their unfinished puzzles. Most important is a list of which unlocks and hints they can see, enabling you
to judge approximately how far through the puzzle they have got without asking them.

Below is a list of solved puzzles together with the team's finish time and guesses taken.

## Guesses

```{figure} img/admin_guess_list.png
:width: 1200
:alt: Guesses page showing three guesses by an admin

The Guesses Page
```

This page is a live stream of all guesses submitted by teams. As an organiser you can monitor the stream of guesses
to watch for progress within puzzles, spot issues as they come up such as a variant spelling of an answer not being
marked correct, and quickly perform some common tasks.

The columns are pretty self-explanatory, but note that rows are highlighted different colours if the guess granted the
team an unlock, or was correct.

Linked names (of episodes, puzzles, users or teams) within the list create or update a filter based on the linked thing.
In addition the mini links next to the puzzle name allow you to **E**dit the puzzle or **V**iew it on the player site,
and those next to the guess allow you to add an **A**answer or **U**nlock pre-filled-out with the text of the guess.

## Stats

```{figure} img/admin_stats_completion.png
:width: 1200
:alt: Stats page showing the percentage completion graph

One of the graphs on the Stats page
```

This page presents a number of graphs, giving organisers some more ways of getting an overview of the hunt. The first
two are self-explanatory.

### Progress (scatter)

This renders a point for each team at the time when they solve a particular puzzle.

### Progress (line)

As above, but connects the team's points with a line. This only makes sense for linear episodes.

### Time stuck (per team and puzzle)

For each puzzle, renders a point for each team which has opened but not sovled that puzzle corresponding to how long
ago they opened it.

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
