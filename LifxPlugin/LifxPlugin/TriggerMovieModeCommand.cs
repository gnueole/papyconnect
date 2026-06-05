namespace Loupedeck.LifxPlugin
{
    using System;
    using System.IO;
    using System.Net.Http;
    using System.Threading.Tasks;

    public class TriggerMovieModeCommand : PluginDynamicCommand
    {
        private static readonly HttpClient _client = new HttpClient();

        public TriggerMovieModeCommand()
            : base("Movie Mode", "Triggers the n8n Movie Mode workflow (Sony TV & lights)", "LIFX")
        {
        }

        protected override bool OnLoad()
        {
            return true;
        }

        protected override bool OnUnload()
        {
            return true;
        }

        protected override void RunCommand(string actionParameter)
        {
            Task.Run(async () =>
            {
                var webhookUrl = "https://n8n.eole.me/webhook/movie-mode";
                try
                {
                    // Attempt to load override webhook URL from Documents or User Profile
                    var documentsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                    var documentsWebhookPath = Path.Combine(documentsPath, "n8n_movie_mode_webhook.txt");

                    if (File.Exists(documentsWebhookPath))
                    {
                        var fileContent = File.ReadAllText(documentsWebhookPath).Trim();
                        if (Uri.IsWellFormedUriString(fileContent, UriKind.Absolute))
                        {
                            webhookUrl = fileContent;
                        }
                    }
                    else
                    {
                        var userProfilePath = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                        var userProfileWebhookPath = Path.Combine(userProfilePath, ".n8n_movie_mode_webhook");

                        if (File.Exists(userProfileWebhookPath))
                        {
                            var fileContent = File.ReadAllText(userProfileWebhookPath).Trim();
                            if (Uri.IsWellFormedUriString(fileContent, UriKind.Absolute))
                            {
                                webhookUrl = fileContent;
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, "Failed to load n8n movie mode webhook config.");
                }

                try
                {
                    PluginLog.Info($"Triggering n8n Movie Mode at {webhookUrl}...");
                    var response = await _client.PostAsync(webhookUrl, new StringContent("{}", System.Text.Encoding.UTF8, "application/json"));
                    if (response.IsSuccessStatusCode)
                    {
                        PluginLog.Info("Successfully triggered n8n Movie Mode workflow!");
                    }
                    else
                    {
                        PluginLog.Warning($"Failed to trigger Movie Mode. HTTP Status: {response.StatusCode}");
                    }
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, "Failed to send HTTP POST trigger to n8n webhook.");
                }
            });
        }

        protected override string GetCommandDisplayName(string actionParameter, PluginImageSize imageSize)
        {
            return "Movie\nMode";
        }

        protected override BitmapImage GetCommandImage(string actionParameter, PluginImageSize imageSize)
        {
            return PluginImages.CreateMovieModeImage(imageSize);
        }
    }
}
