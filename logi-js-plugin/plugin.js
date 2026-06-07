/**
 * Logitech Options+ Extension Background Script (plugin.js)
 * Manages the mapping of physical MX console buttons
 */

const logi = chrome.logiOptions || window.logiOptions;

// Register listeners for buttons 1 to 6
for (let i = 1; i <= 6; i++) {
  const btnId = `papyconnect_btn_${i}`;
  logi.actions.onTriggered(btnId, async () => {
    try {
      const settings = await logi.settings.getAll();
      const gatewayUrl = settings.gronas_n8n_url || "http://gronas:5678";
      
      console.log(`[Logi PapyConnect] Button triggered: ${btnId}`);
      const response = await fetch(`${gatewayUrl.replace(/\/$/, "")}/webhook/papyconnect-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ button_id: btnId })
      });
      
      if (response.ok) {
        console.log(`[Logi PapyConnect] ${btnId} executed successfully.`);
      } else {
        console.error(`[Logi PapyConnect] Failed to execute ${btnId}: ${response.status}`);
      }
    } catch (error) {
      console.error(`[Logi PapyConnect] Network error executing ${btnId}:`, error);
    }
  });
}

// Static action to open the Configuration Wizard
logi.actions.onTriggered("open_wizard", async () => {
  try {
    const url = "http://gronas:8000";
    if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
      chrome.tabs.create({ url });
    } else {
      window.open(url, "_blank");
    }
    console.log("[Logi PapyConnect] Configuration wizard opened.");
  } catch (error) {
    console.error("[Logi PapyConnect] Failed to open the wizard:", error);
  }
});
