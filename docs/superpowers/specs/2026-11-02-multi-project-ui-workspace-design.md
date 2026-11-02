# Multi-project UI workspace design

## Intent

The current workflow analyzes one screenshot and one asset directory into one task folder, then exports one Unity Prefab. A studio needs several games, each with several UI pages, a reviewable way to identify shared art, and a handoff for functional controls. The new workspace layer coordinates existing single-page tools without changing their output contract.

## Goals

- One manifest can name multiple game projects and multiple pages per project.
- Each page has an isolated analysis directory, selected common and page-specific asset directories, and a unique Unity Prefab destination.
- Existing `workflow.py` commands and standalone `build_ui_prefab` remain supported.
- Shared art candidates are reported across pages using exact content hashes and structure references. Promotion to common art stays explicit.
- A labeled contact sheet shows all chosen page designs together before any page is analyzed, so a reviewer can spot recurring visual elements.
- Functional UI is described as validated action, navigation, and data-binding contracts tied to structure element paths. No gameplay rules are inferred from a screenshot.
- A batch command prepares/checks/finalizes chosen pages and emits safe per-page Unity build requests. It refuses an existing Prefab by default.

## Non-goals

- Generating game-specific business logic or a runtime controller.
- Automatically moving, renaming, or merging source assets.
- Treating visually similar artwork as identical without review.
- Replacing native UGUI, the per-page structure schema, or the Unity bridge protocol.

## Approach

Two approaches were considered: extending every low-level Python script and the Unity command to understand project/page manifests, or adding a workspace coordinator around their stable single-page interfaces. The coordinator is chosen because the existing verifier has strong per-page snapshot and review rules; broad changes to those internals would risk those guarantees. A third approach of merely documenting folder conventions would not provide collision checks, shared-art evidence, or batch status.

## Manifest and files

`ui_workspace.json` (version 1) names projects. Each project has an `id`, `assetRoot`, optional `unityProject`, `commonAssetDirs`, and pages. Each page has an `id`, `design`, `assetDirs`, `output`, `prefabPath`, and optional `functional` object. Manifest paths are relative to the manifest directory unless absolute. Asset directory entries are relative to `assetRoot`; their prefixes remain in structure asset paths. A page can select several directories, while the existing workflow receives a private symlink-file view of only those directories. The view is generated outside the page's output and contains no source file copies.

`functional.actions` maps a `button` element path to an action ID. `functional.navigation` maps a `button` path to a page ID in the same project. `functional.bindings` maps a `text` element path to a data key. The coordinator checks paths and types against `ui_structure.json` and writes an `integration_contract.json` in the page output. States, progress, and scroll remain in the existing structure schema and preview flow.

`workspace.py` provides `validate`, `overview`, `prepare`, `check`, `finalize`, `report`, and `build-requests` commands. Commands select a project and optionally a page; no selection means all. `overview` writes a labeled contact sheet and JSON page index from the original screenshots. `report` records page status, used assets, exact-hash shared candidates, and functional-contract issues. `build-requests` emits one Bridge request per completed page with `overwrite: false`, includes the target Unity project, and checks the target disk path first when `unityProject` is available. Cross-project requests require each project's `unityProject`. The agent still sends each request through UnityAgentBridge's single-flight protocol after confirming the active Editor is the stated project, then verifies Unity results.

## Safety and compatibility

- IDs, output paths, and Prefab destinations must be unique within a workspace. Project and page selection never crosses project boundaries by accident.
- The coordinator rejects source/output containment and asset-view path escapes. It never writes into source directories.
- Existing target Prefabs are skipped, never overwritten. Other Prefabs are untouched.
- A failed page stops that page and appears in the workspace report; other selected pages may still be processed.
- Existing single-page workflow and Unity command remain unchanged; the manifest layer is opt-in.

## Verification

Unit tests cover two projects with multiple pages, isolated asset views, duplicate IDs/paths, shared-hash detection, functional path/type validation, incomplete-page export refusal, existing Prefab refusal, and backward compatibility of standalone workflow tests. Documentation includes a two-project example and a step-by-step migration from one page.

## Open implementation calls

- The first version uses symlinked individual files for the per-page analysis view; this preserves exact bytes and avoids copying common assets. Platforms without symlink permission should fail clearly rather than silently duplicate assets.
- A shared candidate requires identical bytes. Visually similar candidates are left for human review, which prevents false automatic deduplication.
