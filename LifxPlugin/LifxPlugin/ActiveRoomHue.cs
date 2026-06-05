namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Collections.Generic;
    using System.Threading.Tasks;

    public class ActiveRoomHue : PluginDynamicAdjustment
    {
        // ── Tunable constants ─────────────────────────────────────────────────────
        internal static double HueRange { get; set; } = 360.0;  // degrees — full circle wrap
        internal static double StepPerTick { get; set; } = 5.0;    // degrees per encoder click
        public static string LogFormatGlobal { get; set; } = "[Hue] Global: diff={0:+0;-0}, target={1:0.0}°";
        public static string LogFormatGroup { get; set; } = "[Hue] Group {0}: diff={1:+0;-0}, target={2:0.0}°";
        public static string LogFormatBrightnessGlobal { get; set; } = "[Hue/Brightness] Global Scroll: diff={0:+0;-0}, target={1:0}%";
        public static string LogFormatBrightnessGroup { get; set; } = "[Hue/Brightness] Group {0} Scroll: diff={1:+0;-0}, target={2:0}%";

        private double _globalHue = 0.0;
        private bool _globalInitialized = false;

        private readonly Dictionary<string, double> _groupHues = new Dictionary<string, double>();
        private readonly HashSet<string> _initializedGroups = new HashSet<string>();

        // Coalescers prevent overlapping HTTP calls when dial spins fast
        private RequestCoalescer _globalCoalescer;
        private readonly Dictionary<string, RequestCoalescer> _groupCoalescers = new Dictionary<string, RequestCoalescer>();

        private double _localGlobalBrightness = BrightnessAdjustment.DefaultBrightness;
        private readonly Dictionary<string, double> _localGroupBrightnesses = new Dictionary<string, double>();
        private RequestCoalescer _localGlobalBrightnessCoalescer;
        private readonly Dictionary<string, RequestCoalescer> _localGroupBrightnessCoalescers = new Dictionary<string, RequestCoalescer>();

        public ActiveRoomHue()
            : base(displayName: "Hue", description: "Adjust color (hue) of active room", groupName: "LIFX", hasReset: true)
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

                    // Fetch active room/global brightness for the local cache
                    Task.Run(async () =>
                    {
                        if (plugin.Client != null)
                        {
                            if (string.IsNullOrEmpty(roomId))
                            {
                                this._localGlobalBrightness = await plugin.Client.GetBrightnessAsync();
                            }
                            else
                            {
                                var brightness = await plugin.Client.GetGroupBrightnessAsync(roomId);
                                lock (this._localGroupBrightnesses)
                                {
                                    this._localGroupBrightnesses[roomId] = brightness;
                                }
                            }
                        }
                    });
                }
                this.AdjustmentValueChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in ActiveRoomHue.OnSelectionUpdated");
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
                // Global hue adjustment
                this._globalHue = (this._globalHue + diff * StepPerTick) % HueRange;
                if (this._globalHue < 0)
                {
                    this._globalHue += 360.0;
                }

                PluginLog.Info(string.Format(LogFormatGlobal, diff, this._globalHue));
                this.AdjustmentValueChanged();

                if (this._globalCoalescer == null)
                {
                    this._globalCoalescer = new RequestCoalescer(async () =>
                    {
                        double val;
                        lock (this._groupHues) { val = this._globalHue; }
                        await plugin.Client.SetHueAsync(val);
                    });
                }
                this._globalCoalescer.Trigger();
            }
            else
            {
                // Group-specific hue adjustment
                double currentVal = 0.0;
                lock (this._groupHues)
                {
                    if (this._groupHues.TryGetValue(roomId, out double cachedVal))
                    {
                        currentVal = cachedVal;
                    }
                }

                currentVal = (currentVal + diff * StepPerTick) % HueRange;
                if (currentVal < 0)
                {
                    currentVal += 360.0;
                }

                lock (this._groupHues)
                {
                    this._groupHues[roomId] = currentVal;
                }

                PluginLog.Info(string.Format(LogFormatGroup, roomId, diff, currentVal));
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
                            lock (this._groupHues)
                            {
                                this._groupHues.TryGetValue(capturedRoomId, out val);
                            }
                            await plugin.Client.SetGroupHueAsync(capturedRoomId, val);
                        });
                        this._groupCoalescers[roomId] = coalescer;
                    }
                }
                coalescer.Trigger();
            }
        }

        protected override void RunCommand(String actionParameter)
        {
            // Reset hue to Red (0 degrees)
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return;
            }

            var roomId = plugin.ActiveSelector;

            if (string.IsNullOrEmpty(roomId))
            {
                this._globalHue = 0.0;
                this.AdjustmentValueChanged();

                Task.Run(async () =>
                {
                    await plugin.Client.SetHueAsync(this._globalHue);
                });
            }
            else
            {
                lock (this._groupHues)
                {
                    this._groupHues[roomId] = 0.0;
                }

                this.AdjustmentValueChanged();

                Task.Run(async () =>
                {
                    await plugin.Client.SetGroupHueAsync(roomId, 0.0);
                });
            }
        }

        protected override String GetAdjustmentValue(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return "0°";
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
                            this._globalHue = await plugin.Client.GetHueAsync();
                            this.AdjustmentValueChanged();
                        }
                    });
                }
                return $"{Math.Round(this._globalHue)}°";
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
                            double hue = await plugin.Client.GetGroupHueAsync(roomId);
                            lock (this._groupHues)
                            {
                                this._groupHues[roomId] = hue;
                            }
                            this.AdjustmentValueChanged();
                        }
                    });
                }

                double val = 0.0;
                lock (this._groupHues)
                {
                    if (this._groupHues.TryGetValue(roomId, out double cachedVal))
                    {
                        val = cachedVal;
                    }
                }
                return $"{Math.Round(val)}°";
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
                            return $"{group.Name} Hue";
                        }
                    }
                    else if (plugin.ActiveSelector.StartsWith("id:"))
                    {
                        var lightId = plugin.ActiveSelector.Substring("id:".Length);
                        var light = plugin.Lights.Find(l => l.Id == lightId);
                        if (light != null)
                        {
                            return $"{light.Name} Hue";
                        }
                    }
                }
                return "Hue";
            }
            return "";
        }

        protected override BitmapImage GetAdjustmentImage(String actionParameter, PluginImageSize imageSize)
        {
            return PluginImages.CreateColorWheelImage(imageSize);
        }

        protected override Boolean ProcessEncoderEvent(String actionParameter, DeviceEncoderEvent encoderEvent)
        {
            if (encoderEvent.ControlId == 41 || encoderEvent.ControlId == 0)
            {
                // Roller (vertical scroll) turned: adjust active group's brightness
                this.AdjustBrightness(actionParameter, encoderEvent.Clicks);
                return true;
            }
            else
            {
                // Main Dial turned: adjust hue
                this.ApplyAdjustment(actionParameter, encoderEvent.Clicks);
                return true;
            }
        }

        private void AdjustBrightness(string actionParameter, int diff)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return;
            }

            var roomId = plugin.ActiveSelector;

            if (string.IsNullOrEmpty(roomId))
            {
                this._localGlobalBrightness += diff * BrightnessAdjustment.StepPerTick;
                this._localGlobalBrightness = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(BrightnessAdjustment.MaxBrightness, this._localGlobalBrightness));
                
                PluginLog.Info(string.Format(LogFormatBrightnessGlobal, diff, this._localGlobalBrightness * 100));

                if (this._localGlobalBrightnessCoalescer == null)
                {
                    this._localGlobalBrightnessCoalescer = new RequestCoalescer(async () =>
                    {
                        await plugin.Client.SetBrightnessAsync(this._localGlobalBrightness);
                    });
                }
                this._localGlobalBrightnessCoalescer.Trigger();
            }
            else
            {
                double currentVal = BrightnessAdjustment.DefaultBrightness;
                lock (this._localGroupBrightnesses)
                {
                    if (!this._localGroupBrightnesses.TryGetValue(roomId, out currentVal))
                    {
                        currentVal = BrightnessAdjustment.DefaultBrightness;
                    }
                }

                currentVal += diff * BrightnessAdjustment.StepPerTick;
                currentVal = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(BrightnessAdjustment.MaxBrightness, currentVal));

                lock (this._localGroupBrightnesses)
                {
                    this._localGroupBrightnesses[roomId] = currentVal;
                }

                PluginLog.Info(string.Format(LogFormatBrightnessGroup, roomId, diff, currentVal * 100));

                RequestCoalescer coalescer;
                lock (this._localGroupBrightnessCoalescers)
                {
                    if (!this._localGroupBrightnessCoalescers.TryGetValue(roomId, out coalescer))
                    {
                        var capturedRoomId = roomId;
                        coalescer = new RequestCoalescer(async () =>
                        {
                            double val;
                            lock (this._localGroupBrightnesses)
                            {
                                this._localGroupBrightnesses.TryGetValue(capturedRoomId, out val);
                            }
                            await plugin.Client.SetGroupBrightnessAsync(capturedRoomId, val);
                        });
                        this._localGroupBrightnessCoalescers[roomId] = coalescer;
                    }
                }
                coalescer.Trigger();
            }
        }
    }
}
