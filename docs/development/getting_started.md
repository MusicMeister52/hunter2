Getting Started with Development
===============

This guide assumes you have a working installation.

Overview
--------

### The Services

As a `docker-compose` app, hunter2 comprises several services. The most important are:
* `app` which contains the main django project
* `db` which contains its database
* `webpack` (dev only) which builds and serves JS and CSS
In addition in production and test there are:
* `web` (prod/test only) which is the openresty proxy
* `websocket` (prod/test only) which is the `daphne` server specifically responding to websocket
    requests and running the `consumer` code.

### The Hunter2 Apps

The django project is divided into several apps:

* `hunts`: the main models and logic used in a puzzle hunt
* `events`: everything related to events that is not related to puzzles: timing, event-specific styling, etc
    incorporates the logic used to map subdomains to database schemas, enabling data separation between events
* `teams`: the concept of a team, logic and code to manage them
* `accounts`: models to augment django's auth model
* `hunter2`: a simple app which encapsulates the whole site of a particular instance

Most changes will touch, if not start in, the `hunts` app since it is the main app.

Within each app we follow a fairly standard django app layout with views, urls, models, tests etc.
In addition `factories` defines [factory_boy](https://factoryboy.readthedocs.io/en/stable/)
factories for more-or-less declaratively setting up test scenarios, `consumers` contains
ASGI consumers for handling websockets and `signals` contains signal handlers.

### Running Tests

Run

```
$ docker-compose run --rm app test
```

### Writing Tests

Most of our tests are integration tests which either make use of factories to create models
and then manipulate them, or the django test client to log in and request views. We do almost
no unit testing, and (at the time of writing) no testing which exercises the javascript.

While we would like to improve this at some point, for the time being changes should include
tests of the same kind that we already have: new features and changed behaviour should both
test at least the main aspects of the new behaviour, and bugfixes should include a test which
failed before the introduction of the fix.

### Logic Flow of Hunt Progression

The point of this subsection is to give you a mini overview of several important bits of the application:

Suppose you are at the puzzle page [http://dev.hunter2.local:8080/hunt/ep/1/pz/1](http://dev.hunter2.local:8080/hunt/ep/1/pz/1)
and submit a correct guess.
The page you see was requested via the view at {tree}`hunts.views.player:Puzzle` and the template defines the form
being submitted when the player submits a guess as pointing at [http://dev.hunter2.local:8080/hunt/ep/1/pz/1/an](http://dev.hunter2.local:8080/hunt/ep/1/pz/1/an),
defined in {tree}`hunts.urls` as {tree}`hunts.views.player:Answer`.

A {tree}`Guess <hunts.models:Guess>` is created from the entered text and saved to the database. This triggers the signal handlers in
{tree}`hunts.signals.progress` to which check whether the entered guess was correct. If it was, the
{tree}`TeamPuzzleProgress <hunts.models:TeamPuzzleProgress>` object for the player's team on that puzzle is updated so
that its `solved_by` attribute points to the new guess.

Updating the {tree}`TeamPuzzleProgress <hunts.models:TeamPuzzleProgress>` object triggers the signal handler in
{tree}`hunts.consumers:PuzzleEventWebsocket` to send a notification over the websocket to which the player and all their
teammates will be connected. The notification will indicate that the puzzle has been solved and trigger a redirect to
the next puzzle (if there is one).

Note that the {tree}`hunts.views.player:Answer` view also responds with information about the guess. This is a legacy
system but also serves as a backup in case the websocket dies.

Manual Intervention
-------------------

There may be times when you need to dig into the database or Django ORM to set something up or diagnose an error. In
that case, the preferred way is:

```shell
docker-compose run --rm app shell_plus
```

which launches a `ptpython` shell with all the models and many Django functions and classes already imported.

````{note}
hunter2 uses database schemas to separate the data for different hunts. When you first launch the shell, you will be
using the default `public` schema which contains no hunt-specific data. You will therefore need to *activate the tenant*,
which is simply the Event. For example:
```python3
Event.objects.get().activate()
```
````

The `Factory` classes can be useful during development and manual testing for quickly creating objects.
Check out the [documentation](https://factoryboy.readthedocs.io/en/stable/) for additional usage information, or look
at the automated tests for examples.

You can also use the `dbshell` management command to directly connect to the database, though this is more prone to
breaking things. In that case, note that you will need to set the database's search path to the `schema_name` of the
Event after connecting.

Setting up PyCharm
------------------

Other IDEs are available but we don't know how to set them up. (Let us know if you use one and have a good working
setup) The key in PyCharm is to add an interpreter with the following settings:

```{figure} img/pycharm_interpreter.png
:width: 1200
:alt: Setting up a python interpreter for hunter2 in PyCharm

Setting up an interpreter in PyCharm
```

Note the inclusion of the override `yaml`. This should allow PyCharm to find the packages installed inside the container,
enabling completion. You can then add run configurations with this interpreter to enable interactive debugging and easy
running of individual tests.

Common Tasks
------------

There are several maintainer tools specified (as services) in the `docker-compose.tools.yml`, with the notable exception of `yarn` for which you should use the
`webpack` container in `docker-compose.dev.yml`. To simplify this process you can use the `h2tools.sh` alias file on a `sh` compatible shell:
```shell
. h2tools.sh
```

This will add all the tools with `h2-` prefix to your current shell. (`h2-poetry`, `h2-yarn` etc...). Alternatively you can execute them from `docker-compose`
directly:
```shell
docker-compose -f docker-compose.tools.yml run --rm poetry ...
```

### Adding a Python Dependency ###
Python dependencies can be added with `poetry`/`h2-poetry`:
```shell
h2-poetry add [dependency]
```

### Adding a JavaScript/CSS Dependency ###
These can be added with `yarn`/`h2-yarn`:
```shell
h2-yarn add [dependency]
```

### Check Code for Conformance ###
Hunter2 currently utilises `eslint` and `flake8` for style consistency, and these are enforced by the CI system. The current code-base can be checked with the
following commands for compliance:
```shell
h2-eslint
h2-flake8
```

These commands are helpfully combined in a `h2-lint` alias to run both together.

### Profiling ###
To enable performance profiling with silk, do:
```shell
echo 'H2_SILK=True' >> .env
docker-compose up -d
docker-compose run --rm app migrate_schemas
```

### Building Docs
Docs are built automatically in CI, but if you need to change them and wish to build them locally you can do so by first
allowing the container user to write to the docs file tree:
```shell
chgrp -R 500 docs/_build
chmod -R g+w docs/_build
```
then running:
```shell
make run
```
A `sphinx` run configuration can also be added to PyCharm. It will need to set
`DJANGO_SETTINGS_MODULE=hunter2.settings`, but otherwise the options are as expected.

## MR Checklist

MRs do not have to arrive fully-formed; if you are having trouble with anything you can of course ask for assistance,
before or after creating a draft MR. For an MR to be accepted though, it should usually get to the point where:

* The pipeline passes(!)
* Commits are logical, complete and have descriptive messages.
* New features or behaviour is updated in the documentation if appropriate.
* New features will not break existing installations or past data without very good reason:
    * Migrations, including data migration, are included for model changes.
* Code style is consistent with existing code.
* New behaviour in backend code has tests.
* Bugfixes in backend code have a regression test.
