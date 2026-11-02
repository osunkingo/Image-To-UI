# Multi-project UI Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coordinate multiple Unity games and UI pages, identify shared art candidates, and validate functional UI handoff contracts while preserving the existing single-page workflow.

**Architecture:** A standard-library Python coordinator reads one versioned workspace manifest, creates page-scoped asset views, invokes the current workflow per page, and emits reports and safe Unity build requests. Existing renderer, validator, and Unity exporter remain unchanged.

**Tech Stack:** Python 3.10+, existing Pillow/NumPy workflow, UnityAgentBridge JSON requests.

**Spec:** `docs/superpowers/specs/2026-11-02-multi-project-ui-workspace-design.md`

## Global Constraints

- Existing `workflow.py` and `build_ui_prefab` command remain backward compatible.
- Generated asset views are outside page output and never mutate source assets.
- Existing Prefab targets are never overwritten by batch build requests.
- Functional contracts describe integration points, not gameplay logic.

## Review Focus

- A duplicate project/page ID or output/Prefab path is rejected before a command runs.
- A page cannot reference an asset outside its selected common/local directories.
- Asset basenames that collide remain usable by exact relative path; bare ambiguous references are rejected by existing validation.
- A button action or navigation target must resolve to a button and an existing page.
- A completed page with an existing Prefab target emits no build request.

---

### Task 1: Workspace manifest and page-scoped assets

**Files:** Create `image-to-ui/scripts/workspace.py`; test `image-to-ui/tests/test_workspace.py`.

**Interfaces:** `load_workspace(path: Path) -> Workspace`; `select_pages(workspace, project_id, page_id) -> list[Page]`; `sync_asset_view(page) -> Path`.

- [ ] Add failing tests for two projects, two pages, selected common/local assets, and duplicate/crossing paths.
- [ ] Run the tests and confirm they fail for the missing coordinator.
- [ ] Implement manifest parsing, strict path/ID checks, and symlink-file view creation.
- [ ] Run the new tests and confirm they pass.

### Task 2: Functional contracts and shared-art report

**Files:** Modify `image-to-ui/scripts/workspace.py`; extend `image-to-ui/tests/test_workspace.py`.

**Interfaces:** `validate_functional(page, structure) -> dict`; `build_workspace_report(workspace, pages) -> dict`.

- [ ] Add failing tests for valid/invalid action, navigation, and text binding paths, and identical-content candidate detection.
- [ ] Implement per-page `integration_contract.json` and workspace report with page status, used assets, and hash-grouped common candidates.
- [ ] Run tests and confirm the report is deterministic.

### Task 3: Batch workflow and safe Unity requests

**Files:** Modify `image-to-ui/scripts/workspace.py`; extend `image-to-ui/tests/test_workspace.py`.

**Interfaces:** CLI commands `validate`, `prepare`, `check`, `finalize`, `report`, `build-requests`.

- [ ] Add failing tests for project/page selection, page-isolated prepare, incomplete finalize/build refusal, and existing Prefab refusal.
- [ ] Implement sequential invocation of `workflow.py` and safe per-page request emission with `overwrite: false`.
- [ ] Run tests, then run all existing Python tests once dependencies are available.

### Task 4: Documentation and example

**Files:** Create `examples/ui_workspace.example.json`; modify `README.md`, `README.zh-CN.md`, `image-to-ui/SKILL.md`, and `Unity/README.md`.

- [ ] Document two projects, page folders, common-art promotion, functional contract fields, and safe Unity request flow.
- [ ] Verify example manifest with `workspace.py validate` using fixture paths or documented placeholders.
- [ ] Run CLI help and the complete Python test suite.

### Task 5: Cross-page visual overview

**Files:** Modify `image-to-ui/scripts/workspace.py`, `image-to-ui/tests/test_workspace.py`, README files, and `image-to-ui/SKILL.md`.

- [ ] Add a failing test for a labeled contact sheet and machine-readable page index.
- [ ] Implement `overview` for selected pages, preserving each screenshot's aspect ratio.
- [ ] Verify the image opens, its index contains every selected page, and CLI selection works.
