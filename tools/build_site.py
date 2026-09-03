#!/usr/bin/env python3
"""Build do site publico (R5, 03/09/2026).

Le os HTML do repositorio e escreve em _site/:
  - remove comentarios HTML e comentarios de linha inteira em <script> (decisoes internas nao vao pro build);
  - injeta <meta name="build-id" content="<sha>"> em todo HTML;
  - escreve version.json (sha, data) — endpoint publico sem segredo;
  - FALHA (exit 1) se algum HTML publicado contiver promessa proibida (ex.: "PARAR" cancela cobranca).
Uso: python tools/build_site.py <sha> [origem] [destino]
"""
import os, re, sys, json, shutil, datetime

SHA = (sys.argv[1] if len(sys.argv) > 1 else 'dev')[:12]
SRC = sys.argv[2] if len(sys.argv) > 2 else '.'
DST = sys.argv[3] if len(sys.argv) > 3 else '_site'

# Frases que NUNCA podem voltar ao site (texto sem tags, minusculas, sem acento)
PROIBIDAS = [
    r'parar[^.]{0,80}cobran[cç]a[^.]{0,40}interrompid',
    r'cobran[cç]a (e|é) interrompida na hora',
    r'cancele (a qualquer hora )?(no|pelo) pr[oó]prio whatsapp',
    r'cancelamos imediatamente',
    r'responda "?sair"?[^.]{0,60}cancel',
    r'mande "?parar"?[^.]{0,60}cancel',
    r'diretamente ao ambiente seguro',
]
IGNORAR_DIRS = {'.git', '.github', 'tools', '_site', 'node_modules', 'preview', 'experiments'}

def limpar_html(txt):
    # comentarios HTML (fora de <script>/<style> tambem sao HTML) — conteudo condicional do IE nao e' usado aqui
    txt = re.sub(r'<!--(?!\[if).*?-->', '', txt, flags=re.S)
    # dentro de <script>: remove linhas que sao SO' comentario (// ...) ou blocos /* */ inteiros
    def limpa_script(m):
        corpo = m.group(2)
        corpo = re.sub(r'(?m)^[ \t]*//.*\n?', '', corpo)
        corpo = re.sub(r'/\*[\s\S]*?\*/', '', corpo)
        return m.group(1) + corpo + m.group(3)
    txt = re.sub(r'(<script\b[^>]*>)([\s\S]*?)(</script>)', limpa_script, txt, flags=re.I)
    return txt

import hashlib, base64
def _sha(txt):
    return "'sha256-" + base64.b64encode(hashlib.sha256(txt.encode('utf-8')).digest()).decode() + "'"

# CSP real (R5): scripts inline entram por hash; handlers inline (onclick=...) por hash + 'unsafe-hashes';
# nada de 'unsafe-eval' nem 'unsafe-inline' para script. Estilos inline (style="...") seguem 'unsafe-inline'.
HOSTS_SCRIPT = "https://www.googletagmanager.com https://cdnjs.cloudflare.com https://static.cloudflareinsights.com"
HOSTS_CONNECT = ("https://manaa-meta-webhook.manaa-fbx.workers.dev https://www.google-analytics.com https://analytics.google.com "
                 "https://*.google-analytics.com https://stats.g.doubleclick.net https://cloudflareinsights.com https://www.googletagmanager.com")
def csp_para(html):
    hashes = []
    for m in re.finditer(r'<script([^>]*)>([\s\S]*?)</script>', html, flags=re.I):
        attrs, corpo = m.group(1), m.group(2)
        if re.search(r'src\s*=', attrs, re.I):
            continue
        if corpo.strip():
            hashes.append(_sha(corpo))
    handlers = []
    for m in re.finditer(r'\son[a-z]+\s*=\s*"([^"]*)"', html, flags=re.I):
        handlers.append(_sha(m.group(1)))
    script_src = "'self' " + HOSTS_SCRIPT + " " + " ".join(sorted(set(hashes)))
    if handlers:
        script_src += " 'unsafe-hashes' " + " ".join(sorted(set(handlers)))
    return ("default-src 'self'; base-uri 'self'; object-src 'none'; frame-src 'none'; form-action 'self'; "
            "script-src " + script_src + "; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https://www.google-analytics.com https://www.googletagmanager.com; media-src 'self'; "
            "connect-src 'self' " + HOSTS_CONNECT + "; upgrade-insecure-requests")

def injetar_csp(txt):
    csp = csp_para(txt).replace('"', '&quot;')
    tag = '<meta http-equiv="Content-Security-Policy" content="%s">' % csp
    return re.sub(r'(<meta charset[^>]*>)', lambda m: m.group(1) + '
' + tag, txt, count=1, flags=re.I)

def injetar_build(txt):
    tag = '<meta name="build-id" content="%s">' % SHA
    if re.search(r'<meta charset', txt, re.I):
        return re.sub(r'(<meta charset[^>]*>)', r'\1\n' + tag, txt, count=1, flags=re.I)
    return re.sub(r'(<head[^>]*>)', r'\1\n' + tag, txt, count=1, flags=re.I)

def texto_visivel(html):
    t = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', ' ', html, flags=re.I)
    t = re.sub(r'<style\b[^>]*>[\s\S]*?</style>', ' ', t, flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'&nbsp;|&#160;', ' ', t)
    t = re.sub(r'\s+', ' ', t).lower()
    return t

erros = []
if os.path.exists(DST):
    shutil.rmtree(DST)
for root, dirs, files in os.walk(SRC):
    dirs[:] = [d for d in dirs if d not in IGNORAR_DIRS]
    for f in files:
        src = os.path.join(root, f)
        rel = os.path.relpath(src, SRC)
        dst = os.path.join(DST, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if f.lower().endswith('.html'):
            txt = open(src, encoding='utf-8').read()
            txt = injetar_csp(injetar_build(limpar_html(txt)))
            vis = texto_visivel(txt)
            for pat in PROIBIDAS:
                if re.search(pat, vis):
                    erros.append('%s: promessa proibida: /%s/' % (rel, pat))
            open(dst, 'w', encoding='utf-8', newline='\n').write(txt)
        else:
            shutil.copy2(src, dst)

open(os.path.join(DST, 'version.json'), 'w', encoding='utf-8').write(json.dumps({
    'build_id': SHA, 'built_at': datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}))
if erros:
    print('BUILD REPROVADO:'); [print('  ' + e) for e in erros]; sys.exit(1)
print('build ok:', SHA, DST)
