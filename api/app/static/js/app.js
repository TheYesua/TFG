/* Pequeño script global: detecta sesión y oculta/muestra elementos
   con [data-auth="required"] o [data-auth="anonymous"]. También
   conecta el botón de logout. */

(async function () {
  const setAuthState = (autenticado) => {
    document.querySelectorAll('[data-auth="required"]').forEach((el) => {
      el.hidden = !autenticado;
    });
    document.querySelectorAll('[data-auth="anonymous"]').forEach((el) => {
      el.hidden = autenticado;
    });
  };

  let usuario = null;
  try {
    const res = await fetch('/me', { headers: { 'Accept': 'application/json' } });
    if (res.ok) usuario = await res.json();
  } catch (_) { /* offline o similar */ }

  setAuthState(!!usuario);

  // Mensaje en la página de inicio
  const estadoMsg = document.getElementById('estado-msg');
  if (estadoMsg) {
    estadoMsg.textContent = usuario
      ? `Sesión iniciada como ${usuario.nombre} (${usuario.correo}).`
      : 'No hay sesión iniciada.';
  }

  // Botón de logout
  const btn = document.getElementById('logout-btn');
  if (btn) {
    btn.addEventListener('click', async () => {
      await fetch('/auth/logout', { method: 'POST' });
      window.location.href = '/';
    });
  }
})();
