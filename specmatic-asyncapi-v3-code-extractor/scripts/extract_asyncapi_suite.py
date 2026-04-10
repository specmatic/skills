#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


TEXT_EXTENSIONS = {
    ".java",
    ".kt",
    ".kts",
    ".groovy",
    ".scala",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".yaml",
    ".yml",
    ".properties",
    ".conf",
    ".ini",
    ".env",
    ".xml",
    ".avsc",
    ".md",
}

CODE_EXTENSIONS = {
    ".java",
    ".kt",
    ".kts",
    ".groovy",
    ".scala",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
}

CONFIG_EVIDENCE_EXTENSIONS = {
    ".properties",
    ".yaml",
    ".yml",
    ".json",
    ".conf",
    ".ini",
    ".env",
    ".xml",
    ".avsc",
}

METHOD_DEF_RE = re.compile(
    r"""
    ^
    (?:
        (?:public|private|protected|internal|final|open|override|suspend|abstract|static)\s+
    )*
    (?:
        fun\s+(?P<kotlin>[A-Za-z_][A-Za-z0-9_]*)\s*\(
        |
        (?:(?:[\w<>\[\]?.,]+\s+)+)(?P<java>[A-Za-z_][A-Za-z0-9_]*)\s*\(
    )
    """,
    re.VERBOSE,
)

KAFKA_LISTENER_RE = re.compile(r"@KafkaListener\s*\((?P<body>.*?)\)")
LISTENER_TOPICS_RE = re.compile(r"topics?\s*=\s*\[(?P<topics>[^\]]+)\]|topics?\s*=\s*(?P<single>[^,)]+)")
VALUE_ANNOTATION_RE = re.compile(r'@Value\(\s*"(?P<expr>[^"]+)"\s*\)')
PROPERTY_PLACEHOLDER_RE = re.compile(r"\$\{(?P<key>[^}:]+)(?::(?P<default>[^}]+))?\}")
HTTP_MAPPING_PATTERNS = [
    ("GET", re.compile(r'@GetMapping\s*\(\s*(?:value\s*=\s*)?(?:\[)?\s*"(?P<path>[^"]+)"', re.I)),
    ("POST", re.compile(r'@PostMapping\s*\(\s*(?:value\s*=\s*)?(?:\[)?\s*"(?P<path>[^"]+)"', re.I)),
    ("PUT", re.compile(r'@PutMapping\s*\(\s*(?:value\s*=\s*)?(?:\[)?\s*"(?P<path>[^"]+)"', re.I)),
    ("DELETE", re.compile(r'@DeleteMapping\s*\(\s*(?:value\s*=\s*)?(?:\[)?\s*"(?P<path>[^"]+)"', re.I)),
]
CONST_PATTERNS = [
    re.compile(r"\b(?:private\s+)?const\s+val\s+(?P<name>[A-Z0-9_]+)\s*=\s*\"(?P<value>[^\"]+)\""),
    re.compile(r"\b(?:public|private|protected)?\s*static\s+final\s+String\s+(?P<name>[A-Z0-9_]+)\s*=\s*\"(?P<value>[^\"]+)\""),
]
VAR_DECL_PATTERNS = [
    re.compile(r"\b(?:lateinit\s+)?var\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*[\w<>\[\]?.]+(?:\s*=\s*\"(?P<value>[^\"]+)\")?"),
    re.compile(r"\bval\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*[\w<>\[\]?.]+(?:\s*=\s*\"(?P<value>[^\"]+)\")?"),
    re.compile(r"\b(?:private|public|protected)?\s*String\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*\"(?P<value>[^\"]+)\")?\s*;"),
]
SEND_CALL_RE = re.compile(r"\.(?:send|sendDefault|publish)\s*\(\s*(?P<channel>[^,\s)]+)")
PRODUCER_RECORD_RE = re.compile(r"ProducerRecord(?:<[^>]+>)?\s*\(\s*(?P<channel>[^,\s)]+)")
CORRELATION_PATTERNS = [
    re.compile(r"\bcorrelation[_-]?id\b", re.I),
    re.compile(r"\brequest[_-]?id\b", re.I),
    re.compile(r"\btrace[_-]?id\b", re.I),
]
RETRY_PATTERNS = [
    re.compile(r"\b(?:retry|redelivery|requeue|dead letter|dead-letter|dlq)\b", re.I),
    re.compile(r"\bmaxAttempts\b|\battempts\b|\bbackoff\b|\bexponential\b", re.I),
]
AVRO_PATTERNS = [
    re.compile(r"\bavro\b", re.I),
    re.compile(r"\bschema\.registry\.url\b", re.I),
    re.compile(r"\bKafkaAvroSerializer\b", re.I),
    re.compile(r"\bKafkaAvroDeserializer\b", re.I),
]
SCHEMA_HINT_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Event|Message|Payload|Request|Response|Command|Notification))\b")
CALL_RE = re.compile(r"\b(?:(?P<receiver>[A-Za-z_][A-Za-z0-9_]*)\.)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\(")
IGNORE_CALLS = {
    "if",
    "for",
    "while",
    "when",
    "catch",
    "println",
    "print",
    "map",
    "filter",
    "forEach",
    "apply",
    "let",
    "run",
    "require",
    "error",
    "listOf",
    "setOf",
    "mutableListOf",
    "mutableMapOf",
}

IGNORE_DIRS = {
    ".git",
    ".specmatic",
    "node_modules",
    "build",
    "dist",
    "target",
    ".idea",
    ".gradle",
    ".next",
    "coverage",
    ".specmatic-async-generated",
    "__pycache__",
}

GENERATED_DIR_BASENAME = "specmatic"


@dataclass
class Evidence:
    file: str
    line: int
    kind: str
    channel: str
    snippet: str


@dataclass
class PublishSite:
    line: int
    kind: str
    channel: str | None
    token: str
    snippet: str
    resolution: str
    payload_type: str | None


@dataclass
class MethodInfo:
    file: str
    name: str
    start_line: int
    end_line: int
    listener_channels: list[str]
    publishes: list[PublishSite]
    schema_hints: list[str]
    correlation: str
    calls: list[str]
    http_triggers: list[dict[str, Any]]
    body: str


@dataclass
class ModelField:
    name: str
    type_name: str
    required: bool


SCALAR_SCHEMA_TYPES = {
    "String": {"type": "string"},
    "Char": {"type": "string"},
    "UUID": {"type": "string", "format": "uuid"},
    "Int": {"type": "integer"},
    "Long": {"type": "integer"},
    "Short": {"type": "integer"},
    "Byte": {"type": "integer"},
    "Double": {"type": "number"},
    "Float": {"type": "number"},
    "BigDecimal": {"type": "number"},
    "Boolean": {"type": "boolean"},
    "LocalDate": {"type": "string", "format": "date"},
    "LocalDateTime": {"type": "string", "format": "date-time"},
    "Instant": {"type": "string", "format": "date-time"},
}

DATA_CLASS_RE = re.compile(r"\bdata\s+class\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*\(")
JAVA_RECORD_RE = re.compile(r"\brecord\s+(?P<name>[A-Z][A-Za-z0-9_]*)\s*\(")
KOTLIN_PROP_RE = re.compile(r"(?:@\S+\s+)*(?:public|private|internal|protected)?\s*(?:override\s+)?(?:val|var)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<type>[^=]+?)(?:\s*=\s*.+)?$")
JAVA_FIELD_RE = re.compile(r"(?:private|public|protected)?\s*(?:final\s+)?(?P<type>[A-Za-z0-9_<>, ?.]+)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*;")
WRITE_VALUE_AS_STRING_RE = re.compile(r"writeValueAsString\s*\(\s*(?P<expr>[^)]+)\)")
CTOR_OR_FACTORY_RE = re.compile(r"\b(?P<type>[A-Z][A-Za-z0-9_]*)\s*(?:\(|\.)")
LOCAL_ASSIGNMENT_RE = re.compile(r"\b(?:val|var)\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<expr>.+)")


def slug(value: str) -> str:
    lowered = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return lowered or "message"


def pascal_case(value: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", value)
    return "".join(part.capitalize() for part in parts if part) or "Message"


def safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def discover_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in IGNORE_DIRS or re.fullmatch(r"specmatic(?:-\d+)?", part) for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {"Dockerfile", "docker-compose.yml"}:
            files.append(path)
    return files


def parse_properties_from_text(text: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            properties[key.strip()] = value.strip()
        elif ":" in line and not line.startswith("-"):
            key, value = line.split(":", 1)
            if key.strip() and value.strip():
                properties[key.strip()] = value.strip().strip("'\"")
    return properties


def property_sources(root: Path, files: list[Path]) -> dict[str, str]:
    properties: dict[str, str] = {}
    for file in files:
        if file.suffix.lower() not in CONFIG_EVIDENCE_EXTENSIONS:
            continue
        if file.name.endswith((".properties", ".yaml", ".yml", ".env", ".conf", ".ini")):
            properties.update(parse_properties_from_text(safe_read(file)))
    return properties


def property_sources_with_origins(files: list[Path]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for file in files:
        if file.suffix.lower() not in CONFIG_EVIDENCE_EXTENSIONS:
            continue
        if not file.name.endswith((".properties", ".yaml", ".yml", ".env", ".conf", ".ini")):
            continue
        for key, value in parse_properties_from_text(safe_read(file)).items():
            entries.append({"file": str(file), "key": key, "value": value})
    return entries


def resolve_property_expression(expr: str, properties: dict[str, str]) -> tuple[str | None, str]:
    placeholder = PROPERTY_PLACEHOLDER_RE.search(expr)
    if not placeholder:
        return None, "annotation-expression-unresolved"
    key = placeholder.group("key")
    return properties.get(key), f"spring-property:{key}"


def resolve_placeholder_value(raw_value: str) -> str:
    placeholder = PROPERTY_PLACEHOLDER_RE.search(raw_value)
    if placeholder:
        return placeholder.group("default") or raw_value
    return raw_value


def inferred_kafka_bootstrap_servers(property_entries: list[dict[str, str]]) -> list[dict[str, str]]:
    matches = [
        {
            "host": resolve_placeholder_value(entry["value"]),
            "property": entry["key"],
            "source": entry["file"],
            "raw": entry["value"],
        }
        for entry in property_entries
        if entry["key"] == "spring.kafka.bootstrap-servers"
    ]
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in matches:
        key = (match["host"], match["source"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(match)
    return deduped


def choose_generated_dir(root: Path) -> Path:
    candidate = root / GENERATED_DIR_BASENAME
    if not candidate.exists():
        return candidate

    index = 1
    while True:
        candidate = root / f"{GENERATED_DIR_BASENAME}-{index}"
        if not candidate.exists():
            return candidate
        index += 1


def resolve_generated_dir_from_path(path: Path) -> Path:
    parent = path.resolve().parent
    if re.fullmatch(r"specmatic(?:-\d+)?", parent.name):
        return parent
    return parent


def infer_server_port(root: Path) -> int:
    for properties_path in [root / "src/main/resources/application.properties", root / "src/test/resources/application.properties"]:
        if properties_path.exists():
            for raw_line in properties_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if line.startswith("server.port="):
                    try:
                        return int(line.split("=", 1)[1].strip())
                    except ValueError:
                        continue
    return 8080


def detect_app_runtime(root: Path) -> dict[str, Any]:
    port = infer_server_port(root)
    if (root / "gradlew").exists():
        return {
            "serviceName": "app",
            "port": port,
            "image": "eclipse-temurin:17-jdk",
            "workingDir": "/app",
            "volumes": ["../:/app"],
            "command": 'sh -lc "chmod +x ./gradlew && ./gradlew bootRun --no-daemon"',
        }
    if (root / "mvnw").exists():
        return {
            "serviceName": "app",
            "port": port,
            "image": "maven:3.9-eclipse-temurin-17",
            "workingDir": "/app",
            "volumes": ["../:/app"],
            "command": 'sh -lc "chmod +x ./mvnw && ./mvnw spring-boot:run"',
        }
    if (root / "Dockerfile").exists():
        return {
            "serviceName": "app",
            "port": port,
            "build": {"context": ".."},
            "command": None,
        }
    return {
        "serviceName": "app",
        "port": port,
        "image": "eclipse-temurin:17-jdk",
        "workingDir": "/app",
        "volumes": ["../:/app"],
        "command": 'sh -lc "echo Unable to infer an application start command. Update docker-compose.yml in this folder before running. && sleep infinity"',
    }


def parse_http_triggers(annotation_lines: list[str]) -> list[dict[str, str]]:
    triggers: list[dict[str, str]] = []
    for annotation in annotation_lines:
        for method, pattern in HTTP_MAPPING_PATTERNS:
            match = pattern.search(annotation)
            if match:
                triggers.append({"type": "http", "method": method, "path": match.group("path")})
    return triggers


def split_top_level_commas(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    paren_depth = 0
    angle_depth = 0
    bracket_depth = 0
    brace_depth = 0
    for char in value:
        if char == "," and paren_depth == 0 and angle_depth == 0 and bracket_depth == 0 and brace_depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth = max(paren_depth - 1, 0)
        elif char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth = max(angle_depth - 1, 0)
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth = max(bracket_depth - 1, 0)
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth = max(brace_depth - 1, 0)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def extract_balanced_segment(text: str, start_index: int, open_char: str, close_char: str) -> tuple[str, int]:
    depth = 0
    current: list[str] = []
    for index in range(start_index, len(text)):
        char = text[index]
        current.append(char)
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return "".join(current), index + 1
    return "".join(current), len(text)


def const_map_for(text: str, properties: dict[str, str]) -> dict[str, str]:
    symbols: dict[str, str] = {}
    for pattern in CONST_PATTERNS:
        for match in pattern.finditer(text):
            symbols[match.group("name")] = match.group("value")

    lines = text.splitlines()
    pending_property_expr: str | None = None
    for line in lines:
        stripped = line.strip()
        value_match = VALUE_ANNOTATION_RE.search(stripped)
        if value_match:
            pending_property_expr = value_match.group("expr")
            continue

        for pattern in VAR_DECL_PATTERNS:
            match = pattern.search(stripped)
            if not match:
                continue
            name = match.group("name")
            inline_value = match.groupdict().get("value")
            if inline_value:
                symbols[name] = inline_value
            elif pending_property_expr:
                resolved, _ = resolve_property_expression(pending_property_expr, properties)
                if resolved:
                    symbols[name] = resolved
            pending_property_expr = None
            break
        else:
            if stripped and not stripped.startswith("@"):
                pending_property_expr = None

    return symbols


def resolve_channel_token(token: str, symbols: dict[str, str]) -> tuple[str | None, str]:
    cleaned = token.strip().strip("{}[]()").rstrip(",")
    if cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned.strip('"'), "literal"
    if cleaned in symbols:
        return symbols[cleaned], f"symbol:{cleaned}"
    if re.match(r"[a-z0-9._-]+$", cleaned) and re.search(r"[-._]", cleaned):
        return cleaned, "raw-token"
    return None, f"unresolved:{cleaned}"


def parse_listener_channels(annotation_lines: list[str], symbols: dict[str, str]) -> list[str]:
    channels: list[str] = []
    for annotation in annotation_lines:
        if "@KafkaListener" not in annotation:
            continue
        match = KAFKA_LISTENER_RE.search(annotation)
        if not match:
            continue
        body = match.group("body")
        topics_match = LISTENER_TOPICS_RE.search(body)
        if not topics_match:
            continue
        tokens: list[str]
        if topics_match.group("topics"):
            tokens = [part.strip() for part in topics_match.group("topics").split(",")]
        else:
            tokens = [topics_match.group("single").strip()]
        for token in tokens:
            channel, _ = resolve_channel_token(token, symbols)
            if channel:
                channels.append(channel)
    return channels


def extract_methods(path: Path, text: str, symbols: dict[str, str]) -> list[MethodInfo]:
    lines = text.splitlines()
    methods: list[MethodInfo] = []
    pending_annotations: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("@"):
            pending_annotations.append(stripped)
            index += 1
            continue

        if re.match(r"(class|interface|enum)\b", stripped):
            pending_annotations = []
            index += 1
            continue

        method_match = METHOD_DEF_RE.match(stripped)
        if not method_match:
            if stripped:
                pending_annotations = []
            index += 1
            continue

        method_name = method_match.group("kotlin") or method_match.group("java")
        start_index = index
        signature_lines = [lines[index]]
        while "{" not in signature_lines[-1] and index + 1 < len(lines):
            index += 1
            signature_lines.append(lines[index])
        signature_text = "\n".join(signature_lines)
        if "{" not in signature_text:
            pending_annotations = []
            index += 1
            continue

        brace_depth = signature_text.count("{") - signature_text.count("}")
        index += 1
        while index < len(lines):
            brace_depth += lines[index].count("{") - lines[index].count("}")
            if brace_depth <= 0:
                break
            index += 1
        end_index = min(index, len(lines) - 1)
        body_lines = lines[start_index : end_index + 1]
        body = "\n".join(body_lines)
        listener_channels = parse_listener_channels(pending_annotations, symbols)
        http_triggers = parse_http_triggers(pending_annotations)
        methods.append(
            MethodInfo(
                file=str(path),
                name=method_name,
                start_line=start_index + 1,
                end_line=end_index + 1,
                listener_channels=listener_channels,
                publishes=[],
                schema_hints=[],
                correlation="explicit" if any(pattern.search(body) for pattern in CORRELATION_PATTERNS) else "unknown",
                calls=[],
                http_triggers=http_triggers,
                body=body,
            )
        )
        pending_annotations = []
        index += 1
    return methods


def collect_schema_hints(text: str, base_name: str) -> list[str]:
    hints: list[str] = []
    for match in SCHEMA_HINT_RE.finditer(text):
        candidate = match.group(1)
        if candidate not in hints:
            hints.append(candidate)
        if len(hints) >= 3:
            break
    if not hints:
        hints.append(f"{pascal_case(base_name)}Payload")
    return hints


def payload_type_from_expression(expr: str, locals_map: dict[str, str]) -> str | None:
    cleaned = expr.strip().rstrip(",")
    if cleaned in locals_map:
        return locals_map[cleaned]

    write_match = WRITE_VALUE_AS_STRING_RE.search(cleaned)
    if write_match:
        return payload_type_from_expression(write_match.group("expr"), locals_map)

    ctor_match = CTOR_OR_FACTORY_RE.search(cleaned)
    if ctor_match:
        return ctor_match.group("type")

    if "." in cleaned:
        base = cleaned.split(".", 1)[0].strip()
        if base in locals_map:
            return locals_map[base]

    return locals_map.get(cleaned)


def infer_local_types(method_body: str) -> dict[str, str]:
    locals_map: dict[str, str] = {}
    for raw_line in method_body.splitlines():
        stripped = raw_line.strip()
        match = LOCAL_ASSIGNMENT_RE.search(stripped)
        if not match:
            continue
        inferred = payload_type_from_expression(match.group("expr"), locals_map)
        if inferred:
            locals_map[match.group("name")] = inferred
    return locals_map


def extract_publish_sites(method: MethodInfo, symbols: dict[str, str]) -> list[PublishSite]:
    lines = method.body.splitlines()
    publishes: list[PublishSite] = []
    local_types = infer_local_types(method.body)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if ".send(" in stripped or ".sendDefault(" in stripped or ".publish(" in stripped:
            window = "\n".join(lines[index : index + 4])
            send_match = SEND_CALL_RE.search(window)
            if send_match:
                token = send_match.group("channel")
                channel, resolution = resolve_channel_token(token, symbols)
                payload_type = None
                arguments = window[window.find("(") + 1 :]
                parts = split_top_level_commas(arguments)
                if len(parts) >= 2:
                    payload_type = payload_type_from_expression(parts[1], local_types)
                publishes.append(
                    PublishSite(
                        line=method.start_line + index,
                        kind="kafka_send",
                        channel=channel,
                        token=token,
                        snippet=stripped[:240],
                        resolution=resolution,
                        payload_type=payload_type,
                    )
                )
            continue
        if "ProducerRecord" in stripped:
            window = "\n".join(lines[index : index + 4])
            record_match = PRODUCER_RECORD_RE.search(window)
            if record_match:
                token = record_match.group("channel")
                channel, resolution = resolve_channel_token(token, symbols)
                publishes.append(
                    PublishSite(
                        line=method.start_line + index,
                        kind="producer_record",
                        channel=channel,
                        token=token,
                        snippet=stripped[:240],
                        resolution=resolution,
                        payload_type=None,
                    )
                )
    return publishes


def wire_method_calls(methods: list[MethodInfo]) -> None:
    for method in methods:
        called: list[str] = []
        for match in CALL_RE.finditer(method.body):
            receiver = match.group("receiver")
            name = match.group("name")
            is_same_method_without_receiver = name == method.name and receiver is None
            if not is_same_method_without_receiver and name not in called and name not in IGNORE_CALLS:
                called.append(name)
        method.calls = called


def analyze_code_file(path: Path, text: str, properties: dict[str, str]) -> dict[str, Any]:
    symbols = const_map_for(text, properties)
    methods = extract_methods(path, text, symbols)
    for method in methods:
        method.publishes = extract_publish_sites(method, symbols)
        base_name = method.listener_channels[0] if method.listener_channels else method.name
        method.schema_hints = collect_schema_hints(method.body, base_name)
    wire_method_calls(methods)

    unresolved_publishes = [
        {
            "file": method.file,
            "method": method.name,
            "line": publish.line,
            "token": publish.token,
            "resolution": publish.resolution,
            "snippet": publish.snippet,
        }
        for method in methods
        for publish in method.publishes
        if publish.channel is None
    ]

    return {
        "symbols": symbols,
        "methods": methods,
        "unresolvedPublishes": unresolved_publishes,
    }


def strip_annotations(value: str) -> str:
    stripped = re.sub(r"@\S+\s*", "", value).strip()
    return stripped


def parse_field_signature(fragment: str) -> ModelField | None:
    compact = strip_annotations(fragment).strip()
    kotlin_match = KOTLIN_PROP_RE.search(compact)
    if kotlin_match:
        type_name = kotlin_match.group("type").strip().rstrip(",")
        return ModelField(
            name=kotlin_match.group("name"),
            type_name=type_name.replace("?", "").strip(),
            required="?" not in type_name,
        )
    java_match = JAVA_FIELD_RE.search(compact)
    if java_match:
        return ModelField(
            name=java_match.group("name"),
            type_name=java_match.group("type").strip(),
            required=True,
        )
    return None


def parse_kotlin_data_classes(text: str) -> dict[str, list[ModelField]]:
    models: dict[str, list[ModelField]] = {}
    cursor = 0
    while True:
        match = DATA_CLASS_RE.search(text, cursor)
        if not match:
            break
        name = match.group("name")
        segment, end_index = extract_balanced_segment(text, match.end() - 1, "(", ")")
        params = segment[1:-1]
        fields = [field for field in (parse_field_signature(part) for part in split_top_level_commas(params)) if field]
        if fields:
            models[name] = fields
        cursor = end_index
    return models


def parse_java_records(text: str) -> dict[str, list[ModelField]]:
    models: dict[str, list[ModelField]] = {}
    cursor = 0
    while True:
        match = JAVA_RECORD_RE.search(text, cursor)
        if not match:
            break
        name = match.group("name")
        segment, end_index = extract_balanced_segment(text, match.end() - 1, "(", ")")
        params = segment[1:-1]
        fields: list[ModelField] = []
        for part in split_top_level_commas(params):
            tokens = part.strip().split()
            if len(tokens) >= 2:
                fields.append(ModelField(name=tokens[-1], type_name=" ".join(tokens[:-1]), required=True))
        if fields:
            models[name] = fields
        cursor = end_index
    return models


def collect_model_definitions(files: list[Path], file_text_cache: dict[str, str]) -> dict[str, list[ModelField]]:
    models: dict[str, list[ModelField]] = {}
    for file in files:
        if file.suffix.lower() not in CODE_EXTENSIONS:
            continue
        text = file_text_cache[str(file)]
        for name, fields in parse_kotlin_data_classes(text).items():
            models.setdefault(name, fields)
        for name, fields in parse_java_records(text).items():
            models.setdefault(name, fields)
    return models


def reachable_methods(start: MethodInfo, method_map: dict[str, MethodInfo]) -> list[MethodInfo]:
    ordered: list[MethodInfo] = []
    stack = [start]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current.name in seen:
            continue
        seen.add(current.name)
        ordered.append(current)
        for called in reversed(current.calls):
            if called in method_map:
                stack.append(method_map[called])
    return ordered


def confidence_for(request_hits: list[Evidence], reply_hits: list[Evidence]) -> str:
    if request_hits and reply_hits:
        return "high"
    if request_hits or reply_hits:
        return "medium"
    return "low"


def correlation_strategy(text: str) -> str:
    return "explicit" if any(pattern.search(text) for pattern in CORRELATION_PATTERNS) else "unknown"


def build_receive_operation(
    request_channel: str,
    request_evidence: list[Evidence],
    file_text: str,
    unresolved_concerns: list[str],
    schema_hints: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "operationId": f"{slug(request_channel)}-receive",
        "type": "receive-only",
        "applicationPerspective": "consumer",
        "requestChannel": request_channel,
        "replyChannel": None,
        "retryChannel": None,
        "dlqChannel": None,
        "requestMessage": f"{pascal_case(request_channel)}Message",
        "replyMessage": None,
        "requestSchemaHints": schema_hints or collect_schema_hints(file_text, request_channel),
        "replySchemaHints": [],
        "correlationStrategy": correlation_strategy(file_text),
        "confidence": confidence_for(request_evidence, []),
        "evidence": [asdict(ev) for ev in request_evidence[:3]],
        "unresolvedConcerns": unresolved_concerns or ["No paired reply channel detected"],
    }


def build_send_operation(
    channel: str,
    publish_evidence: list[Evidence],
    file_text: str,
    unresolved_concerns: list[str],
    schema_hints: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "operationId": f"{slug(channel)}-send",
        "type": "send-only",
        "applicationPerspective": "producer",
        "requestChannel": channel,
        "replyChannel": None,
        "retryChannel": None,
        "dlqChannel": None,
        "requestMessage": f"{pascal_case(channel)}Message",
        "replyMessage": None,
        "requestSchemaHints": schema_hints or collect_schema_hints(file_text, channel),
        "replySchemaHints": [],
        "correlationStrategy": correlation_strategy(file_text),
        "confidence": confidence_for([], publish_evidence),
        "evidence": [asdict(ev) for ev in publish_evidence[:3]],
        "unresolvedConcerns": unresolved_concerns or ["Producer flow inferred without a visible upstream request"],
    }


def infer_operations(root: Path) -> dict[str, Any]:
    files = discover_files(root)
    properties = property_sources(root, files)
    property_entries = property_sources_with_origins(files)
    kafka_bootstrap_servers = inferred_kafka_bootstrap_servers(property_entries)
    file_text_cache = {str(file): safe_read(file) for file in files}
    model_definitions = collect_model_definitions(files, file_text_cache)
    retry_evidence = [
        str(file)
        for file in files
        if any(pattern.search(file_text_cache[str(file)]) for pattern in RETRY_PATTERNS)
    ]
    avro_evidence = [
        str(file)
        for file in files
        if file.suffix.lower() in CODE_EXTENSIONS.union(CONFIG_EVIDENCE_EXTENSIONS)
        and any(pattern.search(file_text_cache[str(file)]) for pattern in AVRO_PATTERNS)
    ]
    schema_files = [str(file) for file in files if file.suffix.lower() == ".avsc"]

    code_analyses: dict[str, dict[str, Any]] = {}
    for file in files:
        if file.suffix.lower() not in CODE_EXTENSIONS:
            continue
        code_analyses[str(file)] = analyze_code_file(file, file_text_cache[str(file)], properties)

    listener_hits: list[Evidence] = []
    publisher_hits: list[Evidence] = []
    unresolved_publishes: list[dict[str, Any]] = []
    listener_diagnostics: list[dict[str, Any]] = []
    controller_trigger_map: dict[str, list[dict[str, Any]]] = {}
    listener_covered_channels: dict[str, list[str]] = {}
    operations: list[dict[str, Any]] = []

    for file, analysis in code_analyses.items():
        method_map = {method.name: method for method in analysis["methods"]}
        unresolved_publishes.extend(analysis["unresolvedPublishes"])
        for method in analysis["methods"]:
            for channel in method.listener_channels:
                listener_hits.append(
                    Evidence(
                        file=file,
                        line=method.start_line,
                        kind="kafka_listener",
                        channel=channel,
                        snippet=method.body.splitlines()[0].strip()[:240],
                    )
                )

            for publish in method.publishes:
                if publish.channel:
                    publisher_hits.append(
                        Evidence(
                            file=file,
                            line=publish.line,
                            kind=publish.kind,
                            channel=publish.channel,
                            snippet=publish.snippet,
                        )
                    )

        for method in analysis["methods"]:
            reachable = reachable_methods(method, method_map)
            reachable_publishes = [
                (reachable_method, publish)
                for reachable_method in reachable
                for publish in reachable_method.publishes
                if publish.channel
            ]
            if method.listener_channels:
                publish_channels = [publish.channel for _, publish in reachable_publishes if publish.channel]
                listener_diagnostics.append(
                    {
                        "file": file,
                        "listenerMethod": method.name,
                        "listenerChannels": method.listener_channels,
                        "reachableMethods": [reachable_method.name for reachable_method in reachable],
                        "reachablePublishes": [
                            {
                                "method": reachable_method.name,
                                "channel": publish.channel,
                                "line": publish.line,
                                "resolution": publish.resolution,
                            }
                            for reachable_method, publish in reachable_publishes
                        ],
                        "pairingDecision": "receive-only",
                        "pairingReason": "Conservative default: reachable publish without explicit reply/correlation semantics stays separate.",
                    }
                )
                for channel in method.listener_channels:
                    request_evidence = [
                        Evidence(
                            file=file,
                            line=method.start_line,
                            kind="kafka_listener",
                            channel=channel,
                            snippet=method.body.splitlines()[0].strip()[:240],
                        )
                    ]
                    concerns = []
                    if publish_channels:
                        concerns.append(
                            "Reachable downstream publishes were found but kept separate to avoid false-positive request-reply pairing: "
                            + ", ".join(dict.fromkeys(publish_channels))
                        )
                    operations.append(
                        build_receive_operation(
                            request_channel=channel,
                            request_evidence=request_evidence,
                            file_text=method.body,
                            unresolved_concerns=concerns,
                            schema_hints=method.schema_hints,
                        )
                    )
                for publish_channel in dict.fromkeys(publish_channels):
                    if publish_channel:
                        listener_covered_channels.setdefault(publish_channel, []).append(f"{slug(method.listener_channels[0])}-receive")

    all_methods = [method for analysis in code_analyses.values() for method in analysis["methods"]]
    methods_by_name: dict[str, list[MethodInfo]] = {}
    for method in all_methods:
        methods_by_name.setdefault(method.name, []).append(method)

    for controller_method in [method for method in all_methods if method.http_triggers]:
        stack = [controller_method]
        visited: set[tuple[str, str, int]] = set()
        while stack:
            current = stack.pop()
            visit_key = (current.file, current.name, current.start_line)
            if visit_key in visited:
                continue
            visited.add(visit_key)
            for publish in current.publishes:
                if publish.channel:
                    controller_trigger_map.setdefault(publish.channel, []).extend(
                        [
                            {
                                "type": trigger["type"],
                                "method": trigger["method"],
                                "path": trigger["path"],
                                "sourceMethod": controller_method.name,
                                "sourceFile": controller_method.file,
                            }
                            for trigger in controller_method.http_triggers
                        ]
                    )
            for call_name in current.calls:
                for candidate in methods_by_name.get(call_name, []):
                    candidate_key = (candidate.file, candidate.name, candidate.start_line)
                    if candidate_key not in visited:
                        stack.append(candidate)

    # Re-scan publishes so listener-reachable downstream sends still become standalone send-only operations.
    channel_to_evidence: dict[str, list[Evidence]] = {}
    channel_to_schema_hints: dict[str, list[str]] = {}
    channel_to_source_text: dict[str, str] = {}
    for analysis in code_analyses.values():
        for method in analysis["methods"]:
            for publish in method.publishes:
                if not publish.channel:
                    continue
                channel_to_evidence.setdefault(
                    publish.channel,
                    []
                ).append(
                    Evidence(
                        file=method.file,
                        line=publish.line,
                        kind=publish.kind,
                        channel=publish.channel,
                        snippet=publish.snippet,
                    )
                )
                hints = []
                if publish.payload_type:
                    hints.append(publish.payload_type)
                for hint in method.schema_hints:
                    if hint not in hints:
                        hints.append(hint)
                if hints:
                    channel_to_schema_hints.setdefault(publish.channel, [])
                    for hint in hints:
                        if hint not in channel_to_schema_hints[publish.channel]:
                            channel_to_schema_hints[publish.channel].append(hint)
                channel_to_source_text.setdefault(publish.channel, method.body)

    listener_channels = {op["requestChannel"] for op in operations if op["type"] == "receive-only"}
    for channel, publish_evidence in sorted(channel_to_evidence.items()):
        if channel in listener_channels:
            continue
        file_text = file_text_cache[publish_evidence[0].file]
        concerns = []
        trigger_hints = controller_trigger_map.get(channel, [])
        covered_by = listener_covered_channels.get(channel, [])
        if any(
            diagnostic for diagnostic in listener_diagnostics
            if any(reachable_publish["channel"] == channel for reachable_publish in diagnostic["reachablePublishes"])
        ):
            concerns.append("This publish is reachable from a listener flow, but is modeled as send-only to avoid false-positive request-reply inference.")
        if trigger_hints:
            concerns.append("This publish appears to require an external HTTP trigger before Specmatic can observe the message.")
        operations.append(
            build_send_operation(
                channel=channel,
                publish_evidence=publish_evidence,
                file_text=channel_to_source_text.get(channel, file_text),
                unresolved_concerns=concerns,
                schema_hints=channel_to_schema_hints.get(channel),
            )
        )
        operations[-1]["triggerHints"] = trigger_hints
        operations[-1]["coveredByOperationIds"] = covered_by
        operations[-1]["driveability"] = (
            "requires-http-trigger"
            if trigger_hints
            else "covered-by-listener-flow"
            if covered_by
            else "direct-send"
        )

    operations = sorted(operations, key=lambda op: (op["type"], op["requestChannel"]))
    service_name = slug(root.name)
    return {
        "serviceName": service_name,
        "root": str(root),
        "stats": {
            "filesScanned": len(files),
            "listenerHits": len(listener_hits),
            "publisherHits": len(publisher_hits),
        },
        "signals": {
            "avroDetected": bool(avro_evidence or schema_files),
            "avroEvidence": avro_evidence[:10],
            "schemaFiles": schema_files[:20],
            "retryOrDlqEvidence": retry_evidence[:10],
        },
        "diagnostics": {
            "listenerPairing": listener_diagnostics,
            "unresolvedPublishes": unresolved_publishes,
            "propertiesResolved": properties,
            "controllerTriggers": controller_trigger_map,
            "listenerCoveredChannels": listener_covered_channels,
            "runtimeHints": {
                "kafkaBootstrapServers": kafka_bootstrap_servers,
                "suggestedAsyncServers": [
                    {"host": entry["host"], "protocol": "kafka", "source": entry["source"]}
                    for entry in kafka_bootstrap_servers
                ],
            },
            "modelDefinitions": {
                name: [{"name": field.name, "type": field.type_name, "required": field.required} for field in fields]
                for name, fields in model_definitions.items()
            },
        },
        "operations": operations,
    }


def render_review(report: dict[str, Any]) -> str:
    lines = [
        f"# Async Operation Review for {report['serviceName']}",
        "",
        "| Operation | Type | Request | Reply | Retry | DLQ | Confidence | Evidence | Concerns |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for op in report["operations"]:
        evidence = "<br>".join(
            f"{Path(ev['file']).name}:{ev['line']} `{ev['kind']}`"
            for ev in op.get("evidence", [])[:3]
        ) or "none"
        concerns = "<br>".join(op.get("unresolvedConcerns", [])) or "none"
        lines.append(
            "| {operationId} | {type} | {requestChannel} | {replyChannel} | {retryChannel} | {dlqChannel} | {confidence} | {evidence} | {concerns} |".format(
                operationId=op["operationId"],
                type=op["type"],
                requestChannel=op.get("requestChannel") or "-",
                replyChannel=op.get("replyChannel") or "-",
                retryChannel=op.get("retryChannel") or "-",
                dlqChannel=op.get("dlqChannel") or "-",
                confidence=op.get("confidence") or "-",
                evidence=evidence,
                concerns=concerns,
            )
        )

    unresolved = report.get("diagnostics", {}).get("unresolvedPublishes", [])
    if unresolved:
        lines.extend(["", "## Unresolved Publish Tokens", ""])
        for item in unresolved[:10]:
            lines.append(
                f"- {Path(item['file']).name}:{item['line']} `{item['token']}` -> {item['resolution']}"
            )

    lines.extend(
        [
            "",
            "Review gate:",
            "- Confirm which inferred operations are real.",
            "- Correct request versus reply channel assignments where needed.",
            "- Remove low-confidence operations that are only naming guesses.",
            "- Save the confirmed subset as `approved-operations.json` before generation.",
        ]
    )
    return "\n".join(lines) + "\n"


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{escaped}\""


def yaml_from_structure(value: Any, indent: int = 0) -> str:
    space = " " * indent
    if isinstance(value, dict):
        if not value:
            return f"{space}{{}}"
        lines: list[str] = []
        for key, nested in value.items():
            if nested is None:
                continue
            if isinstance(nested, dict) and not nested:
                lines.append(f"{space}{key}: {{}}")
                continue
            if isinstance(nested, list) and not nested:
                lines.append(f"{space}{key}: []")
                continue
            if isinstance(nested, (dict, list)):
                lines.append(f"{space}{key}:")
                lines.append(yaml_from_structure(nested, indent + 2))
            else:
                lines.append(f"{space}{key}: {scalar_to_yaml(nested)}")
        return "\n".join(lines)
    if isinstance(value, list):
        if not value:
            return f"{space}[]"
        lines: list[str] = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{space}-")
                lines.append(yaml_from_structure(item, indent + 2))
            else:
                lines.append(f"{space}- {scalar_to_yaml(item)}")
        return "\n".join(lines)
    return f"{space}{scalar_to_yaml(value)}"


def scalar_to_yaml(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return yaml_quote(str(value))


def normalize_type_name(type_name: str) -> str:
    return type_name.replace("?", "").strip()


def schema_for_type(type_name: str, known_models: dict[str, list[ModelField]], visiting: set[str]) -> dict[str, Any]:
    normalized = normalize_type_name(type_name)
    if normalized in SCALAR_SCHEMA_TYPES:
        return dict(SCALAR_SCHEMA_TYPES[normalized])

    list_match = re.match(r"(?:List|MutableList|Set|Collection)<(?P<inner>.+)>", normalized)
    if list_match:
        inner = normalize_type_name(list_match.group("inner"))
        return {
            "type": "array",
            "items": schema_for_type(inner, known_models, visiting),
        }

    map_match = re.match(r"(?:Map|MutableMap)<.+>", normalized)
    if map_match or normalized == "Any":
        return {"type": "object", "additionalProperties": True}

    simple_name = normalized.split(".")[-1]
    if simple_name in known_models:
        return {"$ref": f"#/components/schemas/{simple_name}"}

    return {"type": "object", "additionalProperties": True}


def build_model_schema(model_name: str, known_models: dict[str, list[ModelField]], visiting: set[str] | None = None) -> dict[str, Any]:
    active = set(visiting or set())
    if model_name in active:
        return {"type": "object", "additionalProperties": True}
    active.add(model_name)

    fields = known_models.get(model_name, [])
    properties: dict[str, Any] = {}
    required: list[str] = []
    for field in fields:
        properties[field.name] = schema_for_type(field.type_name, known_models, active)
        if field.required:
            required.append(field.name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    if not properties:
        schema["additionalProperties"] = True
    return schema


def ensure_schema_components(
    schema_name: str,
    components_schemas: dict[str, Any],
    known_models: dict[str, list[ModelField]],
    visiting: set[str] | None = None,
) -> None:
    simple_name = normalize_type_name(schema_name).split(".")[-1]
    if simple_name in components_schemas:
        return
    if simple_name in known_models:
        components_schemas[simple_name] = build_model_schema(simple_name, known_models, visiting)
        for field in known_models[simple_name]:
            inner_type = normalize_type_name(field.type_name)
            list_match = re.match(r"(?:List|MutableList|Set|Collection)<(?P<inner>.+)>", inner_type)
            if list_match:
                inner_type = normalize_type_name(list_match.group("inner"))
            simple_inner = inner_type.split(".")[-1]
            if simple_inner in known_models:
                ensure_schema_components(simple_inner, components_schemas, known_models, set((visiting or set())) | {simple_name})


def example_from_schema(schema: dict[str, Any], known_schemas: dict[str, Any]) -> Any:
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        if ref_name in known_schemas:
            return example_from_schema(known_schemas[ref_name], known_schemas)
        return {}

    schema_type = schema.get("type")
    if schema_type == "object":
        properties = schema.get("properties", {})
        return {name: example_from_schema(prop_schema, known_schemas) for name, prop_schema in properties.items()}
    if schema_type == "array":
        items = schema.get("items", {"type": "object", "additionalProperties": True})
        return [example_from_schema(items, known_schemas)]
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    if schema_type == "string":
        fmt = schema.get("format")
        if fmt == "date":
            return "2025-01-01"
        if fmt == "date-time":
            return "2025-01-01T00:00:00Z"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        return "sample"
    return {}


def example_payload(op: dict[str, Any], direction: str, schema_components: dict[str, Any]) -> dict[str, Any]:
    hints = op["replySchemaHints"] if direction == "reply" else op["requestSchemaHints"]
    fallback = op.get("replyMessage") or op.get("requestMessage") or "Payload"
    schema_name = normalize_type_name(hints[0] if hints else fallback).split(".")[-1]
    if schema_name in schema_components:
        payload = example_from_schema(schema_components[schema_name], schema_components)
    else:
        payload = {"sample": f"{schema_name}Example"}
    if isinstance(payload, dict) and op.get("correlationStrategy") in {"explicit", "inferred"}:
        payload.setdefault("requestId", "sample-request-id")
    return payload


def build_asyncapi(report: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, Any]:
    channels: dict[str, Any] = {}
    op_nodes: dict[str, Any] = {}
    messages: dict[str, Any] = {}
    schemas: dict[str, Any] = {}
    correlation_ids: dict[str, Any] = {}
    known_models = {
        name: [ModelField(field["name"], field["type"], field["required"]) for field in fields]
        for name, fields in report.get("diagnostics", {}).get("modelDefinitions", {}).items()
    }

    for op in operations:
        request_channel = op["requestChannel"]
        request_message_name = op["requestMessage"]
        channels.setdefault(
            request_channel,
            {"address": request_channel, "messages": {request_message_name: {"$ref": f"#/components/messages/{request_message_name}"}}},
        )
        request_schema = op["requestSchemaHints"][0] if op["requestSchemaHints"] else f"{pascal_case(request_channel)}Payload"
        ensure_schema_components(request_schema, schemas, known_models)
        schemas.setdefault(normalize_type_name(request_schema).split(".")[-1], {"type": "object", "additionalProperties": True})
        message_obj = {
            "name": request_message_name,
            "title": f"{request_message_name} extracted from code",
            "contentType": "application/json",
            "payload": {"$ref": f"#/components/schemas/{normalize_type_name(request_schema).split('.')[-1]}"},
        }
        if op["correlationStrategy"] in {"explicit", "inferred"}:
            correlation_ids.setdefault("requestIdHeader", {"location": "$message.header#/requestId"})
            message_obj["headers"] = {
                "type": "object",
                "properties": {"requestId": {"type": "string"}},
            }
            message_obj["correlationId"] = {"$ref": "#/components/correlationIds/requestIdHeader"}
        messages.setdefault(request_message_name, message_obj)

        operation_node: dict[str, Any] = {
            "action": "send" if op["type"] == "send-only" else "receive",
            "channel": {"$ref": f"#/channels/{request_channel}"},
            "messages": [{"$ref": f"#/channels/{request_channel}/messages/{request_message_name}"}],
        }

        if op.get("replyChannel"):
            reply_channel = op["replyChannel"]
            reply_message_name = op["replyMessage"]
            channels.setdefault(
                reply_channel,
                {"address": reply_channel, "messages": {reply_message_name: {"$ref": f"#/components/messages/{reply_message_name}"}}},
            )
            reply_schema = op["replySchemaHints"][0] if op["replySchemaHints"] else f"{pascal_case(reply_channel)}Payload"
            ensure_schema_components(reply_schema, schemas, known_models)
            schemas.setdefault(normalize_type_name(reply_schema).split(".")[-1], {"type": "object", "additionalProperties": True})
            messages.setdefault(
                reply_message_name,
                {
                    "name": reply_message_name,
                    "title": f"{reply_message_name} extracted from code",
                    "contentType": "application/json",
                    "payload": {"$ref": f"#/components/schemas/{normalize_type_name(reply_schema).split('.')[-1]}"},
                },
            )
            operation_node["reply"] = {
                "channel": {"$ref": f"#/channels/{reply_channel}"},
                "messages": [{"$ref": f"#/channels/{reply_channel}/messages/{reply_message_name}"}],
            }

        if op.get("retryChannel") and op.get("replyChannel"):
            retry_channel = op["retryChannel"]
            reply_message_name = op["replyMessage"]
            channels.setdefault(
                retry_channel,
                {"address": retry_channel, "messages": {reply_message_name: {"$ref": f"#/components/messages/{reply_message_name}"}}},
            )
            operation_node["x-specmatic-retry"] = {
                "channel": {"$ref": f"#/channels/{retry_channel}"},
                "messages": [{"$ref": f"#/channels/{retry_channel}/messages/{reply_message_name}"}],
                "maxAttempts": 3,
                "strategy": {
                    "type": "exponential",
                    "initialDelaySeconds": 5,
                    "multiplier": 2,
                },
            }

        if op.get("dlqChannel") and op.get("replyChannel"):
            dlq_channel = op["dlqChannel"]
            reply_message_name = op["replyMessage"]
            channels.setdefault(
                dlq_channel,
                {"address": dlq_channel, "messages": {reply_message_name: {"$ref": f"#/components/messages/{reply_message_name}"}}},
            )
            operation_node["x-specmatic-dlq"] = {
                "channel": {"$ref": f"#/channels/{dlq_channel}"},
                "messages": [{"$ref": f"#/channels/{dlq_channel}/messages/{reply_message_name}"}],
                "waitTimeInSeconds": 10,
            }

        op_nodes[op["operationId"]] = operation_node

    doc: dict[str, Any] = {
        "asyncapi": "3.0.0",
        "info": {
            "title": f"{report['serviceName']} extracted async contract",
            "version": "0.1.0",
            "description": "Generated from code evidence. Review operation semantics before adopting as a source contract.",
        },
        "channels": channels,
        "operations": op_nodes,
        "components": {
            "messages": messages,
            "schemas": schemas,
        },
    }
    if correlation_ids:
        doc["components"]["correlationIds"] = correlation_ids
    return doc


def build_specmatic_config(root: Path, report: dict[str, Any], generated_dir: Path) -> dict[str, Any]:
    rel_spec = str((generated_dir / "specs" / "asyncapi-extracted.yaml").relative_to(root))
    rel_overlay = str((generated_dir / "specs" / "asyncapi-overlay.yaml").relative_to(root))
    rel_examples = str((generated_dir / "examples" / report["serviceName"]).relative_to(root))

    inferred_server = (
        report.get("diagnostics", {})
        .get("runtimeHints", {})
        .get("suggestedAsyncServers", [{}])[0]
    )
    protocol = inferred_server.get("protocol", "kafka")
    default_host = inferred_server.get("host", "localhost:9092")
    asyncapi_options: dict[str, Any] = {
        "type": "test",
        "provides": report["serviceName"],
        "servers": [
            {
                "host": default_host,
                "protocol": protocol,
            }
        ],
        "specs": [
            {
                "path": rel_spec,
                "overlay": rel_overlay,
            }
        ],
    }
    if report["signals"]["avroDetected"]:
        asyncapi_options["schemaRegistry"] = {
            "url": "${SCHEMA_REGISTRY_URL}",
            "kind": "DEFAULT",
        }

    return {
        "version": 3,
        "systemUnderTest": {
            "service": {
                "definitions": [{"type": "asyncapi", "path": rel_spec}],
                "data": {"examples": {"directories": [rel_examples]}},
                "runOptions": {"asyncapi": asyncapi_options},
            }
        },
        "dependencies": {"services": {}},
        "components": {
            "sources": {
                report["serviceName"]: {"provides": report["serviceName"]},
            },
            "services": {
                report["serviceName"]: {"source": report["serviceName"]},
            },
            "runOptions": {
                report["serviceName"]: {"asyncapi": asyncapi_options},
            },
        },
    }


def build_example(op: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    known_models = {
        name: [ModelField(field["name"], field["type"], field["required"]) for field in fields]
        for name, fields in report.get("diagnostics", {}).get("modelDefinitions", {}).items()
    }
    schema_components: dict[str, Any] = {}
    for schema_name in op.get("requestSchemaHints", []) + op.get("replySchemaHints", []):
        ensure_schema_components(schema_name, schema_components, known_models)
    example = {"name": op["operationId"].upper().replace("-", "_")}
    if op["type"] == "send-only":
        example["send"] = {
            "topic": op["requestChannel"],
            "headers": {"requestId": "sample-request-id"} if op["correlationStrategy"] in {"explicit", "inferred"} else {},
            "payload": example_payload(op, "request", schema_components),
        }
    else:
        example["receive"] = {
            "topic": op["requestChannel"],
            "headers": {"requestId": "sample-request-id"} if op["correlationStrategy"] in {"explicit", "inferred"} else {},
            "payload": example_payload(op, "request", schema_components),
        }
    if op.get("replyChannel"):
        example["send"] = {
            "topic": op["replyChannel"],
            "headers": {"requestId": "sample-request-id"} if op["correlationStrategy"] in {"explicit", "inferred"} else {},
            "payload": example_payload(op, "reply", schema_components),
        }
    if op.get("retryChannel"):
        example["retry"] = {
            "topic": op["retryChannel"],
            "headers": {"requestId": "sample-request-id"} if op["correlationStrategy"] in {"explicit", "inferred"} else {},
            "payload": example_payload(op, "reply", schema_components),
        }
    if op.get("dlqChannel"):
        example["dlq"] = {
            "topic": op["dlqChannel"],
            "headers": {"requestId": "sample-request-id"} if op["correlationStrategy"] in {"explicit", "inferred"} else {},
            "payload": example_payload(op, "reply", schema_components),
        }
    return example


def build_compose_test_command(app_port: int, protocol: str) -> str:
    broker_rewrite = ""
    if protocol == "kafka":
        broker_rewrite = "sed -i 's#host: \"localhost:9092\"#host: \"kafka:29092\"#' /tmp/specmatic-run/specmatic.yaml && "
    return (
        "sh -lc \"rm -rf /tmp/specmatic-run && "
        "cp -R /workspace /tmp/specmatic-run && "
        f"{broker_rewrite}"
        f"find /tmp/specmatic-run/examples -name '*.json' -exec sed -i 's#http://localhost:{app_port}#http://app:{app_port}#g' {{}} + 2>/dev/null || true && "
        "specmatic test --config /tmp/specmatic-run/specmatic.yaml\""
    )


def build_docker_compose(root: Path, report: dict[str, Any], generated_dir: Path) -> dict[str, Any]:
    app_runtime = detect_app_runtime(root)
    app_port = app_runtime["port"]
    protocol = (
        report.get("diagnostics", {})
        .get("runtimeHints", {})
        .get("suggestedAsyncServers", [{}])[0]
        .get("protocol", "kafka")
    )

    services: dict[str, Any] = {}
    app_service: dict[str, Any] = {
        "ports": [f"{app_port}:{app_port}"],
    }
    if "build" in app_runtime:
        app_service["build"] = app_runtime["build"]
    else:
        app_service["image"] = app_runtime["image"]
        app_service["working_dir"] = app_runtime["workingDir"]
        app_service["volumes"] = app_runtime["volumes"]
    if app_runtime.get("command"):
        app_service["command"] = app_runtime["command"]

    depends_on: dict[str, Any] = {}
    environment: dict[str, Any] = {}

    if protocol == "kafka":
        services["zookeeper"] = {
            "image": "confluentinc/cp-zookeeper:7.6.1",
            "environment": {
                "ZOOKEEPER_CLIENT_PORT": 2181,
                "ZOOKEEPER_TICK_TIME": 2000,
            },
        }
        services["kafka"] = {
            "image": "confluentinc/cp-kafka:7.6.1",
            "ports": ["9092:9092"],
            "depends_on": {"zookeeper": {"condition": "service_started"}},
            "environment": {
                "KAFKA_BROKER_ID": 1,
                "KAFKA_ZOOKEEPER_CONNECT": "zookeeper:2181",
                "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT",
                "KAFKA_ADVERTISED_LISTENERS": "PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092",
                "KAFKA_LISTENERS": "PLAINTEXT://0.0.0.0:29092,PLAINTEXT_HOST://0.0.0.0:9092",
                "KAFKA_INTER_BROKER_LISTENER_NAME": "PLAINTEXT",
                "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": 1,
                "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": 1,
                "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": 1,
            },
        }
        depends_on["kafka"] = {"condition": "service_started"}
        environment["KAFKA_BOOTSTRAP_SERVERS"] = "kafka:29092"
        environment["SPRING_KAFKA_BOOTSTRAP_SERVERS"] = "kafka:29092"
        if report["signals"]["avroDetected"]:
            services["schema-registry"] = {
                "image": "confluentinc/cp-schema-registry:7.6.1",
                "ports": ["8081:8081"],
                "depends_on": {"kafka": {"condition": "service_started"}},
                "environment": {
                    "SCHEMA_REGISTRY_HOST_NAME": "schema-registry",
                    "SCHEMA_REGISTRY_LISTENERS": "http://0.0.0.0:8081",
                    "SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS": "PLAINTEXT://kafka:29092",
                },
            }
            depends_on["schema-registry"] = {"condition": "service_started"}
            environment["SCHEMA_REGISTRY_URL"] = "http://schema-registry:8081"

    if environment:
        app_service["environment"] = environment
    if depends_on:
        app_service["depends_on"] = depends_on

    services["app"] = app_service
    services["specmatic-tests"] = {
        "image": "specmatic/enterprise",
        "working_dir": "/workspace",
        "volumes": ["./:/workspace"],
        "depends_on": {"app": {"condition": "service_started"}, **depends_on},
        "command": build_compose_test_command(app_port, protocol),
    }

    return {
        "services": services,
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def command_inspect(args: argparse.Namespace) -> int:
    root = Path(args.target).resolve()
    report = infer_operations(root)
    generated_dir = choose_generated_dir(root)
    generated_dir.mkdir(parents=True, exist_ok=True)
    report_path = generated_dir / "extraction-report.json"
    review_path = generated_dir / "operation-review.md"
    write_json(report_path, report)
    write_text(review_path, render_review(report))
    print(f"Wrote extraction report: {report_path}")
    print(f"Wrote operation review: {review_path}")
    print(render_review(report))
    return 0


def load_approved_operations(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "operations" in data:
        operations = data["operations"]
    else:
        operations = data
    if not isinstance(operations, list):
        raise SystemExit("Approved operations file must be a list or an object with an 'operations' list.")
    return operations


def command_generate(args: argparse.Namespace) -> int:
    root = Path(args.target).resolve()
    report_path = Path(args.report).resolve()
    approved_path = Path(args.approved).resolve()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    approved = load_approved_operations(approved_path)

    generated_dir = resolve_generated_dir_from_path(report_path)
    specs_dir = generated_dir / "specs"
    examples_dir = generated_dir / "examples" / report["serviceName"]
    reports_dir = generated_dir / "reports"
    specs_dir.mkdir(parents=True, exist_ok=True)
    examples_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    asyncapi_doc = build_asyncapi(report, approved)
    specmatic_doc = build_specmatic_config(root, report, generated_dir)
    write_text(specs_dir / "asyncapi-extracted.yaml", yaml_from_structure(asyncapi_doc) + "\n")
    write_text(
        specs_dir / "asyncapi-overlay.yaml",
        "# Overlay for generated contract refinement.\n# Keep spec-only adjustments here when they should remain separate from the base extraction.\n",
    )
    write_text(generated_dir / "specmatic.yaml", yaml_from_structure(specmatic_doc) + "\n")
    write_text(generated_dir / "docker-compose.yml", yaml_from_structure(build_docker_compose(root, report, generated_dir)) + "\n")
    shutil.copy2(
        Path(__file__).with_name("run_specmatic_async_tests.sh"),
        generated_dir / "run_async_contract_tests.sh",
    )
    os.chmod(generated_dir / "run_async_contract_tests.sh", 0o755)
    write_json(generated_dir / "approved-operations.json", {"operations": approved})
    write_json(generated_dir / "extraction-report.json", report)

    for op in approved:
        example = build_example(op, report)
        write_json(examples_dir / f"{op['operationId']}.json", example)

    print(f"Generated suite at: {generated_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract AsyncAPI 3.0.0 and a Specmatic async suite from code.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a codebase and infer candidate operations.")
    inspect_parser.add_argument("target", help="Target application root")
    inspect_parser.set_defaults(func=command_inspect)

    generate_parser = subparsers.add_parser("generate", help="Generate a suite from approved operations.")
    generate_parser.add_argument("target", help="Target application root")
    generate_parser.add_argument("--report", required=True, help="Path to extraction-report.json")
    generate_parser.add_argument("--approved", required=True, help="Path to approved-operations.json")
    generate_parser.set_defaults(func=command_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
