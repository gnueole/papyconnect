/**
 * Logitech Options+ Extension Background Script
 * Gère la communication dynamique avec la passerelle n8n
 */

const logi = chrome.logiOptions || window.logiOptions;

// 1. Récupération dynamique des touches à afficher sur l'écran LCD
logi.actions.onRegisterDynamicActions("trigger_papy_action", async () => {
  try {
    // Récupère l'URL configurée par l'utilisateur dans l'interface Logi+
    const settings = await logi.settings.getAll();
    const gatewayUrl = settings.n8n_gateway_url || "http://gronas:5678";

    // Appelle le workflow n8n (getActionsList)
    const response = await fetch(`${gatewayUrl.replace(/\/$/, "")}/webhook/get-exposed-actions`);
    if (!response.ok) throw new Error(`Status ${response.status}`);

    const actions = await response.json();

    // Mappe les données pour l'écran LCD
    return actions.map(action => ({
      id: action.Id,
      name: action.Name,
      color: action.Color || "#8200FF"
    }));
  } catch (error) {
    console.error("[Logi PapyConnect] Impossible de récupérer les touches:", error);
    return [
      { id: "error", name: "Erreur n8n", color: "#FF0000" }
    ];
  }
});

// 2. Exécution lors d'un appui sur une touche LCD de la console MX
logi.actions.onTriggered("trigger_papy_action", async (actionId) => {
  if (actionId === "error") return;

  try {
    const settings = await logi.settings.getAll();
    const gatewayUrl = settings.n8n_gateway_url || "http://gronas:5678";

    // Envoie l'ID au webhook d'exécution de n8n (launchAction)
    const response = await fetch(`${gatewayUrl.replace(/\/$/, "")}/webhook/papyconnect-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action_id: actionId })
    });

    if (response.ok) {
      console.log(`[Logi PapyConnect] Action '${actionId}' exécutée.`);
    } else {
      console.error(`[Logi PapyConnect] Retour HTTP: ${response.status}`);
    }
  } catch (error) {
    console.error("[Logi PapyConnect] Échec d'envoi du déclencheur:", error);
  }
});
