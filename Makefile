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
