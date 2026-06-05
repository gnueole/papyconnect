namespace Loupedeck.LifxPlugin
{
    using System;
    using System.Collections.Generic;
    using System.IO;
    using System.Net.Http;
    using System.Net.Http.Headers;
    using System.Text.Json;
    using System.Threading.Tasks;

    public class LifxGroup
    {
        public string Id { get; set; }
        public string Name { get; set; }
    }

    public class LifxScene
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public List<string> ColorsHex { get; set; } = new List<string>();
    }

    public class LifxLight
    {
        public string Id { get; set; }
        public string Name { get; set; }
        public bool Connected { get; set; }
        public string Power { get; set; }
        public double Brightness { get; set; }
        public string Type { get; set; }
    }

    public class LifxClient
    {
        public static string TokenFileName { get; set; } = "LIFX_Token.txt";
        public static string FallbackTokenFileName { get; set; } = ".lifx_token";

        private readonly HttpClient _httpClient;
        private readonly string _token;

        public LifxClient()
        {
            try
            {
                // First try Documents/LIFX_Token.txt (user-friendly location)
                var documentsPath = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
                var documentsTokenPath = Path.Combine(documentsPath, TokenFileName);

                if (File.Exists(documentsTokenPath))
                {
                    this._token = File.ReadAllText(documentsTokenPath).Trim();
                }
                else
                {
                    // Fallback to UserProfile/.lifx_token (developer/power-user location)
                    var userProfilePath = Environment.GetFolderPath(Environment.SpecialFolder.UserProfile);
                    var userProfileTokenPath = Path.Combine(userProfilePath, FallbackTokenFileName);

                    if (File.Exists(userProfileTokenPath))
                    {
                        this._token = File.ReadAllText(userProfileTokenPath).Trim();
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to load LIFX token from Documents/{TokenFileName} or ~/{FallbackTokenFileName}");
            }

            this._httpClient = new HttpClient();
            if (!string.IsNullOrEmpty(this._token))
            {
                this._httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", this._token);
            }
        }

        public bool HasToken => !string.IsNullOrEmpty(this._token);

        public async Task<bool> ToggleLightsAsync()
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot toggle lights: LIFX token is not configured.");
                return false;
            }

            try
            {
                var response = await this._httpClient.PostAsync("https://api.lifx.com/v1/lights/all/toggle", null);
                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully toggled LIFX lights.");
                    return true;
                }

                PluginLog.Warning($"Failed to toggle lights. API returned status code: {response.StatusCode}");
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "HTTP request to toggle LIFX lights failed.");
                return false;
            }
        }

        public async Task<double> GetBrightnessAsync()
        {
            if (!this.HasToken)
            {
                return 0.5;
            }

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array && document.RootElement.GetArrayLength() > 0)
                {
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (element.TryGetProperty("connected", out var connectedProp) && connectedProp.GetBoolean())
                        {
                            if (element.TryGetProperty("brightness", out var brightnessProp))
                            {
                                return brightnessProp.GetDouble();
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to retrieve current LIFX brightness.");
            }

            return 0.5;
        }

        public async Task<bool> SetBrightnessAsync(double brightness)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot set brightness: LIFX token is not configured.");
                return false;
            }

            try
            {
                brightness = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(BrightnessAdjustment.MaxBrightness, brightness));

                var payload = new { brightness = brightness, power = brightness > 0.001 ? "on" : "off" };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                var startTime = DateTime.UtcNow;
                PluginLog.Info($"LIFX Client: Sending SetBrightnessAsync({brightness * 100:0}%) to all lights...");
                var response = await this._httpClient.PutAsync("https://api.lifx.com/v1/lights/all/state", content);
                var elapsed = (DateTime.UtcNow - startTime).TotalMilliseconds;

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info($"LIFX Client: SetBrightnessAsync succeeded in {elapsed:0}ms.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                PluginLog.Warning($"LIFX Client: SetBrightnessAsync failed in {elapsed:0}ms. Status: {response.StatusCode} ({(int)response.StatusCode}). Response: {contentString}");
                if (response.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
                {
                    PluginLog.Warning("LIFX Client: Rate limit reached! Please slow down adjustments.");
                }
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "HTTP request to set LIFX brightness failed.");
                return false;
            }
        }

        public async Task<List<LifxGroup>> GetGroupsAsync()
        {
            var groups = new List<LifxGroup>();
            if (!this.HasToken)
            {
                return groups;
            }

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array)
                {
                    var seenIds = new HashSet<string>();
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (element.TryGetProperty("group", out var groupProp) && groupProp.ValueKind == JsonValueKind.Object)
                        {
                            if (groupProp.TryGetProperty("id", out var idProp) && groupProp.TryGetProperty("name", out var nameProp))
                            {
                                var id = idProp.GetString();
                                var name = nameProp.GetString();
                                if (!string.IsNullOrEmpty(id) && !seenIds.Contains(id))
                                {
                                    seenIds.Add(id);
                                    groups.Add(new LifxGroup { Id = id, Name = name });
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to retrieve LIFX groups.");
            }

            return groups;
        }

        public async Task<List<LifxScene>> GetScenesAsync()
        {
            var scenes = new List<LifxScene>();
            if (!this.HasToken)
            {
                return scenes;
            }

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/scenes");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array)
                {
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (element.TryGetProperty("uuid", out var uuidProp) && element.TryGetProperty("name", out var nameProp))
                        {
                            var uuid = uuidProp.GetString();
                            var name = nameProp.GetString();
                            if (!string.IsNullOrEmpty(uuid))
                            {
                                var colorsHex = new List<string>();
                                if (element.TryGetProperty("states", out var statesProp) && statesProp.ValueKind == JsonValueKind.Array)
                                {
                                    var seenHex = new HashSet<string>();
                                    foreach (var state in statesProp.EnumerateArray())
                                    {
                                        if (state.TryGetProperty("color", out var colorProp) && colorProp.ValueKind == JsonValueKind.Object)
                                        {
                                            double hue = 0;
                                            double sat = 0;
                                            int kelvin = 3500;

                                            if (colorProp.TryGetProperty("hue", out var hProp)) hue = hProp.GetDouble();
                                            if (colorProp.TryGetProperty("saturation", out var sProp)) sat = sProp.GetDouble();
                                            if (colorProp.TryGetProperty("kelvin", out var kProp)) kelvin = kProp.GetInt32();

                                            BitmapColor colorVal;
                                            if (sat < 0.01)
                                            {
                                                if (kelvin < 2500) colorVal = new BitmapColor(255, 180, 100);
                                                else if (kelvin < 4000) colorVal = new BitmapColor(255, 230, 180);
                                                else if (kelvin < 6500) colorVal = new BitmapColor(245, 245, 255);
                                                else colorVal = new BitmapColor(200, 220, 255);
                                            }
                                            else
                                            {
                                                colorVal = HslToRgb(hue, sat, 0.5);
                                            }

                                            var hex = $"#{colorVal.R:X2}{colorVal.G:X2}{colorVal.B:X2}";
                                            if (!seenHex.Contains(hex))
                                            {
                                                seenHex.Add(hex);
                                                colorsHex.Add(hex);
                                                if (colorsHex.Count >= 3) break;
                                            }
                                        }
                                    }
                                }

                                scenes.Add(new LifxScene { Id = uuid, Name = name, ColorsHex = colorsHex });
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to retrieve LIFX scenes.");
            }

            return scenes;
        }

        private static BitmapColor HslToRgb(double h, double s, double l)
        {
            double r = 0, g = 0, b = 0;
            if (s == 0)
            {
                r = g = b = l;
            }
            else
            {
                double q = l < 0.5 ? l * (1.0 + s) : l + s - l * s;
                double p = 2.0 * l - q;
                r = HueToRgb(p, q, h / 360.0 + 1.0 / 3.0);
                g = HueToRgb(p, q, h / 360.0);
                b = HueToRgb(p, q, h / 360.0 - 1.0 / 3.0);
            }
            return new BitmapColor((int)Math.Round(r * 255), (int)Math.Round(g * 255), (int)Math.Round(b * 255));
        }

        private static double HueToRgb(double p, double q, double t)
        {
            if (t < 0.0) t += 1.0;
            if (t > 1.0) t -= 1.0;
            if (t < 1.0 / 6.0) return p + (q - p) * 6.0 * t;
            if (t < 1.0 / 2.0) return q;
            if (t < 2.0 / 3.0) return p + (q - p) * (2.0 / 3.0 - t) * 6.0;
            return p;
        }

        public async Task<bool> ActivateSceneAsync(string sceneId)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot activate scene: LIFX token is not configured.");
                return false;
            }

            try
            {
                PluginLog.Info($"LIFX Client: Activating scene scene_id:{sceneId}...");
                var response = await this._httpClient.PutAsync($"https://api.lifx.com/v1/scenes/scene_id:{sceneId}/activate", null);
                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully activated scene.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("ActivateSceneAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to activate scene {sceneId}.");
                return false;
            }
        }

        public async Task<List<LifxLight>> GetLightsAsync()
        {
            var lights = new List<LifxLight>();
            if (!this.HasToken)
            {
                return lights;
            }

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array)
                {
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (element.TryGetProperty("id", out var idProp) && element.TryGetProperty("label", out var labelProp))
                        {
                            var id = idProp.GetString();
                            var name = labelProp.GetString();
                            var connected = false;
                            if (element.TryGetProperty("connected", out var connProp))
                            {
                                connected = connProp.GetBoolean();
                            }
                            var power = "off";
                            if (element.TryGetProperty("power", out var powerProp))
                            {
                                power = powerProp.GetString();
                            }
                            var brightness = 0.5;
                            if (element.TryGetProperty("brightness", out var brightProp))
                            {
                                brightness = brightProp.GetDouble();
                            }

                            var type = "bulb";
                            if (element.TryGetProperty("product", out var productProp))
                            {
                                if (productProp.TryGetProperty("capabilities", out var capProp))
                                {
                                    if (capProp.TryGetProperty("has_multizone", out var mzProp) && mzProp.GetBoolean())
                                    {
                                        type = "string";
                                    }
                                    else if (capProp.TryGetProperty("has_matrix", out var matProp) && matProp.GetBoolean())
                                    {
                                        type = "other";
                                    }
                                }
                            }

                            if (!string.IsNullOrEmpty(id))
                            {
                                lights.Add(new LifxLight
                                {
                                    Id = id,
                                    Name = name,
                                    Connected = connected,
                                    Power = power,
                                    Brightness = brightness,
                                    Type = type
                                });
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to retrieve LIFX lights.");
            }

            return lights;
        }

        private string ResolveSelector(string selector)
        {
            if (string.IsNullOrEmpty(selector) || selector == "all")
            {
                return "all";
            }
            if (selector.StartsWith("id:") || selector.StartsWith("group_id:") || selector.StartsWith("location_id:"))
            {
                return selector;
            }
            return $"group_id:{selector}";
        }

        private bool LightMatchesSelector(JsonElement element, string selector)
        {
            if (selector == "all")
            {
                return true;
            }
            if (selector.StartsWith("id:"))
            {
                var lightId = selector.Substring(3);
                if (element.TryGetProperty("id", out var idProp) && idProp.GetString() == lightId)
                {
                    return true;
                }
            }
            else if (selector.StartsWith("group_id:"))
            {
                var groupId = selector.Substring(9);
                if (element.TryGetProperty("group", out var groupProp) && groupProp.ValueKind == JsonValueKind.Object)
                {
                    if (groupProp.TryGetProperty("id", out var idProp) && idProp.GetString() == groupId)
                    {
                        return true;
                    }
                }
            }
            return false;
        }

        public async Task<bool> ToggleGroupAsync(string groupId)
        {
            if (!this.HasToken)
            {
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/toggle", null);
                if (response.IsSuccessStatusCode)
                {
                    return true;
                }
                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("ToggleGroupAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to toggle LIFX selector {selector}.");
                return false;
            }
        }

        public async Task<double> GetGroupBrightnessAsync(string groupId)
        {
            if (!this.HasToken)
            {
                return 0.5;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array)
                {
                    double sum = 0;
                    int count = 0;
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (this.LightMatchesSelector(element, selector))
                        {
                            if (element.TryGetProperty("connected", out var connectedProp) && connectedProp.GetBoolean())
                            {
                                if (element.TryGetProperty("brightness", out var brightnessProp))
                                {
                                    sum += brightnessProp.GetDouble();
                                    count++;
                                }
                            }
                        }
                    }
                    if (count > 0)
                    {
                        return sum / count;
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to retrieve brightness for selector {selector}.");
            }

            return 0.5;
        }

        public async Task<bool> SetGroupBrightnessAsync(string groupId, double brightness)
        {
            if (!this.HasToken)
            {
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                brightness = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(BrightnessAdjustment.MaxBrightness, brightness));
                var payload = new { brightness = brightness, power = brightness > 0.001 ? "on" : "off" };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                var startTime = DateTime.UtcNow;
                PluginLog.Info($"LIFX Client: Sending SetGroupBrightnessAsync({brightness * 100:0}%) for selector {selector}...");
                var response = await this._httpClient.PutAsync($"https://api.lifx.com/v1/lights/{selector}/state", content);
                var elapsed = (DateTime.UtcNow - startTime).TotalMilliseconds;

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info($"LIFX Client: SetGroupBrightnessAsync succeeded in {elapsed:0}ms.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("SetGroupBrightnessAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to set brightness for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> SetColorToWhiteAsync(string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot set color to white: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var payload = new { color = "white" };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                var response = await this._httpClient.PutAsync($"https://api.lifx.com/v1/lights/{selector}/state", content);
                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info($"Successfully reset color to standard white for selector: {selector}.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("SetColorToWhiteAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to reset color for selector {selector}.");
                return false;
            }
        }

        public async Task<double> GetHueAsync()
        {
            if (!this.HasToken)
            {
                return 0.0;
            }

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array && document.RootElement.GetArrayLength() > 0)
                {
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (element.TryGetProperty("connected", out var connectedProp) && connectedProp.GetBoolean())
                        {
                            if (element.TryGetProperty("color", out var colorProp) && colorProp.ValueKind == JsonValueKind.Object)
                            {
                                if (colorProp.TryGetProperty("hue", out var hueProp))
                                {
                                    return hueProp.GetDouble();
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to retrieve current LIFX hue.");
            }

            return 0.0;
        }

        public async Task<bool> SetHueAsync(double hue)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot set hue: LIFX token is not configured.");
                return false;
            }

            try
            {
                hue = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(ActiveRoomHue.HueRange, hue));

                var payload = new { color = $"hue:{hue:0.0} saturation:1.0", power = "on" };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                var startTime = DateTime.UtcNow;
                PluginLog.Info($"LIFX Client: Sending SetHueAsync({hue:0.0}) to all lights...");
                var response = await this._httpClient.PutAsync("https://api.lifx.com/v1/lights/all/state", content);
                var elapsed = (DateTime.UtcNow - startTime).TotalMilliseconds;

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info($"LIFX Client: SetHueAsync succeeded in {elapsed:0}ms.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                PluginLog.Warning($"LIFX Client: SetHueAsync failed in {elapsed:0}ms. Status: {response.StatusCode} ({(int)response.StatusCode}). Response: {contentString}");
                if (response.StatusCode == System.Net.HttpStatusCode.TooManyRequests)
                {
                    PluginLog.Warning("LIFX Client: Rate limit reached! Please slow down adjustments.");
                }
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "HTTP request to set LIFX hue failed.");
                return false;
            }
        }

        public async Task<double> GetGroupHueAsync(string groupId)
        {
            if (!this.HasToken)
            {
                return 0.0;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array)
                {
                    double sum = 0;
                    int count = 0;
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (this.LightMatchesSelector(element, selector))
                        {
                            if (element.TryGetProperty("connected", out var connectedProp) && connectedProp.GetBoolean())
                            {
                                if (element.TryGetProperty("color", out var colorProp) && colorProp.ValueKind == JsonValueKind.Object)
                                {
                                    if (colorProp.TryGetProperty("hue", out var hueProp))
                                    {
                                        sum += hueProp.GetDouble();
                                        count++;
                                    }
                                }
                            }
                        }
                    }
                    if (count > 0)
                    {
                        return sum / count;
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to retrieve hue for selector {selector}.");
            }

            return 0.0;
        }

        public async Task<bool> SetGroupHueAsync(string groupId, double hue)
        {
            if (!this.HasToken)
            {
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                hue = Math.Max(BrightnessAdjustment.MinBrightness, Math.Min(ActiveRoomHue.HueRange, hue));
                var payload = new { color = $"hue:{hue:0.0} saturation:1.0", power = "on" };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                var startTime = DateTime.UtcNow;
                PluginLog.Info($"LIFX Client: Sending SetGroupHueAsync({hue:0.0}) for selector {selector}...");
                var response = await this._httpClient.PutAsync($"https://api.lifx.com/v1/lights/{selector}/state", content);
                var elapsed = (DateTime.UtcNow - startTime).TotalMilliseconds;

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info($"LIFX Client: SetGroupHueAsync succeeded in {elapsed:0}ms.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("SetGroupHueAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to set hue for selector {selector}.");
                return false;
            }
        }

        public async Task<int> GetTemperatureAsync()
        {
            if (!this.HasToken)
            {
                return 3500;
            }

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array && document.RootElement.GetArrayLength() > 0)
                {
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (element.TryGetProperty("connected", out var connectedProp) && connectedProp.GetBoolean())
                        {
                            if (element.TryGetProperty("color", out var colorProp) && colorProp.ValueKind == JsonValueKind.Object)
                            {
                                if (colorProp.TryGetProperty("kelvin", out var kelvinProp))
                                {
                                    return kelvinProp.GetInt32();
                                }
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "Failed to retrieve current LIFX temperature.");
            }

            return 3500;
        }

        public async Task<bool> SetTemperatureAsync(int kelvin)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot set temperature: LIFX token is not configured.");
                return false;
            }

            try
            {
                kelvin = Math.Max(1500, Math.Min(9000, kelvin));

                var payload = new { color = $"kelvin:{kelvin}", power = "on" };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                var startTime = DateTime.UtcNow;
                PluginLog.Info($"LIFX Client: Sending SetTemperatureAsync({kelvin}K) to all lights...");
                var response = await this._httpClient.PutAsync("https://api.lifx.com/v1/lights/all/state", content);
                var elapsed = (DateTime.UtcNow - startTime).TotalMilliseconds;

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info($"LIFX Client: SetTemperatureAsync succeeded in {elapsed:0}ms.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                PluginLog.Warning($"LIFX Client: SetTemperatureAsync failed in {elapsed:0}ms. Status: {response.StatusCode}. Response: {contentString}");
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, "HTTP request to set LIFX temperature failed.");
                return false;
            }
        }

        public async Task<int> GetGroupTemperatureAsync(string groupId)
        {
            if (!this.HasToken)
            {
                return 3500;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var responseJson = await this._httpClient.GetStringAsync("https://api.lifx.com/v1/lights/all");
                using var document = JsonDocument.Parse(responseJson);

                if (document.RootElement.ValueKind == JsonValueKind.Array)
                {
                    double sum = 0;
                    int count = 0;
                    foreach (var element in document.RootElement.EnumerateArray())
                    {
                        if (this.LightMatchesSelector(element, selector))
                        {
                            if (element.TryGetProperty("connected", out var connectedProp) && connectedProp.GetBoolean())
                            {
                                if (element.TryGetProperty("color", out var colorProp) && colorProp.ValueKind == JsonValueKind.Object)
                                {
                                    if (colorProp.TryGetProperty("kelvin", out var kelvinProp))
                                    {
                                        sum += kelvinProp.GetInt32();
                                        count++;
                                    }
                                }
                            }
                        }
                    }
                    if (count > 0)
                    {
                        return (int)Math.Round(sum / count);
                    }
                }
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to retrieve temperature for selector {selector}.");
            }

            return 3500;
        }

        public async Task<bool> SetGroupTemperatureAsync(string groupId, int kelvin)
        {
            if (!this.HasToken)
            {
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                kelvin = Math.Max(1500, Math.Min(9000, kelvin));
                var payload = new { color = $"kelvin:{kelvin}", power = "on" };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                var startTime = DateTime.UtcNow;
                PluginLog.Info($"LIFX Client: Sending SetGroupTemperatureAsync({kelvin}K) for selector {selector}...");
                var response = await this._httpClient.PutAsync($"https://api.lifx.com/v1/lights/{selector}/state", content);
                var elapsed = (DateTime.UtcNow - startTime).TotalMilliseconds;

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info($"LIFX Client: SetGroupTemperatureAsync succeeded in {elapsed:0}ms.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("SetGroupTemperatureAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to set temperature for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlayBreatheEffectAsync(string color, double period, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play breathe effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var calculatedCycles = Math.Max(1.0, Math.Round(10.0 / period, 1));
                var payload = new 
                { 
                    color = color,
                    period = period,
                    cycles = calculatedCycles,
                    persist = false,
                    power_on = true
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering breathe effect ({color}) at period {period}s ({calculatedCycles} cycles) for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/breathe", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered breathe effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlayBreatheEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger breathe effect for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlayPulseEffectAsync(string color, double period, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play pulse effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var calculatedCycles = Math.Max(1.0, Math.Round(10.0 / period, 1));
                var payload = new 
                { 
                    color = color,
                    period = period,
                    cycles = calculatedCycles,
                    persist = false,
                    power_on = true
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering pulse effect ({color}) at period {period}s ({calculatedCycles} cycles) for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/pulse", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered pulse effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlayPulseEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger pulse effect for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> StopEffectsAsync(string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot stop effects: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var payload = new 
                { 
                    power_off = false
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Stopping effects for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/off", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully stopped effects.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("StopEffectsAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to stop effects for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlayMoveEffectAsync(double period, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play move effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var payload = new 
                { 
                    direction = "forward",
                    period = period,
                    power_on = true
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering move effect at period {period}s for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/move", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered move effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlayMoveEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger move effect for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlayMorphEffectAsync(double period, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play morph effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var payload = new 
                { 
                    period = period,
                    power_on = true
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering morph effect at period {period}s for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/morph", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered morph effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlayMorphEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger morph effect for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlayFlameEffectAsync(double period, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play flame effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var payload = new 
                { 
                    period = period,
                    power_on = true
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering flame effect at period {period}s for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/flame", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered flame effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlayFlameEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger flame effect for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlayCloudsEffectAsync(double period, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play clouds effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var cloudPeriod = period * 10.0;
                var payload = new 
                { 
                    period = cloudPeriod,
                    power_on = true,
                    min_saturation = 0.2
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering clouds effect at period {cloudPeriod}s for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/clouds", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered clouds effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlayCloudsEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger clouds effect for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlaySunriseEffectAsync(double duration, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play sunrise effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var sunriseDuration = duration * 10.0;
                var payload = new 
                { 
                    duration = sunriseDuration,
                    power_on = true,
                    persist = true
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering sunrise effect with duration {sunriseDuration}s for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/sunrise", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered sunrise effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlaySunriseEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger sunrise effect for selector {selector}.");
                return false;
            }
        }

        public async Task<bool> PlaySunsetEffectAsync(double duration, string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play sunset effect: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var sunsetDuration = duration * 10.0;
                var payload = new 
                { 
                    duration = sunsetDuration,
                    power_on = true,
                    soft_off = false
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Triggering sunset effect with duration {sunsetDuration}s for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/effects/sunset", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully triggered sunset effect.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlaySunsetEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to trigger sunset effect for selector {selector}.");
                return false;
            }
        }

        /// <summary>
        /// Plays sunrise or sunset on any selector, routing correctly per device type:
        /// - Standard bulbs: use the dedicated /effects/sunrise or /effects/sunset endpoint
        /// - String/multizone lights: use a warm color state transition (those endpoints don't support multizone)
        /// - When selector is "all" or group-based: tries effect API first, falls back gracefully
        /// </summary>
        public async Task<bool> PlaySunriseSunsetCompatAsync(bool isSunrise, double duration, string selectorArg, List<LifxLight> knownLights)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play sunrise/sunset: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(selectorArg);
            var effectDuration = duration * 10.0;

            // Parse individual IDs from selector if it's a comma-separated multi-selector
            // e.g. "id:abc123,id:def456" or "group_id:xyz"
            var selectorParts = selector.Split(',');
            var bulbSelectors = new List<string>();
            var stringSelectors = new List<string>();
            var groupOrAllSelectors = new List<string>();

            foreach (var part in selectorParts)
            {
                var p = part.Trim();
                if (p.StartsWith("id:"))
                {
                    // Look up this light in knownLights to determine type
                    var lightId = p.Substring(3);
                    var light = knownLights?.Find(l => l.Id == lightId);
                    if (light != null && light.Type == "string")
                    {
                        stringSelectors.Add(p);
                        PluginLog.Info($"SunriseSunsetCompat: light {light.Name} ({lightId}) is a string/multizone light - will use state transition.");
                    }
                    else
                    {
                        bulbSelectors.Add(p);
                    }
                }
                else
                {
                    // group_id: or all - try the effect API, it may partially succeed
                    groupOrAllSelectors.Add(p);
                }
            }

            var overallSuccess = false;

            // 1. Handle bulb selectors with the real effect endpoint
            if (bulbSelectors.Count > 0)
            {
                var bulkSelector = string.Join(",", bulbSelectors);
                if (isSunrise)
                {
                    overallSuccess |= await this.PlaySunriseEffectAsync(duration, bulkSelector);
                }
                else
                {
                    overallSuccess |= await this.PlaySunsetEffectAsync(duration, bulkSelector);
                }
            }

            // 2. Handle string/multizone lights with state transition
            if (stringSelectors.Count > 0)
            {
                var strSelector = string.Join(",", stringSelectors);
                try
                {
                    object payload;
                    if (isSunrise)
                    {
                        // Sunrise: start dim warm orange and ramp to warm white over duration
                        payload = new
                        {
                            color = "hue:30 saturation:0.8 brightness:0.7 kelvin:2500",
                            duration = effectDuration,
                            power = "on"
                        };
                    }
                    else
                    {
                        // Sunset: warm amber, dimming to low brightness
                        payload = new
                        {
                            color = "hue:25 saturation:0.6 brightness:0.25 kelvin:2000",
                            duration = effectDuration,
                            power = "on"
                        };
                    }

                    var payloadString = JsonSerializer.Serialize(payload);
                    var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                    PluginLog.Info($"SunriseSunsetCompat: Sending warm-state transition ({(isSunrise ? "sunrise" : "sunset")}) for string lights: {strSelector}");
                    var response = await this._httpClient.PutAsync($"https://api.lifx.com/v1/lights/{strSelector}/state", content);

                    if (response.IsSuccessStatusCode)
                    {
                        PluginLog.Info($"SunriseSunsetCompat: State transition applied to string lights successfully.");
                        overallSuccess = true;
                    }
                    else
                    {
                        var resp = await response.Content.ReadAsStringAsync();
                        this.LogHttpError("SunriseSunsetCompat (string lights)", response, resp);
                    }
                }
                catch (Exception ex)
                {
                    PluginLog.Error(ex, $"SunriseSunsetCompat: Failed to apply state transition to string lights: {strSelector}");
                }
            }

            // 3. Handle group or "all" selectors - try the real effect first
            if (groupOrAllSelectors.Count > 0)
            {
                var grpSelector = string.Join(",", groupOrAllSelectors);
                if (isSunrise)
                {
                    overallSuccess |= await this.PlaySunriseEffectAsync(duration, grpSelector);
                }
                else
                {
                    overallSuccess |= await this.PlaySunsetEffectAsync(duration, grpSelector);
                }
            }

            return overallSuccess;
        }

        public async Task<bool> PlayCycleEffectAsync(string groupId = null)
        {
            if (!this.HasToken)
            {
                PluginLog.Warning("Cannot play cycle: LIFX token is not configured.");
                return false;
            }

            var selector = this.ResolveSelector(groupId);

            try
            {
                var payload = new 
                { 
                    states = new[] 
                    {
                        new { color = "red" },
                        new { color = "orange" },
                        new { color = "yellow" },
                        new { color = "green" },
                        new { color = "cyan" },
                        new { color = "blue" },
                        new { color = "purple" },
                        new { color = "pink" }
                    },
                    direction = "forward"
                };
                var payloadString = JsonSerializer.Serialize(payload);
                var content = new StringContent(payloadString, System.Text.Encoding.UTF8, "application/json");

                PluginLog.Info($"LIFX Client: Cycling states for selector {selector}...");
                var response = await this._httpClient.PostAsync($"https://api.lifx.com/v1/lights/{selector}/cycle", content);

                if (response.IsSuccessStatusCode)
                {
                    PluginLog.Info("Successfully cycled states.");
                    return true;
                }

                var contentString = await response.Content.ReadAsStringAsync();
                this.LogHttpError("PlayCycleEffectAsync", response, contentString);
                return false;
            }
            catch (Exception ex)
            {
                PluginLog.Error(ex, $"Failed to cycle states for selector {selector}.");
                return false;
            }
        }

        // Maps each known HTTP status code to its log action.
        // Add new entries here without touching control flow.
        private static readonly Dictionary<System.Net.HttpStatusCode, Action<string>> HttpErrorHandlers =
            new Dictionary<System.Net.HttpStatusCode, Action<string>>
            {
                [System.Net.HttpStatusCode.Unauthorized]     = msg => PluginLog.Error($"LIFX API Error: {msg} -> Unauthorized! Your LIFX Token is invalid, missing, or expired. Please check your token file."),
                [System.Net.HttpStatusCode.Forbidden]        = msg => PluginLog.Error($"LIFX API Error: {msg} -> Forbidden! The token is valid but doesn't have permission to perform this action on the target lights."),
                [System.Net.HttpStatusCode.NotFound]         = msg => PluginLog.Warning($"LIFX API Error: {msg} -> Not Found! The selector (e.g. active room or group) did not match any connected lights."),
                [(System.Net.HttpStatusCode)422]             = msg => PluginLog.Error($"LIFX API Error: {msg} -> Unprocessable Entity! The parameters (e.g. invalid color string, duration, or cycles) are invalid."),
                [System.Net.HttpStatusCode.TooManyRequests]  = msg => PluginLog.Warning($"LIFX API Error: {msg} -> Rate limit reached! Please wait a moment before sending more commands."),
            };

        private void LogHttpError(string actionName, HttpResponseMessage response, string responseContent)
        {
            var statusCode = response.StatusCode;
            var intCode = (int)statusCode;
            var baseMsg = $"{actionName} failed. Status: {statusCode} ({intCode}). Response: {responseContent}";

            if (HttpErrorHandlers.TryGetValue(statusCode, out var handler))
            {
                handler(baseMsg);
            }
            else
            {
                PluginLog.Warning($"LIFX API Error: {baseMsg}");
            }
        }
    }

    public class RequestCoalescer
    {
        public static int DefaultDelayMs { get; set; } = 350;

        private readonly Func<Task> _action;
        private readonly int _delayMs;
        private System.Threading.CancellationTokenSource _cts;
        private readonly object _lock = new object();
        private bool _isRunning;
        private bool _hasPending;

        public RequestCoalescer(Func<Task> action)
            : this(action, DefaultDelayMs)
        {
        }

        public RequestCoalescer(Func<Task> action, int delayMs)
        {
            this._action = action;
            this._delayMs = delayMs;
        }

        public void Trigger()
        {
            lock (this._lock)
            {
                if (this._cts != null)
                {
                    this._cts.Cancel();
                    this._cts.Dispose();
                }

                this._cts = new System.Threading.CancellationTokenSource();
                var token = this._cts.Token;

                Task.Run(async () =>
                {
                    try
                    {
                        await Task.Delay(this._delayMs, token);
                    }
                    catch (TaskCanceledException)
                    {
                        return;
                    }

                    this.ExecuteAction();
                });
            }
        }

        private void ExecuteAction()
        {
            lock (this._lock)
            {
                if (this._isRunning)
                {
                    this._hasPending = true;
                    return;
                }
                this._isRunning = true;
            }

            Task.Run(async () =>
            {
                while (true)
                {
                    try
                    {
                        await this._action();
                    }
                    catch (Exception ex)
                    {
                        PluginLog.Error(ex, "Error in throttled request execution.");
                    }

                    lock (this._lock)
                    {
                        if (!this._hasPending)
                        {
                            this._isRunning = false;
                            break;
                        }
                        this._hasPending = false;
                    }
                }
            });
        }
    }
}

