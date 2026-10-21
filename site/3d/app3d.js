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
/* texto vindo de bases externas entra no HTML sempre escapado */
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
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
  /* camadas "sob_demanda" (arquivos grandes que começam desligados) só são baixadas quando alguém liga a camada */
  await Promise.all([...F.pintura, ...F.camadas].filter(l => l.arquivo && !l.sob_demanda).map(async l => {
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
    fmt: p.por === "per_capita" || p.por === "percentual" ? fmt1 : fmt
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
  const trilhos = fc(DATA.rail ? DATA.rail.trechos.map(t => ({ type: "Feature", properties: { uf: t.uf, op: t.op, obra: t.obra || 0, b: t.b || "" }, geometry: { type: "LineString", coordinates: t.l } })) : []);
  const portos = fc((DATA.ports || []).map(p => ponto(p.c, { n: p.n, uf: p.uf, org: p.org || 0, obra: p.obra || 0 })));
  const aeros = fc((DATA.air || []).map(a => ponto(a.c, { n: a.n + (a.i ? " (" + a.i + ")" : ""), uf: a.uf })));
  /* poços em produção: [lon, lat, boe/dia, barris de petróleo/dia, mil m³ de gás/dia, poço, campo, UF, mar/terra] */
  const pocosFC = d => fc(d.pocos.map(p => ponto([p[0], p[1]], { b: p[2], o: p[3], g: p[4], n: p[5], c: p[6], u: p[7], a: p[8] })));

  /* ---------- mapa ---------- */
  const fonte = (estilo) => [estilo];
  const SEMI = "Open Sans Semibold", REG = "Open Sans Regular", ITA = "Open Sans Italic";
  const halo = { "text-halo-color": "rgba(6,14,10,.85)", "text-halo-width": 1.6 };
  const AREA = ["==", ["get", "parte"], "area"], LIMITE = ["==", ["get", "parte"], "limite"];
  const map = new maplibregl.Map({
    container: "map",
    locale: { "AttributionControl.ToggleAttribution": "Mostrar ou ocultar os créditos do mapa" },
    attributionControl: { compact: true, customAttribution: "NASA Blue Marble · Terrain Tiles (AWS) · Natural Earth · IBGE · Marine Regions · ANP · EPE · Anatel" },
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
        pocos: { type: "geojson", data: fc([]) },
        boi: { type: "geojson", data: fc([]) },
        usinas: { type: "geojson", data: fc([]) },
        lt: { type: "geojson", data: fc([]) },
        celm: { type: "geojson", data: fc([]) },
        g5: { type: "geojson", data: fc([]) },
        uep: { type: "geojson", data: DATA.uep || fc([]) },
        campos: { type: "geojson", data: DATA.campos || fc([]) },
        presal: { type: "geojson", data: DATA.presal || fc([]) },
        rod: { type: "geojson", data: DATA.rod || fc([]) },
        rodest: { type: "geojson", data: fc([]) },
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
        { id: "campos-fill", type: "fill", source: "campos", paint: { "fill-color": "rgba(217,144,43,.2)" } },
        { id: "campos-line", type: "line", source: "campos", paint: { "line-color": cor("--campo"), "line-width": 0.8, "line-opacity": 0.85 } },
        { id: "presal-line", type: "line", source: "presal", filter: AREA,
          paint: { "line-color": cor("--presal"), "line-width": 1.5, "line-opacity": 0.9, "line-dasharray": [3, 2] } },
        /* rodovias (IBGE, BC250): estaduais pavimentadas por baixo; federais pavimentadas em traço cheio,
           federais sem pavimento tracejadas */
        { id: "rodovias-est", type: "line", source: "rodest", layout: { "line-cap": "round" },
          paint: { "line-color": cor("--road-est"), "line-opacity": 0.5, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.4, 8, 1.3] } },
        { id: "rodovias-terra", type: "line", source: "rod", filter: ["==", ["get", "p"], 0],
          paint: { "line-color": cor("--road"), "line-opacity": 0.5, "line-dasharray": [2, 2], "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 8, 1.4] } },
        { id: "rodovias", type: "line", source: "rod", filter: ["==", ["get", "p"], 1], layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": cor("--road"), "line-opacity": 0.62,
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.8, 8, 2] } },
        { id: "ferrovias", type: "line", source: "trilhos", filter: ["!=", ["get", "obra"], 1],
          paint: { "line-color": cor("--rail"), "line-opacity": 0.9, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1, 8, 2.6] } },
        { id: "ferrovias-obra", type: "line", source: "trilhos", filter: ["==", ["get", "obra"], 1],
          paint: { "line-color": cor("--rail"), "line-opacity": 0.9, "line-dasharray": [2, 1.5], "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1, 8, 2.4] } },
        /* linhas de transmissão (EPE): mais grossas quanto maior a tensão (230 a 800 kV) */
        { id: "lt", type: "line", source: "lt", layout: { "line-join": "round" },
          paint: { "line-color": cor("--lt"), "line-opacity": 0.72,
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["interpolate", ["linear"], ["get", "kv"], 230, 0.5, 500, 1, 800, 1.6], 8, ["interpolate", ["linear"], ["get", "kv"], 230, 1.2, 500, 2.4, 800, 3.6]] } },
        /* rebanho bovino por município: tamanho pela raiz quadrada das cabeças (a área do ponto acompanha o rebanho);
           os maiores vêm primeiro no arquivo e ficam por baixo, para os pequenos continuarem visíveis */
        { id: "boi", type: "circle", source: "boi", layout: { "circle-sort-key": ["-", 0, ["get", "b"]] },
          paint: { "circle-color": cor("--boi"), "circle-opacity": 0.72, "circle-stroke-color": "#2b1a0c", "circle-stroke-width": 0.4,
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.5, 100, 1, 300, 2, 700, 3.6, 1700, 7],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.9, 100, 1.9, 300, 3.8, 700, 7, 1700, 13],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 1.6, 100, 3.4, 300, 6.8, 700, 12, 1700, 22]] } },
        /* usinas (EPE): cor pela fonte, tamanho pela raiz quadrada da potência (a área do ponto acompanha os MW) */
        { id: "usinas", type: "circle", source: "usinas", layout: { "circle-sort-key": ["-", 0, ["get", "kw"]] },
          paint: { "circle-color": ["match", ["get", "t"], ["uhe", "pch", "cgh"], cor("--hid"), "eol", cor("--eol"), "sol", cor("--sol"), "bio", cor("--bio"), "fos", cor("--fos"), "nuc", cor("--nuc"), "#ffffff"],
            "circle-opacity": 0.88, "circle-stroke-color": "#0d1712", "circle-stroke-width": 0.6,
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 1, 100, 1.4, 300, 2.4, 1000, 4.5, 3800, 12],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 1.8, 100, 2.6, 300, 4.4, 1000, 8, 3800, 20],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 3, 100, 4.4, 300, 7.5, 1000, 13, 3800, 30]] } },
        /* sinal 4G/5G por município (Anatel, IBC): cor pela faixa da população com sinal; os de sinal fraco ficam por cima */
        { id: "celm", type: "circle", source: "celm", layout: { "circle-sort-key": ["-", 0, ["get", "s"]] },
          paint: { "circle-color": ["step", ["get", "s"], cor("--cel1"), 50, cor("--cel2"), 80, cor("--cel3"), 95, cor("--cel4")],
            "circle-opacity": 0.9, "circle-stroke-color": "#06100c", "circle-stroke-width": 0.5,
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 1.5, 6, 3, 9, 5.5] } },
        /* 5G (Anatel, RQUAL): anel em volta da sede dos municípios com 5G */
        { id: "g5", type: "circle", source: "g5",
          paint: { "circle-opacity": 0, "circle-stroke-color": cor("--g5"),
            "circle-stroke-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 5, 0.95],
            "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 5, 1.2, 8, 1.8],
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 2, 5, 3.6, 7, 5.6, 9, 8] } },
        /* tamanho do poço pela produção (raiz quadrada: a área do ponto acompanha os barris) */
        { id: "pocos", type: "circle", source: "pocos", layout: { "circle-sort-key": ["get", "b"] },
          paint: { "circle-color": cor("--oil"), "circle-opacity": 0.88, "circle-stroke-color": "#2a1d05", "circle-stroke-width": 0.5,
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.8, 10, 1.2, 50, 2.4, 150, 4.5, 260, 6.5],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 1.4, 10, 2.2, 50, 4, 150, 7.5, 260, 10.5],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 2.4, 10, 3.6, 50, 6.5, 150, 12, 260, 17]] } },
        { id: "plataformas", type: "symbol", source: "uep",
          layout: { "icon-image": ["case", ["get", "prevista"], "uep-prevista", "uep"], "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, 0.55, 6, 0.85, 9, 1.15] } },
        { id: "estado-sel", type: "line", source: "estados", filter: ["==", ["get", "sigla"], ""],
          paint: { "line-color": cor("--accent"), "line-width": 2.6 } },
        { id: "pce-rotulo", type: "symbol", source: "pce", filter: ["==", ["get", "parte"], "rotulo"],
          layout: { "text-field": ["get", "texto"], "text-font": fonte(SEMI), "text-size": 10, "text-letter-spacing": 0.12, "text-transform": "uppercase", "text-max-width": 14 },
          paint: { "text-color": "rgba(244,196,235,.9)", ...halo } },
        { id: "presal-rotulo", type: "symbol", source: "presal", filter: ["==", ["get", "parte"], "rotulo"],
          layout: { "text-field": ["get", "texto"], "text-font": fonte(SEMI), "text-size": 11, "text-letter-spacing": 0.3 },
          paint: { "text-color": "rgba(255,240,168,.95)", ...halo } },
        { id: "rodovias-rotulo", type: "symbol", source: "rod", minzoom: 6, filter: ["!=", ["get", "s"], ""],
          layout: { "symbol-placement": "line", "symbol-spacing": 420, "text-field": ["get", "s"], "text-font": fonte(SEMI), "text-size": 10,
            "text-letter-spacing": 0.05, "text-max-angle": 35, "text-padding": 6 },
          paint: { "text-color": "#f3ecd6", ...halo } },
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
    if ((e.id === "uep" || e.id === "uep-prevista") && !map.hasImage(e.id)) {
      /* plataforma: quadrado cheio; prevista: só o contorno */
      const n = 24, c = document.createElement("canvas"); c.width = c.height = n;
      const x = c.getContext("2d");
      if (e.id === "uep") { x.fillStyle = "#200805"; x.fillRect(3, 3, 18, 18); x.fillStyle = cor("--uep"); x.fillRect(5, 5, 14, 14); }
      else { x.strokeStyle = "#200805"; x.lineWidth = 5; x.strokeRect(6, 6, 12, 12); x.strokeStyle = cor("--uep"); x.lineWidth = 2.6; x.strokeRect(6, 6, 12, 12); }
      map.addImage(e.id, x.getImageData(0, 0, n, n), { pixelRatio: 2 });
      return;
    }
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
    pce: ["pce-fill-rec", "pce-fill-ana", "pce-line-rec", "pce-line-ana", "pce-rotulo"], rod: ["rodovias", "rodovias-terra", "rodovias-rotulo"], rodest: ["rodovias-est"],
    oil: ["pocos"], uep: ["plataformas"], campos: ["campos-fill", "campos-line"], presal: ["presal-line", "presal-rotulo"], boi: ["boi"], usinas: ["usinas"], lt: ["lt"], celm: ["celm"], g5: ["g5"],
    rail: ["ferrovias", "ferrovias-obra"], ports: ["portos"], air: ["aeroportos"] };

  /* ---------- painel e enquadramento ---------- */
  const stage = document.getElementById("stage");
  const dock = document.querySelector(".dock"), unfold = document.getElementById("unfold");
  const largo = () => innerWidth > 900;
  const espacoPainel = () => largo() && !dock.hidden ? dock.offsetWidth + 40 : 0;
  const topo = () => largo() ? document.getElementById("top").offsetHeight : 0;
  const folga = () => largo() ? { top: topo() + 40, bottom: 40, left: 10, right: espacoPainel() + 110 } : { top: 20, bottom: 20, left: 12, right: 12 };
  function ajustarCabecalho() {
    stage.style.setProperty("--head", (topo() + 4) + "px"); stage.style.setProperty("--dock-w", espacoPainel() + "px");
    requestAnimationFrame(afastarLegenda);
  }
  /* enquadramento pelo continente: cada estado traz a "caixa" sem as ilhas oceânicas (Fernando de Noronha, Trindade),
     gravada pelo gerador do contorno; sem ela, o Espírito Santo seria enquadrado junto com Trindade, a 1.100 km da costa */
  const caixaUF = f => f.properties.caixa || caixa(f.geometry);
  const BRASIL = (() => { const cs = estados.features.map(caixaUF);
    return [[Math.min(...cs.map(c => c[0][0])), Math.min(...cs.map(c => c[0][1]))], [Math.max(...cs.map(c => c[1][0])), Math.max(...cs.map(c => c[1][1]))]]; })();
  /* afastar tem limite: até o globo inteiro caber na tela, abaixo do cabeçalho, com uma folga pequena.
     Visto de cima, o globo fica sempre no centro da tela. O MapLibre aplica o limite ao tamanho do globo,
     que é o mesmo em qualquer latitude (zoom "no equador"). */
  function limitarZoom() {
    const cv = map.getCanvas(), w = cv.clientWidth, h = cv.clientHeight;
    if (!w || !h) return;
    const m = largo() ? 16 : 10;
    const r = Math.max(60, Math.min(h / 2 - topo() - m, w / 2 - m));               /* raio do disco que cabe, em pixels */
    const f = (map.transform && map.transform.cameraToCenterDistance) || 1.5 * h;     /* distância da câmera, em pixels */
    /* contorno de uma esfera vista em perspectiva: r = f·R / √(f² + 2fR)  →  R = (r² + r·√(r² + f²)) / f */
    const R = (r * r + r * Math.sqrt(r * r + f * f)) / f;
    let z = Math.log2(2 * Math.PI * R / 512);
    /* nunca impede o enquadramento do Brasil (o botão Centralizar) */
    const c = map.cameraForBounds(BRASIL, { padding: folga() });
    if (c && isFinite(c.zoom)) z = Math.min(z, c.zoom - Math.log2(Math.cos(maplibregl.LngLat.convert(c.center).lat * Math.PI / 180)));
    map.setMinZoom(Math.max(0, z));
  }
  /* legenda e créditos dividem a última linha do mapa; quando não cabem lado a lado, a legenda sobe para cima dos créditos */
  function afastarLegenda() {
    const lg = document.getElementById("legend"), at = document.querySelector(".maplibregl-ctrl-attrib");
    lg.style.bottom = "";
    if (!largo() || !at || !lg.childElementCount) return;
    const a = at.getBoundingClientRect(), l = lg.getBoundingClientRect();
    if (a.width && l.right + 16 > a.left) lg.style.bottom = Math.round(stage.getBoundingClientRect().bottom - a.top + 8) + "px";
  }
  function verBrasil(dur = 1400) {
    map.fitBounds(BRASIL, { padding: folga(), pitch: modo3d ? 45 : 0, bearing: 0, duration: reduce ? 0 : dur });
  }
  function verEstado(s, dur = 1400) {
    const f = estados.features.find(x => x.properties.sigla === s);
    map.fitBounds(caixaUF(f), { padding: folga(), pitch: modo3d ? 55 : 0, bearing: 0, maxZoom: 8, duration: reduce ? 0 : dur });
  }
  /* "Mostrar painel" ocupa o mesmo lugar do "Recolher" (posição definida no style.css): dá para clicar duas vezes sem mover o mouse */
  function mostrarPainel(abrir) {
    dock.hidden = !abrir; unfold.hidden = abrir;
    try { localStorage.setItem("bec-painel", abrir ? "aberto" : "recolhido"); } catch (e) {}
    ajustarCabecalho(); limitarZoom(); sel ? verEstado(sel, 600) : verBrasil(600);
  }
  document.getElementById("fold").onclick = () => mostrarPainel(false);
  unfold.onclick = () => mostrarPainel(true);
  try { if (largo() && localStorage.getItem("bec-painel") === "recolhido") { dock.hidden = true; unfold.hidden = false; } } catch (e) {}
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

  /* contorno detalhado do IBGE (desvio máximo ≈ 1,7 km, contra ≈ 5 km do contorno leve da abertura):
     baixado na primeira vez que alguém aproxima o mapa ou escolhe um estado */
  let detalhe = "nao";
  async function detalhar() {
    if (detalhe !== "nao") return;
    detalhe = "baixando";
    const d = await getJSON(D + "geo/estados_detalhe.json");
    if (!d) { detalhe = "nao"; return; }
    const aplicar = () => {
      map.getSource("estados").setData(d); detalhe = "ok";
      estados.features.forEach(f => { const u = f.properties.sigla; map.setFeatureState({ source: "estados", id: u }, { fade: !!sel && u !== sel, hover: u === hover }); });
    };
    map.getSource("estados") ? aplicar() : map.once("load", aplicar);
  }
  map.on("zoomend", () => { if (map.getZoom() >= 5) detalhar(); });

  function selecionar(s) {
    if (sel) { map.setFeatureState({ source: "estados", id: sel }, { sel: false }); }
    sel = (sel === s) ? null : s;
    if (sel) detalhar();
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
    const vis = l => map.getLayer(l) && map.getLayoutProperty(l, "visibility") !== "none";
    const { x: px, y: py } = e.point, perto = [[px - 5, py - 5], [px + 5, py + 5]];
    const ue = vis("plataformas") ? map.queryRenderedFeatures(perto, { layers: ["plataformas"] }) : [];
    if (ue.length) {
      const p = ue[0].properties;
      new maplibregl.Popup({ closeButton: false, offset: 10, maxWidth: "300px" }).setLngLat(ue[0].geometry.coordinates)
        .setHTML(`<b>${esc(p.nome)}</b><br>${esc(p.tipo)}${p.operador ? " · " + esc(p.operador) : ""}${p.prevista === true || p.prevista === "true" ? "<br><b>Prevista</b>" : ""}
          ${p.atende ? `<br>Atende: ${esc(p.atende)}` : ""}${p.capacidade_bbl_dia ? `<br>Capacidade: ${fmt(+p.capacidade_bbl_dia)} barris de petróleo/dia` : ""}
          ${p.lamina_m ? `<br>Profundidade da água: ${fmt(+p.lamina_m)} m` : ""}<br><span class="pop-fonte">ANP, cadastro de unidades de produção</span>`).addTo(map);
      return;
    }
    const po = vis("pocos") ? map.queryRenderedFeatures(perto, { layers: ["pocos"] }) : [];
    if (po.length) {
      const f = po.reduce((a, b) => b.properties.b > a.properties.b ? b : a), p = f.properties, M = DATA.oil.meta;
      new maplibregl.Popup({ closeButton: false, offset: 8 }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>Poço ${esc(p.n)}</b><br>Campo ${esc(p.c)} · ${p.a === "M" ? "mar" : "terra"}${p.u ? " · " + esc(p.u) : ""}
          <br>Petróleo: ${fmt(Math.round(p.o))} barris/dia<br>Gás: ${fmt1(p.g)} mil m³/dia<br>Total: ${fmt(Math.round(p.b))} boe/dia
          <br><span class="pop-fonte">ANP, média de ${esc(M.referencia)}</span>`).addTo(map);
      return;
    }
    const us = vis("usinas") && map.getZoom() >= 4 ? map.queryRenderedFeatures(perto, { layers: ["usinas"] }) : [];
    if (us.length) {
      const f = us.reduce((a, b) => b.properties.kw > a.properties.kw ? b : a), p = f.properties, M = DATA.usinas.meta;
      const hidro = ["uhe", "pch", "cgh"].includes(p.t), obs = (M.observacoes || {})[p.n];
      new maplibregl.Popup({ closeButton: false, offset: 8, maxWidth: "300px" }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${esc(p.n)}</b><br>${esc(M.tipos[p.t])} · ${fmt1(p.kw / 1000)} MW${p.uf ? " · " + esc(p.uf) : ""}${p.a ? "<br>Em operação desde " + p.a : ""}
          ${p.x ? "<br>" + (hidro ? "Rio: " : "Combustível: ") + esc(p.x) : ""}${p.d ? "<br>" + esc(p.d) : ""}${obs ? "<br><i>" + esc(obs) + "</i>" : ""}
          <br><span class="pop-fonte">EPE, Webmap; ${esc(M.referencia)}</span>`).addTo(map);
      return;
    }
    /* de longe os pontos do gado cobrem os estados: o clique abre o estado; a partir do zoom 4,5 abre o município */
    const bo = vis("boi") && map.getZoom() >= 4.5 ? map.queryRenderedFeatures(perto, { layers: ["boi"] }) : [];
    if (bo.length) {
      const f = bo.reduce((a, b) => b.properties.b > a.properties.b ? b : a), p = f.properties, M = DATA.boi.meta;
      new maplibregl.Popup({ closeButton: false, offset: 8 }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${esc(p.n)} · ${esc(p.u)}</b><br>${fmt(p.b)} cabeças de gado bovino
          <br><span class="pop-fonte">IBGE, Pesquisa da Pecuária Municipal ${esc(M.referencia)}. O ponto fica na sede do município.</span>`).addTo(map);
      return;
    }
    /* celular: de perto (zoom 4,5), como o gado; a janelinha junta o sinal e o 5G do município, se os dois arquivos já chegaram */
    const ce = map.getZoom() >= 4.5 ? map.queryRenderedFeatures(perto, { layers: ["celm", "g5"].filter(vis) }) : [];
    if (ce.length) {
      const p = ce[0].properties, m = indice("celm")[p.c], g = indice("g5")[p.c];
      const lin = [];
      if (m) lin.push(`Sinal 4G ou 5G: ${fmt1(m[2])}% da população (estimativa da Anatel, IBC ${esc(DATA.celm.meta.referencia)})`);
      if (DATA.g5) lin.push(g ? `5G: ${esc(g[4])} (${esc(DATA.g5.meta.referencia)})` : `Sem 5G registrado em ${esc(DATA.g5.meta.referencia)}`);
      new maplibregl.Popup({ closeButton: false, offset: 8, maxWidth: "300px" }).setLngLat(ce[0].geometry.coordinates)
        .setHTML(`<b>${esc(p.n)} · ${esc(p.u)}</b><br>${lin.join("<br>")}<br><span class="pop-fonte">Anatel, dados abertos. O ponto fica na sede do município.</span>`).addTo(map);
      return;
    }
    const pts = map.queryRenderedFeatures(e.point, { layers: ["portos", "aeroportos", "capitais"].filter(l => map.getLayoutProperty(l, "visibility") !== "none") });
    if (pts.length) {
      const f = pts[0], tipo = f.layer.id === "portos" ? "Porto" : f.layer.id === "aeroportos" ? "Aeroporto" : "Capital";
      const extra = f.layer.id === "portos" ? (f.properties.org == 1 ? "<br>Porto organizado" : "") + (f.properties.obra == 1 ? "<br>Em obras" : "") : "";
      new maplibregl.Popup({ closeButton: false, offset: 10 }).setLngLat(f.geometry.coordinates).setHTML(`<b>${tipo}</b><br>${esc(f.properties.n)}${extra}`).addTo(map);
      return;
    }
    /* rodovias e ferrovias: de perto (zoom 6), para não atrapalhar o clique nos estados */
    const vias = map.getZoom() >= 6 ? map.queryRenderedFeatures([[px - 4, py - 4], [px + 4, py + 4]],
      { layers: ["lt", "ferrovias", "ferrovias-obra", "rodovias", "rodovias-terra", "rodovias-est"].filter(vis) }) : [];
    if (vias.length) {
      const f = vias[0], p = f.properties, trem = f.layer.id.startsWith("ferrovias");
      if (f.layer.id === "lt") {
        new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "300px" }).setLngLat(e.lngLat)
          .setHTML(`<b>${esc(p.n) || "Linha de transmissão"}</b><br>${p.kv} kV${p.ano ? " · em operação desde " + p.ano : ""}${p.c ? "<br>" + esc(p.c) : ""}
            <br><span class="pop-fonte">EPE, Webmap (sistema elétrico existente)</span>`).addTo(map);
        return;
      }
      const html = trem
        ? `<b>Ferrovia${p.obra == 1 ? " em obras" : ""}</b><br>${esc(p.op)}${p.b ? "<br>Bitola " + esc(p.b).toLowerCase() : ""}`
        : f.layer.id === "rodovias-est"
          ? `<b>${esc(p.s)}</b><br>Rodovia estadual pavimentada`
          : `<b>${p.s ? esc(p.s) : "Rodovia federal"}</b><br>Rodovia federal ${p.p == 1 ? "pavimentada" : "sem pavimento"}${p.c ? "<br>Concessionada" + (p.c !== "concessionada" ? " (" + esc(p.c) + ")" : "") : ""}`;
      new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "280px" }).setLngLat(e.lngLat)
        .setHTML(`${html}<br><span class="pop-fonte">IBGE, base cartográfica 1:250.000 (2025)</span>`).addTo(map);
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
    const cp = vis("campos-fill") ? map.queryRenderedFeatures(e.point, { layers: ["campos-fill"] }) : [];
    if (cp.length) {
      const p = cp[0].properties;
      new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "290px" }).setLngLat(e.lngLat)
        .setHTML(`<b>Campo ${esc(p.nome)}</b><br>${esc(p.etapa)}${p.fluido ? " · " + esc(p.fluido) : ""}
          ${p.operador ? `<br>Operador: ${esc(p.operador)}` : ""}${p.bacia ? `<br>Bacia ${esc(p.bacia)}` : ""}${p.inicio ? ` · produção desde ${esc(p.inicio)}` : ""}
          <br><span class="pop-fonte">ANP, servidor de mapas</span>`).addTo(map);
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
    oil: "M6 21L12 3l6 18M8 15h8M9 10h6M4 21h16",
    uep: "M3 20h18M6 20v-8h12v8M8 12V8h8v4M12 8V3M10 3h4",
    campos: "M3 7l6-3 6 3 6-3v13l-6 3-6-3-6 3zM9 4v13M15 7v13",
    presal: "M4 9l7-5 9 4-2 10-11 2z",
    "p-def": "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z",
    "p-cel": "M12 10v11M8 21h8M9 7a4 4 0 016 0M6 4a8 8 0 0112 0",
    "p-pec": "M4 10h14l2 3v4h-2M4 10v7h2M8 17h8M4 10l-1-3M16 10l1-3",
    boi: "M4 10h14l2 3v4h-2M4 10v7h2M8 17h8M4 10l-1-3M16 10l1-3",
    "p-rod": "M8 21L10 3M16 21L14 3M12 6v2M12 11v2M12 16v2",
    rod: "M8 21L10 3M16 21L14 3M12 6v2M12 11v2M12 16v2",
    rodest: "M8 21L10 3M16 21L14 3M12 8v1M12 14v1",
    "p-ene": "M13 2L5 14h6l-1 8 8-12h-6z",
    usinas: "M13 2L5 14h6l-1 8 8-12h-6z",
    lt: "M12 2l-5 20M12 2l5 20M8 9h8M7 14h10M5 20h14",
    celm: "M12 10v11M8 21h8M9 7a4 4 0 016 0M6 4a8 8 0 0112 0",
    g5: "M12 10v11M8 21h8M9 7a4 4 0 016 0M6 4a8 8 0 0112 0"
  };
  const quando = id => { const m = DATA[id] && DATA[id].meta; return m && m.atualizado_em ? ` · ${m.referencia ? "ref. " + esc(m.referencia) + ", " : ""}atualizado em ${m.atualizado_em}` : ""; };
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
    const zv = LUZ.filter(l => minF === "todos" || l.ministerio === minF), gl = document.getElementById("luzes");
    gl.hidden = !zv.length;
    gl.innerHTML = `<span class="lbl">Luzes à noite</span>` + zv.map(l =>
      `<button class="back" data-l="${l.id}" aria-pressed="${luz === l.id}" ${l.falhou ? "disabled title=\"Não foi possível carregar\"" : `title="${luz === l.id ? "Apagar as luzes" : "Acender: " + l.titulo}"`}>${l.nome}</button>`).join("");
    gl.querySelectorAll("button:not([disabled])").forEach(b => b.onclick = () => definirLuz(luz === b.dataset.l ? "off" : b.dataset.l));
    const L = LUZ.find(l => l.id === luz), info = document.getElementById("luz-info");
    if (!L) info.innerHTML = "";
    else {
      const dd = L.id === "pop" ? luzPop : null;
      info.innerHTML = `<h2 style="margin-top:14px">Luzes à noite</h2><div class="luz-info"><p class="note"><b>${L.titulo}.</b> ${L.explica}</p>
        <div>${dd ? `${pill(dd.nivel)} <span class="note">${dd.fonte} · atualizado em ${dd.atualizado_em}. Posição: ${dd.posicao}.</span>`
             : `${pill(L.nivel)} <span class="note">${L.fonte}.</span>`}</div>
        <p class="note">Com as luzes acesas, os estados ficam sem cor e as rodovias e ferrovias se apagam, para não se confundirem com as luzes (dá para religar em Camadas). Para apagar, clique de novo no botão da luz, no alto do mapa, ou escolha uma pintura acima.</p></div>`;
    }
    const lv = LAYERS.filter(l => minF === "todos" || l.ministerio === minF);
    document.getElementById("layers").innerHTML = lv.length ? lv.map(l => `
      <label class="layer ${l.nivel === "pendente" ? "pend" : ""}">
        <input type="checkbox" id="ly-${l.id}" ${l.on ? "checked" : ""} ${l.nivel === "pendente" ? "disabled" : ""}>${icon(l.id)}
        <span><span class="nm">${l.cor ? `<i class="key" style="background:var(${l.cor})"></i>` : ""}${l.nome} ${pill(l.nivel)}</span>
        <span class="src">${l.fonte}${quando(l.id)} · ${F.ministerios[l.ministerio]}${l.baixando ? " · <b>carregando…</b>" : ""}${l.falhou ? " · <b>não foi possível carregar agora; tente de novo</b>" : ""}</span></span>
      </label>`).join("") : `<p class="note">Este ministério ainda não tem camadas de mapa.</p>`;
    lv.filter(l => l.nivel !== "pendente").forEach(l => document.getElementById("ly-" + l.id).onchange = e => { l.on = e.target.checked; render(); });
    /* ligar ou desligar de uma vez todas as camadas da lista (respeita o ministério escolhido) */
    const lig = lv.filter(l => l.nivel !== "pendente"), todas = document.getElementById("todas");
    if (todas) {
      const tudo = lig.length > 0 && lig.every(l => l.on);
      todas.hidden = !lig.length;
      todas.textContent = tudo ? "Desligar todas" : "Ligar todas";
      todas.onclick = () => { lig.forEach(l => { l.on = !tudo; }); guardadas = null; render(); };
    }
  }

  /* "Legenda no mapa": mostra ou esconde tudo o que fica sobre o mapa (escala de cores e símbolos das camadas).
     Começa ligada; a escolha fica guardada neste navegador. A legenda completa fica sempre no rodapé. */
  let legMapa = true;
  try { legMapa = localStorage.getItem("bec-legenda") !== "rodape"; } catch (e) {}
  document.getElementById("legenda-mapa").onclick = () => {
    legMapa = !legMapa;
    try { localStorage.setItem("bec-legenda", legMapa ? "mapa" : "rodape"); } catch (e) {}
    render();
  };
  /* camadas sob demanda: o arquivo é baixado na primeira vez que a camada é ligada */
  /* id da camada → [fonte de dados do mapa, conversão do arquivo] */
  const SOB = { boi: ["boi", d => fc(d.municipios.map(m => ponto([m[0], m[1]], { b: m[2], n: m[3], u: m[4] })))],
    oil: ["pocos", pocosFC], uep: ["uep", d => d], campos: ["campos", d => d], zc: ["zc", d => d], pce: ["pce", d => d], rodest: ["rodest", d => d],
    usinas: ["usinas", d => fc(d.usinas.map(u => ponto([u[0], u[1]], { kw: u[2], t: u[3], n: u[4], uf: u[5], a: u[6] || 0, d: u[7] || "", x: u[8] || "" })))],
    lt: ["lt", d => d],
    celm: ["celm", d => fc(d.municipios.map(m => ponto([m[0], m[1]], { s: m[2], n: m[3], u: m[4], c: m[5] })))],
    g5: ["g5", d => fc(d.municipios.map(m => ponto([m[0], m[1]], { n: m[2], u: m[3], o: m[4], c: m[5] })))] };
  /* município (código do IBGE) → linha do arquivo, para a janelinha do celular juntar as duas camadas */
  const INDICE = {};
  const indice = id => DATA[id] ? (INDICE[id] || (INDICE[id] = Object.fromEntries(DATA[id].municipios.map(m => [m[5], m])))) : {};
  function baixarSobDemanda() {
    LAYERS.filter(l => l.on && l.sob_demanda && !DATA[l.id] && !l.baixando).forEach(async l => {
      l.baixando = true; l.falhou = false;
      const d = await getJSON(D + l.arquivo);
      l.baixando = false;
      if (!d) { l.on = false; l.falhou = true; render(); return; }
      DATA[l.id] = d;
      const [fonte, converte] = SOB[l.id];
      const aplicar = () => map.getSource(fonte).setData(converte(d));
      map.getSource(fonte) ? aplicar() : map.once("load", aplicar);
      render();
    });
  }
  /* ---------- desenho ---------- */
  function render() {
    baixarSobDemanda();
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
      leg = `<span>${L.titulo}</span><span class="faixa"><span>${L.id === "pop" ? "menos gente" : "escuro"}</span>
        <span class="ramp">${cores.map(c => `<i style="background:${c}"></i>`).join("")}</span><span>${L.id === "pop" ? "mais gente" : "mais luz"}</span></span>`;
    } else if (P && P.val) {
      const vals = Object.keys(NAME).map(P.val).filter(v => v != null);
      const q = quintis(vals), cores = RAMP.map(cor);
      const m = ["match", ["get", "sigla"]];
      /* sem valor: cor da terra; quando a falta tem significado ("sem produção"), cinza, para não parecer o grupo mais baixo */
      Object.keys(NAME).forEach(s => { const v = P.val(s); m.push(s, v == null ? cor(P.vazio ? "--sem" : "--land") : cores[q(v)]); });
      m.push(cor("--land"));
      if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color", m);
      const DD = DATA[P.id];
      leg = `<span>${P.nome}${DD.unidade ? " (" + DD.unidade + ")" : ""}</span><span class="faixa"><span>${P.fmt(Math.min(...vals))}</span>
        <span class="ramp">${RAMP.map(c => `<i style="background:var(${c})"></i>`).join("")}</span><span>${P.fmt(Math.max(...vals))}</span></span>
        ${vals.length < 27 ? (P.vazio ? `<span><i class="key sq" style="background:var(--sem)"></i>${P.vazio}</span>` : "<span>sem cor = sem dado</span>") : ""}`;
    } else if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color", cor("--land"));
    /* legenda completa (escala de cores + símbolos das camadas ligadas): sempre no rodapé, ao lado dos níveis de confiança;
       sobre o mapa só quando o botão "Legenda no mapa" está ligado (bom para tela cheia) */
    const itens = LAYERS.filter(l => l.on && l.cor).map(l => `<span class="item">${(l.legenda || [{ nome: l.nome }]).map(k => {
      const forma = k.forma || (k.hachura ? "hach" : ""), contorno = ["hach", "sqv", "tr", "anel"].includes(forma);
      return `<span><i class="key ${forma}" style="${contorno ? "color" : "background"}:var(${k.cor || l.cor})"></i>${k.nome}</span>`;
    }).join("")}</span>`).join("");
    document.getElementById("legend").innerHTML = legMapa ? leg + itens : "";
    const bl = document.getElementById("legenda-mapa");
    if (bl) bl.setAttribute("aria-pressed", legMapa);
    const lr = document.getElementById("legenda");
    if (lr) lr.innerHTML = (leg ? `<span class="item escala">${leg}</span>` : "") + (itens || `<span class="note">Nenhuma camada ligada. Escolha as camadas no painel.</span>`);
    document.getElementById("back").hidden = !sel;
    document.getElementById("where").textContent = sel ? `${NAME[sel]} · ${sel}` : "Brasil · 27 UFs";
  }

  /* ---------- luzes à noite ---------- */
  const FADE = ["boolean", ["feature-state", "fade"], false], HOVER = ["boolean", ["feature-state", "hover"], false];
  const COR_POP_LEG = ["#6e370a", "#d77d23", "#ffbe50", "#ffe8aa", "#fffceb"];
  const COR_NOITE_LEG = ["#0a0c1c", "#2c2a44", "#a8823f", "#f2d083", "#fffbe8"];
  function linhasTrem() {
    const n = luz !== "off";
    for (const id of ["ferrovias", "ferrovias-obra"]) map.setPaintProperty(id, "line-opacity", sel ? ["case", ["==", ["get", "uf"], sel], n ? 0.6 : 1, n ? 0.06 : 0.15] : (n ? 0.35 : 0.9));
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
    map.setPaintProperty("rodovias", "line-opacity", n ? 0.22 : 0.62);
    map.setPaintProperty("rodovias-terra", "line-opacity", n ? 0.18 : 0.5);
    map.setPaintProperty("rodovias-est", "line-opacity", n ? 0.18 : 0.5);
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
    const linhas = LAYERS.filter(l => ["rod", "rodest", "rail"].includes(l.id) && l.nivel !== "pendente");
    if (antes === "off" && luz !== "off") { guardadas = {}; linhas.forEach(l => { guardadas[l.id] = l.on; l.on = false; }); }
    if (antes !== "off" && luz === "off" && guardadas) { linhas.forEach(l => { if (l.id in guardadas) l.on = guardadas[l.id]; }); guardadas = null; }
    if (map.getLayer("estados-fill")) { prepararLuzes(); aplicarNoite(); }
    render();
  }

  function fichaOleo(s) {
    const O = DATA.oleo;
    if (!O) return "";
    const v = O.valores[s], rk = Object.entries(O.valores).sort((a, b) => b[1].valor - a[1].valor).findIndex(e => e[0] === s) + 1;
    return `<div class="sec"><h3>Petróleo e gás</h3>${v ? `
      <div class="kv"><span>Produção total</span><span class="v">${fmt(v.valor)} boe/dia</span></div>
      <div class="kv"><span>Petróleo</span><span class="v">${fmt(v.petroleo_bbl_dia)} barris/dia</span></div>
      <div class="kv"><span>Gás natural</span><span class="v">${fmt(v.gas_mil_m3_dia)} mil m³/dia</span></div>
      <div class="kv"><span>Poços produzindo</span><span class="v">${fmt(v.pocos)}</span></div>
      <div class="kv"><span>Posição no país</span><span class="v">${rk}º · ${fmt1(v.valor / O.total_boe_dia * 100)}%</span></div>`
      : `<div class="list">Nenhuma produção registrada na ANP neste mês.</div>`}
      ${pill(O.nivel)} <span class="note">${esc(O.fonte)}; média de ${esc(O.referencia)} · atualizado em ${O.atualizado_em}</span></div>`;
  }

  /* energia elétrica do estado (EPE): potência instalada por fonte */
  function fichaEnergia(s) {
    const E = DATA.ene;
    if (!E) return "";
    const v = E.valores[s], fonte = `${pill(E.nivel)} <span class="note">${esc(E.fonte)}; ${esc(E.referencia)} · atualizado em ${E.atualizado_em}</span>`;
    if (!v) return `<div class="sec"><h3>Energia elétrica</h3><div class="list">Nenhuma usina deste estado na base da EPE (geração centralizada).</div>${fonte}</div>`;
    const NOM = { hid: "Hidrelétricas", eol: "Eólicas", sol: "Solares", bio: "Térmicas a biomassa", fos: "Térmicas fósseis", nuc: "Nucleares" };
    const partes = [["hid", (v.uhe || 0) + (v.pch || 0) + (v.cgh || 0)], ["eol", v.eol], ["sol", v.sol], ["bio", v.bio], ["fos", v.fos], ["nuc", v.nuc]]
      .filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]);
    const rk = Object.entries(E.valores).sort((a, b) => b[1].valor - a[1].valor).findIndex(e => e[0] === s) + 1;
    return `<div class="sec"><h3>Energia elétrica</h3>
      <div class="kv"><span>Potência instalada</span><span class="v">${fmt(Math.round(v.valor))} MW</span></div>
      <div class="kv"><span>Posição no país</span><span class="v">${rk}º · ${fmt1(v.valor / E.total_mw * 100)}%</span></div>
      ${partes.map(([k, mw]) => `<div class="kv"><span>${NOM[k]}</span><span class="v">${fmt(Math.round(mw))} MW · ${mw / v.valor < 0.001 ? "menos de 0,1" : fmt1(mw / v.valor * 100)}%</span></div>`).join("")}
      <div class="list">${fmt(v.usinas)} usinas na base. Só a geração centralizada: os painéis solares de telhado não entram.</div>
      ${(v.obs || []).map(o => `<div class="list"><i>${esc(o)}</i></div>`).join("")}
      ${fonte}</div>`;
  }

  /* telefonia celular do estado (Anatel): sinal 4G/5G, 5G nos municípios, fibra, antenas e o índice de conectividade */
  function fichaCelular(s) {
    const C = DATA.cel;
    if (!C || !C.valores[s]) return "";
    const v = C.valores[s], G5 = C.cinco_g;
    const pos = k => Object.entries(C.valores).filter(e => e[1][k] != null).sort((a, b) => b[1][k] - a[1][k]).findIndex(e => e[0] === s) + 1;
    return `<div class="sec"><h3>Telefonia celular</h3>
      <div class="kv"><span>Moradores com sinal 4G ou 5G</span><span class="v">${fmt1(v.valor)}% · ${pos("valor")}º</span></div>
      ${v.g5 ? `<div class="kv"><span>Municípios com 5G</span><span class="v">${fmt(v.g5[0])} de ${fmt(v.g5[1])}</span></div>` : ""}
      ${v.fibra != null ? `<div class="kv"><span>Municípios com fibra óptica</span><span class="v">${fmt(v.fibra)}%</span></div>` : ""}
      ${v.erb_10mil != null ? `<div class="kv"><span>Antenas por 10 mil habitantes</span><span class="v">${fmt1(v.erb_10mil)}</span></div>` : ""}
      ${v.ibc != null ? `<div class="kv"><span>Índice Brasileiro de Conectividade</span><span class="v">${fmt1(v.ibc)} · ${pos("ibc")}º</span></div>` : ""}
      <div class="list">O sinal é estimado pela Anatel a partir das antenas licenciadas, não medido no local. Fibra óptica: a rede que leva a internet até a cidade (backhaul). O índice vai de 0 a 100 e junta sinal, acessos, antenas, fibra e concorrência.</div>
      ${pill(C.nivel)} <span class="note">${esc(C.fonte)} · atualizado em ${C.atualizado_em}</span>
      ${G5 ? `<br>${pill(C.nivel)} <span class="note">5G: Anatel, presença da telefonia móvel (RQUAL), ${esc(G5.referencia)} · atualizado em ${G5.atualizado_em}</span>` : ""}</div>`;
  }

  /* pecuária e aquicultura do estado (IBGE, PPM) */
  function fichaPecuaria(s) {
    const R = DATA.reb;
    if (!R) return "";
    const v = R.valores[s];
    if (!v) return "";
    const rk = Object.entries(R.valores).sort((a, b) => (b[1].bovino || 0) - (a[1].bovino || 0)).findIndex(e => e[0] === s) + 1;
    const n = x => x == null ? "—" : fmt(x);
    return `<div class="sec"><h3>Pecuária e aquicultura</h3>
      <div class="kv"><span>Bois e vacas</span><span class="v">${n(v.bovino)}</span></div>
      <div class="kv"><span>Posição no país (bovinos)</span><span class="v">${rk}º · ${fmt1(v.bovino / R.total_bovino * 100)}%</span></div>
      <div class="kv"><span>Porcos</span><span class="v">${n(v.suino)}</span></div>
      <div class="kv"><span>Galinhas e frangos</span><span class="v">${n(v.galinaceos)}</span></div>
      <div class="kv"><span>Ovelhas</span><span class="v">${n(v.ovino)}</span></div>
      <div class="kv"><span>Cabras</span><span class="v">${n(v.caprino)}</span></div>
      ${v.aquicultura_mil_rs != null ? `<div class="kv"><span>Aquicultura (valor da produção)</span><span class="v">${reais(v.aquicultura_mil_rs)}</span></div>
        ${v.aquicultura_principal ? `<div class="list">Principal produto: ${esc(v.aquicultura_principal)} (${reais(v.aquicultura_principal_mil_rs)}).</div>` : ""}` : ""}
      <div class="list">Animais contados pelo IBGE em 31 de dezembro.</div>
      ${pill(R.nivel)} <span class="note">${esc(R.fonte)}, ref. ${esc(R.referencia)} · atualizado em ${R.atualizado_em}</span></div>`;
  }

  function ficha() {
    const el = document.getElementById("ficha");
    const popInfo = DATA.pop ? `${pill(DATA.pop.nivel)} <span class="note">${DATA.pop.fonte} · atualizado em ${DATA.pop.atualizado_em}</span>` : pill("pendente");
    if (!sel) {
      el.innerHTML = `<h2>Visão nacional</h2><div class="fname">Brasil</div>
        <div class="kv"><span>População</span><span class="v">${fmt(popTot)}</span></div>${popInfo}
        ${DATA.oleo ? `<div class="kv" style="margin-top:8px"><span>Petróleo e gás</span><span class="v">${fmt1(DATA.oleo.total_boe_dia / 1e6)} milhões de boe/dia</span></div>
          ${pill(DATA.oleo.nivel)} <span class="note">ANP, média de ${esc(DATA.oleo.referencia)} · atualizado em ${DATA.oleo.atualizado_em}. boe = barril de óleo equivalente.</span>` : ""}
        ${DATA.ene ? `<div class="kv" style="margin-top:8px"><span>Energia elétrica</span><span class="v">${fmt(Math.round(DATA.ene.total_mw / 1000))} mil MW</span></div>
          ${pill(DATA.ene.nivel)} <span class="note">EPE, potência instalada (${esc(DATA.ene.referencia)}) · atualizado em ${DATA.ene.atualizado_em}. Sem os painéis solares de telhado.</span>` : ""}
        ${DATA.cel && DATA.cel.cinco_g ? `<div class="kv" style="margin-top:8px"><span>Municípios com 5G</span><span class="v">${fmt(DATA.cel.cinco_g.municipios)} de ${fmt(DATA.cel.cinco_g.total)}</span></div>
          ${pill(DATA.cel.nivel)} <span class="note">Anatel, presença da telefonia móvel (RQUAL), ${esc(DATA.cel.cinco_g.referencia)} · atualizado em ${DATA.cel.cinco_g.atualizado_em}. Pelo menos uma operadora com 5G no município.</span>` : ""}
        <p class="lede">Clique num estado para aproximar. Arraste para girar o globo, role para aproximar e use o botão "Relevo 3D" para ver as montanhas em altura.</p>`;
      return;
    }
    const s = sel;
    const rk = Object.entries(POP).sort((a, b) => b[1] - a[1]).findIndex(e => e[0] === s) + 1;
    const Pt = (DATA.ports || []).filter(p => p.uf === s), A = (DATA.air || []).filter(a => a.uf === s);
    const km = DATA.rail ? DATA.rail.km_por_uf[s] || 0 : 0;
    const kr = DATA.rod && DATA.rod.meta && DATA.rod.meta.km_por_uf ? DATA.rod.meta.km_por_uf[s] : null;
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
      ${fichaPecuaria(s)}
      <div class="sec"><h3>Logística</h3>
        ${kr ? `<div class="kv"><span>Rodovias federais</span><span class="v">≈ ${fmt(kr[0])} km</span></div>
          <div class="list">${fmt(kr[1])} km pavimentados.</div>` : ""}
        <div class="kv"><span>Ferrovias em operação</span><span class="v">${km ? "≈ " + fmt(km) + " km" : "nenhuma na base"}</span></div>
        <div class="kv"><span>Portos e terminais</span><span class="v">${Pt.length}</span></div>
        ${Pt.length ? `<div class="list">${Pt.map(p => esc(p.n)).join(", ")}</div>` : ""}
        ${pill("manual")} <span class="note">IBGE, base cartográfica 1:250.000 (BC250, 2025); medidas no desenho do mapa.</span>
        <div class="kv" style="margin-top:8px"><span>Aeroportos na base</span><span class="v">${A.length}</span></div>
        ${A.length ? `<div class="list">${A.map(a => a.n + (a.i ? " (" + a.i + ")" : "")).join(", ")}</div>` : ""}
        ${pill("base")} <span class="note">Natural Earth, só os maiores. Ausência na base não significa ausência real.</span></div>
      ${fichaOleo(s)}
      ${fichaEnergia(s)}
      ${fichaCelular(s)}
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
  limitarZoom(); verBrasil(0);
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
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { ajustarCabecalho(); map.resize(); limitarZoom(); }, 150); });
  /* a legenda acompanha os créditos quando eles abrem ou fecham (botão i) e quando a própria legenda muda de tamanho */
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => afastarLegenda());
    ro.observe(document.getElementById("legend"));
    const at = document.querySelector(".maplibregl-ctrl-attrib"); if (at) ro.observe(at);
  }
  window.__mapa = map;
})();
