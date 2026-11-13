#!/bin/sh
# Integrationstests in Docker (Python 3.14, Linux). Aufruf: tools/test-ha.sh [min] [pytest-Argumente]
# "min" testet gegen die kleinste unterstützte HA-Version (requirements_test_min.txt).
set -e
REQ=requirements_test.txt
if [ "$1" = "min" ]; then REQ=requirements_test_min.txt; shift; fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm -v "$ROOT:/repo" -v tarif-cockpit-pip:/root/.cache/pip -w /repo python:3.14-slim \
  sh -c "pip install -q --root-user-action=ignore -r $REQ && python -m pytest ${*:-tests}"
