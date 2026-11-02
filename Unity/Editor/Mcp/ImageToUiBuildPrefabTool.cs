using System;
using MCPForUnity.Editor.Helpers;
using MCPForUnity.Editor.Tools;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;

namespace ImageToUI.Editor
{
    [McpForUnityTool("image_to_ui_build_prefab", Description = "Build a UGUI prefab from a completed Image-To-UI structure and sprite directory. Refuses to replace an existing prefab unless overwrite is true.")]
    public static class ImageToUiBuildPrefabTool
    {
        public sealed class Parameters
        {
            [ToolParameter("Absolute or Unity-project-relative path to ui_structure.json")]
            public string structurePath { get; set; }

            [ToolParameter("Sprite directory path")]
            public string assetsPath { get; set; }

            [ToolParameter("Target Assets/.../*.prefab path")]
            public string prefabPath { get; set; }

            [ToolParameter("Allow replacement of an existing prefab; defaults to false", Required = false, DefaultValue = "false")]
            public bool overwrite { get; set; }

            [ToolParameter("Optional font family to font file mapping", Required = false)]
            public object fontMap { get; set; }

            [ToolParameter("Optional fallback font file path", Required = false)]
            public string defaultFontPath { get; set; }
        }

        public static object HandleCommand(JObject parameters)
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode)
                return Error("UI_EDIT_MODE_REQUIRED", "Generate UI prefabs in Edit Mode.");
            try
            {
                return new SuccessResponse("UGUI prefab built", UiPrefabBuilder.Build(parameters));
            }
            catch (UiPrefabBuildException ex) { return Error(ex.Code, ex.Message); }
            catch (JsonException ex) { return Error("UI_INVALID_STRUCTURE", ex.Message); }
            catch (ArgumentException ex) { return Error("UI_INVALID_STRUCTURE", ex.Message); }
            catch (Exception ex) { return Error("UI_PREFAB_BUILD_FAILED", ex.Message); }
        }

        private static object Error(string code, string message)
        {
            return new { success = false, code, error = message };
        }
    }
}
