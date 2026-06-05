namespace Loupedeck.LifxPlugin
{
    using System;

    public class LifxApplication : ClientApplication
    {
        public LifxApplication()
        {
        }

        // This method can be used to link the plugin to a Windows application.
        protected override String GetProcessName() => "";

        // This method can be used to link the plugin to a macOS application.
        protected override String GetBundleName() => "";
    }
}
