from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    volume_serial TEXT NOT NULL,
    node_type TEXT NOT NULL CHECK (node_type IN ('FILE', 'FOLDER')),
    status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'MISSING', 'DELETED', 'ACCESS_DENIED')),
    name TEXT NOT NULL,
    path TEXT NOT NULL,
    file_hash TEXT,
    layout_x REAL,
    layout_y REAL,
    note TEXT,
    highlight_color TEXT,
    ai_status TEXT NOT NULL DEFAULT 'PENDING'
        CHECK (ai_status IN ('PENDING', 'SUCCESS', 'FAILED', 'SKIPPED')),
    ai_context TEXT,
    ai_category TEXT,
    last_seen TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (path),
    UNIQUE (file_id, volume_serial)
);

CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_file_hash ON nodes(file_hash);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);

CREATE TABLE IF NOT EXISTS relation_types (
    relation_type_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    color TEXT NOT NULL DEFAULT '#64748B',
    default_is_directional INTEGER NOT NULL DEFAULT 0
        CHECK (default_is_directional IN (0, 1)),
    is_system INTEGER NOT NULL DEFAULT 0
        CHECK (is_system IN (0, 1)),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO relation_types (
    relation_type_id,
    code,
    name,
    description,
    color,
    default_is_directional,
    is_system
) VALUES
    (1, 'RELATED', '관련 있음', '일반적인 관련 관계', '#64748B', 0, 1),
    (2, 'REFERENCE', '참고자료', '출발 노드가 도착 노드를 참고함', '#2563EB', 1, 1),
    (3, 'GENERATED_FROM', '원본에서 생성됨', '출발 노드가 도착 노드에서 생성됨', '#7C3AED', 1, 1),
    (4, 'CONTAINS', '포함', '출발 노드가 도착 노드를 포함함', '#059669', 1, 1),
    (5, 'VERSION_OF', '다른 버전', '두 노드가 서로 다른 버전임', '#D97706', 0, 1);

CREATE TABLE IF NOT EXISTS relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_type_id INTEGER NOT NULL DEFAULT 1,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    is_directional INTEGER NOT NULL DEFAULT 0
        CHECK (is_directional IN (0, 1)),
    strength TEXT NOT NULL DEFAULT 'MEDIUM'
        CHECK (strength IN ('HIGH', 'MEDIUM', 'LOW')),
    created_by TEXT NOT NULL DEFAULT 'USER'
        CHECK (created_by IN ('USER', 'AI')),
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (relation_type_id) REFERENCES relation_types(relation_type_id),
    FOREIGN KEY (source_id) REFERENCES nodes(node_id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES nodes(node_id) ON DELETE CASCADE,
    CHECK (source_id <> target_id)
);

CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(relation_type_id);
CREATE INDEX IF NOT EXISTS idx_relations_direction ON relations(is_directional);

CREATE TABLE IF NOT EXISTS drive_map (
    old_file_id TEXT NOT NULL,
    old_volume_serial TEXT NOT NULL,
    new_file_id TEXT,
    new_volume_serial TEXT,
    file_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (old_file_id, old_volume_serial)
);

CREATE INDEX IF NOT EXISTS idx_drive_map_hash ON drive_map(file_hash);

CREATE TABLE IF NOT EXISTS move_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT NOT NULL,
    node_id INTEGER,
    old_path TEXT NOT NULL,
    new_path TEXT NOT NULL,
    old_file_hash TEXT,
    new_file_hash TEXT,
    moved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    undone_at TEXT,
    FOREIGN KEY (node_id) REFERENCES nodes(node_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_move_history_operation ON move_history(operation_id);
CREATE INDEX IF NOT EXISTS idx_move_history_node ON move_history(node_id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scan_history (
    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    total_files INTEGER NOT NULL DEFAULT 0,
    changed_files INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    note TEXT
);
"""

_UNSET = object()


class DatabaseError(Exception):
    """Base exception for database-layer failures."""


class DuplicateNodeError(DatabaseError):
    def __init__(self, existing_node: dict[str, Any]) -> None:
        super().__init__("A node for this path already exists.")
        self.existing_node = existing_node


class DuplicateRelationError(DatabaseError):
    def __init__(self, existing_relation: dict[str, Any]) -> None:
        super().__init__("A matching relation already exists.")
        self.existing_relation = existing_relation


class DatabaseManager:
    def __init__(self, db_path: str | os.PathLike[str]) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> "DatabaseManager":
        self.connect()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        if self._conn is None:
            raise RuntimeError("Database connection was not initialized.")
        return self._conn

    def connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode = MEMORY")
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def init_db(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self._apply_migrations()
        self.conn.commit()

    def add_node(
        self,
        path: str | os.PathLike[str],
        *,
        node_type: str | None = None,
        name: str | None = None,
        file_hash: str | None = None,
        ai_status: str = "PENDING",
        ai_context: str | None = None,
        ai_category: str | None = None,
    ) -> int:
        normalized_path = normalize_path(path)
        existing = self.get_node_by_path(normalized_path)
        if existing:
            if existing["status"] == "DELETED":
                return self.restore_node(
                    existing["node_id"],
                    path=normalized_path,
                    node_type=node_type,
                    name=name,
                    file_hash=file_hash,
                    ai_status=ai_status,
                    ai_context=ai_context,
                    ai_category=ai_category,
                )
            raise DuplicateNodeError(existing)

        metadata = get_file_identity(normalized_path)
        resolved_node_type = node_type or infer_node_type(normalized_path)
        resolved_name = name or Path(normalized_path).name or normalized_path

        cursor = self.conn.execute(
            """
            INSERT INTO nodes (
                file_id,
                volume_serial,
                node_type,
                status,
                name,
                path,
                file_hash,
                ai_status,
                ai_context,
                ai_category,
                last_seen
            ) VALUES (?, ?, ?, 'ACTIVE', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                metadata["file_id"],
                metadata["volume_serial"],
                resolved_node_type,
                resolved_name,
                normalized_path,
                file_hash,
                ai_status,
                ai_context,
                ai_category,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def restore_node(
        self,
        node_id: int,
        *,
        path: str | os.PathLike[str] | None = None,
        node_type: str | None = None,
        name: str | None = None,
        file_hash: str | None = None,
        ai_status: str | None = None,
        ai_context: str | None = None,
        ai_category: str | None = None,
    ) -> int:
        existing = self.get_node(node_id)
        if existing is None:
            raise ValueError("Unknown node.")

        normalized_path = normalize_path(path or existing["path"])
        metadata = get_file_identity(normalized_path)
        resolved_node_type = node_type or infer_node_type(normalized_path)
        resolved_name = name or Path(normalized_path).name or normalized_path
        resolved_ai_status = ai_status or existing["ai_status"]
        resolved_ai_context = ai_context if ai_context is not None else existing["ai_context"]
        resolved_ai_category = ai_category if ai_category is not None else existing["ai_category"]

        self.conn.execute(
            """
            UPDATE nodes
            SET file_id = ?,
                volume_serial = ?,
                node_type = ?,
                status = 'ACTIVE',
                name = ?,
                path = ?,
                file_hash = ?,
                ai_status = ?,
                ai_context = ?,
                ai_category = ?,
                last_seen = CURRENT_TIMESTAMP,
                deleted_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE node_id = ?
            """,
            (
                metadata["file_id"],
                metadata["volume_serial"],
                resolved_node_type,
                resolved_name,
                normalized_path,
                file_hash,
                resolved_ai_status,
                resolved_ai_context,
                resolved_ai_category,
                node_id,
            ),
        )
        self.conn.commit()
        return node_id

    def get_node(self, node_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE node_id = ?",
            (node_id,),
        ).fetchone()
        return row_to_dict(row)

    def get_node_by_path(self, path: str | os.PathLike[str]) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE path = ?",
            (normalize_path(path),),
        ).fetchone()
        return row_to_dict(row)

    def list_nodes(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM nodes"
        params: tuple[Any, ...] = ()
        if not include_deleted:
            sql += " WHERE status <> ?"
            params = ("DELETED",)
        sql += " ORDER BY name COLLATE NOCASE"
        return rows_to_dicts(self.conn.execute(sql, params).fetchall())

    def search_nodes(self, query: str, *, limit: int = 50) -> list[dict[str, Any]]:
        pattern = f"%{query.strip()}%"
        rows = self.conn.execute(
            """
            SELECT *
            FROM nodes
            WHERE status <> 'DELETED'
              AND (
                  name LIKE ?
                  OR path LIKE ?
                  OR COALESCE(ai_category, '') LIKE ?
                  OR COALESCE(ai_context, '') LIKE ?
              )
            ORDER BY name COLLATE NOCASE
            LIMIT ?
            """,
            (pattern, pattern, pattern, pattern, limit),
        ).fetchall()
        return rows_to_dicts(rows)

    def update_node_layout(self, node_id: int, layout_x: float | None, layout_y: float | None) -> None:
        self.conn.execute(
            """
            UPDATE nodes
            SET layout_x = ?, layout_y = ?, updated_at = CURRENT_TIMESTAMP
            WHERE node_id = ?
            """,
            (layout_x, layout_y, node_id),
        )
        self.conn.commit()

    def update_node_file_hash(self, node_id: int, file_hash: str | None) -> None:
        self.conn.execute(
            """
            UPDATE nodes
            SET file_hash = ?, updated_at = CURRENT_TIMESTAMP
            WHERE node_id = ?
            """,
            (file_hash, node_id),
        )
        self.conn.commit()

    def update_node_status(self, node_id: int, status: str) -> None:
        self.conn.execute(
            """
            UPDATE nodes
            SET status = ?,
                deleted_at = CASE WHEN ? IN ('MISSING', 'DELETED') THEN CURRENT_TIMESTAMP ELSE NULL END,
                last_seen = CASE WHEN ? = 'ACTIVE' THEN CURRENT_TIMESTAMP ELSE last_seen END,
                updated_at = CURRENT_TIMESTAMP
            WHERE node_id = ?
            """,
            (status, status, status, node_id),
        )
        self.conn.commit()

    def update_node_note(self, node_id: int, note: str | None) -> None:
        self.conn.execute(
            """
            UPDATE nodes
            SET note = ?, updated_at = CURRENT_TIMESTAMP
            WHERE node_id = ?
            """,
            (normalize_optional_text(note), node_id),
        )
        self.conn.commit()

    def update_node_highlight_color(self, node_id: int, color: str | None) -> None:
        self.conn.execute(
            """
            UPDATE nodes
            SET highlight_color = ?, updated_at = CURRENT_TIMESTAMP
            WHERE node_id = ?
            """,
            (normalize_optional_text(color), node_id),
        )
        self.conn.commit()

    def list_relation_types(self, *, include_inactive: bool = False) -> list[dict[str, Any]]:
        sql = "SELECT * FROM relation_types"
        params: tuple[Any, ...] = ()
        if not include_inactive:
            sql += " WHERE is_active = ?"
            params = (1,)
        sql += " ORDER BY is_system DESC, relation_type_id"
        return rows_to_dicts(self.conn.execute(sql, params).fetchall())

    def get_relation_type_by_code(self, code: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM relation_types WHERE code = ?",
            (code.upper(),),
        ).fetchone()
        return row_to_dict(row)

    def add_relation_type(
        self,
        name: str,
        *,
        description: str | None = None,
        color: str = "#64748B",
        default_is_directional: bool = False,
    ) -> int:
        code = relation_type_code_from_name(name)
        cursor = self.conn.execute(
            """
            INSERT INTO relation_types (
                code,
                name,
                description,
                color,
                default_is_directional,
                is_system
            ) VALUES (?, ?, ?, ?, ?, 0)
            """,
            (code, name.strip(), description, color, int(default_is_directional)),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def update_relation_type_color(self, relation_type_id: int, color: str) -> None:
        self.conn.execute(
            """
            UPDATE relation_types
            SET color = ?, updated_at = CURRENT_TIMESTAMP
            WHERE relation_type_id = ?
            """,
            (color, relation_type_id),
        )
        self.conn.commit()

    def add_relation(
        self,
        source_id: int,
        target_id: int,
        *,
        relation_type_id: int | None = None,
        relation_type_code: str = "RELATED",
        is_directional: bool | None = None,
        strength: str = "MEDIUM",
        created_by: str = "USER",
        description: str | None = None,
    ) -> int:
        if source_id == target_id:
            raise ValueError("source_id and target_id must be different.")

        relation_type = self._resolve_relation_type(relation_type_id, relation_type_code)
        resolved_is_directional = (
            bool(relation_type["default_is_directional"])
            if is_directional is None
            else bool(is_directional)
        )

        existing = self.find_duplicate_relation(
            source_id,
            target_id,
            relation_type["relation_type_id"],
            resolved_is_directional,
        )
        if existing:
            raise DuplicateRelationError(existing)

        cursor = self.conn.execute(
            """
            INSERT INTO relations (
                relation_type_id,
                source_id,
                target_id,
                is_directional,
                strength,
                created_by,
                description
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                relation_type["relation_type_id"],
                source_id,
                target_id,
                int(resolved_is_directional),
                strength,
                created_by,
                description,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def find_duplicate_relation(
        self,
        source_id: int,
        target_id: int,
        relation_type_id: int,
        is_directional: bool,
    ) -> dict[str, Any] | None:
        if is_directional:
            row = self.conn.execute(
                """
                SELECT r.*, rt.code AS relation_type_code, rt.name AS relation_type_name
                FROM relations r
                JOIN relation_types rt ON rt.relation_type_id = r.relation_type_id
                WHERE r.source_id = ?
                  AND r.target_id = ?
                  AND r.relation_type_id = ?
                  AND r.is_directional = 1
                """,
                (source_id, target_id, relation_type_id),
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT r.*, rt.code AS relation_type_code, rt.name AS relation_type_name
                FROM relations r
                JOIN relation_types rt ON rt.relation_type_id = r.relation_type_id
                WHERE r.relation_type_id = ?
                  AND r.is_directional = 0
                  AND (
                    (r.source_id = ? AND r.target_id = ?)
                    OR (r.source_id = ? AND r.target_id = ?)
                  )
                """,
                (relation_type_id, source_id, target_id, target_id, source_id),
            ).fetchone()
        return row_to_dict(row)

    def list_relations(
        self,
        *,
        node_id: int | None = None,
        include_deleted: bool = False,
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT
                r.*,
                rt.code AS relation_type_code,
                rt.name AS relation_type_name,
                rt.color AS relation_type_color,
                s.name AS source_name,
                t.name AS target_name
            FROM relations r
            JOIN relation_types rt ON rt.relation_type_id = r.relation_type_id
            JOIN nodes s ON s.node_id = r.source_id
            JOIN nodes t ON t.node_id = r.target_id
            WHERE (? IS NULL OR r.source_id = ? OR r.target_id = ?)
              AND (? = 1 OR (s.status <> 'DELETED' AND t.status <> 'DELETED'))
            ORDER BY r.created_at DESC, r.relation_id DESC
            """,
            (node_id, node_id, node_id, int(include_deleted)),
        ).fetchall()
        return rows_to_dicts(rows)

    def get_relation(self, relation_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
                r.*,
                rt.code AS relation_type_code,
                rt.name AS relation_type_name,
                rt.color AS relation_type_color,
                s.name AS source_name,
                t.name AS target_name
            FROM relations r
            JOIN relation_types rt ON rt.relation_type_id = r.relation_type_id
            JOIN nodes s ON s.node_id = r.source_id
            JOIN nodes t ON t.node_id = r.target_id
            WHERE r.relation_id = ?
            """,
            (relation_id,),
        ).fetchone()
        return row_to_dict(row)

    def update_relation(
        self,
        relation_id: int,
        *,
        relation_type_id: int | None = None,
        strength: str | None = None,
        description: Any = _UNSET,
        is_directional: bool | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE relations
            SET relation_type_id = CASE WHEN ? THEN ? ELSE relation_type_id END,
                strength = CASE WHEN ? THEN ? ELSE strength END,
                description = CASE WHEN ? THEN ? ELSE description END,
                is_directional = CASE WHEN ? THEN ? ELSE is_directional END,
                updated_at = CURRENT_TIMESTAMP
            WHERE relation_id = ?
            """,
            (
                int(relation_type_id is not None),
                relation_type_id,
                int(strength is not None),
                strength,
                int(description is not _UNSET),
                None if description is _UNSET else description,
                int(is_directional is not None),
                None if is_directional is None else int(is_directional),
                relation_id,
            ),
        )
        self.conn.commit()

    def delete_relation(self, relation_id: int) -> None:
        self.conn.execute(
            "DELETE FROM relations WHERE relation_id = ?",
            (relation_id,),
        )
        self.conn.commit()

    def set_setting(self, key: str, value: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value),
        )
        self.conn.commit()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
        return default if row is None else row["value"]

    def list_orphan_nodes(self) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT n.*
            FROM nodes n
            WHERE n.status <> 'DELETED'
              AND NOT EXISTS (
                  SELECT 1
                  FROM relations r
                  JOIN nodes s ON s.node_id = r.source_id
                  JOIN nodes t ON t.node_id = r.target_id
                  WHERE (r.source_id = n.node_id OR r.target_id = n.node_id)
                    AND s.status <> 'DELETED'
                    AND t.status <> 'DELETED'
              )
            ORDER BY n.name COLLATE NOCASE
            """
        ).fetchall()
        return rows_to_dicts(rows)

    def list_duplicate_candidate_groups(self) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        rows = self.conn.execute(
            """
            SELECT file_hash, COUNT(*) AS match_count
            FROM nodes
            WHERE status <> 'DELETED'
              AND COALESCE(file_hash, '') <> ''
            GROUP BY file_hash
            HAVING COUNT(*) > 1
            ORDER BY match_count DESC, file_hash
            """
        ).fetchall()
        for row in rows:
            nodes = rows_to_dicts(
                self.conn.execute(
                    """
                    SELECT *
                    FROM nodes
                    WHERE status <> 'DELETED'
                      AND file_hash = ?
                    ORDER BY name COLLATE NOCASE
                    """,
                    (row["file_hash"],),
                ).fetchall()
            )
            groups.append({"kind": "hash", "value": row["file_hash"], "nodes": nodes})

        rows = self.conn.execute(
            """
            SELECT LOWER(name) AS normalized_name, COUNT(*) AS match_count
            FROM nodes
            WHERE status <> 'DELETED'
            GROUP BY LOWER(name)
            HAVING COUNT(*) > 1
            ORDER BY match_count DESC, normalized_name
            """
        ).fetchall()
        for row in rows:
            nodes = rows_to_dicts(
                self.conn.execute(
                    """
                    SELECT *
                    FROM nodes
                    WHERE status <> 'DELETED'
                      AND LOWER(name) = ?
                    ORDER BY path COLLATE NOCASE
                    """,
                    (row["normalized_name"],),
                ).fetchall()
            )
            groups.append({"kind": "name", "value": row["normalized_name"], "nodes": nodes})
        return groups

    def _resolve_relation_type(self, relation_type_id: int | None, relation_type_code: str) -> dict[str, Any]:
        if relation_type_id is not None:
            row = self.conn.execute(
                "SELECT * FROM relation_types WHERE relation_type_id = ? AND is_active = 1",
                (relation_type_id,),
            ).fetchone()
        else:
            row = self.conn.execute(
                "SELECT * FROM relation_types WHERE code = ? AND is_active = 1",
                (relation_type_code.upper(),),
            ).fetchone()
        relation_type = row_to_dict(row)
        if relation_type is None:
            raise ValueError("Unknown relation type.")
        return relation_type

    def _apply_migrations(self) -> None:
        existing_columns = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(nodes)").fetchall()
        }
        for column_name, column_sql in (
            ("note", "ALTER TABLE nodes ADD COLUMN note TEXT"),
            ("highlight_color", "ALTER TABLE nodes ADD COLUMN highlight_color TEXT"),
        ):
            if column_name not in existing_columns:
                self.conn.execute(column_sql)


def normalize_path(path: str | os.PathLike[str]) -> str:
    return str(Path(path).expanduser().resolve(strict=False))


def infer_node_type(path: str | os.PathLike[str]) -> str:
    return "FOLDER" if Path(path).is_dir() else "FILE"


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def get_file_identity(path: str | os.PathLike[str]) -> dict[str, str]:
    normalized_path = normalize_path(path)
    volume_serial = get_volume_label(normalized_path)
    try:
        stat_result = os.stat(normalized_path)
        file_id = str(stat_result.st_ino)
    except OSError:
        digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
        file_id = f"path:{digest}"
    return {"file_id": file_id, "volume_serial": volume_serial}


def get_volume_label(path: str | os.PathLike[str]) -> str:
    drive, _tail = os.path.splitdrive(str(path))
    return drive.upper() or "LOCAL"


def relation_type_code_from_name(name: str) -> str:
    stripped = name.strip()
    ascii_code = re.sub(r"[^A-Za-z0-9]+", "_", stripped).strip("_").upper()
    if ascii_code:
        return f"CUSTOM_{ascii_code}"
    digest = hashlib.sha256(stripped.encode("utf-8")).hexdigest()[:12].upper()
    return f"CUSTOM_{digest}"


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return None if row is None else dict(row)


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]
