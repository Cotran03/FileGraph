from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .database_manager import DatabaseManager, normalize_path


@dataclass(frozen=True)
class DetectedRelationship:
    source_node_id: int
    target_node_id: int
    relation_type_code: str
    confidence: float
    detector: str
    evidence: str


READ_CALLS = {
    "open",
    "read_csv",
    "read_excel",
    "read_json",
    "read_parquet",
    "read_text",
    "read_bytes",
}
WRITE_CALLS = {
    "to_csv",
    "to_excel",
    "to_json",
    "to_parquet",
    "write_text",
    "write_bytes",
}


class PythonFileReferenceDetector:
    name = "PythonFileReferenceDetector"

    def detect(
        self,
        source_node: dict,
        nodes_by_path: dict[str, dict],
    ) -> list[DetectedRelationship]:
        source_path = Path(str(source_node["path"]))
        if source_path.suffix.casefold() != ".py" or not source_path.is_file():
            return []
        try:
            source = source_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(source_path))
        except (OSError, UnicodeError, SyntaxError):
            return []

        detected: list[DetectedRelationship] = []
        for call in (node for node in ast.walk(tree) if isinstance(node, ast.Call)):
            candidate = self._detect_call(call, source_path, nodes_by_path)
            if candidate is None:
                continue
            relation_type_code, target_node, expression = candidate
            if int(target_node["node_id"]) == int(source_node["node_id"]):
                continue
            detected.append(
                DetectedRelationship(
                    source_node_id=int(source_node["node_id"]),
                    target_node_id=int(target_node["node_id"]),
                    relation_type_code=relation_type_code,
                    confidence=0.95,
                    detector=self.name,
                    evidence=f"{source_path.name}:{call.lineno}에서 `{expression}` 발견",
                )
            )
        return detected

    def _detect_call(self, call, source_path, nodes_by_path):
        call_name = _call_name(call.func)
        if call_name not in READ_CALLS | WRITE_CALLS or not call.args:
            return None
        raw_path = _literal_string(call.args[0])
        if not raw_path:
            return None
        relation_type = "WRITES" if call_name in WRITE_CALLS else "READS"
        if call_name == "open" and len(call.args) > 1:
            mode = _literal_string(call.args[1]) or "r"
            relation_type = "WRITES" if any(flag in mode for flag in "wax+") else "READS"
        resolved_path = Path(raw_path)
        if not resolved_path.is_absolute():
            resolved_path = source_path.parent / resolved_path
        target_node = nodes_by_path.get(normalize_path(resolved_path).casefold())
        if target_node is None:
            return None
        return relation_type, target_node, f"{call_name}({raw_path!r})"


def analyze_registered_python_files(database: DatabaseManager) -> dict[str, int]:
    nodes = database.list_nodes()
    nodes_by_path = {str(node["path"]).casefold(): node for node in nodes}
    detector = PythonFileReferenceDetector()
    detected_count = 0
    created_count = 0
    for node in nodes:
        for candidate in detector.detect(node, nodes_by_path):
            detected_count += 1
            candidate_id = database.add_relationship_candidate(
                candidate.source_node_id,
                candidate.target_node_id,
                candidate.relation_type_code,
                confidence=candidate.confidence,
                detector=candidate.detector,
                evidence=candidate.evidence,
            )
            if candidate_id is not None:
                created_count += 1
    return {"detected": detected_count, "created": created_count}


def _call_name(function: ast.expr) -> str:
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _literal_string(expression: ast.expr) -> str | None:
    if isinstance(expression, ast.Constant) and isinstance(expression.value, str):
        return expression.value
    return None
