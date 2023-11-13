PYTEST_FLAGS=-W error::SyntaxWarning

TEMP_TEST_OUTPUT=/tmp/sse-contract-test-service.log

SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SPHINXPROJ    = launchdarkly-eventsource
SOURCEDIR     = docs
BUILDDIR      = $(SOURCEDIR)/build

.PHONY: help
help: #! Show this help message
	@echo 'Usage: make [target] ... '
	@echo ''
	@echo 'Targets:'
	@grep -h -F '#!' $(MAKEFILE_LIST) | grep -v grep | sed 's/:.*#!/:/' | column -t -s":"

#
# Quality control checks
#

.PHONY: test
test: #! Run unit tests
	poetry run pytest $(PYTEST_FLAGS)

.PHONY: lint
lint: #! Run type analysis and linting checks
	poetry run mypy ld_eventsource testing

#
# Documentation generation
#

.PHONY: docs
docs: #! Generate sphinx-based documentation
	poetry install --with docs
	cd docs
	poetry run $(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

#
# Contract test service commands
#

.PHONY: install-contract-tests-deps
install-contract-tests-deps:
	poetry install --with contract-tests

.PHONY: start-contract-test-service
start-contract-test-service:
	@cd contract-tests && poetry run python service.py

.PHONY: start-contract-test-service-bg
start-contract-test-service-bg:
	@echo "Test service output will be captured in $(TEMP_TEST_OUTPUT)"
	@make start-contract-test-service >$(TEMP_TEST_OUTPUT) 2>&1 &

.PHONY: run-contract-tests
run-contract-tests:
	@curl -s https://raw.githubusercontent.com/launchdarkly/sse-contract-tests/v2.0.0/downloader/run.sh \
      | VERSION=v2 PARAMS="-url http://localhost:8000 -debug -stop-service-at-end" sh

.PHONY: contract-tests
contract-tests: #! Run the SSE contract test harness
contract-tests: install-contract-tests-deps start-contract-test-service-bg run-contract-tests
