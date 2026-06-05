namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Collections.Generic;
    using System.Threading.Tasks;

    public class BrightnessAdjustment : PluginDynamicAdjustment
    {
        // ── Tunable constants ─────────────────────────────────────────────────────
        internal static double DefaultBrightness { get; set; } = 0.5;   // initial / fallback value (0–1)
        internal static double MaxBrightness { get; set; } = 1.0;   // reset target — full brightness
        internal static double MinBrightness { get; set; } = 0.0;   // floor
        internal static double StepPerTick { get; set; } = 0.02;  // brightness change per encoder click
        internal static int CoalesceDelayMs { get; set; } = 350;   // ms — throttle rapid encoder turns before sending HTTP
        internal static string LogFormatAll { get; set; } = "[Brightness/All] diff={0:+0;-0}, target={1:0}%";
        internal static string LogFormatGroup { get; set; } = "[Brightness/Group {0}] diff={1:+0;-0}, target={2:0}%";

        private double _cachedBrightness = DefaultBrightness;
        private bool _isInitialized = false;

        private readonly Dictionary<string, double> _groupBrightnesses = new Dictionary<string, double>();
        private readonly HashSet<string> _initializedGroups = new HashSet<string>();

        // Coalescers prevent overlapping HTTP calls when dial spins fast
        private RequestCoalescer _globalCoalescer;
        private readonly Dictionary<string, RequestCoalescer> _groupCoalescers = new Dictionary<string, RequestCoalescer>();

        public BrightnessAdjustment()
            : base(displayName: "All Brightness", description: "Adjust room or light brightness", groupName: "LIFX", hasReset: true)
        {
        }

        protected override bool OnLoad()
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin != null)
            {
                plugin.GroupsUpdated += this.OnGroupsUpdated;

                // Load groups if already populated
                if (plugin.Groups.Count > 0)
                {
                    this.OnGroupsUpdated(this, EventArgs.Empty);
                }
                else
                {
                    // Register default "All Lights" parameter
                    this.AddParameter(string.Empty, "All Brightness", "LIFX");
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

                // Register global action
                this.AddParameter(string.Empty, "All Brightness", "LIFX");

                this.ParametersChanged();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error in BrightnessAdjustment.OnGroupsUpdated");
            }
        }

        protected override void ApplyAdjustment(String actionParameter, Int32 diff)
        {
            var plugin = (LifxPlugin)this.Plugin;

            if (string.IsNullOrEmpty(actionParameter))
            {
                // Global brightness adjustment
                this._cachedBrightness += diff * StepPerTick;
                this._cachedBrightness = Math.Max(MinBrightness, Math.Min(MaxBrightness, this._cachedBrightness));

                PluginLog.Info(string.Format(LogFormatAll, diff, this._cachedBrightness * 100));
                this.AdjustmentValueChanged();

                if (this._globalCoalescer == null)
                {
                    this._globalCoalescer = new RequestCoalescer(async () =>
                    {
                        await plugin.Client.SetBrightnessAsync(this._cachedBrightness);
                    });
                }
                this._globalCoalescer.Trigger();
            }
            else
            {
                // Group-specific brightness adjustment
                double currentVal = DefaultBrightness;
                lock (this._groupBrightnesses)
                {
                    if (this._groupBrightnesses.TryGetValue(actionParameter, out double cachedVal))
                    {
                        currentVal = cachedVal;
                    }
                }

                currentVal += diff * StepPerTick;
                currentVal = Math.Max(MinBrightness, Math.Min(MaxBrightness, currentVal));

                lock (this._groupBrightnesses)
                {
                    this._groupBrightnesses[actionParameter] = currentVal;
                }

                PluginLog.Info(string.Format(LogFormatGroup, actionParameter, diff, currentVal * 100));
                this.AdjustmentValueChanged(actionParameter);

                RequestCoalescer coalescer;
                lock (this._groupCoalescers)
                {
                    if (!this._groupCoalescers.TryGetValue(actionParameter, out coalescer))
                    {
                        var capturedParam = actionParameter;
                        coalescer = new RequestCoalescer(async () =>
                        {
                            double val;
                            lock (this._groupBrightnesses)
                            {
                                this._groupBrightnesses.TryGetValue(capturedParam, out val);
                            }
                            await plugin.Client.SetGroupBrightnessAsync(capturedParam, val);
                        });
                        this._groupCoalescers[actionParameter] = coalescer;
                    }
                }
                coalescer.Trigger();
            }
        }

        protected override void RunCommand(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;

            if (string.IsNullOrEmpty(actionParameter))
            {
                // Reset global brightness to 100%
                this._cachedBrightness = MaxBrightness;
                this.AdjustmentValueChanged();

                Task.Run(async () =>
                {
                    await plugin.Client.SetBrightnessAsync(this._cachedBrightness);
                });
            }
            else
            {
                // Reset group brightness to 100%
                lock (this._groupBrightnesses)
                {
                    this._groupBrightnesses[actionParameter] = MaxBrightness;
                }

                this.AdjustmentValueChanged(actionParameter);

                Task.Run(async () =>
                {
                    await plugin.Client.SetGroupBrightnessAsync(actionParameter, MaxBrightness);
                });
            }
        }

        protected override String GetAdjustmentValue(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;

            if (string.IsNullOrEmpty(actionParameter))
            {
                if (!this._isInitialized)
                {
                    this._isInitialized = true;
                    Task.Run(async () =>
                    {
                        if (plugin?.Client != null)
                        {
                            this._cachedBrightness = await plugin.Client.GetBrightnessAsync();
                            this.AdjustmentValueChanged();
                        }
                    });
                }
                return $"{Math.Round(this._cachedBrightness * 100)}%";
            }
            else
            {
                bool shouldInit = false;
                lock (this._initializedGroups)
                {
                    if (!this._initializedGroups.Contains(actionParameter))
                    {
                        this._initializedGroups.Add(actionParameter);
                        shouldInit = true;
                    }
                }

                if (shouldInit)
                {
                    Task.Run(async () =>
                    {
                        if (plugin?.Client != null)
                        {
                            double brightness = await plugin.Client.GetGroupBrightnessAsync(actionParameter);
                            lock (this._groupBrightnesses)
                            {
                                this._groupBrightnesses[actionParameter] = brightness;
                            }
                            this.AdjustmentValueChanged(actionParameter);
                        }
                    });
                }

                double val = DefaultBrightness;
                lock (this._groupBrightnesses)
                {
                    if (this._groupBrightnesses.TryGetValue(actionParameter, out double cachedVal))
                    {
                        val = cachedVal;
                    }
                }
                return $"{Math.Round(val * 100)}%";
            }
        }

        protected override BitmapImage GetAdjustmentImage(String actionParameter, PluginImageSize imageSize)
        {
            return PluginImages.CreateBrightnessGaugeImage(imageSize);
        }

        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            var isGroup = !string.IsNullOrEmpty(actionParameter);
            return PluginImages.CreateBulbButtonImage(imageSize, isGroup, PluginImages.PurpleColor, PluginImages.BlackColor);
        }

        protected override Boolean ProcessEncoderEvent(String actionParameter, DeviceEncoderEvent encoderEvent)
        {
            this.ApplyAdjustment(actionParameter, encoderEvent.Clicks);
            return true;
        }
    }
}
