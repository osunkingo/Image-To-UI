using System;

namespace ImageToUI.Editor
{
    public sealed class UiPrefabBuildException : Exception
    {
        public string Code { get; }

        public UiPrefabBuildException(string code, string message) : base(message)
        {
            Code = code;
        }
    }
}
