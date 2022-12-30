# type: ignore
from setuptools import find_packages, setup, Command

import sys

# Get VERSION constant from version module - we can't simply import that module because
# __init__.py imports other files that require dependencies we may not have loaded yet.
# Based on https://packaging.python.org/guides/single-sourcing-package-version/
version_module_globals = {}
with open('./ld_eventsource/version.py') as f:
    exec(f.read(), version_module_globals)
package_version = version_module_globals['VERSION']

def parse_requirements(filename):
    """ load requirements from a pip requirements file """
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]

install_reqs = parse_requirements('requirements.txt')
test_reqs = parse_requirements('test-requirements.txt')

reqs = [ir for ir in install_reqs]
testreqs = [ir for ir in test_reqs]


class PyTest(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        import sys
        import subprocess
        errno = subprocess.call([sys.executable, 'runtests.py'])
        raise SystemExit(errno)

setup(
    name='launchdarkly-eventsource',
    version=package_version,
    author='LaunchDarkly',
    author_email='dev@launchdarkly.com',
    packages=find_packages(),
    url='https://github.com/launchdarkly/python-eventsource',
    description='LaunchDarkly SSE Client',
    long_description='LaunchDarkly SSE Client for Python',
    install_requires=reqs,
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries',
    ],
    tests_require=testreqs,
    cmdclass={'test': PyTest},
)
