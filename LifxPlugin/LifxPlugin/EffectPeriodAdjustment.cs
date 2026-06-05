namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Threading.Tasks;

    public class EffectPeriodAdjustment : PluginDynamicAdjustment
    {
        // ── Tunable constants ─────────────────────────────────────────────────────
        internal static double DefaultPeriod { get; set; } = 2.0;   // seconds — initial / reset value
        internal static double MinPeriod { get; set; } = 0.5;   // seconds — slowest allowed effect
        internal static double MaxPeriod { get; set; } = 10.0;  // seconds — fastest allowed effect
        internal static double StepPerTick { get; set; } = 0.1;   // seconds added/removed per encoder click
        internal static int CoalesceDelayMs { get; set; } = 300;  // ms — throttle rapid encoder turns before re-triggering
        public static string LogFormatAdjustment { get; set; } = "[Effect Speed] diff={0:+0;-0}, target={1:0.0}s";
        public static string LogFormatRetrigger { get; set; } = "[Effect Speed] Re-triggering last effect '{0}' at period {1:0.0}s...";
        public static string LogReset { get; set; } = "[Effect Speed] Reset to {0:0.0}s";

        private RequestCoalescer _coalescer;

        public EffectPeriodAdjustment()
            : base(displayName: "Effect Speed", description: "Adjust speed of LIFX light effects", groupName: "LIFX", hasReset: true)
        {
        }

        protected override bool OnLoad()
        {
            this.AddParameter(string.Empty, "Effect Speed", "LIFX");
            return true;
        }

        protected override void ApplyAdjustment(String actionParameter, Int32 diff)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return;
            }

            plugin.EffectPeriod += diff * StepPerTick;
            PluginLog.Info(string.Format(LogFormatAdjustment, diff, plugin.EffectPeriod));
            this.AdjustmentValueChanged();

            if (this._coalescer == null)
            {
                this._coalescer = new RequestCoalescer(async () =>
                {
                    if (plugin.Client == null || string.IsNullOrEmpty(plugin.LastEffectParameter))
                    {
                        return;
                    }

                    var roomId = plugin.ActiveSelector;
                    var param  = plugin.LastEffectParameter;
                    var period = plugin.EffectPeriod;

                    PluginLog.Info(string.Format(LogFormatRetrigger, param, period));

                    if (LifxEffectsCommand.Effects.TryGetValue(param, out var def))
                    {
                        await def.Run(plugin, roomId, period);
                    }
                }, CoalesceDelayMs);
            }
            this._coalescer.Trigger();
        }

        protected override void RunCommand(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null)
            {
                return;
            }

            plugin.EffectPeriod = DefaultPeriod;
            PluginLog.Info(string.Format(LogReset, DefaultPeriod));
            this.AdjustmentValueChanged();

            if (this._coalescer != null)
            {
                this._coalescer.Trigger();
            }
        }

        protected override String GetAdjustmentValue(String actionParameter)
        {
            var plugin = (LifxPlugin)this.Plugin;
            return plugin == null ? $"{DefaultPeriod:0.0}s" : $"{plugin.EffectPeriod:0.0}s";
        }

        protected override BitmapImage GetAdjustmentImage(String actionParameter, PluginImageSize imageSize)
        {
            return PluginImages.CreateBrightnessGaugeImage(imageSize);
        }

        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            return PluginImages.CreateBulbButtonImage(imageSize, false, PluginImages.PurpleColor, PluginImages.BlackColor);
        }

        protected override Boolean ProcessEncoderEvent(String actionParameter, DeviceEncoderEvent encoderEvent)
        {
            this.ApplyAdjustment(actionParameter, encoderEvent.Clicks);
            return true;
        }
    }
}
