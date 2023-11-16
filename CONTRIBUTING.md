# Contributing to this project
 
## Submitting bug reports and feature requests

The LaunchDarkly SDK team monitors the [issue tracker](https://github.com/launchdarkly/python-eventsource/issues) in this repository. Bug reports and feature requests specific to this project should be filed in this issue tracker. The SDK team will respond to all newly filed issues within two business days.

Some of this code is used by the LaunchDarkly Python SDK. For issues or requests that are more generally related to the LaunchDarkly Python SDK, rather than specifically for the code in this repository, please use the [`python-server-sdk`](https://github.com/launchdarkly/python-server-sdk) repository.
 
## Submitting pull requests
 
We encourage pull requests and other contributions from the community. Before submitting pull requests, ensure that all temporary or unintended code is removed. Don't worry about adding reviewers to the pull request; the LaunchDarkly SDK team will add themselves. The SDK team will acknowledge all pull requests within two business days.
 
## Build instructions
 
### Prerequisites
 
This project should be developed against its minimum compatible version as described in [`README.md`](./README.md).

To install the runtime and test requirements:

```
poetry shell
poetry install
```

### Testing

To run all unit tests:

```
make test
```

To run the standardized contract tests that are run against all LaunchDarkly SSE client implementations:
```
make contract-tests
```

### Linting

To run the linter and check type hints:

```
make lint
```
