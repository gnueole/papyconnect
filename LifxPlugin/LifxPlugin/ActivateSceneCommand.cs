namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Threading.Tasks;

    public class ActivateSceneCommand : PluginDynamicCommand
    {
        public ActivateSceneCommand()
            : base()
        {
        }

        protected override bool OnLoad()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.ScenesUpdated += this.OnScenesUpdated;

                if (plugin.Scenes.Count > 0)
                {
                    this.OnScenesUpdated(this, EventArgs.Empty);
                }
            }
            return true;
        }

        protected override bool OnUnload()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.ScenesUpdated -= this.OnScenesUpdated;
            }
            return true;
        }

        private void OnScenesUpdated(object sender, EventArgs e)
        {
            try
            {
                var plugin = (LifxPlugin)this.Plugin;
                if (plugin == null)
                {
                    return;
                }

                this.RemoveAllParameters();

                if (plugin.Scenes != null)
                {
                    foreach (var scene in plugin.Scenes)
                    {
                        this.AddParameter(scene.Id, scene.Name, "LIFX Scenes");
                    }
                }

                this.ParametersChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in ActivateSceneCommand.OnScenesUpdated");
            }
        }

        protected override void RunCommand(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null || string.IsNullOrEmpty(actionParameter))
            {
                return;
            }

            Task.Run(async () =>
            {
                var success = await plugin.Client.ActivateSceneAsync(actionParameter);
                if (success)
                {
                    plugin.TriggerManualRefresh();
                }
            });
        }

        protected override String GetCommandDisplayName(String actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter))
            {
                return "Activate Scene";
            }

            var plugin = (LifxPlugin)this.Plugin;
            var scene = plugin.Scenes.Find(s => s.Id == actionParameter);
            return scene != null ? scene.Name : "Scene";
        }

        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null && !string.IsNullOrEmpty(actionParameter))
            {
                var scene = plugin.Scenes.Find(s => s.Id == actionParameter);
                if (scene != null && scene.ColorsHex != null && scene.ColorsHex.Count > 0)
                {
                    return PluginImages.CreateSceneButtonImage(imageSize, scene.ColorsHex, PluginImages.PurpleColor, PluginImages.BlackColor);
                }
            }
            return PluginImages.CreateSceneButtonImage(imageSize, null, PluginImages.PurpleColor, PluginImages.BlackColor);
        }
    }
}
