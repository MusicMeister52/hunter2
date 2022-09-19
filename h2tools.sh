#!/bin/sh

# Common developer aliases for developing on hunter2.
alias h2-poetry="docker-compose -f docker-compose.tools.yml run --rm poetry"
alias h2-yarn="docker-compose -f docker-compose.dev.yml run --rm webpack"
alias h2-dot="docker-compose -f docker-compose.tools.yml run --rm dot"
alias h2-eslint="docker-compose -f docker-compose.tools.yml run --rm eslint"
alias h2-flake8="docker-compose -f docker-compose.tools.yml run --rm flake8"
alias h2-lint="h2-flake8 && h2-eslint"
alias h2-test="docker-compose run -v ${PWD}/coverage:/opt/hunter2/src/coverage -v ${PWD}/reports:/opt/hunter2/src/reports -v ${PWD}/pytest_cache:/opt/hunter2/src/.pytest_cache --entrypoint /opt/hunter2/venv/bin/python --rm app -m pytest"
