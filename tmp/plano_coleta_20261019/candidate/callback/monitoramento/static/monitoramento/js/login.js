(() => {
  'use strict';
  const formulario = document.querySelector('[data-formulario-login]');
  if (!formulario) return;

  const senha = formulario.querySelector('input[name="password"]');
  const avisoCaps = document.getElementById('aviso-caps-lock');
  const botao = formulario.querySelector('[data-botao-entrar]');
  const textoBotao = formulario.querySelector('[data-texto-botao]');

  const atualizarCaps = (evento) => {
    avisoCaps.hidden = !evento.getModifierState('CapsLock');
  };
  senha.addEventListener('keyup', atualizarCaps);
  senha.addEventListener('keydown', atualizarCaps);
  senha.addEventListener('blur', () => { avisoCaps.hidden = true; });

  formulario.addEventListener('submit', () => {
    botao.disabled = true;
    textoBotao.textContent = 'Entrando…';
    formulario.setAttribute('aria-busy', 'true');
  });

  window.addEventListener('pageshow', () => {
    botao.disabled = false;
    textoBotao.textContent = 'Entrar';
    formulario.removeAttribute('aria-busy');
  });

  const avisoErro = document.querySelector('[data-aviso-erro]');
  const campoInvalido = formulario.querySelector('[aria-invalid="true"]');
  if (avisoErro) avisoErro.focus();
  else if (campoInvalido) campoInvalido.focus();
})();
