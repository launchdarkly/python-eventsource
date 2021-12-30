
lint:
	mypy --config-file mypy.ini ld_eventsource testing

.PHONY: lint

TEMP_TEST_OUTPUT=/tmp/sse-contract-test-service.log

build-contract-test-service:
	@cd contract-tests && pip install -r requirements.txt

start-contract-test-service:
	@cd contract-tests && python service.py

start-contract-test-service-bg:
	@echo "Test service output will be captured in $(TEMP_TEST_OUTPUT)"
	@make start-contract-test-service >$(TEMP_TEST_OUTPUT) 2>&1 &

run-contract-tests:
	@curl -s https://raw.githubusercontent.com/launchdarkly/sse-contract-tests/master/downloader/run.sh \
      | VERSION=v1 PARAMS="-url http://localhost:8000 -debug -stop-service-at-end" sh

contract-tests: build-contract-test-service start-contract-test-service-bg run-contract-tests

.PHONY: build-contract-test-service start-contract-test-service run-contract-tests contract-tests
