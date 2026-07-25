/* Manaã — motor de movimento sutil sobre GSAP + ScrollTrigger.
   Progressive enhancement: se algo falhar (GSAP não carrega, erro, etc.),
   removemos a classe motion-on e TODO o conteúdo volta a ficar visível.
   Movimento contido de propósito — público 50-70, leitura calma. */
(function () {
  var root = document.documentElement;
  var SEL = '.section-label,.section-title,.section-desc,.feature,.step,.plan,.card,.faq-item,.hero-text,.hero-media,[data-reveal]';

  function showAll() { root.classList.remove('motion-on'); }

  // usuário pediu menos movimento → não anima nada
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    showAll();
    return;
  }

  function init() {
    if (!window.gsap || !window.ScrollTrigger) { showAll(); return; }
    try {
      gsap.registerPlugin(ScrollTrigger);
      var els = document.querySelectorAll(SEL);
      els.forEach(function (el) {
        gsap.fromTo(el,
          { opacity: 0, y: 18 },
          {
            opacity: 1, y: 0, duration: 0.6, ease: 'power2.out',
            scrollTrigger: { trigger: el, start: 'top 90%', once: true }
          });
      });
      ScrollTrigger.refresh();
    } catch (e) {
      showAll();
    }
  }

  if (document.readyState !== 'loading') init();
  else document.addEventListener('DOMContentLoaded', init);

  // failsafe duplo: se o GSAP não estiver disponível, garante conteúdo visível
  window.addEventListener('load', function () {
    if (!window.gsap || !window.ScrollTrigger) showAll();
    else setTimeout(function () { try { ScrollTrigger.refresh(); } catch (e) {} }, 150);
  });
  setTimeout(function () { if (!window.gsap || !window.ScrollTrigger) showAll(); }, 3500);
})();
