# AIGC Multimodal Content Quality V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one Dify workflow that evaluates advertising video, image, or script inputs and returns one deterministic, human-readable evaluation contract and report.

**Architecture:** Preserve the existing FastAPI video lifecycle. Add a FastAPI-side evaluation contract and Markdown renderer, then generate a separate candidate Dify DSL: video keeps the bounded Agent loop, while image and script use one structured model call each. All branches submit the same payload to the renderer and expose business output separately from technical details.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, unittest, Dify Workflow DSL, the model provider already configured in Dify, FFmpeg/FFprobe.

**Spec:** `docs/superpowers/specs/2026-10-28-multimodal-content-quality-v1-design.md`

## Global Constraints

- Do not modify `workflow/current/AI-Ad-QA-current.yml`.
- Do not overwrite `workflow/candidate/AI-Ad-QA-agent-v1.yml`.
- Write the new DSL to `workflow/candidate/AIGC-Multimodal-QA-v1.yml`.
- Preserve every existing video API contract.
- Do not modify `.env`, credentials, Docker, system configuration, or database schema.
- Do not push, publish, deploy, or expose port 8000 publicly.
- Video uses the bounded Agent; image and script use one structured model call each.
- The user report must never embed raw `state_json`.
- Run project commands with `.venv\Scripts\python.exe`.

## Review Focus

- Missing optional context produces `partial` and `missing_information`, never invented facts; Task 1.
- `not_applicable` dimensions are excluded from score calculation; Task 1.
- Invalid evidence references and malformed results fail deterministically; Tasks 1-2.
- Image completion requires verified image transport, not a text-only call; Tasks 4 and 6.
- New work does not regress legacy APIs or Agent cleanup; Tasks 2-3 and 6.

---

### Task 1: Unified Evaluation Contract

**Files:**
- Create: `video_processor/evaluation.py`
- Create: `tests/test_evaluation.py`

**Interfaces:**
- Consumes: plain dictionaries from Dify structured outputs.
- Produces: `EvaluationRequest`, `EvaluationResult`, `DimensionScore`, `EvidenceItem`, `IssueItem`, `SuggestionItem`, `RunSummary`; `calculate_overall_score(dimensions: list[DimensionScore]) -> int`; `normalize_evaluation(request: EvaluationRequest) -> EvaluationResult`.

- [ ] **Step 1: Write failing tests**

Add these exact tests:

- `test_calculate_overall_score_uses_equal_weight_for_evaluated_dimensions`
- `test_calculate_overall_score_excludes_not_applicable_dimensions`
- `test_missing_optional_context_marks_partial_without_inventing_facts`
- `test_evidence_refs_must_resolve_to_known_evidence`
- `test_low_confidence_or_conflicting_evidence_requires_human_review`

Assert 0-10 dimension scores, 0-100 overall score, statuses `completed`, `partial`,
`human_review_required`, priorities `P0`, `P1`, `P2`, and spec source types.

- [ ] **Step 2: Verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_evaluation -v`

Expected: import failure because the evaluation module does not exist.

- [ ] **Step 3: Implement the Pydantic models and deterministic scoring**

`normalize_evaluation` records missing optional context, validates evidence references, and
never invents product functions, prices, effects, certifications, or business data.

- [ ] **Step 4: Verify pass**

Run the Task 1 command. Expected: all focused tests pass.

- [ ] **Step 5: Commit**

Run: `git add video_processor/evaluation.py tests/test_evaluation.py`

Run: `git commit -m "feat: add unified multimodal evaluation contract"`

### Task 2: Human-Readable Report API

**Files:**
- Create: `video_processor/reporting.py`
- Modify: `video_processor/app.py`
- Create: `tests/test_reporting.py`
- Modify: `tests/test_api.py`

**Interfaces:**
- Consumes: `EvaluationRequest` JSON at `POST /api/v1/evaluations/render`.
- Produces: `{"result": EvaluationResult, "report_markdown": str, "technical_details": object}` and `render_markdown(result: EvaluationResult) -> str`.

- [ ] **Step 1: Write failing tests**

Add:

- `test_render_contains_summary_score_issues_and_evidence`
- `test_render_shows_missing_information_and_human_review_reason`
- `test_render_does_not_embed_raw_state_json`
- `test_render_endpoint_separates_report_and_technical_details`
- `test_render_endpoint_rejects_unknown_evidence_reference_with_422`

The report headings are `总体结论`, `关键问题`, `分项评分`, `内容优势`, `优化方案`,
and `缺失信息与人工复核提示`.

- [ ] **Step 2: Verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_reporting tests.test_api -v`

Expected: missing renderer or 404 for the endpoint.

- [ ] **Step 3: Implement deterministic Markdown rendering**

Render from normalized fields only. Keep run summary and debug state under
`technical_details`; never interpolate debug JSON into the report.

- [ ] **Step 4: Add the render endpoint without changing existing routes**

Add `POST /api/v1/evaluations/render` inside `create_app` with the exact response contract.

- [ ] **Step 5: Verify focused and full suites**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_reporting tests.test_api -v`

Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`

Expected: all tests pass, including legacy video APIs.

- [ ] **Step 6: Commit**

Stage the four Task 2 files and commit with `feat: render readable evaluation reports`.

### Task 3: Candidate DSL Baseline and Video Branch

**Files:**
- Create: `workflow/tools/build_multimodal_v1.py`
- Create: `workflow/candidate/AIGC-Multimodal-QA-v1.yml`
- Create: `tests/test_multimodal_v1_dsl.py`
- Modify: `workflow/README.md`

**Interfaces:**
- Consumes Dify variables: `asset_type`, `video`, `image`, `script`, `product_context`, `target_audience`, `conversion_goal`, `additional_requirements`.
- Produces Dify outputs: `report_markdown`, `evaluation_result`, `final_status`, `technical_details`; builder `main() -> None` writes the fixed candidate path.

- [ ] **Step 1: Write failing static DSL tests**

Add:

- `test_has_one_asset_type_entry_and_three_branches`
- `test_video_retains_bounded_agent_and_video_lifecycle`
- `test_outputs_separate_report_and_technical_details`
- `test_public_report_never_interpolates_state_json`
- `test_protected_dsl_files_are_unchanged`

Store SHA-256 values for the two protected DSL files at task start.

- [ ] **Step 2: Verify failure**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_multimodal_v1_dsl -v`

Expected: candidate DSL missing.

- [ ] **Step 3: Build a separate candidate from the controlled-Agent design**

Do not redirect the old builder. Keep loop count 5, one supplement round, cleanup, and
whitelisted actions. Add `asset_type` routing.

- [ ] **Step 4: Map video terminal state into `EvaluationRequest`**

Add a deterministic node after the loop and call
`http://host.docker.internal:8000/api/v1/evaluations/render`.

- [ ] **Step 5: Generate and verify**

Run: `.\.venv\Scripts\python.exe workflow\tools\build_multimodal_v1.py`

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_multimodal_v1_dsl tests.test_dify_agent_v1_dsl -v`

Expected: both new and legacy DSL tests pass.

- [ ] **Step 6: Document candidate promotion rules**

State in `workflow/README.md` that this is a portfolio candidate and cannot replace current
until all three live input paths pass.

- [ ] **Step 7: Commit**

Stage Task 3 files and commit with `feat: add multimodal candidate video workflow`.

### Task 4: Image Evaluation Branch

**Files:**
- Modify: `workflow/tools/build_multimodal_v1.py`
- Modify: `workflow/candidate/AIGC-Multimodal-QA-v1.yml`
- Modify: `tests/test_multimodal_v1_dsl.py`

**Interfaces:**
- Consumes uploaded image plus optional business context.
- Produces one `EvaluationRequest` using profile `ad_image_v1`, then the common renderer response.

- [ ] **Step 1: Add failing tests**

Add:

- `test_image_requires_real_vision_input_selector`
- `test_image_uses_ad_image_v1_and_common_schema`
- `test_image_covers_subject_composition_readability_selling_point_audience_cta_and_risk`
- `test_image_renderer_failure_requires_human_review`

- [ ] **Step 2: Verify failure**

Run the multimodal DSL test. Expected: image assertions fail.

- [ ] **Step 3: Add one structured vision call and renderer call**

Enable Dify vision with the uploaded image selector. Use location `image:1`. Missing optional
context produces `partial`; do not create an image Agent loop.

- [ ] **Step 4: Regenerate and verify**

Run the generator and multimodal DSL test. Expected: pass.

- [ ] **Step 5: Commit**

Commit Task 4 files with `feat: add advertisement image evaluation branch`.

### Task 5: Script Evaluation Branch

**Files:**
- Modify: `workflow/tools/build_multimodal_v1.py`
- Modify: `workflow/candidate/AIGC-Multimodal-QA-v1.yml`
- Modify: `tests/test_multimodal_v1_dsl.py`

**Interfaces:**
- Consumes script text plus optional business context.
- Produces one `EvaluationRequest` using profile `ad_script_v1`, then the common renderer response.

- [ ] **Step 1: Add failing tests**

Add:

- `test_script_uses_ad_script_v1_and_common_schema`
- `test_script_covers_hook_pain_selling_point_audience_structure_cta_and_claim_risk`
- `test_script_evidence_uses_paragraph_or_scene_references`
- `test_blank_script_is_rejected_before_model_call`

- [ ] **Step 2: Verify failure**

Run the multimodal DSL test. Expected: script assertions fail.

- [ ] **Step 3: Add deterministic input guard, one model call, and renderer call**

Reject blank content before the model. Malformed structured output becomes
`human_review_required`; do not create a script Agent loop.

- [ ] **Step 4: Regenerate and verify**

Run the generator and multimodal DSL test. Expected: pass.

- [ ] **Step 5: Commit**

Commit Task 5 files with `feat: add advertisement script evaluation branch`.

### Task 6: Live Validation and Portfolio Documentation

**Files:**
- Create: `tests/fixtures/multimodal/README.md`
- Create: `tests/fixtures/multimodal/sample_script.txt`
- Create: `tests/fixtures/multimodal/sample_image.png`
- Reuse the existing generated video fixture helper.
- Create: `docs/multimodal-v1-validation.md`
- Modify: `README.md`
- Modify: `docs/dify-agent-v1-runbook.md`

**Interfaces:**
- Consumes generated/public non-sensitive video, image, and script samples.
- Produces a reproducible record with one real Dify run per type and explicit limitations.

- [ ] **Step 1: Add non-sensitive fixtures and source notes**

Document origin and allowed use. Do not add company/user media. State that fixtures prove the
technical chain, not real advertising quality.

- [ ] **Step 2: Run automated verification**

Run the generator, then `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

Expected: all tests pass; no secret, upload, runtime output, or environment file is tracked.

- [ ] **Step 3: Verify readiness without changing configuration**

Run: `Invoke-RestMethod http://localhost:8000/health`

Expected: `{"status":"ok"}`. If Dify/model is unavailable, record the blocker and do not
modify credentials, `.env`, Docker, or firewall.

- [ ] **Step 4: Import candidate and run minimum image transport check**

Confirm the model receives actual image data and returns image-specific evidence. Otherwise
stop the image completion claim and record exact evidence.

- [ ] **Step 5: Run one video, image, and script sample**

Record final status, score, issue/evidence count, review flag, report headings, and whether raw
JSON leaked.

- [ ] **Step 6: Update README and validation documentation**

Separate completed functions, automated evidence, live evidence, limitations, and roadmap.

- [ ] **Step 7: Final verification**

Run the full unittest suite, `git status --short`, and `git diff --check`.

Expected: all tests pass and only plan-owned files changed.

- [ ] **Step 8: Commit**

Commit documentation and fixtures with `docs: validate multimodal content quality v1`.

## Self-Review Result

- Every V1 goal, exclusion, profile, output boundary, and validation rule maps to Tasks 1-6.
- Every DSL branch produces the Task 1 contract; Task 2 is the single renderer interface.
- The five highest-risk input/failure conditions have tests or a live gate.
- The plan specifies interfaces and assertions without transcribing implementation bodies.
