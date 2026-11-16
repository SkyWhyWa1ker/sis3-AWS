#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_PAGER=""
BASE="${1:?Usage: bash cleanup.sh sis3-copy}"
if [[ ! "$BASE" =~ ^[a-z][a-z0-9-]{0,39}$ ]]; then
  echo 'Invalid stack prefix.' >&2; exit 1
fi
echo "This deletes $BASE-app (including orders and logs), then $BASE-registry (including images)."
read -r -p "Type the prefix $BASE to confirm: " answer
[[ "$answer" == "$BASE" ]] || exit 1
aws cloudformation delete-stack --stack-name "$BASE-app"
aws cloudformation wait stack-delete-complete --stack-name "$BASE-app"
aws cloudformation delete-stack --stack-name "$BASE-registry"
aws cloudformation wait stack-delete-complete --stack-name "$BASE-registry"
echo "Deleted both stacks for $BASE."
