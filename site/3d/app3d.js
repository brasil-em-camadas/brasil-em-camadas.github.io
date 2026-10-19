/* Brasil em Camadas — mapa em globo 3D (MapLibre GL), página principal do site.
   Usa os mesmos dados e o mesmo registro de camadas da versão leve em 2D (data/fontes.json). */
"use strict";

const NIVEL = {
  api:       ["n-api", "Oficial · API", "Vem da API do órgão oficial e atualiza sozinho."],
  manual:    ["n-manual", "Oficial · manual", "Arquivo oficial inserido à mão, com data do último download."],
  entidade:  ["n-entidade", "Imprensa / entidade", "Número público de terceiros, sempre com fonte e data."],
  base:      ["n-base", "Base aberta internacional", "Base mundial aberta, real porém menos detalhada."],
  calculado: ["n-calculado", "Estimado / calculado", "Calculado por nós, com o método explicado."],
  pendente:  ["n-pendente", "Em apuração", "Ainda sem dado. O campo fica vazio, sem estimativa."]
};
const RAMP = ["--q1", "--q2", "--q3", "--q4", "--q5"];
const fmt = n => n.toLocaleString("pt-BR");
const fmt1 = n => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
const kmTxt = a => a >= 1e6 ? `${(a / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} milhão de km²` : `${fmt(Math.round(a / 1e3))} mil km²`;
const reais = mil => mil >= 1e6 ? `R$ ${fmt1(mil / 1e6)} bi` : `R$ ${fmt(Math.round(mil / 1e3))} mi`;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
const pill = n => `<span class="pill ${NIVEL[n][0]}">${NIVEL[n][1]}</span>`;
const cor = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
/* caminhos contados a partir deste arquivo (pasta 3d/), não da página: o site pode mudar de endereço ou de domínio */
const AQUI = new URL(".", document.currentScript.src).href;
const D = new URL("../data/", AQUI).href;
const FONTES = new URL("fontes/", AQUI).href;

async function getJSON(p) {
  try { const r = await fetch(p); if (!r.ok) return null; return await r.json(); } catch { return null; }
}
const fc = feats => ({ type: "FeatureCollection", features: feats });
const ponto = (c, props) => ({ type: "Feature", properties: props, geometry: { type: "Point", coordinates: c } });

/* centro aproximado do maior polígono de um país, para o rótulo */
function centroPais(g) {
  const polis = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  let melhor = null, maior = -1;
  for (const p of polis) {
    const r = p[0]; let a = 0, cx = 0, cy = 0;
    for (let i = 0, j = r.length - 1; i < r.length; j = i++) {
      const f = r[j][0] * r[i][1] - r[i][0] * r[j][1]; a += f; cx += (r[j][0] + r[i][0]) * f; cy += (r[j][1] + r[i][1]) * f;
    }
    if (Math.abs(a) > maior) { maior = Math.abs(a); melhor = [cx / (3 * a), cy / (3 * a)]; }
  }
  return melhor;
}
function caixa(g) {
  let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
  const v = c => { if (typeof c[0] === "number") { x0 = Math.min(x0, c[0]); x1 = Math.max(x1, c[0]); y0 = Math.min(y0, c[1]); y1 = Math.max(y1, c[1]); } else c.forEach(v); };
  v(g.coordinates); return [[x0, y0], [x1, y1]];
}
/* faixas por quintil (5 grupos de tamanho igual) */
function quintis(vals) {
  const s = [...vals].sort((a, b) => a - b), q = [0.2, 0.4, 0.6, 0.8].map(p => s[Math.floor(p * (s.length - 1))]);
  return v => q.filter(t => v > t).length;
}

(async function main() {
  const temGL = (() => { try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; } })();
  if (!temGL) { document.getElementById("sem3d").hidden = false; return; }
  const [F, estados, mundo, ROT, REL] = await Promise.all([
    getJSON(D + "fontes.json"), getJSON(D + "geo/estados.json"), getJSON(D + "geo/mundo.json"),
    getJSON(D + "geo/rotulos.json"), getJSON(D + "relevo/relevo.json")]);
  if (!F || !estados) { document.getElementById("ficha").innerHTML = `<p class="note">Não foi possível carregar os dados. Recarregue a página.</p>`; return; }
  const NAME = {}; estados.features.forEach(f => NAME[f.properties.sigla] = f.properties.name);

  const DATA = {};
  await Promise.all([...F.pintura, ...F.camadas].filter(l => l.arquivo).map(async l => {
    DATA[l.id] = await getJSON(D + l.arquivo);
    if (!DATA[l.id] && l.nivel) l.nivel = "pendente";
  }));
  const POP = DATA.pop ? DATA.pop.valores : {};
  const popTot = Object.values(POP).reduce((a, b) => a + b, 0);
  const PAINT = [{ id: "none", nome: "Sem cor" }, ...F.pintura.map(p => ({
    ...p, ok: !!DATA[p.id], nivel: DATA[p.id] ? DATA[p.id].nivel : "pendente",
    val: !DATA[p.id] ? null
      : p.por === "per_capita" ? s => (DATA[p.id].valores[s] && POP[s]) ? DATA[p.id].valores[s].valor / POP[s] * 1e5 : null
      : s => { const v = DATA[p.id].valores[s]; return v == null ? null : (typeof v === "object" ? v.valor : v); },
    fmt: p.por === "per_capita" ? fmt1 : fmt
  }))];
  const LAYERS = F.camadas.map(l => ({ ...l, on: !!l.ligada && l.nivel !== "pendente" }));
  const CLA = F.camadas.find(l => l.id === "cla");
  const LUZ = (F.luzes || []).map(l => ({ ...l }));
  let paint = "pop", sel = null, minF = "todos", modo3d = false, luz = "off", luzPop = null, guardadas = null;

  /* ---------- dados no formato do mapa ---------- */
  const ROTULOS = ["Argentina", "Uruguai", "Paraguai", "Bolívia", "Peru", "Colômbia", "Venezuela", "Chile", "Equador"];
  const paises = fc([
    ...(mundo ? mundo.features.filter(f => ROTULOS.includes(f.properties.NAME_PT)).map(f => ponto(centroPais(f.geometry), { n: f.properties.NAME_PT })) : []),
    ponto([-58.9, 5.7], { n: "Guiana" }), ponto([-55.8, 4.4], { n: "Suriname" }), ponto([-53.1, 4.0], { n: "Guiana\nFrancesa" })]);
  const oceanos = fc([ponto([-26, -30], { n: "Oceano Atlântico" }), ponto([-92, -12], { n: "Oceano Pacífico" })]);
  const ufPts = fc((ROT ? ROT.estados : []).map(e => ponto(e.c, { s: e.s, n: e.n })));
  const capPts = fc((ROT ? ROT.capitais : []).map(c => ponto(c.c, { n: c.n, pais: !!c.pais })));
  const ilhaPts = fc((ROT ? ROT.ilhas : []).map(i => ponto(i.c, { n: i.n, nome: i.nome_completo })));
  const trilhos = fc(DATA.rail ? DATA.rail.trechos.map(t => ({ type: "Feature", properties: { uf: t.uf }, geometry: { type: "LineString", coordinates: t.l } })) : []);
  const portos = fc((DATA.ports || []).map(p => ponto(p.c, { n: p.n, uf: p.uf })));
  const aeros = fc((DATA.air || []).map(a => ponto(a.c, { n: a.n + (a.i ? " (" + a.i + ")" : ""), uf: a.uf })));

  /* ---------- mapa ---------- */
  const fonte = (estilo) => [estilo];
  const SEMI = "Open Sans Semibold", REG = "Open Sans Regular", ITA = "Open Sans Italic";
  const halo = { "text-halo-color": "rgba(6,14,10,.85)", "text-halo-width": 1.6 };
  const AREA = ["==", ["get", "parte"], "area"], LIMITE = ["==", ["get", "parte"], "limite"];
  const map = new maplibregl.Map({
    container: "map",
    attributionControl: { compact: true, customAttribution: "NASA Blue Marble · Terrain Tiles (AWS) · Natural Earth · IBGE · Marine Regions" },
    style: {
      version: 8,
      projection: { type: "globe" },
      glyphs: FONTES + "{fontstack}/{range}.pbf",
      sky: { "sky-color": "#06121c", "horizon-color": "#1d4b5e", "fog-color": "#0b2233", "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0] },
      sources: {
        nasa: { type: "raster", tileSize: 256, maxzoom: 8,
          tiles: ["https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg"] },
        dem: { type: "raster-dem", encoding: "terrarium", tileSize: 256, maxzoom: 13,
          tiles: ["https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"] },
        estados: { type: "geojson", data: estados, promoteId: "sigla" },
        mundo: { type: "geojson", data: mundo || fc([]) },
        zee: { type: "geojson", data: DATA.zee || fc([]) },
        mt: { type: "geojson", data: DATA.mt || fc([]) },
        zc: { type: "geojson", data: DATA.zc || fc([]) },
        pce: { type: "geojson", data: DATA.pce || fc([]) },
        rod: { type: "geojson", data: DATA.rod || fc([]) },
        trilhos: { type: "geojson", data: trilhos },
        portos: { type: "geojson", data: portos },
        aeros: { type: "geojson", data: aeros },
        paises: { type: "geojson", data: paises },
        oceanos: { type: "geojson", data: oceanos },
        uf: { type: "geojson", data: ufPts },
        caps: { type: "geojson", data: capPts },
        ilhas: { type: "geojson", data: ilhaPts }
      },
      layers: [
        { id: "fundo", type: "background", paint: { "background-color": "#0a1d2a" } },
        { id: "nasa", type: "raster", source: "nasa", paint: { "raster-brightness-max": 0.62, "raster-saturation": -0.15, "raster-contrast": 0.08, "raster-fade-duration": 200 } },
        { id: "paises-borda", type: "line", source: "mundo", paint: { "line-color": "rgba(214,198,150,.35)", "line-width": 0.6 } },
        /* mar: cada arquivo traz a área ("area") e as linhas de limite separadas ("limite", "base") */
        { id: "pce-fill-rec", type: "fill", source: "pce", filter: ["all", AREA, ["==", ["get", "status"], "reconhecida"]],
          paint: { "fill-color": "rgba(229,143,211,.17)" } },
        { id: "pce-fill-ana", type: "fill", source: "pce", filter: ["all", AREA, ["==", ["get", "status"], "em_analise"]],
          paint: { "fill-pattern": "hachura" } },
        { id: "zee-fill", type: "fill", source: "zee", filter: AREA, paint: { "fill-color": "rgba(88,207,224,.10)" } },
        { id: "zc-fill", type: "fill", source: "zc", filter: AREA, paint: { "fill-color": "rgba(95,208,168,.16)" } },
        { id: "mt-fill", type: "fill", source: "mt", filter: AREA, paint: { "fill-color": "rgba(159,230,242,.2)" } },
        { id: "estados-fill", type: "fill", source: "estados",
          paint: { "fill-color": cor("--land"),
            "fill-opacity": ["case", ["boolean", ["feature-state", "fade"], false], 0.18, ["boolean", ["feature-state", "hover"], false], 0.95, 0.82] } },
        { id: "zee-line", type: "line", source: "zee", filter: LIMITE, paint: { "line-color": cor("--sea-line"), "line-width": 1.4, "line-dasharray": [3, 2] } },
        { id: "zc-line", type: "line", source: "zc", filter: LIMITE, paint: { "line-color": cor("--zc"), "line-width": 0.8, "line-opacity": 0.7 } },
        { id: "mt-line", type: "line", source: "mt", filter: LIMITE, paint: { "line-color": cor("--mt"), "line-width": 0.8, "line-opacity": 0.7 } },
        { id: "mt-base", type: "line", source: "mt", filter: ["==", ["get", "parte"], "base"],
          layout: { "line-cap": "round" }, paint: { "line-color": cor("--mt"), "line-width": 1.2, "line-opacity": 0.85, "line-dasharray": [0.1, 2.2] } },
        { id: "pce-line-rec", type: "line", source: "pce", filter: ["all", LIMITE, ["==", ["get", "status"], "reconhecida"]],
          paint: { "line-color": cor("--pce"), "line-width": 1.3 } },
        { id: "pce-line-ana", type: "line", source: "pce", filter: ["all", LIMITE, ["==", ["get", "status"], "em_analise"]],
          paint: { "line-color": cor("--pce"), "line-width": 1.2, "line-opacity": 0.85, "line-dasharray": [3, 2] } },
        { id: "estados-line", type: "line", source: "estados", paint: { "line-color": "rgba(220,240,225,.55)", "line-width": 0.8 } },
        { id: "rodovias", type: "line", source: "rod",
          paint: { "line-color": cor("--road"), "line-opacity": ["case", ["==", ["get", "type"], "Major Highway"], 0.6, 0.38],
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["case", ["==", ["get", "type"], "Major Highway"], 0.8, 0.5], 8, ["case", ["==", ["get", "type"], "Major Highway"], 2.2, 1.2]] } },
        { id: "ferrovias", type: "line", source: "trilhos",
          paint: { "line-color": cor("--rail"), "line-opacity": 0.9, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1, 8, 2.6] } },
        { id: "estado-sel", type: "line", source: "estados", filter: ["==", ["get", "sigla"], ""],
          paint: { "line-color": cor("--accent"), "line-width": 2.6 } },
        { id: "pce-rotulo", type: "symbol", source: "pce", filter: ["==", ["get", "parte"], "rotulo"],
          layout: { "text-field": ["get", "texto"], "text-font": fonte(SEMI), "text-size": 10, "text-letter-spacing": 0.12, "text-transform": "uppercase", "text-max-width": 14 },
          paint: { "text-color": "rgba(244,196,235,.9)", ...halo } },
        { id: "zee-rotulo", type: "symbol", source: "zee", filter: LIMITE,
          layout: { "symbol-placement": "line", "symbol-spacing": 900, "text-field": "ZONA ECONÔMICA EXCLUSIVA · 200 MILHAS", "text-font": fonte(SEMI), "text-size": 10, "text-letter-spacing": 0.2, "text-max-angle": 30 },
          paint: { "text-color": "rgba(159,230,242,.75)", ...halo } },
        { id: "portos", type: "circle", source: "portos",
          paint: { "circle-color": cor("--port"), "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 3, 8, 6], "circle-stroke-color": "#05101a", "circle-stroke-width": 1 } },
        { id: "aeroportos", type: "circle", source: "aeros",
          paint: { "circle-color": cor("--air"), "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 3, 8, 6], "circle-stroke-color": "#05101a", "circle-stroke-width": 1 } },
        { id: "ilhas-ponto", type: "circle", source: "ilhas", paint: { "circle-color": cor("--sea-line"), "circle-radius": 2.6, "circle-stroke-color": "#05101a", "circle-stroke-width": 1 } },
        { id: "ilhas-rotulo", type: "symbol", source: "ilhas", filter: ["!=", ["get", "n"], ""],
          layout: { "text-field": ["get", "n"], "text-font": fonte(REG), "text-size": 11, "text-anchor": "left", "text-offset": [0.7, 0] },
          paint: { "text-color": "#cdeff5", ...halo } },
        { id: "oceanos", type: "symbol", source: "oceanos",
          layout: { "text-field": ["get", "n"], "text-font": fonte(ITA), "text-size": 13, "text-letter-spacing": 0.45, "text-transform": "uppercase" },
          paint: { "text-color": "rgba(159,230,242,.45)" } },
        { id: "paises", type: "symbol", source: "paises",
          layout: { "text-field": ["get", "n"], "text-font": fonte(SEMI), "text-size": 10, "text-letter-spacing": 0.2, "text-transform": "uppercase" },
          paint: { "text-color": "rgba(236,233,222,.6)", ...halo } },
        { id: "capitais", type: "circle", source: "caps",
          paint: { "circle-color": ["case", ["get", "pais"], cor("--accent"), "#ffffff"], "circle-radius": ["case", ["get", "pais"], 4, 3], "circle-stroke-color": "#081408", "circle-stroke-width": 1.2 } },
        { id: "capitais-rotulo", type: "symbol", source: "caps",
          layout: { "text-field": ["step", ["zoom"], ["case", ["get", "pais"], ["get", "n"], ""], 4.6, ["get", "n"]], "text-font": fonte(SEMI), "text-size": 12, "text-anchor": "left", "text-offset": [0.6, 0], "text-optional": true },
          paint: { "text-color": "#ffffff", ...halo } },
        { id: "uf-rotulo", type: "symbol", source: "uf",
          layout: { "text-field": ["step", ["zoom"], ["get", "s"], 5.6, ["get", "n"]], "text-font": fonte(SEMI),
            "text-size": ["step", ["zoom"], 11, 5.6, 13], "text-letter-spacing": ["step", ["zoom"], 0.1, 5.6, 0.02], "text-allow-overlap": false },
          paint: { "text-color": "#f4f1e6", ...halo } }
      ]
    },
    center: [-50, -14], zoom: 2.6, maxPitch: 75,
    pixelRatio: Math.min(devicePixelRatio || 1, innerWidth < 900 ? 1.5 : 2)
  });
  /* hachura (listras diagonais) da plataforma continental ainda em análise na ONU */
  map.on("styleimagemissing", e => {
    if (e.id !== "hachura" || map.hasImage("hachura")) return;
    const n = 16, c = document.createElement("canvas"); c.width = c.height = n;
    const x = c.getContext("2d");
    x.strokeStyle = cor("--pce"); x.globalAlpha = 0.6; x.lineWidth = 2.2;
    x.beginPath(); x.moveTo(0, n); x.lineTo(n, 0); x.moveTo(-n / 2, n / 2); x.lineTo(n / 2, -n / 2); x.moveTo(n / 2, n * 1.5); x.lineTo(n * 1.5, n / 2); x.stroke();
    map.addImage("hachura", x.getImageData(0, 0, n, n), { pixelRatio: 2 });
  });
  let falhouNasa = false;
  map.on("error", e => {
    /* se a imagem da NASA não carregar, usa o relevo próprio do Natural Earth (já está no site) */
    if (!falhouNasa && e.sourceId === "nasa" && REL && map.getLayer("nasa")) {
      falhouNasa = true;
      for (const k of ["mundo", "cor"]) {
        const r = REL[k]; if (!r) continue;
        map.addSource("rel-" + k, { type: "image", url: D + "relevo/" + r.arquivo, coordinates: [[r.oeste, r.norte], [r.leste, r.norte], [r.leste, r.sul], [r.oeste, r.sul]] });
        map.addLayer({ id: "rel-" + k, type: "raster", source: "rel-" + k, paint: { "raster-brightness-max": 0.55, "raster-saturation": -0.1, "raster-fade-duration": 0 } }, "paises-borda");
      }
      map.setLayoutProperty("nasa", "visibility", "none");
    }
  });

  /* Alcântara: marcador HTML que pisca */
  let mkCla = null;
  if (CLA) {
    const el = document.createElement("div"); el.className = "mk-cla"; el.title = CLA.nome;
    el.innerHTML = '<i class="p"></i><i></i><b></b>';
    mkCla = new maplibregl.Marker({ element: el }).setLngLat(CLA.ponto);
  }

  const G = { zee: ["zee-fill", "zee-line", "zee-rotulo", "ilhas-ponto", "ilhas-rotulo"], mt: ["mt-fill", "mt-line", "mt-base"], zc: ["zc-fill", "zc-line"],
    pce: ["pce-fill-rec", "pce-fill-ana", "pce-line-rec", "pce-line-ana", "pce-rotulo"], rod: ["rodovias"],
    rail: ["ferrovias"], ports: ["portos"], air: ["aeroportos"] };

  /* ---------- painel e enquadramento ---------- */
  const stage = document.getElementById("stage");
  const dock = document.querySelector(".dock"), unfold = document.getElementById("unfold");
  const largo = () => innerWidth > 900;
  const espacoPainel = () => largo() && !dock.hidden ? dock.offsetWidth + 40 : 0;
  const topo = () => largo() ? document.getElementById("top").offsetHeight : 0;
  const folga = () => largo() ? { top: topo() + 40, bottom: 40, left: 10, right: espacoPainel() + 110 } : { top: 20, bottom: 20, left: 12, right: 12 };
  function ajustarCabecalho() { stage.style.setProperty("--head", (topo() + 4) + "px"); stage.style.setProperty("--dock-w", espacoPainel() + "px"); }
  const BRASIL = caixa({ coordinates: estados.features.map(f => f.geometry.coordinates) });
  function verBrasil(dur = 1400) {
    map.fitBounds(BRASIL, { padding: folga(), pitch: modo3d ? 45 : 0, bearing: 0, duration: reduce ? 0 : dur });
  }
  function verEstado(s, dur = 1400) {
    const f = estados.features.find(x => x.properties.sigla === s);
    map.fitBounds(caixa(f.geometry), { padding: folga(), pitch: modo3d ? 55 : 0, bearing: 0, maxZoom: 8, duration: reduce ? 0 : dur });
  }
  const fold = document.getElementById("fold");
  function alinharBotoes() {
    /* "Mostrar painel" ocupa o mesmo lugar do "Recolher": dá para clicar duas vezes sem mover o mouse */
    if (dock.hidden) return;
    const r = fold.getBoundingClientRect(), s = stage.getBoundingClientRect();
    unfold.style.top = (r.top - s.top) + "px";
    unfold.style.right = (s.right - r.right) + "px";
    unfold.style.minWidth = r.width + "px"; unfold.style.height = r.height + "px";
  }
  function mostrarPainel(abrir) {
    if (!abrir) alinharBotoes();
    dock.hidden = !abrir; unfold.hidden = abrir;
    try { localStorage.setItem("bec-painel", abrir ? "aberto" : "recolhido"); } catch (e) {}
    ajustarCabecalho(); sel ? verEstado(sel, 600) : verBrasil(600);
  }
  document.getElementById("fold").onclick = () => mostrarPainel(false);
  unfold.onclick = () => mostrarPainel(true);
  try { if (largo() && localStorage.getItem("bec-painel") === "recolhido") { alinharBotoes(); dock.hidden = true; unfold.hidden = false; } } catch (e) {}
  /* tamanho das letras do painel (A− / A+), lembrado entre visitas */
  const ESC = [0.85, 1, 1.12, 1.25, 1.4], conteudo = document.getElementById("conteudo");
  let ie = 1; try { const v = +localStorage.getItem("bec-letra"); if (ESC.includes(v)) ie = ESC.indexOf(v); } catch (e) {}
  function letra(d) {
    ie = Math.max(0, Math.min(ESC.length - 1, ie + d));
    conteudo.style.zoom = ESC[ie];
    document.getElementById("menos").disabled = ie === 0; document.getElementById("mais").disabled = ie === ESC.length - 1;
    try { localStorage.setItem("bec-letra", ESC[ie]); } catch (e) {}
  }
  document.getElementById("menos").onclick = () => letra(-1);
  document.getElementById("mais").onclick = () => letra(1);
  letra(0);

  function selecionar(s) {
    if (sel) { map.setFeatureState({ source: "estados", id: sel }, { sel: false }); }
    sel = (sel === s) ? null : s;
    estados.features.forEach(f => map.setFeatureState({ source: "estados", id: f.properties.sigla }, { fade: !!sel && f.properties.sigla !== sel }));
    map.setFilter("estado-sel", ["==", ["get", "sigla"], sel || ""]);
    linhasTrem();
    sel ? verEstado(sel) : verBrasil(1000);
    render(); ficha();
  }
  document.getElementById("back").onclick = () => { if (sel) selecionar(sel); };
  document.getElementById("center").onclick = () => sel ? verEstado(sel, 900) : verBrasil(900);
  const b3d = document.getElementById("modo3d");
  b3d.onclick = () => {
    modo3d = !modo3d; b3d.setAttribute("aria-pressed", modo3d);
    map.setTerrain(modo3d ? { source: "dem", exaggeration: 1.6 } : null);
    map.easeTo({ pitch: modo3d ? (sel ? 55 : 45) : 0, duration: reduce ? 0 : 1200 });
  };

  /* passar o mouse e clicar nos estados */
  let hover = null;
  map.on("mousemove", "estados-fill", e => {
    map.getCanvas().style.cursor = "pointer";
    const s = e.features[0].properties.sigla;
    if (hover !== s) { if (hover) map.setFeatureState({ source: "estados", id: hover }, { hover: false }); hover = s; map.setFeatureState({ source: "estados", id: s }, { hover: true }); }
  });
  map.on("mouseleave", "estados-fill", () => { map.getCanvas().style.cursor = ""; if (hover) map.setFeatureState({ source: "estados", id: hover }, { hover: false }); hover = null; });
  map.on("click", e => {
    if (luz === "pop" && map.getLayer("luz-pop-ponto") && map.getZoom() >= 5) {
      const { x, y } = e.point, m = map.queryRenderedFeatures([[x - 5, y - 5], [x + 5, y + 5]], { layers: ["luz-pop-ponto"] });
      if (m.length) {
        const f = m.reduce((a, b) => b.properties.p > a.properties.p ? b : a);
        new maplibregl.Popup({ closeButton: false, offset: 8 }).setLngLat(f.geometry.coordinates)
          .setHTML(`<b>${f.properties.n} · ${f.properties.u}</b><br>${fmt(f.properties.p)} habitantes<br><span class="pop-fonte">IBGE, Censo 2022</span>`).addTo(map);
        return;
      }
    }
    const pts = map.queryRenderedFeatures(e.point, { layers: ["portos", "aeroportos", "capitais"].filter(l => map.getLayoutProperty(l, "visibility") !== "none") });
    if (pts.length) {
      const f = pts[0], tipo = f.layer.id === "portos" ? "Porto" : f.layer.id === "aeroportos" ? "Aeroporto" : "Capital";
      new maplibregl.Popup({ closeButton: false, offset: 10 }).setLngLat(f.geometry.coordinates).setHTML(`<b>${tipo}</b><br>${f.properties.n}`).addTo(map);
      return;
    }
    const pc = map.queryRenderedFeatures(e.point, { layers: ["pce-fill-rec", "pce-fill-ana"].filter(l => map.getLayoutProperty(l, "visibility") !== "none") });
    if (pc.length) {
      const p = pc[0].properties;
      /* perto do painel, o quadro abre para a esquerda, para não ficar escondido atrás dele */
      const perto = e.point.x > map.getCanvas().clientWidth - espacoPainel() - 320;
      new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "290px", ...(perto ? { anchor: "right" } : {}) }).setLngLat(e.lngLat)
        .setHTML(`<b>Plataforma continental estendida</b><br>${p.nome}: ${p.situacao}.<br>Área no desenho: ≈ ${kmTxt(p.area_km2)} · Marinha: ${p.area_marinha}
          <br><span class="pop-fonte">${p.fonte_curta}. Desenho para consulta, sem valor legal.</span>`).addTo(map);
      return;
    }
    const st = map.queryRenderedFeatures(e.point, { layers: ["estados-fill"] });
    if (st.length) selecionar(st[0].properties.sigla);
    else if (sel) selecionar(sel);
  });

  /* ---------- ícones, filtro por ministério, camadas ---------- */
  const ICON = {
    zee: "M2 8c3-3 5 3 8 0s5 3 8 0M2 13c3-3 5 3 8 0s5 3 8 0M2 18c3-3 5 3 8 0s5 3 8 0",
    mt: "M3 3v18M7 9c2-2 4 2 6 0s4 2 6 0M7 15c2-2 4 2 6 0s4 2 6 0",
    zc: "M2 8c3-3 5 3 8 0s5 3 8 0M2 15h3M8 15h3M14 15h3M20 15h2",
    pce: "M2 6h7l3 7 3 3h7M2 20h20",
    cla: "M12 2c3 3 4 7 3 12h-6C8 9 9 5 12 2zM9 14l-3 4h3M15 14l3 4h-3M11 18h2v3h-2z",
    rail: "M7 3h10v12H7zM7 9h10M9 15l-3 6M15 15l3 6M7 19h10",
    ports: "M12 3v12M8 7h8M4 13c0 4 4 7 8 7s8-3 8-7M4 13h3M17 13h3",
    air: "M2 13l9-2V4c0-1 2-1 2 0v7l9 2v2l-9-1v5l3 2v1l-4-1-4 1v-1l3-2v-5l-9 1z",
    "p-oil": "M6 21L12 3l6 18M8 15h8M9 10h6M4 21h16",
    "p-def": "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z",
    "p-cel": "M12 10v11M8 21h8M9 7a4 4 0 016 0M6 4a8 8 0 0112 0",
    "p-pec": "M4 10h14l2 3v4h-2M4 10v7h2M8 17h8M4 10l-1-3M16 10l1-3",
    "p-rod": "M8 21L10 3M16 21L14 3M12 6v2M12 11v2M12 16v2",
    "p-ene": "M13 2L5 14h6l-1 8 8-12h-6z"
  };
  const icon = id => ICON[id] ? `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICON[id]}"/></svg>` : `<span class="ico"></span>`;
  const mins = document.getElementById("mins");
  mins.insertAdjacentHTML("beforeend", [["todos", "Todos"], ...Object.entries(F.ministerios)]
    .map(([k, v]) => `<button class="tab" data-m="${k}" aria-pressed="${k === "todos"}">${v}</button>`).join(""));
  mins.querySelectorAll(".tab").forEach(b => b.onclick = () => {
    minF = b.dataset.m; guardadas = null;
    mins.querySelectorAll(".tab").forEach(x => x.setAttribute("aria-pressed", x === b));
    LAYERS.forEach(l => { if (l.nivel !== "pendente") l.on = minF === "todos" ? !!l.ligada : l.ministerio === minF; });
    const p = PAINT.find(p => p.ministerio === minF && p.ok);
    paint = minF === "todos" ? "pop" : (p ? p.id : "none");
    const lz = LUZ.find(l => l.id === luz);
    if (lz && minF !== "todos" && lz.ministerio !== minF) definirLuz("off"); else render();
  });
  function controls() {
    const pv = PAINT.filter(p => p.id === "none" || minF === "todos" || p.ministerio === minF);
    document.getElementById("paint").innerHTML = pv.map(p =>
      `<button class="chip" data-p="${p.id}" aria-pressed="${paint === p.id}" ${p.id !== "none" && !p.ok ? "disabled title=\"Em apuração\"" : ""}>${p.nome}</button>`).join("");
    document.querySelectorAll("#paint .chip:not([disabled])").forEach(b => b.onclick = () => {
      paint = b.dataset.p;
      if (luz !== "off" && paint !== "none") definirLuz("off"); else render();
    });
    document.getElementById("paint").classList.toggle("apagado", luz !== "off");
    /* luzes à noite: uma de cada vez, para não misturar as duas imagens */
    const zv = LUZ.filter(l => minF === "todos" || l.ministerio === minF);
    document.getElementById("luzes").innerHTML = [{ id: "off", nome: "Desligadas" }, ...zv].map(l =>
      `<button class="chip" data-l="${l.id}" aria-pressed="${luz === l.id}" ${l.falhou ? "disabled title=\"Não foi possível carregar\"" : ""}>${l.nome}</button>`).join("");
    document.querySelectorAll("#luzes .chip:not([disabled])").forEach(b => b.onclick = () => definirLuz(b.dataset.l));
    const L = LUZ.find(l => l.id === luz), info = document.getElementById("luz-info");
    if (!L) info.innerHTML = "";
    else {
      const dd = L.id === "pop" ? luzPop : null;
      info.innerHTML = `<div class="luz-info"><p class="note"><b>${L.titulo}.</b> ${L.explica}</p>
        <div>${dd ? `${pill(dd.nivel)} <span class="note">${dd.fonte} · atualizado em ${dd.atualizado_em}. Posição: ${dd.posicao}.</span>`
             : `${pill(L.nivel)} <span class="note">${L.fonte}.</span>`}</div>
        <p class="note">Com as luzes acesas, os estados ficam sem cor e as rodovias e ferrovias se apagam, para não se confundirem com as luzes (dá para religar em Camadas). Escolha uma pintura acima para voltar às cores.</p></div>`;
    }
    const lv = LAYERS.filter(l => minF === "todos" || l.ministerio === minF);
    document.getElementById("layers").innerHTML = lv.length ? lv.map(l => `
      <label class="layer ${l.nivel === "pendente" ? "pend" : ""}">
        <input type="checkbox" id="ly-${l.id}" ${l.on ? "checked" : ""} ${l.nivel === "pendente" ? "disabled" : ""}>${icon(l.id)}
        <span><span class="nm">${l.cor ? `<i class="key" style="background:var(${l.cor})"></i>` : ""}${l.nome} ${pill(l.nivel)}</span>
        <span class="src">${l.fonte} · ${F.ministerios[l.ministerio]}</span></span>
      </label>`).join("") : `<p class="note">Este ministério ainda não tem camadas de mapa.</p>`;
    lv.filter(l => l.nivel !== "pendente").forEach(l => document.getElementById("ly-" + l.id).onchange = e => { l.on = e.target.checked; render(); });
  }

  /* ---------- desenho ---------- */
  function render() {
    controls();
    if (map.getLayer("estados-fill")) {
      LAYERS.forEach(l => (G[l.id] || []).forEach(id => map.getLayer(id) && map.setLayoutProperty(id, "visibility", l.on ? "visible" : "none")));
      const lc = LAYERS.find(l => l.id === "cla");
      if (mkCla) { if (lc && lc.on) mkCla.addTo(map); else mkCla.remove(); }
    }
    const P = PAINT.find(p => p.id === paint);
    let leg = "";
    const L = LUZ.find(l => l.id === luz);
    if (L) {
      if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color", ["case", ["boolean", ["feature-state", "hover"], false], "#ffffff", "#01050a"]);
      const cores = L.id === "pop" ? COR_POP_LEG : COR_NOITE_LEG;
      leg = `<span>${L.titulo}</span><span>${L.id === "pop" ? "menos gente" : "escuro"}</span>
        <span class="ramp">${cores.map(c => `<i style="background:${c}"></i>`).join("")}</span><span>${L.id === "pop" ? "mais gente" : "mais luz"}</span>`;
    } else if (P && P.val) {
      const vals = Object.keys(NAME).map(P.val).filter(v => v != null);
      const q = quintis(vals), cores = RAMP.map(cor);
      const m = ["match", ["get", "sigla"]];
      Object.keys(NAME).forEach(s => { const v = P.val(s); m.push(s, v == null ? cor("--land") : cores[q(v)]); });
      m.push(cor("--land"));
      if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color", m);
      const DD = DATA[P.id];
      leg = `<span>${P.nome}${DD.unidade ? " (" + DD.unidade + ")" : ""}</span><span>${P.fmt(Math.min(...vals))}</span>
        <span class="ramp">${RAMP.map(c => `<i style="background:var(${c})"></i>`).join("")}</span><span>${P.fmt(Math.max(...vals))}</span>
        ${vals.length < 27 ? "<span>sem cor = sem dado</span>" : ""}`;
    } else if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color", cor("--land"));
    leg += LAYERS.filter(l => l.on && l.cor).map(l => (l.legenda || [{ nome: l.nome }]).map(k =>
      `<span><i class="key${k.hachura ? " hach" : ""}" style="${k.hachura ? "color" : "background"}:var(${k.cor || l.cor})"></i>${k.nome}</span>`).join("")).join("");
    document.getElementById("legend").innerHTML = leg;
    document.getElementById("back").hidden = !sel;
    document.getElementById("where").textContent = sel ? `${NAME[sel]} · ${sel}` : "Brasil · 27 UFs";
  }

  /* ---------- luzes à noite ---------- */
  const FADE = ["boolean", ["feature-state", "fade"], false], HOVER = ["boolean", ["feature-state", "hover"], false];
  const COR_POP_LEG = ["#6e370a", "#d77d23", "#ffbe50", "#ffe8aa", "#fffceb"];
  const COR_NOITE_LEG = ["#0a0c1c", "#2c2a44", "#a8823f", "#f2d083", "#fffbe8"];
  function linhasTrem() {
    const n = luz !== "off";
    map.setPaintProperty("ferrovias", "line-opacity", sel ? ["case", ["==", ["get", "uf"], sel], n ? 0.6 : 1, n ? 0.06 : 0.15] : (n ? 0.35 : 0.9));
  }
  function aplicarNoite() {
    if (!map.getLayer("estados-fill")) return;
    const n = luz !== "off";
    map.setPaintProperty("nasa", "raster-brightness-max", n ? 0.2 : 0.62);
    map.setPaintProperty("nasa", "raster-saturation", n ? -0.55 : -0.15);
    for (const id of ["rel-mundo", "rel-cor"]) if (map.getLayer(id)) map.setPaintProperty(id, "raster-brightness-max", n ? 0.2 : 0.55);
    if (map.getLayer("relevo")) map.setLayoutProperty("relevo", "visibility", n ? "none" : "visible");
    map.setPaintProperty("estados-fill", "fill-opacity", n ? ["case", FADE, 0.6, HOVER, 0.07, 0] : ["case", FADE, 0.18, HOVER, 0.95, 0.82]);
    map.setPaintProperty("estados-line", "line-opacity", n ? 0.55 : 1);
    map.setPaintProperty("rodovias", "line-opacity", ["*", n ? 0.35 : 1, ["case", ["==", ["get", "type"], "Major Highway"], 0.6, 0.38]]);
    linhasTrem();
  }
  function prepararLuzes() {
    if (luz === "noite" && !map.getSource("luz-noite")) {
      map.addSource("luz-noite", { type: "raster", tileSize: 256, maxzoom: 8, tiles: [LUZ.find(l => l.id === "noite").ladrilhos], attribution: "NASA Black Marble" });
      map.addLayer({ id: "luz-noite", type: "raster", source: "luz-noite", paint: { "raster-fade-duration": 300 } }, "paises-borda");
    }
    if (luz === "pop" && !map.getSource("luz-pop")) {
      map.addSource("luz-pop", { type: "geojson", data: fc(luzPop.municipios.map(m => ponto([m[0], m[1]], { p: m[2], n: m[3], u: m[4] }))) });
      /* brilho espalhado: soma os municípios vizinhos (escala em logaritmo, para as cidades pequenas também aparecerem) */
      map.addLayer({ id: "luz-pop-calor", type: "heatmap", source: "luz-pop", paint: {
        "heatmap-weight": ["interpolate", ["linear"], ["ln", ["+", ["get", "p"], 1]], 7.6, 0, 9.9, 0.12, 12.2, 0.45, 14.5, 0.85, 16.3, 1],
        "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 3, 1.4, 5, 1.5, 8, 2.6],
        "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 3, 6, 5, 11, 8, 28],
        "heatmap-color": ["interpolate", ["linear"], ["heatmap-density"], 0, "rgba(0,0,0,0)", 0.08, "rgba(110,55,10,0.35)",
          0.25, "rgba(215,125,35,0.7)", 0.5, "rgba(255,190,80,0.9)", 0.8, "rgba(255,232,170,1)", 1, "rgba(255,252,235,1)"],
        "heatmap-opacity": 0.95 } }, "paises-borda");
      /* um ponto de luz por município, do tamanho da população (raiz quadrada: área do ponto proporcional às pessoas) */
      const RAIO = ["interpolate", ["linear"], ["sqrt", ["get", "p"]], 0, 0.6, 100, 1.1, 300, 1.8, 1000, 3.4, 3500, 6.5];
      map.addLayer({ id: "luz-pop-ponto", type: "circle", source: "luz-pop", paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, ["*", 0.6, RAIO], 5, ["*", 0.9, RAIO], 8, ["*", 1.6, RAIO]],
        "circle-color": "#ffe4a8", "circle-blur": 0.6, "circle-opacity": 0.9 } }, "paises-borda");
    }
    const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    vis("luz-noite", luz === "noite"); vis("luz-pop-calor", luz === "pop"); vis("luz-pop-ponto", luz === "pop");
  }
  async function definirLuz(id) {
    const L = LUZ.find(l => l.id === id);
    if (L && L.id === "pop" && !luzPop) {
      document.getElementById("luz-info").innerHTML = `<p class="note">Carregando os 5.570 municípios…</p>`;
      luzPop = await getJSON(D + L.arquivo);
      if (!luzPop) { L.falhou = true; luz = "off"; render(); return; }
    }
    const antes = luz;
    luz = L ? id : "off";
    /* rodovias e ferrovias se apagam com as luzes (parecem estradas iluminadas) e voltam como estavam depois */
    const linhas = LAYERS.filter(l => (l.id === "rod" || l.id === "rail") && l.nivel !== "pendente");
    if (antes === "off" && luz !== "off") { guardadas = {}; linhas.forEach(l => { guardadas[l.id] = l.on; l.on = false; }); }
    if (antes !== "off" && luz === "off" && guardadas) { linhas.forEach(l => { if (l.id in guardadas) l.on = guardadas[l.id]; }); guardadas = null; }
    if (map.getLayer("estados-fill")) { prepararLuzes(); aplicarNoite(); }
    render();
  }

  function ficha() {
    const el = document.getElementById("ficha");
    const popInfo = DATA.pop ? `${pill(DATA.pop.nivel)} <span class="note">${DATA.pop.fonte} · atualizado em ${DATA.pop.atualizado_em}</span>` : pill("pendente");
    if (!sel) {
      el.innerHTML = `<h2>Visão nacional</h2><div class="fname">Brasil</div>
        <div class="kv"><span>População</span><span class="v">${fmt(popTot)}</span></div>${popInfo}
        <p class="lede">Clique num estado para aproximar. Arraste para girar o globo, role para aproximar e use o botão "Relevo 3D" para ver as montanhas em altura.</p>`;
      return;
    }
    const s = sel;
    const rk = Object.entries(POP).sort((a, b) => b[1] - a[1]).findIndex(e => e[0] === s) + 1;
    const Pt = (DATA.ports || []).filter(p => p.uf === s), A = (DATA.air || []).filter(a => a.uf === s);
    const km = DATA.rail ? DATA.rail.km_por_uf[s] || 0 : 0;
    const ev = DATA.evpc && DATA.evpc.valores[s];
    const ag = DATA.agro && DATA.agro.valores[s];
    el.innerHTML = `
      <h2>${s} · ficha do estado</h2><div class="fname">${NAME[s]}</div>
      <div class="sec"><h3>População</h3>
        <div class="kv"><span>Habitantes</span><span class="v">${POP[s] ? fmt(POP[s]) : "—"}</span></div>
        <div class="kv"><span>Posição no país</span><span class="v">${rk}º · ${fmt1(POP[s] / popTot * 100)}%</span></div>${popInfo}</div>
      <div class="sec"><h3>Agricultura</h3>
        ${ag != null ? `<div class="kv"><span>${DATA.agro.titulo}</span><span class="v">${reais(ag)}</span></div>
          ${pill(DATA.agro.nivel)} <span class="note">${DATA.agro.fonte}, ref. ${DATA.agro.referencia} · atualizado em ${DATA.agro.atualizado_em}</span>`
        : `${pill("pendente")} <span class="note">O robô de atualização ainda não rodou.</span>`}</div>
      <div class="sec"><h3>Logística</h3>
        <div class="kv"><span>Ferrovias no mapa</span><span class="v">${km ? "≈ " + fmt(km) + " km" : "nenhuma na base"}</span></div>
        <div class="kv"><span>Portos na base</span><span class="v">${Pt.length}</span></div>
        ${Pt.length ? `<div class="list">${Pt.map(p => p.n).join(", ")}</div>` : ""}
        <div class="kv"><span>Aeroportos na base</span><span class="v">${A.length}</span></div>
        ${A.length ? `<div class="list">${A.map(a => a.n + (a.i ? " (" + a.i + ")" : "")).join(", ")}</div>` : ""}
        ${pill("base")} <span class="note">Ausência na base não significa ausência real.</span></div>
      ${CLA && s === CLA.uf ? `<div class="sec"><h3>Defesa</h3><div class="list">${CLA.nome}, base de lançamento de foguetes da Força Aérea.</div>${pill("calculado")} <span class="note">posição aproximada</span></div>` : ""}
      <div class="sec"><h3>Mobilidade elétrica</h3>
        <div class="kv"><span>Eletropostos</span><span class="v">${ev ? fmt(ev.valor) : "—"}</span></div>
        ${ev ? `${pill("entidade")} <span class="note">${ev.fonte}, ref. ${ev.referencia}</span>` : `${pill("pendente")} <span class="note">Nenhum número publicado encontrado.</span>`}</div>`;
  }

  const AP = F.apoio, apoio = document.getElementById("apoio");
  if (AP && AP.link) {
    apoio.innerHTML = `<a class="apoiar" href="${AP.link}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.6-7 10-7 10z"/></svg>${AP.texto}</a>
      ${AP.nota ? `<span class="note">${AP.nota}</span>` : ""}`;
    apoio.hidden = false;
  }
  document.getElementById("tiers").innerHTML = Object.values(NIVEL)
    .map(([c, t, d]) => `<div><span><span class="pill ${c}">${t}</span></span><span>${d}</span></div>`).join("");

  /* ---------- abertura ---------- */
  ajustarCabecalho(); controls(); ficha();
  verBrasil(0);
  /* aplica cores e camadas ligadas assim que o estilo é lido, antes das imagens chegarem */
  map.once("style.load", () => render());
  const aviso = document.getElementById("carregando");
  map.on("load", () => {
    render();
    window.MAPA_PRONTO = true;
  });
  map.once("idle", () => {
    aviso.classList.add("fim"); setTimeout(() => aviso.remove(), 700);
    /* o relevo sombreado chega depois da primeira imagem, em ladrilhos maiores (menos pedidos) */
    map.addSource("demh", { type: "raster-dem", encoding: "terrarium", tileSize: 512, maxzoom: 10,
      tiles: ["https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"] });
    map.addLayer({ id: "relevo", type: "hillshade", source: "demh",
      paint: { "hillshade-exaggeration": 0.5, "hillshade-shadow-color": "#04100a", "hillshade-highlight-color": "rgba(255,255,240,.55)", "hillshade-accent-color": "#0c2a18" } }, "zee-line");
    if (luz !== "off") map.setLayoutProperty("relevo", "visibility", "none");
  });
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { ajustarCabecalho(); map.resize(); if (!dock.hidden) alinharBotoes(); }, 150); });
  window.__mapa = map;
})();
