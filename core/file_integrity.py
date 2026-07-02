from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
from typing import Any, Callable, Iterable, Sequence

from .database_manager import DatabaseManager


ACTIVE = "ACTIVE"
MISSING = "MISSING"
ACCESS_DENIED = "ACCESS_DENIED"
VALID_SCAN_STATUSES = {ACTIVE, MISSING, ACCESS_DENIED}
MAX_AUTO_HASH_BYTES = 100 * 1024 * 1024
HASH_CHUNK_SIZE = 1024 * 1024
SKIPPED_SCAN_DIR_NAMES = {
    ".git",
    ".venv",
    "venv",
    "ENV",
    "node_modules",
    "__pycache__",
}


@dataclass(frozen=True)
class NodeStatusChange:
    node_id: int
    name: str
    path: str
    old_status: str
    new_status: str


@dataclass(frozen=True)
class IntegrityScanResult:
    total: int
    active: int
    missing: int
    access_denied: int
    changed: tuple[NodeStatusChange, ...]
    hashes_updated: int = 0

    @property
    def changed_count(self) -> int:
        return len(self.changed)


@dataclass(frozen=True)
class RediscoveredNode:
    node_id: int
    name: str
    old_path: str
    new_path: str
    file_hash: str


@dataclass(frozen=True)
class RediscoveryResult:
    total_missing: int
    eligible_missing: int
    scanned_files: int
    restored: tuple[RediscoveredNode, ...]

    @property
    def restored_count(self) -> int:
        return len(self.restored)


StatusProbe = Callable[[dict[str, Any]], str]


def scan_file_statuses(
    database: DatabaseManager,
    *,
    status_probe: StatusProbe | None = None,
    update_hashes: bool = True,
    max_hash_size: int = MAX_AUTO_HASH_BYTES,
) -> IntegrityScanResult:
    probe = status_probe or probe_node_status
    counts = {ACTIVE: 0, MISSING: 0, ACCESS_DENIED: 0}
    changes: list[NodeStatusChange] = []
    hashes_updated = 0
    nodes = database.list_nodes()

    for node in nodes:
        new_status = probe(node)
        if new_status not in VALID_SCAN_STATUSES:
            raise ValueError(f"Unsupported scanned node status: {new_status}")

        counts[new_status] += 1
        old_status = node["status"]
        if old_status != new_status:
            database.update_node_status(node["node_id"], new_status)
            changes.append(
                NodeStatusChange(
                    node_id=int(node["node_id"]),
                    name=str(node.get("name") or ""),
                    path=str(node.get("path") or ""),
                    old_status=str(old_status),
                    new_status=new_status,
                )
            )

        if update_hashes and new_status == ACTIVE and should_hash_node(node):
            file_hash = compute_file_hash(node["path"], max_size=max_hash_size)
            if file_hash and file_hash != node.get("file_hash"):
                database.update_node_file_hash(node["node_id"], file_hash)
                hashes_updated += 1

    return IntegrityScanResult(
        total=len(nodes),
        active=counts[ACTIVE],
        missing=counts[MISSING],
        access_denied=counts[ACCESS_DENIED],
        changed=tuple(changes),
        hashes_updated=hashes_updated,
    )


def rediscover_missing_nodes(
    database: DatabaseManager,
    search_roots: Sequence[str | os.PathLike[str]],
    *,
    max_hash_size: int = MAX_AUTO_HASH_BYTES,
) -> RediscoveryResult:
    missing_nodes = [
        node
        for node in database.list_nodes()
        if node.get("status") == MISSING and node.get("node_type") == "FILE"
    ]
    nodes_by_hash: dict[str, list[dict[str, Any]]] = {}
    for node in missing_nodes:
        file_hash = node.get("file_hash")
        if file_hash:
            nodes_by_hash.setdefault(str(file_hash), []).append(node)

    scanned_files = 0
    restored: list[RediscoveredNode] = []
    restored_node_ids: set[int] = set()

    if not nodes_by_hash:
        return RediscoveryResult(
            total_missing=len(missing_nodes),
            eligible_missing=0,
            scanned_files=0,
            restored=(),
        )

    for candidate_path in iter_search_files(search_roots):
        scanned_files += 1
        candidate_hash = compute_file_hash(candidate_path, max_size=max_hash_size)
        if not candidate_hash:
            continue

        candidates = nodes_by_hash.get(candidate_hash, [])
        for node in candidates:
            node_id = int(node["node_id"])
            if node_id in restored_node_ids:
                continue

            normalized_candidate = str(candidate_path.expanduser().resolve(strict=False))
            existing = database.get_node_by_path(normalized_candidate)
            if existing and int(existing["node_id"]) != node_id:
                continue

            database.restore_node(
                node_id,
                path=normalized_candidate,
                node_type="FILE",
                file_hash=candidate_hash,
            )
            restored_node_ids.add(node_id)
            restored.append(
                RediscoveredNode(
                    node_id=node_id,
                    name=str(node.get("name") or ""),
                    old_path=str(node.get("path") or ""),
                    new_path=normalized_candidate,
                    file_hash=candidate_hash,
                )
            )
            break

    return RediscoveryResult(
        total_missing=len(missing_nodes),
        eligible_missing=sum(len(nodes) for nodes in nodes_by_hash.values()),
        scanned_files=scanned_files,
        restored=tuple(restored),
    )


def probe_node_status(node: dict[str, Any]) -> str:
    return probe_path_status(node.get("path") or "")


def probe_path_status(path: str | os.PathLike[str]) -> str:
    path_string = str(path)
    if not path_string:
        return MISSING

    try:
        stat_result = os.stat(path_string)
    except PermissionError:
        return ACCESS_DENIED
    except FileNotFoundError:
        return MISSING
    except OSError:
        return MISSING

    if stat.S_ISDIR(stat_result.st_mode):
        return probe_directory_access(path_string)
    return probe_file_access(path_string)


def probe_directory_access(path: str | os.PathLike[str]) -> str:
    try:
        with os.scandir(path):
            pass
    except PermissionError:
        return ACCESS_DENIED
    except FileNotFoundError:
        return MISSING
    except OSError:
        return ACCESS_DENIED
    return ACTIVE


def probe_file_access(path: str | os.PathLike[str]) -> str:
    try:
        with Path(path).open("rb"):
            pass
    except PermissionError:
        return ACCESS_DENIED
    except FileNotFoundError:
        return MISSING
    except IsADirectoryError:
        return ACTIVE
    except OSError:
        return ACCESS_DENIED
    return ACTIVE


def should_hash_node(node: dict[str, Any]) -> bool:
    return node.get("node_type") == "FILE" and bool(node.get("path"))


def compute_file_hash(
    path: str | os.PathLike[str],
    *,
    max_size: int = MAX_AUTO_HASH_BYTES,
) -> str | None:
    try:
        resolved_path = Path(path)
        if not resolved_path.is_file():
            return None
        if resolved_path.stat().st_size > max_size:
            return None
        digest = hashlib.sha256()
        with resolved_path.open("rb") as file:
            for chunk in iter(lambda: file.read(HASH_CHUNK_SIZE), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except (OSError, PermissionError):
        return None


def iter_search_files(search_roots: Iterable[str | os.PathLike[str]]) -> Iterable[Path]:
    seen_roots: set[str] = set()
    for raw_root in search_roots:
        root = Path(raw_root).expanduser().resolve(strict=False)
        root_key = os.path.normcase(str(root))
        if root_key in seen_roots or not root.is_dir():
            continue
        seen_roots.add(root_key)

        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                dirname
                for dirname in dirnames
                if dirname not in SKIPPED_SCAN_DIR_NAMES
            ]
            for filename in filenames:
                yield Path(current_root) / filename
