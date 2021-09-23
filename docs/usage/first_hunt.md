# Creating your first Hunt

## Adding an Event

Before we continue, you should be aware that an "Event" is synonymous with a "Hunt".

If you followed the setup instructions you will already have created an event, but it's worth noting that you
*cannot* create one through the Django admin due to technical limitations (when in the admin interface, you
are restricted to accessing and modifying data within a database schema, and the new Event needs to be in
a different schema.)

If you want to proceed with the default event, which we shall do in the subsequent sections, you can skip the following.

To create an event run:

```shell
docker-compose run --rm app createevent
```

You will be taken through a series of questions on the CLI to specify the required information.
Once you are done, if you haven't already, you will need to ensure that the full domain for the event
(i.e. the domain of the application server with the subdomain you gave when prompted) resolves
to the server.

If you gave your event the subdomain `ev` then you should now be able to login with your superuser
credentials at [http://ev.hunter2.local:8080/](http://ev.hunter2.local:8080/).

Events contain important extra information such as rules and help. These are optional but useful for your participants.

You can set a *maximum team size* according to the kind of event you wish to run, enable *seat assignments* if you are
running a hunt on-location and need to be able to find people, and add discord integration information

## Creating an Admin Team

Load an event page (such as [http://dev.hunter2.local:8080/hunt/](http://dev.hunter2.local:8080/hunt/)) and log in.

To access the hunter2 admin functionality, create a team normally and then use the Django admin interface
at [/admin/crud/](http://dev.hunter2.local:8080/admin/crud/)
to change the team's role to "Admin" or "Author". The normal hunt pages will then have an "Admin site" link at the top.

```{figure} img/crud_admin_team.png
:width: 1200
:alt: Django admin page showing an author team

Altering the admin team
```

```{note}
The difference between the two roles is that there can be at most one author team for an event, and the people
in it are credited as the authors. Both roles have the same permissions.
```

For your fellow admins to also have access to the Django admin interface, you will need to find their user
in it and set them be a Staff Member.

## Adding an Episode

An episode is a collection of puzzles within a hunt: it collects them together logically (and sometimes thematically).
Hunter 2 is designed around multi-episode hunts, which might release one set of puzzles on a Saturday and another set
on Sunday. Even if there are no such natural splits in your hunt, you need to first add an episode.

Navigate to the "Episodes" section of the admin interface and click "Add Episode":

```{figure} img/crud_episode_1.png
:width: 1200
:alt: Django admin page showing a demonstration episode

Adding an episode
```

Enter details for the episode. The *name* could simply be the day the puzzles start, an overarching theme for the puzzles
within it, or something related to the story.

*Flavour text* is optional. Many players skip it, but some enjoy a bit of story!

Before the *start date*, the puzzles in the episode will not be visible except to admins.
Note that episodes have start dates; events have end dates. Episodes and puzzles are available until the entire event
ends, and the event starts whenever the earliest episode starts.

Hunter 2 currently supports two progression models within episodes: linear and *parallel*. Linear means that each puzzle
must be solved before the next one is revealed; parallel means that each puzzle becomes available at a specific time
and can be solved regardless of whether others have been.

The *headstart from* field does not make sense for the first episode in a hunt: if one or more puzzles in an episode grant
headstart, another episode which lists it in "headstart from" will advance its start time for those teams which
have solved those puzzles.

A *winning* episode must be won in order for the site to inform a team that it has finished the hunt.

Again *prequel* episodes will always be blank for the first episode: they must be completed in order for puzzles from
this episode to be available.

Click "save" to return to the episode list and see an overview of the episodes currently in the event.

## Adding a Puzzle

Click the "puzzles" section and "add puzzle".

Select the *episode* that you just created. Note that it is possible to save a puzzle without an episode (which you
may wish to do if you don't want to decide which episode to put it on yet) but it won't be accessible.

Like episodes, puzzles have *flavour text*. Note that the puzzle page includes a pair of HTML comments saying where the
puzzle-relevant content begins and ends: puzzle flavour text will be added outside this. This does not mean no hunt
admin should ever include something relevant in the flavour text, but it does mean that if you include a subtle hint
there and a player looks at the HTML source, they will be quite confused, so think carefully. You can always include
the story within the body of the puzzle.

The *puzzle page content* is the star of the show. By default this is HTML that directly appears on the page during the
hunt, containing whatever constitutes the body (or just the starting-off point) of the puzzle.
No validation of the HTML is done so be careful that it doesn't break anything else on the page. Note you can include
extra `<style>` and `<script>` tags.

```{figure} img/crud_puzzle_1.png
:width: 1200
:alt: Django admin page showing a partially created puzzle

Adding a puzzle
```

*Solution content* can be viewed when the hunt is over. It can also be useful during the hunt so admins can familiarise
themselves with the puzzle.

*Start date* is only relevant for puzzles in parallel episodes: in this case it is the point at which the puzzle appears
and becomes available.

Remember that you can define which episodes an episode receives headstart from? The amount each puzzle gives is defined
in *headstart granted*.

## Adding Static Media

Some puzzles are just words on a webpage, but most include images, audio, video and other media. Click
"add another puzzle file" (you will be adding the first; never mind the wording) and select an image on your local
computer. Enter a "slug" for the file, say "`an_image`". Enter a different filename under *URL filename*, say
"`cow.jpg`". Add the text `<img src="$an_image">` to the puzzle content: once the puzzle is available on the site,
a picture of whatever you uploaded will be visible, and the filename in the URL will be `cow.jpg`.

```{figure} img/crud_puzzle_files.png
:width: 1200
:alt: Django admin page showing a partially created puzzle with a puzzle file

Adding a puzzle file
```

Why so many fields for a simple file upload? Suppose you are writing a puzzle featuring 10 images which must each be
interpreted and yield a word. You might wish to name those image files after the word they yield so that you can keep
track of them while working on the puzzle, but it would be catastrophic if that information were in the URL under which
the file was ultimately served! This allows you to separate it out with minimal effort. Similarly the customisable slug
can allow you to use a more descriptive or different label in the puzzle content.

Note that apart from the filename you specify, puzzle files are served under a predictable URL which requires the user
to have access to the puzzle: if you rely on a file not being guessable for someone who already has that access, make sure
to name it unpredictably.

Solution files are exactly like puzzle files but are only available (even if someone is on the puzzle and guesses the
URL) once the hunt is over.

## Answers and Clues

Every puzzle needs an *answer* to be solvable (note that you are responsible for checking this!) so add one now. There
is no limit to the number of answers a puzzle has; a team can enter a guess which matches any one of them to solve the
puzzle. By default, a guess is compared against answers by stripping any surrounding whitespace and comparing
case-insensitively. Add an answer now, for example, "the correct answer".

Clues come in two flavours: *hints* which appear after a time delay and *unlocks* which appear when something specific
is entered in the answer box.

Add a hint with some text, leave the *start after unlock* field blank and enter a delay of `00:00:10` (i.e. 10 seconds).

Add an unlock with some helpful text like, "have you tried entering the correct answer into the answer box?" For an
unlock to ever appear it needs an *unlock answer* just like a puzzle needs an answer. Add one to the unlock, for example
with the text "melisma".

Now let's return to the *start after unlock* option for hints: this means that the delay for displaying the hint only
starts counting down after the specified unlock has been displayed. At the bottom of the page click "Save and continue
editing" then scroll back down. Now add another hint which starts after the unlock you
just added. It could say, "have you tried entering &lt;i&gt;the correct answer&lt;/i&gt; into the answer box".

```{figure} img/crud_puzzle_files.png
:width: 1200
:alt: Django admin page showing a partially created puzzle with an answer and clues

Adding a puzzle file
```

## Try it out

Click "save and continue editing". (Notice that the warning message has gone away and a button has appeared at the top
right) allowing you to preview the puzzle. Do so now: you should see the content you added with the image you uploaded
(even if the hunt is not started yet, since you are an admin). After 10 seconds, the hint you added should appear.
If you type in the unlock answer you picked and submit it, the unlock should appear and, after a delay, so should the
dependent hint you added.

```{figure} img/puzzle.png
:width: 1200
:alt: Main puzzle page showing the puzzle we have added

Previewing the puzzle
```

## Regexes and Other Advanced Options

Before we leave the puzzle admin page behind, at the top click the "show advanced options" button. Scroll back down
to the answer you added and click the *validator* dropdown: you can change this to "regex" to have incoming guesses
be evaluated against the answer interpreted as a regular expression, or "lua" to have it interpreted as a sandboxed
lua script. The validator configuration can be used to alter the case sensitivity and whitespace stripping.

These options apply equally to unlock answers. Similar options exist for the puzzle content: it can be interpreted as
a URL to be rendered in an IFrame, or a lua script which will return HTML. Note that not all options in these advanced
option drop-downs make sense in all places: test your puzzles if you are unsure! (Test them anyway!)

## Discord Integration

[h2bot](https://gitlab.com/hunter2.app/h2bot) helps run hunts through discord, handling tasks such as creating channels
for teams and receiving requests for help. See its documentation to see how to set it up.
