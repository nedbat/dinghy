.PHONY: clean help quality requirements test validate

.DEFAULT_GOAL := help

help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@awk -F ':.*?## ' '/^[a-zA-Z]/ && NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

clean: ## remove stuff we don't need
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	rm -fr build/
	rm -fr dist/
	rm -fr src/*.egg-info
	rm -fr .*_cache/

requirements: ## install development environment requirements
	pip install -r dev-requirements.txt

test: ## run tests in the current virtualenv
	pytest tests

black: ## run black to format source
	black src tests

pylint: ## run pylint to find code smells
	pylint src tests


.PHONY: dist pypi testpypi

dist: ## build the distributions
	python -m check_manifest
	python -m build --sdist --wheel
	python -m twine check dist/*

pypi: ## upload the built distributions to PyPI.
	python -m twine upload --verbose dist/*

testpypi: ## upload the distrubutions to PyPI's testing server.
	python -m twine upload --verbose --repository testpypi dist/*
