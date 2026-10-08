"use strict";
document.addEventListener("click", function (event) {
  const button = event.target.closest("[data-fiscal-cancel]");
  if (!button) return;
  const editor = button.closest(".fiscal-editor");
  if (!editor) return;
  editor.querySelectorAll("form").forEach(function (form) { form.reset(); });
  editor.open = false;
  editor.querySelector("summary").focus({ preventScroll: true });
});
