/* Manaã — chaves de funcionalidade do site (R5, 03/09/2026).
   pixOnly = true: some da interface tudo que nao e' Pix Automatico mensal (cartao, anual, parcelado, selos de bandeira).
   Nada e' apagado: os elementos carregam data-flag="cartao" ou data-flag="anual" e ficam ocultos.
   Para reabrir: pixOnly=false aqui, PIX_ONLY="0" no Worker, e revisar Termos/FAQ. */
window.MANAA_FLAGS = { pixOnly: false };
(function () {
  function aplicar() {
    if (!window.MANAA_FLAGS.pixOnly) return;
    document.querySelectorAll('[data-flag="cartao"],[data-flag="anual"]').forEach(function (el) {
      el.hidden = true;
      el.querySelectorAll('input').forEach(function (i) { i.checked = false; i.disabled = true; });
    });
    document.documentElement.classList.add('pix-only');
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aplicar); else aplicar();
})();
