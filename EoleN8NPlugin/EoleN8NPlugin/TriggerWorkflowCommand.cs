namespace Loupedeck.EoleN8NPlugin
{
    using System;
    using System.Collections.Generic;
    using System.IO;
    using System.Net.Http;
    using System.Text.Json;
    using System.Threading.Tasks;

    public class N8NTrigger
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public string Url { get; set; }
        public string Color { get; set; }
    }

    public class TriggerWorkflowCommand : PluginDynamicCommand
    {
        private static readonly HttpClient _httpClient = new HttpClient();
        private readonly List<N8NTrigger> _triggers = new List<N8NTrigger>();
        private string _triggersFilePath;

        public TriggerWorkflowCommand()
            : base("n8n Trigger", "Triggers an n8n webhook workflow", "n8n")
        {
        }

        protected override bool OnLoad()
        {
            try
            {
                var documentsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                this._triggersFilePath = Path.Combine(documentsPath, "n8n_triggers.json");

                this.EnsureTriggersFileExists();
                this.LoadTriggers();
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to initialize TriggerWorkflowCommand");
            }
            return true;
        }

        private void EnsureTriggersFileExists()
        {
            try
            {
                if (!File.Exists(this._triggersFilePath))
                {
                    var defaultTriggers = new List<N8NTrigger>
                    {
                        new N8NTrigger
                        {
                            Id = "movie_mode",
                            Name = "Movie Mode",
                            Url = "https://n8n.eole.me/webhook/movie-mode",
                            Color = "#8200FF"
                        }
                    };

                    var options = new JsonSerializerOptions { WriteIndented = true };
                    var json = JsonSerializer.Serialize(defaultTriggers, options);
                    File.WriteAllText(this._triggersFilePath, json);
                    PluginLog.Info($"Created default n8n triggers file at: {this._triggersFilePath}");
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to create default n8n triggers file");
            }
        }

        private void LoadTriggers()
        {
            try
            {
                if (File.Exists(this._triggersFilePath))
                {
                    var json = File.ReadAllText(this._triggersFilePath);
                    var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
                    var list = JsonSerializer.Deserialize<List<N8NTrigger>>(json, options);

                    this._triggers.Clear();
                    this.RemoveAllParameters();

                    if (list != null)
                    {
                        foreach (var item in list)
                        {
                            if (!string.IsNullOrEmpty(item.Id) && !string.IsNullOrEmpty(item.Url))
                            {
                                this._triggers.Add(item);
                                this.AddParameter(item.Id, item.Name, "n8n Triggers");
                            }
                        }
                    }

                    this.ParametersChanged();
                    PluginLog.Info($"Loaded {this._triggers.Count} n8n triggers from config.");
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Error loading triggers from JSON file");
            }
        }

        protected override void RunCommand(string actionParameter)
        {
            if (string.IsNullOrEmpty(actionParameter))
            {
                return;
            }

            var trigger = this._triggers.Find(t => t.Id == actionParameter);
            if (trigger == null)
            {
                // Try reloading triggers in case config was edited
                this.LoadTriggers();
                trigger = this._triggers.Find(t => t.Id == actionParameter);
                if (trigger == null)
                {
                    PluginLog.Warning($"Trigger ID '{actionParameter}' not found.");
                    return;
                }
            }

            Task.Run(async () =>
            {
                try
                {
                    PluginLog.Info($"n8n Trigger: Sending request to {trigger.Url}...");
                    var response = await _httpClient.PostAsync(trigger.Url, new StringContent("{}", System.Text.Encoding.UTF8, "application/json"));
                    
                    if (response.IsSuccessStatusCode)
                    {
                        PluginLog.Info($"n8n Trigger: Successful response from {trigger.Name}");
                    }
                    else
                    {
                        PluginLog.Warning($"n8n Trigger: Failed trigger for {trigger.Name}. Status: {response.StatusCode}");
                    }
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, $"n8n Trigger: HTTP request failed for trigger: {trigger.Name}");
                }
            });
        }

        protected override string GetCommandDisplayName(string actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter))
            {
                return "n8n Trigger";
            }

            var trigger = this._triggers.Find(t => t.Id == actionParameter);
            return trigger != null ? trigger.Name : actionParameter;
        }

        protected override BitmapImage GetCommandImage(string actionParameter, PluginImageSize imageSize)
        {
            if (string.IsNullOrEmpty(actionParameter))
            {
                return PluginImages.CreateButtonImage(imageSize, "n8n\nTrigger");
            }

            var trigger = this._triggers.Find(t => t.Id == actionParameter);
            if (trigger != null)
            {
                var color = PluginImages.ParseHexColor(trigger.Color);
                return PluginImages.CreateButtonImage(imageSize, trigger.Name, color, PluginImages.BlackColor);
            }

            return PluginImages.CreateButtonImage(imageSize, actionParameter);
        }
    }
}
