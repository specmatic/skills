import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "extract_asyncapi.py"


def slugify(value: str) -> str:
    import re

    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "value"


class ExtractAsyncAPITest(unittest.TestCase):
    def run_extractor(self, repo: Path):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(repo)],
            capture_output=True,
            text=True,
            check=False,
        )

    def read_json(self, path: Path):
        return json.loads(path.read_text())

    def test_generates_asyncapi_and_examples_for_mixed_operations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "src").mkdir()
            (repo / "src" / "consumer.java").write_text(
                textwrap.dedent(
                    """
                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "OrderRequest",
                    //   "contentType": "application/json",
                    //   "payloadSchema": {
                    //     "type": "object",
                    //     "required": ["id"],
                    //     "properties": { "id": { "type": "integer" } }
                    //   },
                    //   "headersSchema": {
                    //     "type": "object",
                    //     "properties": { "orderCorrelationId": { "type": "string" } }
                    //   },
                    //   "correlationId": {
                    //     "id": "orderCorrelationId",
                    //     "location": "$message.header#/orderCorrelationId"
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class OrderRequest {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "OrderAccepted",
                    //   "contentType": "application/json",
                    //   "payloadSchema": {
                    //     "type": "object",
                    //     "required": ["id", "status"],
                    //     "properties": {
                    //       "id": { "type": "integer" },
                    //       "status": { "type": "string" }
                    //     }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class OrderAccepted {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "Order",
                    //   "contentType": "application/json",
                    //   "payloadSchema": {
                    //     "type": "object",
                    //     "required": ["id", "status"],
                    //     "properties": {
                    //       "id": { "type": "integer" },
                    //       "status": { "type": "string" }
                    //     }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class Order {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "operation",
                    //   "role": "consumer",
                    //   "operationId": "placeOrder",
                    //   "channel": { "name": "NewOrderPlaced", "address": "new-orders" },
                    //   "message": "OrderRequest",
                    //   "example": {
                    //     "name": "NEW_ORDER",
                    //     "id": "new-order",
                    //     "payload": { "id": 10 },
                    //     "headers": { "orderCorrelationId": "12345" },
                    //     "key": 10
                    //   },
                    //   "replies": [
                    //     {
                    //       "channel": { "name": "OrderInitiated", "address": "wip-orders" },
                    //       "message": "Order",
                    //       "example": {
                    //         "payload": { "id": 10, "status": "INITIATED" },
                    //         "headers": { "orderCorrelationId": "12345" },
                    //         "key": 10
                    //       }
                    //     },
                    //     {
                    //       "channel": { "name": "OrderAccepted", "address": "accepted-orders" },
                    //       "message": "OrderAccepted",
                    //       "example": {
                    //         "payload": { "id": 10, "status": "ACCEPTED" }
                    //       }
                    //     }
                    //   ]
                    // }
                    // @end-specmatic-asyncapi
                    @KafkaListener(topics = "new-orders")
                    public void handleNewOrder(String payload) {
                        publish("wip-orders");
                        publish("accepted-orders");
                    }

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "operation",
                    //   "role": "publisher",
                    //   "operationId": "warehouseNotification",
                    //   "channel": { "name": "WarehouseNotification", "address": "warehouse-events" },
                    //   "message": "OrderAccepted",
                    //   "example": {
                    //     "name": "WAREHOUSE_NOTIFICATION",
                    //     "payload": { "id": 55, "status": "ACCEPTED" }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    public void notifyWarehouse() {
                        send("warehouse-events");
                    }
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            asyncapi_text = (repo / "asyncapi-extracted.yaml").read_text()
            self.assertIn("asyncapi: 3.0.0", asyncapi_text)
            self.assertIn("placeOrder__to__orderinitiated", asyncapi_text)
            self.assertIn("placeOrder__to__orderaccepted", asyncapi_text)
            self.assertIn("warehouseNotification:", asyncapi_text)

            report = self.read_json(repo / "asyncapi-extraction-report.json")
            self.assertEqual(report["errors"], [])
            self.assertEqual(len(report["operations"]), 3)
            self.assertIn("generated", report)
            suite_dir = Path(report["generated"]["suiteDir"])
            self.assertTrue((suite_dir / "specmatic.yaml").exists())
            self.assertTrue((suite_dir / "scripts" / "prepare_async_test_data.sh").exists())
            self.assertTrue((suite_dir / "run_async_contract_tests.sh").exists())
            specmatic_text = (suite_dir / "specmatic.yaml").read_text()
            run_script_text = (suite_dir / "run_async_contract_tests.sh").read_text()
            self.assertIn("asyncapi:", specmatic_text)
            self.assertIn("type: test", specmatic_text)
            self.assertIn("prepare_async_test_data.sh", run_script_text)
            self.assertIn("specmatic test", run_script_text)
            self.assertIn("docker pull", run_script_text)

            examples_dir = repo / "examples" / slugify(repo.name)
            example_files = sorted(path.name for path in examples_dir.glob("*.json"))
            self.assertEqual(
                example_files,
                [
                    "placeorder-to-orderaccepted.json",
                    "placeorder-to-orderinitiated.json",
                    "warehousenotification.json",
                ],
            )

            reply_example = self.read_json(examples_dir / "placeorder-to-orderinitiated.json")
            self.assertEqual(reply_example["receive"]["topic"], "new-orders")
            self.assertEqual(reply_example["send"]["topic"], "wip-orders")
            self.assertEqual(reply_example["receive"]["headers"]["orderCorrelationId"], "12345")
            self.assertEqual(reply_example["receive"]["key"], 10)

            send_only_example = self.read_json(examples_dir / "warehousenotification.json")
            self.assertIn("send", send_only_example)
            self.assertNotIn("receive", send_only_example)

    def test_generates_receive_only_example(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "listener.py").write_text(
                textwrap.dedent(
                    """
                    # @specmatic-asyncapi
                    # {
                    #   "kind": "message",
                    #   "name": "DeliveryEvent",
                    #   "contentType": "application/json",
                    #   "payloadSchema": {
                    #     "type": "object",
                    #     "properties": { "orderId": { "type": "integer" } }
                    #   }
                    # }
                    # @end-specmatic-asyncapi
                    class DeliveryEvent:
                        pass

                    # @specmatic-asyncapi
                    # {
                    #   "kind": "operation",
                    #   "role": "consumer",
                    #   "operationId": "deliverOrder",
                    #   "channel": { "name": "OrderDeliveryInitiated", "address": "out-for-delivery-orders" },
                    #   "message": "DeliveryEvent",
                    #   "example": {
                    #     "name": "ORDER_OUT_FOR_DELIVERY",
                    #     "payload": { "orderId": 456 }
                    #   }
                    # }
                    # @end-specmatic-asyncapi
                    def subscribe_delivery():
                        subscribe("out-for-delivery-orders")
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            example = self.read_json(repo / "examples" / slugify(repo.name) / "deliverorder.json")
            self.assertIn("receive", example)
            self.assertNotIn("send", example)

    def test_copies_openapi_dependency_specs_into_generated_suite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "src").mkdir()
            (repo / "specs").mkdir()
            (repo / "examples" / "tax-service").mkdir(parents=True)
            (repo / "examples" / "tax-service" / "raise-tax.json").write_text(
                json.dumps(
                    {
                        "name": "RAISE_TAX",
                        "http-request": {"method": "POST", "path": "/tax/invoices"},
                    },
                    indent=2,
                ) + "\n"
            )
            (repo / "specs" / "tax-service.yaml").write_text(
                textwrap.dedent(
                    """
                    openapi: 3.0.3
                    info:
                      title: Tax Service API
                      version: 1.0.0
                    paths:
                      /tax/invoices:
                        post:
                          operationId: raiseTaxInvoice
                          responses:
                            '201':
                              description: ok
                    """
                ).strip() + "\n"
            )
            (repo / "src" / "consumer.java").write_text(
                textwrap.dedent(
                    """
                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "OrderRequest",
                    //   "contentType": "application/json",
                    //   "payloadSchema": {
                    //     "type": "object",
                    //     "properties": { "id": { "type": "integer" } }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class OrderRequest {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "operation",
                    //   "role": "consumer",
                    //   "operationId": "placeOrder",
                    //   "channel": { "name": "NewOrderPlaced", "address": "new-orders" },
                    //   "message": "OrderRequest",
                    //   "example": {
                    //     "name": "NEW_ORDER",
                    //     "payload": { "id": 10 }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    @KafkaListener(topics = "new-orders")
                    public void handleNewOrder(String payload) {}
                    """
                ).strip() + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            report = self.read_json(repo / "asyncapi-extraction-report.json")
            suite_dir = Path(report["generated"]["suiteDir"])
            specmatic_text = (suite_dir / "specmatic.yaml").read_text()
            copied_dependency_spec = suite_dir / "specs" / "dependencies" / "tax-service.yaml"
            copied_dependency_examples = suite_dir / "examples" / "dependencies" / "tax-service" / "raise-tax.json"

            self.assertTrue(copied_dependency_spec.exists())
            self.assertTrue(copied_dependency_examples.exists())
            self.assertIn("dependencies:", specmatic_text)
            self.assertIn("#/components/services/taxservice", specmatic_text)
            self.assertIn("specs/dependencies/tax-service.yaml", specmatic_text)
            self.assertIn("examples/dependencies/tax-service", specmatic_text)

    def test_synthesizes_downstream_http_dependency_spec_when_no_checked_in_spec_exists(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "src").mkdir()
            (repo / "src" / "consumer.py").write_text(
                textwrap.dedent(
                    """
                    # @specmatic-asyncapi
                    # {
                    #   "kind": "message",
                    #   "name": "OrderRequest",
                    #   "contentType": "application/json",
                    #   "payloadSchema": {
                    #     "type": "object",
                    #     "properties": { "id": { "type": "integer" } }
                    #   }
                    # }
                    # @end-specmatic-asyncapi
                    class OrderRequest:
                        pass

                    # @specmatic-asyncapi
                    # {
                    #   "kind": "operation",
                    #   "role": "consumer",
                    #   "operationId": "placeOrder",
                    #   "channel": { "name": "NewOrderPlaced", "address": "new-orders" },
                    #   "message": "OrderRequest",
                    #   "example": {
                    #     "name": "NEW_ORDER",
                    #     "payload": { "id": 10 }
                    #   }
                    # }
                    # @end-specmatic-asyncapi
                    def handle():
                        requests.post("http://tax-service.local/tax/invoices", json={"orderId": 10})
                        subscribe("new-orders")
                    """
                ).strip() + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

            report = self.read_json(repo / "asyncapi-extraction-report.json")
            suite_dir = Path(report["generated"]["suiteDir"])
            specmatic_text = (suite_dir / "specmatic.yaml").read_text()
            generated_dependency_spec = suite_dir / "specs" / "dependencies" / "generated-taxservicelocal.yaml"

            self.assertTrue(generated_dependency_spec.exists())
            generated_spec_text = generated_dependency_spec.read_text()
            self.assertIn("openapi: 3.0.3", generated_spec_text)
            self.assertIn("/tax/invoices:", generated_spec_text)
            self.assertIn("post:", generated_spec_text)
            self.assertIn("#/components/services/taxservicelocal", specmatic_text)
            self.assertIn("specs/dependencies/generated-taxservicelocal.yaml", specmatic_text)

    def test_synthesizes_missing_annotations_from_code(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "src").mkdir()
            (repo / "src" / "app.properties").write_text("channel.new-orders=new-orders\n")
            (repo / "src" / "consumer.java").write_text(
                textwrap.dedent(
                    """
                    public class OrderRequest {
                        private Integer id;
                        private String name;
                    }

                    public class OrderListener {
                        @KafkaListener(topics = "${channel.new-orders}")
                        public void handle(OrderRequest request) {}
                    }
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            generated_annotations = (repo / "specmatic-asyncapi.generated.annotations.txt").read_text()
            self.assertIn('"generated": true', generated_annotations)
            self.assertIn('"operationId": "handle"', generated_annotations)
            self.assertIn('"message": "OrderRequest"', generated_annotations)
            asyncapi_text = (repo / "asyncapi-extracted.yaml").read_text()
            self.assertIn("OrderRequest:", asyncapi_text)
            self.assertIn("address: new-orders", asyncapi_text)

    def test_generates_examples_with_before_after_fixtures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "listener.java").write_text(
                textwrap.dedent(
                    """
                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "OrderAccepted",
                    //   "contentType": "application/json",
                    //   "payloadSchema": {
                    //     "type": "object",
                    //     "properties": { "id": { "type": "integer" } }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class OrderAccepted {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "operation",
                    //   "role": "publisher",
                    //   "operationId": "acceptOrder",
                    //   "channel": { "name": "OrderAccepted", "address": "accepted-orders" },
                    //   "message": "OrderAccepted",
                    //   "example": {
                    //     "name": "ACCEPT_ORDER",
                    //     "payload": { "id": 123 },
                    //     "before": [
                    //       {
                    //         "type": "http",
                    //         "wait": "PT1S",
                    //         "http-request": {
                    //           "baseUrl": "http://localhost:8080",
                    //           "path": "/orders",
                    //           "method": "PUT"
                    //         },
                    //         "http-response": { "status": 200 }
                    //       }
                    //     ],
                    //     "after": [
                    //       {
                    //         "type": "http",
                    //         "http-request": {
                    //           "baseUrl": "http://localhost:8080",
                    //           "path": "/orders/123",
                    //           "method": "GET"
                    //         },
                    //         "http-response": { "status": 200 }
                    //       }
                    //     ]
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    public void trigger() {
                        send("accepted-orders");
                    }
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            example = self.read_json(repo / "examples" / slugify(repo.name) / "acceptorder.json")
            self.assertIn("before", example)
            self.assertIn("after", example)
            self.assertEqual(example["before"][0]["http-response"]["status"], 200)

    def test_auto_annotates_unannotated_consumer_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "unannotated.java").write_text(
                textwrap.dedent(
                    """
                    public class Unannotated {
                        @KafkaListener(topics = "orders")
                        public void handle(String payload) {}
                    }
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            report = self.read_json(repo / "asyncapi-extraction-report.json")
            self.assertEqual(report["errors"], [])
            generated_annotations = (repo / "specmatic-asyncapi.generated.annotations.txt").read_text()
            self.assertIn('"operationId": "handle"', generated_annotations)

    def test_generates_local_avro_file_refs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "src" / "main" / "avro").mkdir(parents=True)
            (repo / "src" / "main" / "avro" / "NewOrders.avsc").write_text('{"type":"record","name":"NewOrders","fields":[]}\n')
            (repo / "messages.java").write_text(
                textwrap.dedent(
                    """
                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "OrderRequest",
                    //   "title": "An order request",
                    //   "avro": {
                    //     "source": "file",
                    //     "file": "src/main/avro/NewOrders.avsc"
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class OrderRequest {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "operation",
                    //   "role": "consumer",
                    //   "operationId": "placeOrder",
                    //   "channel": { "name": "NewOrders", "address": "new-orders" },
                    //   "message": "OrderRequest",
                    //   "example": {
                    //     "name": "NEW_ORDER",
                    //     "payload": { "id": 10 }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    @KafkaListener(topics = "new-orders")
                    public void handle(String payload) {}
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            asyncapi_text = (repo / "asyncapi-extracted.yaml").read_text()
            self.assertIn("schemaFormat: \"application/vnd.apache.avro+json;version=1.9.0\"", asyncapi_text)
            self.assertIn("$ref: ./src/main/avro/NewOrders.avsc", asyncapi_text)

    def test_generates_placeholder_registry_avro_refs_and_warning(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "src" / "main" / "resources").mkdir(parents=True)
            (repo / "src" / "main" / "resources" / "application.properties").write_text(
                "spring.kafka.properties.schema.registry.url=http://localhost:8085\n"
            )
            (repo / "register-schemas.sh").write_text(
                "curl http://localhost:8085/subjects/new-orders-value/versions/1/schema\n"
            )
            (repo / "messages.java").write_text(
                textwrap.dedent(
                    """
                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "OrderRequest",
                    //   "title": "An order request",
                    //   "avro": {
                    //     "source": "registry",
                    //     "ref": "http://localhost:8085/subjects/new-orders-value/versions/1/schema"
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class OrderRequest {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "operation",
                    //   "role": "consumer",
                    //   "operationId": "placeOrder",
                    //   "channel": { "name": "NewOrders", "address": "new-orders" },
                    //   "message": "OrderRequest",
                    //   "example": {
                    //     "name": "NEW_ORDER",
                    //     "payload": { "id": 10 }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    @KafkaListener(topics = "new-orders")
                    public void handle(String payload) {}
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            asyncapi_text = (repo / "asyncapi-extracted.yaml").read_text()
            self.assertIn('$ref: "<SCHEMA_REGISTRY_URL>/subjects/new-orders-value/versions/1/schema"', asyncapi_text)
            self.assertNotIn("http://localhost:8085/subjects/new-orders-value/versions/1/schema", asyncapi_text)

            report = self.read_json(repo / "asyncapi-extraction-report.json")
            self.assertTrue(any("SCHEMA_REGISTRY_BASE_URL" in warning for warning in report["warnings"]))

    def test_generates_servers_and_specmatic_yaml_for_kafka_avro(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "src" / "main" / "resources").mkdir(parents=True)
            (repo / "src" / "main" / "resources" / "application.properties").write_text(
                textwrap.dedent(
                    """
                    receive.protocol=kafka
                    send.protocol=kafka
                    spring.kafka.bootstrap-servers=localhost:9092
                    spring.kafka.properties.security.protocol=SASL_PLAINTEXT
                    spring.kafka.properties.sasl.mechanism=PLAIN
                    spring.kafka.properties.sasl.jaas.config=test-config
                    spring.kafka.properties.basic.auth.credentials.source=USER_INFO
                    spring.kafka.properties.basic.auth.user.info=admin:admin-secret
                    spring.kafka.properties.schema.registry.url=http://localhost:8085
                    """
                ).strip()
                + "\n"
            )
            (repo / "messages.java").write_text(
                textwrap.dedent(
                    """
                    // @specmatic-asyncapi
                    // {
                    //   "kind": "message",
                    //   "name": "OrderRequest",
                    //   "avro": {
                    //     "source": "registry",
                    //     "subject": "new-orders-value",
                    //     "version": "1"
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    class OrderRequest {}

                    // @specmatic-asyncapi
                    // {
                    //   "kind": "operation",
                    //   "role": "consumer",
                    //   "operationId": "placeOrder",
                    //   "channel": { "name": "NewOrders", "address": "new-orders" },
                    //   "message": "OrderRequest",
                    //   "example": {
                    //     "name": "NEW_ORDER",
                    //     "payload": { "id": 10 }
                    //   }
                    // }
                    // @end-specmatic-asyncapi
                    @KafkaListener(topics = "new-orders")
                    public void handle(String payload) {}
                    """
                ).strip()
                + "\n"
            )

            result = self.run_extractor(repo)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            asyncapi_text = (repo / "asyncapi-extracted.yaml").read_text()
            self.assertIn("servers:", asyncapi_text)
            self.assertIn("protocol: kafka", asyncapi_text)
            self.assertIn("host: localhost:9092", asyncapi_text)

            report = self.read_json(repo / "asyncapi-extraction-report.json")
            suite_dir = Path(report["generated"]["suiteDir"])
            specmatic_text = (suite_dir / "specmatic.yaml").read_text()
            self.assertIn("schemaRegistry:", specmatic_text)
            self.assertIn("kind: CONFLUENT", specmatic_text)
            self.assertIn("replyTimeoutInMilliseconds: 10000", specmatic_text)


if __name__ == "__main__":
    unittest.main()
