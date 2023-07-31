.PHONY: help clean requirements

.DEFAULT_GOAL := help

help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@awk -F ':.*?## ' '/^[a-zA-Z]/ && NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

clean: ## remove stuff we don't need
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	rm -fr build/ dist/ src/*.egg-info
	rm -fr .*_cache/
	rm -f out_*.json save_*.json

requirements: ## install development environment requirements
	pip install -r dev-requirements.txt


.PHONY: test quality black lint _check_manifest sample

test: ## run tests in the current virtualenv
	pytest tests

quality: black lint _check_manifest ## run code-checking tools

black:
	black -q src tests

lint:
	pylint src tests

_check_manifest:
	python -m check_manifest


.PHONY: check_release _check_version _check_scriv

VERSION := $(shell python -c "import dinghy as d; print(d.__version__)")

check_release: _check_manifest _check_version _check_scriv  ## check that we are ready for a release
	@echo "Release checks passed"

_check_version:
	@if [[ $$(git tags | grep -q -w $(VERSION) && echo "x") == "x" ]]; then \
		echo 'A git tag for $(VERSION) exists! Did you forget to bump the version in src/dinghy/__init__.py?'; \
		exit 1; \
	fi

_check_scriv:
	@if (( $$(ls -1 scriv.d | wc -l) != 1 )); then \
		echo 'There are scriv fragments! Did you forget `scriv collect`?'; \
		exit 1; \
	fi


.PHONY: release dist testpypi pypi tag gh_release

release: clean check_release dist pypi tag gh_release ## do all the steps for a release

dist: ## build the distributions
	python -m build --sdist --wheel
	python -m twine check dist/*

testpypi: ## upload the distributions to PyPI's testing server.
	@if [[ -z "$$TWINE_TEST_PASSWORD" ]]; then \
		echo 'Missing TWINE_TEST_PASSWORD: opvars'; \
		exit 1; \
	fi
	python -m twine upload --verbose --repository testpypi --password $$TWINE_TEST_PASSWORD dist/*

pypi: ## upload the built distributions to PyPI.
	@if [[ -z "$$TWINE_PASSWORD" ]]; then \
		echo 'Missing TWINE_PASSWORD: opvars'; \
		exit 1; \
	fi
	python -m twine upload --verbose dist/*

tag: ## make a git tag with the version number
	git tag -a -m "Version $(VERSION)" $(VERSION)
	git push --all

gh_release: ## make a GitHub release
	python -m scriv github-release
