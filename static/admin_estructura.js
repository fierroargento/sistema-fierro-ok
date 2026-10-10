document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-estructura-cancel]");
  if (!button) return;
  event.preventDefault();
  const editor = button.closest(".estructura-editor");
  if (!editor) return;
  editor.querySelectorAll("form").forEach((form) => form.reset());
  editor.open = false;
  editor.querySelector("summary")?.focus({preventScroll: true});
});

// Enter en un campo de texto no debe enviar accidentalmente un alta o edición.
// Los botones conservan su activación por teclado.
document.addEventListener("keydown", (event) => {
  if (event.key !== "Enter" || event.isComposing) return;
  const field = event.target;
  if (field.tagName !== "INPUT" || !field.closest(".estructura-editor")) return;
  if (["button", "submit", "reset", "checkbox", "radio", "file"].includes(field.type)) return;
  event.preventDefault();
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!form.closest(".estructura-editor") || event.defaultPrevented) return;
  const action = form.querySelector('input[name="accion"]')?.value;
  if (!action?.startsWith("crear_") && action !== "agregar_producto_catalogo") return;
  if (!window.confirm("¿Confirmar la creación de este registro con los datos ingresados?")) {
    event.preventDefault();
  }
});
