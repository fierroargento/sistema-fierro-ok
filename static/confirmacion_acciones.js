(function () {
  "use strict";
  document.querySelectorAll('input[type="hidden"][data-confirm-word]').forEach(function (input) {
    const form = input.form;
    if (!form) return;
    form.addEventListener("submit", function (event) {
      input.value = "";
      if (event.defaultPrevented) return;
      const message = input.getAttribute("data-confirm-message");
      const word = input.getAttribute("data-confirm-word");
      if (!message || !word || !window.confirm(message)) {
        event.preventDefault();
        return;
      }
      input.value = word;
    });
    form.addEventListener("reset", function () { input.value = ""; });
  });
})();
