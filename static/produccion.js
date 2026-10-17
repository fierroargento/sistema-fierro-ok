/* Gestion local de ventanas; solo el envio explicito del formulario guarda. */
document.addEventListener('DOMContentLoaded', () => {
  const page = document.querySelector('.production-page');
  if (!page) return;
  page.addEventListener('click', (event) => {
    const trigger = event.target.closest('[data-production-dialog]');
    if (trigger) {
      const dialog = document.getElementById(trigger.dataset.productionDialog);
      if (dialog && !dialog.open) {
        dialog.querySelectorAll('form').forEach(form => form.reset());
        dialog.showModal();
      }
    }
    const close = event.target.closest('[data-production-close]');
    if (close) close.closest('dialog').close();
    const cancelCreate = event.target.closest('[data-lot-create-cancel]');
    if (cancelCreate) {
      cancelCreate.closest('form').reset();
      cancelCreate.closest('details').open = false;
    }
  });
  page.querySelectorAll('.production-dialog').forEach(dialog => {
    dialog.addEventListener('close', () => {
      dialog.querySelectorAll('form').forEach(form => form.reset());
    });
  });
});
