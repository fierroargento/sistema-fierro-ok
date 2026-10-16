"use strict";
document.addEventListener("DOMContentLoaded", function () {
  const form = document.querySelector(".simulator-form");
  if (!form) return;
  const button = form.querySelector("[data-simulation-submit]");
  const progress = form.querySelector("[data-simulation-progress]");
  function restore() {
    form.removeAttribute("aria-busy");
    button.disabled = false;
    button.textContent = "Simular escenario";
    progress.textContent = "";
  }
  window.addEventListener("pageshow", restore);
  form.addEventListener("submit", function (event) {
    if (event.defaultPrevented) return;
    if (form.getAttribute("aria-busy") === "true") {
      event.preventDefault();
      return;
    }
    form.setAttribute("aria-busy", "true");
    button.disabled = true;
    button.textContent = "Simulando…";
    progress.textContent = "Calculando el escenario…";
  });
  const response = document.querySelector("[data-simulation-response]");
  if (response) {
    response.focus({ preventScroll: true });
    response.scrollIntoView({ behavior: "auto", block: "start" });
  }
});
