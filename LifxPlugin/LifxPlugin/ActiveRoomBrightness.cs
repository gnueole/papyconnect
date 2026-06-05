namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Collections.Generic;
    using System.Threading.Tasks;

    public class ActiveRoomBrightness : PluginDynamicAdjustment
    {
        public static string LogFormatGlobal { get; set; } = "[Brightness] Global: diff={0:+0;-0}, target={1:0}%";
        public static string LogFormatGroup { get; set; } = "[Brightness] Group {0}: diff={1:+0;-0}, target={2:0}%";
        public static string LogResetGlobal { get; set; } = "[Brightness] Reset global brightness to 100%";
        public static string LogResetGroup { get; set; } = "[Brightness] Reset group {0} brightness to 100%";

        private double _globalBrightness = BrightnessAdjustment.DefaultBrightness;
        private bool _globalInitialized = false;

        private readonly Dictionary<string, double> _groupBrightnesses = new Dictionary<string, double>();
        private readonly HashSet<string> _initializedGroups = new HashSet<string>();

        // Coalescers prevent overlapping HTTP calls when dial spins fast
        private RequestCoalescer _globalCoalescer;
        private readonly Dictionary<string, RequestCoalescer> _groupCoalescers = new Dictionary<string, RequestCoalescer>();

        public ActiveRoomBrightness()
            : base(displayName: "Active Brightness", description: "Adjust brightness of active room", groupName: "LIFX", hasReset: true)
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
                var plugin = (LifxPlugin)this.Plugin;
                if (plugin != null)
                {
                    var roomId = plugin.ActiveSelector;
                    lock (this._initializedGroups)
                    {
                        if (!string.IsNullOrEmpty(roomId))
                        {
                            this._initializedGroups.Remove(roomId);
                        }
                        else
                        {
                            this._globalInitialized = false;
                        }
                    }
                }
                this.AdjustmentValueChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in ActiveRoomBrightness.OnSelectionUpdated");
            }
        }

        protected override void ApplyAdjustment(String actionParameter, Int32 diff)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return;
            }

            var roomId = plugin.ActiveSelector;

            if (string.IsNullOrEmpty(roomId))
            {
                // Global brightness adjustment
                this._globalBrightness += diff * BrightnessAdjustment.StepPerTick;
                this._globalBrightness = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(BrightnessAdjustment.MaxBrightness, this._globalBrightness));
                var targetBrightness = this._globalBrightness;

                PluginLog.Info(string.Format(LogFormatGlobal, diff, targetBrightness * 100));
                this.AdjustmentValueChanged();

                if (this._globalCoalescer == null)
                {
                    this._globalCoalescer = new RequestCoalescer(async () =>
                    {
                        await plugin.Client.SetBrightnessAsync(this._globalBrightness);
                    });
                }
                this._globalCoalescer.Trigger();
            }
            else
            {
                // Group-specific brightness adjustment
                double currentVal = BrightnessAdjustment.DefaultBrightness;
                lock (this._groupBrightnesses)
                {
                    if (this._groupBrightnesses.TryGetValue(roomId, out double cachedVal))
                    {
                        currentVal = cachedVal;
                    }
                }

                currentVal += diff * BrightnessAdjustment.StepPerTick;
                currentVal = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(BrightnessAdjustment.MaxBrightness, currentVal));

                lock (this._groupBrightnesses)
                {
                    this._groupBrightnesses[roomId] = currentVal;
                }

                PluginLog.Info(string.Format(LogFormatGroup, roomId, diff, currentVal * 100));
                this.AdjustmentValueChanged();

                RequestCoalescer coalescer;
                lock (this._groupCoalescers)
                {
                    if (!this._groupCoalescers.TryGetValue(roomId, out coalescer))
                    {
                        var capturedRoomId = roomId;
                        coalescer = new RequestCoalescer(async () =>
                        {
                            double val;
                            lock (this._groupBrightnesses)
                            {
                                this._groupBrightnesses.TryGetValue(capturedRoomId, out val);
                            }
                            await plugin.Client.SetGroupBrightnessAsync(capturedRoomId, val);
                        });
                        this._groupCoalescers[roomId] = coalescer;
                    }
                }
                coalescer.Trigger();
            }
        }

        protected override void RunCommand(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return;
            }

            var roomId = plugin.ActiveSelector;

            if (string.IsNullOrEmpty(roomId))
            {
                // Reset global brightness to 100%
                this._globalBrightness = BrightnessAdjustment.MaxBrightness;
                PluginLog.Info(LogResetGlobal);
                this.AdjustmentValueChanged();

                Task.Run(async () => await plugin.Client.SetBrightnessAsync(1.0));
            }
            else
            {
                // Reset group brightness to 100%
                lock (this._groupBrightnesses)
                {
                    this._groupBrightnesses[roomId] = BrightnessAdjustment.MaxBrightness;
                }

                PluginLog.Info(string.Format(LogResetGroup, roomId));
                this.AdjustmentValueChanged();

                Task.Run(async () => await plugin.Client.SetGroupBrightnessAsync(roomId, 1.0));
            }
        }

        protected override String GetAdjustmentValue(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return "50%";
            }

            var roomId = plugin.ActiveSelector;

            if (string.IsNullOrEmpty(roomId))
            {
                if (!this._globalInitialized)
                {
                    this._globalInitialized = true;
                    Task.Run(async () =>
                    {
                        if (plugin?.Client != null)
                        {
                            this._globalBrightness = await plugin.Client.GetBrightnessAsync();
                            this.AdjustmentValueChanged();
                        }
                    });
                }
                return $"{Math.Round(this._globalBrightness * 100)}%";
            }
            else
            {
                bool shouldInit = false;
                lock (this._initializedGroups)
                {
                    if (!this._initializedGroups.Contains(roomId))
                    {
                        this._initializedGroups.Add(roomId);
                        shouldInit = true;
                    }
                }

                if (shouldInit)
                {
                    Task.Run(async () =>
                    {
                        if (plugin?.Client != null)
                        {
                            double brightness = await plugin.Client.GetGroupBrightnessAsync(roomId);
                            lock (this._groupBrightnesses)
                            {
                                this._groupBrightnesses[roomId] = brightness;
                            }
                            this.AdjustmentValueChanged();
                        }
                    });
                }

                double val = BrightnessAdjustment.DefaultBrightness;
                lock (this._groupBrightnesses)
                {
                    if (this._groupBrightnesses.TryGetValue(roomId, out double cachedVal))
                    {
                        val = cachedVal;
                    }
                }
                return $"{Math.Round(val * 100)}%";
            }
        }

        protected override String GetAdjustmentDisplayName(String actionParameter, PluginImageSize imageSize)
        {
            if (imageSize == PluginImageSize.None)
            {
                var plugin = (LifxPlugin)this.Plugin;
                if (plugin != null && !string.IsNullOrEmpty(plugin.ActiveSelector))
                {
                    if (plugin.ActiveSelector.StartsWith("group_id:"))
                    {
                        var groupId = plugin.ActiveSelector.Substring("group_id:".Length);
                        var group = plugin.Groups.Find(g => g.Id == groupId);
                        if (group != null)
                        {
                            return $"{group.Name} Brightness";
                        }
                    }
                    else if (plugin.ActiveSelector.StartsWith("id:"))
                    {
                        var lightId = plugin.ActiveSelector.Substring("id:".Length);
                        var light = plugin.Lights.Find(l => l.Id == lightId);
                        if (light != null)
                        {
                            return $"{light.Name} Brightness";
                        }
                    }
                }
                return "Active Brightness";
            }
            return "";
        }

        protected override BitmapImage GetAdjustmentImage(String actionParameter, PluginImageSize imageSize)
        {
            return PluginImages.CreateBrightnessGaugeImage(imageSize);
        }

        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            var plugin = (LifxPlugin)this.Plugin;
            var isGroup = plugin == null || string.IsNullOrEmpty(plugin.ActiveSelector) || plugin.ActiveSelector.StartsWith("group_id:");
            return PluginImages.CreateBulbButtonImage(imageSize, isGroup, PluginImages.PurpleColor, PluginImages.BlackColor);
        }

        protected override Boolean ProcessEncoderEvent(String actionParameter, DeviceEncoderEvent encoderEvent)
        {
            // Both the Roller (vertical scroll, ControlId 41/0) and the Contextual Dial (ControlId 42/1)
            // will adjust the brightness in this mode.
            this.ApplyAdjustment(actionParameter, encoderEvent.Clicks);
            return true;
        }
    }
}

