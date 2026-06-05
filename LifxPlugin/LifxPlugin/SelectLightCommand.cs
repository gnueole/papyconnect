namespace Loupedeck.LifxPlugin
{
    using System;

    public class SelectLightCommand : PluginDynamicCommand
    {
        public SelectLightCommand()
            : base()
        {
        }

        protected override bool OnLoad()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.LightsUpdated += this.OnLightsUpdated;
                plugin.SelectionUpdated += this.OnSelectionUpdated;

                if (plugin.Lights.Count > 0)
                {
                    this.OnLightsUpdated(this, EventArgs.Empty);
                }
            }
            return true;
        }

        protected override bool OnUnload()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.LightsUpdated -= this.OnLightsUpdated;
                plugin.SelectionUpdated -= this.OnSelectionUpdated;
            }
            return true;
        }

        private void OnLightsUpdated(object sender, EventArgs e)
        {
            try
            {
                var plugin = (LifxPlugin)this.Plugin;
                if (plugin == null)
                {
                    return;
                }

                this.RemoveAllParameters();

                if (plugin.Lights != null)
                {
                    foreach (var light in plugin.Lights)
                    {
                        this.AddParameter(light.Id, light.Name, "LIFX Light Selector");
                    }
                }

                this.ParametersChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in SelectLightCommand.OnLightsUpdated");
            }
        }

        private void OnSelectionUpdated(object sender, EventArgs e)
        {
            try
            {
                this.ActionImageChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in SelectLightCommand.OnSelectionUpdated");
            }
        }

        protected override void RunCommand(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null || string.IsNullOrEmpty(actionParameter))
            {
                return;
            }

            plugin.ToggleLightSelection(actionParameter);
            plugin.TriggerManualRefresh();
        }

        protected override String GetCommandDisplayName(String actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter))
            {
                return "Select Light";
            }

            var plugin = (LifxPlugin)this.Plugin;
            var light = plugin.Lights.Find(l => l.Id == actionParameter);
            return light != null ? light.Name : "Light";
        }

        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null || string.IsNullOrEmpty(actionParameter))
            {
                return null;
            }

            var light = plugin.Lights.Find(l => l.Id == actionParameter);
            var isOffline = light != null && !light.Connected;
            var type = light?.Type ?? "bulb";

            if (isOffline)
            {
                // Muted gray crossed-out light icon
                return PluginImages.CreateLightTypeButtonImage(imageSize, type, false, null, null, true);
            }

            if (plugin.SelectedLightIds.Contains(actionParameter))
            {
                // Active/Selected state: Purple background, Black icon
                return PluginImages.CreateLightTypeButtonImage(imageSize, type, false, PluginImages.BlackColor, PluginImages.PurpleColor, false);
            }
            else
            {
                // Inactive state: Black background, Purple icon
                return PluginImages.CreateLightTypeButtonImage(imageSize, type, false, PluginImages.PurpleColor, PluginImages.BlackColor, false);
            }
        }
    }
}
