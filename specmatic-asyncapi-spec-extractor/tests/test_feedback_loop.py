import json
import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch


RUNNER = Path(__file__).resolve().parents[1] / "scripts" / "run_async_feedback_loop.py"
RUNNER_SPEC = importlib.util.spec_from_file_location("async_feedback_loop", RUNNER)
RUNNER_MODULE = importlib.util.module_from_spec(RUNNER_SPEC)
assert RUNNER_SPEC.loader is not None
RUNNER_SPEC.loader.exec_module(RUNNER_MODULE)


class AsyncFeedbackLoopTest(unittest.TestCase):
    def run_loop(self, repo: Path, suite_dir: Path, test_command: str):
        env = dict(os.environ)
        env["SPECMATIC_ASYNC_SKIP_SCHEMA_VALIDATION"] = "1"
        return subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                str(repo),
                "--suite-dir",
                str(suite_dir),
                "--assume-started",
                "--test-command",
                test_command,
            ],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

    def test_feedback_loop_increases_timeouts_for_timeout_failures(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            suite_dir = repo / ".specmatic-async-generated"
            (suite_dir / "examples" / "orders").mkdir(parents=True)
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    x-specmatic-feedback-loop:
                      replyTimeoutInMilliseconds: 10000
                      subscriberReadinessWaitTimeInMilliseconds: 2000
                      maxAttempts: 3
                    """
                ).strip()
                + "\n"
            )
            (suite_dir / "examples" / "orders" / "ok.json").write_text(
                json.dumps(
                    {
                        "name": "OK",
                        "receive": {
                            "topic": "orders",
                            "payload": {"id": 1},
                        },
                    },
                    indent=2,
                )
                + "\n"
            )
            fake = repo / "fake_timeout_test.py"
            fake.write_text(
                textwrap.dedent(
                    """
                    import sys

                    args = sys.argv
                    reply_timeout = int(args[args.index("--reply-timeout") + 1])
                    if reply_timeout < 20000:
                        print("Timed out waiting for reply message")
                        raise SystemExit(1)
                    print("success")
                    """
                ).strip()
                + "\n"
            )

            result = self.run_loop(repo, suite_dir, f"{sys.executable} {fake}")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            updated_specmatic = (suite_dir / "specmatic.yaml").read_text()
            self.assertIn("replyTimeoutInMilliseconds: 20000", updated_specmatic)
            summary = json.loads((suite_dir / "reports" / "feedback-loop-summary.json").read_text())
            self.assertEqual(summary["result"], "success")
            self.assertEqual(summary["attempts"][0]["classification"], "timeout")
            self.assertTrue(summary["fixableFailures"])
            self.assertFalse(summary["deferredFailures"])

    def test_feedback_loop_flags_implementation_failures_without_touching_repo_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            source_file = repo / "src" / "main.py"
            source_file.parent.mkdir(parents=True)
            source_file.write_text("print('do not change me')\n")
            original_contents = source_file.read_text()

            suite_dir = repo / ".specmatic-async-generated"
            (suite_dir / "examples" / "orders").mkdir(parents=True)
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    x-specmatic-feedback-loop:
                      replyTimeoutInMilliseconds: 10000
                      subscriberReadinessWaitTimeInMilliseconds: 2000
                      maxAttempts: 2
                    """
                ).strip()
                + "\n"
            )
            (suite_dir / "examples" / "orders" / "ok.json").write_text(
                json.dumps(
                    {
                        "name": "OK",
                        "receive": {
                            "topic": "orders",
                            "payload": {"id": 1},
                        },
                    },
                    indent=2,
                )
                + "\n"
            )
            fake = repo / "fake_impl_test.py"
            fake.write_text(
                textwrap.dedent(
                    """
                    print("NullPointerException: implementation bug")
                    raise SystemExit(1)
                    """
                ).strip()
                + "\n"
            )

            result = self.run_loop(repo, suite_dir, f"{sys.executable} {fake}")
            self.assertEqual(result.returncode, 1)
            summary = json.loads((suite_dir / "reports" / "feedback-loop-summary.json").read_text())
            self.assertEqual(summary["result"], "implementation")
            self.assertTrue(summary["implementationFailures"])
            self.assertTrue(summary["nonFixableFailures"])
            self.assertEqual(source_file.read_text(), original_contents)

    def test_prepare_runtime_pulls_latest_specmatic_image_for_docker_path(self):
        calls = []

        def fake_run(command, capture_output=False, text=False, check=False):
            calls.append(command)

            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            return Result()

        with patch.object(RUNNER_MODULE.subprocess, "run", side_effect=fake_run):
            RUNNER_MODULE.prepare_runtime(["docker", "run", "--rm", "specmatic/enterprise:latest", "test"])

        self.assertEqual(calls, [["docker", "pull", "specmatic/enterprise:latest"]])

    def test_feedback_loop_fails_fast_on_invalid_generated_examples(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            suite_dir = repo / ".specmatic-async-generated"
            (suite_dir / "examples" / "orders").mkdir(parents=True)
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    x-specmatic-feedback-loop:
                      replyTimeoutInMilliseconds: 10000
                      subscriberReadinessWaitTimeInMilliseconds: 2000
                      maxAttempts: 2
                    """
                ).strip()
                + "\n"
            )
            (suite_dir / "examples" / "orders" / "bad.json").write_text(
                json.dumps({"name": "BAD_EXAMPLE"}, indent=2) + "\n"
            )
            fake = repo / "should_not_run.py"
            fake.write_text("raise SystemExit('test command should not run')\n")

            result = self.run_loop(repo, suite_dir, f"{sys.executable} {fake}")
            self.assertEqual(result.returncode, 1)
            summary = json.loads((suite_dir / "reports" / "feedback-loop-summary.json").read_text())
            self.assertEqual(summary["result"], "contract")
            self.assertEqual(summary["attempts"][0]["attempt"], 0)
            self.assertEqual(summary["attempts"][0]["classification"], "contract")
            self.assertTrue(summary["fixableFailures"])
            self.assertTrue(summary["deferredFailures"])

    def test_preflight_validation_accepts_valid_generated_suite(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir = Path(temp_dir)
            (suite_dir / "examples" / "orders").mkdir(parents=True)
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    """
                ).strip()
                + "\n"
            )
            (suite_dir / "examples" / "orders" / "ok.json").write_text(
                json.dumps(
                    {
                        "name": "OK",
                        "receive": {
                            "topic": "orders",
                            "payload": {"id": 1},
                        },
                    },
                    indent=2,
                )
                + "\n"
            )

            with patch.dict(os.environ, {"SPECMATIC_ASYNC_SKIP_SCHEMA_VALIDATION": "1"}):
                result = RUNNER_MODULE.run_preflight_validation(suite_dir)
            self.assertEqual(result["classification"], "success")

    def test_preflight_validation_ignores_dependency_example_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir = Path(temp_dir)
            (suite_dir / "reports").mkdir(parents=True)
            service_examples_dir = suite_dir / "examples" / "orders"
            dependency_examples_dir = suite_dir / "examples" / "dependencies" / "tax-service"
            service_examples_dir.mkdir(parents=True)
            dependency_examples_dir.mkdir(parents=True)
            (suite_dir / "reports" / "asyncapi-extraction-report.json").write_text(
                json.dumps(
                    {
                        "generated": {
                            "suiteExamplesDir": service_examples_dir.as_posix()
                        }
                    },
                    indent=2,
                ) + "\n"
            )
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    """
                ).strip()
                + "\n"
            )
            (service_examples_dir / "ok.json").write_text(
                json.dumps(
                    {
                        "name": "OK",
                        "receive": {
                            "topic": "orders",
                            "payload": {"id": 1},
                        },
                    },
                    indent=2,
                ) + "\n"
            )
            (dependency_examples_dir / "raise-tax.json").write_text(
                json.dumps(
                    {
                        "name": "RAISE_TAX",
                        "http-request": {"method": "POST", "path": "/tax/invoices"},
                    },
                    indent=2,
                ) + "\n"
            )

            with patch.dict(os.environ, {"SPECMATIC_ASYNC_SKIP_SCHEMA_VALIDATION": "1"}):
                result = RUNNER_MODULE.run_preflight_validation(suite_dir)
            self.assertEqual(result["classification"], "success")

    def test_run_prepare_script_executes_generated_hook(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            suite_dir = Path(temp_dir)
            (suite_dir / "scripts").mkdir(parents=True)
            marker = suite_dir / "reports" / "prepared.txt"
            (suite_dir / "scripts" / "prepare_async_test_data.sh").write_text(
                textwrap.dedent(
                    f"""
                    #!/bin/sh
                    set -eu
                    mkdir -p "{marker.parent.as_posix()}"
                    echo "$1" > "{marker.as_posix()}"
                    """
                ).strip()
                + "\n"
            )

            result = RUNNER_MODULE.run_prepare_script(suite_dir, 3)
            self.assertEqual(result["classification"], "success")
            self.assertEqual(marker.read_text().strip(), "3")

    def test_feedback_loop_summary_records_fix_layer_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            suite_dir = repo / ".specmatic-async-generated"
            (suite_dir / "examples" / "orders").mkdir(parents=True)
            (suite_dir / "scripts").mkdir(parents=True)
            (suite_dir / "scripts" / "prepare_async_test_data.sh").write_text(
                "#!/bin/sh\nset -eu\n",
            )
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    x-specmatic-feedback-loop:
                      replyTimeoutInMilliseconds: 10000
                      subscriberReadinessWaitTimeInMilliseconds: 2000
                      maxAttempts: 3
                    """
                ).strip()
                + "\n"
            )
            (suite_dir / "examples" / "orders" / "ok.json").write_text(
                json.dumps(
                    {
                        "name": "OK",
                        "receive": {
                            "topic": "orders",
                            "payload": {"id": 1}
                        }
                    },
                    indent=2,
                ) + "\n"
            )
            fake = repo / "fake_timeout_test.py"
            fake.write_text(
                textwrap.dedent(
                    """
                    import sys
                    args = sys.argv
                    reply_timeout = int(args[args.index("--reply-timeout") + 1])
                    if reply_timeout < 20000:
                        print("Timed out waiting for reply message")
                        raise SystemExit(1)
                    print("success")
                    """
                ).strip() + "\n"
            )

            result = self.run_loop(repo, suite_dir, f"{sys.executable} {fake}")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = json.loads((suite_dir / "reports" / "feedback-loop-summary.json").read_text())
            self.assertEqual(summary["fixLayerOrder"], ["annotations", "overlay", "timeouts"])
            self.assertEqual(summary["attempts"][0]["fixLayer"], "timeouts")

    def test_feedback_loop_marks_unresolved_harness_failure_as_deferred(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            suite_dir = repo / ".specmatic-async-generated"
            (suite_dir / "examples" / "orders").mkdir(parents=True)
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    x-specmatic-feedback-loop:
                      replyTimeoutInMilliseconds: 10000
                      subscriberReadinessWaitTimeInMilliseconds: 2000
                      maxAttempts: 2
                    """
                ).strip()
                + "\n"
            )
            (suite_dir / "examples" / "orders" / "ok.json").write_text(
                json.dumps(
                    {
                        "name": "OK",
                        "receive": {"topic": "orders", "payload": {"id": 1}},
                    },
                    indent=2,
                ) + "\n"
            )
            fake = repo / "fake_harness_test.py"
            fake.write_text(
                textwrap.dedent(
                    """
                    print("connection refused while contacting broker")
                    raise SystemExit(1)
                    """
                ).strip() + "\n"
            )

            result = self.run_loop(repo, suite_dir, f"{sys.executable} {fake}")
            self.assertEqual(result.returncode, 1)
            summary = json.loads((suite_dir / "reports" / "feedback-loop-summary.json").read_text())
            self.assertEqual(summary["result"], "harness")
            self.assertTrue(summary["fixableFailures"])
            self.assertTrue(summary["deferredFailures"])

    def test_feedback_loop_batches_large_example_sets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            suite_dir = repo / ".specmatic-async-generated"
            (suite_dir / "examples" / "orders").mkdir(parents=True)
            (suite_dir / "specmatic.yaml").write_text(
                textwrap.dedent(
                    """
                    version: 3
                    systemUnderTest:
                      service:
                        $ref: "#/components/services/orders"
                        runOptions:
                          $ref: "#/components/runOptions/ordersTest"
                        data:
                          examples:
                            - directories:
                                - examples/orders
                    components:
                      services:
                        orders:
                          definitions: []
                      runOptions:
                        ordersTest:
                          asyncapi:
                            type: test
                            servers: []
                    x-specmatic-feedback-loop:
                      replyTimeoutInMilliseconds: 10000
                      subscriberReadinessWaitTimeInMilliseconds: 2000
                      maxAttempts: 2
                      batchSize: 2
                    """
                ).strip()
                + "\n"
            )
            for index in range(5):
                (suite_dir / "examples" / "orders" / f"example-{index}.json").write_text(
                    json.dumps(
                        {
                            "name": f"EXAMPLE_{index}",
                            "receive": {"topic": "orders", "payload": {"id": index}},
                        },
                        indent=2,
                    ) + "\n"
                )
            fake = repo / "fake_success_test.py"
            fake.write_text("print('success')\n")

            result = self.run_loop(repo, suite_dir, f"{sys.executable} {fake}")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            summary = json.loads((suite_dir / "reports" / "feedback-loop-summary.json").read_text())
            self.assertTrue(summary["batched"])
            self.assertEqual(len(summary["batches"]), 3)
            self.assertTrue(all("batch" in attempt for attempt in summary["attempts"]))


if __name__ == "__main__":
    unittest.main()
