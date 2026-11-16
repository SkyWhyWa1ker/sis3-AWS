"""Small teaching API. No authentication: use only synthetic lab data."""
import json
import os
import re
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import boto3

from worker import consume

TOPIC_ARN = os.environ["TOPIC_ARN"]
TABLE_NAME = os.environ["TABLE_NAME"]
sns = boto3.client("sns")
table = boto3.resource("dynamodb").Table(TABLE_NAME)
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}")


class Handler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/health":
            self.reply(200, {"status": "ok", "environment": os.environ.get("ENV", "dev")})
            return
        if path.startswith("/orders/"):
            event_id = path.removeprefix("/orders/")
            if not ID_PATTERN.fullmatch(event_id):
                self.reply(400, {"error": "Invalid eventId"})
                return
            try:
                item = table.get_item(Key={"eventId": event_id}, ConsistentRead=True).get("Item")
                if item:
                    self.reply(200, {"eventId": event_id, "status": "PROCESSED", "order": json.loads(item["payload"])})
                else:
                    self.reply(404, {"eventId": event_id, "status": "NOT_PROCESSED_YET"})
            except Exception as exc:
                print(json.dumps({"action": "api_error", "error": type(exc).__name__}), flush=True)
                self.reply(503, {"error": "DynamoDB unavailable; check CloudWatch"})
            return
        self.reply(404, {"routes": ["GET /health", "POST /orders", "GET /orders/{eventId}"]})

    def do_POST(self):
        if urlsplit(self.path).path != "/orders":
            self.reply(404, {"error": "Unknown route"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                raise ValueError("Body must be 1..16384 bytes")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Body must be a JSON object")
            event_id = body.get("eventId", str(uuid.uuid4()))
            if not isinstance(event_id, str) or not ID_PATTERN.fullmatch(event_id):
                raise ValueError("eventId: 1..80 letters, digits, underscore or hyphen")
            sku = body.get("sku", "book")
            quantity = body.get("quantity", 1)
            if not isinstance(sku, str) or not 1 <= len(sku) <= 100:
                raise ValueError("sku: string of 1..100 characters")
            if type(quantity) is not int or not 1 <= quantity <= 1000:
                raise ValueError("quantity: integer 1..1000")
            force_fail = body.get("forceFail", False)
            if type(force_fail) is not bool:
                raise ValueError("forceFail: boolean")
            event = {"eventType": "OrderCreated", "eventId": event_id,
                     "sku": sku, "quantity": quantity, "forceFail": force_fail}
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.reply(400, {"error": str(exc)})
            return
        try:
            result = sns.publish(TopicArn=TOPIC_ARN, Message=json.dumps(event))
            self.reply(202, {"eventId": event_id, "status": "QUEUED", "messageId": result["MessageId"]})
        except Exception as exc:
            print(json.dumps({"action": "publish_error", "error": type(exc).__name__}), flush=True)
            self.reply(503, {"error": "SNS unavailable; check CloudWatch"})


if __name__ == "__main__":
    threading.Thread(target=consume, daemon=True, name="sqs-consumer").start()
    print(json.dumps({"action": "api_started", "port": 8080}), flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
