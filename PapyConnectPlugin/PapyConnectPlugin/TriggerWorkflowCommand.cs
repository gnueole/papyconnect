namespace Loupedeck.PapyConnectPlugin
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

    // ── Shared config model ──────────────────────────────────────────────────
    public class PapyConfig
    {
        public string N8nGatewayUrl { get; set; } = "http://gronas:5678";
    }

    // ── Shared config loader (singleton) ─────────────────────────────────────
    internal static class N8NTriggerConfig
    {
        private static readonly HttpClient _http = new HttpClient();
        private static List<N8NTrigger> _triggers;
        private static string _filePath;
        private static string _configFilePath;

        public static HttpClient Http => _http;

        public static string GetFilePath()
        {
            if (string.IsNullOrEmpty(_filePath))
            {
                _filePath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "n8n_triggers.json");
            }
            return _filePath;
        }

        public static string GetConfigFilePath()
        {
            if (string.IsNullOrEmpty(_configFilePath))
            {
                _configFilePath = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                    "papyconnect_config.json");
            }
            return _configFilePath;
        }

        public static PapyConfig LoadConfig()
        {
            try
            {
                var path = GetConfigFilePath();
                if (File.Exists(path))
                {
                    var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                    return JsonSerializer.Deserialize<PapyConfig>(File.ReadAllText(path), opts) ?? new PapyConfig();
                }
                else
                {
                    var config = new PapyConfig();
                    var opts = new JsonSerializerOptions { WriteIndented = true };
                    File.WriteAllText(path, JsonSerializer.Serialize(config, opts));
                    return config;
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "N8NTriggerConfig: failed to load config");
                return new PapyConfig();
            }
        }

        public static List<N8NTrigger> Load()
        {
            if (_triggers != null)
                return _triggers;

            try
            {
                var path = GetFilePath();
                if (File.Exists(path))
                {
                    var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                    _triggers = JsonSerializer.Deserialize<List<N8NTrigger>>(
                        File.ReadAllText(path), opts)
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

        public static void Save(List<N8NTrigger> triggers)
        {
            try
            {
                _triggers = triggers;
                var path = GetFilePath();
                var opts = new JsonSerializerOptions { WriteIndented = true };
                File.WriteAllText(path, JsonSerializer.Serialize(triggers, opts));
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "N8NTriggerConfig: failed to save triggers");
            }
        }

        public static N8NTrigger Find(string id)
            => Load().Find(t => t.Id == id);
    }

    // ── Dynamic actions trigger class ─────────────────────────────────────────
    public class PapyConnectActionsCommand : PluginDynamicCommand
    {
        public PapyConnectActionsCommand()
            : base("PapyConnect Actions", "Dynamic actions triggered via n8n", "PapyConnect")
        {
            // Initial parameter loading
            this.RefreshParameters();

            // Asynchronously fetch latest actions from n8n
            _ = this.FetchLatestActionsAsync();
        }

        private void RefreshParameters()
        {
            // Remove parameters from Loupedeck registration
            this.RemoveAllParameters();

            var triggers = N8NTriggerConfig.Load();
            foreach (var trigger in triggers)
            {
                this.AddParameter(trigger.Id, trigger.Name, "PapyConnect");
            }
        }

        private async Task FetchLatestActionsAsync()
        {
            try
            {
                var config = N8NTriggerConfig.LoadConfig();
                string baseUrl = (config.N8nGatewayUrl ?? "http://gronas:5678").TrimEnd('/');

                PluginLog.Info($"[PapyConnect] Fetching actions from {baseUrl}/webhook/get-exposed-actions");
                var resp = await N8NTriggerConfig.Http.GetAsync($"{baseUrl}/webhook/get-exposed-actions");
                if (resp.IsSuccessStatusCode)
                {
                    var content = await resp.Content.ReadAsStringAsync();
                    var opts = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                    var remoteTriggers = JsonSerializer.Deserialize<List<N8NTrigger>>(content, opts);
                    if (remoteTriggers != null && remoteTriggers.Count > 0)
                    {
                        N8NTriggerConfig.Save(remoteTriggers);
                        this.RefreshParameters();
                        this.ParametersChanged();
                        PluginLog.Info($"[PapyConnect] Successfully synchronized dynamic actions.");
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Warning($"[PapyConnect] Failed to synchronize dynamic actions: {ex.Message}");
            }
        }

        protected override void RunCommand(string actionParameter)
        {
            var trigger = N8NTriggerConfig.Find(actionParameter);
            if (trigger == null)
            {
                PluginLog.Warning($"[{actionParameter}] Trigger not found in config.");
                return;
            }

            Task.Run(async () =>
            {
                try
                {
                    PluginLog.Info($"[{actionParameter}] Sending request to {trigger.Url}");
                    var resp = await N8NTriggerConfig.Http.PostAsync(
                        trigger.Url,
                        new System.Net.Http.StringContent("{}", System.Text.Encoding.UTF8, "application/json"));

                    if (resp.IsSuccessStatusCode)
                        PluginLog.Info($"[{actionParameter}] Success");
                    else
                        PluginLog.Warning($"[{actionParameter}] HTTP {resp.StatusCode}");
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, $"[{actionParameter}] Request failed");
                }
            });
        }

        protected override BitmapImage GetCommandImage(string actionParameter, PluginImageSize imageSize)
        {
            if (actionParameter == "netflix" || actionParameter == "disney_plus" ||
                actionParameter == "amazon"  || actionParameter == "youtube" || actionParameter == "spotify")
            {
                return PluginImages.CreateAppButtonImage(imageSize, actionParameter);
            }

            var trigger = N8NTriggerConfig.Find(actionParameter);
            var color = trigger != null
                ? PluginImages.ParseHexColor(trigger.Color)
                : PluginImages.PurpleColor;

            var label = trigger?.Name ?? actionParameter;
            return PluginImages.CreateButtonImage(imageSize, label, color, PluginImages.BlackColor);
        }
    }
}
