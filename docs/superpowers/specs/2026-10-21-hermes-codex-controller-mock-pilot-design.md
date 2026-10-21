# Hermes–Codex–VPS Controller 모의 통합 설계

**날짜:** 2026-10-21
**상태:** DESIGN ONLY — 서면 검토 대기. 코드 구현, Hermes 설치, Codex 실행, 서비스 배포를 승인하지 않는다.
**저장소:** mingi201209-star/shorts-studio
**기준:** Draft PR #57 (head c145e07cbbbb3676a879844d97bd8fcd8fadeb04); 기존 설계 브랜치 design/always-on-asset-factory-20261020 (33b406ae); 기존 main fcd20fd.
**승인한 방향:** A — Hermes 감독자 + Codex 개발 작업자 + 기존 Controller 검증자를 **모의 작업**으로 먼저 연결한다.

## 1. 사용자 목표·비목표

Hermes는 어떤 개발 업무를 할지 계획하고 상태를 설명하는 최상위 감독자다. Codex는 명시적 허가를 받은 경우에만 깨끗한 임시 Git 작업 공간에서 제한된 스크래치 코딩을 한다. PR #57의 작업 관리자는 작업의 실질적인 ID, 중복 방지, 임대권, 증거 해시, 재시작 후 상태의 유일한 진실 공급원이다. 실제 렌더 품질은 향후 Shorts Studio 원래 QA가 판정하며 Hermes의 문장으로 통과시키지 않는다.

이번 파일럿의 성공은 다음을 뜻한다: 검증 가능한 mock 요청 세 건이 안전하게 제출되고, 중복 전송·실패·재시작을 견디며, 콘텐츠 바이트와 저장된 증거가 일치하고, 감독자가 그 결과를 정확히 보고한다. 실제 3D 모델이나 최종 Shorts 영상을 제작했다는 뜻은 아니다.

**이번에는 하지 않는다:** Hermes 설치/로그인/실행, Codex 실제 실행, systemd 설치·시작·enable, 새로운 서버·B2·API 구매, GitHub PR 병합, YouTube 업로드, render worker 연결, 24시간 무인 운전. 향후 별도 승인 없이는 실행하지 않는다. 1080×1920, 30fps, Cycles32, 900개 고유 원본 프레임, 영어 내레이션 및 기존 영상 QA 기준도 완화하지 않는다.

## 2. 검증된 제품 인터페이스

PR #57의 현 HEAD에서 확인한 구현:

- contracts.py: JobSpec에는 job_id, asset_id/version, 정확한 소문자 40자리 source_sha, 64자리 input_digest, stage, worker_kind, payload_json, max_attempts, budget_usd가 있다.
- queue.py: enqueue는 동일 job_id의 동일 계약을 한 번만 수용한다. 충돌은 거부한다. BEGIN IMMEDIATE와 lease/fencing을 사용하고, claim_next는 **worker_kind=mock**만 선택한다.
- runner.py: run_once는 MockWorker 이외를 거부하고 로컬 산출물 해시를 검증한 후에만 **completed_mock**을 기록한다. 이는 영상 QA PASS가 아니다.
- workers.py: CodexWorker는 기본 enabled=False이며 runner에 연결되어 있지 않다. 사용할 경우 헤드 SHA, 클린 worktree, 예상 변경 파일, 실제 테스트, 해시·diff, ignored 파일까지 감사한다.
- __main__.py: 기존 CLI는 init, enqueue-mock, step, serve, status, snapshot, recover뿐이다. Hermes 범용 입력 API는 아직 없다.
- database.py 및 recovery.py: Controller DB 상태는 SQLite WAL에 남는다. 불확실한 만료 작업은 차단한다. DB 복원 시 모든 외부·관리자 권한 SQLite 사용자까지 중단하는 것은 별도 운영 절차로 유지한다.
- PR #57 GitHub CI test와 render-smoke 성공은 **기존 테스트/Comet 회귀의 증거**이며 Hermes 통합의 검증은 아니다. PR은 Draft·미병합이므로 main에 코드가 있다고 가정하지 않는다.

Hermes 공식 문서에서 확인한 별도 기능: SQLite 영구 Kanban, 프로필, 역할별 작업 프로세스, Cron 및 gateway, openai-codex OAuth 공급자, 실행 승인과 격리 설정. **Hermes Kanban 완료는 Controller 영구 receipt와 동의어가 아니다.** Hermes 모델용 OAuth는 standalone Codex CLI의 인증과 독립적이며, 두 인증 저장소를 자동 공유·경쟁 갱신하지 않는다. Hermes는 관리형 Python 3.14 설치를 요구하므로 VPS 기본 Python 3.12 또는 기존 Studio venv에 덮어 설치하지 않는다.

공식 참고:
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/kanban.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/integrations/providers.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/security.md
- https://github.com/NousResearch/hermes-agent/blob/main/website/docs/getting-started/installation.md
- https://github.com/NousResearch/hermes-agent/blob/main/cli-config.yaml.example

## 3. 통합 방식 선택

- **기각 A — Hermes가 Controller SQLite를 직접 조작:** 상태 전이, fencing, 감사 로직과 기존 테스트를 우회한다.
- **기각 B — Hermes 임의 shell/webhook으로 실행:** 명령 주입·재전송·권한 경계·공개 네트워크 표면이 커진다.
- **채택 C — 비신뢰 JSON 제안 + 검증된 로컬 브리지 + 기존 mock-only queue:** 구현 범위와 권한을 작게 유지하고 오프라인 통합부터 증명할 수 있다.

권한 흐름:

    Hermes / Kanban
      └─ ProposedIntent (제안만; 비신뢰 데이터)
           └─ hermes_pilot_bridge (schema, SHA, 중복 검사, 별도 사용자 승인)
                ├─ Controller.enqueue(JobSpec(worker_kind=mock))
                │    └─ Controller.run_once(MockWorker)
                │          └─ LocalArtifactStore + verified completed_mock receipt
                └─ status/report read-only → Hermes에 안전한 enum과 증거만 반환

    CodexWorker scratch probe (기본 disabled, 별도 허가)
      └─ CodexProbeResult와 테스트 증거 (Controller 완료 상태와 혼동하지 않음)

**두 개의 큐를 중복 생산 스케줄러로 만들지 않는다.** Hermes Kanban은 계획·검토·보고의 상태를 가진다. Controller SQLite만 모의 작업 실행의 authoritative state다. 브리지의 데이터는 상관관계와 승인 증거다. Hermes의 자체 카드 상태가 done이라고 해도 Controller의 검증 결과가 없으면 사용자에게 "미검증"이라고 보고한다.

## 4. 경계 계약: ProposedIntent v1

로컬 파일/함수 경계로 전달하는 **최대 4KiB의 UTF-8 JSON**. 사전 정의된 키 이외는 모두 거부한다. 중복 JSON 키, NaN/Infinity, 제어 문자, 경로, 쉘 문자열, URL, 인증 토큰, 임의 Python 코드를 거부한다.

허용 필드:
- schema = "hermes-controller-pilot/v1" (정확히 일치)
- intent_id = 소문자 영숫자·하이픈으로 된 길이 8–64의 한 논리 요청 ID
- origin_task_id = Hermes Kanban 상관관계용 길이/문자 제한 문자열 (실행 권한 아님)
- source_sha = 정확히 40자리 소문자 hex; 현재 감사된 작업 checkout HEAD와 비교
- kind = "mock_proof" 외에는 불허
- requested_by = "hermes-proposal" 고정; 모델은 자신이 승인됐다고 표기할 수 없음
- payload = 빈 객체 {} 고정

브리지는 정렬된 키와 동일한 UTF-8 표현의 canonical JSON에서 **input_digest(SHA256)**를 계산한다. 모델이 전달한 digest는 채택하지 않는다. job_id는 "hp-" + canonical JSON SHA256 선두 40자리로 결정한다. 동일 intent_id+동일 digest의 재제출은 no-op, 동일 ID+다른 digest는 conflict로 차단한다.

Controller JobSpec으로 매핑할 때 asset_id="hermes-pilot", asset_version="v1", stage="mock-proof", worker_kind="mock", payload_json="{}", budget_usd="0", max_attempts=1로 강제한다. 브리지는 기존 JobSpec 생성자·queue.enqueue·MockWorker·LocalArtifactStore를 호출하며 SQL 내부 상태를 직접 조작하지 않는다.

**승인:** Hermes 요청만으로 enqueue 불가. 신뢰된 로컬 운영자 경로에서 intent_id+input_digest를 일회성 승인하고 내역을 기록한 경우만 제출한다. 사용자의 채팅 문장, Hermes의 카드 완료 여부, LLM이 만든 "승인됨" 필드는 인정하지 않는다. 승인·감사 기록은 fsync 및 원자적 보존을 사용하며 비밀값은 포함하지 않는다.

## 5. 단계별 동작과 진실 공급원

### P0: 완전 오프라인 모의 통합

FakeHermes → 비신뢰 ProposedIntent → FakeOwnerApproval(정확한 digest) → 브리지 validator → 기존 mock queue → MockWorker → 로컬 콘텐츠 SHA256 receipt → 브리지 read-only status → FakeHermes의 구조화된 보고.

P0에서 모의 Codex는 스크래치 테스트 결과 형식만 제공할 수 있으며, 실제 codex subprocess를 실행하지 않는다. completed_mock은 검증된 모의 바이트에만 부여되고 render_qa_pass, video_qa_pass, publish_ready는 모두 false 또는 not_evaluated다.

### P1: 실제 Hermes 연결 — 별도 설치/로그인/실행 승인 후

기존 VPS에 **별도 비root Unix UID·별도 홈/프로필**로 관리형 Hermes를 설치한다. Cron·gateway·Kanban dispatcher 자동 분배·로그인 가져오기·유료 API fallback은 기본 비활성화. 최초 시험은 한 사람이 보고 있는 유한한 단일 Hermes 세션이다. 모델 인증이 필요하면 사용자가 직접 로그인하고 auth.adopt_external_logins=false로 기존 ubuntu 사용자의 Codex CLI 인증과 격리한다. 구독 OAuth 성공이 무료 무제한 사용 보장은 아니다.

Hermes는 제안만 하고, 별도 운영자가 승인한 뒤 P0와 같은 브리지/큐를 거친다. Hermes 재시작 뒤에도 Controller receipt에서만 결과를 재구성한다. Telegram, 외부 Web UI, 공개 inbound port는 열지 않는다.

### P2: 실제 Codex 스크래치 한 건 — 별도 명시적 1회 실행 승인 후

CodexWorker.run의 enabled=False를 무인으로 켜지 않는다. 허가가 내려진 경우에만 기존 CLI 로그인 상태를 검증하고, 별도의 깨끗한 Git worktree에서 1개 작업을 최대 5분 동안 실행한다. 정확한 HEAD·허용 파일 집합·테스트·해시·ignored-file 변경 감사를 요구한다. 반환된 CodexProbeResult는 **독립적인 스크래치 근거**이지 Controller completed_mock 또는 native 영상 QA 증거가 아니다. 모델 한도/인증 실패는 blocked로 남고 다른 계정·유료 API로 자동 전환하지 않는다.

## 6. 보안, 비용, 자원 제한

- Hermes UID는 Controller SQLite/객체 디렉터리, GitHub 쓰기 자격증명, SSH 개인키, Shorts Studio 원본 디렉터리에 쓰기 권한이 없어야 한다. 스키마 승인 브리지가 유일한 작업 제출 입구다.
- Hermes의 위험 명령 승인 프롬프트는 보조 수단이다. 실제 제한은 OS ACL·별도 사용자·기존 AppArmor/Bwrap 격리·read-only worktree·엄격한 bridge 정책으로 강제한다. --yolo와 광범위한 영구 명령 허용은 금지한다.
- 외부 webhook·API 수신/공개 dashboard, 유료 API 키, Telegram 권한, GitHub push/merge, 파일 삭제/배포 권한을 연결하지 않는다. Hermes inference/OAuth를 위한 외부 통신은 **P1 별도 승인 이후**만 허용한다.
- mock 세션당 최대 3건, 작업자 동시성 1, Codex 프로세스는 P2 허가 전 0. 접수 큐 상한 20건, 요청 문서 4KiB. MemAvailable 1GiB 미만 경고·512MiB 미만 정지, 디스크 여유 15% 미만이면 신규 접수 중지. 기존 Controller의 10% 하한은 낮추지 않는다.
- 비용 허용: 이미 결제한 기존 VPS 외 **신규 지출 0달러**. 추가 서버/B2/모델 API/구독 변경 없음. 구독 한도 초과 시 작업을 보류한다.
- 모든 로그는 safe enum/짧은 SHA/숫자만 출력한다. 자격증명·사용자 메시지·프롬프트 원문·민감 파일 경로는 출력/업로드하지 않는다.

## 7. 장애와 복구의 불변조건

| 실패 | 올바른 결과 | 금지 |
| --- | --- | --- |
| 동일 Hermes 제안을 두 번 제출 | 기존 job_id 재조회, attempt 추가 없음 | 중복 실행 |
| 같은 intent_id에 다른 digest | conflict/rejected, 기존 데이터 보존 | 작업 덮어쓰기 |
| Hermes가 enqueue 직후 중단 | Controller DB의 실제 상태로 복구 | Hermes 기억만으로 성공 처리 |
| source_sha 변경 | 차단·운영자 확인 | 작업 대상 무단 변경 |
| Codex quota/auth 문제 | auth_or_quota_blocked, 보류 | 유료 API/타 계정 자동 사용 |
| 만료 lease·실행 상태 불명 | Controller reconciliation 후 blocked | 확인 없는 자동 재시도 |
| mock 결과 해시 불일치 | proof_not_verified, 성공 거부 | 영상 QA PASS로 승격 |
| 디스크·RAM 한도 초과 | 중단·상태 보존·보고 | 자동 구매·무단 삭제 |
| Hermes 명령 삽입·승인 사칭 | schema reject·감사 | 임의 shell 명령 실행 |
| DB 복구 필요 | 서비스와 외부 SQLite 클라이언트 중단, 검증된 snapshot 사용 | 열린 DB 강제 교체 |

브리지·Hermes에서 실패하더라도 Controller DB와 마지막 검증된 원본 아티팩트는 삭제하지 않는다. 미확인 외부 부작용이 있는 재시도는 인간 검토 전 금지한다.

## 8. 필수 검증과 수용 기준

구현 **이후** 자동 테스트에서 검증할 항목:

1. 스키마·canonical SHA·정확한 source_sha, 알 수 없는 필드·중복 키·주입·크기 제한.
2. 동일 요청 중복/내용 충돌; 승인 없는 enqueue 금지.
3. 모의 3건의 P0 종단간 처리, 정확한 receipt 해시, safe status 보고.
4. Hermes의 "완료" 또는 Codex 종료 코드 0만으로 Controller 완료/영상 QA 통과 불가.
5. 브리지 종료를 제출 직전·직후 강제하고 재시작해도 작업 중복 없음.
6. 인증/모델 한도, lease 만료, SHA drift, ignored 파일 수정, 디스크·메모리 경고가 fail-closed.
7. Hermes UID와 컨트롤러 UID 사이의 권한 분리를 OS 수준에서 실제 증명.
8. 기존 전체 pytest, Ruff, exact-HEAD GitHub test/render-smoke CI 게이트 유지.

P0 PASS: 세 모의 작업이 올바른 증거와 함께 완료되며 모든 거부 경로가 통과한다. 이것은 **AI나 영상 생산 성능 검증이 아니다**.
P1 PASS(별도 승인): 실제 Hermes의 요청과 보고 1건, 인위적 재시작 상태 재구성, 모델 사용량/CPU/RAM 기록, 신규 billable API 요청 0건.
P2 PASS(별도 승인): 정확히 한 번의 Codex scratch 수정, 지정 파일과 테스트/해시 일치, Hermes·Controller의 상태 혼동 없음.
24시간 soak는 Asset Factory Milestone D에서 추가 승인 후 실시한다.

## 9. 장래 구현 파일 분리 (현재 생성하지 않음)

- shorts_studio/asset_factory/integrations/hermes_pilot/contracts.py: 타입·schema·canonicalization.
- shorts_studio/asset_factory/integrations/hermes_pilot/bridge.py: 운영자 승인 검증, 기존 JobSpec/enqueue 호출, 재제출.
- shorts_studio/asset_factory/integrations/hermes_pilot/audit.py: 승인·correlation_id 매핑·원자적 감사.
- shorts_studio/asset_factory/integrations/hermes_pilot/report.py: Controller 증거에서 생성한 read-only 보고.
- tests/test_hermes_pilot_*.py: FakeHermes/FakeOwnerApproval/가짜 Codex·장애·권한·회귀.
- docs/operations/hermes-controller-pilot.md: 승인된 P1/P2 시험 시 수동 실행·중단·롤백 안내.

현 Controller 함수/스키마/임대 정책을 침범하는 새 자동 실행기나 임의 webhook은 만들지 않는다. PR #57은 별도 검토·미병합이므로 구현 계획을 세우기 직전 해당 HEAD와 CI, Factory PR 토폴로지를 재확인한다.

## 10. Superpowers 승인 단계

**지금 승인된 것: 이 서면 설계 문서를 별도 브랜치에 기록하고 검토를 요청하는 행위만.**

1. 사용자가 이 문서 자체를 읽고 승인하거나 수정을 요청한다.
2. 서면 승인 후 Superpowers writing-plans로 단계별 구현 계획을 별도 작성한다.
3. 구현 계획 검토·Native 또는 Subagent-driven 선택 승인 이후에야 isolated worktree에서 코드·테스트를 작성한다.
4. Hermes 설치/실제 OAuth 사용/P1 실행은 별도 승인.
5. 실제 Codex CLI 프로세스 실행/P2 시험도 별도 승인.
6. systemd 활성화·24시간 모의 운영·B2·렌더 워커·자동 배포·GitHub PR 병합·YouTube 업로드·추가 과금은 각각 새로운 명시적 승인 필요.

롤백 시 운영자 제어 프로세스를 중지하고 전용 시험 기록을 보존한다. 기존 main, PR #57 및 다른 Factory PR, 원본 모델과 검증된 DB를 삭제·변경하지 않는다.

## 11. 문서 검토 체크리스트

- [ ] Hermes는 감독자이고 Controller는 검증된 실행 상태의 단일 진실 공급원인가?
- [ ] CodexProbeResult와 completed_mock/영상 QA는 서로 다른 결과인가?
- [ ] 승인·원본 SHA·입력 digest·중복 방지가 불변조건인가?
- [ ] 미승인 로그인/설치/배포/과금/병합/업로드가 기술적으로 차단되는가?
- [ ] 파일럿 P0/P1/P2와 후속 24시간 soak가 구분되는가?
