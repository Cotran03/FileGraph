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


class SameStemExportDetector:
    name = "SameStemExportDetector"
    source_extensions = {".docx", ".pptx", ".xlsx", ".odt", ".odp", ".ods"}
    target_extensions = {".pdf"}

    def detect_all(self, nodes: list[dict]) -> list[DetectedRelationship]:
        by_parent_and_stem: dict[tuple[str, str], list[dict]] = {}
        for node in nodes:
            path = Path(str(node["path"]))
            key = (str(path.parent).casefold(), path.stem.casefold())
            by_parent_and_stem.setdefault(key, []).append(node)
        detected = []
        for matching_nodes in by_parent_and_stem.values():
            sources = [n for n in matching_nodes if Path(str(n["path"])).suffix.casefold() in self.source_extensions]
            targets = [n for n in matching_nodes if Path(str(n["path"])).suffix.casefold() in self.target_extensions]
            for source_node in sources:
                for target_node in targets:
                    source_path = Path(str(source_node["path"]))
                    target_path = Path(str(target_node["path"]))
                    confidence = _export_confidence(source_path, target_path)
                    detected.append(
                        DetectedRelationship(
                            source_node_id=int(source_node["node_id"]),
                            target_node_id=int(target_node["node_id"]),
                            relation_type_code="EXPORTED_AS",
                            confidence=confidence,
                            detector=self.name,
                            evidence=(
                                f"같은 폴더의 동일 파일명 `{source_path.name}` / `{target_path.name}`"
                                f" · 수정 시각 근접도 반영"
                            ),
                        )
                    )
        return detected


def analyze_registered_files(
    database: DatabaseManager,
    *,
    changed_node_ids: set[int] | None = None,
) -> dict[str, int]:
    nodes = database.list_nodes()
    nodes_by_path = {str(node["path"]).casefold(): node for node in nodes}
    candidates: list[DetectedRelationship] = []
    python_detector = PythonFileReferenceDetector()
    for node in nodes:
        if changed_node_ids is not None and int(node["node_id"]) not in changed_node_ids:
            continue
        candidates.extend(python_detector.detect(node, nodes_by_path))
    export_candidates = SameStemExportDetector().detect_all(nodes)
    if changed_node_ids is not None:
        export_candidates = [
            candidate
            for candidate in export_candidates
            if candidate.source_node_id in changed_node_ids or candidate.target_node_id in changed_node_ids
        ]
    candidates.extend(export_candidates)
    detected_count = 0
    created_count = 0
    for candidate in candidates:
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


def analyze_registered_python_files(database: DatabaseManager) -> dict[str, int]:
    return analyze_registered_files(database)


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


def _export_confidence(source_path: Path, target_path: Path) -> float:
    try:
        seconds = abs(source_path.stat().st_mtime - target_path.stat().st_mtime)
    except OSError:
        return 0.65
    if seconds <= 300:
        return 0.85
    if seconds <= 3600:
        return 0.75
    return 0.65
