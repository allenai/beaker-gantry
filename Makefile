IMAGE_NAME=gantry

.PHONY : run-checks
run-checks :
	isort --check .
	black --check .
	ruff check .
	mypy .
	pytest -v --durations=5 tests/

.PHONY : docker-image
docker-image :
	docker build -f Dockerfile -t $(IMAGE_NAME) .
	echo "Built image '$(IMAGE_NAME)', size: $$(docker inspect -f '{{ .Size }}' $(IMAGE_NAME) | numfmt --to=si)"

# .PHONY : beaker-image
# beaker-image : docker-image
#     ./src/scripts/beaker/create_beaker_image.sh olmax olmax $(BEAKER_WORKSPACE)

.PHONY : dev-tools-image
dev-tools-image :
	docker build -f test_fixtures/Dockerfile -t gantry-dev-tools .
	beaker image create gantry-dev-tools --name gantry-dev-tools --workspace ai2/gantry-testing

.PHONY : test-dev-tools-image
test-dev-tools-image :
	gantry run --timeout -1 --workspace ai2/gantry-testing --beaker-image petew/gantry-dev-tools --allow-dirty --yes -- python -c 'print("Hello, World!")'
