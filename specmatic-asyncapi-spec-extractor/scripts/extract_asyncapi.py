#!/usr/bin/env python3
"""Extract AsyncAPI 3.0.0 and Specmatic externalised examples from annotated code."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse


DEFAULT_OUTPUT = "asyncapi-extracted.yaml"
DEFAULT_REPORT = "asyncapi-extraction-report.json"
DEFAULT_EXAMPLES_ROOT = "examples"
DEFAULT_SUITE_DIR = ".specmatic-async-generated"
GENERATED_ANNOTATIONS_FILE = "specmatic-asyncapi.generated.annotations.txt"
COMMENT_START = "@specmatic-asyncapi"
COMMENT_END = "@end-specmatic-asyncapi"
BLOCK_WINDOW = 40
CONSUMER_REGION_WINDOW = 120
DEFAULT_EXCLUDES = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    "target",
    "build",
    "dist",
    ".venv",
    "venv",
    "__pycache__",
}
TEXT_EXTENSIONS = {
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".groovy",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
    ".rb",
    ".php",
    ".cs",
    ".go",
    ".rs",
    ".swift",
    ".yaml",
    ".yml",
    ".json",
    ".properties",
    ".conf",
    ".cfg",
    ".ini",
    ".xml",
    ".sql",
    ".txt",
}
CONSUMER_PATTERNS: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("KafkaListener", re.compile(r"@KafkaListener\b")),
    ("SqsListener", re.compile(r"@SqsListener\b")),
    ("JmsListener", re.compile(r"@JmsListener\b")),
    ("RabbitListener", re.compile(r"@RabbitListener\b")),
    ("Incoming", re.compile(r"@Incoming\b")),
    ("subscribe-call", re.compile(r"\bsubscribe\s*\(")),
    ("consumer-call", re.compile(r"\bconsume\w*\s*\(")),
    ("receive-call", re.compile(r"\breceive\w*\s*\(")),
)
PUBLISHER_PATTERNS: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("publish-call", re.compile(r"\bpublish\s*\(")),
    ("send-call", re.compile(r"(?<!@)\bsend\s*\(")),
    ("template-send", re.compile(r"\.\s*send\s*\(")),
    ("convertAndSend", re.compile(r"\bconvertAndSend\s*\(")),
    ("ProducerRecord", re.compile(r"\bProducerRecord\b")),
    ("KafkaTemplate", re.compile(r"\bKafkaTemplate\b")),
    ("emit-call", re.compile(r"\bemit\s*\(")),
)
SCHEMA_REGISTRY_PLACEHOLDER = "<SCHEMA_REGISTRY_URL>"
AVRO_SCHEMA_FORMAT = "application/vnd.apache.avro+json;version=1.9.0"
AVRO_CONTENT_TYPE = "application/vnd.apache.avro+json"
REGISTRY_SCHEMA_REF_RE = re.compile(
    r"https?://[^'\"]+/subjects/([^/\s]+)/versions/([^/\s]+)/schema"
)
REGISTRY_SUBJECT_RE = re.compile(r"/subjects/([^/\s]+)/versions(?:/([^/\s]+))?")
CONCRETE_REGISTRY_URL_RE = re.compile(r"https?://[^'\"]+/subjects/[^'\"]+/versions/[^'\"]+/schema")
HTTP_CALL_PATTERNS: Sequence[Tuple[str, re.Pattern[str], str]] = (
    ("requests", re.compile(r"\brequests\.(get|post|put|patch|delete)\(\s*[\"'](https?://[^\"']+)[\"']"), "direct"),
    ("httpx", re.compile(r"\bhttpx\.(get|post|put|patch|delete)\(\s*[\"'](https?://[^\"']+)[\"']"), "direct"),
    ("axios", re.compile(r"\baxios\.(get|post|put|patch|delete)\(\s*[\"'](https?://[^\"']+)[\"']"), "direct"),
    ("fetch", re.compile(r"\bfetch\(\s*[\"'](https?://[^\"']+)[\"']"), "fetch"),
    ("restTemplate", re.compile(r"\b(?:restTemplate|RestTemplate)\.(getForObject|getForEntity|postForObject|postForEntity|put|delete)\(\s*[\"'](https?://[^\"']+)[\"']"), "restTemplate"),
)


class ExtractionError(Exception):
    pass


@dataclass
class SourceRef:
    path: str
    start_line: int
    end_line: int
    code_line: Optional[int] = None
    detection_pattern: Optional[str] = None


@dataclass
class CommentBlock:
    data: Dict[str, Any]
    source: SourceRef


@dataclass
class MessageDef:
    name: str
    title: Optional[str]
    content_type: str
    payload_schema: Optional[Dict[str, Any]]
    headers_schema: Optional[Dict[str, Any]]
    correlation_id: Optional[Dict[str, str]]
    bindings: Optional[Dict[str, Any]]
    avro: Optional[Dict[str, Any]]
    source: SourceRef


@dataclass
class AvroEvidence:
    avsc_files: Dict[str, str]
    registry_urls: List[str]
    registry_subject_versions: Dict[str, str]
    registry_detected: bool


@dataclass
class BrokerServer:
    name: str
    protocol: str
    host: str
    description: Optional[str] = None
    admin_credentials: Dict[str, Any] = field(default_factory=dict)
    client_producer: Dict[str, Any] = field(default_factory=dict)
    client_consumer: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BrokerEvidence:
    servers: List[BrokerServer]
    active_protocols: List[str]
    schema_registry: Optional[Dict[str, Any]]
    properties: Dict[str, str]


@dataclass
class ExampleSeed:
    name: str
    payload: Any
    headers: Dict[str, Any] = field(default_factory=dict)
    key: Any = None
    example_id: Optional[str] = None
    before: List[Dict[str, Any]] = field(default_factory=list)
    after: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReplySeed:
    operation_id: Optional[str]
    channel_name: str
    address: str
    message_name: str
    example: ExampleSeed


@dataclass
class OperationSeed:
    role: str
    operation_id: str
    channel_name: str
    address: str
    message_name: str
    example: ExampleSeed
    replies: List[ReplySeed]
    source: SourceRef


@dataclass
class Candidate:
    role: str
    path: str
    line: int
    pattern: str
    text: str


@dataclass
class EmittedOperation:
    operation_id: str
    kind: str
    action: str
    inbound_channel_name: Optional[str]
    inbound_address: Optional[str]
    inbound_message: Optional[str]
    outbound_channel_name: Optional[str]
    outbound_address: Optional[str]
    outbound_message: Optional[str]
    example_name: str
    example_id: Optional[str]
    example_path: str
    source: SourceRef


@dataclass
class ClassInfo:
    name: str
    path: str
    line: int
    fields: List[Tuple[str, str]]


@dataclass
class DependencySpec:
    service_id: str
    spec_type: str
    spec_path: str
    source_path: str
    examples_dir: Optional[str] = None
    generated: bool = False


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return slug or "value"


def default_example_name(operation_id: str) -> str:
    return slugify(operation_id).replace("-", "_").upper()


def relative_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def strip_comment_prefix(line: str) -> str:
    stripped = line.rstrip("\n")
    stripped = re.sub(r"^\s*/\*\s?", "", stripped)
    stripped = re.sub(r"^\s*\*/\s?", "", stripped)
    stripped = re.sub(r"^\s*\*\s?", "", stripped)
    stripped = re.sub(r"^\s*//\s?", "", stripped)
    stripped = re.sub(r"^\s*#\s?", "", stripped)
    stripped = re.sub(r"^\s*--\s?", "", stripped)
    return stripped


def is_comment_or_blank(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    return bool(re.match(r"^(#|//|/\*|\*|\*/|--)", stripped))


def detect_pattern(line: str, patterns: Sequence[Tuple[str, re.Pattern[str]]]) -> Optional[str]:
    if is_comment_or_blank(line):
        return None
    for name, pattern in patterns:
        if pattern.search(line):
            return name
    return None


def should_skip(path: Path, root: Path, include_globs: Sequence[str], exclude_globs: Sequence[str]) -> bool:
    rel = relative_posix(path, root)
    parts = set(path.parts)
    if parts & DEFAULT_EXCLUDES:
        return True
    if exclude_globs and any(fnmatch(rel, pattern) for pattern in exclude_globs):
        return True
    if include_globs and not any(fnmatch(rel, pattern) for pattern in include_globs):
        return True
    return False


def iter_text_files(root: Path, include_globs: Sequence[str], exclude_globs: Sequence[str]) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue
        if should_skip(path, root, include_globs, exclude_globs):
            continue
        yield path


def parse_comment_blocks(root: Path, include_globs: Sequence[str], exclude_globs: Sequence[str]) -> Tuple[List[CommentBlock], Dict[str, List[str]]]:
    blocks: List[CommentBlock] = []
    file_cache: Dict[str, List[str]] = {}

    for path in iter_text_files(root, include_globs, exclude_globs):
        rel = relative_posix(path, root)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        file_cache[rel] = lines

        index = 0
        while index < len(lines):
            if COMMENT_START not in lines[index]:
                index += 1
                continue

            start = index + 1
            payload_lines: List[str] = []
            index += 1
            while index < len(lines) and COMMENT_END not in lines[index]:
                payload_lines.append(strip_comment_prefix(lines[index]))
                index += 1
            if index >= len(lines):
                raise ExtractionError(f"Unterminated {COMMENT_START} block in {rel}:{start}")

            raw = "\n".join(payload_lines).strip()
            if not raw:
                raise ExtractionError(f"Empty {COMMENT_START} block in {rel}:{start}")
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ExtractionError(f"Invalid JSON in comment block {rel}:{start}: {exc}") from exc

            blocks.append(
                CommentBlock(
                    data=data,
                    source=SourceRef(path=rel, start_line=start, end_line=index + 1),
                )
            )
            index += 1

    return blocks, file_cache


def load_file_cache(root: Path, include_globs: Sequence[str], exclude_globs: Sequence[str]) -> Dict[str, List[str]]:
    file_cache: Dict[str, List[str]] = {}
    for path in iter_text_files(root, include_globs, exclude_globs):
        rel = relative_posix(path, root)
        try:
            file_cache[rel] = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
    return file_cache


def scan_candidates(file_cache: Dict[str, List[str]]) -> Dict[str, List[Candidate]]:
    candidates: Dict[str, List[Candidate]] = {"consumer": [], "publisher": []}
    for rel, lines in file_cache.items():
        for idx, line in enumerate(lines, start=1):
            consumer_pattern = detect_pattern(line, CONSUMER_PATTERNS)
            if consumer_pattern:
                candidates["consumer"].append(
                    Candidate("consumer", rel, idx, consumer_pattern, line.strip())
                )
            publisher_pattern = detect_pattern(line, PUBLISHER_PATTERNS)
            if publisher_pattern:
                candidates["publisher"].append(
                    Candidate("publisher", rel, idx, publisher_pattern, line.strip())
                )
    return candidates


def constant_map(file_cache: Dict[str, List[str]], properties: Dict[str, str]) -> Dict[str, str]:
    constants = dict(properties)
    patterns = [
        re.compile(r"\b(?:private\s+|public\s+|protected\s+|internal\s+)?const\s+val\s+(\w+)\s*=\s*\"([^\"]+)\""),
        re.compile(r"\b(?:private\s+|public\s+|protected\s+)?static\s+final\s+String\s+(\w+)\s*=\s*\"([^\"]+)\""),
        re.compile(r"\bval\s+(\w+)\s*=\s*\"([^\"]+)\""),
    ]
    for lines in file_cache.values():
        for line in lines:
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    constants[match.group(1)] = match.group(2)
    return constants


def resolve_token(token: str, constants: Dict[str, str]) -> str:
    raw = token.strip().strip("[]{}()")
    raw = raw.rstrip(",")
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw.strip('"')
    if raw.startswith("'") and raw.endswith("'"):
        raw = raw.strip("'")
    placeholder = re.fullmatch(r"\$\{([^}:]+)(?::([^}]+))?\}", raw)
    if placeholder:
        key = placeholder.group(1)
        default = placeholder.group(2)
        return constants.get(key, default or key)
    return constants.get(raw, raw)


def infer_comment_prefix(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return "#" if suffix in {".py", ".sh", ".properties", ".yaml", ".yml", ".ini", ".cfg", ".conf"} else "//"


def nearby_block_exists(existing_operation_blocks: List[CommentBlock], candidate: Candidate) -> bool:
    for block in existing_operation_blocks:
        data = block.data
        source = data.get("source", {})
        block_path = source.get("file") if isinstance(source, dict) else None
        block_line = source.get("line") if isinstance(source, dict) else None
        if block_path == candidate.path and isinstance(block_line, int) and abs(block_line - candidate.line) <= BLOCK_WINDOW:
            return True
        if block.source.path == candidate.path and abs(block.source.end_line - candidate.line) <= BLOCK_WINDOW:
            return True
    return False


def find_signature_line(lines: List[str], start_line: int) -> Optional[int]:
    for idx in range(max(0, start_line - 1), min(len(lines), start_line + BLOCK_WINDOW)):
        text = lines[idx].strip()
        if re.search(r"\bfun\s+\w+\s*\(", text) or re.search(r"\bdef\s+\w+\s*\(", text):
            return idx + 1
        if re.search(r"\b(public|private|protected|internal)?\s*(suspend\s+)?[\w<>\[\],?. ]+\s+\w+\s*\(", text):
            return idx + 1
    return None


def extract_method_name(signature: str, fallback: str) -> str:
    for pattern in (
        re.compile(r"\bfun\s+(\w+)\s*\("),
        re.compile(r"\bdef\s+(\w+)\s*\("),
        re.compile(r"\b([A-Za-z_]\w*)\s*\("),
    ):
        match = pattern.search(signature)
        if match:
            return match.group(1)
    return fallback


def parse_method_params(signature: str) -> List[Tuple[str, str]]:
    params_match = re.search(r"\((.*)\)", signature)
    if not params_match:
        return []
    params_text = params_match.group(1)
    params: List[Tuple[str, str]] = []
    for part in [item.strip() for item in params_text.split(",") if item.strip()]:
        kotlin = re.match(r"(\w+)\s*:\s*([A-Za-z_][\w.<>,?]*)", part)
        if kotlin:
            params.append((kotlin.group(1), kotlin.group(2)))
            continue
        java = re.match(r"([A-Za-z_][\w.<>,?]*)\s+(\w+)$", part)
        if java:
            params.append((java.group(2), java.group(1)))
    return params


def clean_type_name(type_name: str) -> str:
    cleaned = type_name.split(".")[-1]
    cleaned = cleaned.replace("?", "")
    if "<" in cleaned and ">" in cleaned:
        inner = cleaned[cleaned.find("<") + 1: cleaned.rfind(">")]
        parts = [segment.strip().split(".")[-1] for segment in inner.split(",") if segment.strip()]
        if parts:
            cleaned = parts[-1]
    return cleaned


def infer_consumer_message_type(lines: List[str], candidate: Candidate) -> str:
    signature_line = find_signature_line(lines, candidate.line)
    if signature_line is None:
        return "MessagePayload"
    signature = lines[signature_line - 1]
    consumer_record = re.search(r"ConsumerRecord<[^,>]+,\s*([A-Za-z_][\w.]*)>", signature)
    if consumer_record:
        return clean_type_name(consumer_record.group(1))
    for _, param_type in parse_method_params(signature):
        cleaned = clean_type_name(param_type)
        if cleaned not in {"String", "Acknowledgment", "Message"}:
            return cleaned
    search_window = lines[signature_line - 1: min(len(lines), signature_line + 40)]
    for line in search_window:
        match = re.search(r"readValue\([^,]+,\s*([A-Za-z_][\w.]*)::class\.java\)", line) or re.search(
            r"readValue\([^,]+,\s*([A-Za-z_][\w.]*)\.class\)", line
        )
        if match:
            return clean_type_name(match.group(1))
    method_name = extract_method_name(signature, f"consumer_{candidate.line}")
    return f"{method_name[:1].upper()}{method_name[1:]}Message"


def build_variable_type_map(lines: List[str], start_line: int, end_line: int, params: List[Tuple[str, str]]) -> Dict[str, str]:
    mapping = {name: clean_type_name(type_name) for name, type_name in params}
    patterns = [
        re.compile(r"\b([A-Za-z_][\w.]*)\s+(\w+)\s*=\s*new\b"),
        re.compile(r"\bval\s+(\w+)\s*:\s*([A-Za-z_][\w.]*)"),
        re.compile(r"\bval\s+(\w+)\s*=\s*([A-Za-z_][\w.]*)\.newBuilder\("),
        re.compile(r"\bval\s+(\w+)\s*=\s*([A-Za-z_][\w.]*)\("),
        re.compile(r"\b([A-Za-z_][\w.]*)\s+(\w+)\s*="),
    ]
    for idx in range(max(0, start_line - 1), min(len(lines), end_line)):
        line = lines[idx]
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            if pattern.pattern.startswith("\\bval"):
                if "newBuilder" in pattern.pattern or r"\(" in pattern.pattern:
                    mapping[match.group(1)] = clean_type_name(match.group(2))
                else:
                    mapping[match.group(1)] = clean_type_name(match.group(2))
            else:
                mapping[match.group(2)] = clean_type_name(match.group(1))
    return mapping


def infer_send_calls(lines: List[str], candidate: Candidate, constants: Dict[str, str]) -> List[Tuple[str, str]]:
    signature_line = find_signature_line(lines, candidate.line)
    if signature_line is None:
        return []
    params = parse_method_params(lines[signature_line - 1])
    end_line = min(len(lines), signature_line + 80)
    variable_types = build_variable_type_map(lines, signature_line, end_line, params)
    replies: List[Tuple[str, str]] = []
    for idx in range(signature_line - 1, end_line):
        line = lines[idx]
        match = re.search(r"\bpublish\s*\((.+)\)", line) or re.search(r"\bsend\s*\((.+)\)", line)
        if not match:
            continue
        args = [part.strip() for part in match.group(1).split(",") if part.strip()]
        if not args:
            continue
        address = resolve_token(args[0], constants)
        payload_expr = args[1] if "publish" in line and len(args) > 1 else args[-1]
        message_type = "MessagePayload"
        new_builder = re.search(r"([A-Za-z_][\w.]*)\.newBuilder\(", payload_expr)
        if new_builder:
            message_type = clean_type_name(new_builder.group(1))
        elif payload_expr in variable_types:
            message_type = variable_types[payload_expr]
        else:
            json_payload = re.search(r"writeValueAsString\((\w+)\)", payload_expr)
            if json_payload and json_payload.group(1) in variable_types:
                message_type = variable_types[json_payload.group(1)]
        replies.append((address, message_type))
    return replies


def infer_candidate_channels(lines: List[str], candidate: Candidate, constants: Dict[str, str]) -> List[str]:
    text = candidate.text
    for pattern in (
        re.compile(r"topics\s*=\s*\[([^\]]+)\]"),
        re.compile(r"topics\s*=\s*([^,)]+)"),
        re.compile(r"destination\s*=\s*([^,)]+)"),
        re.compile(r"queues\s*=\s*([^,)]+)"),
    ):
        match = pattern.search(text)
        if match:
            raw_items = [item.strip() for item in match.group(1).split(",") if item.strip()]
            return [resolve_token(item, constants) for item in raw_items]
    send_match = re.search(r"\b(?:publish|send)\s*\(([^,)]+)", text)
    if send_match:
        return [resolve_token(send_match.group(1), constants)]
    return []


def build_class_index(file_cache: Dict[str, List[str]]) -> Dict[str, ClassInfo]:
    classes: Dict[str, ClassInfo] = {}
    for path, lines in file_cache.items():
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            match = re.search(r"\bdata\s+class\s+([A-Za-z_]\w*)\s*\(", line) or re.search(r"\bclass\s+([A-Za-z_]\w*)\s*\(", line) or re.search(r"\bclass\s+([A-Za-z_]\w*)\b", line)
            if not match:
                idx += 1
                continue
            class_name = match.group(1)
            fields: List[Tuple[str, str]] = []
            window = lines[idx: min(len(lines), idx + 20)]
            for candidate in window:
                for field_match in re.finditer(r"\b(?:val|var)\s+(\w+)\s*:\s*([A-Za-z_][\w.<>,?]*)", candidate):
                    fields.append((field_match.group(1), clean_type_name(field_match.group(2))))
                java_field = re.search(r"\b(?:private|public|protected)?\s*(?:final\s+)?([A-Za-z_][\w.<>,?]*)\s+(\w+)\s*;", candidate.strip())
                if java_field:
                    fields.append((java_field.group(2), clean_type_name(java_field.group(1))))
            classes.setdefault(class_name, ClassInfo(name=class_name, path=path, line=idx + 1, fields=fields))
            idx += 1
    return classes


def schema_and_example_for_class(class_info: Optional[ClassInfo]) -> Tuple[Dict[str, Any], Any]:
    if class_info is None or not class_info.fields:
        return ({"type": "object"}, {})
    properties: Dict[str, Any] = {}
    required: List[str] = []
    example: Dict[str, Any] = {}
    type_map = {
        "Int": ("integer", 1),
        "Integer": ("integer", 1),
        "Long": ("integer", 1),
        "Double": ("number", 1.0),
        "Float": ("number", 1.0),
        "String": ("string", "value"),
        "Boolean": ("boolean", True),
        "OrderStatus": ("string", "VALUE"),
    }
    for field_name, field_type in class_info.fields:
        json_type, sample = type_map.get(field_type, ("string", "value"))
        properties[field_name] = {"type": json_type}
        required.append(field_name)
        example[field_name] = sample
    return ({"type": "object", "required": required, "properties": properties}, example)


def address_to_channel_name(address: str) -> str:
    parts = [segment.capitalize() for segment in re.split(r"[^A-Za-z0-9]+", address) if segment]
    return "".join(parts) or "GeneratedChannel"


def address_to_subject(address: str) -> str:
    return f"{address}-value"


def address_to_avsc_guess(address: str) -> List[str]:
    camel = "".join(part.capitalize() for part in address.split("-") if part)
    return [camel.lower(), camel, address.replace("-", ""), address.lower()]


def infer_message_block(
    message_name: str,
    address: Optional[str],
    classes: Dict[str, ClassInfo],
    avro_evidence: AvroEvidence,
    source_file: str,
    source_line: int,
) -> Dict[str, Any]:
    class_info = classes.get(message_name)
    message_block: Dict[str, Any] = {
        "kind": "message",
        "generated": True,
        "name": message_name,
        "source": {"file": source_file, "line": source_line},
    }
    if avro_evidence.registry_detected or avro_evidence.avsc_files:
        if address:
            avro_info: Dict[str, Any] = {"source": "auto", "subject": address_to_subject(address)}
            guesses = address_to_avsc_guess(address)
            for guess in guesses:
                if guess in avro_evidence.avsc_files:
                    avro_info["file"] = avro_evidence.avsc_files[guess]
                    break
            message_block["title"] = f"{message_name} message"
            message_block["avro"] = avro_info
            return message_block
    schema, _ = schema_and_example_for_class(class_info)
    message_block["contentType"] = "application/json"
    message_block["payloadSchema"] = schema
    if class_info and class_info.fields:
        message_block["title"] = f"{message_name} message"
    return message_block


def synthesize_annotations(
    repo_path: Path,
    file_cache: Dict[str, List[str]],
    existing_blocks: List[CommentBlock],
    candidates: Dict[str, List[Candidate]],
    properties: Dict[str, str],
    avro_evidence: AvroEvidence,
) -> None:
    constants = constant_map(file_cache, properties)
    classes = build_class_index(file_cache)
    operation_blocks = [block for block in existing_blocks if block.data.get("kind") == "operation"]
    existing_messages = {
        str(block.data.get("name")): block
        for block in existing_blocks
        if block.data.get("kind") == "message" and block.data.get("name")
    }
    generated_operations: List[Dict[str, Any]] = []
    generated_messages: Dict[str, Dict[str, Any]] = {}

    consumer_candidates = [candidate for candidate in candidates["consumer"] if not nearby_block_exists(operation_blocks, candidate)]
    consumer_regions = [(candidate.path, candidate.line, candidate.line + CONSUMER_REGION_WINDOW) for candidate in consumer_candidates]
    publisher_candidates = []
    for candidate in candidates["publisher"]:
        if nearby_block_exists(operation_blocks, candidate):
            continue
        if any(path == candidate.path and start <= candidate.line <= end for path, start, end in consumer_regions):
            continue
        publisher_candidates.append(candidate)

    for candidate in consumer_candidates + publisher_candidates:
        lines = file_cache.get(candidate.path, [])
        addresses = infer_candidate_channels(lines, candidate, constants) or [f"unknown-{candidate.role}-{candidate.line}"]
        signature_line = find_signature_line(lines, candidate.line) or candidate.line
        signature = lines[signature_line - 1] if 0 <= signature_line - 1 < len(lines) else candidate.text
        method_name = extract_method_name(signature, f"{candidate.role}_{candidate.line}")
        message_name = infer_consumer_message_type(lines, candidate) if candidate.role == "consumer" else infer_consumer_message_type(lines, candidate)
        example_payload_schema, example_payload = schema_and_example_for_class(classes.get(message_name))
        operation_block: Dict[str, Any] = {
            "kind": "operation",
            "generated": True,
            "role": candidate.role,
            "operationId": method_name,
            "channel": {
                "name": address_to_channel_name(addresses[0]),
                "address": addresses[0],
            },
            "message": message_name,
            "example": {
                "name": default_example_name(method_name),
                "payload": example_payload,
            },
            "source": {
                "file": candidate.path,
                "line": candidate.line,
                "pattern": candidate.pattern,
            },
        }
        if candidate.role == "consumer":
            replies = []
            for reply_address, reply_message in infer_send_calls(lines, candidate, constants):
                _, reply_example = schema_and_example_for_class(classes.get(reply_message))
                replies.append(
                    {
                        "channel": {
                            "name": address_to_channel_name(reply_address),
                            "address": reply_address,
                        },
                        "message": reply_message,
                        "example": {
                            "name": default_example_name(f"{method_name}-{reply_address}"),
                            "payload": reply_example,
                        },
                    }
                )
                if reply_message not in existing_messages:
                    generated_messages.setdefault(
                        reply_message,
                        infer_message_block(reply_message, reply_address, classes, avro_evidence, candidate.path, candidate.line),
                    )
            if replies:
                operation_block["replies"] = replies
        generated_operations.append(operation_block)
        if message_name not in existing_messages:
            generated_messages.setdefault(
                message_name,
                infer_message_block(message_name, addresses[0], classes, avro_evidence, candidate.path, candidate.line),
            )

    generated_file = repo_path / GENERATED_ANNOTATIONS_FILE
    if not generated_operations and not generated_messages:
        if generated_file.exists():
            generated_file.unlink()
        return

    blocks: List[str] = []
    for block in list(generated_messages.values()) + generated_operations:
        prefix = infer_comment_prefix(GENERATED_ANNOTATIONS_FILE)
        blocks.append(f"{prefix} {COMMENT_START}")
        blocks.extend(f"{prefix} {line}" for line in json.dumps(block, indent=2).splitlines())
        blocks.append(f"{prefix} {COMMENT_END}")
        blocks.append("")
    generated_file.write_text("\n".join(blocks).rstrip() + "\n", encoding="utf-8")


def normalize_example(example_data: Dict[str, Any], operation_id: str) -> ExampleSeed:
    if "payload" not in example_data:
        raise ExtractionError(f"Operation '{operation_id}' is missing example.payload")
    return ExampleSeed(
        name=example_data.get("name") or default_example_name(operation_id),
        example_id=example_data.get("id"),
        payload=example_data["payload"],
        headers=example_data.get("headers") or {},
        key=example_data.get("key"),
        before=example_data.get("before") or [],
        after=example_data.get("after") or [],
    )


def normalize_message_block(block: CommentBlock) -> MessageDef:
    data = block.data
    if "name" not in data:
        raise ExtractionError(
            f"Message block {block.source.path}:{block.source.start_line} is missing 'name'"
        )
    correlation = data.get("correlationId")
    if correlation is not None:
        if not isinstance(correlation, dict) or not correlation.get("id") or not correlation.get("location"):
            raise ExtractionError(
                f"Message block {block.source.path}:{block.source.start_line} has an invalid correlationId"
            )

    has_payload_schema = "payloadSchema" in data
    has_avro = "avro" in data
    if has_payload_schema == has_avro:
        raise ExtractionError(
            f"Message block {block.source.path}:{block.source.start_line} must define exactly one of payloadSchema or avro"
        )
    if has_avro and not isinstance(data["avro"], dict):
        raise ExtractionError(
                f"Message block {block.source.path}:{block.source.start_line} has an invalid avro block"
            )
    if has_payload_schema and "contentType" not in data:
        raise ExtractionError(
            f"Message block {block.source.path}:{block.source.start_line} is missing 'contentType'"
        )

    source_ref = block.source
    source_override = data.get("source")
    if isinstance(source_override, dict) and source_override.get("file"):
        source_ref = SourceRef(
            path=str(source_override["file"]),
            start_line=int(source_override.get("line") or block.source.start_line),
            end_line=int(source_override.get("line") or block.source.end_line),
            code_line=int(source_override.get("line")) if source_override.get("line") else None,
            detection_pattern=source_override.get("pattern"),
        )

    return MessageDef(
        name=str(data["name"]),
        title=data.get("title"),
        content_type=str(data.get("contentType") or (AVRO_CONTENT_TYPE if has_avro else "")),
        payload_schema=data.get("payloadSchema"),
        headers_schema=data.get("headersSchema"),
        correlation_id=correlation,
        bindings=data.get("bindings"),
        avro=data.get("avro"),
        source=source_ref,
    )


def gather_avro_evidence(root: Path, file_cache: Dict[str, List[str]]) -> AvroEvidence:
    avsc_files: Dict[str, str] = {}
    registry_urls: List[str] = []
    registry_subject_versions: Dict[str, str] = {}
    registry_detected = False

    for path in root.rglob("*.avsc"):
        if path.is_file():
            rel = relative_posix(path, root)
            avsc_files.setdefault(path.stem.lower(), rel)

    for rel, lines in file_cache.items():
        for line in lines:
            lowered = line.lower()
            if "schema.registry.url" in lowered or "schemaregistry" in lowered or "kafka-avro-serializer" in lowered:
                registry_detected = True
            for url in re.findall(r"https?://[^\s'\"\\]+", line):
                if "schema" in url or "registry" in url:
                    registry_urls.append(url)
            for subject, version in REGISTRY_SCHEMA_REF_RE.findall(line):
                registry_subject_versions[subject] = version
                registry_detected = True
            for subject, version in REGISTRY_SUBJECT_RE.findall(line):
                if version:
                    registry_subject_versions.setdefault(subject, version)
                registry_detected = True

    return AvroEvidence(
        avsc_files=avsc_files,
        registry_urls=sorted(set(registry_urls)),
        registry_subject_versions=registry_subject_versions,
        registry_detected=registry_detected,
    )


def parse_properties(file_cache: Dict[str, List[str]]) -> Dict[str, str]:
    properties: Dict[str, str] = {}
    for rel, lines in file_cache.items():
        if not rel.endswith(".properties"):
            continue
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("!"):
                continue
            if "=" in stripped:
                key, value = stripped.split("=", 1)
            elif ":" in stripped:
                key, value = stripped.split(":", 1)
            else:
                continue
            properties[key.strip()] = value.strip()
    return properties


def has_text(file_cache: Dict[str, List[str]], pattern: str) -> bool:
    lowered = pattern.lower()
    return any(lowered in line.lower() for lines in file_cache.values() for line in lines)


def infer_schema_registry(properties: Dict[str, str], avro_evidence: AvroEvidence) -> Optional[Dict[str, Any]]:
    registry_url = (
        properties.get("spring.kafka.properties.schema.registry.url")
        or properties.get("schema.registry.url")
    )
    if not registry_url and not avro_evidence.registry_detected:
        return None

    default_url = registry_url or "http://localhost:8085"
    url = "${SCHEMA_REGISTRY_BASE_URL:" + default_url + "}"
    auth_user_info = (
        properties.get("spring.kafka.properties.basic.auth.user.info")
        or properties.get("schema.registry.basic.auth.user.info")
    )
    username = None
    password = None
    if auth_user_info and ":" in auth_user_info:
        username, password = auth_user_info.split(":", 1)

    return {
        "url": url,
        "kind": "CONFLUENT",
        "username": username,
        "password": password,
    }


def infer_broker_evidence(
    file_cache: Dict[str, List[str]],
    properties: Dict[str, str],
    avro_evidence: AvroEvidence,
) -> BrokerEvidence:
    active_protocols = []
    for key in ("receive.protocol", "send.protocol"):
        value = properties.get(key)
        if value and value not in active_protocols:
            active_protocols.append(value)

    servers: List[BrokerServer] = []

    kafka_detected = (
        "kafka" in active_protocols
        or "spring.kafka.bootstrap-servers" in properties
        or has_text(file_cache, "@KafkaListener")
        or has_text(file_cache, "KafkaTemplate")
    )
    if kafka_detected:
        kafka_admin = {}
        for prop in ("security.protocol", "sasl.mechanism", "sasl.jaas.config"):
            value = properties.get(f"spring.kafka.properties.{prop}")
            if value:
                kafka_admin[prop] = value
        kafka_producer = {}
        for prop in ("basic.auth.credentials.source", "basic.auth.user.info"):
            value = properties.get(f"spring.kafka.properties.{prop}")
            if value:
                kafka_producer[prop] = value
        servers.append(
            BrokerServer(
                name="kafkaServer",
                protocol="kafka",
                host=properties.get("spring.kafka.bootstrap-servers", "${KAFKA_BROKER_HOST:localhost:9092}"),
                description="Kafka broker",
                admin_credentials=kafka_admin,
                client_producer=kafka_producer,
            )
        )

    sqs_detected = (
        "sqs" in active_protocols
        or "spring.cloud.aws.sqs.endpoint" in properties
        or has_text(file_cache, "@SqsListener")
    )
    if sqs_detected:
        sqs_host = properties.get("spring.cloud.aws.sqs.endpoint") or properties.get("spring.cloud.aws.endpoint") or "http://localhost:4566"
        servers.append(
            BrokerServer(
                name="sqsServer",
                protocol="sqs",
                host=sqs_host,
                description="AWS SQS server",
                admin_credentials={
                    k: v
                    for k, v in {
                        "region": properties.get("spring.cloud.aws.region.static"),
                        "aws.access.key.id": properties.get("spring.cloud.aws.credentials.access-key"),
                        "aws.secret.access.key": properties.get("spring.cloud.aws.credentials.secret-key"),
                    }.items()
                    if v
                },
            )
        )

    jms_detected = (
        "jms" in active_protocols
        or "spring.artemis.host" in properties
        or has_text(file_cache, "@JmsListener")
    )
    if jms_detected:
        host = properties.get("spring.artemis.host", "localhost")
        port = properties.get("spring.artemis.port", "61616")
        servers.append(
            BrokerServer(
                name="jmsServer",
                protocol="jms",
                host=f"tcp://{host}:{port}",
                description="JMS server",
                admin_credentials={
                    k: v
                    for k, v in {
                        "username": properties.get("spring.artemis.user"),
                        "password": properties.get("spring.artemis.password"),
                    }.items()
                    if v
                },
            )
        )

    amqp_detected = (
        "amqp" in active_protocols
        or "spring.rabbitmq.host" in properties
        or has_text(file_cache, "@RabbitListener")
    )
    if amqp_detected:
        host = properties.get("spring.rabbitmq.host", "localhost")
        port = properties.get("spring.rabbitmq.port", "5672")
        servers.append(
            BrokerServer(
                name="amqpServer",
                protocol="amqp",
                host=f"amqp://{host}:{port}",
                description="AMQP server",
                admin_credentials={
                    k: v
                    for k, v in {
                        "username": properties.get("spring.rabbitmq.username"),
                        "password": properties.get("spring.rabbitmq.password"),
                    }.items()
                    if v
                },
            )
        )

    mqtt_detected = (
        "mqtt" in active_protocols
        or "mqtt.broker-url" in properties
        or has_text(file_cache, "MqttClient")
    )
    if mqtt_detected:
        servers.append(
            BrokerServer(
                name="mqttServer",
                protocol="mqtt",
                host=properties.get("mqtt.broker-url", "tcp://localhost:1884"),
                description="MQTT server",
                admin_credentials={
                    k: v
                    for k, v in {
                        "username": properties.get("mqtt.username"),
                        "password": properties.get("mqtt.password"),
                        "connection.timeout": properties.get("mqtt.connection-timeout"),
                    }.items()
                    if v
                },
            )
        )

    schema_registry = infer_schema_registry(properties, avro_evidence)
    return BrokerEvidence(
        servers=servers,
        active_protocols=active_protocols,
        schema_registry=schema_registry,
        properties=properties,
    )


def make_relative_ref(from_file: Path, target: Path) -> str:
    relative = os.path.relpath(target, from_file.parent).replace(os.sep, "/")
    if relative.startswith("../"):
        return relative
    if relative.startswith("./"):
        return relative
    return f"./{relative}"


def normalize_registry_ref(ref: str) -> str:
    match = REGISTRY_SCHEMA_REF_RE.search(ref)
    if match:
        subject, version = match.groups()
        return f"{SCHEMA_REGISTRY_PLACEHOLDER}/subjects/{subject}/versions/{version}/schema"
    if ref.startswith(f"{SCHEMA_REGISTRY_PLACEHOLDER}/subjects/"):
        return ref
    return ref


def infer_avro_file(message: MessageDef, avro: Dict[str, Any], evidence: AvroEvidence) -> Optional[str]:
    explicit = avro.get("file")
    if explicit:
        return str(explicit)
    candidates = [message.name.lower(), slugify(message.name).replace("-", ""), slugify(message.name)]
    for candidate in candidates:
        if candidate in evidence.avsc_files:
            return evidence.avsc_files[candidate]
    return None


def infer_registry_subject_version(message: MessageDef, avro: Dict[str, Any], evidence: AvroEvidence) -> Tuple[Optional[str], Optional[str]]:
    subject = avro.get("subject")
    version = avro.get("version")
    if subject and version:
        return str(subject), str(version)

    explicit_ref = avro.get("ref")
    if explicit_ref:
        match = REGISTRY_SCHEMA_REF_RE.search(str(explicit_ref))
        if match:
            return match.group(1), match.group(2)
        subject_match = re.search(r"/subjects/([^/\s]+)/versions/([^/\s]+)/schema", str(explicit_ref))
        if subject_match:
            return subject_match.group(1), subject_match.group(2)

    if subject and not version:
        return str(subject), str(evidence.registry_subject_versions.get(str(subject), "1"))

    channel_name = avro.get("channelAddress")
    if channel_name:
        guess = f"{channel_name}-value"
        return guess, str(evidence.registry_subject_versions.get(guess, "1"))

    for known_subject, known_version in evidence.registry_subject_versions.items():
        if slugify(message.name) in known_subject or message.name.lower() in known_subject.lower():
            return known_subject, known_version

    return (str(subject) if subject else None, str(version) if version else None)


def resolve_message_payload(
    message: MessageDef,
    repo_root: Path,
    output_path: Path,
    evidence: AvroEvidence,
    channel_addresses: Sequence[str],
) -> Tuple[Dict[str, Any], List[str]]:
    warnings: List[str] = []
    if message.avro is None:
        return (message.payload_schema or {}, warnings)

    avro = dict(message.avro)
    source = str(avro.get("source", "auto"))
    explicit_ref = avro.get("ref")
    if explicit_ref and CONCRETE_REGISTRY_URL_RE.search(str(explicit_ref)):
        warnings.append(
            f"Message '{message.name}' used a concrete schema registry URL. Rewriting it to placeholder form."
        )
        explicit_ref = normalize_registry_ref(str(explicit_ref))
    if channel_addresses and "channelAddress" not in avro:
        avro["channelAddress"] = channel_addresses[0]
    file_ref = infer_avro_file(message, avro, evidence)
    subject, version = infer_registry_subject_version(message, avro, evidence)

    chosen_source = source
    if source == "auto":
        if subject and (evidence.registry_detected or explicit_ref):
            chosen_source = "registry"
        elif file_ref:
            chosen_source = "file"
        elif subject:
            chosen_source = "registry"
        else:
            raise ExtractionError(
                f"Avro message '{message.name}' could not infer whether to use a local file or schema registry reference"
            )

    if chosen_source == "file":
        if not file_ref:
            raise ExtractionError(f"Avro message '{message.name}' is configured for file references but no .avsc file could be resolved")
        target = Path(file_ref)
        if not target.is_absolute():
            target = (repo_root / target).resolve()
        relative_ref = make_relative_ref(output_path, target)
        return (
            {
                "schemaFormat": AVRO_SCHEMA_FORMAT,
                "schema": {"$ref": relative_ref},
            },
            warnings,
        )

    if chosen_source == "registry":
        warnings.append(
            f"Message '{message.name}' uses schema registry references. Set SCHEMA_REGISTRY_BASE_URL before running Specmatic against the generated spec."
        )
        if explicit_ref:
            ref = normalize_registry_ref(str(explicit_ref))
        else:
            if not subject:
                raise ExtractionError(
                    f"Avro message '{message.name}' is configured for schema registry references but no subject could be resolved"
                )
            version = version or "1"
            ref = f"{SCHEMA_REGISTRY_PLACEHOLDER}/subjects/{subject}/versions/{version}/schema"
        return (
            {
                "schemaFormat": AVRO_SCHEMA_FORMAT,
                "schema": {"$ref": ref},
            },
            warnings,
        )

    raise ExtractionError(f"Avro message '{message.name}' has unsupported avro.source '{source}'")


def normalize_operation_block(block: CommentBlock) -> OperationSeed:
    data = block.data
    source_ref = block.source
    source_override = data.get("source")
    if isinstance(source_override, dict) and source_override.get("file"):
        source_ref = SourceRef(
            path=str(source_override["file"]),
            start_line=int(source_override.get("line") or block.source.start_line),
            end_line=int(source_override.get("line") or block.source.end_line),
            code_line=int(source_override.get("line")) if source_override.get("line") else None,
            detection_pattern=source_override.get("pattern"),
        )
    role = data.get("role")
    operation_id = data.get("operationId")
    channel = data.get("channel")
    message_name = data.get("message")
    example = data.get("example")

    if role not in {"consumer", "publisher"}:
        raise ExtractionError(
            f"Operation block {block.source.path}:{block.source.start_line} must set role to consumer or publisher"
        )
    if not operation_id:
        raise ExtractionError(
            f"Operation block {block.source.path}:{block.source.start_line} is missing operationId"
        )
    if not isinstance(channel, dict) or not channel.get("name") or not channel.get("address"):
        raise ExtractionError(
            f"Operation block {block.source.path}:{block.source.start_line} must define channel.name and channel.address"
        )
    if not message_name:
        raise ExtractionError(
            f"Operation block {block.source.path}:{block.source.start_line} is missing message"
        )
    if not isinstance(example, dict):
        raise ExtractionError(
            f"Operation block {block.source.path}:{block.source.start_line} must define example"
        )

    replies_data = data.get("replies") or []
    if role == "publisher" and replies_data:
        raise ExtractionError(
            f"Publisher operation '{operation_id}' cannot define replies"
        )

    replies: List[ReplySeed] = []
    for idx, reply in enumerate(replies_data, start=1):
        if not isinstance(reply, dict):
            raise ExtractionError(f"Operation '{operation_id}' has an invalid reply at index {idx}")
        reply_channel = reply.get("channel")
        if not isinstance(reply_channel, dict) or not reply_channel.get("name") or not reply_channel.get("address"):
            raise ExtractionError(
                f"Operation '{operation_id}' reply {idx} must define channel.name and channel.address"
            )
        reply_message = reply.get("message")
        if not reply_message:
            raise ExtractionError(f"Operation '{operation_id}' reply {idx} is missing message")
        reply_example = reply.get("example")
        if not isinstance(reply_example, dict):
            raise ExtractionError(f"Operation '{operation_id}' reply {idx} is missing example")

        reply_operation_id = reply.get("operationId")
        replies.append(
            ReplySeed(
                operation_id=reply_operation_id,
                channel_name=str(reply_channel["name"]),
                address=str(reply_channel["address"]),
                message_name=str(reply_message),
                example=normalize_example(reply_example, reply_operation_id or f"{operation_id}-{idx}"),
            )
        )

    return OperationSeed(
        role=role,
        operation_id=str(operation_id),
        channel_name=str(channel["name"]),
        address=str(channel["address"]),
        message_name=str(message_name),
        example=normalize_example(example, str(operation_id)),
        replies=replies,
        source=source_ref,
    )


def attach_operation_matches(operations: List[OperationSeed], file_cache: Dict[str, List[str]]) -> None:
    for operation in operations:
        lines = file_cache.get(operation.source.path, [])
        begin = max(0, operation.source.end_line - 1)
        end = min(len(lines), operation.source.end_line - 1 + BLOCK_WINDOW)
        patterns = CONSUMER_PATTERNS if operation.role == "consumer" else PUBLISHER_PATTERNS
        for idx in range(begin, end):
            match_name = detect_pattern(lines[idx], patterns)
            if match_name:
                operation.source.code_line = idx + 1
                operation.source.detection_pattern = match_name
                break
        if operation.source.code_line is None:
            raise ExtractionError(
                f"Annotated {operation.role} operation '{operation.operation_id}' in "
                f"{operation.source.path}:{operation.source.start_line} has no nearby matching code pattern"
            )


def detect_unannotated_candidates(
    operations: List[OperationSeed],
    candidates: Dict[str, List[Candidate]],
) -> List[str]:
    errors: List[str] = []
    operation_by_role = {"consumer": [], "publisher": []}
    for operation in operations:
        operation_by_role[operation.role].append(operation)

    consumer_regions: Dict[str, List[Tuple[int, int]]] = {}
    for operation in operation_by_role["consumer"]:
        if operation.source.code_line is None:
            continue
        consumer_regions.setdefault(operation.source.path, []).append(
            (operation.source.code_line, operation.source.code_line + CONSUMER_REGION_WINDOW)
        )

    for role, role_candidates in candidates.items():
        for candidate in role_candidates:
            matched = False
            for operation in operation_by_role[role]:
                if operation.source.path != candidate.path or operation.source.code_line is None:
                    continue
                if abs(operation.source.code_line - candidate.line) <= BLOCK_WINDOW:
                    matched = True
                    break
            if matched:
                continue

            if role == "publisher":
                regions = consumer_regions.get(candidate.path, [])
                if any(start <= candidate.line <= end for start, end in regions):
                    continue

            errors.append(
                f"Discovered {role} candidate without annotation at {candidate.path}:{candidate.line} "
                f"({candidate.pattern})"
            )

    return errors


def derive_reply_operation_id(base_operation_id: str, reply: ReplySeed) -> str:
    if reply.operation_id:
        return reply.operation_id
    return f"{base_operation_id}__to__{slugify(reply.channel_name or reply.address)}"


def build_asyncapi_and_examples(
    repo_root: Path,
    output_path: Path,
    service_name: str,
    operations: List[OperationSeed],
    messages: Dict[str, MessageDef],
    evidence: AvroEvidence,
    broker_evidence: BrokerEvidence,
    examples_root: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[EmittedOperation], List[str]]:
    channels: Dict[str, Dict[str, Any]] = {}
    operations_doc: Dict[str, Dict[str, Any]] = {}
    examples: List[Dict[str, Any]] = []
    emitted: List[EmittedOperation] = []
    correlation_ids: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    for message in messages.values():
        if message.correlation_id:
            correlation_ids[message.correlation_id["id"]] = {
                "location": message.correlation_id["location"]
            }

    components_messages: Dict[str, Dict[str, Any]] = {}
    message_to_addresses: Dict[str, List[str]] = {}
    for operation in operations:
        message_to_addresses.setdefault(operation.message_name, []).append(operation.address)
        for reply in operation.replies:
            message_to_addresses.setdefault(reply.message_name, []).append(reply.address)
    for message in messages.values():
        payload_doc, payload_warnings = resolve_message_payload(
            message,
            repo_root,
            output_path,
            evidence,
            message_to_addresses.get(message.name, []),
        )
        warnings.extend(payload_warnings)
        message_doc: Dict[str, Any] = {
            "name": message.name,
            "contentType": message.content_type or "application/json",
            "payload": payload_doc,
        }
        if message.title:
            message_doc["title"] = message.title
        if message.headers_schema is not None:
            message_doc["headers"] = message.headers_schema
        if message.bindings is not None:
            message_doc["bindings"] = message.bindings
        if message.correlation_id is not None:
            message_doc["correlationId"] = {
                "$ref": f"#/components/correlationIds/{message.correlation_id['id']}"
            }
        components_messages[message.name] = message_doc

    def ensure_channel(name: str, address: str, message_name: str) -> None:
        channels.setdefault(
            name,
            {
                "address": address,
                "messages": {
                    f"{slugify(message_name)}.message": {
                        "$ref": f"#/components/messages/{message_name}"
                    }
                },
            },
        )

    def message_ref(channel_name: str, message_name: str) -> str:
        return f"#/channels/{channel_name}/messages/{slugify(message_name)}.message"

    for operation in operations:
        if operation.message_name not in messages:
            raise ExtractionError(
                f"Operation '{operation.operation_id}' references unknown message '{operation.message_name}'"
            )
        ensure_channel(operation.channel_name, operation.address, operation.message_name)

        if operation.role == "publisher":
            op_id = operation.operation_id
            operations_doc[op_id] = {
                "action": "send",
                "channel": {"$ref": f"#/channels/{operation.channel_name}"},
                "messages": [{"$ref": message_ref(operation.channel_name, operation.message_name)}],
            }
            example_path = examples_root / f"{slugify(op_id)}.json"
            example_doc = {
                "name": operation.example.name,
                "send": {
                    "topic": operation.address,
                    "payload": operation.example.payload,
                },
            }
            if operation.example.before:
                example_doc["before"] = operation.example.before
            if operation.example.after:
                example_doc["after"] = operation.example.after
            if operation.example.example_id:
                example_doc["id"] = operation.example.example_id
            if operation.example.headers:
                example_doc["send"]["headers"] = operation.example.headers
            if operation.example.key is not None:
                example_doc["send"]["key"] = operation.example.key
            examples.append({"path": example_path, "document": example_doc})
            emitted.append(
                EmittedOperation(
                    operation_id=op_id,
                    kind="send-only",
                    action="send",
                    inbound_channel_name=None,
                    inbound_address=None,
                    inbound_message=None,
                    outbound_channel_name=operation.channel_name,
                    outbound_address=operation.address,
                    outbound_message=operation.message_name,
                    example_name=operation.example.name,
                    example_id=operation.example.example_id,
                    example_path=example_path.as_posix(),
                    source=operation.source,
                )
            )
            continue

        if not operation.replies:
            op_id = operation.operation_id
            operations_doc[op_id] = {
                "action": "receive",
                "channel": {"$ref": f"#/channels/{operation.channel_name}"},
                "messages": [{"$ref": message_ref(operation.channel_name, operation.message_name)}],
            }
            example_path = examples_root / f"{slugify(op_id)}.json"
            example_doc = {
                "name": operation.example.name,
                "receive": {
                    "topic": operation.address,
                    "payload": operation.example.payload,
                },
            }
            if operation.example.before:
                example_doc["before"] = operation.example.before
            if operation.example.after:
                example_doc["after"] = operation.example.after
            if operation.example.example_id:
                example_doc["id"] = operation.example.example_id
            if operation.example.headers:
                example_doc["receive"]["headers"] = operation.example.headers
            if operation.example.key is not None:
                example_doc["receive"]["key"] = operation.example.key
            examples.append({"path": example_path, "document": example_doc})
            emitted.append(
                EmittedOperation(
                    operation_id=op_id,
                    kind="receive-only",
                    action="receive",
                    inbound_channel_name=operation.channel_name,
                    inbound_address=operation.address,
                    inbound_message=operation.message_name,
                    outbound_channel_name=None,
                    outbound_address=None,
                    outbound_message=None,
                    example_name=operation.example.name,
                    example_id=operation.example.example_id,
                    example_path=example_path.as_posix(),
                    source=operation.source,
                )
            )
            continue

        for reply in operation.replies:
            if reply.message_name not in messages:
                raise ExtractionError(
                    f"Operation '{operation.operation_id}' references unknown reply message '{reply.message_name}'"
                )
            ensure_channel(reply.channel_name, reply.address, reply.message_name)
            op_id = derive_reply_operation_id(operation.operation_id, reply)
            operations_doc[op_id] = {
                "action": "receive",
                "channel": {"$ref": f"#/channels/{operation.channel_name}"},
                "messages": [{"$ref": message_ref(operation.channel_name, operation.message_name)}],
                "reply": {
                    "channel": {"$ref": f"#/channels/{reply.channel_name}"},
                    "messages": [{"$ref": message_ref(reply.channel_name, reply.message_name)}],
                },
            }
            example_path = examples_root / f"{slugify(op_id)}.json"
            example_doc = {
                "name": reply.example.name or operation.example.name,
                "receive": {
                    "topic": operation.address,
                    "payload": operation.example.payload,
                },
                "send": {
                    "topic": reply.address,
                    "payload": reply.example.payload,
                },
            }
            if operation.example.before:
                example_doc["before"] = operation.example.before
            after_fixtures = reply.example.after or operation.example.after
            if after_fixtures:
                example_doc["after"] = after_fixtures
            example_id = reply.example.example_id or operation.example.example_id
            if example_id:
                example_doc["id"] = example_id
            if operation.example.headers:
                example_doc["receive"]["headers"] = operation.example.headers
            if operation.example.key is not None:
                example_doc["receive"]["key"] = operation.example.key
            if reply.example.headers:
                example_doc["send"]["headers"] = reply.example.headers
            if reply.example.key is not None:
                example_doc["send"]["key"] = reply.example.key
            examples.append({"path": example_path, "document": example_doc})
            emitted.append(
                EmittedOperation(
                    operation_id=op_id,
                    kind="receive-reply",
                    action="receive",
                    inbound_channel_name=operation.channel_name,
                    inbound_address=operation.address,
                    inbound_message=operation.message_name,
                    outbound_channel_name=reply.channel_name,
                    outbound_address=reply.address,
                    outbound_message=reply.message_name,
                    example_name=example_doc["name"],
                    example_id=example_id,
                    example_path=example_path.as_posix(),
                    source=operation.source,
                )
            )

    asyncapi_doc: Dict[str, Any] = {
        "asyncapi": "3.0.0",
        "info": {"title": service_name, "version": "1.0.0"},
        "channels": channels,
        "operations": operations_doc,
        "components": {"messages": components_messages},
    }
    if broker_evidence.servers:
        asyncapi_doc["servers"] = {
            server.name: {
                k: v
                for k, v in {
                    "host": server.host,
                    "protocol": server.protocol,
                    "description": server.description,
                }.items()
                if v
            }
            for server in broker_evidence.servers
        }
    if correlation_ids:
        asyncapi_doc["components"]["correlationIds"] = correlation_ids
    return asyncapi_doc, examples, emitted, warnings


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if value == "":
            return '""'
        if re.match(r"^[A-Za-z0-9_.:/#@$%-]+$", value):
            return value
        return json.dumps(value)
    return json.dumps(value)


def to_yaml(value: Any, indent: int = 0) -> List[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return [prefix + "{}"]
        lines: List[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        if not value:
            return [prefix + "[]"]
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                nested = to_yaml(item, indent + 2)
                first = nested[0].lstrip()
                lines.append(f"{prefix}- {first}")
                for extra in nested[1:]:
                    lines.append(extra)
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines
    return [prefix + yaml_scalar(value)]


def build_report(
    service_name: str,
    emitted: List[EmittedOperation],
    warnings: List[str],
    errors: List[str],
    generated: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    report = {
        "service": service_name,
        "asyncapiVersion": "3.0.0",
        "operations": [
            {
                "operationId": op.operation_id,
                "kind": op.kind,
                "action": op.action,
                "source": {
                    "file": op.source.path,
                    "startLine": op.source.start_line,
                    "endLine": op.source.end_line,
                    "codeLine": op.source.code_line,
                    "detectionPattern": op.source.detection_pattern,
                },
                "inbound": (
                    {
                        "channelName": op.inbound_channel_name,
                        "address": op.inbound_address,
                        "message": op.inbound_message,
                    }
                    if op.inbound_channel_name
                    else None
                ),
                "outbound": (
                    {
                        "channelName": op.outbound_channel_name,
                        "address": op.outbound_address,
                        "message": op.outbound_message,
                    }
                    if op.outbound_channel_name
                    else None
                ),
                "example": {
                    "name": op.example_name,
                    "id": op.example_id,
                    "path": op.example_path,
                },
            }
            for op in emitted
        ],
        "warnings": warnings,
        "errors": errors,
    }
    if generated:
        report["generated"] = generated
    return report


def detect_spec_type(path: Path) -> Optional[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return None
    for line in lines[:40]:
        stripped = line.strip().lower()
        if stripped.startswith("openapi:"):
            return "openapi"
        if stripped.startswith("asyncapi:"):
            return "asyncapi"
    return None


def discover_dependency_specs(repo_root: Path, service_name: str) -> List[Tuple[Path, str]]:
    dependencies: List[Tuple[Path, str]] = []
    skip_dirs = {DEFAULT_SUITE_DIR, ".git", "build", "target", "dist", "node_modules"}
    service_slug = slugify(service_name)
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.suffix.lower() not in {".yaml", ".yml", ".json"}:
            continue
        if path.name in {DEFAULT_OUTPUT, DEFAULT_REPORT}:
            continue
        spec_type = detect_spec_type(path)
        if spec_type != "openapi":
            continue
        stem_slug = slugify(path.stem)
        if stem_slug == service_slug:
            continue
        dependencies.append((path, spec_type))
    deduped: List[Tuple[Path, str]] = []
    seen = set()
    for path, spec_type in dependencies:
        key = path.resolve().as_posix()
        if key in seen:
            continue
        seen.add(key)
        deduped.append((path, spec_type))
    return deduped


def infer_http_method(pattern_kind: str, match: re.Match[str], line: str) -> str:
    if pattern_kind == "fetch":
        method_match = re.search(r"method\s*:\s*[\"'](GET|POST|PUT|PATCH|DELETE)[\"']", line, re.IGNORECASE)
        return (method_match.group(1) if method_match else "GET").upper()
    if pattern_kind == "restTemplate":
        mapping = {
            "getForObject": "GET",
            "getForEntity": "GET",
            "postForObject": "POST",
            "postForEntity": "POST",
            "put": "PUT",
            "delete": "DELETE",
        }
        return mapping.get(match.group(1), "GET")
    return match.group(1).upper()


def infer_http_url(pattern_kind: str, match: re.Match[str]) -> str:
    if pattern_kind == "fetch":
        return match.group(1)
    return match.group(2)


def synthesize_openapi_dependency_specs(
    repo_root: Path,
    file_cache: Dict[str, List[str]],
    existing_service_ids: Sequence[str],
) -> List[Tuple[str, Dict[str, Any], str]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    existing_ids = set(existing_service_ids)

    for rel, lines in file_cache.items():
        for line in lines:
            for _, pattern, pattern_kind in HTTP_CALL_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                url = infer_http_url(pattern_kind, match)
                parsed = urlparse(url)
                if not parsed.scheme or not parsed.netloc:
                    continue
                service_id = slugify(parsed.hostname or parsed.netloc).replace("-", "") or "dependencyservice"
                if service_id in existing_ids:
                    continue
                path = parsed.path or "/"
                method = infer_http_method(pattern_kind, match, line)
                service = grouped.setdefault(
                    service_id,
                    {
                        "source_path": rel,
                        "host": parsed.netloc,
                        "paths": {},
                    },
                )
                operation_id = f"{method.lower()}{slugify(path).replace('-', '_') or 'root'}"
                path_item = service["paths"].setdefault(path, {})
                operation_doc: Dict[str, Any] = {
                    "operationId": operation_id,
                    "responses": {
                        "200": {
                            "description": "Generated mock response",
                            "content": {
                                "application/json": {
                                    "schema": {"type": "object"}
                                }
                            },
                        }
                    },
                }
                if method in {"POST", "PUT", "PATCH"}:
                    operation_doc["requestBody"] = {
                        "required": False,
                        "content": {
                            "application/json": {
                                "schema": {"type": "object"}
                            }
                        },
                    }
                path_item[method.lower()] = operation_doc

    generated_specs: List[Tuple[str, Dict[str, Any], str]] = []
    for service_id, service in grouped.items():
        doc = {
            "openapi": "3.0.3",
            "info": {
                "title": f"{service_id} dependency API",
                "version": "1.0.0",
            },
            "paths": service["paths"],
        }
        generated_specs.append((service_id, doc, service["source_path"]))
    return generated_specs


def build_specmatic_doc(
    service_name: str,
    suite_spec_path: str,
    suite_examples_path: str,
    broker_evidence: BrokerEvidence,
    dependencies: List[DependencySpec],
) -> Dict[str, Any]:
    service_id = slugify(service_name).replace("-", "")
    if not service_id:
        service_id = "asyncservice"
    run_options: Dict[str, Any] = {
        "asyncapi": {
            "type": "test",
            "servers": [
                {
                    k: v
                    for k, v in {
                        "host": server.host,
                        "protocol": server.protocol,
                        "adminCredentials": server.admin_credentials or None,
                        "client": (
                            {
                                key: value
                                for key, value in {
                                    "producer": server.client_producer or None,
                                    "consumer": server.client_consumer or None,
                                }.items()
                                if value
                            }
                            or None
                        ),
                    }.items()
                    if v is not None
                }
                for server in broker_evidence.servers
            ],
        }
    }
    if broker_evidence.schema_registry:
        run_options["asyncapi"]["schemaRegistry"] = {
            k: v for k, v in broker_evidence.schema_registry.items() if v is not None
        }

    services: Dict[str, Any] = {
        service_id: {
            "definitions": [
                {
                    "definition": {
                        "source": {"$ref": "#/components/sources/generatedContracts"},
                        "specs": [suite_spec_path],
                    }
                }
            ]
        }
    }
    run_options_block: Dict[str, Any] = {
        f"{service_id}Test": run_options,
    }
    dependencies_block: List[Dict[str, Any]] = []

    for dependency in dependencies:
        services[dependency.service_id] = {
            "definitions": [
                {
                    "definition": {
                        "source": {"$ref": "#/components/sources/generatedContracts"},
                        "specs": [dependency.spec_path],
                    }
                }
            ]
        }
        if dependency.spec_type == "openapi":
            run_options_block[f"{dependency.service_id}Mock"] = {
                "openapi": {
                    "type": "mock",
                    "baseUrl": f"${{{dependency.service_id.upper()}_BASE_URL:http://0.0.0.0:9000}}",
                }
            }
        dependency_service = {
            "service": {
                "$ref": f"#/components/services/{dependency.service_id}",
                "runOptions": {"$ref": f"#/components/runOptions/{dependency.service_id}Mock"},
            }
        }
        if dependency.examples_dir:
            dependency_service["service"]["data"] = {
                "examples": [{"directories": [dependency.examples_dir]}]
            }
        dependencies_block.append(dependency_service)

    doc = {
        "version": 3,
        "systemUnderTest": {
            "service": {
                "$ref": f"#/components/services/{service_id}",
                "runOptions": {"$ref": f"#/components/runOptions/{service_id}Test"},
                "data": {"examples": [{"directories": [suite_examples_path]}]},
            }
        },
        "components": {
            "sources": {
                "generatedContracts": {
                    "filesystem": {
                        "directory": ".",
                    }
                }
            },
            "services": services,
            "runOptions": run_options_block,
        },
        "x-specmatic-feedback-loop": {
            "replyTimeoutInMilliseconds": 10000,
            "subscriberReadinessWaitTimeInMilliseconds": 2000,
            "maxAttempts": 5,
            "batchSize": 25,
        },
    }
    if dependencies_block:
        doc["dependencies"] = {"services": dependencies_block}
    return doc


def write_suite_outputs(
    suite_dir: Path,
    repo_root: Path,
    file_cache: Dict[str, List[str]],
    service_name: str,
    asyncapi_doc: Dict[str, Any],
    examples: List[Dict[str, Any]],
    report_doc: Dict[str, Any],
    broker_evidence: BrokerEvidence,
) -> Dict[str, str]:
    suite_spec = suite_dir / "specs" / "asyncapi-extracted.yaml"
    suite_overlay = suite_dir / "specs" / "asyncapi-overlay.yaml"
    suite_examples_root = suite_dir / "examples" / slugify(service_name)
    suite_report = suite_dir / "reports" / "asyncapi-extraction-report.json"
    suite_logs_dir = suite_dir / "logs"
    suite_scripts_dir = suite_dir / "scripts"
    suite_prepare_script = suite_scripts_dir / "prepare_async_test_data.sh"
    suite_run_script = suite_dir / "run_async_contract_tests.sh"
    suite_dependency_specs_root = suite_dir / "specs" / "dependencies"
    suite_dependency_examples_root = suite_dir / "examples" / "dependencies"
    suite_logs_dir.mkdir(parents=True, exist_ok=True)
    suite_scripts_dir.mkdir(parents=True, exist_ok=True)
    suite_dependency_specs_root.mkdir(parents=True, exist_ok=True)
    suite_dependency_examples_root.mkdir(parents=True, exist_ok=True)

    suite_spec.parent.mkdir(parents=True, exist_ok=True)
    suite_spec.write_text("\n".join(to_yaml(asyncapi_doc)) + "\n", encoding="utf-8")
    suite_report.parent.mkdir(parents=True, exist_ok=True)
    suite_report.write_text(json.dumps(report_doc, indent=2) + "\n", encoding="utf-8")

    for example in examples:
        example_name = Path(example["path"]).name
        example_path = suite_examples_root / example_name
        example_path.parent.mkdir(parents=True, exist_ok=True)
        example_path.write_text(json.dumps(example["document"], indent=2) + "\n", encoding="utf-8")

    dependency_specs: List[DependencySpec] = []
    for dependency_path, spec_type in discover_dependency_specs(repo_root, service_name):
        dependency_filename = dependency_path.name
        copied_spec_path = suite_dependency_specs_root / dependency_filename
        copied_spec_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dependency_path, copied_spec_path)
        dependency_service_id = slugify(dependency_path.stem).replace("-", "") or "dependencyservice"
        dependency_examples_dir = None
        source_examples_dir = repo_root / "examples" / dependency_path.stem
        if source_examples_dir.exists() and source_examples_dir.is_dir():
            target_examples_dir = suite_dependency_examples_root / dependency_path.stem
            if target_examples_dir.exists():
                shutil.rmtree(target_examples_dir)
            shutil.copytree(source_examples_dir, target_examples_dir)
            dependency_examples_dir = relative_posix(target_examples_dir, suite_dir)
        dependency_specs.append(
            DependencySpec(
                service_id=dependency_service_id,
                spec_type=spec_type,
                spec_path=relative_posix(copied_spec_path, suite_dir),
                source_path=relative_posix(dependency_path, repo_root),
                examples_dir=dependency_examples_dir,
                generated=False,
            )
        )

    generated_dependency_specs = synthesize_openapi_dependency_specs(
        repo_root=repo_root,
        file_cache=file_cache,
        existing_service_ids=[dependency.service_id for dependency in dependency_specs],
    )
    for service_id, doc, source_path in generated_dependency_specs:
        generated_spec_path = suite_dependency_specs_root / f"generated-{service_id}.yaml"
        generated_spec_path.write_text("\n".join(to_yaml(doc)) + "\n", encoding="utf-8")
        dependency_specs.append(
            DependencySpec(
                service_id=service_id,
                spec_type="openapi",
                spec_path=relative_posix(generated_spec_path, suite_dir),
                source_path=source_path,
                examples_dir=None,
                generated=True,
            )
        )

    specmatic_doc = build_specmatic_doc(
        service_name=service_name,
        suite_spec_path="specs/asyncapi-extracted.yaml",
        suite_examples_path=f"examples/{slugify(service_name)}",
        broker_evidence=broker_evidence,
        dependencies=dependency_specs,
    )
    suite_specmatic = suite_dir / "specmatic.yaml"
    suite_specmatic.write_text("\n".join(to_yaml(specmatic_doc)) + "\n", encoding="utf-8")
    suite_overlay.write_text("overlay: 1.0.0\nactions: []\n", encoding="utf-8")
    suite_prepare_script.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                "",
                'ATTEMPT=\"${1:-default}\"',
                'MANIFEST_DIR=\"$(dirname \"$0\")/../reports\"',
                'MANIFEST_PATH=\"$MANIFEST_DIR/prepare-async-test-data-manifest.json\"',
                "mkdir -p \"$MANIFEST_DIR\"",
                "",
                "# Populate this script with deterministic setup steps for your async contract tests.",
                "# Examples:",
                "# - reset broker topics or queues used by the suite",
                "# - seed databases or HTTP state required by before/after fixtures",
                "# - refresh example values if they depend on deterministic IDs",
                "",
                "cat > \"$MANIFEST_PATH\" <<EOF",
                "{",
                "  \"attempt\": \"$ATTEMPT\",",
                f"  \"service\": {json.dumps(service_name)},",
                "  \"prepared\": false",
                "}",
                "EOF",
                "",
                'echo \"No project-specific async test data setup configured. Attempt: $ATTEMPT\"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    suite_prepare_script.chmod(0o755)
    suite_run_script.write_text(
        "\n".join(
            [
                "#!/bin/sh",
                "set -eu",
                "",
                'SUITE_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"',
                'PREPARE_SCRIPT="$SUITE_DIR/scripts/prepare_async_test_data.sh"',
                'REPLY_TIMEOUT="${REPLY_TIMEOUT:-10000}"',
                'SUBSCRIBER_READINESS_WAIT_TIME="${SUBSCRIBER_READINESS_WAIT_TIME:-2000}"',
                'SPECMATIC_IMAGE="${SPECMATIC_IMAGE:-specmatic/enterprise:latest}"',
                "",
                "# Preconditions:",
                "# 1. Start Docker Engine if you intend to use the Docker execution path.",
                "# 2. Start the application under test and the broker before running this script.",
                "# 3. Update scripts/prepare_async_test_data.sh if your suite needs deterministic setup.",
                "",
                'if [ -x "$PREPARE_SCRIPT" ]; then',
                '  "$PREPARE_SCRIPT" "full-run"',
                "fi",
                "",
                "if command -v specmatic >/dev/null 2>&1; then",
                '  exec specmatic test --overlay specs/asyncapi-overlay.yaml --reply-timeout "$REPLY_TIMEOUT" --subscriber-readiness-wait-time "$SUBSCRIBER_READINESS_WAIT_TIME"',
                "fi",
                "",
                "if ! command -v docker >/dev/null 2>&1; then",
                '  echo "Neither specmatic CLI nor docker is available." >&2',
                "  exit 1",
                "fi",
                "",
                'docker pull "$SPECMATIC_IMAGE"',
                'exec docker run --rm --network host -v "$SUITE_DIR:/usr/src/app" "$SPECMATIC_IMAGE" test --overlay specs/asyncapi-overlay.yaml --reply-timeout "$REPLY_TIMEOUT" --subscriber-readiness-wait-time "$SUBSCRIBER_READINESS_WAIT_TIME"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    suite_run_script.chmod(0o755)

    return {
        "suiteDir": suite_dir.as_posix(),
        "suiteSpecPath": suite_spec.as_posix(),
        "suiteOverlayPath": suite_overlay.as_posix(),
        "suiteExamplesDir": suite_examples_root.as_posix(),
        "suiteSpecmaticPath": suite_specmatic.as_posix(),
        "suiteReportPath": suite_report.as_posix(),
        "suiteLogsDir": suite_logs_dir.as_posix(),
        "suitePrepareScriptPath": suite_prepare_script.as_posix(),
        "suiteRunScriptPath": suite_run_script.as_posix(),
    }


def write_outputs(
    output_path: Path,
    report_path: Path,
    examples: List[Dict[str, Any]],
    asyncapi_doc: Dict[str, Any],
    report_doc: Dict[str, Any],
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(to_yaml(asyncapi_doc)) + "\n", encoding="utf-8")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_doc, indent=2) + "\n", encoding="utf-8")
    for example in examples:
        example_path: Path = example["path"]
        example_path.parent.mkdir(parents=True, exist_ok=True)
        example_path.write_text(json.dumps(example["document"], indent=2) + "\n", encoding="utf-8")


def extract_project(
    repo_path: Path,
    output_path: Path,
    report_path: Path,
    examples_dir: Path,
    suite_dir: Path,
    include_globs: Sequence[str],
    exclude_globs: Sequence[str],
    service_name: Optional[str] = None,
) -> int:
    warnings: List[str] = []
    errors: List[str] = []
    asyncapi_doc: Dict[str, Any] = {}
    examples: List[Dict[str, Any]] = []
    emitted: List[EmittedOperation] = []
    broker_evidence = BrokerEvidence(servers=[], active_protocols=[], schema_registry=None, properties={})
    generated_paths: Dict[str, str] = {}

    try:
        raw_file_cache = load_file_cache(repo_path, include_globs, exclude_globs)
        raw_properties = parse_properties(raw_file_cache)
        raw_candidates = scan_candidates(raw_file_cache)
        raw_blocks, _ = parse_comment_blocks(repo_path, include_globs, exclude_globs)
        raw_avro_evidence = gather_avro_evidence(repo_path, raw_file_cache)
        synthesize_annotations(
            repo_path=repo_path,
            file_cache=raw_file_cache,
            existing_blocks=raw_blocks,
            candidates=raw_candidates,
            properties=raw_properties,
            avro_evidence=raw_avro_evidence,
        )

        blocks, file_cache = parse_comment_blocks(repo_path, include_globs, exclude_globs)
        candidates = scan_candidates(file_cache)
        properties = parse_properties(file_cache)

        message_blocks = [block for block in blocks if block.data.get("kind") == "message"]
        operation_blocks = [block for block in blocks if block.data.get("kind") == "operation"]

        messages = {}
        for block in message_blocks:
            message = normalize_message_block(block)
            if message.name in messages:
                raise ExtractionError(
                    f"Duplicate message definition '{message.name}' in {block.source.path}:{block.source.start_line}"
                )
            messages[message.name] = message

        operations = [normalize_operation_block(block) for block in operation_blocks]
        attach_operation_matches(operations, file_cache)
        avro_evidence = gather_avro_evidence(repo_path, file_cache)
        broker_evidence = infer_broker_evidence(file_cache, properties, avro_evidence)

        errors.extend(detect_unannotated_candidates(operations, candidates))
        if not operations:
            errors.append("No annotated operation blocks found")
        if not messages:
            errors.append("No annotated message blocks found")

        inferred_service_name = service_name or repo_path.name.replace("-", " ").title()
        examples_root = examples_dir / slugify(service_name or repo_path.name)

        if not errors:
            asyncapi_doc, examples, emitted, payload_warnings = build_asyncapi_and_examples(
                repo_path,
                output_path,
                inferred_service_name,
                operations,
                messages,
                avro_evidence,
                broker_evidence,
                examples_root,
            )
            warnings.extend(payload_warnings)
    except ExtractionError as exc:
        errors.append(str(exc))

    report_doc = build_report(service_name or repo_path.name, emitted, warnings, errors)
    write_outputs(output_path, report_path, examples, asyncapi_doc, report_doc)
    if asyncapi_doc:
        generated_paths = write_suite_outputs(
            suite_dir=suite_dir,
            repo_root=repo_path,
            file_cache=file_cache,
            service_name=service_name or repo_path.name,
            asyncapi_doc=asyncapi_doc,
            examples=examples,
            report_doc=report_doc,
            broker_evidence=broker_evidence,
        )
        report_doc = build_report(service_name or repo_path.name, emitted, warnings, errors, generated=generated_paths)
        report_path.write_text(json.dumps(report_doc, indent=2) + "\n", encoding="utf-8")
        suite_report_path = Path(generated_paths["suiteReportPath"])
        suite_report_path.write_text(json.dumps(report_doc, indent=2) + "\n", encoding="utf-8")

    return 1 if errors else 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract AsyncAPI 3.0.0 and Specmatic externalised examples from annotated code."
    )
    parser.add_argument("repo_path", help="Path to the repository to scan")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="AsyncAPI output file")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="Extraction report JSON file")
    parser.add_argument(
        "--examples-dir",
        default=DEFAULT_EXAMPLES_ROOT,
        help="Root directory for generated externalised examples",
    )
    parser.add_argument(
        "--suite-dir",
        default=DEFAULT_SUITE_DIR,
        help="Directory for the generated contract-test suite",
    )
    parser.add_argument("--service-name", help="Service name used in the AsyncAPI info title")
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Glob pattern to include. Repeatable.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Glob pattern to exclude. Repeatable.",
    )
    return parser.parse_args(argv)


def resolve_output(base: Path, output: str) -> Path:
    candidate = Path(output)
    if candidate.is_absolute():
        return candidate
    return base / candidate


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists() or not repo_path.is_dir():
        print(f"Repository path is invalid: {repo_path}", file=sys.stderr)
        return 2

    output_path = resolve_output(repo_path, args.output)
    report_path = resolve_output(repo_path, args.report)
    examples_dir = resolve_output(repo_path, args.examples_dir)
    suite_dir = resolve_output(repo_path, args.suite_dir)

    return extract_project(
        repo_path=repo_path,
        output_path=output_path,
        report_path=report_path,
        examples_dir=examples_dir,
        suite_dir=suite_dir,
        include_globs=args.include,
        exclude_globs=args.exclude,
        service_name=args.service_name,
    )


if __name__ == "__main__":
    sys.exit(main())
    source_ref = block.source
    source_override = data.get("source")
    if isinstance(source_override, dict) and source_override.get("file"):
        source_ref = SourceRef(
            path=str(source_override["file"]),
            start_line=int(source_override.get("line") or block.source.start_line),
            end_line=int(source_override.get("line") or block.source.end_line),
            code_line=int(source_override.get("line")) if source_override.get("line") else None,
            detection_pattern=source_override.get("pattern"),
        )
