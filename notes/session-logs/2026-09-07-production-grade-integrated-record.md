# Production-Grade 통합 실행·감사·수정·회귀 기록

## 기록 정보

- 작업일: 2026-09-07
- 저장소: `/Users/gimjunseong/Downloads/2ndbrainforsocialscience-main`
- 기준 프롬프트: Production-Grade Obsidian Research Second Brain 실행·감사·디버깅·보안 수정·회귀검증 통합 프롬프트
- 작업 목적: React/TypeScript + FastAPI 전환 상태를 실제 실행하고, 연구 무결성·파일시스템·업로드·기존 테스트 전체를 통합 검증
- 기록 성격: 실행 근거가 있는 정리본. 추정과 미검증 영역을 별도로 표시

## 최종 상태

```text
COMPLETED
- Repository discovery
- Architecture reconstruction
- Dependency/install verification
- Baseline build and full test run
- Runtime defect reproduction
- Minimal safe fixes
- Targeted regression tests
- Full regression and build verification
- FastAPI boot and React browser smoke test
- English audit report and change ledger

REMAINING / NOT VERIFIED
- Live LLM provider calls with user credentials
- Real Zotero synchronization
- Real user Obsidian vault mutation
- Production vector store and embedding lifecycle
- Runtime research agents
- Full crash-recovery transaction across Markdown, graph, memory, and cache
- Concurrent writers and Windows-specific filesystem behavior
```

## 실행 구조 확인

현재 기본 실행 경로는 다음과 같다.

```text
main.py
  -> FastAPI api.app
  -> api.runtime.WebAnalysisRuntime
  -> core.analysis_pipeline.AnalysisPipeline
  -> security / parser / bounded RAG / local or provider analysis
  -> LLM-output gate
  -> epistemic and provenance envelope
  -> cognitive engines
  -> optional Obsidian Markdown save
  -> graph / memory / cache / integrity state
  -> React result and runtime events
```

React 개발 실행은 `npm run dev`이며, Vite는 `127.0.0.1:5173`, FastAPI는 `127.0.0.1:8000`에서 실행된다. PyQt는 기본 `requirements.txt`와 웹 런타임에 포함되지 않으며, 기존 `ui/`와 `core/worker.py`는 선택적 호환 레거시 코드로 남아 있다.

## 기준선

코드 수정 전 기준선은 다음과 같다.

| 검사 | 기준선 결과 |
|---|---|
| `npm ci --ignore-scripts --no-audit --no-fund` | PASS |
| `python3 -m pip check` | PASS |
| `npm audit --omit=dev --audit-level=high` | PASS, 0 vulnerabilities |
| `npm run build` | PASS |
| `python3 -m pytest -q` | 337 passed, 6 warnings |
| 애플리케이션 부트 | FastAPI/Vite 수동 smoke PASS |

## 실제로 재현한 결함

### FIX-001 — 볼트 경계 밖 저장

- 파일: `core/obsidian_sync.py`
- 심각도: P0/P1 경계 위험
- 재현: `topic_override="../../escaped"`로 임시 볼트 밖에 Markdown이 실제 생성됨
- 원인: 사용자 입력 topic을 vault 경로에 직접 결합하고 symlink 경계를 검증하지 않음
- 수정: 단일 경로 구성요소 검증, `resolve()` containment 검사, symlink 거부, 백업 디렉터리 경계 검사
- 검증: `test_topic_override_cannot_escape_vault`, `test_symlinked_topic_root_cannot_escape_vault`
- 상태: RUNTIME VERIFIED

### FIX-002 — 원자적 교체 실패 시 원본 보호

- 파일: `core/obsidian_sync.py`
- 심각도: P1 데이터 무결성
- 원인: 기존 직접 쓰기 fallback이 부분 파일을 만들 수 있었음
- 수정: 같은 디렉터리의 임시 파일에 write/flush/fsync 후 `os.replace`; 실패 시 원본 유지
- 검증: `test_failed_atomic_replace_preserves_existing_note`
- 상태: RUNTIME VERIFIED

### FIX-003 — multipart 업로드 필드 손실

- 파일: `api/app.py`, `frontend/src/api.ts`
- 심각도: P1 기능 오류
- 재현: 브라우저가 FormData로 보낸 `title`, `input_type`, `model`이 FastAPI plain parameter 선언 때문에 무시됨
- 원인: FastAPI form fields가 `Form(...)`으로 선언되지 않음
- 수정: 모든 multipart 필드를 `Form(...)`으로 바인딩하고 `topic_override`도 전달
- 검증: `test_file_upload_honors_multipart_analysis_fields`
- 상태: RUNTIME VERIFIED

### FIX-004 — 업로드 무제한 메모리 읽기

- 파일: `api/app.py`
- 심각도: P1 신뢰성/DoS 위험
- 원인: `await file.read()` 한 번으로 전체 업로드를 메모리에 적재
- 수정: 1 MiB chunk 스트리밍, 허용 확장자 목록, 50 MiB 상한, 임시 파일 정리
- 검증: `test_file_upload_rejects_oversized_payload`, `test_file_upload_rejects_unsupported_extension`
- 상태: RUNTIME VERIFIED

### FIX-005 — 제목 개행을 통한 frontmatter 위조

- 파일: `core/analysis_pipeline.py`, `core/utils/markdown_utils.py`, `api/runtime.py`
- 심각도: P1 연구 무결성
- 재현: 제목에 개행을 넣어 `human_verified: true` 필드를 생성
- 원인: 메타데이터 정화 전 local demo frontmatter 문자열 보간과 ad hoc YAML 파싱
- 수정: 메타데이터 보안 검증, 구조화된 `yaml.safe_load/safe_dump`, `ai_generated: true`, `human_verified: false`, `evidence_status: AI_INTERPRETED`, `citation_status: NOT_VERIFIED`, provenance envelope 강제
- 검증: `test_pipeline_sanitizes_title_and_forces_epistemic_state`, 웹 smoke 출력 확인
- 상태: RUNTIME VERIFIED

### FIX-006 — 캐시 결과 자동 저장 누락

- 파일: `core/analysis_pipeline.py`
- 심각도: P1 기능/지속성
- 재현: 캐시 hit + `auto_save=True`에서 성공 응답은 왔지만 Markdown 파일이 생성되지 않음
- 원인: 캐시 분기가 저장 경로보다 먼저 반환
- 수정: 캐시 결과도 공용 `_save_output` 계약을 통과하고, 저장 실패를 `Err`로 전파
- 검증: `test_pipeline_cached_result_honors_auto_save`, `test_pipeline_save_failure_prevents_graph_mutation`
- 상태: RUNTIME VERIFIED

## 연구 무결성 판단

| 질문 | 현재 판단 |
|---|---|
| 중요한 결과를 원본 입력으로 추적할 수 있는가 | 생성 Markdown의 source type/ref와 provenance는 기록됨. claim/page 단위는 PARTIALLY VERIFIED |
| source, AI 해석, synthesis, human judgment가 구분되는가 | 생성 결과에 AI/human/evidence/citation 상태를 강제. 공용 파이프라인은 RUNTIME VERIFIED |
| 상충 연구가 조용히 덮어써지지 않는가 | contradiction 엔진과 scientific context가 존재하고 테스트됨. 전체 cross-paper lifecycle은 PARTIALLY VERIFIED |
| literature에서 synthesis/hypothesis로 추적 가능한가 | note evolution/lineage 구성요소는 존재. full golden workflow는 NOT VERIFIED |
| derived index 삭제 후 canonical knowledge를 보존할 수 있는가 | graph/cache는 derived로 분리됨. 전체 rebuild command는 NOT VERIFIED |
| provider 교체가 domain model 변경을 요구하는가 | provider boundary가 분리됨. live multi-provider 실행은 NOT VERIFIED |
| 악성 문서가 임의 파일을 쓸 수 있는가 | 입력/출력 gate와 vault containment가 적용됨. race condition은 NOT VERIFIED |

## 외부 참고 비교

외부 프로젝트는 코드를 복사하지 않고 architecture inspiration과 공개 문서만 비교했다.

- Karpathy LLM Wiki 계열은 `raw/`를 immutable source로 두고 `wiki/`, index, append-only log를 축적하는 구조를 명시한다. 현재 저장소의 Markdown/provenance envelope와 방향이 맞지만 raw/wiki 폴더를 완전히 동일하게 복제하지는 않았다.
- `eugeniughelbur/obsidian-second-brain`은 여러 명령·Agent Skills·vault MCP를 통해 AI-first vault workflow를 제공한다. 현재 저장소는 자체 연구 ontology와 FastAPI boundary를 유지하고, 해당 프로젝트의 코드를 가져오지 않았다.
- Khoj는 Obsidian plugin에서 주기 sync, force sync, search, similar notes를 제공한다. 현재 저장소의 RAG는 local bounded retrieval이며 Khoj 기능을 구현했다고 주장하지 않는다.
- Smart Connections는 local-first embedding과 관련 노트 탐색을 강조한다. 현재 저장소에는 실제 vector store/embedding lifecycle이 없으므로 이 기능은 roadmap으로 기록했다.

참고 링크: [Karpathy LLM Wiki](https://github.com/Astro-Han/karpathy-llm-wiki/blob/main/SKILL.md), [obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain/blob/main/README.md), [Khoj Obsidian client](https://github.com/khoj-ai/khoj/blob/master/documentation/docs/clients/obsidian.md), [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections)

## 기존 테스트 통합 목록

`pytest.ini`가 `tests/`를 testpath로 지정하므로 아래 21개 파일이 자동 수집된다. 파일별 수는 `pytest --collect-only -q` 결과다.

| 테스트 파일 | 수집 수 | 검증 범위 |
|---|---:|---|
| `tests/test_analysis_pipeline.py` | 7 | 보안 게이트, output gate, cache/save, provenance |
| `tests/test_config_reliability.py` | 3 | config atomicity/quarantine |
| `tests/test_document_intelligence.py` | 52 | document intelligence, language, layout, OCR interfaces |
| `tests/test_document_pipeline.py` | 67 | validator, identifier, parser, cleaner, storage, recovery |
| `tests/test_graph_integrity_transactions.py` | 2 | graph transaction rollback |
| `tests/test_input_file_support.py` | 4 | Markdown/SRT/VTT/TSV/audio gates |
| `tests/test_main_window_startup.py` | 1 | optional legacy PyQt startup |
| `tests/test_model_presets.py` | 4 | provider/model preset policy |
| `tests/test_performance_hot_paths.py` | 9 | cache, bounded scans, dedup, context bounds |
| `tests/test_phase1_hardening.py` | 24 | security/persistence hardening and optional worker |
| `tests/test_phase2_secure.py` | 19 | output boundary, parser gates, backup, vault security |
| `tests/test_phase3_correct.py` | 15 | safe mode, stream guard, RAG, lineage, lifecycle |
| `tests/test_phase4_refactor.py` | 42 | refactor contracts, provider profiles, migration |
| `tests/test_professor_workflow.py` | 6 | professor input readiness and UI defaults |
| `tests/test_rag_retrieval_bounds.py` | 2 | retrieval file/count bounds |
| `tests/test_ros_engine_contracts.py` | 5 | provider validation and graph extraction |
| `tests/test_scientific_context.py` | 36 | literature providers, evidence, provenance, scientific graph |
| `tests/test_semantic_knowledge_graph.py` | 4 | typed graph nodes/edges/idempotency |
| `tests/test_system_integrity_verifier.py` | 2 | report generation contract |
| `tests/test_v8.py` | 35 | legacy broad regression, Obsidian, security, integration |
| `tests/test_web_api.py` | 5 | FastAPI health/demo/upload contract |
| `tests/test_worker_semantic_graph.py` | 2 | optional legacy worker graph events |
| 합계 | **346** | **전체 회귀 실행** |

저장소 루트의 `test_worker_semantic_graph.py`는 `tests/test_worker_semantic_graph.py`와 중복되는 레거시 파일이며 `pytest.ini` 범위 밖이라 자동 수집되지 않는다. 삭제하지 않고 이 사실을 기록했으며, 실제 회귀 기준은 `tests/`의 346개다.

## 최종 실행 증거

```text
npm ci --ignore-scripts --no-audit --no-fund        PASS
python3 -m pip check                                PASS
npm audit --omit=dev --audit-level=high             PASS, 0 vulnerabilities
npm run build                                       PASS
npm test                                             346 passed, 6 warnings
python3 -m compileall -q api core literature tools main.py  PASS
git diff --check                                     PASS
npm run verify:integrity                             PASS, 13 reports
```

실제 브라우저에서는 `http://127.0.0.1:5173/`에 접속해 FastAPI online 상태, Analyze 동작, provenance가 포함된 결과, runtime event 목록을 확인했다. 브라우저 콘솔의 error/warn은 없었다. 백엔드 health 응답은 `{"ok":true,"runtime":"fastapi","frontend_dist":true,"demo_model":"demo-local"}`였다.

## 세 관점 교차 검토

### Staff Software Engineer

공용 Qt-free pipeline과 React/FastAPI 경계가 분리되어 있고 전체 회귀가 통과한다. 다만 레거시 PyQt 영역과 새 웹 경로의 장기적 중복을 정리할 필요가 있다.

### Security / Reliability Engineer

경로 순회, symlink escape, unbounded upload, frontmatter injection, save failure masking을 수정했다. cross-store transaction, TOCTOU, concurrent writer는 아직 부분 검증이다.

### Humanities / Social Science Research Infrastructure Architect

AI 생성물과 human verification을 구분하는 envelope가 추가되었고 source reference가 보존된다. 그러나 실제 citation/page evidence 검증, contradiction resolution, hypothesis lineage는 다음 단계다.

## 연결 문서

- 영문 최종 보고서: `notes/system-integrity/SYSTEM_RUNTIME_AUDIT_AND_VERIFICATION_REPORT.md`
- 변경 원장: `notes/system-integrity/CHANGE_LEDGER.md`
- 기존 자동 검증 보고서: `notes/system-integrity/SYSTEM_IMPLEMENTATION_AND_RUNTIME_VERIFICATION_REPORT.md`
- 실행 구조: `notes/system-integrity/ACTION_CHAIN_VERIFICATION.md`
- 미검증 영역: `notes/system-integrity/UNVERIFIED_AREAS.md`

## 다음 작업

1. 3개 논문·10개 claim·2개 contradiction·1개 synthesis·1개 hypothesis를 갖는 deterministic golden vault 추가
2. Markdown/graph/memory/cache drift를 검사하고 derived index를 재생성하는 doctor 명령 추가
3. live provider 대신 녹화 fixture 기반 provider contract 테스트 확장
4. vector store를 실제 구현하거나 roadmap으로 명시적으로 격리
5. PyQt 레거시 제거 전 호환 테스트 정책 결정
