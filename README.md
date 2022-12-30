# LaunchDarkly SSE Client for Python

[![Circle CI](https://img.shields.io/circleci/project/launchdarkly/python-eventsource.png)](https://circleci.com/gh/launchdarkly/python-eventsource)
[![PyPI](https://img.shields.io/pypi/v/launchdarkly-eventsource.svg?maxAge=2592000)](https://pypi.python.org/pypi/launchdarkly-eventsource)
[![Documentation](https://img.shields.io/static/v1?label=GitHub+Pages&message=API+reference&color=00add8)](https://launchdarkly.github.io/python-eventsource)

## Overview

The `launchdarkly/python-eventsource` package allows Python developers to consume Server-Sent-Events (SSE) from a remote API. The SSE specification is defined here: [https://html.spec.whatwg.org/multipage/server-sent-events.html](https://html.spec.whatwg.org/multipage/server-sent-events.html#server-sent-events)

This package's primary purpose is to support the [LaunchDarkly SDK for Python](https://github.com/launchdarkly/python-server-sdk), but it can be used independently. In its simplest configuration, it emulates the behavior of the EventSource API as defined in the SSE specification, with the addition of exponential backoff behavior for retries. However, it also includes optional features used by LaunchDarkly SDKs that are not part of the core specification, such as:

* Customizing the backoff/jitter behavior.
* Setting read timeouts, custom headers, and other HTTP request properties.
* Specifying that connections should be retried under circumstances where the standard EventSource behavior would not retry them, such as if the server returns an HTTP error status.

This is a synchronous implementation which blocks the caller's thread when reading events or reconnecting. By default, it uses `urllib3` to make HTTP requests, but it can be configured to read any input stream.

## Supported Python versions

This version of the package is compatible with Python 3.7 and higher.

## Contributing

We encourage pull requests and other contributions from the community. Check out our [contributing guidelines](CONTRIBUTING.md) for instructions on how to contribute to this SDK.

## About LaunchDarkly

* LaunchDarkly is a continuous delivery platform that provides feature flags as a service and allows developers to iterate quickly and safely. We allow you to easily flag your features and manage them from the LaunchDarkly dashboard.  With LaunchDarkly, you can:
    * Roll out a new feature to a subset of your users (like a group of users who opt-in to a beta tester group), gathering feedback and bug reports from real-world use cases.
    * Gradually roll out a feature to an increasing percentage of users, and track the effect that the feature has on key metrics (for instance, how likely is a user to complete a purchase if they have feature A versus feature B?).
    * Turn off a feature that you realize is causing performance problems in production, without needing to re-deploy, or even restart the application with a changed configuration file.
    * Grant access to certain features based on user attributes, like payment plan (eg: users on the ‘gold’ plan get access to more features than users in the ‘silver’ plan). Disable parts of your application to facilitate maintenance, without taking everything offline.
* LaunchDarkly provides feature flag SDKs for a wide variety of languages and technologies. Read [our documentation](https://docs.launchdarkly.com/sdk) for a complete list.
* Explore LaunchDarkly
    * [launchdarkly.com](https://www.launchdarkly.com/ "LaunchDarkly Main Website") for more information
    * [docs.launchdarkly.com](https://docs.launchdarkly.com/  "LaunchDarkly Documentation") for our documentation and SDK reference guides
    * [apidocs.launchdarkly.com](https://apidocs.launchdarkly.com/  "LaunchDarkly API Documentation") for our API documentation
    * [blog.launchdarkly.com](https://blog.launchdarkly.com/  "LaunchDarkly Blog Documentation") for the latest product updates
