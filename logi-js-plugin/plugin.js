/**
 * Logitech Options+ Extension Background Script (plugin.js)
 * Gère la communication dynamique avec la passerelle n8n
 */

const logi = chrome.logiOptions || window.logiOptions;

// Récupère l'URL du webhook de manière dynamique au chargement / configuration
logi.actions.onRegisterDynamicActions("trigger_papy_action", async () => {
  try {
    // Récupère la configuration gronas_n8n_url saisie dans les réglages Logi+
    const settings = await logi.settings.getAll();
    const gatewayUrl = settings.gronas_n8n_url || "http://gronas:5678";

    // Effectue un fetch() vers le webhook getActionsList
    const response = await fetch(`${gatewayUrl.replace(/\/$/, "")}/webhook/get-exposed-actions`);
    if (!response.ok) throw new Error(`HTTP Error ${response.status}`);

    const actions = await response.json();

    // Injecte dynamiquement les boutons reçus sur les touches LCD de la console
    return actions.map(action => ({
      id: action.Id,
      name: action.Name,
      color: action.Color || "#8200FF"
    }));
  } catch (error) {
    console.error("[Logi PapyConnect] Échec de la récupération des boutons:", error);
    return [
      { id: "error", name: "Erreur n8n", color: "#FF0000" }
    ];
  }
});

// Exécute le webhook d'action lors de l'appui sur une touche LCD
logi.actions.onTriggered("trigger_papy_action", async (actionId) => {
  if (actionId === "error") return;

  try {
    const settings = await logi.settings.getAll();
    const gatewayUrl = settings.gronas_n8n_url || "http://gronas:5678";

    // Lance le webhook d'exécution launchAction de n8n
    const response = await fetch(`${gatewayUrl.replace(/\/$/, "")}/webhook/papyconnect-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId })
    });

    if (response.ok) {
      console.log(`[Logi PapyConnect] Action '${actionId}' déclenchée.`);
    } else {
      console.error(`[Logi PapyConnect] Échec d'exécution: ${response.status}`);
    }
  } catch (error) {
    console.error("[Logi PapyConnect] Erreur réseau lors du déclenchement:", error);
  }
});
