.PHONY: help
help:
	@echo "Builds and runs a development instance of Hunter 2"
	@echo "Targets:"
	@echo "    help                   - Prints this help text"
	@echo "    run                    - Rebuilds images if Dockerfile or project manifests have changed,"
	@echo "                             then starts or updates the service"
	@echo "    .build/<component>.txt - Builds the docker image for <component> and outputs its image ID"
	@echo "                             to a text file for dependency tracking."

.PHONY: run
run: dev-images
	docker-compose up -d

.PHONY: test
test: dev-images
	docker-compose run --rm app test -v2

.PHONY: dev-images
dev-images: .build/app.txt .build/db.txt .build/webpack.txt

.PHONY: docs
docs: dev-images
	docker-compose run --rm --entrypoint /opt/hunter2/src/docs/docker-build-docs.sh app

BUILD_TAG ?= latest

export COMPOSE_DOCKER_CLI_BUILD := 1
export DOCKER_BUILDKIT := 1

.build:
	mkdir -p .build

.build/app.txt: pyproject.toml poetry.lock Dockerfile | .build
	docker-compose build --build-arg BUILD_TAG=$(BUILD_TAG) app
	docker image inspect -f '{{.Id}}' registry.gitlab.com/hunter2.app/hunter2/app:$(BUILD_TAG) > .build/app.txt

.build/db.txt: postgres/* | .build
	docker-compose build --build-arg BUILD_TAG=$(BUILD_TAG) db
	docker image inspect -f '{{.Id}}' registry.gitlab.com/hunter2.app/hunter2/db:$(BUILD_TAG) > .build/db.txt

.build/metrics.txt: prometheus/* | .build
	docker-compose build --build-arg BUILD_TAG=$(BUILD_TAG) metrics
	docker image inspect -f '{{.Id}}' registry.gitlab.com/hunter2.app/hunter2/metrics:$(BUILD_TAG) > .build/metrics.txt

.build/web.txt: .build/app.txt nginx/* | .build
	docker-compose build --build-arg BUILD_TAG=$(BUILD_TAG) web
	docker image inspect -f '{{.Id}}' registry.gitlab.com/hunter2.app/hunter2/web:$(BUILD_TAG) > .build/web.txt

.build/webpack.txt: webpack/* | .build
	docker-compose build --build-arg BUILD_TAG=$(BUILD_TAG) webpack
	docker image inspect -f '{{.Id}}' registry.gitlab.com/hunter2.app/hunter2/webpack:$(BUILD_TAG) > .build/webpack.txt
