.PHONY : docs
docs :
	rm -rf docs/build/
	sphinx-autobuild -b html --watch gantry/ docs/source/ docs/build/

.PHONY : run-checks
run-checks :
	isort --check .
	black --check .
	flake8 .
	mypy .
	CUDA_VISIBLE_DEVICES='' pytest -v --color=yes --doctest-modules tests/ gantry/
