# Unity MCP adapter design

## Goal

Build the same UGUI Prefab from a finalized Image-To-UI structure through MCP for Unity 10.3.0 while retaining the existing UnityAgentBridge command. Python prepare, check, visual review, and finalize remain unchanged.

## Architecture

- `ImageToUI.Editor` owns the Unity Prefab builder and a transport-neutral build exception. It references UGUI and Newtonsoft, but neither bridge package.
- A Bridge-only Editor assembly registers `build_ui_prefab` when UnityAgentBridge is installed. It maps neutral errors back to the existing Bridge error codes.
- An MCP-only Editor assembly registers the custom tool `image_to_ui_build_prefab` when `com.coplaydev.unity-mcp` is installed. It accepts the same structure, asset roots, target, font options, and overwrite flag, and returns the builder's result.
- `workspace.py build-requests --backend mcp` emits requests for the MCP tool. The existing `bridge` backend remains the default. Both use the same finalized-structure, target-exists, project-routing, and non-overwrite gates.

## Safety

- The MCP tool runs only in Edit Mode. It keeps the builder's existing resource rollback and refuses existing Prefabs unless `overwrite` is explicitly true. Workspace requests always set it false.
- A request identifies the intended Unity project. The caller selects that MCP instance before invoking the tool.
- No existing game Prefab is modified during integration testing; use a unique test target and verify dependencies and layout in Unity.

## Verification

- Python tests cover both request backends, stale/incomplete pages, and existing targets.
- Unity Editor tests cover MCP tool discovery, input validation, successful build, and non-overwrite behavior. Existing Bridge tests remain available when Bridge is installed.
- A live `testui` MCP session is used to confirm tool discovery, compile state, build result, and Prefab inspection after the local package is loaded.
