# Phase C Diagnosis Implementation Plan

> **For agentic workers:** Execute task-by-task. Steps use checkbox syntax.

**Goal:** Complete Phase C workstream C1 (Camera diagnosis docs) while C2 idle-fill runs on nuc; do **not** enqueue Phase A' FT.

**Architecture:** Documentation-only updates to `strategy/02` and the Phase C spec. No training code changes. Video re-watch is best-effort if run artifacts still exist on thor.

**Tech Stack:** existing parc strategy markdown, SSH to thor for artifacts if present

---

### Task 1: View gap + Phase B fixed text → 02

**Files:**
- Modify: `strategy/02_results_and_findings.md`
- Modify: `docs/superpowers/specs/2026-08-01-phase-c-cam-diagnosis-design.md` (checkboxes)

- [x] Add section **Phase C diagnosis** with train-safe vs eval hard table
- [x] Paste Phase B failure fixed paragraph
- [x] Note continue10k Cam deep remasurement SR=0.16 (task-level: artifact pruned → use prior 0.20 review + registry)

### Task 2: A' draft pointer

- [x] In 02 / 03, point to Phase C spec C1.4 as next FT candidate (approval-gated)
- [x] Update 01 snapshot if needed

### Task 3: C2 status

- [x] Record nuc Sensor deep job id; when DONE, log SR vs thor 0.16 in 02 (not for parent)
  - **DONE SR=0.24** · `q_…7bbbffb5` · `20260731T180023Z_nuc_cb27a7ad_…`（vs thor 0.16 · 親決め禁止）

### Task 4: A'（ユーザー承認済 · thor）

- [x] mix v4 完了 · wrist/front 検証（wrist AV1→h264 · 40214f）
- [x] FT enqueue `q_20260731T185532…e5d15dcf`
