(function () {
  "use strict";
  const dialog = document.getElementById("cost-product-dialog");
  if (!dialog) return;
  const content = dialog.querySelector("[data-cost-history-content]");
  let pending;
  let trigger;
  document.querySelectorAll("[data-cost-history-url]").forEach(function (button) {
    button.addEventListener("click", async function () {
      if (pending) pending.abort();
      const controller = new AbortController();
      pending = controller;
      trigger = button;
      content.textContent = "Cargando versiones de costo…";
      dialog.showModal();
      try {
        const response = await fetch(button.dataset.costHistoryUrl, {
          signal: controller.signal, credentials: "same-origin",
          headers: { "X-Requested-With": "XMLHttpRequest" }
        });
        if (response.redirected) throw new Error("La sesión venció. Volvé a iniciar sesión.");
        if (response.status === 404) throw new Error("No hay versiones de costo en esta unidad. La ficha todavía no tiene un cálculo guardado.");
        if (!response.ok) throw new Error("No se pudo cargar el historial. Cerrá y volvé a intentar.");
        const html = await response.text();
        if (pending === controller && dialog.open) content.innerHTML = html;
      } catch (error) {
        if (error.name !== "AbortError" && pending === controller && dialog.open) content.textContent = error.message;
      }
    });
  });
  dialog.querySelectorAll("[data-close-cost-history]").forEach(function (button) {
    button.addEventListener("click", function () { dialog.close(); });
  });
  dialog.addEventListener("click", function (event) { if (event.target === dialog) dialog.close(); });
  dialog.addEventListener("close", function () {
    if (pending) pending.abort();
    pending = null;
    content.replaceChildren();
    if (trigger) trigger.focus({ preventScroll: true });
  });
})();
