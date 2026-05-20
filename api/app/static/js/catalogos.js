/* Catálogos de valores controlados para los desplegables del frontend.
   Coherentes con los descritos en el documento (cap. 4 y 5).             */

window.CATALOGOS = {
  cursos: ['1º ESO', '2º ESO', '3º ESO', '4º ESO'],

  // Matemáticas A y B son los dos itinerarios oficiales de 4.º ESO
  // según el RD 217/2022 y la Orden EFP/754/2022. Para 1.º a 3.º se
  // usa "Matemáticas" sin sufijo.
  materias: ['Tecnología', 'Lengua', 'Matemáticas', 'Matemáticas A', 'Matemáticas B', 'Inglés'],

  metodologias: [
    'Aprendizaje basado en proyectos (ABP)',
    'Aprendizaje cooperativo',
    'Flipped classroom',
    'Aprendizaje basado en retos',
    'Gamificación',
    'Aprendizaje-servicio',
    'Trabajo por proyectos',
    'Clase magistral participativa',
  ],
};

/**
 * Rellena un <select> con las opciones del catálogo indicado.
 * @param {HTMLSelectElement} sel
 * @param {string[]} opciones
 * @param {{placeholder?: string, valor?: string}} opts
 */
window.rellenarSelect = function (sel, opciones, opts = {}) {
  if (!sel) return;
  sel.innerHTML = '';
  if (opts.placeholder) {
    const op = document.createElement('option');
    op.value = '';
    op.textContent = opts.placeholder;
    sel.appendChild(op);
  }
  for (const v of opciones) {
    const op = document.createElement('option');
    op.value = v;
    op.textContent = v;
    sel.appendChild(op);
  }
  // Si el valor preexistente no está en la lista, lo añadimos para no
  // perderlo (situaciones antiguas creadas con texto libre).
  if (opts.valor && !opciones.includes(opts.valor)) {
    const op = document.createElement('option');
    op.value = opts.valor;
    op.textContent = opts.valor + ' (heredado)';
    sel.appendChild(op);
  }
  if (opts.valor) sel.value = opts.valor;
};
