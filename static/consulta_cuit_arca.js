/* Consulta explícita, revisión y aplicación: consultar nunca guarda el alta. */
(() => {
  'use strict';
  document.querySelectorAll('[data-arca-form]').forEach(form => {
    const cliente = form.dataset.arcaForm === 'cliente';
    const cuit = form.elements.namedItem(cliente ? 'documento' : 'cuit');
    const box = form.querySelector('[data-arca-lookup]');
    const tipo = form.elements.namedItem('tipo');
    let tipoElegido = false;
    if (tipo) tipo.addEventListener('change', () => { tipoElegido = true; });
    const consult = box.querySelector('[data-arca-consult]');
    const feedback = box.querySelector('[data-arca-feedback]');
    const result = box.querySelector('[data-arca-result]');
    const fields = box.querySelector('[data-arca-fields]');
    const apply = box.querySelector('[data-arca-apply]');
    let datos = null, secuencia = 0, controller = null;
    const limpio = () => cuit.value.replace(/[ .-]/g, '');
    const avisar = (texto, error = false) => {
      feedback.textContent = texto;
      feedback.dataset.error = String(error);
    };
    const invalidar = () => {
      secuencia++;
      if (controller) controller.abort();
      datos = null; result.hidden = true; fields.replaceChildren();
      consult.disabled = false; consult.textContent = 'Consultar ARCA';
      box.removeAttribute('aria-busy');
    };
    cuit.addEventListener('input', () => { invalidar(); avisar('Consultá por CUIT para completar los datos fiscales.'); });
    form.addEventListener('reset', () => { tipoElegido = false; invalidar(); avisar('Consultá por CUIT para completar los datos fiscales.'); });
    cuit.addEventListener('keydown', event => {
      if (event.key === 'Enter') { event.preventDefault(); if (!consult.disabled) consult.click(); }
    });
    consult.addEventListener('click', async () => {
      invalidar();
      const solicitado = limpio();
      if (!/^\d{11}$/.test(solicitado)) { avisar('Para consultar ARCA ingresá un CUIT de 11 dígitos. El DNI se carga manualmente.', true); cuit.focus(); return; }
      const csrf = form.querySelector('[name="_csrf_token"]');
      if (!csrf) { avisar('Actualizá la pantalla e intentá nuevamente. Los datos no se guardaron.', true); return; }
      const intento = secuencia;
      controller = new AbortController();
      const abortar = controller;
      const timer = setTimeout(() => abortar.abort(), 12000);
      consult.disabled = true; consult.textContent = 'Consultando…'; box.setAttribute('aria-busy', 'true');
      avisar('Consultando datos fiscales en ARCA…');
      try {
        const respuesta = await fetch(form.dataset.arcaUrl, {
          method: 'POST', credentials: 'same-origin', signal: abortar.signal,
          headers: {'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'},
          body: new URLSearchParams({cuit: solicitado, _csrf_token: csrf.value})
        });
        if (intento !== secuencia || limpio() !== solicitado) return;
        if (!respuesta.headers.get('content-type')?.includes('application/json')) throw new Error('sesion');
        const payload = await respuesta.json();
        if (intento !== secuencia || limpio() !== solicitado) return;
        if (!respuesta.ok || !payload.ok) { avisar(payload.mensaje || 'No se pudo consultar ARCA. Podés continuar manualmente.', true); return; }
        if (payload.datos?.cuit !== solicitado) throw new Error('cuit');
        datos = payload.datos;
        for (const [clave, etiqueta] of [['cuit','CUIT'],['razon_social','Nombre / razón social'],['domicilio','Domicilio fiscal'],['localidad','Localidad'],['provincia','Provincia'],['codigo_postal','Código postal']]) {
          const grupo = document.createElement('div');
          const dt = document.createElement('dt'); dt.textContent = etiqueta;
          const dd = document.createElement('dd'); dd.textContent = datos[clave] || 'No informado por ARCA';
          grupo.append(dt, dd); fields.append(grupo);
        }
        result.hidden = false;
        avisar('Datos obtenidos de ARCA. Revisalos y pulsá “Usar estos datos”.');
      } catch (_) {
        if (intento === secuencia) avisar('No se pudo completar la consulta. Tus datos se conservaron; podés continuar manualmente.', true);
      } finally {
        clearTimeout(timer);
        if (intento === secuencia) { consult.disabled = false; consult.textContent = 'Consultar ARCA'; box.removeAttribute('aria-busy'); }
      }
    });
    apply.addEventListener('click', () => {
      if (!datos || datos.cuit !== limpio()) { invalidar(); avisar('El CUIT cambió. Volvé a consultar ARCA.', true); return; }
      const mapa = { [cliente ? 'nombre' : 'razon_social']: 'razon_social', domicilio:'domicilio', localidad:'localidad', provincia:'provincia', codigo_postal:'codigo_postal' };
      if (cliente) mapa.tipo = 'tipo';
      let aplicados = 0, conservados = 0, pendientes = 0;
      const reemplazar = box.querySelector('[data-arca-replace]').checked;
      const cambios = [];
      for (const [destino, origen] of Object.entries(mapa)) {
        const input = form.elements.namedItem(destino);
        const valor = String(datos[origen] || '');
        if (!valor) continue;
        if (!input || input.disabled) { pendientes++; continue; }
        if (!reemplazar && (destino === 'tipo' ? tipoElegido : input.value.trim())) { conservados++; continue; }
        if (input.maxLength > 0 && valor.length > input.maxLength) { avisar('Un dato de ARCA supera el largo permitido. Revisá y completá el formulario manualmente.', true); return; }
        cambios.push([input, valor]);
      }
      cambios.forEach(([input, valor]) => { input.value = valor; input.dispatchEvent(new Event('change', {bubbles:true})); aplicados++; });
      result.hidden = true;
      avisar(`Se completaron ${aplicados} campos. ${conservados ? `Se conservaron ${conservados} campos ya cargados. ` : ''}${pendientes ? 'Domicilio y código postal requieren preparar el maestro de clientes. ' : ''}Revisá el formulario y guardá cuando esté correcto.`);
      datos = null;
    });
    box.querySelector('[data-arca-dismiss]').addEventListener('click', () => { invalidar(); avisar('Consulta descartada. El formulario conserva tus datos.'); });
  });
  document.querySelectorAll('[data-cliente-datos]').forEach(button => {
    const dialog = document.getElementById(button.dataset.clienteDatos);
    button.addEventListener('click', () => dialog.showModal());
    dialog.querySelector('[data-cliente-cerrar]').addEventListener('click', () => dialog.close());
  });
})();
