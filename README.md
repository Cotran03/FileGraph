# FileGraph

## 물리적인 폴더 구조에 종속되지 않고, 파일-파일 / 파일-폴더 / 폴더-폴더 간의 논리적 연관 관계를 직접 등록하고 이를 그래프(노드와 간선) 형태로 시각화하여 관리하는 툴이다.

# 핵심 기능

## 그래프로 관계를 시각화

- **사용자가 직접 관계 등록**: 두 가지(혹은 그 이상)의 파일이나 폴더(이하 파일)를 선택하고 관계명을 등록한다. 이때 파일간의 상관관계 정도를 상/중/하 3단계로 설정하여 등록한다. 등록된 파일은 그래프에서 상관관계에 따라 선의 굵기나 길이 등으로 구분된다. 관계명은 간선 위에 표시한다.
- **AI를 통한 관계 등록**: AI를 활용하여 파일의 내용을 분석한 후, 상관관계까지 모두 자동으로 그래프에 등록된다. 사용자는 얼마든지 이를 직접 수정할 수 있다. 분석에 실패한 파일은 별도로 표시한다.
- **그래프 표시**: 상관관계에 따라 강한 상관관계일수록 더 가깝게, 약한 상관관계일수록 더 멀리 연결한다. 단, 사용자가 직접 노드를 드래그하여 수동 배치한 경우 해당 좌표(layout_x, layout_y)를 DB에 영속적으로 저장하고 자동 배치보다 최우선하여 렌더링한다. 사용자는 정렬 기능을 통해 기본 자동 배치 레이아웃으로 돌아갈 수 있다.
- **포커스 및 검색 뷰**: 사용자가 어느 한 노드를 선택하거나 검색 창을 통해 파일명/경로/카테고리를 검색하여 노드를 선택하면, 해당 노드에 포커스를 고정하고 화면을 해당 위치로 자동 이동(MoveTo)시킨다. 선택된 노드를 중심으로 직접 연결된 노드만을 표시하고 나머지 노드는 숨긴다. 이 단계 n은 사용자가 기본 설정값(Default: 2단계)을 조절하여 원한다면 그 이상으로도 표시가 가능하게 하며, 데이터 부하를 줄이기 위해 DB의 재귀 쿼리(Recursive CTE)를 통해 노드를 추출한다. 사용자는 그래프 위 파일을 더블클릭함으로써 실행할 수 있다.

# 부가 기능

## AI를 기반으로 한 폴더 정리

- **AI를 통한 폴더 정리**: AI를 통해 지정한 톨더 내 파일들 내용을 분석하고, 사용자가 지정한 규칙에 따라 정리한다.
- **사용자 지정 규칙**: 다음과 같은 4가지 규칙 중에 선택한다.
  1. 업무 성격 중심 순서: \[대분류/부서\] -> \[상세 업무명\] -> \[연도\]
     - 예시: 마케팅 -> SNS*광고*집행 -> 2026

  2. 시간 흐름 중심 순서: \[연도\] -> \[월\] -> \[프로젝트명\]
     - 예시: 2026 -> 06월 -> 외주\_브랜딩디자인

  3. 프로젝트/고객 중심 순서: \[프로젝트명/고객사\] -> \[산출물 종류\] -> \[확장자 그룹\]
     - 예시: A사\_신제품런칭 -> 디자인소스 -> Images

  4. 파일 포맷 중심 순서: \[확장자 그룹\] -> \[연도\] -> \[사용처\]
     - 예시: Videos -> 2026 -> 유튜브\_업로드용
  - 정리 예외 및 충돌 방지 정책 (안전장치):
    - 파일명 중복 처리: AI 폴더 정리 중 목적지 폴더에 동일한 이름의 파일이 이미 존재할 경우, 기존 파일을 덮어쓰지 않고 파일명 뒤에 순차적 일련번호를 부여한다. (예: 보고서.pdf ➔ 보고서\_1.pdf)

    - 중복 파일 처리: 파일명은 다르더라도 내용(SHA-256 해시)이 완벽히 일치하는 중복 파일은 이동을 건너뛰고 기존 노드와 통합할지 유저에게 확인 팝업을 띄운다.

    - 실행 취소(Undo) 지원: 유저 승인 후 폴더 정리가 실행될 때마다 모든 이동 이력을 MoveHistory 테이블에 기록하며, 유저가 잘못 정리했다고 판단할 경우 \[되돌리기\] 버튼을 통해 파일들을 이전 경로로 즉시 원상복구(Undo)할 수 있도록 한다. 단, Undo를 실행하기 전 현재 경로(new_path)에 파일이 실제로 존재하는지, 그사이 파일 내용이 수정되었는지 검증한 후 복구를 진행한다.

사용자는 이 4가지 규칙 중 하나를 선택한 후, AI가 이를 기반으로 하여 폴더를 정리하게 한다. AI는 폴더 구조를 바로 정리하지 않고, 사용자에게 우선 가상의 구조를 보여준 후 사용자의 최종 승인 후 그에 맞게 변경한다. 이때 Program files나 Appdata같은 시스템적인 파일들은 정리하지 못하게 미리 블랙리스트를 등록하여 둔다. 또한 AI가 내용 분석을 하면서 컴퓨터나 다른 파일에 해가 될 수 있다고 판단되는 경우 경고를 띄우고 정리하지 않는다.

# 데이터베이스

## 1. 노드 테이블 (Nodes)

- 파일과 폴더의 기본 정보 및 AI 분석 결과를 담는 핵심 테이블
  | 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
  |:-----:|:----------:|:---------:|:---:|
  | node_id | INTEGER | PRIMARY KEY AUTOINCREMENT | DB 고유 일련번호 |
  | file_id | TEXT | NOT NULL | Windows File ID (st_ino)를 TEXT로 저장 |
  | volume_serial | TEXT | NOT NULL | 하드디스크 볼륨 고유 시리얼 번호 |
  | node_type| TEXT | CHECK(...) | FILE 또는 FOLDER 구분 |
  | status | TEXT | CHECK(...) | ACTIVE, MISSING, DELETED, ACCESS_DENIED |
  | name | TEXT | NOT NULL | 파일명 또는 폴더명 |
  | path | TEXT | NOT NULL | 현재 디바이스 상의 절대경로 |
  | file_hash | TEXT | NULLABLE (INDEX 처리) | SHA-256 해시 (UNIQUE 제거, 동일파일 다중위치 저장 허용) |
  | layout_x | REAL | DEFAULT NULL | 유저가 드래그한 X 좌표 |
  | layout_y | REAL | DEFAULT NULL | 유저가 드래그한 Y 좌표 |
  | ai_status | TEXT | CHECK(...) | PENDING, SUCCESS, FAILED (AI 분석 상태 관리) |
  | ai_context | TEXT | | AI가 분석한 파일의 맥락/사용처 (분석 실패 시 NULL) |
  | ai_category | TEXT | | AI가 분석한 업무/대분류 (분석 실패 시 NULL) |
  | last_seen | DATETIME | | 마지막으로 파일 존재를 확인한 시간 |
  | deleted_at | DATETIME | DEFAULT NULL | 파일이 삭제(MISSING)된 시간 기록 |

## 2. 관계 테이블 (Relations)

- 사용자가 직접 등록한 노드 간의 링크 지도
  | 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
  |:-----:|:----------:|:---------:|:---:|
  | relation_id | INTEGER | PRIMARY KEY AUTOINCREMENT | 관계 고유 일련번호 |
  | relation_type | TEXT | CHECK(...) | CONTAINS, REFERENCE, GENERATED_FROM, RELATED |
  | source_id | INTEGER | FOREIGN KEY | 출발지 노드 ID (Nodes.node_id) |
  | target_id | INTEGER | FOREIGN KEY | 목적지 노드 ID (Nodes.node_id) |
  | strength | TEXT | CHECK(...) | 관계 강도 (상, 중, 하) |
  | created_by | TEXT | CHECK(...) | USER, AI (관계 등록 주체 구분) |
  | description | TEXT | | 관계 메모 (예: "참고 자료", "영수증") |
  | created_at | DATETIME | | 관계 등록일 |

## 3. 드라이브 추적 헬퍼 테이블 (DriveMap)

- 드라이브 간 이동으로 File ID가 바뀐 파일들을 매핑하기 위한 백업 테이블
  | 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
  |:-----:|:----------:|:---------:|:---:|
  | old_file_id | TEXT | NOT NULL | 바뀌기 전 과거 Windows File ID |
  | old_volume_serial | TEXT | NOT NULL | 과거 파일이 존재했던 드라이브 볼륨 시리얼 |
  | new_file_id | TEXT | | 이동 후 새로 발급된 Windows File ID |
  | new_volume_serial | TEXT | | 이동 후의 현재 드라이브 볼륨 시리얼 |
  | file_hash | TEXT | NOT NULL | 추적용 SHA-256 해시값 (PRIMARY KEY: old_file_id, old_volume_serial) |

## 4. 자동 폴더 정리 히스토리 테이블 (MoveHistory)

- 폴더 정리 일괄 취소(Undo)를 구현하기 위한 이동 로그 테이블
  | 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
  |:-----:|:----------:|:---------:|:---:|
  | history_id | INTEGER | PRIMARY KEY AUTOINCREMENT | 히스토리 고유 번호 |
  | operation_id | TEXT | NOT NULL | 일괄 정리 작업을 묶어주는 ID (예: 20260629_001) |
  | node_id | INTEGER | FOREIGN KEY | Nodes.node_id |
  | old_path | TEXT | NOT NULL | 이동 전 절대경로 |
  | new_path | TEXT | NOT NULL | 이동 후 절대경로 |
  | moved_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 파일 이동 시간 |

## 5. 앱 환경설정 테이블 (Settings)

- 사용자의 앱 설정 값을 키-값 형태로 저장하는 테이블
  | 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
  |:-----:|:----------:|:---------:|:---:|
  | key | TEXT | PRIMARY KEY | 설정 항목 키 |
  | value | TEXT | | 설정 값 |
  | updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 최종 수정 시간 |

## 6. 무결성 스캔 기록 테이블 (ScanHistory)

- 백그라운드 스캔 성능 최적화 및 디버깅용 기록 테이블
  | 컬럼명 | 데이터 타입 | 제약 조건 | 설명 |
  |:-----:|:----------:|:---------:|:---:|
  | scan_id | INTEGER | PRIMARY KEY AUTOINCREMENT | 스캔 고유 번호 |
  | started_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | 스캔 시작 시간 |
  | finished_at | DATETIME | | 스캔 종료 시간 |
  | total_files | INTEGER | DEFAULT 0 | 총 검사 파일 수 |
  | changed_files | INTEGER | DEFAULT 0 | 변경 발견 파일 수 |

# 사용 기술 스택

- Language: Python 3.10+
- GUI Framework: PySide6(Qt for Python)
  - 그래픽 엔진: QGraphicsView, QGraphicsScene, QGraphicsItem (성능 및 줌/팬/드래그 조작 전용)
- Database: sqlite3
- Graph Mathematics: NetworkX
  - 역할: 노드의 초기 물리적 배치 좌표(Spring Layout 등) 계산 및 n단계 연쇄 연결 추적 알고리즘 처리
- AI/LLM API: Google Gemini API (Gemini 1.5 Flash / Pro)
  - 역할: 파일 본문 텍스트 임베딩/요약 및 폴더 분류/네이밍 태깅
- API 관리 정책: BYOK (Bring Your Own Key) 방식 채택. 사용자 개인 API 키를 입력받아 운영 환경 비용 제로화.
- 보안 기술: Windows 자격 증명(Credential Manager) 연동을 위한 Python keyring 라이브러리 사용.
- OS Interactivity: Python 표준 라이브러리 (os, shutil, hashlib, subprocess)

# 앱 핵심 흐름

1. 앱 구동 및 데이터 치유(Healing) 흐름
   1. DB 로드: SQLite DB를 연결하고 기존 Nodes 리스트를 가져옵니다.
   2. 무결성 검사: os.path.exists(path)로 파일들이 제자리에 있는지 전수 조사합니다.
   3. 위치 보정: \* 파일이 없다면 컴퓨터 내 지정된 작업 공간을 스캔하여 File ID가 일치하는 녀석을 찾습니다(동일 드라이브 이동). 찾으면 DB path 업데이트.
      - File ID로도 못 찾으면 file_hash를 대조하여 찾습니다(타 드라이브 이동). 찾으면 DriveMap을 거쳐 새 node_id 발급 및 Relations 테이블의 ID값들을 일괄 갱신합니다.
   4. 그래프 렌더링: 4. 그래프 렌더링: 치유가 완료된 데이터로 전체 인덱스 지도를 그리며 앱을 시작한다. 이때, NetworkX의 spring_layout 연산 시 Relations.strength 값을 가중치(weight) 정보로 변환하여 적용한다. (가중치 기준: 상=3, 중=2, 하=1로 설정하여 상에 가까울수록 노드 간 거리를 좁게 배치한다.)
   5. 파일/폴더 더블클릭 오퍼레이션: 유저가 그래프 상의 노드를 더블클릭할 시 node_type에 따라 분기 처리를 실행한다. FILE 타입은 os.startfile(path)을 통해 윈도우 기본 연결 프로그램으로 실행하고, FOLDER 타입은 explorer.exe를 호출하여 해당 폴더 창을 활성화한다.

2. AI 자동 폴더 정리 흐름
   1. 유저 프리셋 선택: 유저가 UI에서 4가지 규칙 중 하나를 선택하고 [정리 시작]을 누릅니다.
   2. 시스템 보호 스캔: 선택한 대상 폴더 내에 시스템 폴더(블랙리스트)나 해킹/악성코드로 의심되는 위험 파일이 있는지 백엔드 필터가 검사합니다. 위험 감지 시 경고 팝업 후 중단합니다.
   3. 가상 구조 제안(Preview): AI 분석 값(ai_context, ai_category)과 파일 생성 연도를 조합하여 가상의 폴더 트리 구조(Tree View)를 화면에 띄웁니다.
   4. 최종 승인 및 이동: 유저가 수락하면 shutil.move()로 실제 디스크 상에서 파일을 이동시키고, 동시에 DB의 path와 변경된 File ID를 실시간 갱신한 뒤 그래프를 리로드합니다.

# 예외 처리 및 정책

1. 파일 탐색기와의 실시간 동기화 제약
   - 상황: 프로그램이 켜져 있는 동안 사용자가 윈도우 탐색기에서 파일을 마음대로 지우거나 옮기면 프로그램 내 그래프와 엇박자가 납니다.
   - 대응: 파일 시스템 이벤트 폭발 및 내부 DB 동기화 교착 상태를 방지하기 위해, watchdog 기반의 실시간 감시 기능은 MVP 이후 버전에서 지원하는 것으로 완화한다. MVP 단계에서는 앱 구동 시 실행되는 ScanHistory 기반의 무결성 검사 및 수동 \[새로고침\] 기능을 기본 동기화 정책으로 채택한다.

2. 동일 드라이브 내 대용량 파일 이동 시 예외 처리
   - 상황: 드라이브 간 이동(C: ➔ D:) 시 파일 크기가 몇십 GB라면 파일을 복사하고 지우는 데 시간이 오래 걸려 앱이 멈춘 것처럼 보일 수 있습니다.
   - 대응: 파일 이동 로직은 반드시 QThread를 활용해 비동기로 처리하며, UI에 프로그레스 바(Progress Bar)를 띄워 현재 정리가 몇 % 진행 중인지 표시합니다.

3. AI 분석 실패 노드 처리 정책
   - 상황: 암호가 걸린 문서, 텍스트 추출이 불가능한 깨진 파일 등은 AI 분석이 실패합니다.
   - 대응: 이 노드들은 Nodes 테이블의 ai_context에 FAILED라는 값을 넣고, 그래프 상에서 흑백이나 경고 아이콘으로 표시하여 유저가 수동으로 관계를 맺도록 유도합니다.

4. 파일 분석 지원 범위 및 보안 제약
   - 분석 대상 및 방법 규칙:
     - 텍스트 기반 (.txt, .md, .pdf, .docx, .xlsx, .pptx 등): 본문 텍스트 추출 및 분석을 수행하되, 100MB 초과 대용량 파일은 제외한다.
     - 이미지 기반 (.jpg, .png 등): OCR 지원 포맷에 한해 텍스트를 추출하여 분석한다.
     - 분석 제외 대상: 암호화된 문서, 실행 파일 및 이진 파일(.exe, .dll, .sys 등), 영상/오디오 매체 파일 종류는 내용 분석에서 제외한다.
   - AI 전송 알림: AI 분석을 시작하기 전, "사용자 API 키를 통해 파일 내용 일부가 외부 AI 서버로 전송됩니다"라는 명시적 동기 부여 팝업을 노출한다.

5. 파일 삭제 및 권한 거부 상태 관리 Policy
   - 논리적 삭제(Soft Delete): 사용자가 실제 윈도우 탐색기에서 파일을 삭제한 경우, DB에서 해당 레코드를 즉시 DELETE하지 않고 `status` 값을 'MISSING' 또는 'DELETED'로 변경한다. 이를 통해 그동안 누적된 관계 기록(Relations)을 보존하며, 파일이 다시 복구되면 원래 관계를 즉시 재활성화한다.
   - 접근 권한 거부: 관리자 권한이 필요하거나 타 사용자의 폴더 제한으로 접근이 막힐 경우, 노드 상태를 'ACCESS_DENIED'로 마크하고 그래프 상에서 자물쇠 아이콘 등으로 시각적 경고를 표시한다.

# \[추가\] 데이터 무결성 및 충돌 정책

1. 파일 이름 충돌 방지: 자동 폴더 정리 중 목적지에 동일 이름의 파일이 존재할 경우, 원본을 덮어쓰지 않고 파일명 뒤에 순차적 일련번호(예: 파일명\_1.ext)를 부여한다.
2. 중복 파일(동일 해시) 처리: 파일 경로와 이름은 다르나 SHA-256 해시가 완벽히 일치하는 파일은 이동을 건너뛰고 기존 노드와 통합을 유저에게 제안한다.
3. 드라이브 간 고유 ID 충돌 방지: node_id는 DB 고유 일련번호(AUTOINCREMENT)로 변경하고, Windows File ID(st_ino)와 볼륨 문자를 조합하여 복합 식별자로 관리한다.

# \[추가\] UI 레이아웃 영속성 정책

1. 사용자 지정 좌표 기억: 유저가 그래프 상에서 노드를 드래그하여 이동시키면, 해당 노드의 X, Y 좌표를 Nodes 테이블의 layout_x, layout_y 컬럼에 실시간 기록한다.
2. 렌더링 우선순위: 앱 구동 및 새로고침 시, 사용자 지정 좌표 값이 존재하는 노드는 NetworkX의 자동 배치 알고리즘 연산에서 제외하고 해당 좌표에 고정 배치한다.

# AI 한계 완화 및 대안 처리 정책 (Hybrid Engine)

AI API 호출의 물리적 제약(Rate Limit, 토큰 한계, 대용량 처리 지연)을 극복하고 안정적인 구동을 보장하기 위해 다음과 같은 완화 기술 및 로컬 대안 처리를 적용한다.

1. API 반복 요청 거절(Rate Limit) 완화 정책
    - 청크(Chunk) 단위 배치 처리: 파일을 하나씩 개별 API로 호출하지 않고, 여러 파일의 메타데이터(파일명, 절대경로, 확장자, 텍스트 요약본)를 하나의 JSON 구조 리스트로 묶어 단 한 번의 프롬프트 쿼리로 전송함으로써 분당 요청 수(RPM)를 최소화한다.
    - 지수 백오프(Exponential Backoff) 재시도 루프: API 서버가 `429 Too Many Requests` 에러를 반환할 경우, 작업을 실패 처리하지 않고 백그라운드 스큐(`QThread`) 내에서 대기 시간을 두 배씩 늘려가며(1초 ➔ 2초 ➔ 4초 ➔ 8초) 재시도 메커니즘을 구동한다.

2. 대용량 파일 분석 및 토큰 절약 정책 (Smart Slicing)
    - 스마트 텍스트 슬라이싱(Head-Tail Extraction): 10MB~100MB 사이의 문서 파일은 전체 본문을 전달하지 않는다. 문서의 주요 문맥이 집중된 헤더(앞부분 4,000자)와 테일(뒷부분 4,000자) 영역만 파이썬 백엔드에서 잘라내어(Slicing) 프롬프트에 동봉함으로써 분당 토큰 제한(TPM) 부하를 방지한다.

3. 오프라인 및 로컬 대안 처리 알고리즘 (비-AI 룰 엔진 가동)
    - 로컬 텍스트 유사도 매핑 (TF-IDF): 사용자의 인터넷 연결이 끊겼거나 API 키가 유효하지 않을 경우, 로컬 텍스트 연산 라이브러리(`scikit-learn`)를 기반으로 문서 간 '코사인 유사도(Cosine Similarity)'를 연산하여 관계를 자동 생성한다. (유사도 80% 이상: 관계 강도 '상' / 유사도 50~80%: 관계 강도 '중')
    - 형태소/키워드 기반 로컬 분류 규칙: AI 분류가 불가능한 환경에서는 한국어 명사 추출기 또는 정규표현식(Regex) 규칙 알고리즘을 사용한다. 파일명 내 텍스트 분리 문자(`,`, `_`, 공백) 및 본문 내 최다 빈출 핵심 키워드를 자동 매칭하여 폴더 분류 및 네이밍 구조를 완성한다.

# 프로젝트 데이터 및 소스코드 폴더 구조

본 프로그램은 배포 및 유지보수의 편리성을 극대화하고, Windows 시스템의 'Program Files' 내 쓰기 권한 제한(Access Denied) 문제를 완벽하게 우회하기 위해 **실행 소스코드 디렉터리**와 사용자별 **런타임 데이터 디렉터리**를 분리하여 운영한다.

## 1. 애플리케이션 설치 및 소스코드 구조 (Development & App Directory)
- 본 구조는 개발 환경의 프로젝트 루트이며, 배포 시 `C:\Program Files\FileGraph\` 내에 읽기 전용으로 설치되는 뼈대이다.
- 개발 환경의 최상위 루트에는 진입 스크립트와 의존성 파일만 남기고, 모든 기능 코드는 하위 폴더로 격리한다.

FileGraph_Dev/                      # 프로젝트 최상위 루트 폴더
 ├ .venv/                           # [가상환경] 외부 라이브러리 패키지 독립 격리 폴더
 ├ .vscode/                         # [IDE 설정] 작업 영역 전용 VS Code 환경 제어 폴더
 │   └ settings.json                # 가상환경 파이썬 인터프리터 경로 및 자동 포맷 규칙 지정
 ├ .gitignore                       # Git 버전 관리 대상 제외 명세 파일
 ├ requirements.txt                 # PySide6, networkx, scikit-learn 등 외부 의존성 목록
 ├ main.py                          # 애플리케이션 진입점(Entry Point). 환경 초기화 및 메인 루프 실행
 ├ config/                          # 사용자의 앱 환경설정 데이터 격리 폴더
 │   └ settings.json                # API Key, 다크모드 등 계층형 구조 파싱용 JSON 설정 파일
 ├ db/                              # 데이터베이스 엔진 관련 파일 격리 폴더
 │   ├ database.db                  # [개발용] 디버깅 및 런타임 읽기/쓰기가 수행되는 로컬 DB 파일
 │   └ template_db.db               # 최초 실행 시 환경 구축을 위해 사용되는 원본 마스터 공백 DB
 ├ core/                            # 백엔드 핵심 비즈니스 로직 연산 기능 폴더
 │   ├ __init__.py                  
 │   ├ database_manager.py          # SQLite DB 커넥션 관리 및 노드/관계 CRUD 쿼리 제어 모듈
 │   ├ ai_engine.py                 # Gemini API(청크/슬라이싱) 및 오프라인 TF-IDF 대안 알고리즘 구현 모듈
 │   └ graph_manager.py             # NetworkX를 통한 가중치 좌표 연산 및 n단계 탐색 로직 처리 모듈
 ├ gui/                             # PySide6(Qt) 프레임워크 기반 레이어 폴더
 │   ├ __init__.py                  
 │   ├ main_window.py               # 상단바, 검색창, 핵심 레이아웃 프레임을 총괄하는 메인 윈도우 UI
 │   ├ graph_viewer.py              # QGraphicsView 기반 노드 드래그, 팬/줌 및 간선 실시간 렌더링 UI
 │   ├ control_panel.py             # AI 폴더 정리 규칙 프리셋 제어 및 수동 관계 수정을 지시하는 UI
 │   └ components/                  # 알림 팝업, 셋업 위젯, 프로그레스 바 등 공통 UI 컴포넌트 모음
 ├ resources/                       # 앱 아이콘 및 GUI 그래픽 요소 보관용 읽기 전용 폴더
 └ logs/                            # 시스템 트래킹 및 오류 추적용 폴더
     └ app.log                      # [개발용] 실시간 디버깅 텍스트 로그 파일


## 2. 로컬 시스템 데이터 폴더 구조 (Runtime Data Directory)
- 소스코드 컴파일 및 빌드 이후, 실제 프로그램 동작(Runtime) 중에 수정·변경·추가되는 모든 영속성 파일은 Windows 가 사용자별 자유 쓰기 권한을 완벽히 보장하는 환경변수 경로(`%LOCALAPPDATA%/FileGraph/`) 내에 실시간 격리 저장된다.
- 프로그램 구동 시 최초 1회 자가 진단을 수행하여 해당 경로 내 자원이 누락되었을 경우, App Directory의 원본 템플릿 파일들을 복사(`shutil.copy`)하여 유저 런타임 환경을 안전하게 구성한다.

%LOCALAPPDATA%/FileGraph/
 ├ database.db                      # 실시간 유저 데이터 변동 사항이 무결하게 반영되는 메인 SQLite3 파일
 ├ config/                          # 사용자 고유 API Key 및 커스텀 암호화 자격 증명 설정 보관 폴더
 ├ logs/                            # 백그라운드 스캔 이력 및 디스크 오퍼레이션 로깅 파일 보관 폴더 (app.log)
 └ backup/                          # 일괄 자동 폴더 정리 및 스캔 무결성 검사 직전 자동 덤프되는 DB 백업 폴더