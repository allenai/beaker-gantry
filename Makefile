IMAGE_NAME=gantry
BEAKER_WORKSPACE=ai2/gantry-testing
GANTRY_VERSION := $(shell cat gantry/version.py | cut -d'"' -f2-2)

.PHONY : run-checks
run-checks : style lint test

.PHONY : style
style :
	isort --check .
	black --check .

.PHONY : lint
lint :
	ruff check .
	mypy .

.PHONY : test
test :
	pytest -v --durations=5 tests/

.PHONY : docker-image
docker-image :
	docker build -f Dockerfile -t $(IMAGE_NAME) .
	echo "Built image '$(IMAGE_NAME)', size: $$(docker inspect -f '{{ .Size }}' $(IMAGE_NAME) | numfmt --to=si)"

.PHONY : beaker-image
beaker-image : docker-image
	./scripts/create_beaker_image.sh $(IMAGE_NAME) $(IMAGE_NAME) $(BEAKER_WORKSPACE)
	./scripts/create_beaker_image.sh $(IMAGE_NAME) $(IMAGE_NAME)-v$(GANTRY_VERSION) $(BEAKER_WORKSPACE)

.PHONY : dev-tools-image
dev-tools-image :
	docker build -f test_fixtures/Dockerfile -t gantry-dev-tools .
	beaker image create gantry-dev-tools --name gantry-dev-tools --workspace ai2/gantry-testing

.PHONY : test-dev-tools-image
test-dev-tools-image :
	gantry run --timeout -1 --workspace ai2/gantry-testing --beaker-image petew/gantry-dev-tools --allow-dirty --yes -- python -c 'print("Hello, World!")'

.PHONY : check-version
check-version :
	@echo "❯ Latest published version is: $(shell python scripts/get_latest_version.py)"
	@echo "❯ Local version to build is:   v$(GANTRY_VERSION)"
	@read -rp "Press ENTER to continue, or CTRL-C to cancel."

.PHONY : build
build : check-version
	@rm -rf *.egg-info/ dist/
	@echo "❯ Building distribution files..."
	@python -m build
	@echo "❯ Done."

.PHONY : publish
publish : build
	@echo "❯ Preparing to upload the following distribution files:"
	@echo
	@ls -1 dist/
	@echo
	@read -rp "Press ENTER to continue, or CTRL-C to cancel."
	@echo "❯ Uploading distribution files..."
	@twine upload dist/*
	@echo "❯ Done."
