#!/bin/sh

. /opt/hunter2/venv/bin/activate
pip install "Sphinx<5.0.0" "myst-parser<1.0.0"
DJANGO_SETTINGS_MODULE=hunter2.settings sphinx-build -v -b html docs docs/_build/html
