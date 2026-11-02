# Unity MCP Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the existing UGUI Prefab builder through MCP for Unity without removing the Bridge route.

**Architecture:** Transport-neutral builder with separate optional Editor adapter assemblies. The Python workspace emits either Bridge or MCP request descriptors after the same safety checks.

**Tech Stack:** Unity 2022.3, C#, MCP for Unity 10.3.0 custom tools, Python 3.10+.

**Spec:** `docs/superpowers/specs/2026-11-02-unity-mcp-adapter-design.md`

## Global Constraints

- Preserve existing `build_ui_prefab` behavior and default workspace output.
- Never overwrite an existing Prefab through workspace requests.
- Keep Python image analysis and review gates unchanged.

## Review Focus

- MCP-only package installation must compile without UnityAgentBridge.
- Bridge-only package installation must compile without MCP for Unity.
- Both adapters must surface an existing target as `UI_PREFAB_EXISTS`.
- MCP build results must include the same resource and state evidence as Bridge results.
- Cross-project requests must include a Unity project identity.

---

### Task 1: Neutralize builder and split assemblies

**Files:** `Unity/Editor/UiPrefabBuilder.cs`, `Unity/Editor/UiPrefabBuildException.cs`, `Unity/Editor/ImageToUi.Editor.asmdef`, Bridge adapter files/asmdef, Bridge test asmdef.

- [ ] Make a test fail for the neutral existing-Prefab exception.
- [ ] Add the neutral exception and map it in the Bridge handler.
- [ ] Move Bridge registration into an optional Bridge-only assembly.
- [ ] Compile and run existing Bridge Editor tests.

### Task 2: MCP custom tool

**Files:** MCP adapter C# file/asmdef and MCP Editor tests.

- [ ] Add tests for discovery, successful build, and existing target refusal.
- [ ] Implement `image_to_ui_build_prefab` with typed parameters and a `HandleCommand(JObject)` entry point.
- [ ] Confirm its tool metadata and result through the live testui MCP connection.

### Task 3: Workspace backend and docs

**Files:** `image-to-ui/scripts/workspace.py`, `image-to-ui/tests/test_workspace.py`, README files, Unity README, skill.

- [ ] Add a failing Python test for `--backend mcp` requests and the unchanged Bridge default.
- [ ] Implement backend selection with identical safety gates and request metadata.
- [ ] Document installation, project selection, request execution, and the continued Python review flow.
- [ ] Run Python tests and Unity end-to-end checks with a unique test Prefab path.
