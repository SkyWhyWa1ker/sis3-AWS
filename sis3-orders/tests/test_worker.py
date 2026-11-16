import json
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from worker import consume, process_message


class WorkerTest(unittest.TestCase):
    def message(self, **changes):
        event = {"eventType": "OrderCreated", "eventId": "order-001", "sku": "book", "quantity": 1}
        event.update(changes)
        return {"Body": json.dumps(event)}

    def test_order_and_dedup_key_are_written_atomically(self):
        table = Mock()
        self.assertEqual(process_message(self.message(), table), "processed")
        args = table.put_item.call_args.kwargs
        self.assertEqual(args["ConditionExpression"], "attribute_not_exists(eventId)")
        self.assertEqual(args["Item"]["eventId"], "order-001")
        self.assertEqual(json.loads(args["Item"]["payload"])["sku"], "book")

    def test_redelivered_order_cannot_overwrite_original_order(self):
        class MemoryTable:
            def __init__(self):
                self.items = {}
            def put_item(self, Item, ConditionExpression):
                if Item["eventId"] in self.items:
                    raise ClientError({"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem")
                self.items[Item["eventId"]] = Item
        table = MemoryTable()
        self.assertEqual(process_message(self.message(), table), "processed")
        self.assertEqual(process_message(self.message(sku="changed"), table), "duplicate_skipped")
        self.assertEqual(len(table.items), 1)
        self.assertEqual(json.loads(table.items["order-001"]["payload"])["sku"], "book")

    def test_storage_outage_is_retried_not_treated_as_duplicate(self):
        table = Mock()
        table.put_item.side_effect = ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "PutItem")
        with self.assertRaises(ClientError):
            process_message(self.message(), table)

    def test_poison_message_does_not_write_a_business_record(self):
        table = Mock()
        with self.assertRaises(ValueError):
            process_message(self.message(forceFail=True), table)
        table.put_item.assert_not_called()

    def test_invalid_json_is_not_acknowledged_as_success(self):
        with self.assertRaises(ValueError):
            process_message({"Body": "not-json"}, Mock())

    def run_one_poll(self, processing_result=None, processing_error=None):
        class StopConsumer(BaseException):
            pass
        sqs = Mock()
        message = dict(self.message(), ReceiptHandle="receipt-1", MessageId="message-1")
        sqs.receive_message.side_effect = [{"Messages": [message]}, StopConsumer()]
        with patch.dict("os.environ", {"QUEUE_URL": "queue-url", "TABLE_NAME": "table"}), \
             patch("worker.boto3.client", return_value=sqs), \
             patch("worker.boto3.resource"), \
             patch("worker.process_message", return_value=processing_result, side_effect=processing_error):
            with self.assertRaises(StopConsumer):
                consume()
        return sqs

    def test_duplicate_is_acknowledged_after_safe_processing(self):
        sqs = self.run_one_poll(processing_result="duplicate_skipped")
        sqs.delete_message.assert_called_once_with(QueueUrl="queue-url", ReceiptHandle="receipt-1")

    def test_failed_processing_is_not_acknowledged_and_can_reach_dlq(self):
        sqs = self.run_one_poll(processing_error=ValueError("retry this message"))
        sqs.delete_message.assert_not_called()


if __name__ == "__main__":
    unittest.main()
