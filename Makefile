.PHONY : run-checks
run-checks :
	isort --check .
	black --check .
	ruff check .
	mypy .
