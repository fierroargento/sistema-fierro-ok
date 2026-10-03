(function () {
  "use strict";
  const error = document.getElementById("inventario-error");
  const target = document.getElementById(window.location.hash.slice(1));
  if (target && target.closest(".inventory-admin") && target.tagName === "DETAILS") {
    target.open = true;
  }
  if (!error) return;
  if (target && target.closest(".inventory-admin")) {
    if (target.tagName === "DETAILS") {
      target.open = true;
      const summary = target.querySelector("summary");
      if (summary) summary.insertAdjacentElement("afterend", error);
      else target.prepend(error);
    } else {
      target.prepend(error);
    }
  }
  window.requestAnimationFrame(function () {
    error.focus({ preventScroll: true });
    error.scrollIntoView({ block: "center" });
  });
})();
