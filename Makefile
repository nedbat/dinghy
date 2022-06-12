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

SAMPLE = docs/black_digest

sample: ## make the sample digest
	DINGHY_SAVE_ENTRIES=0 DINGHY_SAVE_RESPONSES=0 DINGHY_SAVE_RESULT=0 python -m dinghy $(SAMPLE).yaml
	sed -i "" -e '/Activity/s/ since ....-..-..</</' $(SAMPLE).html


.PHONY: check_release _check_version _check_scriv _check_sample

check_release: _check_manifest _check_version _check_scriv _check_sample  ## check that we are ready for a release
	@echo "Release checks passed"

_check_version:
	@if [[ $$(git tags | grep -q -w $$(python setup.py --version) && echo "x") == "x" ]]; then \
		echo 'A git tag for this version exists! Did you forget to bump the version in src/dinghy/__init__.py?'; \
		exit 1; \
	fi

_check_scriv:
	@if (( $$(ls -1 scriv.d | wc -l) != 1 )); then \
		echo 'There are scriv fragments! Did you forget `scriv collect`?'; \
		exit 1; \
	fi

_check_sample:
	@if [[ $$(python setup.py --version) != $$(grep dinghy_version $(SAMPLE).html | grep -E -o '[0-9][0-9.]+') ]]; then \
		echo 'The sample digest has the wrong version! Did you forget `make sample`?'; \
		exit 1; \
	fi

.PHONY: release dist testpypi pypi tag gh_release

release: clean check_release dist pypi tag gh_release ## do all the steps for a release

dist: ## build the distributions
	python -m build --sdist --wheel
	python -m twine check dist/*

testpypi: ## upload the distributions to PyPI's testing server.
	python -m twine upload --verbose --repository testpypi dist/*

pypi: ## upload the built distributions to PyPI.
	python -m twine upload --verbose dist/*

tag: ## make a git tag with the version number
	git tag -a -m "Version $$(python setup.py --version)" $$(python setup.py --version)
	git push --all

gh_release: ## make a GitHub release
	python -m scriv github-release
