#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export AWS_PAGER=""
BASE="${1:?Usage: bash deploy.sh sis3-main dev}"
ENVIRONMENT="${2:-dev}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
if [[ ! "$BASE" =~ ^[a-z][a-z0-9-]{0,39}$ ]]; then
  echo 'Name: lowercase letter first; letters, digits, hyphens; max 40 characters.' >&2
  exit 1
fi
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
  echo 'Environment must be dev, staging or prod.' >&2; exit 1
fi
if [[ "$(git rev-parse --show-toplevel 2>/dev/null)" != "$PWD" ]]; then
  echo 'Initialize and commit this project as its own git repository first.' >&2; exit 1
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo 'Commit your changes first: immutable image tags refer to committed code.' >&2; exit 1
fi
IMAGE_TAG="$(git rev-parse HEAD)"
aws sts get-caller-identity
docker info >/dev/null

deploy_reviewed() {
  local stack="$1" template="$2" output change_set answer
  shift 2
  if ! output=$(aws cloudformation deploy --stack-name "$stack" \
      --template-file "$template" --capabilities CAPABILITY_IAM \
      --no-execute-changeset --no-fail-on-empty-changeset "$@" 2>&1); then
    printf '%s\n' "$output" >&2; return 1
  fi
  printf '%s\n' "$output"
  if [[ "$output" == *'No changes to deploy'* ]]; then
    return 0
  fi
  change_set=$(aws cloudformation list-change-sets --stack-name "$stack" \
    --query "Summaries[?Status=='CREATE_COMPLETE' && ExecutionStatus=='AVAILABLE'] | sort_by(@, &CreationTime)[-1].ChangeSetId" \
    --output text)
  if [[ "$change_set" == None || -z "$change_set" ]]; then
    echo 'No executable change set found. Inspect CloudFormation Events.' >&2; return 1
  fi
  aws cloudformation describe-change-set --stack-name "$stack" --change-set-name "$change_set" \
    --query 'Changes[].ResourceChange.[Action,LogicalResourceId,Replacement]' --output table
  echo 'Review Add / Modify / Remove and Replacement. Initial deployment should contain Add.'
  read -r -p "Execute change set for $stack? [y/N] " answer
  if [[ "$answer" != y && "$answer" != Y ]]; then
    echo 'Not executed. Run this script again when ready.'; exit 1
  fi
  local before_status
  before_status=$(aws cloudformation describe-stacks --stack-name "$stack" \
      --query 'Stacks[0].StackStatus' --output text)
  aws cloudformation execute-change-set --stack-name "$stack" --change-set-name "$change_set"
  # New stacks prepared by create-change-set have REVIEW_IN_PROGRESS status.
  if [[ "$before_status" == REVIEW_IN_PROGRESS ]]; then
    aws cloudformation wait stack-create-complete --stack-name "$stack"
  else
    aws cloudformation wait stack-update-complete --stack-name "$stack"
  fi
}

deploy_reviewed "$BASE-registry" infra/registry.yaml
REPO_NAME=$(aws cloudformation describe-stacks --stack-name "$BASE-registry" \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryName'].OutputValue | [0]" --output text)
REPO_URI=$(aws cloudformation describe-stacks --stack-name "$BASE-registry" \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryUri'].OutputValue | [0]" --output text)
if result=$(aws ecr describe-images --repository-name "$REPO_NAME" --image-ids imageTag="$IMAGE_TAG" 2>&1); then
  echo "Reusing immutable image $REPO_URI:$IMAGE_TAG"
elif [[ "$result" == *ImageNotFoundException* ]]; then
  aws ecr get-login-password | docker login --username AWS --password-stdin "${REPO_URI%%/*}"
  docker build --platform linux/amd64 -t "$REPO_URI:$IMAGE_TAG" .
  docker push "$REPO_URI:$IMAGE_TAG"
else
  printf '%s\n' "$result" >&2; exit 1
fi
deploy_reviewed "$BASE-app" infra/app.yaml --parameter-overrides \
  "Env=$ENVIRONMENT" "ImageUri=$REPO_URI:$IMAGE_TAG"
echo 'Deployment complete. Save the Outputs for the defence:'
aws cloudformation describe-stacks --stack-name "$BASE-app" \
  --query 'Stacks[0].Outputs.[OutputKey,OutputValue]' --output table
