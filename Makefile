PYTEST_FLAGS=-W error::SyntaxWarning

TEMP_TEST_OUTPUT=/tmp/sse-contract-test-service.log
TEMP_ASYNC_TEST_OUTPUT=/tmp/sse-async-contract-test-service.log

SPHINXOPTS    = -W --keep-going
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

.PHONY: install
install:
	@uv sync --all-extras

#
# Quality control checks
#

.PHONY: test
test: #! Run unit tests
test: install
	@uv run pytest $(PYTEST_FLAGS)

.PHONY: lint
lint: #! Run type analysis and linting checks
lint: install
	@uv run mypy ld_eventsource
	@uv run isort --check --atomic ld_eventsource contract-tests
	@uv run pycodestyle ld_eventsource contract-tests

#
# Documentation generation
#

.PHONY: docs
docs: #! Generate sphinx-based documentation
	@uv sync --group docs
	cd docs
	@uv run $(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

#
# Contract test service commands
#

.PHONY: install-contract-tests-deps
install-contract-tests-deps:
	uv sync --all-extras --group contract-tests

.PHONY: start-contract-test-service
start-contract-test-service: install-contract-tests-deps
	@cd contract-tests && uv run python service.py

.PHONY: start-contract-test-service-bg
start-contract-test-service-bg:
	@echo "Test service output will be captured in $(TEMP_TEST_OUTPUT)"
	@make start-contract-test-service >$(TEMP_TEST_OUTPUT) 2>&1 &

.PHONY: run-contract-tests
run-contract-tests:
	@curl -s https://raw.githubusercontent.com/launchdarkly/sse-contract-tests/main/downloader/run.sh \
      | VERSION=v2 PARAMS="-url http://localhost:8000 -debug -stop-service-at-end" sh

.PHONY: contract-tests
contract-tests: #! Run the SSE contract test harness
contract-tests: install-contract-tests-deps start-contract-test-service-bg run-contract-tests

.PHONY: start-async-contract-test-service
start-async-contract-test-service: install-contract-tests-deps
	@cd contract-tests && uv run python async_service.py 8001

.PHONY: start-async-contract-test-service-bg
start-async-contract-test-service-bg:
	@echo "Async test service output will be captured in $(TEMP_ASYNC_TEST_OUTPUT)"
	@make start-async-contract-test-service >$(TEMP_ASYNC_TEST_OUTPUT) 2>&1 &

.PHONY: run-async-contract-tests
run-async-contract-tests:
	@curl -s https://raw.githubusercontent.com/launchdarkly/sse-contract-tests/main/downloader/run.sh \
      | VERSION=v2 PARAMS="-url http://localhost:8001 -debug -stop-service-at-end" sh

.PHONY: async-contract-tests
async-contract-tests: #! Run the SSE async contract test harness
async-contract-tests: install-contract-tests-deps start-async-contract-test-service-bg run-async-contract-tests
