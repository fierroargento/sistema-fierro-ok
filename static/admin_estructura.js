document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-estructura-cancel]");
  if (!button) return;
  const editor = button.closest(".estructura-editor");
  if (!editor) return;
  editor.querySelectorAll("form").forEach((form) => form.reset());
  editor.open = false;
  editor.querySelector("summary")?.focus({preventScroll: true});
});
