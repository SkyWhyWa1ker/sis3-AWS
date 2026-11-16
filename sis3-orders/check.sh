#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python -m unittest discover -s tests -v
cfn-lint -t infra/registry.yaml infra/app.yaml
python policy_check.py
echo 'All local checks passed. Cloud deployment still needs to be verified in your AWS account.'
