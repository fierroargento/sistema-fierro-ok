(function () {
  "use strict";
  const feedback = document.getElementById("inventario-error")
    || document.getElementById("inventario-ok");
  const target = document.getElementById(window.location.hash.slice(1));
  if (target && target.closest(".inventory-admin") && target.tagName === "DETAILS") {
    target.open = true;
  }
  if (!feedback) {
    if (target && target.closest(".inventory-admin")) {
      window.requestAnimationFrame(function () {
        target.scrollIntoView({ block: "start" });
      });
    }
    return;
  }
  if (target && target.closest(".inventory-admin")) {
    if (target.tagName === "DETAILS") {
      target.open = true;
      const summary = target.querySelector("summary");
      if (summary) summary.insertAdjacentElement("afterend", feedback);
      else target.prepend(feedback);
    } else {
      target.prepend(feedback);
    }
  }
  window.requestAnimationFrame(function () {
    feedback.focus({ preventScroll: true });
    feedback.scrollIntoView({ block: "center" });
  });
})();
