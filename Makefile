.PHONY : run-checks
run-checks :
	isort --check .
	black --check .
	ruff check .
	mypy .
	pytest -v --durations=5 tests/

.PHONY : dev-tools-image
dev-tools-image :
	docker build -f test_fixtures/Dockerfile -t gantry-dev-tools .
	beaker image create gantry-dev-tools --name gantry-dev-tools --workspace ai2/gantry-testing

.PHONY : test-dev-tools-image
test-dev-tools-image :
	gantry run --timeout -1 --workspace ai2/gantry-testing --beaker-image petew/gantry-dev-tools --allow-dirty --yes -- python -c 'print("Hello, World!")'
