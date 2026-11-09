"""Gera a imagem da prévia de compartilhamento (site/previa/brasil-em-camadas.jpg, 1200 × 630 px): o próprio globo do
site com a luz "População" acesa, fotografado num navegador sem janela (Playwright + Chromium).

É um estudo, roda só à mão (não entra no robô):
    pip install playwright pillow && python -m playwright install chromium
    python scripts/estudos/previa_compartilhamento.py                 (as duas versões, em scripts/estudos/imagens/)
    python scripts/estudos/previa_compartilhamento.py --versao b --site   (grava a versão escolhida em site/previa/)
Versões: a = só o globo; b = o globo com o nome e a frase do título, nas letras do site (a escolhida em 08/11/2026);
c = estudo de 09/11/2026: tudo dentro do quadrado do meio (630 × 630), que é o que o WhatsApp mostra: o nome em cima, o
Brasil no meio e a frase embaixo (com --versao c, grava também previa_c_quadrado.jpg, o recorte que o WhatsApp faz).
O relevo de altitude (ladrilhos da AWS) não abre no ambiente do assistente; sem ele a foto sai sem o sombreado de perto,
que nessa aproximação quase não aparece.
"""
import argparse
import functools
import http.server
import io
import threading
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]
SITE = RAIZ / "site"
SAIDA_ESTUDO = RAIZ / "scripts" / "estudos" / "imagens"
SAIDA_SITE = SITE / "previa" / "brasil-em-camadas.jpg"
L, A = 1200, 630          # tamanho da prévia (Open Graph e cartão grande do X)
ESCALA = 1.5              # fotografa maior e reduz, para as bordas ficarem lisas

ESCONDE = """
.top,.where,.legend,.unfold,.dock,.foot,.carregando,.sem3d,.maplibregl-control-container,#apoio-fim{display:none!important}
html,body{margin:0!important;overflow:hidden!important;background:#05070d!important}
.stage{height:100vh!important}
"""

NOME = """
<div id="previa-nome" style="position:fixed;z-index:50;right:64px;top:50%;transform:translateY(-50%);text-align:right;
  pointer-events:none;color:#f4c552;text-shadow:0 2px 18px rgba(0,0,0,.85),0 0 2px rgba(0,0,0,.9)">
  <div style="font-family:'Big Shoulders Display',sans-serif;font-weight:800;font-size:88px;line-height:.92;
    letter-spacing:.5px">Brasil em<br>Camadas</div>
  <div style="margin-top:18px;font-family:Barlow,sans-serif;font-weight:500;font-size:27px;line-height:1.25;color:#f3e6c8">
    mapa do Brasil<br>com dados verificáveis</div>
</div>
"""


NOME_C = """
<div id="previa-nome" style="position:fixed;z-index:50;left:0;right:0;top:0;bottom:0;pointer-events:none;
  text-shadow:0 2px 18px rgba(0,0,0,.9),0 0 2px rgba(0,0,0,.9)">
  <div style="position:absolute;left:0;right:0;top:26px;text-align:center;color:#f4c552;font-family:'Big Shoulders Display',sans-serif;
    font-weight:800;font-size:70px;line-height:1;letter-spacing:.5px">Brasil em Camadas</div>
  <div style="position:absolute;left:0;right:0;bottom:26px;text-align:center;color:#f3e6c8;font-family:Barlow,sans-serif;
    font-weight:500;font-size:28px;line-height:1.2">mapa do Brasil com dados verificáveis</div>
</div>
"""


def servidor():
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE))
    h.log_message = lambda *a, **k: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def fotografar(pagina, versao, centro, zoom):
    pagina.evaluate("""([c, z]) => new Promise(ok => {
        const m = window.__mapa; m.resize(); m.jumpTo({ center: c, zoom: z, pitch: 0, bearing: 0 });
        m.once('idle', () => setTimeout(ok, 400)); m.triggerRepaint(); })""", [centro, zoom])
    if versao in ("b", "c"):
        pagina.evaluate("h => document.body.insertAdjacentHTML('beforeend', h)", NOME if versao == "b" else NOME_C)
        pagina.evaluate("document.fonts.ready.then(() => true)")
        pagina.wait_for_timeout(400)
    png = pagina.screenshot(type="png")
    if versao in ("b", "c"):
        pagina.evaluate("document.getElementById('previa-nome').remove()")
    return Image.open(io.BytesIO(png)).convert("RGB").resize((L, A), Image.LANCZOS)


def principal():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--versao", choices=["a", "b", "c", "ambas"], default="ambas")
    ap.add_argument("--site", action="store_true", help="grava em site/previa/ (só com uma versão)")
    ap.add_argument("--zoom-a", type=float, default=2.8)
    ap.add_argument("--zoom-b", type=float, default=2.8)
    ap.add_argument("--zoom-c", type=float, default=2.45)
    args = ap.parse_args()
    versoes = ["a", "b"] if args.versao == "ambas" else [args.versao]
    s = servidor()
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                          "--ignore-gpu-blocklist"])
            ctx = nav.new_context(viewport={"width": L, "height": A}, device_scale_factor=ESCALA)
            ctx.add_init_script("try { localStorage.setItem('bec-painel', 'recolhido'); } catch (e) {}")
            ctx.route("**/*goatcounter.com/**", lambda r: r.abort())
            ctx.route("**/elevation-tiles-prod.s3.amazonaws.com/**", lambda r: r.abort())
            pagina = ctx.new_page()
            pagina.goto(f"http://127.0.0.1:{s.server_address[1]}/", wait_until="load")
            pagina.wait_for_function("window.MAPA_PRONTO === true", timeout=240000)
            pagina.add_style_tag(content=ESCONDE)
            pagina.evaluate("""() => new Promise(ok => {
                const b = document.querySelector('#luzes button[data-l="pop"]'); b.click();
                const espera = () => (window.__mapa.getLayer('luz-grade') ? ok() : setTimeout(espera, 200)); espera(); })""")
            # sem nomes e sem os pontos das capitais: na miniatura eles viram poeira; ficam o globo, as luzes e o contorno
            pagina.evaluate("""() => { const m = window.__mapa;
                m.getStyle().layers.forEach(l => { if (l.type === 'symbol' || ['capitais', 'capviz', 'capviz-ponto', 'ilhas-ponto'].includes(l.id))
                  m.setLayoutProperty(l.id, 'visibility', 'none'); }); }""")
            pagina.wait_for_timeout(1500)
            for v in versoes:
                # na versão b o nome fica à direita, então o Brasil vai um pouco para a esquerda
                centro, zoom = {"a": ([-54, -14.5], args.zoom_a), "b": ([-46, -14.5], args.zoom_b),
                                "c": ([-53.5, -15.2], args.zoom_c)}[v]
                img = fotografar(pagina, v, centro, zoom)
                destino = SAIDA_SITE if args.site else SAIDA_ESTUDO / f"previa_{v}.jpg"
                destino.parent.mkdir(parents=True, exist_ok=True)
                img.save(destino, "JPEG", quality=84, optimize=True, progressive=True)
                print(f"[prévia] {v}: {destino.relative_to(RAIZ)} ({destino.stat().st_size // 1024} KB)")
                if v == "c" and not args.site:
                    q = SAIDA_ESTUDO / "previa_c_quadrado.jpg"
                    img.crop(((L - A) // 2, 0, (L + A) // 2, A)).save(q, "JPEG", quality=84, optimize=True)
                    print(f"[prévia] recorte do WhatsApp: {q.relative_to(RAIZ)}")
            nav.close()
    finally:
        s.shutdown()


if __name__ == "__main__":
    principal()
