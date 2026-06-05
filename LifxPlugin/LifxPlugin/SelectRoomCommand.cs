namespace Loupedeck.LifxPlugin
{
    using System;

    public class SelectRoomCommand : PluginDynamicCommand
    {
        public SelectRoomCommand()
            : base()
        {
        }

        protected override bool OnLoad()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.GroupsUpdated += this.OnGroupsUpdated;
                plugin.SelectionUpdated += this.OnSelectionUpdated;

                // Load groups if already populated
                if (plugin.Groups.Count > 0)
                {
                    this.OnGroupsUpdated(this, EventArgs.Empty);
                }
            }
            return true;
        }

        protected override bool OnUnload()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.GroupsUpdated -= this.OnGroupsUpdated;
                plugin.SelectionUpdated -= this.OnSelectionUpdated;
            }
            return true;
        }

        private void OnGroupsUpdated(object sender, EventArgs e)
        {
            try
            {
                var plugin = (LifxPlugin)this.Plugin;
                if (plugin == null)
                {
                    return;
                }

                this.RemoveAllParameters();

                // Register room selectors
                if (plugin.Groups != null)
                {
                    foreach (var group in plugin.Groups)
                    {
                        this.AddParameter(group.Id, group.Name, "LIFX Room Selector");
                    }
                }

                this.ParametersChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in SelectRoomCommand.OnGroupsUpdated");
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
                PluginLog.Error(ex, "Error in SelectRoomCommand.OnSelectionUpdated");
            }
        }

        protected override void RunCommand(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null || string.IsNullOrEmpty(actionParameter))
            {
                return;
            }

            plugin.ToggleRoomSelection(actionParameter);
            plugin.TriggerManualRefresh();
        }

        protected override String GetCommandDisplayName(String actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter))
            {
                return "Select Room";
            }

            var plugin = (LifxPlugin)this.Plugin;
            var group = plugin.Groups.Find(g => g.Id == actionParameter);
            return group != null ? group.Name : "Room";
        }

        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            var plugin = (LifxPlugin)this.Plugin;

            if (plugin != null && plugin.SelectedRoomIds.Contains(actionParameter))
            {
                // Active/Selected state: Purple background, Black icon
                return PluginImages.CreateBulbButtonImage(imageSize, true, PluginImages.BlackColor, PluginImages.PurpleColor);
            }
            else
            {
                // Inactive state: Black background, Purple icon
                return PluginImages.CreateBulbButtonImage(imageSize, true, PluginImages.PurpleColor, PluginImages.BlackColor);
            }
        }
    }
}
