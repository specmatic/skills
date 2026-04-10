#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


RULES = [
    ("environment-issue", re.compile(r"connection refused|timed out|broker|schema registry|not reachable|not running", re.I)),
    ("generated-config-mismatch", re.compile(r"specmatic\.yaml|config|overlay|examples directory|servers|schemaRegistry", re.I)),
    ("generated-example-mismatch", re.compile(r"example|payload|header|correlation|key|does not match", re.I)),
    ("generated-contract-mismatch", re.compile(r"channel|operation|message|reply|retry|dlq|\$ref|asyncapi", re.I)),
]


def classify_line(line: str) -> str:
    for label, pattern in RULES:
        if pattern.search(line):
            return label
    return "implementation-mismatch"


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_generated_server_host(specmatic_yaml: str) -> str | None:
    match = re.search(r'host:\s*"?(?P<host>[^"\n]+)"?', specmatic_yaml)
    return match.group("host") if match else None


def extract_timeout_topics(lines: list[str]) -> list[str]:
    topics: list[str] = []
    for line in lines:
        match = re.search(r"Timeout waiting for a message on topic '([^']+)'", line)
        if match:
            topics.append(match.group(1))
    return topics


def has_kafka_construction_failure(lines: list[str]) -> bool:
    joined = "\n".join(lines)
    return "Failed to construct kafka consumer" in joined or "Failed to construct kafka producer" in joined


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify Specmatic async test failures.")
    parser.add_argument("logfile", help="Path to a Specmatic async test log")
    args = parser.parse_args()

    log_path = Path(args.logfile).resolve()
    lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    generated_dir = log_path.parent.parent
    extraction_report = read_json(generated_dir / "extraction-report.json") or {}
    examples_dir = generated_dir / "examples"
    specmatic_yaml_text = (generated_dir / "specmatic.yaml").read_text(encoding="utf-8", errors="ignore") if (generated_dir / "specmatic.yaml").exists() else ""

    findings = []
    for line in lines:
        if not line.strip():
            continue
        if not re.search(r"fail|error|exception|mismatch|timed out|refused|invalid", line, re.I):
            continue
        findings.append({"classification": classify_line(line), "message": line})

    timeout_topics = set(extract_timeout_topics(lines))
    operations = extraction_report.get("operations", [])
    operation_by_channel = {op.get("requestChannel"): op for op in operations}
    generated_server = parse_generated_server_host(specmatic_yaml_text)
    suggested_servers = extraction_report.get("diagnostics", {}).get("runtimeHints", {}).get("suggestedAsyncServers", [])
    suggested_host = suggested_servers[0]["host"] if suggested_servers else None

    if has_kafka_construction_failure(lines) and generated_server and suggested_host and generated_server != suggested_host:
        findings.append(
            {
                "classification": "generated-config-mismatch",
                "message": f"Generated Kafka server host '{generated_server}' does not match inferred app bootstrap server '{suggested_host}'.",
                "suggestion": "Update generated specmatic/specmatic.yaml asyncapi.servers to the inferred bootstrap server from app config.",
                "action": "set_async_server_host",
                "host": suggested_host,
            }
        )

    for topic in sorted(timeout_topics):
        operation = operation_by_channel.get(topic)
        if not operation:
            continue
        example_path = examples_dir / extraction_report.get("serviceName", "") / f"{operation['operationId']}.json"
        example = read_json(example_path) if example_path.exists() else {}
        if operation.get("driveability") == "requires-http-trigger" and not example.get("before"):
            findings.append(
                {
                    "classification": "generated-example-mismatch",
                    "message": f"Send-only topic '{topic}' appears to require an HTTP trigger, but the generated example has no before fixture.",
                    "suggestion": "Add an HTTP before fixture using the triggerHints from extraction-report.json, or do not generate this standalone send-only test until a trigger is available.",
                    "triggerHints": operation.get("triggerHints", []),
                    "action": "add_http_before_fixture",
                    "operationId": operation["operationId"],
                    "topic": topic,
                }
            )
        if operation.get("driveability") == "covered-by-listener-flow":
            findings.append(
                {
                    "classification": "generated-example-mismatch",
                    "message": f"Send-only topic '{topic}' is already covered by listener-driven flow(s) {operation.get('coveredByOperationIds', [])}.",
                    "suggestion": "Remove or suppress the standalone send-only example if the listener scenario already validates this publish.",
                    "action": "remove_redundant_send_only_operation",
                    "operationId": operation["operationId"],
                    "topic": topic,
                }
            )

    output = {
        "logfile": str(log_path),
        "generatedDir": str(generated_dir),
        "findings": findings,
        "runtimeHints": extraction_report.get("diagnostics", {}).get("runtimeHints", {}),
    }
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
