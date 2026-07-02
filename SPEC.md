# FileGraph SPEC

이 문서는 FileGraph를 실제로 구현하기 위한 작업용 사양서입니다. README는 제품 소개와 방향을 담고, 이 파일은 기술 스택, 구현 결정, DB 구조, 정책, 테스트 기준을 관리합니다.

## 문서 상태

- 상태: Draft
- 기준일: 2026-07-03
- 구현 상태: 수동 파일 관계 그래프 MVP 완료, 파일 상태 확인과 해시 기반 누락 파일 재탐색 구현
- 이후 범위: 관계 타입 관리, AI 관계 분석, AI 폴더 정리, 파일 이동 Undo

## 관련 문서

- [README.md](./README.md): 제품 소개, 핵심 아이디어, 현재 상태
- [USAGE.md](./USAGE.md): 실행 방법과 사용 흐름
- [requirements.txt](./requirements.txt): Python 의존성 목록

## 기술 스택

- Python 3.10+
- PySide6: Windows 데스크톱 GUI
- SQLite: 로컬 영속 저장소
- NetworkX: 그래프 구성과 레이아웃 계산
- pytest: 자동 테스트
- scikit-learn: 이후 로컬 TF-IDF 관계 추천 후보
- requests: 이후 외부 AI API 호출 후보
- keyring: 이후 사용자 API 키 저장 후보

## 현재 구현 모듈

- `main.py`: 런타임 경로 준비, DB 초기화, PySide6 앱 실행
- `core/database_manager.py`: SQLite 스키마, relation type seed, 노드/관계 CRUD, 검색, 설정, 좌표/상태/해시 저장
- `core/graph_manager.py`: NetworkX 그래프 생성, 관계 강도 weight 변환, 레이아웃 계산, 포커스 노드 추출
- `core/file_integrity.py`: 파일 상태 검사, SHA-256 해시 계산, 누락 파일 해시 기반 재탐색
- `core/ai_engine.py`: AI 기능 자리만 준비되어 있으며 아직 구현 전
- `gui/main_window.py`: 메인 윈도우, 툴바, 검색, 그래프/제어 패널 연결, 파일 상태 확인, 누락 찾기
- `gui/graph_viewer.py`: 그래프 렌더링, 확장자/상태별 SVG 아이콘 표시, 드래그, 선택, 라벨, 컨텍스트 메뉴, 드롭 처리
- `gui/control_panel.py`: 사이드 패널, 관계 목록, 포커스/전체 보기, 글자 크기, 상태 확인/누락 찾기 버튼
- `gui/relation_dialog.py`: 관계 추가/수정 다이얼로그
- `tests/`: DB, 그래프, GUI, 파일 무결성 자동 테스트

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

- AI 기능의 첫 출시 범위:

  ```text
  - AI 관계 추천
  - 이후 AI 폴더 정리
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

### Phase 1: 수동 그래프 MVP

이 단계는 AI 없이 동작해야 합니다. 현재 MVP 범위는 구현 완료 상태입니다.

- DB 생성 및 마이그레이션 기초
- 노드 CRUD
- 관계 CRUD
- 샘플 데이터 생성
- 그래프 레이아웃 계산
- PySide6 메인 윈도우
- 그래프 노드/간선 표시
- 노드 드래그 후 좌표 저장
- 노드 더블클릭으로 파일 또는 폴더 열기
- 파일명, 경로, 카테고리 검색

### Phase 2: 파일 무결성 및 복구

현재 일부 구현되어 있습니다.

- 앱 시작 시 `path` 존재 여부 검사
- 누락 파일을 `MISSING` 상태로 표시
- 접근 불가 파일을 `ACCESS_DENIED` 상태로 표시
- 활성 파일 SHA-256 해시 저장
- 사용자가 선택한 폴더 안에서 해시 기반 누락 파일 재탐색
- 수동 상태 확인

아직 남은 항목:

- 동일 드라이브 이동 파일 자동 추적
- 중복 해시 파일 통합 UX
- scan_history 기록
- 대량 스캔 진행률 표시
- 수동/자동 새로고침 정책 정리

### Phase 3: AI 관계 분석

- 사용자 API 키 입력
- keyring 저장
- 파일 본문 일부 추출
- Gemini API 요청
- AI 분석 실패 처리
- 로컬 TF-IDF 대안 분석
- AI가 만든 관계를 사용자가 수정할 수 있게 제공

### Phase 4: AI 폴더 정리

- 정리 대상 폴더 선택
- 위험 경로 블랙리스트 검사
- 정리 규칙 선택
- AI가 가상 폴더 구조 제안
- 사용자 최종 승인
- 실제 파일 이동
- MoveHistory 기록
- Undo

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
    settings.json
  db/
    database.db
    template_db.db
  core/
    __init__.py
    database_manager.py
    ai_engine.py
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

- DB: `%LOCALAPPDATA%/FileGraph/database.db`
- 설정: `%LOCALAPPDATA%/FileGraph/config/`
- 로그: `%LOCALAPPDATA%/FileGraph/logs/`

최초 실행 시 `db/template_db.db`가 존재하고 런타임 DB가 없다면 복사합니다.

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

created_by:
  USER
  AI

ai_status:
  PENDING
  SUCCESS
  FAILED
  SKIPPED
```

관계 타입은 고정 enum이 아니라 `relation_types` 테이블로 관리합니다. 앱은 기본 프리셋을 제공하고, 사용자는 새 관계 타입을 추가할 수 있습니다.

```text
기본 relation_types seed:
  RELATED        -> 관련 있음
  REFERENCE      -> 참고자료
  GENERATED_FROM -> 원본에서 생성됨
  CONTAINS       -> 포함
  VERSION_OF     -> 다른 버전

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
- `상태 확인` 실행 시 활성 파일의 SHA-256 해시를 계산해 `nodes.file_hash`에 저장한다.
- `누락 찾기` 실행 시 사용자가 선택한 폴더 안에서 같은 해시 파일을 찾아 `MISSING` 노드의 경로를 복구한다.
- 100MB 초과 파일은 자동 해시 계산하지 않는다.
- `.git`, `.venv`, `venv`, `node_modules`, `__pycache__` 등은 누락 파일 재탐색에서 건너뛴다.

정식 Windows 추적은 이후 WinAPI 기반으로 보강합니다.

```text
결정:
- MVP에서는 WinAPI를 바로 쓰지 않는다.
- 파일 등록 시 해시는 즉시 계산하지 않는다.
- 상태 확인 시 활성 파일 해시를 저장한다.
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
- "자동 정렬" 기능은 선택된 노드 또는 전체 노드의 수동 좌표를 초기화할 수 있다.

포커스 뷰는 선택 노드 기준 n단계 관계를 보여줍니다.

- 기본값: 2단계
- 대량 데이터에서는 DB 재귀 CTE로 대상 노드를 먼저 추출한다.

```text
- 기본 포커스 단계 2(직접 연결된 것만 보이기)
- 자동 정렬이 전체 좌표를 지움
- 노드 크기는 폴더가 조금 더 크게
- 노드는 밝은 원형 배경 위에 `assets/*.svg` 아이콘을 표시
- 폴더는 `folder`, 파일은 확장자별 아이콘, 누락/권한 문제는 상태 아이콘을 우선 표시
- 간선 라벨은 마우스가 위로 올라가면 표시
- 노드/간선 라벨 글자 크기는 UI에서 조절 가능
```

## 8. UI 흐름

### 8.1 메인 화면

MVP 메인 화면 구성 초안:

- 상단 툴바
- 검색 입력
- 그래프 뷰
- 오른쪽 속성/관계 패널
- 하단 상태 표시줄
- 사이드 패널 주요 동작: 관계 추가, 새로고침, 상태 확인, 샘플, 자동 정렬, 누락 찾기

### 8.2 노드 추가

사용자는 파일 또는 폴더를 선택해 노드로 등록합니다.

MVP 입력값:

- 파일 또는 폴더 경로
- 노드 타입 자동 판별
- 이름 자동 추출
- 카테고리 선택 입력은 선택 사항

```text
결정:
- 파일 추가 방식은 버튼과 드래그 앤 드롭을 모두 지원한다.
- 폴더 추가 시 내부 파일 재귀 등록 여부는 체크박스로 사용자가 선택한다.
- 내부 파일을 함께 등록하면 폴더 노드에서 각 파일 노드로 `CONTAINS` 관계를 자동 생성한다.
- MVP에서는 `path` 기준 중복만 검사한다.
- 같은 `path`가 이미 등록되어 있으면 새 노드를 만들지 않는다.
- 중복 팝업에는 [기존 노드로 이동], [관계 추가하기], [취소]를 제공한다.
- [기존 노드로 이동]은 그래프에서 기존 노드를 포커스한다.
- [관계 추가하기]는 기존 노드를 선택 상태로 두고 관계 추가 흐름으로 이어간다.
- `file_id`/`file_hash` 기반 중복 판단은 Phase 2 이후에 구현한다.
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

### 8.4 노드 열기

그래프에서 노드를 더블클릭하면 다음처럼 동작합니다.

- `FILE`: `os.startfile(path)`로 기본 연결 프로그램 실행
- `FOLDER`: Explorer에서 폴더 열기
- `MISSING`: 경고 표시
- `ACCESS_DENIED`: 권한 안내 표시

### 8.5 파일 상태 확인과 누락 찾기

상태 확인:

- 앱 시작 시 자동으로 한 번 실행한다.
- 사용자는 사이드 패널의 `상태 확인` 버튼으로 수동 실행할 수 있다.
- `ACTIVE`: 현재 경로에 접근 가능
- `MISSING`: 현재 경로에서 파일 또는 폴더를 찾을 수 없음
- `ACCESS_DENIED`: 현재 경로는 있으나 권한 문제 등으로 접근 불가
- 활성 파일은 SHA-256 해시를 저장한다.
- 100MB 초과 파일은 자동 해시 계산에서 제외한다.

누락 찾기:

- 사용자가 검색할 폴더를 직접 선택한다.
- 저장된 `file_hash`가 있는 `MISSING` 파일 노드만 복구 후보로 본다.
- 선택 폴더 안에서 같은 해시 파일을 찾으면 기존 노드의 `path`, `file_id`, `volume_serial`, `last_seen`, `status`, `deleted_at`을 복구한다.
- 이미 다른 노드가 같은 경로를 사용 중이면 해당 후보는 건너뛴다.
- `.git`, `.venv`, `venv`, `node_modules`, `__pycache__` 등은 검색하지 않는다.

## 9. AI 관계 분석 정책

AI 기능은 MVP 이후 단계입니다.

기본 방향:

- 사용자 개인 API 키를 사용한다.
- API 키는 `keyring`에 저장한다.
- `settings.json`에는 API 키 원문을 저장하지 않는다.
- 분석 전에 외부 전송 동의 팝업을 보여준다.

분석 대상:

- 텍스트 기반: `.txt`, `.md`, `.pdf`, `.docx`, `.xlsx`, `.pptx`
- 이미지 기반: `.jpg`, `.png` 등 OCR 가능한 포맷

분석 제외:

- 암호화된 문서
- 실행 파일
- 이진 라이브러리
- 영상 및 오디오
- 100MB 초과 파일

대용량 문서 처리:

- 10MB 이상 100MB 이하 문서는 전체 본문을 보내지 않는다.
- 앞부분 4,000자와 뒷부분 4,000자를 추출한다.

Rate Limit 대응:

- 여러 파일 메타데이터를 하나의 JSON 리스트로 묶어 배치 요청한다.
- 429 응답 시 지수 백오프를 적용한다.

오프라인 대안:

- `scikit-learn` 기반 TF-IDF
- cosine similarity 기준 관계 제안
- 80% 이상: `HIGH`
- 50% 이상 80% 미만: `MEDIUM`

결정:

```text
- Gemini 모델명은 `settings`에서 관리하고 코드에 하드코딩하지 않는다.
- 기본값은 구현 시점의 안정 Flash 계열 모델로 둔다.
- 운영 기본값에는 latest alias를 쓰지 않고 stable model string을 사용한다.
- AI 응답은 JSON으로 고정한다.
- AI 응답은 파일별 분석 결과와 관계 추천 결과를 분리한다.
- 잘못된 JSON이면 해당 배치는 실패 처리하고 재시도한다.
- AI는 기본적으로 기존 `relation_types` 중 하나를 선택한다.
- 애매하면 `RELATED`를 선택한다.
- AI가 새 관계 타입을 자동 생성하지 않는다.
- AI가 새 타입이 필요하다고 판단하면 제안만 하고, 사용자가 승인해야 `relation_types`에 추가한다.
- AI 분석 실패 시 노드는 삭제하지 않는다.
- 실패한 노드는 `ai_status = FAILED`로 저장하고 실패 사유를 보여준다.
- 사용자는 실패한 파일만 다시 분석할 수 있다.
- 실패한 파일도 수동 관계 등록은 가능하다.
- OCR은 MVP와 첫 AI 관계 추천 단계에서는 제외한다.
- OCR은 이미지/스캔 PDF 분석이 실제로 필요해진 뒤 별도 단계로 추가한다.
```

AI 응답 JSON 스키마 초안:

```json
{
  "nodes": [
    {
      "node_id": 1,
      "ai_status": "SUCCESS",
      "ai_context": "2026년 마케팅 캠페인 기획서",
      "ai_category": "마케팅"
    }
  ],
  "relations": [
    {
      "source_id": 2,
      "target_id": 1,
      "relation_type_code": "REFERENCE",
      "is_directional": true,
      "strength": "HIGH",
      "description": "발표자료가 기획서를 참고함",
      "confidence": 0.91
    }
  ],
  "warnings": []
}
```

## 10. AI 폴더 정리 정책

AI 폴더 정리는 MVP 이후 단계입니다.

사용자는 다음 규칙 중 하나를 선택합니다.

1. 업무 성격 중심

   ```text
   [대분류/부서] -> [상세 업무명] -> [연도]
   예: 마케팅 -> SNS_광고_집행 -> 2026
   ```

2. 시간 흐름 중심

   ```text
   [연도] -> [월] -> [프로젝트명]
   예: 2026 -> 06월 -> 외주_브랜딩디자인
   ```

3. 프로젝트/고객 중심

   ```text
   [프로젝트명/고객사] -> [산출물 종류] -> [확장자 그룹]
   예: A사_신제품런칭 -> 디자인소스 -> Images
   ```

4. 파일 포맷 중심

   ```text
   [확장자 그룹] -> [연도] -> [사용처]
   예: Videos -> 2026 -> 유튜브_업로드용
   ```

안전 정책:

- AI가 바로 파일을 옮기지 않는다.
- 먼저 가상 폴더 구조를 보여준다.
- 사용자가 승인해야 실제 이동한다.
- 정리 대상과 목적지는 모두 사용자가 선택한 작업 공간 폴더 내부여야 한다.
- 정리 실행 직전에 원본 경로와 목적지 경로를 절대경로로 해석한 뒤 작업 공간 밖으로 벗어나는지 검사한다.
- 경로 검증에 실패한 항목은 이동하지 않고 미리보기/결과 화면에 제외 사유를 표시한다.
- 목적지에 같은 이름이 있으면 `_1`, `_2`처럼 순차 번호를 붙인다.
- 같은 해시의 중복 파일은 이동을 건너뛰고 통합 여부를 묻는다.
- 모든 이동은 `move_history`에 기록한다.
- Undo 전 현재 경로 존재 여부와 해시를 검증한다.
- 이동 전 현재 DB를 백업한다.
- MVP에서는 같은 드라이브 안의 이동만 허용한다. 다른 드라이브로 옮기는 복사 후 삭제 방식은 이후 버전에서 구현한다.
- 한 번의 자동 정리 작업은 기본 500개 파일 이하로 제한한다. 500개를 넘으면 사용자에게 작업을 나누도록 안내한다.
- 이동 도중 실패가 발생해도 전체 앱을 중단하지 않고, 실패 항목을 기록한 뒤 나머지 이동을 계속할 수 있게 한다.

보호 경로 기본값:

```text
C:\Windows
C:\Program Files
C:\Program Files (x86)
C:\ProgramData
%APPDATA%
%LOCALAPPDATA%
드라이브 루트: C:\, D:\ 등
$Recycle.Bin
System Volume Information
WindowsApps
.git
.venv
venv
node_modules
__pycache__
```

Undo 정책:

- Undo는 `operation_id` 단위로 실행한다.
- Undo 전 `new_path`에 파일이 존재하는지 확인한다.
- 이동 당시 저장한 해시가 있으면 현재 해시와 비교한다.
- 해시가 다르면 자동 Undo를 막고 사용자 확인을 요구한다.
- `old_path`에 이미 같은 이름의 파일이 있으면 덮어쓰지 않고 복구 파일명에 `_restored_1` 같은 접미사를 붙인다.
- 일부 파일만 Undo에 실패하면 성공한 항목은 그대로 두고, 실패 항목과 실패 사유를 결과 화면에 표시한다.

나중에 조정 가능:

```text
- 사용자가 직접 규칙을 추가할 수 있게 할지
- 자동 정리 1회당 파일 수 제한을 500개로 유지할지
- 다른 드라이브 이동을 언제 지원할지
```

## 11. 오류와 상태 정책

### 11.1 파일 삭제

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

### 11.2 접근 거부

접근 권한 문제로 파일을 읽을 수 없으면 다음처럼 처리합니다.

- `status = ACCESS_DENIED`
- 그래프에서 권한 문제 표시
- 파일 내용 분석은 건너뛴다.

### 11.3 실시간 동기화

MVP에서는 watchdog 기반 실시간 감시를 넣지 않습니다.

- 앱 시작 시 무결성 검사 실행
- 사용자의 수동 `상태 확인`
- 사용자의 수동 `누락 찾기`
- 이후 버전에서 실시간 감시 검토

## 12. 설정과 보안

설정 저장 후보:

- 그래프 기본 포커스 단계
- 테마
- 마지막 작업 폴더
- AI 기능 사용 여부
- 최근 열었던 DB

보안 정책:

- API 키 원문은 `settings.json`에 저장하지 않는다.
- API 키는 `keyring`을 사용한다.
- 외부 AI 전송 전 사용자의 명시적 동의를 받는다.

결정:

```text
- `settings.json`에는 UI/동작 설정만 저장한다.
- API 키 원문은 `settings.json`에 저장하지 않는다.
- API 키는 `keyring`에 저장한다.
- keyring service name은 `FileGraph`로 둔다.
- keyring username은 `gemini_api_key`로 둔다.
- `settings.json` 저장 항목은 `workspace_root`, `theme`, `graph_focus_depth`, `ai_enabled`, `gemini_model`, `last_opened_at`로 시작한다.
- AI 전송 동의 문구는 아래 문장을 기본값으로 사용한다.
```

AI 전송 동의 문구:

```text
선택한 파일의 이름, 경로, 메타데이터 및 내용 일부가 사용자의 API 키를 통해 외부 AI 서버로 전송될 수 있습니다. 계속하려면 전송에 동의해 주세요.
```

## 13. 테스트 기준

현재 자동 테스트는 pytest 기반이며, DB/그래프/GUI/파일 무결성 흐름을 검증합니다.

- DB 생성 테스트
- 노드 추가/수정/조회 테스트
- 관계 추가/수정/조회 테스트
- 관계 강도 weight 변환 테스트
- 수동 좌표 저장 테스트
- 검색 테스트
- 포커스 그래프 테스트
- 파일 상태 검사 테스트
- 해시 계산과 누락 파일 재탐색 테스트
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

## 14. 구현 우선순위

완료된 MVP 구현 순서:

1. `core/database_manager.py`
2. DB DDL과 CRUD
3. 샘플 데이터 삽입 스크립트 또는 함수
4. `core/graph_manager.py`
5. NetworkX layout 계산
6. `gui/main_window.py`
7. `gui/graph_viewer.py`
8. 노드 드래그 좌표 저장
9. 관계 추가 UI
10. 검색과 포커스 뷰

다음 우선순위:

1. 관계 타입 관리 화면
2. 파일 이동 추적 정책 보강
3. scan_history 기록과 스캔 결과 화면
4. AI 관계 추천
5. AI 폴더 정리와 Undo

## 15. 현재 기본 결정

이 섹션은 구현 중 흔들릴 수 있는 기준의 현재 기본값을 정리합니다.

```text
결정:
1. 첫 MVP는 샘플 데이터 생성 기능과 실제 파일/폴더 선택 기능을 모두 제공한다.
2. 기본 관계 타입별 기본 방향성 값은 현재 추천값으로 시작한다.
3. 폴더 노드 등록 시 내부 파일 자동 노드화는 기본 OFF로 두고 사용자가 체크박스로 선택한다. 선택 시 폴더에서 각 내부 파일로 `CONTAINS` 관계를 자동 생성한다.
4. 같은 파일이 여러 위치에 있으면 기본적으로 별도 노드로 본다. 단, `MISSING` 노드는 저장된 해시와 같은 파일을 사용자가 선택한 폴더 안에서 찾으면 기존 노드 경로를 복구할 수 있다.
5. AI 기능은 사용자가 켜기 전까지 비활성화한다.
```
