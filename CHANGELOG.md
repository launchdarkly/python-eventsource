# Change log

All notable changes to the LaunchDarkly SSE Client for Python will be documented in this file. This project adheres to [Semantic Versioning](http://semver.org).

## [1.2.3](https://github.com/launchdarkly/python-eventsource/compare/1.2.2...1.2.3) (2025-05-29)


### Bug Fixes

* Replace deprecated ssl.wrap_socket usage ([#42](https://github.com/launchdarkly/python-eventsource/issues/42)) ([34510b6](https://github.com/launchdarkly/python-eventsource/commit/34510b697d05fd037cb00a49ad9c5da1d62bfb45))

## [1.2.2](https://github.com/launchdarkly/python-eventsource/compare/1.2.1...1.2.2) (2025-02-28)


### Bug Fixes

* Fix SSE delay reset handling ([#39](https://github.com/launchdarkly/python-eventsource/issues/39)) ([fd401b5](https://github.com/launchdarkly/python-eventsource/commit/fd401b5348a8a62b18b823bf9c0dbaf5001a7285))

## [1.2.1](https://github.com/launchdarkly/python-eventsource/compare/1.2.0...1.2.1) (2024-12-23)


### Bug Fixes

* Ensure blocking read stream can be shutdown ([#37](https://github.com/launchdarkly/python-eventsource/issues/37)) ([58c4702](https://github.com/launchdarkly/python-eventsource/commit/58c4702f0920c0df1d188f79ec8b9fc018f00ae1))

## [1.2.0](https://github.com/launchdarkly/python-eventsource/compare/1.1.1...1.2.0) (2024-04-04)


### Features

* Drop support for python 3.7 [#30](https://github.com/launchdarkly/python-eventsource/issues/30) ([4372af2](https://github.com/launchdarkly/python-eventsource/commit/4372af2c77fde7085964f28ceacda4a41ad32fc7))


### Bug Fixes

* Move tests under ld_eventsource namespace ([#29](https://github.com/launchdarkly/python-eventsource/issues/29)) ([74a41db](https://github.com/launchdarkly/python-eventsource/commit/74a41dbef437cb9fc4b0b66f3ac80585917ab856))


### Documentation

* Fix broken formatting ([#27](https://github.com/launchdarkly/python-eventsource/issues/27)) ([eb8fbd2](https://github.com/launchdarkly/python-eventsource/commit/eb8fbd28ea354286a5245e9b275b7ac38811acfd))

## [1.1.1](https://github.com/launchdarkly/python-eventsource/compare/1.1.0...1.1.1) (2024-03-01)


### Bug Fixes

* **deps:** Bump jsonpickle to fix CVE-2020-22083 ([#23](https://github.com/launchdarkly/python-eventsource/issues/23)) ([3487311](https://github.com/launchdarkly/python-eventsource/commit/3487311a768cb557d39d8aa2dc57b569d9a55b0c))
* Raise minimum urllib3 package to 1.26.0 ([#26](https://github.com/launchdarkly/python-eventsource/issues/26)) ([ca5408d](https://github.com/launchdarkly/python-eventsource/commit/ca5408dc822ec8e9b8ac6674c3e72f5b84954ac0)), closes [#25](https://github.com/launchdarkly/python-eventsource/issues/25)


### Documentation

* Add status badge ([#19](https://github.com/launchdarkly/python-eventsource/issues/19)) ([777330b](https://github.com/launchdarkly/python-eventsource/commit/777330b303641bbe3983d2599ceb82a098d2ab98))
* Fix GH pages rendering of published docs ([#21](https://github.com/launchdarkly/python-eventsource/issues/21)) ([0a7ae7a](https://github.com/launchdarkly/python-eventsource/commit/0a7ae7ab967f1bbc374f572f799c4347703ac1c8))

## [1.1.0](https://github.com/launchdarkly/python-eventsource/compare/1.0.1...1.1.0) (2023-11-16)


### Features

* Expand support to include urllib3 v2 ([#15](https://github.com/launchdarkly/python-eventsource/issues/15)) ([340ff73](https://github.com/launchdarkly/python-eventsource/commit/340ff73f211bf6d98d5582baef8096a4a8b0c74d))

## [1.0.1] - 2023-01-04
### Fixed:
- Fixed packaging error that made installs fail.

## [1.0.0] - 2023-01-04
Initial release.
