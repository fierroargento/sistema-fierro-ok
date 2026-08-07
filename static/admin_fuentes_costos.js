(function () {
  "use strict";

  function iniciarCriteriosDistribucion() {
    document.querySelectorAll("[data-production-cost]").forEach(function (control) {
      const distribucion = control.form.querySelector("[data-distribution]");
      if (!distribucion) return;

      function sincronizar() {
        const informativo = control.value === "0";
        if (informativo) distribucion.value = "sin_distribuir";
        distribucion.setAttribute("aria-disabled", String(informativo));
      }

      control.addEventListener("change", sincronizar);
      sincronizar();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarCriteriosDistribucion);
  } else {
    iniciarCriteriosDistribucion();
  }
})();
