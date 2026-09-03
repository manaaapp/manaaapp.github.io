#!/usr/bin/env python3
"""Publica o site (R5, 03/09/2026).

Fluxo: build (tools/build_site.py) -> guarda de promessas proibidas -> commit do build no branch gh-pages
-> push -> espera a borda -> verificacao EXTERNA (tools/check_site.sh). Se a guarda reprovar, NADA e' publicado.
Uso: python tools/publish.py            (publica o HEAD atual de master)
     python tools/publish.py --so-build (apenas build + guarda)
"""
import os, subprocess, sys, shutil, time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(RAIZ)
def sh(cmd, check=True, capture=False):
    r = subprocess.run(cmd, shell=True, text=True, capture_output=capture)
    if check and r.returncode != 0:
        raise SystemExit('falhou: ' + cmd + ('\n' + r.stdout + r.stderr if capture else ''))
    return r.stdout.strip() if capture else ''

sha = sh('git rev-parse --short=12 HEAD', capture=True)
if sh('git status --porcelain', capture=True):
    raise SystemExit('arvore suja: commit ou descarte antes de publicar')
print('build de', sha)
sh('python tools/build_site.py %s . _site' % sha)  # exit 1 = guarda reprovou -> nada publicado
if '--so-build' in sys.argv:
    print('so build; nada publicado'); sys.exit(0)

wt = os.path.join(RAIZ, '.gh-pages-wt')
if os.path.exists(wt):
    sh('git worktree remove --force .gh-pages-wt', check=False)
    shutil.rmtree(wt, ignore_errors=True)
sh('git fetch origin gh-pages', check=False)
if sh('git ls-remote --heads origin gh-pages', capture=True):
    sh('git worktree add .gh-pages-wt origin/gh-pages')
    sh('git -C .gh-pages-wt checkout -B gh-pages')
else:
    sh('git worktree add --detach .gh-pages-wt')
    sh('git -C .gh-pages-wt checkout --orphan gh-pages')
    sh('git -C .gh-pages-wt rm -rfq . ', check=False)
# limpa e copia o build
for nome in os.listdir(wt):
    if nome == '.git': continue
    alvo = os.path.join(wt, nome)
    shutil.rmtree(alvo) if os.path.isdir(alvo) else os.remove(alvo)
for nome in os.listdir('_site'):
    src = os.path.join('_site', nome); dst = os.path.join(wt, nome)
    shutil.copytree(src, dst) if os.path.isdir(src) else shutil.copy2(src, dst)
open(os.path.join(wt, '.nojekyll'), 'w').close()
sh('git -C .gh-pages-wt add -A')
if sh('git -C .gh-pages-wt status --porcelain', capture=True):
    sh('git -C .gh-pages-wt -c user.name="Luigi Funaro" -c user.email="dev.luigifunaro@gmail.com" commit -q -m "build %s"' % sha)
    sh('git -C .gh-pages-wt push -q origin gh-pages')
    print('publicado gh-pages =', sha)
else:
    print('gh-pages ja estava igual ao build')
sh('git worktree remove --force .gh-pages-wt', check=False)

# espera a borda e confere de fora
for i in range(30):
    v = sh('curl -s -H "Cache-Control: no-cache" "https://manaaapp.com/version.json?nc=%d"' % int(time.time()), capture=True)
    if '"%s"' % sha in v:
        break
    time.sleep(10)
r = subprocess.run(['bash', 'tools/check_site.sh', sha])
sys.exit(r.returncode)
