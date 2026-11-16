#!/usr/bin/env bash
# Source this file in CloudShell: source outputs.sh sis3-main
BASE="${1:-sis3-main}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_PAGER=""
sis3_output() {
  aws cloudformation describe-stacks --stack-name "$BASE-app" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue | [0]" --output text
}
API=$(sis3_output ApiUrl)
QUEUE=$(sis3_output QueueUrl)
DLQ=$(sis3_output DlqUrl)
TABLE=$(sis3_output TableName)
LOGS=$(sis3_output LogGroup)
CLUSTER=$(sis3_output ClusterName)
SERVICE=$(sis3_output ServiceName)
export BASE API QUEUE DLQ TABLE LOGS CLUSTER SERVICE
printf 'API=%s\nTABLE=%s\nLOGS=%s\n' "$API" "$TABLE" "$LOGS"
unset -f sis3_output
