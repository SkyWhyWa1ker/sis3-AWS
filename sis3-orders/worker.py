"""At-least-once SQS delivery; atomic idempotent business write in DynamoDB."""
import json
import os
import re
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


def process_message(message, table):
    event = json.loads(message["Body"])
    event_id = event["eventId"]
    if not isinstance(event_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", event_id):
        raise ValueError("Invalid eventId")
    if event.get("eventType") != "OrderCreated":
        raise ValueError("Unknown eventType")
    if event.get("forceFail") is True:
        raise ValueError("Intentional DLQ demonstration")
    try:
        # The order and the deduplication key are the SAME atomic write.
        # A crash before SQS delete leads to a harmless duplicate on retry.
        table.put_item(
            Item={"eventId": event_id, "payload": json.dumps(event),
                  "processedAt": datetime.now(timezone.utc).isoformat()},
            ConditionExpression="attribute_not_exists(eventId)",
        )
        action = "processed"
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        action = "duplicate_skipped"
    print(json.dumps({"action": action, "eventId": event_id}), flush=True)
    return action


def consume():
    sqs = boto3.client("sqs")
    queue_url = os.environ["QUEUE_URL"]
    table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    while True:
        try:
            messages = sqs.receive_message(
                QueueUrl=queue_url, MaxNumberOfMessages=1, WaitTimeSeconds=20,
            ).get("Messages", [])
            for message in messages:
                try:
                    process_message(message, table)
                    sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message["ReceiptHandle"])
                except Exception as exc:
                    # Leave failed messages on the queue. SQS retries, then redrives to DLQ.
                    print(json.dumps({"action": "processing_failed", "messageId": message.get("MessageId"),
                                      "error": str(exc)}), flush=True)
        except Exception as exc:
            print(json.dumps({"action": "poll_error", "error": str(exc)}), flush=True)
            time.sleep(3)
