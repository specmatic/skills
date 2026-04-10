import importlib.util
import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_asyncapi_suite.py"
SPEC = importlib.util.spec_from_file_location("extract_asyncapi_suite", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ExtractAsyncApiSuiteTests(unittest.TestCase):
    def write_file(self, root: Path, relative_path: str, contents: str) -> None:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(contents).strip() + "\n", encoding="utf-8")

    def test_resolves_property_backed_topic_send(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_file(
                root,
                "src/main/resources/application.properties",
                """
                kafka.topic.product-queries=product-queries
                spring.kafka.bootstrap-servers=${KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
                """,
            )
            self.write_file(
                root,
                "src/main/kotlin/com/example/OrderService.kt",
                """
                package com.example

                import org.springframework.beans.factory.annotation.Value
                import org.springframework.kafka.core.KafkaTemplate

                class OrderService(private val kafkaTemplate: KafkaTemplate<String, String>) {
                    @Value("${kafka.topic.product-queries}")
                    lateinit var productQueriesTopic: String

                    fun findProducts() {
                        kafkaTemplate.send(productQueriesTopic, "payload")
                    }
                }
                """,
            )

            report = MODULE.infer_operations(root)
            channels = {op["requestChannel"] for op in report["operations"]}
            self.assertIn("product-queries", channels)
            runtime_hints = report["diagnostics"]["runtimeHints"]["kafkaBootstrapServers"]
            self.assertEqual(runtime_hints[0]["host"], "localhost:9092")

    def test_listener_keeps_unrelated_same_file_publish_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_file(
                root,
                "src/main/kotlin/com/example/OrderService.kt",
                """
                package com.example

                import org.springframework.kafka.annotation.KafkaListener
                import org.springframework.kafka.core.KafkaTemplate

                class OrderService(private val kafkaTemplate: KafkaTemplate<String, String>) {
                    @KafkaListener(topics = ["wip-orders"])
                    fun run(payload: String) {
                        initiateOrderDelivery()
                    }

                    private fun initiateOrderDelivery() {
                        kafkaTemplate.send("out-for-delivery-orders", "payload")
                    }

                    private fun sendNewOrdersEvent() {
                        kafkaTemplate.send("new-orders", "payload")
                    }
                }
                """,
            )

            report = MODULE.infer_operations(root)
            operation_index = {op["operationId"]: op for op in report["operations"]}
            self.assertIn("wip-orders-receive", operation_index)
            self.assertIn("out-for-delivery-orders-send", operation_index)
            self.assertIn("new-orders-send", operation_index)
            self.assertNotIn("wip-orders-new-orders", operation_index)

    def test_listener_call_chain_is_visible_in_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_file(
                root,
                "src/main/kotlin/com/example/OrderService.kt",
                """
                package com.example

                import org.springframework.kafka.annotation.KafkaListener
                import org.springframework.kafka.core.KafkaTemplate

                class OrderService(private val kafkaTemplate: KafkaTemplate<String, String>) {
                    @KafkaListener(topics = ["wip-orders"])
                    fun run(payload: String) {
                        firstHop()
                    }

                    private fun firstHop() {
                        secondHop()
                    }

                    private fun secondHop() {
                        kafkaTemplate.send("out-for-delivery-orders", "payload")
                    }
                }
                """,
            )

            report = MODULE.infer_operations(root)
            diagnostics = report["diagnostics"]["listenerPairing"]
            self.assertEqual(len(diagnostics), 1)
            self.assertEqual(diagnostics[0]["reachableMethods"], ["run", "firstHop", "secondHop"])
            self.assertEqual(diagnostics[0]["reachablePublishes"][0]["channel"], "out-for-delivery-orders")

    def test_choose_generated_dir_prefers_specmatic_then_increments(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.assertEqual(MODULE.choose_generated_dir(root), root / "specmatic")
            (root / "specmatic").mkdir()
            self.assertEqual(MODULE.choose_generated_dir(root), root / "specmatic-1")
            (root / "specmatic-1").mkdir()
            self.assertEqual(MODULE.choose_generated_dir(root), root / "specmatic-2")

    def test_generate_writes_specmatic_folder_with_docker_compose(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_file(
                root,
                "gradlew",
                """
                #!/bin/sh
                echo gradle
                """,
            )
            self.write_file(
                root,
                "src/main/resources/application.properties",
                """
                spring.kafka.bootstrap-servers=${KAFKA_BOOTSTRAP_SERVERS:localhost:9092}
                server.port=8085
                """,
            )

            report = {
                "serviceName": "sample-app",
                "signals": {"avroDetected": False},
                "diagnostics": {
                    "runtimeHints": {
                        "suggestedAsyncServers": [
                            {"host": "localhost:9092", "protocol": "kafka", "source": "application.properties"}
                        ]
                    }
                },
                "operations": [
                    {
                        "operationId": "orders-send",
                        "type": "send-only",
                        "applicationPerspective": "producer",
                        "requestChannel": "orders",
                        "replyChannel": None,
                        "retryChannel": None,
                        "dlqChannel": None,
                        "requestMessage": "OrdersMessage",
                        "replyMessage": None,
                        "requestSchemaHints": ["OrdersEvent"],
                        "replySchemaHints": [],
                        "correlationStrategy": "unknown",
                        "confidence": "high",
                        "evidence": [],
                        "unresolvedConcerns": [],
                    }
                ],
            }

            generated_dir = root / "specmatic"
            generated_dir.mkdir()
            report_path = generated_dir / "extraction-report.json"
            approved_path = generated_dir / "approved-operations.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            approved_path.write_text(json.dumps({"operations": report["operations"]}), encoding="utf-8")

            args = type("Args", (), {"target": str(root), "report": str(report_path), "approved": str(approved_path)})
            exit_code = MODULE.command_generate(args)
            self.assertEqual(exit_code, 0)
            self.assertTrue((generated_dir / "docker-compose.yml").exists())
            self.assertTrue((generated_dir / "specmatic.yaml").exists())
            compose_text = (generated_dir / "docker-compose.yml").read_text(encoding="utf-8")
            self.assertIn("specmatic-tests", compose_text)
            self.assertIn("specmatic/enterprise", compose_text)
            self.assertIn("kafka:29092", compose_text)
            runner_text = (generated_dir / "run_async_contract_tests.sh").read_text(encoding="utf-8")
            self.assertIn("localhost:9092", runner_text)

    def test_build_asyncapi_infers_payload_schema_from_kotlin_data_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            self.write_file(
                root,
                "src/main/kotlin/com/example/Publisher.kt",
                """
                package com.example

                import com.fasterxml.jackson.databind.ObjectMapper
                import org.springframework.kafka.core.KafkaTemplate

                class Publisher(private val kafkaTemplate: KafkaTemplate<String, String>) {
                    fun publish(orderId: Int) {
                        kafkaTemplate.send(
                            "new-orders",
                            ObjectMapper().writeValueAsString(NewOrderEvent.from(orderId))
                        )
                    }
                }

                data class NewOrderEvent(
                    val id: Int,
                    val orderItems: List<OrderItem>
                ) {
                    data class OrderItem(
                        val id: Int,
                        val quantity: Int
                    )

                    companion object {
                        fun from(orderId: Int): NewOrderEvent {
                            return NewOrderEvent(orderId, emptyList())
                        }
                    }
                }
                """,
            )

            report = MODULE.infer_operations(root)
            operation = next(op for op in report["operations"] if op["operationId"] == "new-orders-send")
            self.assertEqual(operation["requestSchemaHints"][0], "NewOrderEvent")

            asyncapi = MODULE.build_asyncapi(report, report["operations"])
            new_order_schema = asyncapi["components"]["schemas"]["NewOrderEvent"]
            self.assertEqual(new_order_schema["properties"]["id"]["type"], "integer")
            self.assertEqual(new_order_schema["properties"]["orderItems"]["type"], "array")
            self.assertEqual(
                new_order_schema["properties"]["orderItems"]["items"]["$ref"],
                "#/components/schemas/OrderItem",
            )
            order_item_schema = asyncapi["components"]["schemas"]["OrderItem"]
            self.assertEqual(order_item_schema["properties"]["quantity"]["type"], "integer")

    def test_real_order_bff_regression_if_repo_exists(self) -> None:
        root = Path("/Users/yogeshanandanikam/project/specmatic-order-bff-java")
        if not root.exists():
            self.skipTest("Local sample repo not present")

        report = MODULE.infer_operations(root)
        operation_index = {op["operationId"]: op for op in report["operations"]}

        self.assertIn("wip-orders-receive", operation_index)
        self.assertIn("out-for-delivery-orders-send", operation_index)
        self.assertIn("new-orders-send", operation_index)
        self.assertIn("product-queries-send", operation_index)
        self.assertNotIn("wip-orders-new-orders", operation_index)
        self.assertEqual(
            report["diagnostics"]["runtimeHints"]["suggestedAsyncServers"][0]["host"],
            "localhost:9092",
        )
        self.assertEqual(
            operation_index["new-orders-send"]["driveability"],
            "requires-http-trigger",
        )
        self.assertEqual(
            operation_index["product-queries-send"]["driveability"],
            "requires-http-trigger",
        )
        self.assertEqual(
            operation_index["out-for-delivery-orders-send"]["driveability"],
            "covered-by-listener-flow",
        )


if __name__ == "__main__":
    unittest.main()
