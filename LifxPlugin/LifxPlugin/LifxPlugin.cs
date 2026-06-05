namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Collections.Generic;
    using System.Threading.Tasks;

    public class LifxPlugin : Plugin
    {
        // Gets a value indicating whether this is an API-only plugin.
        public override Boolean UsesApplicationApiOnly => true;

        // Gets a value indicating whether this is a Universal plugin or an Application plugin.
        public override Boolean HasNoApplication => true;

        public LifxClient Client { get; private set; }
        internal static TimeSpan UpdateInterval { get; set; } = TimeSpan.FromMinutes(2);

        public List<LifxGroup> Groups { get; private set; } = new List<LifxGroup>();
        public List<LifxScene> Scenes { get; private set; } = new List<LifxScene>();
        public List<LifxLight> Lights { get; private set; } = new List<LifxLight>();

        public event EventHandler GroupsUpdated;
        public event EventHandler ScenesUpdated;
        public event EventHandler LightsUpdated;

        public System.Collections.Generic.HashSet<string> SelectedRoomIds { get; } = new System.Collections.Generic.HashSet<string>();
        public System.Collections.Generic.HashSet<string> SelectedLightIds { get; } = new System.Collections.Generic.HashSet<string>();

        // For backward compatibility
        public string SelectedRoomId
        {
            get => this.SelectedRoomIds.Count > 0 ? new System.Collections.Generic.List<string>(this.SelectedRoomIds)[0] : null;
            set
            {
                this.SelectedRoomIds.Clear();
                if (value != null)
                {
                    this.SelectedRoomIds.Add(value);
                }
                this.SelectionUpdated?.Invoke(this, EventArgs.Empty);
            }
        }

        // For backward compatibility
        public string SelectedLightId
        {
            get => this.SelectedLightIds.Count > 0 ? new System.Collections.Generic.List<string>(this.SelectedLightIds)[0] : null;
            set
            {
                this.SelectedLightIds.Clear();
                if (value != null)
                {
                    this.SelectedLightIds.Add(value);
                }
                this.SelectionUpdated?.Invoke(this, EventArgs.Empty);
            }
        }

        public string ActiveSelector
        {
            get
            {
                var selectors = new System.Collections.Generic.List<string>();
                foreach (var lightId in this.SelectedLightIds)
                {
                    selectors.Add($"id:{lightId}");
                }
                foreach (var roomId in this.SelectedRoomIds)
                {
                    selectors.Add($"group_id:{roomId}");
                }

                if (selectors.Count > 0)
                {
                    return string.Join(",", selectors);
                }
                return null;
            }
        }

        public event EventHandler SelectionUpdated;

        public void ToggleRoomSelection(string roomId)
        {
            if (this.SelectedRoomIds.Contains(roomId))
            {
                this.SelectedRoomIds.Remove(roomId);
            }
            else
            {
                this.SelectedRoomIds.Add(roomId);
            }
            this.SelectionUpdated?.Invoke(this, EventArgs.Empty);
        }

        public void ToggleLightSelection(string lightId)
        {
            if (this.SelectedLightIds.Contains(lightId))
            {
                this.SelectedLightIds.Remove(lightId);
            }
            else
            {
                this.SelectedLightIds.Add(lightId);
            }
            this.SelectionUpdated?.Invoke(this, EventArgs.Empty);
        }

        private double _effectPeriod = EffectPeriodAdjustment.DefaultPeriod;
        public double EffectPeriod
        {
            get => this._effectPeriod;
            set => this._effectPeriod = Math.Max(EffectPeriodAdjustment.MinPeriod, Math.Min(EffectPeriodAdjustment.MaxPeriod, value));
        }

        public string LastEffectParameter { get; set; } = null;

        // Initializes a new instance of the plugin class.
        public LifxPlugin()
        {
            // Initialize the plugin log.
            PluginLog.Init(this.Log);

            // Initialize the plugin resources.
            PluginResources.Init(this.Assembly);
        }

        // This method is called when the plugin is loaded.
        public override void Load()
        {
            try
            {
                this.Client = new LifxClient();
                if (!this.Client.HasToken)
                {
                    PluginLog.Warning($"LIFX API Token was not found. Please create a text file named '{LifxClient.TokenFileName}' in your Documents folder with your token.");
                }
                else
                {
                    PluginLog.Info("LIFX Plugin initializing...");

                    // Start background update loop
                    Task.Run(async () =>
                    {
                        var isFirstRun = true;
                        while (true)
                        {
                            try
                            {
                                // Fetch groups
                                var groupsList = await this.Client.GetGroupsAsync();
                                this.Groups = groupsList ?? new List<LifxGroup>();

                                // Fetch scenes
                                var scenesList = await this.Client.GetScenesAsync();
                                this.Scenes = scenesList ?? new List<LifxScene>();

                                // Fetch lights
                                var lightsList = await this.Client.GetLightsAsync();
                                this.Lights = lightsList ?? new List<LifxLight>();

                                if (isFirstRun)
                                {
                                    PluginLog.Info($"LIFX Plugin: Initial load completed. Groups: {this.Groups.Count}, Scenes: {this.Scenes.Count}, Lights: {this.Lights.Count}");
                                    isFirstRun = false;
                                }

                                // Notify UI
                                this.GroupsUpdated?.Invoke(this, EventArgs.Empty);
                                this.ScenesUpdated?.Invoke(this, EventArgs.Empty);
                                this.LightsUpdated?.Invoke(this, EventArgs.Empty);
                            }
                            catch (Exception ex)
                            {
                                PluginLog.Error(ex, "Exception in background update loop.");
                            }

                            // Wait before next update
                            await Task.Delay(UpdateInterval);
                        }
                    });
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to initialize LIFX Client in Load()");
            }
        }

        public void TriggerManualRefresh()
        {
            Task.Run(async () =>
            {
                try
                {
                    // Fetch groups
                    var groupsList = await this.Client.GetGroupsAsync();
                    this.Groups = groupsList ?? new List<LifxGroup>();

                    // Fetch scenes
                    var scenesList = await this.Client.GetScenesAsync();
                    this.Scenes = scenesList ?? new List<LifxScene>();

                    // Fetch lights
                    var lightsList = await this.Client.GetLightsAsync();
                    this.Lights = lightsList ?? new List<LifxLight>();

                    // Notify UI
                    this.GroupsUpdated?.Invoke(this, EventArgs.Empty);
                    this.ScenesUpdated?.Invoke(this, EventArgs.Empty);
                    this.LightsUpdated?.Invoke(this, EventArgs.Empty);
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, "Exception in manual refresh.");
                }
            });
        }

        // This method is called when the plugin is unloaded.
        public override void Unload()
        {
        }
    }
}
