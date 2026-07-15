# FileGraph SPEC

이 문서는 FileGraph를 실제로 구현하기 위한 작업용 사양서입니다. README는 제품 소개와 방향을 담고, 이 파일은 기술 스택, 구현 결정, DB 구조, 정책, 테스트 기준을 관리합니다.

## 문서 상태

- 상태: MVP 구현 기준 정리 완료, 이후 기능은 Draft
- 기준일: 2026-07-09
- 구현 상태: 수동 파일 관계 그래프 MVP 완료, 설정 화면/라벨 UX/검색 제안/메모/강조/보기 프리셋/DB 가져오기/진행률과 취소 보강
- 이후 범위: 관계 타입 관리, 파일 이동 Undo, 대규모 성능 QA

## 관련 문서

- [README.md](../README.md): 제품 소개, 핵심 아이디어, 현재 상태
- [USAGE.md](./USAGE.md): 실행 방법과 사용 흐름
- [RELEASE_CHECKLIST.md](./RELEASE_CHECKLIST.md): AI 없는 첫 릴리즈 후보 검증 기준
- [requirements.txt](./requirements.txt): Python 의존성 목록

## 기술 스택

- Python 3.10+
- PySide6: Windows 데스크톱 GUI
- SQLite: 로컬 영속 저장소
- NetworkX: 그래프 구성과 레이아웃 계산
- pytest: 자동 테스트

## 현재 구현 모듈

- `main.py`: 런타임 경로 준비, 단일 프로세스 잠금, DB 초기화, PySide6 앱 실행
- `core/database_manager.py`: SQLite 스키마, relation type seed, 노드/관계 CRUD, 검색, 설정, 좌표/상태/해시 저장
- `core/graph_manager.py`: NetworkX 그래프 생성, 관계 강도 weight 변환, 레이아웃 계산, 포커스 노드 추출
- `core/relationship_detection.py`: 설명 가능한 관계 탐지기와 Python 로컬 파일 읽기·쓰기 후보 생성
- `core/file_integrity.py`: 파일 상태 검사, SHA-256 해시 계산, 누락 파일 해시 기반 재탐색, 진행률/취소 콜백
- `gui/main_window.py`: 메인 윈도우, 검색/검색 제안, 보기 프리셋, 그래프/제어 패널 연결, 설정 저장, 파일 위치 갱신, 누락 찾기, 폴더 내부 파일 접기/펼치기, 단축키, 백업/가져오기/내보내기
- `gui/graph_viewer.py`: 그래프 렌더링, 확장자/상태별 SVG 아이콘 표시, 사용자 지정 아이콘 매핑, 드래그, 선택, 라벨 표시 모드, 컨텍스트 메뉴, 드롭 처리
- `gui/control_panel.py`: 작업 패널, 관계 목록, 관계 수정/삭제, 검색/포커스/전체 보기/보기 프리셋, 주요 액션 버튼
- `gui/relation_dialog.py`: 관계 추가/수정 다이얼로그
- `gui/settings_dialog.py`: 그래프 표시, 노드 색상 선택기/미리보기/초기화, 강조색, 확장자 아이콘 매핑, 무시 폴더 설정 화면
- `gui/icon_mapping_dialog.py`: 확장자 아이콘 매핑 표 구성에 사용하는 아이콘 목록/라벨 보조 모듈
- `tests/`: DB, 그래프, GUI, 파일 무결성 자동 테스트

## 구현 완료 기능 요약

- 파일/폴더 노드 등록, 드래그 앤 드롭 등록
- 폴더 내부 파일 재귀 등록 기본 ON, 추가 전 미리보기, `CONTAINS` 관계 자동 생성
- 기본 관계 타입 seed와 관계 추가/수정/삭제
- 관계 방향성, 강도, 설명 저장
- 그래프 렌더링, 자동 배치, 노드 드래그 좌표 저장
- 파일 확장자/폴더/누락/권한 상태별 SVG 아이콘 표시, 사용자 지정 확장자 아이콘 매핑
- 폴더 노드의 내부 파일 접기/펼치기
- 검색, 검색 제안, 포커스 뷰, 전체 보기, 보기 프리셋, 자동 정렬
- 우클릭 컨텍스트 메뉴, 관계 목록 편집, 다중 선택 이동/삭제, 메모, 강조, 관계 타입 색상 변경
- 컨트롤 패널의 선택 노드 개수 표시와 선택 집합 일괄 삭제
- 별도 설정 화면, 노드 타입별/hover 라벨 표시 방식 설정, 간선 라벨 표시 방식 설정, 색상 선택기/미리보기/초기화, 강조/아이콘/무시 폴더 UI
- `Ctrl+A`로 현재 그래프에 보이는 노드 전체 선택
- 추가 단축키와 F1 단축키 도움말, 범례
- `Ctrl+Z` 그래프 작업 되돌리기
- 노드 soft delete와 삭제 노드 관계 숨김
- 수동 파일 위치 갱신
- SHA-256 해시 저장과 해시 기반 누락 파일 복구
- 폴더 대량 추가, 파일 위치 갱신, 누락 파일 찾기의 진행률과 취소
- DB 백업, DB 가져오기, JSON/CSV 내보내기, 고립 노드 보기, 중복 후보 확인
- README/USAGE/SPEC 문서 분리

## 결정 요약

아래 항목은 현재 추천 기본값입니다. 구현 중 더 나은 판단이 생기면 이 문서를 갱신합니다.

- MVP에서 반드시 들어가야 하는 기능:

  ```text
  - 파일/폴더 직접 추가
  - 관계 직접 추가
  - 검색
  - 그래프 저장
  ```

- 주 사용 대상과 작업 방식:

  ```text
  - 주 사용자는 누구인가?: 폴더 정리에 어려움을 느끼는 사람 혹은 파일이 너무 많아 찾기 힘든 사람
  - 주로 어떤 파일을 다루는가?: 사용자가 지정한 폴더 속 파일(시스템 파일 등은 제외)
  - 하나의 작업 공간은 보통 어느 폴더인가?: 사용자가 직접 선택한 프로젝트 폴더
  ```

- 관계 타입:

  ```text
  결정:
  - 기본 관계 타입 프리셋을 제공한다.
  - MVP 관계 생성 화면에서는 기본 관계 타입 프리셋 중 하나를 선택한다.
  - 관계의 구체적인 의미와 예외적인 뉘앙스는 description에 적는다.
  - 사용자 지정 관계 타입 추가는 MVP 이후 관계 타입 관리 화면에서 제공한다.
  - 관계마다 방향성 있음/없음을 선택할 수 있다.
  - 설명(description)은 선택 입력으로 둔다.

  기본 프리셋:
  - 관련 있음
  - 참고자료
  - 원본에서 생성됨
  - 포함
  - 다른 버전
  ```

- 파일 이동 안전 정책:

  ```text
  - 자동 정리는 사용자가 선택한 작업 공간 폴더 내부에서만 허용한다.
  - 원본 경로와 목적지 경로가 모두 작업 공간 내부인지 실행 직전에 검증한다.
  - Windows, Program Files, ProgramData, AppData, 드라이브 루트, 휴지통, 시스템 볼륨 정보, .git, .venv 같은 보호 경로는 자동 정리 대상에서 제외한다.
  - 실제 이동 전 반드시 미리보기 화면을 보여주고 사용자 승인을 받는다.
  - MVP에서는 같은 드라이브 안의 이동만 허용한다.
  - 이동 전 DB 백업을 생성하고, 모든 이동은 move_history에 기록한다.
  - Undo가 일부 실패하면 성공/실패 목록을 분리해서 보여주고, 실패한 파일은 사용자가 직접 확인하도록 남긴다.
  ```

## 1. 제품 목표

FileGraph는 파일 시스템의 물리적 위치와 별개로 파일/폴더 사이의 논리적 관계를 저장하고 시각화하는 앱입니다.

핵심 목표는 다음과 같습니다.

- 파일과 폴더를 노드로 등록한다.
- 노드 사이의 관계를 간선으로 등록한다.
- 관계의 강도와 설명을 저장한다.
- 그래프에서 관계가 강한 파일끼리 더 가깝게 보이도록 배치한다.
- 사용자가 수동으로 배치한 좌표는 유지한다.
- 파일이 이동되거나 삭제되어도 누적된 관계 기록은 보존한다.

## 2. 단계별 범위

### Phase 1: 수동 그래프 기반

현재 MVP 범위는 구현 완료 상태입니다.

- DB 생성 및 마이그레이션 기초
- 노드 CRUD
- 관계 CRUD
- 실제 파일/폴더 선택 등록
- 그래프 레이아웃 계산
- PySide6 메인 윈도우
- 그래프 노드/간선 표시
- 노드 드래그 후 좌표 저장
- 노드 더블클릭으로 파일 또는 폴더 열기
- 파일명, 경로 검색
- 폴더 내부 파일 등록과 `CONTAINS` 관계 자동 생성
- 폴더 내부 파일 노드 접기/펼치기
- 관계 수정/삭제와 노드 soft delete
- 오른쪽 드래그 다중 선택과 선택 노드 일괄 삭제

### Phase 2: 파일 무결성 및 복구

현재 구현된 항목은 다음과 같습니다.

- 수동 파일 위치 갱신 시 `path` 존재 여부 검사
- 누락 파일을 `MISSING` 상태로 표시
- 접근 불가 파일을 `ACCESS_DENIED` 상태로 표시
- 활성 파일 SHA-256 해시 저장
- 사용자가 선택한 폴더 안에서 해시 기반 누락 파일 재탐색
- 수동 파일 위치 갱신

아직 남은 항목은 다음과 같습니다.

- 동일 드라이브 이동 파일 자동 추적
- 중복 해시 파일 통합 UX
- scan_history 기록
- 대량 스캔 진행률 표시
- 수동/자동 새로고침 정책 정리

## 3. 프로젝트 구조

현재 구조는 다음과 같습니다.

```text
FileGraph/
  .venv/
  .vscode/
  main.py
  requirements.txt
  README.md
  SPEC.md
  USAGE.md
  config/
    README.md
  db/
    database.db
    template_db.db
  core/
    __init__.py
    database_manager.py
    file_integrity.py
    graph_manager.py
  gui/
    __init__.py
    main_window.py
    graph_viewer.py
    control_panel.py
    relation_dialog.py
  assets/
    *.svg
  tools/
    create_icons.py
  tests/
    test_*.py
  logs/
```

배포 후 런타임 데이터는 사용자별 쓰기 가능한 경로에 둡니다.

```text
%LOCALAPPDATA%/FileGraph/
  database.db
  config/
  logs/
  backup/
```

## 4. 런타임 경로 정책

개발 환경에서는 프로젝트 내부 경로를 사용합니다.

- DB: `db/database.db`
- 설정: `config/`
- 로그: `logs/`

PyInstaller 등으로 빌드된 실행 환경에서는 `%LOCALAPPDATA%/FileGraph/`를 사용합니다.

앱 시작 시 런타임 데이터 경로의 `FileGraph.lock`을 `QLockFile`로 잠급니다. 이미 다른 FileGraph 프로세스가 잠금을 보유하고 있으면 새 프로세스는 DB를 열거나 창을 만들지 않고 즉시 종료합니다.

- DB: `%LOCALAPPDATA%/FileGraph/database.db`
- 설정: `%LOCALAPPDATA%/FileGraph/config/`
- 로그: `%LOCALAPPDATA%/FileGraph/logs/`

최초 실행 시 `db/template_db.db`가 존재하고 런타임 DB가 없다면 복사합니다.

릴리즈 패키징:

- Windows 배포판은 PyInstaller 산출물인 `dist/FileGraph/` 폴더 전체를 zip으로 묶는다.
- GitHub Release asset 이름은 `FileGraph-vX.Y.Z-windows-x64.zip` 형식을 사용한다.
- GitHub가 자동으로 제공하는 `Source code (zip)`은 개발자용 소스 코드이며 일반 실행용 배포 파일로 안내하지 않는다.
- 사용자는 배포 zip을 내려받아 압축을 풀고 `FileGraph.exe`를 실행한다. Python, PySide6, PyInstaller, 소스 checkout은 필요하지 않다.

DB 백업/가져오기:

- DB 백업은 현재 SQLite DB 파일을 사용자가 선택한 `.db` 파일로 복사한다.
- DB 가져오기는 선택한 SQLite 파일에 `nodes`, `relations`, `relation_types`, `settings` 테이블이 있는지 확인한 뒤 현재 DB를 교체한다.
- 교체 전 현재 DB는 같은 폴더에 `.preimport-YYYYMMDD-HHMMSS.db` 형식으로 자동 백업한다.
- 가져오기 후 런타임 설정, 그래프 매니저, 선택 상태, 접힌 폴더 상태를 다시 초기화하고 그래프를 새로 불러온다.

## 5. 데이터 모델

### 5.1 enum 초안

DB에는 영어 enum 값을 저장하고, UI에서 한국어 라벨로 표시합니다.

```text
node_type:
  FILE
  FOLDER

node status:
  ACTIVE
  MISSING
  DELETED
  ACCESS_DENIED

relation strength:
  HIGH
  MEDIUM
  LOW
```

관계 타입은 고정 enum이 아니라 `relation_types` 테이블로 관리합니다. 앱은 기본 프리셋을 제공하고, 사용자는 새 관계 타입을 추가할 수 있습니다.

```text
기본 relation_types seed:
  RELATED        -> 관련 있음
  REFERENCE      -> 참고자료
  GENERATED_FROM -> 원본에서 생성됨
  CONTAINS       -> 포함
  VERSION_OF     -> 다른 버전
  SAME_FILE      -> 같은 파일
  READS          -> 읽음
  WRITES         -> 생성/기록
  EXPORTED_AS    -> 내보낸 파일

relation direction:
  is_directional = 1  방향 있음
  is_directional = 0  방향 없음
```

관계 타입 운영 규칙:

- 기본 프리셋은 `is_system = 1`로 저장한다.
- 기본 프리셋은 삭제하지 않고, 필요하면 비활성화만 검토한다.
- 사용자 지정 타입은 `is_system = 0`으로 저장한다.
- 사용자가 입력한 타입 이름은 중복을 막는다.
- `code`는 내부 식별자이며, 사용자 지정 타입은 앱이 이름을 기반으로 자동 생성한다.
- 관계 타입의 `default_is_directional`은 새 관계를 만들 때 초기값으로만 사용한다.
- 실제 관계의 방향성은 `relations.is_directional`에 저장한다.

### 5.2 SQLite DDL 초안

초기 구현은 아래 DDL을 기준으로 시작합니다. 실제 코드에서는 `core/database_manager.py`의 `init_db()`가 이 스키마를 생성합니다.

```sql
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
    last_seen TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (path)
);

CREATE INDEX IF NOT EXISTS idx_nodes_path ON nodes(path);
CREATE INDEX IF NOT EXISTS idx_nodes_name ON nodes(name);
CREATE INDEX IF NOT EXISTS idx_nodes_file_hash ON nodes(file_hash);
CREATE INDEX IF NOT EXISTS idx_nodes_status ON nodes(status);
CREATE INDEX IF NOT EXISTS idx_nodes_file_identity ON nodes(file_id, volume_serial);

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
    (5, 'VERSION_OF', '다른 버전', '두 노드가 서로 다른 버전임', '#D97706', 0, 1),
    (6, 'SAME_FILE', '같은 파일', '서로 다른 경로가 동일한 실제 파일을 가리킴', '#0891B2', 0, 1),
    (7, 'READS', '읽음', '출발 파일이 도착 파일을 입력으로 읽음', '#2563EB', 1, 1),
    (8, 'WRITES', '생성/기록', '출발 파일이 도착 파일을 생성하거나 기록함', '#DC2626', 1, 1),
    (9, 'EXPORTED_AS', '내보낸 파일', '출발 파일을 도착 형식으로 내보냄', '#7C3AED', 1, 1);

CREATE TABLE IF NOT EXISTS relations (
    relation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_type_id INTEGER NOT NULL DEFAULT 1,
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    is_directional INTEGER NOT NULL DEFAULT 0
        CHECK (is_directional IN (0, 1)),
    strength TEXT NOT NULL DEFAULT 'MEDIUM'
        CHECK (strength IN ('HIGH', 'MEDIUM', 'LOW')),
    description TEXT,
    source TEXT NOT NULL DEFAULT 'MANUAL',
    confidence REAL,
    evidence TEXT,
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

CREATE TABLE IF NOT EXISTS relationship_candidates (
    candidate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_node_id INTEGER NOT NULL,
    target_node_id INTEGER NOT NULL,
    suggested_relation_type_code TEXT NOT NULL,
    confidence REAL NOT NULL,
    detector TEXT NOT NULL,
    evidence TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_node_id) REFERENCES nodes(node_id) ON DELETE CASCADE,
    FOREIGN KEY (target_node_id) REFERENCES nodes(node_id) ON DELETE CASCADE
);

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
```

```text
결정:
- nodes.path는 UNIQUE로 둔다.
- move_history의 old_file_hash, new_file_hash는 저장을 시도하되 NULL을 허용한다.
- status 전이는 ACTIVE, MISSING, DELETED, ACCESS_DENIED 네 상태로 관리한다.
- 실제 파일이 사라진 경우 DB에서 즉시 삭제하지 않고 MISSING으로 둔다.
- 사용자가 앱에서 삭제 처리한 경우에만 DELETED로 둔다.
```

관계 중복 처리:

- 같은 두 노드 사이에 서로 다른 관계 타입은 허용한다.
- 같은 두 노드 사이에 같은 관계 타입을 중복 생성하려 하면 기존 관계 수정을 제안한다.
- 방향 있는 관계는 `source_id -> target_id` 순서를 의미 있게 저장한다.
- 방향 없는 관계는 그래프에서 화살표 없이 표시한다. 중복 판단 시 `A-B`와 `B-A`를 같은 관계로 본다.

## 6. 파일 식별 정책

파일 추적은 다음 정보를 조합합니다.

- `file_id`: Windows 파일 고유 ID
- `volume_serial`: 볼륨 식별자
- `file_hash`: SHA-256
- `path`: 현재 절대경로

현재 구현은 난이도를 낮추기 위해 다음 정책으로 시작합니다.

- `path`를 기본 식별자로 사용한다.
- `os.stat()`에서 얻을 수 있는 값을 `file_id` 후보로 저장한다.
- 파일 등록 시에는 해시를 즉시 계산하지 않는다.
- `파일 위치 갱신` 실행 시 활성 파일의 SHA-256 해시를 계산해 `nodes.file_hash`에 저장한다.
- `누락 찾기` 실행 시 사용자가 선택한 폴더 안에서 같은 해시 파일을 찾아 `MISSING` 노드의 경로를 복구한다.
- 100MB 초과 파일은 자동 해시 계산하지 않는다.
- `.git`, `.venv`, `venv`, `node_modules`, `__pycache__` 등은 누락 파일 재탐색에서 건너뛴다.

정식 Windows 추적은 이후 WinAPI 기반으로 보강합니다.

```text
결정:
- MVP에서는 WinAPI를 바로 쓰지 않는다.
- 파일 등록 시 해시는 즉시 계산하지 않는다.
- 파일 위치 갱신 시 활성 파일 해시를 저장한다.
- 누락 파일 복구는 현재 사용자가 선택한 폴더 안에서 해시가 일치하는 파일만 대상으로 한다.
- 100MB 초과 파일은 자동 해시 계산하지 않는다.
- MVP에서는 네트워크 드라이브를 공식 지원하지 않는다.
- 네트워크 경로는 등록은 허용하되, 자동 정리와 이동 추적은 제한한다.
```

## 7. 그래프 정책

관계 강도는 NetworkX weight로 변환합니다.

```text
HIGH: 3
MEDIUM: 2
LOW: 1
```

기본 배치는 `spring_layout`을 사용합니다.

- 수동 좌표가 없는 노드는 자동 배치한다.
- 수동 좌표가 있는 노드는 DB 좌표를 우선한다.
- 사용자가 노드를 드래그하면 `nodes.layout_x`, `nodes.layout_y`를 갱신한다.
- "자동 정렬" 기능은 전체 노드의 수동 좌표를 초기화하고 새 레이아웃을 저장한다.

포커스 뷰는 선택 노드 기준 n단계 관계를 보여줍니다.

- 기본값: 2단계
- 현재 구현은 NetworkX 그래프에서 n단계 노드를 계산한다.
- 대량 데이터 최적화가 필요해지면 DB 재귀 CTE를 검토한다.

```text
- 기본 포커스 단계 2(직접 연결된 것만 보이기)
- 자동 정렬이 전체 좌표를 지움
- 노드 크기는 폴더가 조금 더 크게
- 노드는 밝은 원형 배경 위에 `assets/*.svg` 아이콘을 표시
- 폴더는 `folder`, 파일은 확장자별 아이콘, 누락/권한 문제는 상태 아이콘을 우선 표시
- 폴더 노드는 우클릭 메뉴에서 `CONTAINS`로 연결된 파일 노드를 접거나 펼칠 수 있음
- 노드 라벨은 `폴더 이름만`, `파일 이름만`, `둘 다`, `마우스가 올라가면 보이기`로 설정 가능
- 타입별 라벨 표시 모드에서 기본 표시되지 않는 타입도 hover 시 이름을 표시한다.
- 간선 라벨은 `항상 보이기` 또는 `마우스가 올라가면 보이기`로 설정 가능
- 노드/간선 라벨 글자 크기는 설정 화면에서 조절 가능
- 자동 정렬 후 노드 간 최소 여백을 보정하고, 수동 드래그 드롭 직후 겹침을 완화한다.
```

현재 확장자 아이콘은 모든 확장자를 개별 아이콘으로 만들지 않고 용도별 SVG 묶음으로 매핑합니다.

- `pdf`: `.pdf`
- `doc`: `.doc`, `.docx`, `.hwp`, `.hwpx`, `.md`, `.odt`, `.rtf`, `.txt`
- `sheet`: `.csv`, `.ods`, `.tsv`, `.xls`, `.xlsx`
- `slide`: `.odp`, `.ppt`, `.pptx`
- `image`: `.bmp`, `.gif`, `.heic`, `.ico`, `.jpeg`, `.jpg`, `.png`, `.svg`, `.tif`, `.tiff`, `.webp`
- `audio`: `.aac`, `.flac`, `.m4a`, `.mp3`, `.ogg`, `.wav`, `.wma`
- `video`: `.avi`, `.flv`, `.mkv`, `.mov`, `.mp4`, `.mpeg`, `.mpg`, `.webm`, `.wmv`
- `archive`: `.7z`, `.bz2`, `.gz`, `.iso`, `.rar`, `.tar`, `.xz`, `.zip`
- `code`: `.c`, `.cc`, `.cpp`, `.cs`, `.css`, `.go`, `.h`, `.hpp`, `.html`, `.ipynb`, `.java`, `.js`, `.jsx`, `.kt`, `.kts`, `.php`, `.py`, `.rb`, `.rs`, `.scss`, `.sh`, `.swift`, `.ts`, `.tsx`, `.vue`
- `data`: `.ini`, `.json`, `.log`, `.toml`, `.xml`, `.yaml`, `.yml`
- `db`: `.db`, `.mdb`, `.sql`, `.sqlite`, `.sqlite3`
- `design`: `.ai`, `.blend`, `.fig`, `.indd`, `.psd`, `.sketch`, `.xd`
- `app`: `.apk`, `.app`, `.appimage`, `.bat`, `.cmd`, `.com`, `.deb`, `.dmg`, `.exe`, `.msi`, `.pkg`, `.ps1`, `.rpm`
- `file`: 위 매핑에 없는 파일의 기본 아이콘
- `folder`: 폴더 노드 아이콘
- `missing`, `access_denied`: 파일 상태 아이콘. 확장자 아이콘보다 우선 표시한다.

사용자 지정 확장자 아이콘 매핑은 설정 화면의 표에서 관리합니다.

- 확장자는 점(`.`)을 입력해도 저장 시 제거한다.
- 아이콘은 `file`, `doc`, `pdf`, `sheet`, `slide`, `image`, `audio`, `video`, `archive`, `code`, `data`, `db`, `design`, `app` 계열 중 선택한다.
- 사용자 지정 매핑은 기본 확장자 매핑보다 우선한다.
- 누락/접근 거부 상태 아이콘은 사용자 지정 확장자 매핑보다 우선한다.

## 8. UI 흐름

### 8.1 메인 화면

현재 메인 화면 구성:

- 그래프 뷰
- 오른쪽 작업 패널
- 작업 패널 상단의 `설정` 버튼으로 여는 별도 설정 화면
- 하단 상태 표시줄
- 작업 패널 주요 동작: 파일/폴더 추가, 검색, 보기 프리셋, 관계 추가, 새로고침, 파일 위치 갱신, 자동 정렬, 누락 파일 찾기, DB 가져오기, JSON/CSV 내보내기
- 작은 창 높이에서는 작업 패널 본문을 내부 스크롤로 탐색한다.
- 설정 화면 주요 동작: 무시 폴더 목록, 그래프 라벨 기본값, 노드 색상 선택기/미리보기/초기화, 강조 색상 슬롯 선택기, 확장자 아이콘 매핑

### 8.2 노드 추가

사용자는 파일 또는 폴더를 선택해 노드로 등록합니다.

MVP 입력값:

- 파일 또는 폴더 경로
- 노드 타입 자동 판별
- 이름 자동 추출

```text
결정:
- 파일 추가 방식은 버튼과 드래그 앤 드롭을 모두 지원한다.
- 폴더 추가 시 내부 파일 재귀 등록은 기본 ON으로 두고 사용자가 체크박스로 끌 수 있다.
- 폴더 추가 확인 창은 등록될 하위 폴더/파일 개수와 `CONTAINS` 관계 개수를 미리 보여준다.
- 내부 파일을 함께 등록하면 폴더-하위 폴더-파일 계층에 맞춰 `CONTAINS` 관계를 자동 생성한다.
- 노드의 고유성은 `path`를 기준으로 판단한다.
- 같은 `path`가 이미 등록되어 있으면 새 노드를 만들지 않는다.
- 서로 다른 경로가 같은 `(file_id, volume_serial)`을 가지면 두 경로를 별도 노드로 저장하고 비방향 `SAME_FILE(같은 파일)` 관계를 강도 `HIGH`로 자동 생성한다.
- 기존 DB의 `(file_id, volume_serial)` 고유 제약은 시작 시 제거하고 조회용 일반 인덱스로 마이그레이션한다.
- 중복 팝업에는 [기존 노드로 이동], [관계 추가하기], [취소]를 제공한다.
- [기존 노드로 이동]은 그래프에서 기존 노드를 포커스한다.
- [관계 추가하기]는 기존 노드를 선택 상태로 두고 관계 추가 흐름으로 이어간다.
- 같은 해시이지만 파일 ID가 다른 복사본은 자동으로 `같은 파일` 관계를 만들지 않으며 중복 후보 기능에서 별도로 다룬다.
```

### 8.3 관계 추가

사용자는 두 노드를 선택하고 관계를 등록합니다.

MVP 입력값:

- 출발 노드
- 도착 노드
- 관계 타입: 기본 프리셋 중 선택
- 방향성: 있음 또는 없음
- 관계 강도
- 설명: 선택 입력

구현 규칙:

```text
- 관계 타입 선택 UI에는 기본 프리셋만 보여준다.
- 사용자는 관계 타입 관리 화면이 추가된 이후 새 타입을 추가할 수 있다.
- MVP에서 기본 프리셋으로 표현하기 어려운 세부 의미는 설명 필드에 작성한다.
- 방향성이 있으면 그래프 간선에 화살표를 표시한다.
- 방향성이 없으면 화살표 없이 두 노드를 연결한다.
- 관계 타입마다 기본 방향성 값을 둘 수 있지만, 관계 생성 시 사용자가 바꿀 수 있다.
- 설명은 비워둘 수 있다.
```

### 8.4 그래프 상호작용

- 노드 드래그로 좌표를 저장한다.
- 노드 라벨은 설정에 따라 `폴더 이름만`, `파일 이름만`, `둘 다`, `마우스가 올라가면 보이기` 중 하나로 표시한다.
- 간선 라벨은 설정에 따라 항상 표시하거나 hover 시 표시한다.
- 오른쪽 드래그로 여러 노드를 선택할 수 있다.
- 선택된 여러 노드는 함께 이동하거나 일괄 삭제할 수 있다.
- `Ctrl+A`는 현재 그래프에 보이는 모든 노드를 선택한다.
- 노드 우클릭 메뉴는 열기, 관계 추가, 관계 수정, 접기/펼치기, 강조, 메모, 관계 색상, 삭제를 제공한다.
- `CONTAINS` 관계가 있는 폴더 노드의 우클릭 메뉴는 내부 파일 접기/펼치기를 제공한다.
- 폴더를 접으면 해당 폴더가 직접 포함하는 파일 노드와 그 파일에 연결된 화면상의 관계를 숨긴다.
- 접힌 폴더 노드는 점선 테두리, 다른 배경색, 포함 파일 개수 배지로 열린 폴더와 구분한다.
- 자신을 포함하는 상위 폴더가 없는 폴더 노드는 최상위 폴더 표시로 구분한다.
- 메모가 있는 노드는 우상단 점 표시를 띄우고, 선택 패널에는 메모 요약을 보여준다.
- 강조 색상이 지정된 노드는 파일/폴더 기본 색보다 강조 색을 우선 적용한다.
- 검색 결과와 포커스 뷰도 현재 접힌 폴더 상태를 렌더 데이터에 반영한다.
- 보기 프리셋은 `전체 보기`, `누락 파일만`, `강조 노드 주변`, `최근 추가`, `선택 폴더 아래`, `고립 노드`를 제공한다.
- `선택 폴더 아래` 프리셋은 선택된 폴더 노드에서 `CONTAINS` 관계를 재귀적으로 따라가며 하위 노드를 표시한다.

### 8.5 노드 열기

그래프에서 노드를 더블클릭하면 다음처럼 동작합니다.

- `FILE`: `os.startfile(path)`로 기본 연결 프로그램 실행
- `FOLDER`: `os.startfile(path)`로 Explorer에서 폴더 열기
- 현재 경로가 없으면 경고 표시

### 8.6 파일 위치 갱신과 누락 찾기

파일 위치 갱신:

- 앱 시작 시 전체 파일 위치 갱신을 즉시 실행하지 않는다.
- 사용자는 작업 패널의 `파일 위치 갱신` 버튼으로 수동 실행할 수 있다.
- `ACTIVE`: 현재 경로에 접근 가능
- `MISSING`: 현재 경로에서 파일 또는 폴더를 찾을 수 없음
- `ACCESS_DENIED`: 현재 경로는 있으나 권한 문제 등으로 접근 불가
- 활성 파일은 SHA-256 해시를 저장한다.
- 100MB 초과 파일은 자동 해시 계산에서 제외한다.
- 파일 위치 갱신은 진행 창에서 처리 개수와 현재 항목을 보여주고, 취소 요청 시 다음 항목부터 중단한다.

누락 찾기:

- 사용자가 검색할 폴더를 직접 선택한다.
- 저장된 `file_hash`가 있는 `MISSING` 파일 노드만 복구 후보로 본다.
- 선택 폴더 안에서 같은 해시 파일을 찾으면 기존 노드의 `path`, `file_id`, `volume_serial`, `last_seen`, `status`, `deleted_at`을 복구한다.
- 이미 다른 노드가 같은 경로를 사용 중이면 해당 후보는 건너뛴다.
- `.git`, `.venv`, `venv`, `node_modules`, `__pycache__` 등은 검색하지 않는다.
- 누락 찾기는 진행 창에서 검사 파일 수와 현재 항목을 보여주고, 취소 요청 시 검색을 중단한다.

## 9. 오류와 상태 정책

### 9.1 파일 삭제

파일이 사라졌을 때 DB 레코드를 바로 삭제하지 않습니다.

- `status = MISSING`
- `deleted_at = CURRENT_TIMESTAMP`
- 기존 관계는 유지한다.

사용자가 명시적으로 앱에서 삭제하면 `DELETED` 상태로 표시합니다.

결정:

```text
- `MISSING`은 파일 시스템에서 파일을 찾지 못한 상태다.
- `DELETED`는 사용자가 앱에서 명시적으로 삭제 처리한 상태다.
- `MISSING`은 관계와 노드 기록을 유지하고 그래프에서 누락 상태로 표시한다.
- `DELETED`도 기본적으로 soft delete로 처리하고 DB 레코드는 유지한다.
- 사용자가 "완전 삭제"를 명시적으로 선택한 경우에만 DB 레코드 삭제를 검토한다.
- `MISSING` 파일이 다시 발견되면 `path`, `file_id`, `volume_serial`, `last_seen`, `status`를 복구한다.
- 복구 시 `deleted_at`은 NULL로 되돌린다.
```

### 9.2 접근 거부

접근 권한 문제로 파일을 읽을 수 없으면 다음처럼 처리합니다.

- `status = ACCESS_DENIED`
- 그래프에서 권한 문제 표시
- 파일 내용 분석은 건너뛴다.

### 9.3 실시간 동기화

MVP에서는 watchdog 기반 실시간 감시를 넣지 않습니다.

- 앱 시작 시 전체 파일 위치 갱신은 즉시 실행하지 않음
- 사용자의 수동 `파일 위치 갱신`
- 사용자의 수동 `누락 찾기`
- 이후 버전에서 실시간 감시 검토

## 10. 설정과 보안

현재 설정 저장 항목:

- 그래프 라벨 글자 크기
- 노드 라벨 표시 방식
- 간선 라벨 표시 방식
- 무시 폴더 목록
- 파일/폴더 노드 기본 색상
- 강조 색상 슬롯
- 확장자 아이콘 사용자 지정 매핑
- 설정 화면 색상 선택기/미리보기와 파일/폴더/강조 슬롯 색상 기본값 초기화

보안 정책:

- 저장소에는 `config/README.md`만 두고 로컬 설정/비밀값 파일은 커밋하지 않는다.

결정:

```text
- UI/동작 설정은 SQLite `settings` 테이블에 저장한다.
- 확장자 아이콘 매핑, 노드 색상, 강조 색상 슬롯처럼 구조가 있는 설정은 JSON 문자열로 저장한다.
- 기본 색상 초기화는 저장 전 입력값만 기본값으로 되돌리며, 저장 버튼을 누르면 DB 설정에 반영한다.
```

## 11. 테스트 기준

현재 자동 테스트는 pytest 기반이며, DB/그래프/GUI/파일 무결성 흐름을 검증합니다. 2026-07-09 기준 전체 테스트는 132개입니다.

- DB 생성 테스트
- 노드 추가/수정/조회 테스트
- 관계 추가/수정/조회 테스트
- 관계 강도 weight 변환 테스트
- 수동 좌표 저장 테스트
- 검색 테스트
- 포커스 그래프 테스트
- 파일 상태 검사 테스트
- 해시 계산과 누락 파일 재탐색 테스트
- 폴더 내부 파일 등록과 `CONTAINS` 관계 자동 생성 테스트
- 폴더 내부 파일 접기/펼치기 테스트
- 라벨 표시 모드와 hover 표시 테스트
- 설정 화면과 확장자 아이콘 매핑 테스트
- 색상 선택기, 미리보기, 기본 색상 초기화 테스트
- 메모/강조/최상위 폴더 시각 표시 테스트
- 되돌리기와 검색 제안 테스트
- 보기 프리셋 필터 테스트
- DB 가져오기 검증과 교체 테스트
- 파일 상태 갱신 취소 콜백 테스트
- MainWindow/ControlPanel/GraphViewer GUI smoke 및 상호작용 테스트

파일 이동 기능이 들어간 뒤에는 임시 폴더 기반 테스트를 추가합니다.

- 이름 충돌 처리
- 중복 해시 처리
- MoveHistory 기록
- Undo 성공
- Undo 실패

결정:

```text
- 테스트 프레임워크는 pytest를 사용한다.
- 테스트 DB는 대부분 in-memory SQLite를 사용한다.
- 운영 DB(`db/database.db`)는 테스트에서 직접 사용하지 않는다.
- DB CRUD, relation_types, 관계 중복 처리, 검색, 좌표 저장, 파일 상태/해시 흐름은 자동 테스트로 검증한다.
- GUI 테스트는 실제 이벤트 루프를 장시간 실행하지 않고 offscreen smoke/interaction 수준으로 유지한다.
- Qt의 블로킹 메뉴/다이얼로그 호출은 테스트 가능한 wrapper 또는 monkeypatch 지점을 둔다.
```

## 12. 구현 우선순위

완료된 MVP 구현 순서:

1. `core/database_manager.py`
2. DB DDL과 CRUD
3. 실제 파일/폴더 선택 등록
4. `core/graph_manager.py`
5. NetworkX layout 계산
6. `gui/main_window.py`
7. `gui/graph_viewer.py`
8. 노드 드래그 좌표 저장
9. 관계 추가 UI
10. 검색과 포커스 뷰
11. 폴더 내부 파일 등록과 포함 관계 자동 생성
12. 파일 위치 갱신과 해시 기반 누락 파일 복구
13. 확장자/상태별 아이콘 표시
14. 폴더 내부 파일 접기/펼치기
15. 다중 노드 삭제 UX 보강
16. 폴더 등록 시 무시 폴더 정책과 설정 UI
17. 별도 설정 화면과 확장자 아이콘 설정 기반
18. 노드/간선 라벨 위치와 가독성 개선
19. 노드 겹침 방지 레이아웃 보정
20. 컨트롤 패널 액션 문구와 관계 확인 UI 개선
21. `Ctrl+A` 전체 선택 단축키
22. 상단 툴바 제거와 컨트롤 패널 중심 액션 정리
23. 색상 선택기, 미리보기, 기본 색상 초기화
24. 기본 보기 프리셋
25. DB 가져오기와 교체 전 자동 백업
26. 폴더 대량 추가, 파일 위치 갱신, 누락 파일 찾기 진행률/취소
27. 작은 창 높이에서 작업 패널 내부 스크롤

다음 우선순위:

1. 빌드 앱 기준 QA 보강
2. 관계 타입 관리 화면
3. 파일 이동 추적 정책 보강
4. scan_history 기록과 스캔 결과 화면
5. 대규모 DB 성능 QA와 렌더링 최적화
6. 장시간 작업의 부분 취소/롤백 정책 고도화

다음 변경 메모:

- 관계 타입 관리 화면을 추가한다. 관계 이름, 색상, 방향성 기본값, 표시 순서, 추천 관계 타입 등을 한 화면에서 관리하고, 현재 우클릭 관계 색상 변경 기능과 연결한다.
- 사용자 정의 보기/필터 프리셋을 저장/수정/삭제하는 관리 UI를 검토한다. 현재는 기본 프리셋만 제공한다.
- 고립 노드 정리 화면을 고도화한다. 현재 단축키로 고립 노드를 표시할 수 있으나, 관계 추가, 삭제, 강조, 메모 같은 정리 작업으로 이어지는 전용 화면이 필요하다.
- 중복/유사 파일 후보 화면을 고도화한다. 현재 후보 목록 확인은 가능하지만, 같은 이름, 같은 해시, 비슷한 경로, 같은 크기/수정일 등을 기준으로 묶고 병합/관계 추가/삭제 판단까지 이어지는 전용 화면이 필요하다.
- DB 가져오기는 현재 전체 DB 교체 방식이다. 이후에는 가져오기 전 비교, 병합, 선택 복구 UX를 별도 검토한다.
- 대량 작업 취소는 남은 항목 중단 방식이다. 이후에는 부분 취소 결과 화면, 롤백 선택, scan_history 연계를 검토한다.
- 등록된 노드/관계가 많은 상태에서 시작 시간, 메모리 사용량, 첫 화면 표시 시간을 측정하는 성능 QA 기준을 만든다. 저장 좌표 사용, 아이콘/SVG 캐시, 점진 렌더링을 추가 검토한다.
- 빈 화면 온보딩을 고도화한다. 현재 빈 그래프 문구는 제공하지만, `파일 추가`, `폴더 추가` 같은 실제 시작 액션을 그래프 영역에서 바로 실행할 수 있게 한다.

최근 반영한 변경 메모:

- 세로로 누적되던 파일 맥락·관계·후보 영역을 상세 탭으로 재구성해 작은 창에서 컨트롤 패널 하단이 잘리는 문제를 해결했다. 새 후보가 생기면 후보 탭으로 자동 전환한다.
- 등록 직후 새 파일만 자동 분석하고 후보 발견 개수를 표시하도록 폴더 등록 흐름과 탐지기를 연결했다.
- 동일 폴더·동일 stem의 편집 문서와 PDF를 수정 시각 근접도에 따라 `EXPORTED_AS` 후보로 제안하는 탐지기를 추가했다.
- 선택 파일에서 관계 의미와 방향을 따라 downstream 파일을 보여주는 `영향 보기`를 추가했다. 화면에서는 실제 장애 확정이 아닌 잠재 영향으로 표현한다.
- 제품 중심을 수동 그래프 작성에서 로컬 파일 관계·출처·의존성 추적으로 확장했다. 관계에 생성 출처, 신뢰도와 근거를 저장하고 실제 관계와 분리된 후보 승인·거절 흐름을 추가했다.
- 첫 설명 가능 탐지기로 Python 로컬 파일 참조 분석을 추가했다. 명시적인 읽기·쓰기 호출만 `READS`, `WRITES` 후보로 만들며 자동 확정하지 않는다.
- 오른쪽 패널을 파일 중심 맥락과 관계 후보 검토가 가능하도록 확장했다.
- `QLockFile` 기반 단일 인스턴스 잠금을 추가해 FileGraph 프로세스가 한 번에 하나만 실행되도록 했다.
- 서로 다른 경로가 동일한 실제 파일을 가리키는 하드 링크를 별도 노드로 허용하고 `같은 파일(SAME_FILE)` 관계를 자동 생성하도록 DB 제약과 마이그레이션을 변경했다.
- 작업 패널과 별도 설정 화면을 분리했다. 설정 화면에서 그래프 표시, 노드 색상, 강조 색상, 확장자 아이콘 매핑, 무시 폴더 설정을 관리한다.
- 노드 이름 표시 옵션은 `폴더 이름만`, `파일 이름만`, `둘 다`, `마우스가 올라가면 보이기`로 세분화했다. 타입별 표시 모드에서도 기본 표시되지 않는 타입은 hover 시 이름이 보인다.
- 노드 라벨 자동 줄바꿈은 파일명과 확장자가 중간에서 잘리지 않도록 개선했다. 확장자는 한 줄에 유지하고, 파일명 본문은 공백, 언더바, 대시 기준으로 줄바꿈한다.
- 확장자별 기본 아이콘 체계를 유지하면서 사용자 지정 확장자-아이콘 매핑을 설정 화면에서 등록/수정/삭제할 수 있게 했다.
- 자동 정렬과 검색 결과 배치가 과하게 멀어지지 않도록 레이아웃 scale과 fit 기준을 조정했다. 수동 드래그 드롭 직후에도 겹침을 완화한다.
- 접힌 폴더는 점선 테두리, 배경색, 포함 파일 개수 배지로 열린 폴더와 구분한다. 최상위 폴더는 별도 색상으로 구분한다.
- 검색 입력 시 매칭 후보 목록을 표시하고, 후보 선택 시 검색/포커스로 이어진다.
- 관계 추가/수정 드롭다운은 직접 상위 폴더 1개만 보조 텍스트로 보여준다.
- 파일 상태 갱신 계열 버튼 문구를 `파일 위치 갱신`으로 바꾸고, 전체 보기와 파일 위치 갱신의 의미를 분리했다.
- 폴더 추가 시 하위 파일 자동 등록을 기본 ON으로 바꾸고, 추가 전 폴더/파일/포함 관계 개수를 미리 보여준다.
- `Ctrl+F`, `Esc`, `Delete`, `Enter`, `Ctrl+L`, `Ctrl+R`, `Ctrl+Shift+R`, `F`, `Shift+F`, `Ctrl+N`, `Ctrl+Shift+N`, `Ctrl+Z` 등 단축키를 추가했다.
- `F1` 단축키 도움말과 `Ctrl+Shift+L` 범례를 추가했다.
- `Ctrl+Z`로 노드 삭제, 관계 삭제, 자동 정렬을 되돌릴 수 있게 했다.
- 관계 타입 색상, 파일/폴더 노드 색상, 강조 색상 슬롯을 설정/적용할 수 있게 했다.
- 설정 화면에 색상 선택기, 미리보기 칩, 파일/폴더/강조 슬롯 색상 기본값 초기화를 추가했다.
- 노드 메모 기능을 추가했다. 우클릭에서 메모를 편집하고, 메모가 있는 노드는 우상단 점 표시와 상세 패널 요약을 보여준다.
- 노드 우클릭 메뉴에 열기, 관계 추가, 접기/펼치기, 강조, 메모, 관계 색상, 삭제를 모았다.
- 작업 패널에 기본 보기 프리셋을 추가했다. `누락 파일만`, `강조 노드 주변`, `최근 추가`, `선택 폴더 아래`, `고립 노드`를 빠르게 적용한다.
- DB 백업, DB 가져오기, JSON/CSV 내보내기, 고립 노드 보기, 중복 후보 확인을 추가했다.
- 폴더 대량 추가는 GUI 스레드를 막지 않도록 백그라운드 worker로 분리하고 진행률/취소를 제공한다.
- 파일 위치 갱신과 누락 파일 찾기에 진행 창, 처리/검사 개수, 취소 버튼을 추가했다.
- 앱 시작 시 전체 파일 위치 갱신을 즉시 실행하지 않게 해 시작 자원 사용량을 줄였다.
- 작은 창 높이에서 작업 패널 본문이 내부 스크롤로 빠지도록 해 버튼과 관계 영역이 겹치지 않게 했다.
- 샘플 데이터 생성 버튼과 샘플 그래프 생성 경로를 제거해 첫 화면이 실제 파일/폴더 추가 흐름에 집중하도록 했다.
- 무시 폴더 이름과 같은 폴더를 직접 추가하거나 드래그한 경우에도 등록 계획에서 제외하도록 했다.
- 작업 패널에 JSON/CSV 내보내기 버튼을 노출하고 CSV 내보내기 단축키를 추가했다.
- 확장자 아이콘 매핑 표의 확장자 칸을 placeholder가 있는 입력칸으로 바꾸고 아이콘 콤보와 행 높이를 맞췄다.
- 작업 패널 내부에 남아 있던 미사용 설정 패널/신호를 제거하고 설정은 별도 설정 창으로 단일화했다.

## 13. 현재 기본 결정

이 섹션은 구현 중 흔들릴 수 있는 기준의 현재 기본값을 정리합니다.

```text
결정:
1. 첫 MVP는 실제 파일/폴더 선택 기능을 중심으로 제공하고 샘플 데이터 생성 기능은 제공하지 않는다.
2. 기본 관계 타입별 기본 방향성 값은 현재 추천값으로 시작한다.
3. 폴더 노드 등록 시 내부 파일 자동 노드화는 기본 ON으로 두고 사용자가 체크박스로 끌 수 있다. 선택 시 폴더에서 각 내부 파일/하위 폴더로 `CONTAINS` 관계를 자동 생성한다.
4. 폴더 노드의 내부 파일 접기/펼치기는 우클릭 컨텍스트 메뉴에서 제공한다.
5. 같은 파일이 여러 위치에 있으면 기본적으로 별도 노드로 본다. 단, `MISSING` 노드는 저장된 해시와 같은 파일을 사용자가 선택한 폴더 안에서 찾으면 기존 노드 경로를 복구할 수 있다.
```
