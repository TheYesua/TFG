# Requisitos de accesibilidad — pendientes para Frontend

Recogidos de la experiencia en CESMA. A incorporar como **requisitos no funcionales** en
la memoria y como **criterios de aceptación** del frontend cuando se implemente. La
referencia técnica es WCAG 2.1 nivel AA.

## Enlaces y secciones obligatorias

- Enlace **"Pasar al contenido principal"** como primer elemento focalizable.
- Enlace de **Accesibilidad** en el footer con:
  - Nivel de conformidad declarado.
  - Declaración de accesibilidad.
  - Formulario de quejas / sugerencias.
  - Mención a la **Unidad Responsable de Accesibilidad (URA)**.
- **Mapa web** y sección de **Ayuda** accesibles desde el footer.

## Fallos críticos a evitar (WCAG)

- **Uso del color**: no transmitir información solo mediante color (apto para daltonismo).
- **Teclado**: toda la navegación debe ser posible sin ratón (`tab`, `enter`, `esc`,
  `flechas`).
- **Foco visible**: los elementos interactivos deben mostrar claramente el foco
  (no eliminar el `outline` por defecto sin sustituirlo).

## Fallos frecuentes a evitar

- **Contenido no textual**: alt text descriptivo en imágenes (no decorativas), `aria-label`
  en iconos.
- **Encabezados y etiquetas**: jerarquía `<h1>` → `<h6>` coherente, `<label>` asociado a
  cada `<input>`.
- **Contraste mínimo**: 4.5:1 para texto normal, 3:1 para texto grande (revisar paleta
  cromática del cap. 5).

## Otros

- Usar listas semánticas: `<ul><li><a>`, no `<div>` apilados.
- Diseño **responsive** que no fuerce orientación.
- Permitir **pausar / detener / ocultar** animaciones (incluyendo `prefers-reduced-motion`).
- **Prevención de errores** en formularios: confirmación, posibilidad de revertir, edición.
- Permitir **ampliación** del contenido (zoom hasta 200% sin scroll horizontal).

## Formación recomendada (referencia)

- Píldoras de Accesibilidad (diseño).
- Insuit Compliance.

## Cómo lo abordaremos en este proyecto

1. **Plantillas Jinja base** con landmarks ARIA (`<header>`, `<nav>`, `<main>`, `<footer>`)
   y skip-link desde el primer momento.
2. **CSS** con foco visible explícito y contrastes verificados con la paleta del cap. 5.
3. Auditoría con **axe-core** o **Lighthouse** integrada en CI.
4. Documento de **Declaración de accesibilidad** en `/accesibilidad` antes del despliegue
   final.

> Estos requisitos se trasladarán al cap. 3 como `RNF-Axx` cuando volvamos a la memoria.
