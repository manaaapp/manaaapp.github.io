/* Manaã — chaves de funcionalidade do site (R5.1, 03/09/2026). Controles independentes, decisão do dono:
   manter Pix e cartão, mensal e anual; o que NÃO pode existir é formulário próprio de cartão (dado completo
   atravessando Worker/n8n). Cartão volta pelo Checkout hospedado do ASAAS (CARD_HOSTED_CHECKOUT_ENABLED).
   Servidor (Worker/n8n) tem as mesmas chaves e é quem decide de verdade; aqui é só a interface. */
window.MANAA_FLAGS = {
  PIX_AUTOMATIC_ENABLED: true,        // mensal por Pix Automático (QR do 1º mês + autorização)
  PIX_SINGLE_ENABLED: true,           // anual por Pix comum (cobrança única)
  CARD_HOSTED_CHECKOUT_ENABLED: false, // cartão pela página hospedada do ASAAS (em implantação)
  CARD_DIRECT_INPUT_ENABLED: false,   // formulário próprio de cartão: NUNCA em produção
  MONTHLY_ENABLED: true,
  ANNUAL_SINGLE_ENABLED: true,        // anual à vista / parcelado
  ANNUAL_RECURRING_ENABLED: false,    // anual automático (Pix Automático anual / cartão recorrente anual)
  GIFT_ENABLED: false
};
(function () {
  var F = window.MANAA_FLAGS;
  function indisponivel(el, texto) {
    el.classList.add('indisponivel');
    el.querySelectorAll('input').forEach(function (i) { i.checked = false; i.disabled = true; });
    var t = el.querySelector('.pay-opt-desc');
    if (t && !el.dataset.avisado) { t.textContent = texto; el.dataset.avisado = '1'; }
    el.style.opacity = '0.55';
    el.style.pointerEvents = 'none';
  }
  function aplicar() {
    var cartaoOk = F.CARD_HOSTED_CHECKOUT_ENABLED || F.CARD_DIRECT_INPUT_ENABLED;
    document.querySelectorAll('[data-flag="cartao"]').forEach(function (el) {
      if (cartaoOk) return;
      if (el.classList.contains('pay-opt')) indisponivel(el, 'Temporariamente indisponível: em breve pelo ambiente seguro do ASAAS.');
      else el.hidden = true; // campos do cartão e selos de bandeira
    });
    if (!F.ANNUAL_SINGLE_ENABLED) document.querySelectorAll('[data-flag="anual"]').forEach(function (el) { el.hidden = true; });
    document.documentElement.classList.toggle('sem-cartao', !cartaoOk);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aplicar); else aplicar();
})();
