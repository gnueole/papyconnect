namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Threading.Tasks;

    public class ActiveRoomResetColor : PluginDynamicCommand
    {
        public ActiveRoomResetColor()
            : base("Reset Color", "Reset active room color to standard white", "LIFX")
        {
        }

        protected override bool OnLoad()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.SelectionUpdated += this.OnSelectionUpdated;
            }
            return true;
        }

        protected override bool OnUnload()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.SelectionUpdated -= this.OnSelectionUpdated;
            }
            return true;
        }

        private void OnSelectionUpdated(object sender, EventArgs e)
        {
            try
            {
                this.ActionImageChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in ActiveRoomResetColor.OnSelectionUpdated");
            }
        }

        protected override void RunCommand(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return;
            }

            Task.Run(async () =>
            {
                var success = await plugin.Client.SetColorToWhiteAsync(plugin.ActiveSelector);
                if (success)
                {
                    plugin.TriggerManualRefresh();
                }
            });
        }

        protected override String GetCommandDisplayName(String actionParameter, PluginImageSize imageSize)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null || string.IsNullOrEmpty(plugin.ActiveSelector))
            {
                return "Reset\nColor";
            }

            if (plugin.ActiveSelector.StartsWith("group_id:"))
            {
                var groupId = plugin.ActiveSelector.Substring("group_id:".Length);
                var group = plugin.Groups.Find(g => g.Id == groupId);
                return group != null ? $"Reset\n{group.Name}" : "Reset\nColor";
            }
            else if (plugin.ActiveSelector.StartsWith("id:"))
            {
                var lightId = plugin.ActiveSelector.Substring("id:".Length);
                var light = plugin.Lights.Find(l => l.Id == lightId);
                return light != null ? $"Reset\n{light.Name}" : "Reset\nColor";
            }
            return "Reset\nColor";
        }

        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            return PluginImages.CreateResetColorImage(imageSize);
        }
    }
}
