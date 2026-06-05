namespace Loupedeck.EoleN8NPlugin
{
    using System;

    public class EoleN8NPlugin : Plugin
    {
        // Gets a value indicating whether this is an API-only plugin.
        public override Boolean UsesApplicationApiOnly => true;

        // Gets a value indicating whether this is a Universal plugin or an Application plugin.
        public override Boolean HasNoApplication => true;

        // Initializes a new instance of the plugin class.
        public EoleN8NPlugin()
        {
            // Initialize the plugin log.
            PluginLog.Init(this.Log);
            // Initialize the plugin resources.
            PluginResources.Init(this.Assembly);
        }

        // This method is called when the plugin is loaded.
        public override void Load()
        {
            PluginLog.Info("Eole n8n Plugin Loaded successfully!");
        }

        // This method is called when the plugin is unloaded.
        public override void Unload()
        {
        }
    }
}
