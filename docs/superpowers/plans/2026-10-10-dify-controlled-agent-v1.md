# AI-Ad-QA Dify Controlled Agent V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backward-compatible Agent video-task API and a Dify Workflow loop that uses the official Dify model `DeepSeek V4.1 Flash` to choose, execute, observe, and stop advertisement-analysis actions.

**Architecture:** Keep the verified `/api/v1/videos/extract` path unchanged. Add a focused `agent_tasks` module and three Agent lifecycle endpoints, prove them with TDD, then gate all Dify work behind a one-image DeepSeek vision preflight. Implement the Agent as an explicit Dify Workflow Loop because the self-hosted Dify 1.15.0 Agent V2 node requires an unavailable backend.

**Tech Stack:** Python 3.11+, FastAPI, standard-library dataclasses/JSON/path handling, FFmpeg/FFprobe, `unittest`, Dify 1.15.0 Workflow, official DeepSeek provider `0.0.24`, `DeepSeek V4.1 Flash`.

**Spec:** `docs/superpowers/specs/2026-10-10-dify-controlled-agent-v1-design.md`

## Global Constraints

- Do not modify `workflow/current/AI-Ad-QA-current.yml` in place.
- Preserve the current `/api/v1/videos/extract` request, response, source-deletion behavior, upload cap, timeouts, and file-serving contract.
- Agent source videos live only under the configured runtime data root and expire after exactly two hours unless explicitly finalized earlier.
- An Agent supplement request accepts at most three timestamps; V1 permits only one successful supplementary round per task.
- The Dify Agent loop executes at most five decision steps and retries the same failed action at most once.
- Use only the official Dify model `DeepSeek V4.1 Flash`; do not add LiteLLM, Claude, OpenAI, RAG, MCP, a second model, or the Dify Agent V2 backend.
- The user enters the DeepSeek API key manually in Dify. Do not read, write, echo, log, export, or commit credentials.
- Do not change `.env`, Docker Compose, global Python, system PATH, firewall, or machine configuration.
- Do not publish the Dify app, initialize Git, push, or create a public artifact without explicit user approval.
- Use `apply_patch` for repository file edits and the project-local `.venv\Scripts\python.exe` for verification.
- The directory is not currently a Git checkout. Every task ends in a verified local checkpoint instead of a commit.

## Review Focus

- A timestamp may be `NaN`, infinity, a boolean, duplicated after float normalization, negative, or equal to the video duration; Task 2 must reject or classify each deterministically.
- A UUID-shaped task directory may be a symlink, lack metadata, contain corrupt metadata, or reference a missing source; Tasks 1, 4, and 5 must fail closed without touching paths outside the data root.
- An upload may exceed the cap partway through streaming or leave a partial task; Task 3 must remove only the new failed task and preserve unrelated tasks.
- Two supplement calls may race or repeat the same timestamp; Task 4 must permit at most one successful supplementary round and never overwrite an already recorded frame as a new result.
- Cleanup may run after source expiry while frames remain useful for a report; Task 5 must delete the expired source and metadata safely without broad recursive deletion outside the validated UUID task.

---

## File Structure

- Create `video_processor/agent_tasks.py`: Agent-task metadata, timestamp validation, safe task lookup, metadata persistence, finalization, and short-retention cleanup.
- Modify `video_processor/app.py`: shared upload helper plus the three Agent lifecycle endpoints; preserve the legacy endpoint.
- Modify `video_processor/service.py`: expose deterministic timestamp normalization needed by Agent supplement extraction while keeping FFmpeg execution here.
- Create `tests/test_agent_tasks.py`: pure lifecycle, metadata, safety, timestamp, and cleanup tests.
- Modify `tests/test_api.py`: real-video API tests for create, supplement, delete, and legacy compatibility.
- Modify `tests/test_readiness_and_limits.py`: partial-upload cleanup and startup-retention coverage where it already owns limit/cleanup behavior.
- Modify `workflow/README.md`: define `candidate/` naming, review, promotion, and credential-scan rules before creating that directory.
- Create `workflow/candidate/AI-Ad-QA-agent-v1.yml`: exported Dify candidate DSL only after the visual preflight and loop tests pass.
- Create `docs/dify-agent-v1-runbook.md`: model preflight, manual credential boundary, node map, test cases, export checks, and unpublished status.

### Task 1: Agent Task Metadata and Safe Lifecycle Boundary

**Files:**
- Create: `video_processor/agent_tasks.py`
- Create: `tests/test_agent_tasks.py`

**Interfaces:**
- Produces: `AgentTaskRecord(video_id: str, duration_seconds: float, source_filename: str, used_timestamps: tuple[float, ...], supplementary_rounds: int, created_at: float, expires_at: float)`.
- Produces: `create_record(video_id: str, duration_seconds: float, source_filename: str, used_timestamps: list[float], created_at: float, retention_seconds: int) -> AgentTaskRecord`.
- Produces: `save_record(task_dir: Path, record: AgentTaskRecord) -> None` using `agent-task.json` and atomic replacement.
- Produces: `load_record(root: Path, video_id: str) -> tuple[Path, AgentTaskRecord]` that accepts only canonical UUID directories under `root`, rejects symlinks, malformed metadata, and missing source files.
- Produces: `delete_agent_task(root: Path, video_id: str) -> bool` returning `False` for missing/invalid tasks and deleting only a validated UUID task directory.

- [ ] **Step 1: Write failing metadata round-trip and expiry tests**

Add `AgentTaskLifecycleTests` covering exact JSON round-trip values, a two-hour `expires_at`, and atomic persistence without a leftover temporary file.

- [ ] **Step 2: Write failing path-safety tests**

Add tests asserting invalid UUIDs, symlink task directories, corrupt `agent-task.json`, `../`-style IDs, and missing source files raise `AgentTaskNotFound`; assert an unrelated sibling directory remains untouched.

- [ ] **Step 3: Run the focused tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_tasks.AgentTaskLifecycleTests -v`

Expected: FAIL because `video_processor.agent_tasks` does not exist.

- [ ] **Step 4: Implement the metadata and safe-path interfaces**

Create immutable dataclasses and domain exceptions in `video_processor/agent_tasks.py`. Serialize only primitive JSON fields; resolve and validate the root and UUID child before reads or deletion; reject symlinks and source paths not represented by a basename.

- [ ] **Step 5: Run Task 1 tests and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_tasks.AgentTaskLifecycleTests -v`

Expected: all Task 1 tests pass.

- [ ] **Step 6: Record the local checkpoint**

Run: `git status --short`

Expected: `fatal: not a git repository`; record this in the execution log and do not initialize Git.

### Task 2: Supplementary Timestamp Validation

**Files:**
- Modify: `video_processor/service.py:9-28`
- Modify: `tests/test_video_service.py:8-30`
- Modify: `tests/test_agent_tasks.py`

**Interfaces:**
- Produces: `normalize_requested_timestamps(duration_seconds: float, requested: list[float], used: set[float], limit: int = 3) -> tuple[list[float], list[str]]`.
- Consumes: exact video duration from `probe_duration`; existing timestamps from `AgentTaskRecord.used_timestamps`.
- Normalization: round accepted timestamps to three decimal places before duplicate comparison and filename generation.

- [ ] **Step 1: Write failing valid-selection tests**

Assert `[8, 12.1234, 8.0]` with no prior usage becomes accepted `[8.0, 12.123]` plus one duplicate warning; preserve request order.

- [ ] **Step 2: Write failing hostile-input tests**

Assert booleans, strings, `NaN`, positive/negative infinity, negative values, values equal to duration, and values greater than duration are not accepted. Assert more than three unique valid timestamps is rejected rather than silently truncated.

- [ ] **Step 3: Write failing already-used tests**

Assert `3.0004` is treated as duplicate of used `3.0` after normalization and produces no extraction request.

- [ ] **Step 4: Run the focused tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_video_service.TimestampSelectionTests tests.test_agent_tasks.SupplementaryTimestampTests -v`

Expected: FAIL because `normalize_requested_timestamps` is absent.

- [ ] **Step 5: Implement timestamp normalization**

Add the exact signature to `service.py`; accept only finite `int`/`float` values that are not booleans; use `0 <= timestamp < duration_seconds`; raise `ValueError` when more than `limit` unique valid new timestamps were requested.

- [ ] **Step 6: Run Task 2 tests and verify GREEN**

Run the focused command from Step 4.

Expected: all timestamp tests pass.

- [ ] **Step 7: Run existing service tests**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_video_service -v`

Expected: existing fixed-timestamp and FFmpeg tests remain green.

### Task 3: Create Agent Video Task Endpoint

**Files:**
- Modify: `video_processor/app.py:19-169`
- Modify: `tests/test_api.py`
- Modify: `tests/test_readiness_and_limits.py`

**Interfaces:**
- Produces: `POST /api/v1/agent-videos` multipart field `video`.
- Produces response: `video_id`, rounded `duration_seconds`, existing frame objects, `warnings`, and UTC ISO-8601 `source_retained_until`.
- Consumes: `create_record` and `save_record` from Task 1; `probe_duration`, `select_timestamps`, and `extract_frames` from the existing service.
- Preserves: `POST /api/v1/videos/extract` and its exact legacy success payload.

- [ ] **Step 1: Extract a reusable test-video factory**

Move the repeated FFmpeg `testsrc2` creation in tests into `tests/video_fixtures.py` as `create_test_video(path: Path, duration_seconds: float = 4.0) -> Path`; update existing tests without changing assertions.

- [ ] **Step 2: Run existing tests after the test-only refactor**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: existing suite passes before endpoint production code changes.

- [ ] **Step 3: Write the failing Agent-create success test**

Post the generated MP4 to `/api/v1/agent-videos`; assert HTTP 200, `[0.0, 3.0]` frames, existing downloadable JPEGs, retained `source.mp4`, valid `agent-task.json`, and an expiry exactly two hours after the recorded creation time within test tolerance.

- [ ] **Step 4: Write failing cleanup-on-error tests**

Cover unsupported extension, empty file, size-limit breach during chunk streaming, FFprobe failure, FFmpeg failure, and `ENOSPC`; assert the newly allocated task directory is removed and a pre-existing unrelated UUID task remains.

- [ ] **Step 5: Run the endpoint tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_api.AgentVideoTaskApiTests -v`

Expected: FAIL with 404 because the route is absent.

- [ ] **Step 6: Refactor upload streaming into one private helper**

In `app.py`, add `_save_upload(video: UploadFile, video_path: Path, max_upload_bytes: int) -> Awaitable[None]` or an equivalent `async def` helper used by both endpoints. Preserve current status codes and messages.

- [ ] **Step 7: Implement `POST /api/v1/agent-videos`**

Keep the source after successful initial extraction, write metadata only after all initial frames succeed, and remove the whole new task on any failure. Use `VIDEO_PROCESSOR_AGENT_SOURCE_RETENTION_SECONDS` with default `7200`, parsed as a positive integer without modifying `.env`.

- [ ] **Step 8: Run Task 3 tests and verify GREEN**

Run the focused command from Step 5.

Expected: all Agent-create and upload cleanup tests pass.

- [ ] **Step 9: Verify legacy response compatibility**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_api.VideoProcessorApiTests -v`

Expected: legacy tests pass and `source.mp4` is still absent after `/api/v1/videos/extract`.

### Task 4: Supplementary Frame Endpoint and One-Round Guard

**Files:**
- Modify: `video_processor/agent_tasks.py`
- Modify: `video_processor/app.py`
- Modify: `tests/test_agent_tasks.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Produces: Pydantic request model `SupplementaryFramesRequest(timestamps: list[float])` in `app.py`.
- Produces: `POST /api/v1/agent-videos/{video_id}/frames`.
- Produces: `record_supplement(record: AgentTaskRecord, new_timestamps: list[float]) -> AgentTaskRecord`, incrementing `supplementary_rounds` exactly once.
- Consumes: `normalize_requested_timestamps` from Task 2 and `extract_frames` from the existing service.

- [ ] **Step 1: Write failing successful-supplement test**

Create a 14-second task, request `[8.0, 12.0]`, assert HTTP 200, two new frame payloads and downloadable JPEGs, updated metadata timestamps, and `supplementary_rounds == 1`.

- [ ] **Step 2: Write failing validation and task-state tests**

Cover invalid UUID, missing task, expired record, missing source, empty accepted set, negative/equal-duration/over-duration values, more than three values, and duplicate used timestamps with exact 404/422 responses.

- [ ] **Step 3: Write failing second-round and repeat-call tests**

After one successful supplement, a second request must return 409 without invoking FFmpeg. Two identical sequential requests must not overwrite metadata or report old frames as newly created.

- [ ] **Step 4: Run focused tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_api.AgentSupplementApiTests -v`

Expected: FAIL because the route is absent.

- [ ] **Step 5: Implement the supplement route**

Load and validate the record, reject expired or completed rounds, normalize timestamps, extract into the existing frames directory, then atomically save the updated record only after every requested frame succeeds.

- [ ] **Step 6: Make partial FFmpeg failure rollback deterministic**

Track filenames created during the current call; if any later extraction fails, remove only those new files and leave metadata unchanged. Add a test that fails on the second requested timestamp.

- [ ] **Step 7: Run Task 4 tests and verify GREEN**

Run the focused command from Step 4.

Expected: all supplement tests pass.

### Task 5: Finalization and Two-Hour Source Cleanup

**Files:**
- Modify: `video_processor/agent_tasks.py`
- Modify: `video_processor/app.py:49-83`
- Modify: `tests/test_agent_tasks.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_readiness_and_limits.py`

**Interfaces:**
- Produces: `DELETE /api/v1/agent-videos/{video_id}` returning HTTP 204 for a valid task and 404 for invalid/missing tasks.
- Produces: `cleanup_expired_agent_sources(root: Path, now: float | None = None) -> list[str]` returning cleaned video IDs for observability.
- Preserves: existing seven-day `cleanup_expired_tasks` behavior for ordinary UUID task directories.

- [ ] **Step 1: Write failing delete tests**

Assert a valid DELETE removes its whole validated UUID task, subsequent frame download returns 404, repeated DELETE returns 404, and unrelated/symlink directories remain.

- [ ] **Step 2: Write failing expiry cleanup tests**

Create one active Agent task, one expired Agent task, one corrupt-metadata UUID directory, one legacy frame-only UUID directory, and one unrelated directory. Assert only the expired Agent task source lifecycle is acted on according to the spec and nothing escapes the root.

- [ ] **Step 3: Resolve the source-versus-frame retention rule in code**

For expired Agent tasks, delete the full Agent task directory because its frames and metadata are part of the same temporary Agent run; retain legacy frame-only tasks under the existing seven-day rule. Document this exact behavior in the runbook so it is not confused with report persistence.

- [ ] **Step 4: Run focused tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_agent_tasks.AgentCleanupTests tests.test_api.AgentDeleteApiTests -v`

Expected: FAIL because cleanup and DELETE are absent.

- [ ] **Step 5: Implement safe finalization and cleanup**

Call short-retention cleanup during `create_app` after the root exists and before the broad seven-day cleanup. Fail closed on corrupt metadata: do not delete it under the two-hour rule; let only the existing UUID age rule handle it later.

- [ ] **Step 6: Run Task 5 tests and verify GREEN**

Run the focused command from Step 4.

Expected: all finalization and cleanup tests pass.

- [ ] **Step 7: Run the complete backend suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all old and new tests pass with no warnings about unclosed files.

### Task 6: Candidate Workflow Rules and DeepSeek Vision Preflight

**Files:**
- Modify: `workflow/README.md`
- Create: `docs/dify-agent-v1-runbook.md`

**Interfaces:**
- Produces: candidate lifecycle `candidate → reviewed → current/archive`; candidate import never replaces the current app during development.
- Produces: a manual preflight record containing Dify version, model identifier, image source, output Schema result, elapsed time, and redacted failure text.
- Consumes: user-entered DeepSeek credential in Dify; no credential is returned to the repository.

- [ ] **Step 1: Add candidate-directory conventions before creating it**

Document `workflow/candidate/AI-Ad-QA-agent-v1.yml`, naming rules, credential scan, review requirements, and the rule that only an explicitly approved candidate can replace `current`.

- [ ] **Step 2: Write the runbook preflight procedure**

Document how to start the existing local Dify stack without changing Compose, select `DeepSeek V4.1 Flash`, let the user enter the API key, send one non-sensitive local JPEG through Dify, and require structured fields `summary`, `visible_text`, `confidence`.

- [ ] **Step 3: Start existing services and inspect Dify capabilities**

Use the existing Docker Compose and FastAPI launchers only. Do not modify `.env` or Compose. Confirm Dify reports version 1.15.0 and that a Workflow Loop plus vision-capable LLM node are available.

- [ ] **Step 4: Pause for the user's credential entry**

The user enters the DeepSeek key directly in Dify. Do not observe, copy, log, or ask the user to paste it into chat.

- [ ] **Step 5: Execute the one-image preflight**

Expected: Dify sends the image bytes—not the inaccessible `host.docker.internal` URL alone—to `DeepSeek V4.1 Flash`, and the node returns valid structured output.

- [ ] **Step 6: Apply the hard gate**

If preflight fails, record the exact redacted error and stop before Task 7. Do not build or claim a video Agent. Any FastAPI-to-DeepSeek fallback requires a new approved design because it changes secret ownership and runtime boundaries.

### Task 7: Build and Test the Dify Controlled Loop

**Files:**
- Create after successful UI export: `workflow/candidate/AI-Ad-QA-agent-v1.yml`
- Modify: `docs/dify-agent-v1-runbook.md`

**Interfaces:**
- Consumes: Agent video endpoints from Tasks 3–5 and successful visual preflight from Task 6.
- Produces state fields: `video_id`, `duration_seconds`, `current_step`, `completed_actions`, `used_timestamps`, `visual_evidence`, `script_evidence`, `missing_dimensions`, `errors`, `retry_count`, `supplementary_rounds`, `needs_human_review`, `final_status`.
- Produces decisions restricted to `analyze_frames`, `extract_additional_frames`, `check_ad_script`, `generate_optimization_plan`, and `stop`.
- Produces terminal states `completed`, `partial`, and `human_review_required`.

- [ ] **Step 1: Create a deliberate candidate app from the current DSL**

Import a copy only after naming it clearly as the Agent V1 candidate. Do not edit or publish the existing current app. Record the candidate app identity in the runbook.

- [ ] **Step 2: Replace the fixed upload path with Agent task creation**

Call `POST /api/v1/agent-videos`; retain the existing parse/failure behavior and initialize the exact Agent state fields.

- [ ] **Step 3: Add the Loop with a hard maximum of five iterations**

Pass complete state into every iteration. Increment `current_step` deterministically outside the model.

- [ ] **Step 4: Add the DeepSeek decision node and strict structured output**

Require `action`, `reason`, `arguments`, and `should_stop`. Reject unknown actions in a deterministic branch before any tool runs.

- [ ] **Step 5: Add action branches one at a time**

First `analyze_frames`, then `check_ad_script`, then `extract_additional_frames`, then `generate_optimization_plan`, and finally `stop`. After each branch, merge results into state without allowing the model to rewrite previous evidence.

- [ ] **Step 6: Add deterministic guards**

Reject a second supplement, a third visual analysis, a second successful script check, a second optimization generation, and any action after a terminal state. Permit one retry for the same failed action.

- [ ] **Step 7: Add cleanup and deterministic report formatting**

On every terminal path, call DELETE best-effort, retain any cleanup warning internally, and format Markdown with a Template node rather than another free-form LLM pass.

- [ ] **Step 8: Run five simulated decision fixtures**

Use cached or fixed structured decisions to prove: direct completion; supplement then completion; two model failures to `partial`; two Schema failures to `human_review_required`; five-step forced stop. Record node traces and stop reasons in the runbook.

- [ ] **Step 9: Run one real DeepSeek controlled loop**

Use a program-generated non-sensitive video. Require at least one observable `decision → tool → result → second decision` sequence and verify task cleanup afterward.

- [ ] **Step 10: Export and inspect the candidate DSL**

Export to `workflow/candidate/AI-Ad-QA-agent-v1.yml`; search for keys, tokens, passwords, local user-profile paths, and unexpected provider secrets. Expected: none present.

### Task 8: Final Verification and Portfolio Evidence Boundary

**Files:**
- Modify: `README.md`
- Modify: `docs/dify-agent-v1-runbook.md`

**Interfaces:**
- Consumes: passing backend suite, exported candidate DSL, five simulated loop cases, one real technical loop, and later one user-supplied non-sensitive advertisement.
- Produces: reproducible startup/test instructions and explicit verified/unverified claims.

- [ ] **Step 1: Run backend verification**

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 2: Run static hygiene checks**

Run: `.\.venv\Scripts\python.exe -m compileall -q video_processor tests`

Expected: exit code 0.

Run: `rg -n -i "api[_-]?key|authorization:|bearer |password|token" workflow/candidate docs README.md`

Expected: only explanatory placeholders or safety prose; no credential values.

- [ ] **Step 3: Verify live local chain**

Check host `/health`, Dify-container access to `host.docker.internal:8000/health`, Agent task creation, supplementary extraction, frame download, DELETE cleanup, and one Dify loop trace.

- [ ] **Step 4: Compare baseline and candidate**

Use the same non-sensitive input to record: final status, number of model calls, supplement use, elapsed time, failures, and report completeness. Do not claim quality improvement from a synthetic video.

- [ ] **Step 5: Pause for a user-supplied advertisement**

The user selects and supplies a non-sensitive video. Run both versions and ask the user to review whether frame-linked findings and recommendations are materially better.

- [ ] **Step 6: Update README with truthful status**

Until real-ad review passes, label the candidate “技术链路已验证，真实广告质量待人工复核.” After review, record the exact case count; do not claim production readiness or broad accuracy.

- [ ] **Step 7: Leave the candidate unpublished**

Report the local candidate path and verification results. Publishing, replacing `current`, Git initialization, commit, and push remain separate user-approved actions.
