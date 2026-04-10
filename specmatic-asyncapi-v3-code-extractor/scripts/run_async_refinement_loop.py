#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def resolve_generated_dir(target: Path) -> Path:
    if (target / "specmatic.yaml").exists() and (target / "extraction-report.json").exists():
        return target

    candidates = sorted(
        [
            child
            for child in target.iterdir()
            if child.is_dir() and (child.name == "specmatic" or child.name.startswith("specmatic-"))
        ],
        key=lambda path: (path.name != "specmatic", path.name),
    )
    if candidates:
        return candidates[0]
    return target / "specmatic"


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), text=True, capture_output=True)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def validate_examples(generated_dir: Path) -> list[str]:
    errors: list[str] = []
    for example_path in sorted((generated_dir / "examples").rglob("*.json")):
        try:
            payload = read_json(example_path)
        except json.JSONDecodeError as exc:
            errors.append(f"{example_path}: invalid JSON: {exc}")
            continue
        if "name" not in payload:
            errors.append(f"{example_path}: missing top-level 'name'")
        if not any(key in payload for key in ("receive", "send", "retry", "dlq")):
            errors.append(f"{example_path}: expected one of receive/send/retry/dlq")
    return errors


def infer_app_base_url(root: Path) -> str:
    specmatic_path = root / "specmatic.yaml"
    if specmatic_path.exists():
        for line in specmatic_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "baseUrl:" in line and "localhost" in line:
                return line.split("baseUrl:", 1)[1].strip().strip('"')

    for properties_path in [root / "src/main/resources/application.properties", root / "src/test/resources/application.properties"]:
        if properties_path.exists():
            properties = properties_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            server_port = next((line.split("=", 1)[1].strip() for line in properties if line.startswith("server.port=")), "8080")
            return f"http://localhost:{server_port}"

    return "http://localhost:8080"


def find_http_example_seed(root: Path, method: str, path: str) -> dict[str, Any] | None:
    resources_root = root / "src/test/resources"
    if not resources_root.exists():
        return None

    for candidate in sorted(resources_root.rglob("*.json")):
        try:
            payload = read_json(candidate)
        except Exception:
            continue
        entry = payload.get("partial", payload)
        http_request = entry.get("http-request")
        http_response = entry.get("http-response")
        if not isinstance(http_request, dict):
            continue
        req_method = str(http_request.get("method", "")).upper()
        req_path = str(http_request.get("path", ""))
        if req_method != method.upper():
            continue
        if req_path == path or req_path.startswith(path + "?"):
            return {
                "request": http_request,
                "response": http_response or {},
                "source": str(candidate),
            }
    return None


def build_http_fixture(root: Path, trigger: dict[str, Any]) -> dict[str, Any]:
    method = trigger["method"].upper()
    path = trigger["path"]
    seed = find_http_example_seed(root, method, path)
    base_url = infer_app_base_url(root)
    request: dict[str, Any] = {
        "baseUrl": base_url,
        "path": path,
        "method": method,
    }

    if seed:
        seed_request = seed["request"]
        request["path"] = seed_request.get("path", path)
        for key in ("headers", "query", "body"):
            if key in seed_request:
                request[key] = seed_request[key]
        response = seed.get("response", {})
        status = response.get("status", 200)
    else:
        if method in {"POST", "PUT", "PATCH"}:
            request["headers"] = {"Content-Type": "application/json"}
            request["body"] = {}
        status = 200

    return {
        "type": "http",
        "wait": "PT1S",
        "http-request": request,
        "http-response": {
            "status": status
        },
    }


def set_async_server_host(specmatic_path: Path, host: str) -> bool:
    text = specmatic_path.read_text(encoding="utf-8")
    updated = text.replace(
        f'host: "{host}"',
        f'host: "{host}"',
    )
    if updated == text:
        updated = text
        lines = []
        replaced = False
        for line in text.splitlines():
            if "host:" in line and not replaced:
                indent = line.split("host:")[0]
                lines.append(f'{indent}host: "{host}"')
                replaced = True
            else:
                lines.append(line)
        updated = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    if updated != text:
        specmatic_path.write_text(updated, encoding="utf-8")
        return True
    return False


def rerender_generated_suite(root: Path, generated_dir: Path) -> bool:
    script = Path(__file__).with_name("extract_asyncapi_suite.py")
    result = run(
        [
            "python3",
            str(script),
            "generate",
            str(root),
            "--report",
            str(generated_dir / "extraction-report.json"),
            "--approved",
            str(generated_dir / "approved-operations.json"),
        ],
        cwd=root,
    )
    return result.returncode == 0


def remove_redundant_operation(root: Path, generated_dir: Path, operation_id: str) -> bool:
    approved_path = generated_dir / "approved-operations.json"
    if not approved_path.exists():
        return False
    approved = read_json(approved_path)
    operations = approved.get("operations", approved)
    filtered = [op for op in operations if op.get("operationId") != operation_id]
    if len(filtered) == len(operations):
        return False
    write_json(approved_path, {"operations": filtered})
    return rerender_generated_suite(root, generated_dir)


def add_http_before_fixture(root: Path, generated_dir: Path, operation_id: str, trigger_hints: list[dict[str, Any]]) -> bool:
    service_name = read_json(generated_dir / "extraction-report.json")["serviceName"]
    example_path = generated_dir / "examples" / service_name / f"{operation_id}.json"
    if not example_path.exists() or not trigger_hints:
        return False
    example = read_json(example_path)
    if example.get("before"):
        return False
    example["before"] = [build_http_fixture(root, trigger_hints[0])]
    write_json(example_path, example)
    return True


def apply_remediations(root: Path, generated_dir: Path, findings: list[dict[str, Any]]) -> list[str]:
    applied: list[str] = []
    applied_actions: set[tuple[str, str]] = set()
    specmatic_path = generated_dir / "specmatic.yaml"

    for finding in findings:
        action = finding.get("action")
        if not action:
            continue
        key = (action, str(finding.get("operationId") or finding.get("host") or ""))
        if key in applied_actions:
            continue

        if action == "set_async_server_host" and finding.get("host"):
            if set_async_server_host(specmatic_path, finding["host"]):
                applied.append(f"Updated async server host to {finding['host']}.")
                applied_actions.add(key)
        elif action == "remove_redundant_send_only_operation" and finding.get("operationId"):
            if remove_redundant_operation(root, generated_dir, finding["operationId"]):
                applied.append(f"Removed redundant standalone send-only operation {finding['operationId']}.")
                applied_actions.add(key)
        elif action == "add_http_before_fixture" and finding.get("operationId"):
            if add_http_before_fixture(root, generated_dir, finding["operationId"], finding.get("triggerHints", [])):
                applied.append(f"Added HTTP before fixture for {finding['operationId']}.")
                applied_actions.add(key)

    return applied


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a generated Specmatic async refinement loop.")
    parser.add_argument("target", help="Target application root or generated specmatic folder")
    parser.add_argument("--max-runs", type=int, default=3, help="Maximum loop iterations")
    args = parser.parse_args()

    root = Path(args.target).resolve()
    generated_dir = resolve_generated_dir(root)
    root = generated_dir.parent if generated_dir.name.startswith("specmatic") else root
    runner = generated_dir / "run_async_contract_tests.sh"
    reports_dir = generated_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    classifier = Path(__file__).with_name("classify_async_failures.py")

    for run_number in range(1, args.max_runs + 1):
        example_errors = validate_examples(generated_dir)
        if example_errors:
            (reports_dir / "example-validation-errors.json").write_text(json.dumps(example_errors, indent=2) + "\n", encoding="utf-8")
            print("Example validation failed. Fix generated examples before running Specmatic.")
            for error in example_errors:
                print(error)
            return 1

        result = run(["bash", str(runner), str(generated_dir)], cwd=root)
        log_path = reports_dir / f"specmatic-test-run-{run_number}.log"
        log_path.write_text(result.stdout + ("\n" + result.stderr if result.stderr else ""), encoding="utf-8")
        if result.returncode == 0:
            print(f"Specmatic async tests passed on run {run_number}.")
            return 0

        classification = run(["python3", str(classifier), str(log_path)], cwd=root)
        classification_path = reports_dir / f"specmatic-test-run-{run_number}-classification.json"
        classification_path.write_text(classification.stdout, encoding="utf-8")

        findings = json.loads(classification.stdout or "{}").get("findings", [])
        actionable = [finding for finding in findings if finding["classification"] in {
            "generated-contract-mismatch",
            "generated-example-mismatch",
            "generated-config-mismatch",
        }]
        if not actionable:
            print(f"Run {run_number} stopped on non-generated-artifact failures. See {classification_path}")
            return result.returncode or 1

        applied = apply_remediations(root, generated_dir, actionable)
        if not applied:
            print(f"Run {run_number} found generated-artifact issues but no automatic remediation applied. Review {classification_path}.")
            for finding in actionable:
                if finding.get("suggestion"):
                    print(f"- {finding['suggestion']}")
            return result.returncode or 1

        print(f"Run {run_number} applied generated-artifact remediations:")
        for item in applied:
            print(f"- {item}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
