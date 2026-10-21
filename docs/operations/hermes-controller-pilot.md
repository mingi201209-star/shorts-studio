# Hermes–Codex–VPS Controller: 모의 연동 운영 지침

**상태: P0 OFFLINE MOCK ONLY. 서비스/AI/렌더 프로덕션 준비 완료가 아님.**
설계: docs/superpowers/specs/2026-10-21-hermes-codex-controller-mock-pilot-design.md
계획: docs/superpowers/plans/2026-10-21-hermes-codex-controller-mock-pilot.md
코드 시작점: Draft PR #57, c145e07cbbbb3676a879844d97bd8fcd8fadeb04.
main, PR #51–57, 다른 worktree, 수동 영상 업로드 정책은 변경하지 않는다.

## P0 — 승인된 코드 구현 이후, 완전 오프라인 테스트

Hermes 프로세스를 켜거나 OAuth를 요청하지 않고, FakeHermes/FakeOwnerApproval만 사용한다.
VPS에서 이 브랜치가 검증된 다음 운영자가 단발성으로 다음 테스트를 돌릴 수 있다.
이 절차는 시스템 서비스 등록, 백그라운드 루프 또는 실제 Codex 실행이 아니다.

    python -m pytest -q tests/test_hermes_pilot_*.py tests/test_asset_controller_*.py
    ruff check shorts_studio/asset_factory tests/test_hermes_pilot_*.py tests/test_asset_controller_*.py
    python -m pytest -q

실제로 사용 중인 정확한 Git HEAD는 git rev-parse HEAD로 확인하고, CI도 반드시
동일 커밋에서 확인한다. .superpowers/sdd/ 실행 작업 기록은 git-ignored 상태로 유지한다.

P0 계약: Hermes 대신 비신뢰 JSON 제안만 전달, UTF-8 4KiB 상한, mock_proof만
허용, 정확한 SHA/해시와 운영자 capability 확인 후 enqueue. API와 외부 프로세스 없음.
Controller 실행 상태/receipt는 SQLite 단일 진실 공급원이며 Hermes Kanban 완료는 증거가 아니다.
3개의 서로 다른 mock intent → 개별 승인 → 기존 queue → MockWorker → 로컬 파일
SHA256 검증 → proof_verified_mock. 네 번째 제출은 거부한다.
현 구현에서는 **실험 전용 사설 감사 DB당 총 3개 제출** 한도이며, 재시험은 새로운
격리 디렉터리/데이터베이스를 만들어야 한다. 기존 실험 기록을 덮어쓰지 않는다.
새 제안은 승인·미승인 합계 20개까지 저장하며, 21번째 새 제안은 거부한다.
20개가 찬 뒤에도 기존 승인된 제안 하나를 Controller 큐로 이동하는 행위는
대기 슬롯을 비우므로 허용한다(단, 기존 3회 실행 상한과 자원 게이트 유지).
이미 submitted 상태인 작업이 Controller DB에서 사라졌다면 복원 과정에서
실행 여부가 불분명하므로 **자동 재제출하지 않고 검토 요청으로 차단**한다.
최초 감사 DB 스키마 생성은 단일 SQLite 트랜잭션으로 유지되어야 한다.

상태만 보고 완료를 인정하지 않는다. 반드시 Controller의 특정 job_id, source_sha,
input_digest, fencing_token, receipt, 실제 로컬 객체 바이트가 일치해야 한다.
시스템이 예외를 냈거나 blob이 누락되면 proof_not_verified/review_required/blocked다.
render_qa_pass, video_qa_pass, publish_ready는 항상 false다.
이 파일럿은 실제 3D, 고유 900원본 프레임, Cycles32, TTS, 자막의 품질을 검증하지 않는다.

## 재전송·중단·복구

같은 intent_id의 동일 canonical hash는 한번만 큐에 넣고, 내용이 달라지면
감사 원본을 보존한 채 충돌로 막는다. 데이터베이스 커밋 이후 브리지 감사 저장 전에
종료되면, Controller JobSpec의 **모든 불변 필드**가 일치하는지 조회해 상태를
재구성한다. 일치하지 않거나 불분명하면 자동 재전송/외부 결제 시도를 하지 않는다.

Controller 만료 lease는 기존 recovery API를 통해 unknown이면 blocked로 둔다.
실제 external worker 상태를 추측하거나 Hermes 텍스트 보고만으로 완료하지 않는다.
파일 소실·SHA 충돌·디스크 부족은 중단하고 원래 기록과 last-good blob을 보존한다.
운영자가 확인하기 전에는 SQL 수동 상태 변경, 강제 retry, 자료 삭제를 하지 않는다.

감사 DB는 운영자 소유 0700 디렉터리 내 0600 파일에 저장한다. P0의 Python
OperatorAuthority 객체는 **시험 환경의 타입/제어흐름 경계일 뿐 실제 OS 권한분리
증거가 아니다.** untrusted Hermes 프로세스가 같은 UID, 같은 Python 프로세스 또는
Controller DB 쓰기 권한을 갖는다면 안전 경계는 무너진다. 실제 UID/ACL 증명은
P1 승인 후 필수이며, 현재 **UNVERIFIED**로 보고한다.

운영 중 임시/private DB에 WAL 및 sidecar가 생성될 수 있다. 복원 시 모든 DB
프로세스와 외부 관리자 권한 SQLite 클라이언트를 종료하고, checksum 검증 및
운영자 동의 후 원래 Controller 절차만 따른다. P0는 기존 Controller DB를 복원하지 않는다.

## P1 — 별도 승인 전 실행 금지: 실제 Hermes 감독자 연결

**Hermes 설치, 로그인, 실제 모델 이용, 권한·네트워크 변경은 별도 승인 필요.**
기존 VPS의 개발용 ubuntu 사용자/SSH 키/Codex 토큰/Shorts Studio 원본을 공유하지 않고
Hermes 전용 비root Unix UID·개인 홈·독립 관리형 Python 3.14 환경을 사용한다.
진짜 Hermes UID가 Controller DB/객체/감사 승인·GitHub 쓰기 권한/SSH 개인키에
쓰기 불가능함을 OS 그룹·ACL/UID 테스트로 증명해야 한다.

Hermes 전용 설정에서 auth.adopt_external_logins=false, Cron·gateway·Kanban
자동 디스패치, 유료 API fallback, 임의 브라우저·네트워크 서버·Telegram 연동은
기본 금지한다. 공개 포트 개방·백그라운드 systemd 활성화·자동 에이전트 확대는 금지.
필요한 한 번의 OAuth 로그인은 사용자가 직접 동의할 때만 진행한다.
ChatGPT Plus/Codex 인증을 쓸 수 있어도 호출 무제한이나 API 비용 0을
보증하지 않는다. 인증 만료/사용량 소진 시 fail closed 및 보류한다.
P1 최소 시험은 **유한한 수동 Hermes 요청 1건**, 재시작 상태 재구성,
CPU/RAM/디스크·과금 확인이며 성공이라도 프로덕션 적용을 의미하지 않는다.

## P2 — 별도 승인 전 실행 금지: 실제 Codex 스크래치

**실제 Codex CLI 실행은 P1이나 P0 성공으로 자동 허가되지 않는다.**
정확히 1건, 최대 5분, 1개 동시 프로세스, 예상 수정 파일/테스트 경로 지정,
정확한 Git HEAD, 깨끗한 독립 임시 worktree, AppArmor/Bwrap 보호, exit-code
이외 독립 파일·diff·test 검증을 유지한다. CodexWorker.run의 enabled=False는
기본값이며 파일럿 브리지에서 호출하지 않는다.
CodexProbeResult의 success도 Controller completed_mock 또는 영상 QA PASS가 아니다.
임시 결과가 이상하거나 quota/auth 실패 시 유료 API/다른 사용자 계정으로
자동 전환하지 않는다. 로그인 파일을 Hermes와 Codex 간에 복사하지 않는다.

## 자원·예산·긴급 중단

동시 mock 작업자 1, 실제 Codex 프로세스 0, P0 총 제출 3, pending 20,
제안 문서 <=4KiB. RAM MemAvailable <1GiB 경고, <512MiB 신규 작업 차단.
디스크 사용 가능 비율 <15%면 bridge 수락 중단(기존 Controller의 10% 하한 불변).
측정값 누락·무효, 등록되지 않은 worker, 비허용 shell 명령은 거부한다.
기존 VPS 비용 외 신규 과금 0달러, B2·GPU·렌더 서버·유튜브 업로드·PR 병합 없음.

중단/롤백은 특정 파일럿 프로세스부터 정상 종료, 감사 DB/Controller DB와
검증된 객체·마지막 정상 소스 SHA를 **보존**하고 손상된 작업만 격리한다.
기존 자료를 git clean -fdx, rm -rf 등으로 무단 삭제하지 않는다.
Hermes OS UID 분리·서비스 설치·24시간 가동은 향후 별도 안전 검토 대상이다.
24시간 soak는 원래 Asset Factory Milestone D이며 이 파일럿에 포함되지 않는다.
