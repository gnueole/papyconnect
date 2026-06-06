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
        public string Id            { get; set; }
        public string Name          { get; set; }
        public string Url           { get; set; }
        public string Color         { get; set; }
        public string IconUrl       { get; set; }
        public string IconActiveUrl { get; set; }
        public string State         { get; set; }
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

        public static string GetBaseDirectory()
        {
            var dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                "PapyConnect");
            if (!Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
            }
            return dir;
        }

        public static string GetFilePath()
        {
            if (string.IsNullOrEmpty(_filePath))
            {
                _filePath = Path.Combine(GetBaseDirectory(), "n8n_triggers.json");
            }
            return _filePath;
        }

        public static string GetConfigFilePath()
        {
            if (string.IsNullOrEmpty(_configFilePath))
            {
                _configFilePath = Path.Combine(GetBaseDirectory(), "config.json");
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

        public static string GetCacheDirectory()
        {
            var dir = Path.Combine(GetBaseDirectory(), "Cache");
            if (!Directory.Exists(dir))
            {
                Directory.CreateDirectory(dir);
            }
            return dir;
        }

        public static string GetLocalIconPath(string id, bool active)
        {
            var suffix = active ? "_active.png" : ".png";
            return Path.Combine(GetCacheDirectory(), $"{id}{suffix}");
        }

        public static async Task EnsureIconCachedAsync(string url, string localPath)
        {
            if (string.IsNullOrEmpty(url)) return;
            try
            {
                if (!File.Exists(localPath))
                {
                    PluginLog.Info($"[PapyConnect] Downloading icon from {url} to {localPath}");
                    var bytes = await _http.GetByteArrayAsync(url);
                    if (bytes != null && bytes.Length > 0)
                    {
                        File.WriteAllBytes(localPath, bytes);
                        PluginLog.Info($"[PapyConnect] Icon cached successfully at {localPath}");
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Warning($"[PapyConnect] Failed to cache icon from {url}: {ex.Message}");
            }
        }
    }

    // ── Dynamic actions trigger class ─────────────────────────────────────────
    public class PapyConnectActionsCommand : PluginDynamicCommand
    {
        public PapyConnectActionsCommand()
            : base()
        {
            // Initial parameter loading
            this.RefreshParameters();

            // Asynchronously fetch latest actions from n8n
            _ = this.FetchLatestActionsAsync();
        }

        protected override string GetCommandDisplayName(string actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter))
            {
                return "PapyConnect Action";
            }

            var trigger = N8NTriggerConfig.Find(actionParameter);
            return trigger != null ? trigger.Name : "Action";
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

                        // Cache icons in background and notify when ready
                        foreach (var trigger in remoteTriggers)
                        {
                            var t = trigger;
                            _ = Task.Run(async () =>
                            {
                                var pathInactive = N8NTriggerConfig.GetLocalIconPath(t.Id, false);
                                var pathActive = N8NTriggerConfig.GetLocalIconPath(t.Id, true);

                                var taskInactive = N8NTriggerConfig.EnsureIconCachedAsync(t.IconUrl, pathInactive);
                                var taskActive = N8NTriggerConfig.EnsureIconCachedAsync(t.IconActiveUrl, pathActive);

                                await Task.WhenAll(taskInactive, taskActive);

                                // Request UI update for this specific action button
                                this.ActionImageChanged(t.Id);
                            });
                        }
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
                    {
                        PluginLog.Info($"[{actionParameter}] Success");
                        // Immediately sync states after action triggered
                        _ = this.FetchLatestActionsAsync();
                    }
                    else
                    {
                        PluginLog.Warning($"[{actionParameter}] HTTP {resp.StatusCode}");
                    }
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, $"[{actionParameter}] Request failed");
                }
            });
        }

        protected override BitmapImage GetCommandImage(string actionParameter, PluginImageSize imageSize)
        {
            var trigger = N8NTriggerConfig.Find(actionParameter);
            if (trigger != null)
            {
                var isActive = string.Equals(trigger.State, "active", StringComparison.OrdinalIgnoreCase);
                var localPath = N8NTriggerConfig.GetLocalIconPath(trigger.Id, isActive);

                if (File.Exists(localPath))
                {
                    try
                    {
                        var bytes = File.ReadAllBytes(localPath);
                        if (bytes != null && bytes.Length > 0)
                        {
                            var img = BitmapImage.FromArray(bytes);
                            if (img != null)
                            {
                                return img;
                            }
                        }
                    }
                    catch (Exception ex)
                    {
                        PluginLog.Error(ex, $"[PapyConnect] Error loading cached image from {localPath}");
                    }
                }

                // Fallback to text/color button if image is not ready or fails
                var color = PluginImages.ParseHexColor(trigger.Color);
                var label = trigger.Name;
                if (isActive)
                {
                    return PluginImages.CreateButtonImage(imageSize, label, PluginImages.BlackColor, color);
                }
                else
                {
                    return PluginImages.CreateButtonImage(imageSize, label, color, PluginImages.BlackColor);
                }
            }

            return PluginImages.CreateButtonImage(imageSize, actionParameter, PluginImages.PurpleColor, PluginImages.BlackColor);
        }
    }
}
