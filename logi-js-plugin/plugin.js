/**
 * Logitech Options+ Extension Background Script (plugin.js)
 * Gère le mapping des boutons physiques de la console MX
 */

const logi = chrome.logiOptions || window.logiOptions;

// Enregistrement des écouteurs pour les boutons 1 à 6
for (let i = 1; i <= 6; i++) {
  const btnId = `papyconnect_btn_${i}`;
  logi.actions.onTriggered(btnId, async () => {
    try {
      const settings = await logi.settings.getAll();
      const gatewayUrl = settings.gronas_n8n_url || "http://gronas:5678";
      
      console.log(`[Logi PapyConnect] Touche déclenchée : ${btnId}`);
      const response = await fetch(`${gatewayUrl.replace(/\/$/, "")}/webhook/papyconnect-action`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ button_id: btnId })
      });
      
      if (response.ok) {
        console.log(`[Logi PapyConnect] ${btnId} exécuté avec succès.`);
      } else {
        console.error(`[Logi PapyConnect] Échec de l'exécution de ${btnId}: ${response.status}`);
      }
    } catch (error) {
      console.error(`[Logi PapyConnect] Erreur réseau lors de l'exécution de ${btnId}:`, error);
    }
  });
}

// Action statique pour ouvrir le Wizard de Configuration
logi.actions.onTriggered("open_wizard", async () => {
  try {
    const url = "http://gronas:8000";
    if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.create) {
      chrome.tabs.create({ url });
    } else {
      window.open(url, "_blank");
    }
    console.log("[Logi PapyConnect] Wizard de configuration ouvert.");
  } catch (error) {
    console.error("[Logi PapyConnect] Impossible d'ouvrir le wizard :", error);
  }
});
