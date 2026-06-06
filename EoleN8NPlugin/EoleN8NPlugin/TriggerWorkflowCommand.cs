namespace Loupedeck.EoleN8NPlugin
{
    using System;
    using System.Collections.Generic;
    using System.IO;
    using System.Net.Http;
    using System.Text.Json;
    using System.Threading.Tasks;

    // ── Shared model ──────────────────────────────────────────────────────────
    public class N8NTrigger
    {
        public string Id    { get; set; }
        public string Name  { get; set; }
        public string Url   { get; set; }
        public string Color { get; set; }
    }

    // ── Shared config loader (singleton) ─────────────────────────────────────
    internal static class N8NTriggerConfig
    {
        private static readonly HttpClient _http = new HttpClient();
        private static List<N8NTrigger> _triggers;
        private static string _filePath;

        public static HttpClient Http => _http;

        public static List<N8NTrigger> Load()
        {
            if (_triggers != null)
                return _triggers;

            try
            {
                _filePath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "n8n_triggers.json");

                if (File.Exists(_filePath))
                {
                    var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                    _triggers = JsonSerializer.Deserialize<List<N8NTrigger>>(
                        File.ReadAllText(_filePath), opts)
                        ?? new List<N8NTrigger>();
                }
                else
                {
                    _triggers = new List<N8NTrigger>();
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "N8NTriggerConfig: failed to load triggers");
                _triggers = new List<N8NTrigger>();
            }

            return _triggers;
        }

        public static N8NTrigger Find(string id)
            => Load().Find(t => t.Id == id);
    }

    // ── Base class for individual trigger commands ────────────────────────────
    public abstract class N8NTriggerCommandBase : PluginDynamicCommand
    {
        private readonly string _triggerId;

        protected N8NTriggerCommandBase(string displayName, string description, string triggerId)
            : base(displayName, description, "PapyConnect")
        {
            _triggerId = triggerId;
        }

        protected override void RunCommand(string actionParameter)
        {
            var trigger = N8NTriggerConfig.Find(_triggerId);
            if (trigger == null)
            {
                PluginLog.Warning($"[{_triggerId}] Trigger not found in config.");
                return;
            }

            Task.Run(async () =>
            {
                try
                {
                    PluginLog.Info($"[{_triggerId}] Sending request to {trigger.Url}");
                    var resp = await N8NTriggerConfig.Http.PostAsync(
                        trigger.Url,
                        new System.Net.Http.StringContent("{}", System.Text.Encoding.UTF8, "application/json"));

                    if (resp.IsSuccessStatusCode)
                        PluginLog.Info($"[{_triggerId}] Success");
                    else
                        PluginLog.Warning($"[{_triggerId}] HTTP {resp.StatusCode}");
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, $"[{_triggerId}] Request failed");
                }
            });
        }

        protected override BitmapImage GetCommandImage(string actionParameter, PluginImageSize imageSize)
        {
            // Use brand icon for streaming apps, colored tile for others
            if (_triggerId == "netflix" || _triggerId == "disney_plus" ||
                _triggerId == "amazon"  || _triggerId == "youtube")
            {
                return PluginImages.CreateAppButtonImage(imageSize, _triggerId);
            }

            var trigger = N8NTriggerConfig.Find(_triggerId);
            var color = trigger != null
                ? PluginImages.ParseHexColor(trigger.Color)
                : PluginImages.PurpleColor;

            var label = trigger?.Name ?? _triggerId;
            return PluginImages.CreateButtonImage(imageSize, label, color, PluginImages.BlackColor);
        }
    }

    // ── One concrete class per trigger ────────────────────────────────────────

    public class MovieModeCommand : N8NTriggerCommandBase
    {
        public MovieModeCommand()
            : base("Movie Mode", "Dim lights and turn on the TV", "movie_mode") { }
    }

    public class NetflixCommand : N8NTriggerCommandBase
    {
        public NetflixCommand()
            : base("Netflix", "Launch Netflix on the TV", "netflix") { }
    }

    public class DisneyPlusCommand : N8NTriggerCommandBase
    {
        public DisneyPlusCommand()
            : base("Disney+", "Launch Disney+ on the TV", "disney_plus") { }
    }

    public class AmazonCommand : N8NTriggerCommandBase
    {
        public AmazonCommand()
            : base("Amazon", "Launch Amazon Prime Video on the TV", "amazon") { }
    }

    public class YouTubeCommand : N8NTriggerCommandBase
    {
        public YouTubeCommand()
            : base("YouTube", "Launch YouTube on the TV", "youtube") { }
    }
}
