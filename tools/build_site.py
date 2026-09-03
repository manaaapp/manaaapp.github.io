#!/usr/bin/env python3
"""Build do site publico (R5, 03/09/2026).

Le os HTML do repositorio e escreve em _site/:
  - remove comentarios HTML e comentarios de linha inteira em <script> (decisoes internas nao vao pro build);
  - injeta <meta name="build-id" content="<sha>"> e uma CSP real por pagina (hash de cada script inline,
    'unsafe-hashes' para handlers on*=, sem 'unsafe-inline'/'unsafe-eval' para script);
  - escreve version.json (sha, data) — endpoint publico sem segredo;
  - FALHA (exit 1) se algum HTML publicado contiver promessa proibida (ex.: "PARAR" cancela cobranca).
Uso: python tools/build_site.py <sha> [origem] [destino]
"""
import os, re, sys, json, shutil, datetime, hashlib, base64

SHA = (sys.argv[1] if len(sys.argv) > 1 else 'dev')[:12]
SRC = sys.argv[2] if len(sys.argv) > 2 else '.'
DST = sys.argv[3] if len(sys.argv) > 3 else '_site'

PROIBIDAS = [
    r'parar[^.]{0,80}cobran[cç]a[^.]{0,40}interrompid',
    r'cobran[cç]a (e|é) interrompida na hora',
    r'cancele (a qualquer hora )?(no|pelo) pr[oó]prio whatsapp',
    r'cancelamos imediatamente',
    r'responda "?sair"?[^.]{0,60}cancel',
    r'mande "?parar"?[^.]{0,60}cancel',
    r'diretamente ao ambiente seguro',
]
IGNORAR_DIRS = {'.git', '.github', 'tools', '_site', 'node_modules', 'preview', 'experiments', '.gh-pages-wt'}

HOSTS_SCRIPT = "https://www.googletagmanager.com https://cdnjs.cloudflare.com https://static.cloudflareinsights.com"
HOSTS_CONNECT = ("https://manaa-meta-webhook.manaa-fbx.workers.dev https://www.google-analytics.com https://analytics.google.com "
                 "https://*.google-analytics.com https://stats.g.doubleclick.net https://cloudflareinsights.com https://www.googletagmanager.com")

RE_SCRIPT = re.compile(r'<script\b([^>]*)>([\s\S]*?)</script>', re.I)
RE_HANDLER = re.compile(r'\son[a-z]+\s*=\s*"([^"]*)"', re.I)
RE_CHARSET = re.compile(r'(<meta charset[^>]*>)', re.I)
RE_HEAD = re.compile(r'(<head[^>]*>)', re.I)


def sha256_csp(txt):
    return "'sha256-" + base64.b64encode(hashlib.sha256(txt.encode('utf-8')).digest()).decode() + "'"


def limpar_html(txt):
    txt = re.sub(r'<!--(?!\[if).*?-->', '', txt, flags=re.S)

    def limpa_script(m):
        corpo = m.group(2)
        corpo = re.sub(r'(?m)^[ \t]*//.*\n?', '', corpo)
        corpo = re.sub(r'/\*[\s\S]*?\*/', '', corpo)
        return m.group(1) + corpo + m.group(3)
    return re.sub(r'(<script\b[^>]*>)([\s\S]*?)(</script>)', limpa_script, txt, flags=re.I)


def csp_para(html):
    hashes = set()
    for m in RE_SCRIPT.finditer(html):
        attrs, corpo = m.group(1), m.group(2)
        if re.search(r'\bsrc\s*=', attrs, re.I):
            continue
        if corpo.strip():
            hashes.add(sha256_csp(corpo))
    handlers = set(sha256_csp(m.group(1)) for m in RE_HANDLER.finditer(html))
    script_src = "'self' " + HOSTS_SCRIPT + " " + " ".join(sorted(hashes))
    if handlers:
        script_src += " 'unsafe-hashes' " + " ".join(sorted(handlers))
    return ("default-src 'self'; base-uri 'self'; object-src 'none'; frame-src 'none'; form-action 'self'; "
            "script-src " + script_src + "; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: https://www.google-analytics.com https://www.googletagmanager.com; media-src 'self'; "
            "connect-src 'self' " + HOSTS_CONNECT + "; upgrade-insecure-requests")


def injetar_head(txt):
    build = '<meta name="build-id" content="%s">' % SHA
    csp = '<meta http-equiv="Content-Security-Policy" content="%s">' % csp_para(txt).replace('"', '&quot;')
    bloco = build + '\n' + csp
    if RE_CHARSET.search(txt):
        return RE_CHARSET.sub(lambda m: m.group(1) + '\n' + bloco, txt, count=1)
    return RE_HEAD.sub(lambda m: m.group(1) + '\n' + bloco, txt, count=1)


def texto_visivel(html):
    t = re.sub(r'<script\b[^>]*>[\s\S]*?</script>', ' ', html, flags=re.I)
    t = re.sub(r'<style\b[^>]*>[\s\S]*?</style>', ' ', t, flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'&nbsp;|&#160;', ' ', t)
    return re.sub(r'\s+', ' ', t).lower()


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
            txt = injetar_head(limpar_html(txt))
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
    print('BUILD REPROVADO:')
    for e in erros:
        print('  ' + e)
    sys.exit(1)
print('build ok:', SHA, DST)
