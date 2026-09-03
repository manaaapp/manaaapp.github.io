#!/usr/bin/env bash
# Verificacao EXTERNA do site publicado (R5): roda de fora, sem cache, e compara com o build esperado.
# Uso: tools/check_site.sh <build-id esperado>
set -u
ESPERADO="${1:-}"
HOST="${HOST:-https://manaaapp.com}"
falhas=0
ok(){ echo "  ok   $1"; }
fail(){ echo "  FALHA $1"; falhas=$((falhas+1)); }

v=$(curl -s -H 'Cache-Control: no-cache' "$HOST/version.json?nc=$RANDOM")
vid=$(printf '%s' "$v" | sed -n 's/.*"build_id": *"\([^"]*\)".*/\1/p')
if [ -n "$ESPERADO" ] && [ "$vid" = "$ESPERADO" ]; then ok "version.json = $vid"; else fail "version.json = '$vid' (esperado '$ESPERADO')"; fi

for pg in index.html faq.html termos.html privacidade.html onboarding.html conta.html pagamento-sucesso.html; do
  html=$(curl -s -H 'Cache-Control: no-cache' "$HOST/$pg?nc=$RANDOM")
  bid=$(printf '%s' "$html" | grep -o 'name="build-id" content="[^"]*"' | head -1 | sed 's/.*content="//;s/"//')
  if [ -n "$ESPERADO" ] && [ "$bid" != "$ESPERADO" ]; then fail "$pg build-id='$bid'"; else ok "$pg build-id=$bid"; fi
  vis=$(printf '%s' "$html" | sed -e 's/<script[^>]*>.*<\/script>//g' -e 's/<[^>]*>/ /g' | tr '\n' ' ' | tr -s ' ' | tr '[:upper:]' '[:lower:]')
  if printf '%s' "$vis" | grep -q -E 'cobran[cç]a (e|é) interrompida na hora|cancele (a qualquer hora )?(no|pelo) pr[oó]prio whatsapp|cancelamos imediatamente|diretamente ao ambiente seguro'; then fail "$pg contem promessa proibida"; fi
  if printf '%s' "$html" | grep -q '<!--'; then fail "$pg ainda tem comentario HTML"; fi
done
echo "falhas: $falhas"
exit $falhas
