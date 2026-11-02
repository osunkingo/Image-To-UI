using System;
using ImageToUI.Editor;
using MCPForUnity.Editor.Tools;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace ImageToUI.Tests
{
    public sealed class ImageToUiMcpTests
    {
        [Test]
        public void ToolIsRegisteredWithExpectedName()
        {
            var attribute = (McpForUnityToolAttribute)Attribute.GetCustomAttribute(
                typeof(ImageToUiBuildPrefabTool), typeof(McpForUnityToolAttribute));
            Assert.IsNotNull(attribute);
            Assert.AreEqual("image_to_ui_build_prefab", attribute.Name);
            Assert.IsTrue(attribute.AutoRegister);
        }

        [Test]
        public void InvalidInputReturnsStructuredError()
        {
            var response = JObject.FromObject(ImageToUiBuildPrefabTool.HandleCommand(new JObject()));
            Assert.IsFalse((bool)response["success"]);
            Assert.AreEqual("UI_INVALID_STRUCTURE", (string)response["code"]);
            Assert.IsNotEmpty((string)response["error"]);
        }
    }
}
