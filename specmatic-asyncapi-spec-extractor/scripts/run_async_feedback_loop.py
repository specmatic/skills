#!/usr/bin/env python3
"""Run an async contract-test feedback loop against generated suite artifacts only."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


EXTRACTOR = Path(__file__).resolve().parent / "extract_asyncapi.py"
DEFAULT_SUITE_DIR = ".specmatic-async-generated"
DEFAULT_SUMMARY = "reports/feedback-loop-summary.json"
DEFAULT_ATTEMPT_LOG = "logs/feedback-loop-attempts.log.md"
DEFAULT_RAW_LOGS = "logs"
SCHEMASTORE_URL = "https://www.schemastore.org/specmatic.json"
DEFAULT_SPECMATIC_IMAGE = "specmatic/enterprise:latest"
FIX_LAYER_ORDER = ["annotations", "overlay", "timeouts"]

TIMEOUT_PATTERNS = (
    "timed out",
    "timeout",
    "waited for",
    "no message received",
    "reply timeout",
    "failed readiness check",
)
HARNESS_PATTERNS = (
    "connection refused",
    "broker not ready",
    "could not connect",
    "failed to connect",
    "schema_registry_base_url",
    "start the application",
    "start the broker",
)
CONTRACT_PATTERNS = (
    "no operation in the spec matched",
    "schema mismatch",
    "invalid example",
    "contract",
    "asyncapi",
    "expected",
    "mismatch",
)
IMPLEMENTATION_PATTERNS = (
    "nullpointerexception",
    "failed to process",
    "internal server error",
    "runtimeexception",
    "stacktrace",
    "exception in thread",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def detect_examples_dir(suite_dir: Path) -> Path:
    report_path = suite_dir / "reports" / "asyncapi-extraction-report.json"
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            generated = report.get("generated", {})
            suite_examples_dir = generated.get("suiteExamplesDir")
            if isinstance(suite_examples_dir, str):
                path = Path(suite_examples_dir)
                if path.exists():
                    return path
        except (json.JSONDecodeError, OSError):
            pass

    examples_root = suite_dir / "examples"
    if not examples_root.exists():
        return examples_root
    child_dirs = sorted(
        path for path in examples_root.iterdir()
        if path.is_dir() and path.name != "dependencies"
    )
    if len(child_dirs) == 1:
        return child_dirs[0]
    return examples_root


def list_example_files(suite_dir: Path) -> List[Path]:
    examples_dir = detect_examples_dir(suite_dir)
    if not examples_dir.exists():
        return []
    return sorted(path for path in examples_dir.rglob("*.json") if path.is_file())


def read_timeout_config(specmatic_path: Path) -> Dict[str, int]:
    text = read_text(specmatic_path)
    reply_match = re.search(r"replyTimeoutInMilliseconds:\s*(\d+)", text)
    readiness_match = re.search(r"subscriberReadinessWaitTimeInMilliseconds:\s*(\d+)", text)
    max_attempts_match = re.search(r"maxAttempts:\s*(\d+)", text)
    batch_size_match = re.search(r"batchSize:\s*(\d+)", text)
    return {
        "replyTimeoutInMilliseconds": int(reply_match.group(1)) if reply_match else 10000,
        "subscriberReadinessWaitTimeInMilliseconds": int(readiness_match.group(1)) if readiness_match else 2000,
        "maxAttempts": int(max_attempts_match.group(1)) if max_attempts_match else 5,
        "batchSize": int(batch_size_match.group(1)) if batch_size_match else 25,
    }


def update_timeout_config(specmatic_path: Path, reply_timeout_ms: int, readiness_timeout_ms: int) -> None:
    text = read_text(specmatic_path)
    replacements = {
        "replyTimeoutInMilliseconds": reply_timeout_ms,
        "subscriberReadinessWaitTimeInMilliseconds": readiness_timeout_ms,
    }
    for key, value in replacements.items():
        if re.search(rf"{key}:\s*\d+", text):
            text = re.sub(rf"({key}:\s*)\d+", rf"\g<1>{value}", text)
        else:
            text += f"\n{key}: {value}\n"
    specmatic_path.write_text(text, encoding="utf-8")


def classify_failure(output: str, return_code: int) -> str:
    if return_code == 0:
        return "success"
    lowered = output.lower()
    if any(pattern in lowered for pattern in TIMEOUT_PATTERNS):
        return "timeout"
    if any(pattern in lowered for pattern in HARNESS_PATTERNS):
        return "harness"
    if any(pattern in lowered for pattern in IMPLEMENTATION_PATTERNS):
        return "implementation"
    if any(pattern in lowered for pattern in CONTRACT_PATTERNS):
        return "contract"
    return "unknown"


def append_attempt_log(path: Path, attempt: int, command: Sequence[str], classification: str, action: str, result: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"## Attempt {attempt} - {now_iso()}\n")
        handle.write(f"- command: `{shlex.join(command)}`\n")
        handle.write(f"- classification: `{classification}`\n")
        handle.write(f"- action: {action}\n")
        handle.write(f"- result: {result}\n\n")


def default_test_command(suite_dir: Path) -> List[str]:
    if shutil.which("specmatic"):
        return ["specmatic", "test"]
    if shutil.which("docker"):
        return [
            "docker",
            "run",
            "--rm",
            "--network",
            "host",
            "-v",
            f"{suite_dir.resolve()}:/usr/src/app",
            DEFAULT_SPECMATIC_IMAGE,
            "test",
        ]
    raise RuntimeError("Neither `specmatic` nor `docker` is available for the async feedback loop")


def prepare_runtime(base_command: Sequence[str]) -> None:
    command = list(base_command)
    if command and command[0] == "docker" and any("specmatic/enterprise" in part for part in command):
        result = subprocess.run(
            ["docker", "pull", DEFAULT_SPECMATIC_IMAGE],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Failed to pull Specmatic image before running async contract tests.\n"
                + (result.stdout or "")
                + ("\n" + result.stderr if result.stderr else "")
            )


def validate_specmatic_config(specmatic_path: Path) -> List[str]:
    text = read_text(specmatic_path)
    required_patterns = {
        "version: 3": r"(?m)^\s*version:\s*3\s*$",
        "systemUnderTest": r"(?m)^\s*systemUnderTest:\s*$",
        "components": r"(?m)^\s*components:\s*$",
        "asyncapi runOptions": r"(?m)^\s*asyncapi:\s*$",
        "async test mode": r"(?m)^\s*type:\s*test\s*$",
    }
    errors = []
    for label, pattern in required_patterns.items():
        if not re.search(pattern, text):
            errors.append(f"Generated specmatic.yaml is missing required section: {label}")
    return errors


def schema_validate_specmatic_config(specmatic_path: Path) -> Dict[str, List[str]]:
    warnings: List[str] = []
    errors: List[str] = []
    if os.environ.get("SPECMATIC_ASYNC_SKIP_SCHEMA_VALIDATION") == "1":
        warnings.append("Skipped schema validation for generated specmatic.yaml because SPECMATIC_ASYNC_SKIP_SCHEMA_VALIDATION=1.")
        return {"warnings": warnings, "errors": errors}
    if not shutil.which("npx"):
        warnings.append(
            f"Skipped schema validation for {specmatic_path.name}: `npx` is not available. "
            f"Schema reference: {SCHEMASTORE_URL}"
        )
        return {"warnings": warnings, "errors": errors}

    command = [
        "npx",
        "--yes",
        "ajv-cli",
        "validate",
        "-s",
        SCHEMASTORE_URL,
        "-d",
        specmatic_path.name,
    ]
    result = subprocess.run(
        command,
        cwd=specmatic_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    lowered = output.lower()
    if result.returncode == 0:
        return {"warnings": warnings, "errors": errors}

    transient_markers = (
        "enoent",
        "eai_again",
        "network",
        "fetch failed",
        "unable to resolve",
        "getaddrinfo",
        "timed out",
        "not found: ajv-cli",
    )
    if any(marker in lowered for marker in transient_markers):
        warnings.append(
            "Skipped strict schema validation for generated specmatic.yaml because the validator toolchain "
            "or remote schema could not be reached."
        )
        return {"warnings": warnings, "errors": errors}

    errors.append("Generated specmatic.yaml failed SchemaStore validation:\n" + output.strip())
    return {"warnings": warnings, "errors": errors}


def validate_example_document(document: object, path: Path) -> List[str]:
    if not isinstance(document, dict):
        return [f"{path.name}: example file must contain a JSON object"]

    errors: List[str] = []
    if not isinstance(document.get("name"), str) or not document.get("name"):
        errors.append(f"{path.name}: missing non-empty `name`")

    has_receive = "receive" in document
    has_send = "send" in document
    if not (has_receive or has_send):
        errors.append(f"{path.name}: example must contain at least one of `receive` or `send`")

    for key in ("receive", "send", "retry", "dlq"):
        if key not in document:
            continue
        envelope = document[key]
        if not isinstance(envelope, dict):
            errors.append(f"{path.name}: `{key}` must be an object")
            continue
        if not isinstance(envelope.get("topic"), str) or not envelope.get("topic"):
            errors.append(f"{path.name}: `{key}.topic` must be a non-empty string")
        if "payload" not in envelope:
            errors.append(f"{path.name}: `{key}.payload` is required")
        if "headers" in envelope and not isinstance(envelope["headers"], dict):
            errors.append(f"{path.name}: `{key}.headers` must be an object when present")

    for fixture_key in ("before", "after"):
        if fixture_key in document and not isinstance(document[fixture_key], list):
            errors.append(f"{path.name}: `{fixture_key}` must be an array when present")

    return errors


def validate_generated_suite(suite_dir: Path) -> List[str]:
    errors = validate_specmatic_config(suite_dir / "specmatic.yaml")
    examples_dir = detect_examples_dir(suite_dir)
    if not examples_dir.exists():
        errors.append(f"Generated examples directory does not exist: {examples_dir.as_posix()}")
        return errors

    example_files = sorted(examples_dir.rglob("*.json"))
    if not example_files:
        errors.append(f"No generated externalised examples found under {examples_dir.as_posix()}")
        return errors

    for example_path in example_files:
        try:
            document = json.loads(example_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{example_path.name}: invalid JSON: {exc}")
            continue
        errors.extend(validate_example_document(document, example_path))

    return errors


def run_preflight_validation(suite_dir: Path) -> Optional[Dict[str, object]]:
    local_errors = validate_generated_suite(suite_dir)
    schema_result = schema_validate_specmatic_config(suite_dir / "specmatic.yaml")
    local_errors.extend(schema_result["errors"])
    if local_errors:
        return {
            "classification": "contract",
            "action": "validated generated config and examples locally",
            "output": "\n".join(local_errors),
            "warnings": schema_result["warnings"],
        }
    return {
        "classification": "success",
        "action": "validated generated config and examples locally",
        "output": "",
        "warnings": schema_result["warnings"],
    }


def read_prepare_script(suite_dir: Path) -> Optional[Path]:
    prepare_script = suite_dir / "scripts" / "prepare_async_test_data.sh"
    return prepare_script if prepare_script.exists() else None


def run_prepare_script(suite_dir: Path, attempt: int) -> Optional[Dict[str, str]]:
    prepare_script = read_prepare_script(suite_dir)
    if prepare_script is None:
        return None

    env = dict(os.environ)
    env.setdefault("SPECMATIC_ASYNC_SUITE_DIR", suite_dir.as_posix())
    result = subprocess.run(
        ["sh", prepare_script.as_posix(), str(attempt)],
        cwd=suite_dir,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    if result.returncode != 0:
        return {
            "classification": "harness",
            "action": "ran generated deterministic setup hook",
            "output": output,
        }
    return {
        "classification": "success",
        "action": "ran generated deterministic setup hook",
        "output": output,
    }


def overlay_has_actions(suite_dir: Path) -> bool:
    overlay_path = suite_dir / "specs" / "asyncapi-overlay.yaml"
    text = read_text(overlay_path)
    return bool(re.search(r"(?m)^\s*-\s+", text))


def partition_examples(example_files: List[Path], batch_size: int) -> List[List[Path]]:
    if batch_size <= 0 or len(example_files) <= batch_size:
        return [example_files] if example_files else [[]]
    return [example_files[index : index + batch_size] for index in range(0, len(example_files), batch_size)]


def prepare_batch_suite(base_suite_dir: Path, batch_name: str, batch_files: List[Path]) -> Path:
    batch_root = base_suite_dir / ".batch-suites" / batch_name
    if batch_root.exists():
        shutil.rmtree(batch_root)
    batch_root.mkdir(parents=True, exist_ok=True)

    for folder in ("specs", "scripts"):
        source = base_suite_dir / folder
        if source.exists():
            shutil.copytree(source, batch_root / folder)

    source_examples_root = base_suite_dir / "examples"
    batch_examples_root = batch_root / "examples"
    batch_examples_root.mkdir(parents=True, exist_ok=True)

    service_examples_dir = detect_examples_dir(base_suite_dir)
    if service_examples_dir.exists():
        service_target_dir = batch_examples_root / service_examples_dir.relative_to(source_examples_root)
        service_target_dir.mkdir(parents=True, exist_ok=True)
        for example_file in batch_files:
            target = service_target_dir / example_file.name
            shutil.copyfile(example_file, target)

    dependency_examples_dir = source_examples_root / "dependencies"
    if dependency_examples_dir.exists():
        shutil.copytree(dependency_examples_dir, batch_examples_root / "dependencies")

    specmatic_text = read_text(base_suite_dir / "specmatic.yaml")
    batch_relative_examples_dir = detect_examples_dir(batch_root).relative_to(batch_root).as_posix()
    specmatic_text = re.sub(
        r'(?m)^(\s*-\s+directories:\s*\n\s*-\s+).*$',
        rf"\1{batch_relative_examples_dir}",
        specmatic_text,
        count=1,
    )
    (batch_root / "specmatic.yaml").write_text(specmatic_text, encoding="utf-8")
    return batch_root


def failure_bucket(classification: str) -> str:
    if classification in {"timeout", "harness", "contract"}:
        return "fixable"
    if classification in {"implementation", "unknown"}:
        return "non-fixable"
    return "none"


def failure_summary_entry(
    attempt: int,
    classification: str,
    action: str,
    log_path: Path,
    fix_layer: str,
) -> Dict[str, object]:
    return {
        "attempt": attempt,
        "classification": classification,
        "action": action,
        "log": log_path.as_posix(),
        "fixLayer": fix_layer,
    }


def command_with_timeouts(base_command: Sequence[str], timeout_config: Dict[str, int]) -> List[str]:
    command = list(base_command)
    overlay_path = Path("specs/asyncapi-overlay.yaml")
    if overlay_path.exists() and command and (command[0] == "specmatic" or (command[0] == "docker" and any("specmatic/enterprise" in part for part in command))):
        command.extend(["--overlay", overlay_path.as_posix()])
    command.extend(
        [
            "--reply-timeout",
            str(timeout_config["replyTimeoutInMilliseconds"]),
            "--subscriber-readiness-wait-time",
            str(timeout_config["subscriberReadinessWaitTimeInMilliseconds"]),
        ]
    )
    return command


def ensure_suite(
    repo_path: Path,
    suite_dir: Path,
    service_name: Optional[str],
) -> None:
    specmatic_path = suite_dir / "specmatic.yaml"
    if specmatic_path.exists():
        return
    command = [
        sys.executable,
        str(EXTRACTOR),
        str(repo_path),
        "--suite-dir",
        str(suite_dir),
        "--output",
        str(suite_dir / "specs" / "asyncapi-extracted.yaml"),
        "--report",
        str(suite_dir / "reports" / "asyncapi-extraction-report.json"),
        "--examples-dir",
        str(suite_dir / "examples"),
    ]
    if service_name:
        command.extend(["--service-name", service_name])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + "\n" + result.stderr)


def rerun_extraction(repo_path: Path, suite_dir: Path, service_name: Optional[str]) -> str:
    command = [
        sys.executable,
        str(EXTRACTOR),
        str(repo_path),
        "--suite-dir",
        str(suite_dir),
        "--output",
        str(suite_dir / "specs" / "asyncapi-extracted.yaml"),
        "--report",
        str(suite_dir / "reports" / "asyncapi-extraction-report.json"),
        "--examples-dir",
        str(suite_dir / "examples"),
    ]
    if service_name:
        command.extend(["--service-name", service_name])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.stdout + "\n" + result.stderr


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the async contract-test feedback loop.")
    parser.add_argument("repo_path", help="Path to the repository under test")
    parser.add_argument("--suite-dir", default=DEFAULT_SUITE_DIR, help="Generated suite directory")
    parser.add_argument("--service-name", help="Optional service name override")
    parser.add_argument("--test-command", help="Override the CLI test command")
    parser.add_argument("--assume-started", action="store_true", help="Skip the prompt asking the user to start the app and broker")
    parser.add_argument("--summary", default=DEFAULT_SUMMARY, help="Summary JSON path relative to the suite dir")
    return parser.parse_args(argv)


def run_loop(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_path = Path(args.repo_path).resolve()
    suite_dir = Path(args.suite_dir)
    if not suite_dir.is_absolute():
        suite_dir = repo_path / suite_dir

    ensure_suite(repo_path, suite_dir, args.service_name)
    specmatic_path = suite_dir / "specmatic.yaml"
    attempt_log = suite_dir / DEFAULT_ATTEMPT_LOG
    summary_path = suite_dir / args.summary
    raw_logs_dir = suite_dir / DEFAULT_RAW_LOGS
    raw_logs_dir.mkdir(parents=True, exist_ok=True)
    base_command = shlex.split(args.test_command) if args.test_command else default_test_command(suite_dir)

    if not args.assume_started:
        if base_command and base_command[0] == "docker":
            print("Start Docker Engine, the application, and the broker, then press Enter to continue.", file=sys.stderr)
        else:
            print("Start the application and broker, then press Enter to continue.", file=sys.stderr)
        try:
            input()
        except EOFError:
            pass

    prepare_runtime(base_command)
    preflight = run_preflight_validation(suite_dir)
    if preflight and preflight["classification"] != "success":
        log_path = raw_logs_dir / "attempt-000-preflight.log"
        log_output = preflight["output"]
        if preflight.get("warnings"):
            log_output = "\n".join(preflight["warnings"]) + ("\n" + log_output if log_output else "")
        log_path.write_text(log_output, encoding="utf-8")
        append_attempt_log(
            attempt_log,
            0,
            ["local-preflight-validation"],
            preflight["classification"],
            preflight["action"],
            "exit_code=1",
        )
        summary = {
            "suiteDir": suite_dir.as_posix(),
            "fixLayerOrder": FIX_LAYER_ORDER,
            "fixableFailures": [],
            "nonFixableFailures": [],
            "deferredFailures": [],
            "attempts": [
                {
                    "attempt": 0,
                    "command": ["local-preflight-validation"],
                    "classification": preflight["classification"],
                    "exitCode": 1,
                    "log": log_path.as_posix(),
                    "action": preflight["action"],
                    "fixLayer": "none",
                    "warnings": preflight.get("warnings", []),
                }
            ],
            "implementationFailures": [],
            "result": preflight["classification"],
        }
        preflight_entry = failure_summary_entry(
            attempt=0,
            classification=str(preflight["classification"]),
            action=str(preflight["action"]),
            log_path=log_path,
            fix_layer="none",
        )
        summary["fixableFailures"].append(preflight_entry)
        summary["deferredFailures"].append(preflight_entry)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        return 1

    timeout_config = read_timeout_config(specmatic_path)
    max_attempts = timeout_config["maxAttempts"]
    batch_size = timeout_config["batchSize"]
    example_files = list_example_files(suite_dir)
    batch_file_groups = partition_examples(example_files, batch_size)
    batched = len(batch_file_groups) > 1
    batch_suites: List[Tuple[str, Path, int]] = []
    if batched:
        for index, batch_files in enumerate(batch_file_groups, start=1):
            batch_name = f"batch-{index:03d}"
            batch_suites.append((batch_name, prepare_batch_suite(suite_dir, batch_name, batch_files), len(batch_files)))
    else:
        batch_suites.append(("batch-001", suite_dir, len(example_files)))
    summary: Dict[str, object] = {
        "suiteDir": suite_dir.as_posix(),
        "fixLayerOrder": FIX_LAYER_ORDER,
        "attempts": [],
        "implementationFailures": [],
        "preflightWarnings": preflight.get("warnings", []) if preflight else [],
        "fixableFailures": [],
        "nonFixableFailures": [],
        "deferredFailures": [],
        "batched": batched,
        "batchSize": batch_size,
        "batches": [
            {"name": batch_name, "suiteDir": batch_suite.as_posix(), "exampleCount": count}
            for batch_name, batch_suite, count in batch_suites
        ],
    }
    reextracted = False

    attempt_number = 0
    overall_result: Optional[str] = None
    for batch_index, (batch_name, initial_batch_suite_dir, batch_count) in enumerate(batch_suites):
        batch_suite_dir = initial_batch_suite_dir
        batch_specmatic_path = batch_suite_dir / "specmatic.yaml"
        batch_base_command = shlex.split(args.test_command) if args.test_command else default_test_command(batch_suite_dir)
        batch_timeout_config = read_timeout_config(batch_specmatic_path)
        batch_resolved = False

        for batch_attempt in range(1, max_attempts + 1):
            attempt_number += 1
            attempt = attempt_number
            fix_layer = "none"

            prepare_result = run_prepare_script(batch_suite_dir, attempt)
            if prepare_result and prepare_result["classification"] != "success":
                log_path = raw_logs_dir / f"attempt-{attempt:03d}.log"
                log_path.write_text(prepare_result["output"], encoding="utf-8")
                append_attempt_log(
                    attempt_log,
                    attempt,
                    ["sh", "scripts/prepare_async_test_data.sh", str(attempt)],
                    prepare_result["classification"],
                    f"{prepare_result['action']} ({batch_name})",
                    "exit_code=1",
                )
                summary["attempts"].append(
                    {
                        "attempt": attempt,
                        "command": ["sh", "scripts/prepare_async_test_data.sh", str(attempt)],
                        "classification": prepare_result["classification"],
                        "exitCode": 1,
                        "log": log_path.as_posix(),
                        "action": prepare_result["action"],
                        "fixLayer": fix_layer,
                        "batch": batch_name,
                        "batchExampleCount": batch_count,
                    }
                )
                failure_entry = failure_summary_entry(
                    attempt=attempt,
                    classification=str(prepare_result["classification"]),
                    action=f"{prepare_result['action']} ({batch_name})",
                    log_path=log_path,
                    fix_layer=fix_layer,
                )
                bucket = failure_bucket(str(prepare_result["classification"]))
                if bucket == "fixable":
                    summary["fixableFailures"].append(failure_entry)
                    summary["deferredFailures"].append(failure_entry)
                elif bucket == "non-fixable":
                    summary["nonFixableFailures"].append(failure_entry)
                overall_result = str(prepare_result["classification"])
                batch_resolved = False
                break

            command = command_with_timeouts(batch_base_command, batch_timeout_config)
            result = subprocess.run(command, cwd=batch_suite_dir, capture_output=True, text=True, check=False)
            output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
            classification = classify_failure(output, result.returncode)
            log_path = raw_logs_dir / f"attempt-{attempt:03d}.log"
            log_path.write_text(output, encoding="utf-8")

            action = "none"
            if classification == "timeout" and batch_attempt < max_attempts:
                batch_timeout_config["replyTimeoutInMilliseconds"] *= 2
                batch_timeout_config["subscriberReadinessWaitTimeInMilliseconds"] *= 2
                update_timeout_config(
                    batch_specmatic_path,
                    batch_timeout_config["replyTimeoutInMilliseconds"],
                    batch_timeout_config["subscriberReadinessWaitTimeInMilliseconds"],
                )
                action = "increased generated timeout settings"
                fix_layer = "timeouts"
            elif classification == "contract" and not reextracted:
                rerun_extraction(repo_path, suite_dir, args.service_name)
                if batched:
                    batch_suite_dir = prepare_batch_suite(suite_dir, batch_name, batch_file_groups[batch_index])
                    batch_specmatic_path = batch_suite_dir / "specmatic.yaml"
                    batch_base_command = shlex.split(args.test_command) if args.test_command else default_test_command(batch_suite_dir)
                    batch_timeout_config = read_timeout_config(batch_specmatic_path)
                reextracted = True
                action = "re-extracted generated suite"
                fix_layer = "annotations"
            elif classification == "contract" and overlay_has_actions(batch_suite_dir):
                action = "overlay present for manual spec-side corrections; no automatic overlay edit applied"
                fix_layer = "overlay"
            elif classification == "implementation":
                summary["implementationFailures"].append({"attempt": attempt, "log": log_path.as_posix(), "batch": batch_name})

            append_attempt_log(
                attempt_log,
                attempt,
                command,
                classification,
                f"{action} ({batch_name})" if action != "none" else batch_name,
                f"exit_code={result.returncode}",
            )
            summary["attempts"].append(
                {
                    "attempt": attempt,
                    "command": command,
                    "classification": classification,
                    "exitCode": result.returncode,
                    "log": log_path.as_posix(),
                    "action": action,
                    "fixLayer": fix_layer,
                    "batch": batch_name,
                    "batchExampleCount": batch_count,
                }
            )

            if classification != "success":
                failure_entry = failure_summary_entry(
                    attempt=attempt,
                    classification=classification,
                    action=f"{action} ({batch_name})" if action != "none" else batch_name,
                    log_path=log_path,
                    fix_layer=fix_layer,
                )
                bucket = failure_bucket(classification)
                if bucket == "fixable":
                    summary["fixableFailures"].append(failure_entry)
                elif bucket == "non-fixable":
                    summary["nonFixableFailures"].append(failure_entry)

            if classification == "success":
                batch_resolved = True
                overall_result = "success"
                break
            if classification == "timeout" and action != "none":
                continue
            if classification == "contract" and action != "none":
                continue

            if failure_bucket(classification) == "fixable":
                summary["deferredFailures"].append(
                    failure_summary_entry(
                        attempt=attempt,
                        classification=classification,
                        action=f"{action} ({batch_name})" if action != "none" else batch_name,
                        log_path=log_path,
                        fix_layer=fix_layer,
                    )
                )
            overall_result = classification
            batch_resolved = False
            break

        if not batch_resolved:
            if overall_result is None:
                overall_result = "max-attempts-reached"
            break

    if overall_result is None:
        overall_result = "success"
    summary["result"] = overall_result

    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if summary.get("result") == "success" else 1


if __name__ == "__main__":
    sys.exit(run_loop())
