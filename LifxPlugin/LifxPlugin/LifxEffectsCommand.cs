namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Collections.Generic;
    using System.Linq;
    using System.Threading.Tasks;

    public class LifxEffectsCommand : PluginDynamicCommand
    {
        public LifxEffectsCommand()
            : base()
        {
        }

        // ── Color palette ─────────────────────────────────────────────────────────
        private static readonly Dictionary<string, BitmapColor> ColorMap =
            new Dictionary<string, BitmapColor>(StringComparer.OrdinalIgnoreCase)
            {
                ["red"]    = new BitmapColor(255, 50,  50),
                ["green"]  = new BitmapColor(50,  255, 50),
                ["blue"]   = new BitmapColor(50,  150, 255),
                ["purple"] = PluginImages.PurpleColor,
            };

        // ── Single source of truth ────────────────────────────────────────────────
        // Every key (exact and prefix-expanded) lives here once.
        // Adding an effect = one new line. No other code to touch.
        internal record EffectDef(
            string DisplayName,
            Func<PluginImageSize, BitmapImage> Image,
            Func<LifxPlugin, string, double, Task<bool>> Run
        );

        internal static readonly Dictionary<string, EffectDef> Effects = BuildEffects();

        private static Dictionary<string, EffectDef> BuildEffects()
        {
            var d = new Dictionary<string, EffectDef>(StringComparer.Ordinal)
            {
                //  key          display name       image factory                                   command
                ["stop"]    = new("Effects off",    sz => PluginImages.CreateEffectsOffImage(sz),   (p, s, t) => p.Client.StopEffectsAsync(s)),
                ["off"]     = new("Effects off",    sz => PluginImages.CreateEffectsOffImage(sz),   (p, s, t) => p.Client.StopEffectsAsync(s)),
                ["breathe"] = new("Breathe Effect", sz => PluginImages.CreateBreatheEffectImage(sz),(p, s, t) => p.Client.PlayBreatheEffectAsync("purple", t, s)),
                ["pulse"]   = new("Pulse Purple",   sz => PluginImages.CreatePulseEffectImage(sz),  (p, s, t) => p.Client.PlayPulseEffectAsync("purple", t, s)),
                ["move"]    = new("Move Effect",    sz => PluginImages.CreateMoveEffectImage(sz),   (p, s, t) => p.Client.PlayMoveEffectAsync(t, s)),
                ["morph"]   = new("Morph Effect",   sz => PluginImages.CreateMorphEffectImage(sz),  (p, s, t) => p.Client.PlayMorphEffectAsync(t, s)),
                ["flame"]   = new("Flame Effect",   sz => PluginImages.CreateFlameEffectImage(sz),  (p, s, t) => p.Client.PlayFlameEffectAsync(t, s)),
                ["clouds"]  = new("Clouds Effect",  sz => PluginImages.CreateCloudsEffectImage(sz), (p, s, t) => p.Client.PlayCloudsEffectAsync(t, s)),
                ["cycle"]   = new("Cycle",          sz => PluginImages.CreateCycleEffectImage(sz),  (p, s, t) => p.Client.PlayCycleEffectAsync(s)),
                ["sunrise"] = new("Sunrise Effect", sz => PluginImages.CreateSunriseEffectImage(sz),(p, s, t) => p.Client.PlaySunriseSunsetCompatAsync(true,  t, s, p.Lights)),
                ["sunset"]  = new("Sunset Effect",  sz => PluginImages.CreateSunsetEffectImage(sz), (p, s, t) => p.Client.PlaySunriseSunsetCompatAsync(false, t, s, p.Lights)),
            };

            // Expand breathe:COLOR and pulse:COLOR from ColorMap — no hardcoded variants
            foreach (var (colorName, color) in ColorMap)
            {
                var label = Capitalize(colorName);
                var c = color; // capture for lambda
                d[$"breathe:{colorName}"] = new($"Breathe {label}", sz => PluginImages.CreateBreatheEffectImage(sz, c), (p, s, t) => p.Client.PlayBreatheEffectAsync(colorName, t, s));
                d[$"pulse:{colorName}"]   = new($"Pulse {label}",   sz => PluginImages.CreatePulseEffectImage(sz, c),   (p, s, t) => p.Client.PlayPulseEffectAsync(colorName, t, s));
            }

            return d;
        }

        private static string Capitalize(string s) =>
            string.IsNullOrEmpty(s) ? s : char.ToUpper(s[0]) + s.Substring(1);

        // ── OnLoad: driven entirely from Effects ──────────────────────────────────
        protected override bool OnLoad()
        {
            foreach (var (key, def) in Effects)
            {
                this.AddParameter(key, def.DisplayName, "LIFX Effects");
            }

            this.ParametersChanged();
            return true;
        }

        // ── RunCommand: single map lookup, no branches ────────────────────────────
        protected override void RunCommand(String actionParameter)
        {
            if (string.IsNullOrEmpty(actionParameter)) return;

            var plugin = (LifxPlugin)this.Plugin;
            if (plugin == null || plugin.Client == null) return;

            plugin.LastEffectParameter = actionParameter;

            var selector = plugin.ActiveSelector;
            var period   = plugin.EffectPeriod;

            if (!Effects.TryGetValue(actionParameter, out var def)) return;

            Task.Run(async () =>
            {
                if (await def.Run(plugin, selector, period))
                    plugin.TriggerManualRefresh();
            });
        }

        // ── GetCommandDisplayName: single map lookup ───────────────────────────────
        protected override String GetCommandDisplayName(String actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter)) return "LIFX Effect";

            return Effects.TryGetValue(actionParameter, out var def) ? def.DisplayName : actionParameter;
        }

        // ── GetCommandImage: single map lookup ────────────────────────────────────
        protected override BitmapImage GetCommandImage(String actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter) || imageSize == PluginImageSize.None) return null;

            return Effects.TryGetValue(actionParameter, out var def) ? def.Image(imageSize) : null;
        }
    }
}
