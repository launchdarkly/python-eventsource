#!/bin/bash

if [[ -d "docs/build/html" ]]; then
  cp -r docs/build/html/* ${LD_RELEASE_DOCS_DIR}
fi
