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
/* versão de teste (endereço com ?teste): visual novo em avaliação, sem mudar o site normal (selo "Teste" no título).
   Em 25/10/2026 tudo o que estava em teste foi para o site normal, a pedido do Edu; hoje o teste não tem nada a mais */
const TESTE = new URLSearchParams(location.search).has("teste");
if (TESTE) document.documentElement.classList.add("teste");
/* versão de teste: fundo inteiro com profundidade (icones.js, fundoTeste; ?teste&fundo=a, b ou c) */
const FUNDO = TESTE ? fundoTeste("") : null;
/* aviãozinho (desenho em 24 × 24), usado no ícone dos aeroportos e na lista de camadas */
const AVIAO = "M2 13l9-2V4c0-1 2-1 2 0v7l9 2v2l-9-1v5l3 2v1l-4-1-4 1v-1l3-2v-5l-9 1z";
const fmt = n => n.toLocaleString("pt-BR");
const fmt1 = n => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
const kmTxt = a => a >= 1e6 ? `${(a / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} milhão de km²` : `${fmt(Math.round(a / 1e3))} mil km²`;
/* texto vindo de bases externas entra no HTML sempre escapado */
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const reais = mil => mil >= 1e6 ? `R$ ${fmt1(mil / 1e6)} bi` : mil >= 1e3 ? `R$ ${fmt(Math.round(mil / 1e3))} mi` : `R$ ${fmt(Math.round(mil))} mil`;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
/* versão de teste, fundo "lente": ao rolar a página para baixo, o globo se afasta e fica no centro da tela (pedido do Edu
   em 25/10/2026). O mapa entra numa caixa (.palco-mapa) mais alta que o palco e fica preso na tela (CSS sticky) por um trecho da
   rolagem; a câmera acompanha a rolagem (recuoGlobo, no fim do main). Só no computador (o CSS liga acima de 900 px) */
const RECUO = { ligado: FUNDO === "lente" && !reduce, ativo: false };
if (RECUO.ligado) {
  const mapa = document.getElementById("map"), caixa = document.createElement("div");
  caixa.className = "palco-mapa"; mapa.before(caixa); caixa.append(mapa);
  document.documentElement.classList.add("recuo");
}
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
/* contorno do Brasil: os trechos de divisa que aparecem num estado só (a costa e a fronteira com os vizinhos);
   os que aparecem em dois estados são divisa entre estados. Os trechos seguem a ordem dos anéis de cada estado. */
function contornoBrasil(geo) {
  const chave = (a, b) => (a[0] < b[0] || (a[0] === b[0] && a[1] < b[1])) ? a + ";" + b : b + ";" + a;
  const aneis = [], usos = new Map(), linhas = [];
  geo.features.forEach(f => { const g = f.geometry; (g.type === "Polygon" ? [g.coordinates] : g.coordinates).forEach(pl => pl.forEach(r => aneis.push(r))); });
  for (const r of aneis) for (let i = 0; i < r.length - 1; i++) { const k = chave(r[i], r[i + 1]); usos.set(k, (usos.get(k) || 0) + 1); }
  for (const r of aneis) {
    let atual = null;
    for (let i = 0; i < r.length - 1; i++) {
      if (usos.get(chave(r[i], r[i + 1])) === 1) { if (!atual) { atual = [r[i]]; linhas.push(atual); } atual.push(r[i + 1]); }
      else atual = null;
    }
  }
  return { type: "Feature", properties: {}, geometry: { type: "MultiLineString", coordinates: linhas } };
}
/* faixas por quintil (5 grupos de tamanho igual) */
function quintis(vals) {
  const s = [...vals].sort((a, b) => a - b), q = [0.2, 0.4, 0.6, 0.8].map(p => s[Math.floor(p * (s.length - 1))]);
  return v => q.filter(t => v > t).length;
}
/* atmosfera do globo */
const ATMOS = ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0];
const CEU = { "sky-color": "#06121c", "horizon-color": "#1d4b5e", "fog-color": "#0b2233", "atmosphere-blend": ATMOS };
/* faixas da pintura (escolha do Edu em 23/10/2026): cinza forte = sem número; cinza fraco = nenhum (ex.: "sem produção")
   ou, nas pinturas de total, menos de 0,1% do Brasil (soma dos estados). Esses estados saem da escala, e as 5 faixas
   (quintis) são feitas só com os outros. Em taxas e porcentagens (por habitante, % da população), só o zero é "nenhum". */
function classesEscala(P, ufs) {
  const v = {}; ufs.forEach(s => { v[s] = P.val(s); });
  const total = P.por === "total" ? ufs.reduce((a, s) => a + (v[s] > 0 ? v[s] : 0), 0) : 0;
  const nada = s => (v[s] == null && !!P.vazio) || v[s] === 0;
  const pouco = s => !nada(s) && v[s] != null && P.por === "total" && v[s] < total * 0.001;
  const escala = ufs.filter(s => v[s] != null && !nada(s) && !pouco(s)).map(s => v[s]);
  const q = quintis(escala), c = {};
  ufs.forEach(s => { c[s] = v[s] == null && !P.vazio ? "forte" : nada(s) || pouco(s) ? "fraco" : q(v[s]); });
  return { c, escala, forte: ufs.some(s => c[s] === "forte"),
    fraco: [ufs.some(nada) ? (P.vazio || "zero") : "", ufs.some(pouco) ? "menos de 0,1% do Brasil" : ""].filter(Boolean).join(" ou ") };
}
/* realce do estado sob o mouse (pedido do Edu em 23/10/2026): contorno dourado aceso e tracinhos claros que correm em volta
   (sequência de tracejados que, trocada a cada 50 ms, faz o traço andar; método do exemplo "linha animada" do Mapbox) */
const TRACOS = [[0, 4, 3], [0.5, 4, 2.5], [1, 4, 2], [1.5, 4, 1.5], [2, 4, 1], [2.5, 4, 0.5], [3, 4, 0],
  [0, 0.5, 3, 3.5], [0, 1, 3, 3], [0, 1.5, 3, 2.5], [0, 2, 3, 2], [0, 2.5, 3, 1.5], [0, 3, 3, 1], [0, 3.5, 3, 0.5]];
/* ícones por município que só aparecem dentro do estado escolhido (direção do Edu em 23/10/2026),
   uma camada por vez; no mapa do Brasil (nenhum estado escolhido), os círculos de antes (pedido do Edu em 24/10/2026).
   Boi: silhueta clara num medalhão escuro com aro dourado (desenho em 24 × 24). Lavouras: um ícone por lavoura (icones.js). */
/* desde 25/10/2026 (diretriz God's Eye View, aprovada pelo Edu): usinas, poços, celular, 5G e pedágios também, com o mesmo
   jeito (círculos no Brasil, ícones no estado escolhido). Camada → [círculos, ícones, campo da UF] */
const ICO_ESTADO = { boi: ["boi-geral", "boi", "u"], lav: ["lav-geral", "lav", "u"],
  usinas: ["usinas", "usinas-ico", "uf"], oil: ["pocos", "pocos-ico", "u"], celm: ["celm", "celm-ico", "u"], g5: ["g5", "g5-ico", "u"],
  pedagio: ["pedagio", "pedagio-ico", "u"] };
const NO_ESTADO = new Set(Object.keys(ICO_ESTADO));
/* escolher um estado com a pintura ligada a estas camadas liga os ícones sozinho (só boi e lavouras, como antes) */
const AUTO_ESTADO = new Set(["boi", "lav"]);
/* "fronteira com ..." (versão de teste) */
const COM_PAIS = { URU: "o Uruguai", ARG: "a Argentina", PAR: "o Paraguai", BOL: "a Bolívia", PER: "o Peru", COL: "a Colômbia", VEN: "a Venezuela",
  GUY: "a Guiana", SUR: "o Suriname", GUF: "a Guiana Francesa (França)" };
const BOI = "M2.6 10.4Q3.4 8.4 5.2 8.1L4.3 5.9 5.7 7.8 6.6 7.7 7.3 5.9 7.4 8.1Q8.2 8.5 9.4 8.5L18.2 8.4Q20.6 8.4 20.9 10.6L21.5 14 20.8 14.1 20.4 11.8Q20.2 13.2 19.6 14L19.7 19.6 18.1 19.6 17.8 15.2 10.4 15.2 10 19.6 8.4 19.6 8.1 14.6Q7.1 13.7 6.8 12.7 5.6 12.9 4.3 12.6 3 12.3 2.6 11.6Z";
/* foguete de Alcântara (desenho em 24 × 34; a base fica no ponto), com chama e vapor animados no CSS */
const FOGUETE = `<path class="chama" d="M10 27.2Q12 34 14 27.2z" fill="#ffc45a"/>
  <path d="M7.6 17.5L3.4 24.4v2.6l4.2-3.4zM16.4 17.5l4.2 6.9v2.6l-4.2-3.4z" fill="#ff7a6b" stroke="#1a1206" stroke-width="1"/>
  <path d="M9.6 23h4.8l.8 4.2H8.8z" fill="#7a7064" stroke="#1a1206" stroke-width="1"/>
  <path d="M12 2c4 4 5.2 9.4 4.6 21H7.4C6.8 11.4 8 6 12 2z" fill="#f3efe6" stroke="#1a1206" stroke-width="1.2"/>
  <path d="M12 2.6c2.4 2.4 3.6 5 4.1 7.6H7.9c.5-2.6 1.7-5.2 4.1-7.6z" fill="#e6b450"/>
  <circle cx="12" cy="14.2" r="2.1" fill="#2b3c4d" stroke="#1a1206" stroke-width=".9"/><circle cx="11.3" cy="13.5" r=".6" fill="#cfe6ff"/>`;

(async function main() {
  const temGL = (() => { try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; } })();
  if (!temGL) { document.getElementById("sem3d").hidden = false; return; }
  const [F, estados, mundo, ROT, REL, CAPVIZ] = await Promise.all([
    getJSON(D + "fontes.json"), getJSON(D + "geo/estados.json"), getJSON(D + "geo/mundo.json"),
    getJSON(D + "geo/rotulos.json"), getJSON(D + "relevo/relevo.json"),
    /* capitais dos países vizinhos (Natural Earth) */
    getJSON(D + "geo/capitais_vizinhos.json")]);
  if (!F || !estados) { document.getElementById("ficha").innerHTML = `<p class="note">Não foi possível carregar os dados. Recarregue a página.</p>`; return; }
  const NAME = {}; estados.features.forEach(f => NAME[f.properties.sigla] = f.properties.name);

  const DATA = {}, UNICO = {};
  /* camadas "sob_demanda" (arquivos grandes que começam desligados) só são baixadas quando alguém liga a camada */
  /* camadas marcadas "teste" no fontes.json só existem na versão de teste */
  F.camadas = F.camadas.filter(l => TESTE || !l.teste);
  await Promise.all([...F.pintura, ...F.camadas].filter(l => l.arquivo && !l.sob_demanda).map(async l => {
    DATA[l.id] = await (UNICO[l.arquivo] || (UNICO[l.arquivo] = getJSON(D + l.arquivo)));
    if (!DATA[l.id] && l.nivel) l.nivel = "pendente";
  }));
  const POP = DATA.pop ? DATA.pop.valores : {};
  const popTot = Object.values(POP).reduce((a, b) => a + b, 0);
  const PAINT = [{ id: "none", nome: "Sem cor" }, ...F.pintura.map(p => ({
    ...p, ok: !!DATA[p.id], nivel: DATA[p.id] ? DATA[p.id].nivel : "pendente",
    val: !DATA[p.id] ? null
      : p.por === "per_capita" ? s => (DATA[p.id].valores[s] && POP[s]) ? DATA[p.id].valores[s].valor / POP[s] * 1e5 : null
      : s => { const v = DATA[p.id].valores[s]; return v == null ? null : (typeof v === "object" ? (v[p.campo || "valor"] ?? null) : v); },
    fmt: p.por === "per_capita" || p.por === "percentual" ? fmt1 : fmt,
    unidade: p.unidade || (DATA[p.id] && DATA[p.id].unidade) || ""
  }))];
  const LAYERS = F.camadas.map(l => ({ ...l, on: !!l.ligada && l.nivel !== "pendente" }));
  /* camadas ligadas a uma pintura (ex.: Rebanho bovino → rebanho por município): clicar de novo na pintura liga e desliga */
  const camadasDa = id => { const P = PAINT.find(p => p.id === id);
    return ((P && P.camadas) || []).map(c => LAYERS.find(l => l.id === c)).filter(l => l && l.nivel !== "pendente"); };
  /* o que o ministério escolhido liga sozinho (em "Todos", as camadas que começam ligadas) */
  const padrao = l => minF === "todos" ? !!l.ligada : l.ministerio === minF && l.no_filtro !== false;
  let proxima = "ligar";   /* botão das camadas: ligar todas → desligar todas → padrão */
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
  const trilhos = fc(DATA.rail ? DATA.rail.trechos.map(t => ({ type: "Feature", properties: { uf: t.uf, op: t.op, obra: t.obra || 0, si: t.si || 0, b: t.b || "" }, geometry: { type: "LineString", coordinates: t.l } })) : []);
  const portos = fc((DATA.ports || []).map(p => ponto(p.c, { n: p.n, uf: p.uf, org: p.org || 0, obra: p.obra || 0 })));
  /* aeroportos (ANAC): [lon, lat, código OACI, nome, município servido, UF, passageiros em 12 meses, carga em t] */
  const aeros = fc(DATA.air && DATA.air.aeroportos ? DATA.air.aeroportos.map((a, i) => ponto([a[0], a[1]], { p: a[6], i })) : []);
  /* poços em produção: [lon, lat, boe/dia, barris de petróleo/dia, mil m³ de gás/dia, poço, campo, UF, mar/terra] */
  const pocosFC = d => fc(d.pocos.map(p => ponto([p[0], p[1]], { b: p[2], o: p[3], g: p[4], n: p[5], c: p[6], u: p[7], a: p[8] })));
  /* pedágios federais (ANTT): [lon, lat, praça, concessionária, rodovia, km, município, UF, veículos/dia, % comerciais,
     meses usados, período, aviso, validador]; a janelinha lê a linha pelo índice */
  const pedFC = d => fc(d.pracas.map((p, i) => ponto([p[0], p[1]], { v: p[8] || 0, c: p[9] == null ? -1 : p[9], a: p[12], u: p[7] || "", i })));

  /* ---------- mapa ---------- */
  const fonte = (estilo) => [estilo];
  const SEMI = "Open Sans Semibold", REG = "Open Sans Regular", ITA = "Open Sans Italic";
  const halo = { "text-halo-color": "rgba(6,14,10,.85)", "text-halo-width": 1.6 };
  const AREA = ["==", ["get", "parte"], "area"], LIMITE = ["==", ["get", "parte"], "limite"];
  const map = new maplibregl.Map({
    container: "map",
    locale: { "AttributionControl.ToggleAttribution": "Mostrar ou ocultar os créditos do mapa" },
    attributionControl: { compact: true, customAttribution: "NASA Blue Marble · Terrain Tiles (AWS) · Natural Earth · IBGE · Marine Regions · ANP · ANEEL · EPE · Anatel · ANTT · ANAC · Ministério da Defesa" },
    style: {
      version: 8,
      projection: { type: "globe" },
      glyphs: FONTES + "{fontstack}/{range}.pbf",
      sky: CEU,
      sources: {
        nasa: { type: "raster", tileSize: 256, maxzoom: 8,
          tiles: ["https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg"] },
        dem: { type: "raster-dem", encoding: "terrarium", tileSize: 256, maxzoom: 13,
          tiles: ["https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png"] },
        estados: { type: "geojson", data: estados, promoteId: "sigla" },
        brasil: { type: "geojson", data: contornoBrasil(estados) },
        /* contorno do estado sob o mouse */
        "contorno-hover": { type: "geojson", data: fc([]) },
        /* relevo da terra do Brasil por cima da cor dos estados (sombra e luz translúcidas; ver scripts/estudos/terra_ouro.py) */
        "relevo-ouro": { type: "image", url: D + "relevo/ouro_relevo.webp", coordinates: [[-75, 6], [-28, 6], [-28, -34.5], [-75, -34.5]] },
        mundo: { type: "geojson", data: mundo || fc([]) },
        zee: { type: "geojson", data: DATA.zee || fc([]) },
        mt: { type: "geojson", data: DATA.mt || fc([]) },
        zc: { type: "geojson", data: DATA.zc || fc([]) },
        pce: { type: "geojson", data: DATA.pce || fc([]) },
        pocos: { type: "geojson", data: fc([]) },
        boi: { type: "geojson", data: fc([]) },
        lav: { type: "geojson", data: fc([]) },
        usinas: { type: "geojson", data: fc([]) },
        lt: { type: "geojson", data: fc([]) },
        dutos: { type: "geojson", data: fc([]) },
        se: { type: "geojson", data: fc([]) },
        refin: { type: "geojson", data: DATA.refin || fc([]) },
        celm: { type: "geojson", data: fc([]) },
        g5: { type: "geojson", data: fc([]) },
        empdef: { type: "geojson", data: fc([]) },
        pedagio: { type: "geojson", data: DATA.pedagio ? pedFC(DATA.pedagio) : fc([]) },
        /* versão de teste: fronteira terrestre por tipo e passagens de fronteira (scripts/gerar_fronteira.py); as estradas do
           outro lado esmaecem a partir da fronteira (line-progress) */
        fronttipo: { type: "geojson", data: DATA.fronttipo || fc([]) },
        passa: { type: "geojson", data: DATA.passa || fc([]), lineMetrics: true },
        /* versão de teste: pista dupla (DNIT, SNV de out/2026) e fluxo nas rodovias federais (DNIT, VMDa 2025, sob demanda) */
        dup: { type: "geojson", data: DATA.dup || fc([]) },
        vmda: { type: "geojson", data: fc([]) },
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
        ilhas: { type: "geojson", data: ilhaPts },
        capviz: { type: "geojson", data: fc(CAPVIZ ? CAPVIZ.capitais.map(c => ponto(c.c, { n: c.n, d: c.d })) : []) }
      },
      layers: [
        { id: "fundo", type: "background", paint: { "background-color": "#0a1d2a" } },
        { id: "nasa", type: "raster", source: "nasa", paint: { "raster-brightness-max": 0.62, "raster-saturation": -0.15, "raster-contrast": 0.08, "raster-fade-duration": 200 } },
        /* a base mundial é simplificada: de perto, as divisas entre os vizinhos viram retas que não seguem os rios
           (ex.: Argentina e Uruguai); na versão de teste elas somem a partir do zoom 6 */
        { id: "paises-borda", type: "line", source: "mundo", paint: { "line-color": "rgba(214,198,150,.35)", "line-width": 0.6,
          ...(TESTE ? { "line-opacity": ["interpolate", ["linear"], ["zoom"], 4.8, 1, 6, 0] } : {}) } },
        /* mar: cada arquivo traz a área ("area") e as linhas de limite separadas ("limite", "base") */
        { id: "pce-fill-rec", type: "fill", source: "pce", filter: ["all", AREA, ["==", ["get", "status"], "reconhecida"]],
          paint: { "fill-color": "rgba(229,143,211,.17)" } },
        { id: "pce-fill-ana", type: "fill", source: "pce", filter: ["all", AREA, ["==", ["get", "status"], "em_analise"]],
          paint: { "fill-pattern": "hachura" } },
        { id: "zee-fill", type: "fill", source: "zee", filter: AREA, paint: { "fill-color": "rgba(88,207,224,.10)" } },
        { id: "zc-fill", type: "fill", source: "zc", filter: AREA, paint: { "fill-color": "rgba(95,208,168,.16)" } },
        { id: "mt-fill", type: "fill", source: "mt", filter: AREA, paint: { "fill-color": "rgba(159,230,242,.2)" } },
        { id: "estados-fill", type: "fill", source: "estados",
          paint: { "fill-color": "rgba(0,0,0,0)", "fill-opacity": 0 } },   /* cor e opacidade vêm do render() (visualModo) */
        /* estado escolhido "levantado" (24/10/2026, aprovado pelo Edu): com uma pintura, os outros estados mantêm a cor (assim dá
           para comparar); o escolhido ganha uma sombra curta embaixo e, por cima, ele mesmo de novo, para a sombra só aparecer
           do lado de fora */
        { id: "sel-sombra", type: "fill", source: "estados", filter: ["==", ["get", "sigla"], ""], layout: { visibility: "none" },
          paint: { "fill-color": "rgba(6,3,0,.55)", "fill-translate": [7, 9] } },
        { id: "sel-fill", type: "fill", source: "estados", filter: ["==", ["get", "sigla"], ""], layout: { visibility: "none" },
          paint: { "fill-color": "rgba(0,0,0,0)" } },
        /* o relevo da terra vale até o zoom 5 e some até o 7, onde o relevo sombreado de altitude mostra mais detalhe */
        { id: "relevo-ouro", type: "raster", source: "relevo-ouro", layout: { visibility: "none" },
          paint: { "raster-opacity": ["interpolate", ["linear"], ["zoom"], 5, 1, 7, 0], "raster-fade-duration": 0, "raster-resampling": "linear" } },
        { id: "zee-line", type: "line", source: "zee", filter: LIMITE, paint: { "line-color": cor("--sea-line"), "line-width": 1.4, "line-dasharray": [3, 2] } },
        { id: "zc-line", type: "line", source: "zc", filter: LIMITE, paint: { "line-color": cor("--zc"), "line-width": 0.8, "line-opacity": 0.7 } },
        { id: "mt-line", type: "line", source: "mt", filter: LIMITE, paint: { "line-color": cor("--mt"), "line-width": 0.8, "line-opacity": 0.7 } },
        { id: "mt-base", type: "line", source: "mt", filter: ["==", ["get", "parte"], "base"],
          layout: { "line-cap": "round" }, paint: { "line-color": cor("--mt"), "line-width": 1.2, "line-opacity": 0.85, "line-dasharray": [0.1, 2.2] } },
        { id: "pce-line-rec", type: "line", source: "pce", filter: ["all", LIMITE, ["==", ["get", "status"], "reconhecida"]],
          paint: { "line-color": cor("--pce"), "line-width": 1.3 } },
        { id: "pce-line-ana", type: "line", source: "pce", filter: ["all", LIMITE, ["==", ["get", "status"], "em_analise"]],
          paint: { "line-color": cor("--pce"), "line-width": 1.2, "line-opacity": 0.85, "line-dasharray": [3, 2] } },
        { id: "estados-line", type: "line", source: "estados", paint: { "line-color": "rgba(240,200,130,.55)", "line-width": 0.9 } },
        /* contorno do Brasil em destaque (brilho dourado por baixo de uma linha cheia) */
        { id: "brasil-brilho", type: "line", source: "brasil", layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "rgba(255,184,70,.45)", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 7, 8, 12], "line-blur": 5 } },
        { id: "brasil-linha", type: "line", source: "brasil", layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "#ffe2a6", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1.5, 8, 2.4] } },
        /* versão de teste: a fronteira terrestre na cor do tipo (em rio ou lagoa, seca, seca na mata), por cima do contorno
           dourado (a costa continua dourada); borda escura para a cor aparecer sobre o ouro e sobre os vizinhos */
        { id: "front-borda", type: "line", source: "fronttipo", layout: { "line-join": "round", "line-cap": "round", visibility: "none" },
          paint: { "line-color": "rgba(6,4,2,.85)", "line-width": ["interpolate", ["linear"], ["zoom"], 3, 4.2, 8, 7.4] } },
        { id: "front-linha", type: "line", source: "fronttipo", layout: { "line-join": "round", "line-cap": "round", visibility: "none" },
          paint: { "line-color": ["match", ["get", "t"], ["rio", "lagoa"], cor("--fr-agua"), "mata", cor("--fr-mata"), cor("--fr-seca")],
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, 2, 8, 3.8] } },
        /* realce do estado sob o mouse: brilho dourado e uma luz que corre pelo contorno (no lugar do realce esbranquiçado) */
        { id: "hover-brilho", type: "line", source: "contorno-hover", layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "rgba(255,176,60,.6)", "line-width": 10, "line-blur": 6 } },
        { id: "hover-sombra", type: "line", source: "contorno-hover", layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "rgba(10,6,2,.8)", "line-width": 5.2 } },
        { id: "hover-linha", type: "line", source: "contorno-hover", layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": "#f5b64a", "line-width": 3 } },
        { id: "hover-tracos", type: "line", source: "contorno-hover", layout: { "line-join": "round" },
          paint: { "line-color": "#fff6dc", "line-width": 3, "line-dasharray": TRACOS[0] } },
        { id: "campos-fill", type: "fill", source: "campos", paint: { "fill-color": "rgba(217,144,43,.2)" } },
        { id: "campos-line", type: "line", source: "campos", paint: { "line-color": cor("--campo"), "line-width": 0.8, "line-opacity": 0.85 } },
        { id: "presal-line", type: "line", source: "presal", filter: AREA,
          paint: { "line-color": cor("--presal"), "line-width": 1.5, "line-opacity": 0.9, "line-dasharray": [3, 2] } },
        /* rodovias (IBGE, BC250): estaduais pavimentadas por baixo; federais pavimentadas em traço cheio,
           federais sem pavimento tracejadas; trechos com sigla BR administrados pelo estado (e=1) na cor das estaduais */
        { id: "rodovias-est", type: "line", source: "rodest", layout: { "line-cap": "round" },
          paint: { "line-color": cor("--road-est"), "line-opacity": 0.5, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.4, 8, 1.3] } },
        { id: "rodovias-terra", type: "line", source: "rod", filter: ["==", ["get", "p"], 0],
          paint: { "line-color": ["case", ["==", ["get", "e"], 1], cor("--road-est"), cor("--road")], "line-opacity": 0.5, "line-dasharray": [2, 2], "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.6, 8, 1.4] } },
        /* borda escura por baixo das rodovias federais pavimentadas, para a linha clara aparecer sobre qualquer cor */
        { id: "rodovias-borda", type: "line", source: "rod", filter: ["==", ["get", "p"], 1], layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "rgba(14,9,4,.7)", "line-opacity": 1,
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["case", ["==", ["get", "e"], 1], 1.7, 2.1], 8, ["case", ["==", ["get", "e"], 1], 3.1, 3.8]] } },
        /* versão de teste: estradas do outro lado da fronteira (Natural Earth), claras e esmaecendo até sumir (~45 km) */
        { id: "passa-estrada-borda", type: "line", source: "passa", filter: ["==", ["get", "k"], "estrada"],
          layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
          paint: { "line-width": ["interpolate", ["linear"], ["zoom"], 3, 2.2, 8, 4.2],
            "line-gradient": ["interpolate", ["linear"], ["line-progress"], 0, "rgba(14,9,4,.7)", 1, "rgba(14,9,4,0)"] } },
        { id: "passa-estrada", type: "line", source: "passa", filter: ["==", ["get", "k"], "estrada"],
          layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
          paint: { "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.8, 8, 2],
            "line-gradient": ["interpolate", ["linear"], ["line-progress"], 0, "rgba(246,243,236,.95)", 0.55, "rgba(246,243,236,.5)", 1, "rgba(246,243,236,0)"] } },
        { id: "rodovias", type: "line", source: "rod", filter: ["==", ["get", "p"], 1], layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": ["case", ["==", ["get", "e"], 1], cor("--road-est"), cor("--road")], "line-opacity": 0.92,
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["case", ["==", ["get", "e"], 1], 0.6, 0.8], 8, ["case", ["==", ["get", "e"], 1], 1.5, 2]] } },
        /* versão de teste: pista dupla (DNIT, SNV): duas linhas finas com a rodovia no meio (line-gap-width); em obra, tracejada */
        { id: "dup", type: "line", source: "dup", filter: ["==", ["get", "d"], 1], layout: { "line-join": "round", visibility: "none" },
          paint: { "line-color": cor("--dup"), "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 8, 1.3],
            "line-gap-width": ["interpolate", ["linear"], ["zoom"], 3, 1.3, 8, 2.8] } },
        { id: "dup-obra", type: "line", source: "dup", filter: ["==", ["get", "d"], 2], layout: { "line-join": "round", visibility: "none" },
          paint: { "line-color": cor("--dup"), "line-width": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 8, 1.3],
            "line-gap-width": ["interpolate", ["linear"], ["zoom"], 3, 1.3, 8, 2.8], "line-dasharray": [2, 1.6] } },
        /* versão de teste: fluxo nas rodovias federais (DNIT, VMDa 2025): largura pelos veículos por dia (raiz quadrada),
           cor pela parte de ônibus e caminhões (as mesmas faixas dos pedágios); os de mais tráfego por cima */
        { id: "vmda-borda", type: "line", source: "vmda", layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
          paint: { "line-color": "rgba(12,8,3,.75)",
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["+", 1.6, ["*", 0.012, ["sqrt", ["get", "v"]]]], 8, ["+", 3.2, ["*", 0.032, ["sqrt", ["get", "v"]]]]] } },
        { id: "vmda", type: "line", source: "vmda", layout: { "line-cap": "round", "line-join": "round", visibility: "none" },
          paint: { "line-color": ["case", ["<", ["get", "p"], 0], cor("--tr0"), ["step", ["get", "p"], cor("--tr1"), 25, cor("--tr2"), 40, cor("--tr3"), 55, cor("--tr4")]],
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["+", 0.4, ["*", 0.012, ["sqrt", ["get", "v"]]]], 8, ["+", 1, ["*", 0.032, ["sqrt", ["get", "v"]]]]] } },
        /* ferrovia no símbolo clássico dos mapas (24/10/2026), para aparecer sobre qualquer cor: faixa escura com o miolo claro
           cortado por "dormentes" escuros; em obras, só os traços (claros com borda escura), sem a faixa */
        { id: "ferrovias-borda", type: "line", source: "trilhos", filter: ["!=", ["get", "obra"], 1], layout: { "line-join": "round" },
          paint: { "line-color": "rgba(12,8,3,.9)", "line-opacity": 0.9, "line-width": ["interpolate", ["linear"], ["zoom"], 3, 3, 8, 5.6] } },
          /* a borda dos traços em obras tem o dobro da largura do miolo: o tracejado (medido em larguras) fica com metade
             do número para os traços dos dois coincidirem */
          { id: "ferrovias-obra-borda", type: "line", source: "trilhos", filter: ["==", ["get", "obra"], 1],
          paint: { "line-color": "rgba(12,8,3,.9)", "line-opacity": 0.9, "line-dasharray": [0.8, 1.1], "line-width": ["interpolate", ["linear"], ["zoom"], 3, 2.6, 8, 5] } },
        { id: "ferrovias", type: "line", source: "trilhos", filter: ["!=", ["get", "obra"], 1],
          paint: { "line-color": "#fbf6ea", "line-opacity": 0.9, "line-dasharray": [3.4, 1.1], "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1.4, 8, 2.6] } },
        { id: "ferrovias-obra", type: "line", source: "trilhos", filter: ["==", ["get", "obra"], 1],
          paint: { "line-color": "#fbf6ea", "line-opacity": 0.9, "line-dasharray": [1.6, 2.2], "line-width": ["interpolate", ["linear"], ["zoom"], 3, 1.3, 8, 2.5] } },
        /* linhas de transmissão (EPE): mais grossas quanto maior a tensão (230 a 800 kV) */
        { id: "lt", type: "line", source: "lt", layout: { "line-join": "round" },
          paint: { "line-color": cor("--lt"), "line-opacity": 0.72,
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["interpolate", ["linear"], ["get", "kv"], 230, 0.5, 500, 1, 800, 1.6], 8, ["interpolate", ["linear"], ["get", "kv"], 230, 1.2, 500, 2.4, 800, 3.6]] } },
        /* subestações (EPE): losango lilás, maior quanto mais alta a tensão */
        { id: "se", type: "symbol", source: "se", layout: { "symbol-sort-key": ["get", "kv"], "icon-image": "se", "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, ["interpolate", ["linear"], ["get", "kv"], 230, 0.35, 500, 0.55, 800, 0.8],
              8, ["interpolate", ["linear"], ["get", "kv"], 230, 0.7, 500, 1, 800, 1.35]] } },
        /* gasodutos e oleodutos (ANP): os de transporte mais grossos */
        { id: "dutos", type: "line", source: "dutos", layout: { "line-join": "round", "line-cap": "round" },
          paint: { "line-color": ["match", ["get", "f"], "gas", cor("--gasd"), cor("--oleod")], "line-opacity": 0.85,
            "line-width": ["interpolate", ["linear"], ["zoom"], 3, ["case", ["==", ["get", "t"], "transporte"], 1.2, 0.6], 8, ["case", ["==", ["get", "t"], "transporte"], 2.8, 1.5]] } },
        /* refinarias (tamanho pela capacidade), unidades de gás natural e terminais de GNL (ANP) */
        { id: "refin", type: "symbol", source: "refin",
          /* medalhão: refinaria (tamanho pela capacidade), chama (unidade de gás natural) e navio (GNL) */
          layout: { "symbol-sort-key": ["-", 0, ["coalesce", ["get", "bbl"], 0]], "icon-image": ["concat", "ref-", ["get", "k"]], "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, ["case", ["==", ["get", "k"], "refinaria"], ["interpolate", ["linear"], ["sqrt", ["coalesce", ["get", "bbl"], 0]], 0, 0.33, 200, 0.42, 660, 0.66], 0.32],
              8, ["case", ["==", ["get", "k"], "refinaria"], ["interpolate", ["linear"], ["sqrt", ["coalesce", ["get", "bbl"], 0]], 0, 0.6, 200, 0.75, 660, 1.15], 0.6]] } },
        /* principal lavoura de cada município (IBGE, PAM): cor pela lavoura de maior valor, tamanho pela raiz do valor de todas
           as lavouras; os maiores vêm primeiro no arquivo e ficam por baixo. No mapa do Brasil, círculos ("lav-geral");
           no estado escolhido, o ícone de cada lavoura ("lav") */
        { id: "lav-geral", type: "circle", source: "lav", layout: { "circle-sort-key": ["-", 0, ["get", "v"]] },
          paint: { "circle-color": ["match", ["get", "g"], "soja", cor("--lav-soja"), "milho", cor("--lav-milho"), "cana", cor("--lav-cana"), "cafe", cor("--lav-cafe"), "mandioca", cor("--lav-mandioca"), "banana", cor("--lav-banana"), "feijao", cor("--lav-feijao"), "arroz", cor("--lav-arroz"), cor("--lav-outras")], "circle-opacity": 0.95,
            /* borda escura mais grossa, para a cor da lavoura não sumir sobre a pintura */
            "circle-stroke-color": "#140c04", "circle-stroke-width": 0.9,
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 0.6, 100, 1.1, 500, 2.4, 1500, 4.6, 3000, 7.5],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 1, 100, 2, 500, 4.4, 1500, 8.5, 3000, 14],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 1.8, 100, 3.6, 500, 8, 1500, 15, 3000, 24]] } },
        /* no estado escolhido, o ícone da lavoura principal (tamanho pelo valor de todas as lavouras) */
        { id: "lav", type: "symbol", source: "lav", filter: ["==", ["get", "u"], ""],
          layout: { "symbol-sort-key": ["-", 0, ["get", "v"]], "icon-image": ["concat", "lav-", ["get", "g"]], "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"],
              4, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 0.3, 100, 0.4, 500, 0.58, 1500, 0.82, 3000, 1.05],
              8, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 0.45, 100, 0.6, 500, 0.88, 1500, 1.2, 3000, 1.5]] } },
        /* rebanho bovino por município: tamanho pela raiz quadrada das cabeças (a área do ponto acompanha o rebanho);
           os maiores vêm primeiro no arquivo e ficam por baixo, para os pequenos continuarem visíveis. No mapa do Brasil,
           círculos ("boi-geral": disco escuro com aro claro, como o medalhão sem o desenho); no estado escolhido, o boi ("boi") */
        { id: "boi-geral", type: "circle", source: "boi", layout: { "circle-sort-key": ["-", 0, ["get", "b"]] },
          paint: { "circle-color": "rgba(18,11,4,.6)", "circle-opacity": 1, "circle-stroke-color": "#f2d9a0", "circle-stroke-width": 0.7,
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.5, 100, 1, 300, 2, 700, 3.6, 1700, 7],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.9, 100, 1.9, 300, 3.8, 700, 7, 1700, 13],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 1.6, 100, 3.4, 300, 6.8, 700, 12, 1700, 22]] } },
        /* no estado escolhido, o boi em medalhão (tamanho pelo rebanho) */
        { id: "boi", type: "symbol", source: "boi", filter: ["==", ["get", "u"], ""],
          layout: { "symbol-sort-key": ["-", 0, ["get", "b"]], "icon-image": "boi", "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"],
              4, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.3, 100, 0.4, 300, 0.55, 700, 0.75, 1700, 1.05],
              8, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.45, 100, 0.6, 300, 0.82, 700, 1.1, 1700, 1.5]] } },
        /* usinas (ANEEL, SIGA; 1 MW ou mais): cor pela fonte, tamanho pela raiz quadrada da potência (a área do ponto acompanha os MW) */
        { id: "usinas", type: "circle", source: "usinas", layout: { "circle-sort-key": ["-", 0, ["get", "kw"]] },
          paint: { "circle-color": ["match", ["get", "t"], ["uhe", "pch", "cgh"], cor("--hid"), "eol", cor("--eol"), "sol", cor("--sol"), "bio", cor("--bio"), "fos", cor("--fos"), "nuc", cor("--nuc"), "#ffffff"],
            "circle-opacity": 0.88, "circle-stroke-color": "#0d1712", "circle-stroke-width": 0.6,
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 1, 100, 1.4, 300, 2.4, 1000, 4.5, 3800, 12],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 1.8, 100, 2.6, 300, 4.4, 1000, 8, 3800, 20],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 3, 100, 4.4, 300, 7.5, 1000, 13, 3800, 30]] } },
        /* no estado escolhido, a usina em medalhão com o desenho da fonte (tamanho pela potência) */
        { id: "usinas-ico", type: "symbol", source: "usinas", filter: ["==", ["get", "uf"], ""],
          layout: { "symbol-sort-key": ["-", 0, ["get", "kw"]], "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-image": ["match", ["get", "t"], ["uhe", "pch", "cgh"], "us-hid", "eol", "us-eol", "sol", "us-sol", "bio", "us-bio", "fos", "us-fos", "nuc", "us-nuc", "us-hid"],
            "icon-size": ["interpolate", ["linear"], ["zoom"],
              4, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 0.3, 100, 0.36, 300, 0.48, 1000, 0.72, 3400, 1.15],
              8, ["interpolate", ["linear"], ["sqrt", ["get", "kw"]], 0, 0.44, 100, 0.54, 300, 0.72, 1000, 1.05, 3400, 1.6]] } },
        /* sinal 4G/5G por município (Anatel, IBC): cor pela faixa da população com sinal; os de sinal fraco ficam por cima */
        { id: "celm", type: "circle", source: "celm", layout: { "circle-sort-key": ["-", 0, ["get", "s"]] },
          paint: { "circle-color": ["step", ["get", "s"], cor("--cel1"), 50, cor("--cel2"), 80, cor("--cel3"), 95, cor("--cel4")],
            "circle-opacity": 0.9, "circle-stroke-color": "#06100c", "circle-stroke-width": 0.5,
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 1.5, 6, 3, 9, 5.5] } },
        /* no estado escolhido, a antena em medalhão, na cor da faixa de sinal (os de sinal fraco por cima) */
        { id: "celm-ico", type: "symbol", source: "celm", filter: ["==", ["get", "u"], ""],
          layout: { "symbol-sort-key": ["-", 0, ["get", "s"]], "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-image": ["step", ["get", "s"], "cel-1", 50, "cel-2", 80, "cel-3", 95, "cel-4"],
            "icon-size": ["interpolate", ["linear"], ["zoom"], 4, 0.4, 6, 0.52, 8, 0.72] } },
        /* 5G (Anatel, RQUAL): anel em volta da sede dos municípios com 5G */
        { id: "g5", type: "circle", source: "g5",
          paint: { "circle-opacity": 0, "circle-stroke-color": cor("--g5"),
            "circle-stroke-opacity": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 5, 0.95],
            "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 3, 0.7, 5, 1.2, 8, 1.8],
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, 2, 5, 3.6, 7, 5.6, 9, 8] } },
        /* no estado escolhido, o anel do 5G em volta do medalhão da antena (raio do medalhão + folga) */
        { id: "g5-ico", type: "circle", source: "g5", filter: ["==", ["get", "u"], ""],
          paint: { "circle-opacity": 0, "circle-stroke-color": cor("--g5"), "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 4, 1.6, 8, 2.4],
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 9, 6, 11, 8, 14.5] } },
        /* pedágios federais (ANTT): tamanho pela raiz dos veículos por dia, cor pela parte de caminhões e ônibus;
           praça sem número confiável (a > 0) fica só com o contorno */
        { id: "pedagio", type: "circle", source: "pedagio", layout: { "circle-sort-key": ["-", 0, ["get", "v"]] },
          paint: { "circle-color": ["step", ["get", "c"], cor("--tr1"), 25, cor("--tr2"), 40, cor("--tr3"), 55, cor("--tr4")],
            "circle-opacity": ["case", [">", ["get", "a"], 0], 0, 0.92],
            "circle-stroke-color": ["case", [">", ["get", "a"], 0], cor("--tr0"), "#1a0d05"],
            "circle-stroke-width": ["case", [">", ["get", "a"], 0], 1.4, 0.6],
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["case", [">", ["get", "a"], 0], 2.4, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 1.5, 100, 3.5, 280, 8]],
              6, ["case", [">", ["get", "a"], 0], 3.5, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 2.5, 100, 6, 280, 13]],
              9, ["case", [">", ["get", "a"], 0], 5, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 4, 100, 9, 280, 20]]] } },
        /* no estado escolhido, a cabine com cancela em medalhão (cor pela parte de caminhões e ônibus,
           tamanho pelos veículos por dia; sem número confiável, cinza e pequeno) */
        { id: "pedagio-ico", type: "symbol", source: "pedagio", filter: ["==", ["get", "u"], ""],
          layout: { "symbol-sort-key": ["-", 0, ["get", "v"]], "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-image": ["case", [">", ["get", "a"], 0], "ped-0", ["step", ["get", "c"], "ped-1", 25, "ped-2", 40, "ped-3", 55, "ped-4"]],
            "icon-size": ["interpolate", ["linear"], ["zoom"],
              4, ["case", [">", ["get", "a"], 0], 0.4, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 0.38, 100, 0.55, 280, 0.9]],
              8, ["case", [">", ["get", "a"], 0], 0.55, ["interpolate", ["linear"], ["sqrt", ["get", "v"]], 0, 0.52, 100, 0.78, 280, 1.3]]] } },
        /* tamanho do poço pela produção (raiz quadrada: a área do ponto acompanha os barris) */
        { id: "pocos", type: "circle", source: "pocos", layout: { "circle-sort-key": ["get", "b"] },
          paint: { "circle-color": cor("--oil"), "circle-opacity": 0.88, "circle-stroke-color": "#2a1d05", "circle-stroke-width": 0.5,
            "circle-radius": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.8, 10, 1.2, 50, 2.4, 150, 4.5, 260, 6.5],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 1.4, 10, 2.2, 50, 4, 150, 7.5, 260, 10.5],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 2.4, 10, 3.6, 50, 6.5, 150, 12, 260, 17]] } },
        /* no estado escolhido, a torre de perfuração em medalhão (tamanho pela produção; os maiores por baixo) */
        { id: "pocos-ico", type: "symbol", source: "pocos", filter: ["==", ["get", "u"], ""],
          layout: { "symbol-sort-key": ["-", 0, ["get", "b"]], "icon-image": "poco", "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"],
              4, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.28, 10, 0.32, 50, 0.45, 150, 0.68, 260, 0.92],
              8, ["interpolate", ["linear"], ["sqrt", ["get", "b"]], 0, 0.4, 10, 0.46, 50, 0.65, 150, 0.98, 260, 1.3]] } },
        { id: "plataformas", type: "symbol", source: "uep",
          layout: { "icon-image": ["case", ["get", "prevista"], "uep-prevista", "uep"], "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, 0.55, 6, 0.85, 9, 1.15] } },
        /* indústria de defesa (Ministério da Defesa): escudo na sede do município, maior quanto mais empresas credenciadas
           (raiz quadrada: a área acompanha o número); os maiores ficam por baixo */
        { id: "empdef", type: "symbol", source: "empdef", layout: { "symbol-sort-key": ["-", 0, ["get", "n"]], "icon-image": "escudo",
            "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, ["interpolate", ["linear"], ["sqrt", ["get", "n"]], 1, 0.5, 7.2, 1.45],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "n"]], 1, 0.75, 7.2, 2.1], 9, ["interpolate", ["linear"], ["sqrt", ["get", "n"]], 1, 1, 7.2, 2.7]] } },
        /* estado escolhido: contorno claro com borda escura (o dourado sumia sobre o ouro) */
        { id: "sel-halo", type: "line", source: "estados", filter: ["==", ["get", "sigla"], ""], layout: { "line-join": "round" },
          paint: { "line-color": "rgba(12,7,2,.9)", "line-width": 8 } },
        { id: "estado-sel", type: "line", source: "estados", filter: ["==", ["get", "sigla"], ""], layout: { "line-join": "round" },
          paint: { "line-color": "#fff3d0", "line-width": 3 } },
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
        { id: "portos", type: "symbol", source: "portos",
          /* âncora em medalhão; porto organizado um pouco maior, em obras mais apagado */
          layout: { "icon-image": "porto", "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, ["case", ["==", ["get", "org"], 1], 0.38, 0.3], 6, ["case", ["==", ["get", "org"], 1], 0.62, 0.5],
              9, ["case", ["==", ["get", "org"], 1], 0.86, 0.7]] },
          paint: { "icon-opacity": ["case", ["==", ["get", "obra"], 1], 0.6, 1] } },
        /* versão de teste: passagens de fronteira (cidades gêmeas), setas cruzando a linha num medalhão */
        { id: "passa-ico", type: "symbol", source: "passa", filter: ["==", ["get", "k"], "passagem"],
          layout: { visibility: "none", "icon-image": "passagem", "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"], 3, 0.34, 6, 0.56, 9, 0.82] } },
        /* aeroportos (ANAC): aviãozinho, tamanho pela raiz dos passageiros de 12 meses; os sem voos de passageiros ficam pequenos e mais claros */
        { id: "aeroportos", type: "symbol", source: "aeros",
          layout: { "symbol-sort-key": ["-", 0, ["get", "p"]], "icon-image": "aviao", "icon-allow-overlap": true, "icon-ignore-placement": true,
            "icon-size": ["interpolate", ["linear"], ["zoom"],
              3, ["interpolate", ["linear"], ["sqrt", ["get", "p"]], 0, 0.36, 300, 0.5, 1500, 0.78, 6600, 1.3],
              6, ["interpolate", ["linear"], ["sqrt", ["get", "p"]], 0, 0.5, 300, 0.7, 1500, 1.1, 6600, 1.9],
              9, ["interpolate", ["linear"], ["sqrt", ["get", "p"]], 0, 0.7, 300, 0.95, 1500, 1.45, 6600, 2.5]] },
          paint: { "icon-opacity": ["case", ["<", ["get", "p"], 1000], 0.55, 1] } },
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
        /* capitais dos países vizinhos: anel claro com um ponto no meio, nome no tom dos países */
        { id: "capviz", type: "circle", source: "capviz",
          paint: { "circle-radius": 3.6, "circle-color": "rgba(10,8,5,.55)", "circle-stroke-color": "#e8e1cc", "circle-stroke-width": 1.3 } },
        { id: "capviz-ponto", type: "circle", source: "capviz", paint: { "circle-radius": 1.3, "circle-color": "#e8e1cc" } },
        { id: "capviz-rotulo", type: "symbol", source: "capviz",
          layout: { "text-field": ["get", "n"], "text-font": fonte(REG), "text-size": 11, "text-anchor": "left", "text-offset": [0.75, 0], "text-optional": true },
          paint: { "text-color": "rgba(236,232,220,.8)", ...halo } },
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
    if (e.id === "escudo" && !map.hasImage("escudo")) {
      /* indústria de defesa: escudo claro com borda escura */
      const n = 32, c = document.createElement("canvas"); c.width = c.height = n;
      const x = c.getContext("2d");
      const escudo = (m) => { x.beginPath(); x.moveTo(5 + m, 3 + m); x.lineTo(27 - m, 3 + m); x.lineTo(27 - m, 15);
        x.quadraticCurveTo(26 - m, 25 - m, 16, 30 - m * 1.4); x.quadraticCurveTo(6 + m, 25 - m, 5 + m, 15); x.closePath(); };
      escudo(0); x.fillStyle = "#0b1622"; x.fill(); escudo(2.6); x.fillStyle = cor("--def"); x.fill();
      map.addImage("escudo", x.getImageData(0, 0, n, n), { pixelRatio: 2 });
      return;
    }
    if (e.id === "boi" && !map.hasImage("boi")) {
      /* boi em medalhão escuro com aro dourado (64 px em dobro: 32 px no tamanho 1) */
      const n = 64, c = document.createElement("canvas"); c.width = c.height = n;
      const x = c.getContext("2d");
      x.beginPath(); x.arc(32, 32, 29.5, 0, 2 * Math.PI); x.fillStyle = "rgba(16,10,4,.88)"; x.fill();
      x.lineWidth = 3; x.strokeStyle = "#e6b450"; x.stroke();
      x.translate(9.6, 7.7); x.scale(1.87, 1.87); x.fillStyle = "#f3dfae"; x.fill(new Path2D(BOI));
      map.addImage("boi", x.getImageData(0, 0, n, n), { pixelRatio: 2 });
      return;
    }
    if (IMG_ICO[e.id] && !map.hasImage(e.id)) {
      /* medalhão das outras camadas de pontos (icones.js) */
      const [i, v] = IMG_ICO[e.id];
      map.addImage(e.id, medalhaoCanvas(ICONES[i], cor(v)), { pixelRatio: 2 });
      return;
    }
    if (e.id.startsWith("lav-") && !map.hasImage(e.id)) {
      /* lavoura em medalhão escuro com aro e desenho na cor da lavoura (icones.js) */
      const g = e.id.slice(4), cv = cor("--lav-" + g) || cor("--lav-outras");
      map.addImage(e.id, medalhaoCanvas(ICONES[g] || ICONES.outras, cv), { pixelRatio: 2 });
      return;
    }
    if (e.id === "aviao" && !map.hasImage("aviao")) {
      /* aviãozinho com sombra e brilho, para parecer em relevo (desenho de 24 px em dobro, nítido em tela fina) */
      const n = 54, c = document.createElement("canvas"); c.width = c.height = n;
      const x = c.getContext("2d"), P = new Path2D(AVIAO);
      x.translate(2, 2); x.scale(2, 2);
      x.save(); x.translate(0.9, 1.3); x.fillStyle = "rgba(0,0,0,.55)"; x.fill(P); x.restore();
      const g = x.createLinearGradient(5, 3, 19, 22); g.addColorStop(0, "#f2f5ff"); g.addColorStop(1, "#7d95df");
      x.lineJoin = "round"; x.lineWidth = 1.5; x.strokeStyle = "#0b1626"; x.stroke(P); x.fillStyle = g; x.fill(P);
      map.addImage("aviao", x.getImageData(0, 0, n, n), { pixelRatio: 2 });
      return;
    }
    if (e.id === "se" && !map.hasImage("se")) {
      /* subestação: losango com borda escura */
      const n = 24, c = document.createElement("canvas"); c.width = c.height = n;
      const x = c.getContext("2d");
      const losango = r => { x.beginPath(); x.moveTo(12, 12 - r); x.lineTo(12 + r, 12); x.lineTo(12, 12 + r); x.lineTo(12 - r, 12); x.closePath(); };
      losango(10); x.fillStyle = "#14082a"; x.fill(); losango(7.5); x.fillStyle = cor("--lt"); x.fill();
      map.addImage("se", x.getImageData(0, 0, n, n), { pixelRatio: 2 });
      return;
    }
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

  /* Alcântara: foguete em pé, com a base no ponto, vapor e chama (marcador HTML) */
  let mkCla = null;
  if (CLA) {
    const el = document.createElement("div"); el.className = "mk-foguete"; el.title = CLA.nome;
    el.innerHTML = '<i class="vapor v1"></i><i class="vapor v2"></i><i class="vapor v3"></i><i class="vapor v4"></i>' +
      `<svg viewBox="0 0 24 34" aria-hidden="true">${FOGUETE}</svg>`;
    mkCla = new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(CLA.ponto);
  }

  const G = { zee: ["zee-fill", "zee-line", "zee-rotulo", "ilhas-ponto", "ilhas-rotulo"], mt: ["mt-fill", "mt-line", "mt-base"], zc: ["zc-fill", "zc-line"],
    pce: ["pce-fill-rec", "pce-fill-ana", "pce-line-rec", "pce-line-ana", "pce-rotulo"], rod: ["rodovias", "rodovias-terra", "rodovias-rotulo", "rodovias-borda"], rodest: ["rodovias-est"],
    oil: ["pocos", "pocos-ico"], uep: ["plataformas"], campos: ["campos-fill", "campos-line"], presal: ["presal-line", "presal-rotulo"], boi: ["boi", "boi-geral"], lav: ["lav", "lav-geral"], usinas: ["usinas", "usinas-ico"], dutos: ["dutos"], refin: ["refin"], se: ["se"], lt: ["lt"], celm: ["celm", "celm-ico"], g5: ["g5", "g5-ico"], empdef: ["empdef"], pedagio: ["pedagio", "pedagio-ico"],
    rail: ["ferrovias", "ferrovias-obra", "ferrovias-borda", "ferrovias-obra-borda"], ports: ["portos"], air: ["aeroportos"],
    fronttipo: ["front-borda", "front-linha"], passa: ["passa-estrada-borda", "passa-estrada", "passa-ico"], vmda: ["vmda-borda", "vmda"], dup: ["dup", "dup-obra"] };

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
    if (RECUO.ativo) return;                       /* com a página rolada, o globo afastado pode ficar menor que o limite */
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
  /* painel em duas abas, "Mapa" (pinturas e camadas) e "Ficha" (o Brasil ou o estado escolhido) */
  const abas = document.createElement("div"); abas.className = "abas"; abas.setAttribute("role", "tablist"); abas.setAttribute("aria-label", "Painel");
  abas.innerHTML = `<button role="tab" data-aba="mapa">Mapa</button><button role="tab" data-aba="ficha">Ficha · Brasil</button>`;
  conteudo.before(abas);
  abas.querySelectorAll("button").forEach(b => b.onclick = () => aba(b.dataset.aba));
  aba("mapa");
  if (TESTE) document.querySelector(".brand").insertAdjacentHTML("beforeend",
    `<a class="selo-teste" href="${location.pathname}" title="Versão de teste. Clique para abrir o site normal, sem as mudanças">Teste</a>`);
  /* selo com a data da última atualização dos robôs (icones.js; diretriz God's Eye View) */
  seloDados(D);
  function aba(nome) {
    dock.dataset.aba = nome;
    abas.querySelectorAll("button").forEach(b => b.setAttribute("aria-selected", b.dataset.aba === nome));
    dock.scrollTop = 0;
  }

  /* contorno detalhado do IBGE (desvio máximo ≈ 1,7 km, contra ≈ 5 km do contorno leve da abertura):
     baixado na primeira vez que alguém aproxima o mapa ou escolhe um estado */
  let detalhe = "nao";
  async function detalhar() {
    if (detalhe !== "nao") return;
    detalhe = "baixando";
    const d = await getJSON(D + "geo/estados_detalhe.json");
    if (!d) { detalhe = "nao"; return; }
    const aplicar = () => {
      map.getSource("estados").setData(d); detalhe = "ok"; geoAtual = d;
      if (map.getSource("brasil")) map.getSource("brasil").setData(contornoBrasil(d));
      estados.features.forEach(f => { const u = f.properties.sigla; map.setFeatureState({ source: "estados", id: u }, { fade: !!sel && u !== sel, hover: u === hover }); });
    };
    map.getSource("estados") ? aplicar() : map.once("load", aplicar);
  }
  map.on("zoomend", () => { if (map.getZoom() >= 5) detalhar(); });

  function selecionar(s) {
    if (sel) { map.setFeatureState({ source: "estados", id: sel }, { sel: false }); }
    sel = (sel === s) ? null : s;
    if (sel) { detalhar(); aba("ficha"); }
    /* escolher um estado com a pintura Rebanho (ou uma das lavouras) liga os ícones dos municípios dele */
    if (sel) camadasDa(paint).filter(l => AUTO_ESTADO.has(l.id)).forEach(l => { if (!l.on) { l.on = true; l.dono = paint; } });
    estados.features.forEach(f => map.setFeatureState({ source: "estados", id: f.properties.sigla }, { fade: !!sel && f.properties.sigla !== sel }));
    for (const id of ["estado-sel", "sel-halo", "sel-sombra", "sel-fill"]) map.setFilter(id, ["==", ["get", "sigla"], sel || ""]);
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
    if (hover !== s) { if (hover) map.setFeatureState({ source: "estados", id: hover }, { hover: false }); hover = s; map.setFeatureState({ source: "estados", id: s }, { hover: true }); realceContorno(); }
  });
  map.on("mouseleave", "estados-fill", () => { map.getCanvas().style.cursor = ""; if (hover) map.setFeatureState({ source: "estados", id: hover }, { hover: false }); hover = null; realceContorno(); });
  /* o estado sob o mouse ganha o contorno dourado com a luz correndo (sem movimento para quem pede menos animação) */
  let geoAtual = estados, animHover = 0;
  function realceContorno() {
    const src = map.getSource("contorno-hover");
    if (!src) return;
    cancelAnimationFrame(animHover);
    const f = hover && geoAtual.features.find(x => x.properties.sigla === hover);
    if (!f) { src.setData(fc([])); return; }
    const g = f.geometry, aneis = (g.type === "Polygon" ? [g.coordinates] : g.coordinates).flatMap(pl => pl);
    src.setData(fc(aneis.map(r => ({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: r } }))));
    map.setLayoutProperty("hover-tracos", "visibility", reduce ? "none" : "visible");
    if (reduce) return;
    const dono = hover; let ult = -1;
    const passo = t => {
      if (hover !== dono) return;
      const k = Math.floor(t / 50) % TRACOS.length;
      if (k !== ult) { ult = k; map.setPaintProperty("hover-tracos", "line-dasharray", TRACOS[k]); }
      animHover = requestAnimationFrame(passo);
    };
    animHover = requestAnimationFrame(passo);
  }
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
    /* indústria de defesa: de longe o clique abre o estado (como no gado e no celular); a partir do zoom 4,5, a lista do município */
    const df = vis("empdef") && DATA.empdef && map.getZoom() >= 4.5 ? map.queryRenderedFeatures(perto, { layers: ["empdef"] }) : [];
    if (df.length) {
      const f = df.reduce((a, b) => b.properties.n < a.properties.n ? b : a), M = DATA.empdef.meta;   /* o menor fica por cima */
      const m = indiceDef()[f.properties.c];
      if (m) {
        const es = m[5], eed = es.filter(x => x[1] === "EED").length, ed = es.length - eed;
        const partes = [eed ? `${fmt(eed)} ${eed > 1 ? "estratégicas" : "estratégica"} de defesa (EED)` : "", ed ? `${fmt(ed)} de defesa (ED)` : ""].filter(Boolean).join(" e ");
        new maplibregl.Popup({ closeButton: false, offset: 10, maxWidth: "340px" }).setLngLat(f.geometry.coordinates)
          .setHTML(`<b>${esc(m[2])} · ${esc(m[3])}</b><br>${fmt(es.length)} ${es.length > 1 ? "empresas credenciadas" : "empresa credenciada"} pelo Ministério da Defesa: ${partes}
            <div class="pop-lista">${es.map(x => `${esc(x[0])} <span>${x[1]}</span>`).join("<br>")}</div>
            <span class="pop-fonte">${esc(M.fonte)}, ${esc(M.referencia)}. O ponto fica na sede do município, não no endereço da empresa.</span>`).addTo(map);
        return;
      }
    }
    /* versão de teste: passagens de fronteira e a fronteira por tipo */
    const pa = vis("passa-ico") ? map.queryRenderedFeatures(perto, { layers: ["passa-ico"] }) : [];
    if (pa.length && DATA.passa) {
      const p = pa[0].properties, M = DATA.passa.meta, FC = M.fontes_curtas || {};
      const tipo = p.t === "rio" || p.t === "lagoa" ? (p.rio ? esc(p.rio) : "em " + p.t) : p.t === "mata" ? "fronteira seca, na mata" : "fronteira seca";
      new maplibregl.Popup({ closeButton: false, offset: 12, maxWidth: "320px" }).setLngLat(pa[0].geometry.coordinates)
        .setHTML(`<b>Passagem de fronteira</b><br>${esc(p.br)} ↔ ${esc(p.viz)}${p.lig ? `<br>Ligação: ${esc(p.lig)}` : `<br>A fronteira ali: ${tipo}`}
          ${p.rod ? `<br>Rodovia que chega à fronteira: ${esc(p.rod)}` : ""}${p.nota ? `<br>${esc(p.nota)}` : ""}<br>Cidade gêmea (Portaria MDR nº 2.507/2021)
          <br><span class="pop-fonte">IBGE (cidades gêmeas e BC250); cidade do outro lado${p.lig ? " e ligação" : ""}: ${String(p.f).split(",").map(k => esc(FC[k] || k)).join("; ")}${p.estradas > 0 ? "; estrada do outro lado: Natural Earth, desenho aproximado" : ""}</span>`).addTo(map);
      return;
    }
    const ft = vis("front-linha") && map.getZoom() >= 4.5 ? map.queryRenderedFeatures([[px - 4, py - 4], [px + 4, py + 4]], { layers: ["front-linha"] }) : [];
    if (ft.length && DATA.fronttipo) {
      const p = ft[0].properties, M = DATA.fronttipo.meta, k = p.p, d = M.km_desenho[k] || {};
      const tot = Object.values(d).reduce((a, b) => a + b, 0) || 1, pc = v => Math.round((v || 0) / tot * 100) + "%";
      const tipo = p.t === "rio" ? "em rio" : p.t === "lagoa" ? "em lagoa" : p.t === "mata" ? "seca, na mata" : "seca";
      new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "320px" }).setLngLat(e.lngLat)
        .setHTML(`<b>Fronteira com ${COM_PAIS[k] || esc(M.paises[k])}</b><br>${p.n ? esc(p.n) + " · " : ""}fronteira ${tipo}
          <br>Extensão oficial: ${fmt(M.km_oficial[k])} km. No desenho, ${pc((d.rio || 0) + (d.lagoa || 0))} em rios e lagoas, ${pc(d.seca)} seca e ${pc(d.mata)} seca na mata.
          <br><span class="pop-fonte">Extensão: ${esc(M.km_oficial_fonte)}. Tipo: classificação do projeto com a BC250 e a cobertura da terra do IBGE (2020), aproximada.</span>`).addTo(map);
      return;
    }
    /* refinarias e portos são medalhões, maiores que os círculos de antes: de longe, o clique abre o estado */
    const longe = map.getZoom() < 4;
    const ri = vis("refin") && !longe ? map.queryRenderedFeatures(perto, { layers: ["refin"] }) : [];
    if (ri.length) {
      const p = ri[0].properties;
      const corpo = p.k === "refinaria"
        ? `<b>${esc(p.n)}${p.s ? " (" + esc(p.s) + ")" : ""}</b><br>Refinaria · ${esc(p.m)} · ${esc(p.uf)}${p.bbl ? `<br>Capacidade: ${fmt(+p.bbl)} barris de petróleo por dia` : ""}${p.e ? "<br>" + esc(p.e) : ""}`
        : p.k === "gnl"
          ? `<b>${esc(p.n)}</b><br>Terminal de GNL (o gás chega líquido, de navio, e volta a ser gás) · ${esc(p.m)} · ${esc(p.uf)}${p.mi_m3 ? `<br>Capacidade: ${fmt(+p.mi_m3)} milhões de m³ de gás por dia` : ""}${p.e ? "<br>" + esc(p.e) : ""}`
          : `<b>${esc(p.n)}</b><br>Unidade de processamento de gás natural${p.tipo ? " (" + esc(p.tipo) + ")" : ""} · ${esc(p.m)} · ${esc(p.uf)}`;
      new maplibregl.Popup({ closeButton: false, offset: 10, maxWidth: "300px" }).setLngLat(ri[0].geometry.coordinates)
        .setHTML(`${corpo}<br><span class="pop-fonte">ANP, servidor de mapas</span>`).addTo(map);
      return;
    }
    const su = vis("se") && map.getZoom() >= 5 ? map.queryRenderedFeatures(perto, { layers: ["se"] }) : [];
    if (su.length) {
      const p = su.reduce((a, b) => b.properties.kv > a.properties.kv ? b : a).properties;
      new maplibregl.Popup({ closeButton: false, offset: 8, maxWidth: "300px" }).setLngLat(su[0].geometry.coordinates)
        .setHTML(`<b>${esc(p.n)}</b><br>Subestação · ${esc(p.t)} kV${p.ano ? " · em operação desde " + p.ano : ""}${p.c ? "<br>" + esc(p.c) : ""}
          <br><span class="pop-fonte">EPE, Webmap (sistema elétrico existente)</span>`).addTo(map);
      return;
    }
    const po = vis("pocos") ? map.queryRenderedFeatures(perto, { layers: ["pocos", "pocos-ico"].filter(l => map.getLayer(l)) }) : [];
    if (po.length) {
      const f = po.reduce((a, b) => b.properties.b > a.properties.b ? b : a), p = f.properties, M = DATA.oil.meta;
      new maplibregl.Popup({ closeButton: false, offset: 8 }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>Poço ${esc(p.n)}</b><br>Campo ${esc(p.c)} · ${p.a === "M" ? "mar" : "terra"}${p.u ? " · " + esc(p.u) : ""}
          <br>Petróleo: ${fmt(Math.round(p.o))} barris/dia<br>Gás: ${fmt1(p.g)} mil m³/dia<br>Total: ${fmt(Math.round(p.b))} boe/dia
          <br><span class="pop-fonte">ANP, média de ${esc(M.referencia)}</span>`).addTo(map);
      return;
    }
    const us = vis("usinas") && map.getZoom() >= 4 ? map.queryRenderedFeatures(perto, { layers: ["usinas", "usinas-ico"].filter(l => map.getLayer(l)) }) : [];
    if (us.length) {
      const f = us.reduce((a, b) => b.properties.kw > a.properties.kw ? b : a), p = f.properties, M = DATA.usinas.meta;
      const hidro = ["uhe", "pch", "cgh"].includes(p.t), obs = (M.observacoes || {})[p.n];
      new maplibregl.Popup({ closeButton: false, offset: 8, maxWidth: "300px" }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${esc(p.n)}</b><br>${esc(M.tipos[p.t])} · ${fmt1(p.kw / 1000)} MW${p.uf ? " · " + esc(p.uf) : ""}${p.a ? "<br>Em operação desde " + p.a : ""}
          ${p.x ? "<br>" + (hidro ? "Bacia: " : "Combustível: ") + esc(p.x) : ""}${p.d ? "<br>" + esc(p.d) : ""}${obs ? "<br><i>" + esc(obs) + "</i>" : ""}
          <br><span class="pop-fonte">${esc(M.fonte)}; ${esc(M.referencia)}</span>`).addTo(map);
      return;
    }
    /* de longe os pontos do gado cobrem os estados: o clique abre o estado; a partir do zoom 4,5 abre o município */
    const bo = vis("boi") && map.getZoom() >= 4.5 ? map.queryRenderedFeatures(perto, { layers: ["boi", "boi-geral"].filter(l => map.getLayer(l)) }) : [];
    if (bo.length) {
      const f = bo.reduce((a, b) => b.properties.b > a.properties.b ? b : a), p = f.properties, M = DATA.boi.meta;
      new maplibregl.Popup({ closeButton: false, offset: 8 }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${esc(p.n)} · ${esc(p.u)}</b><br>${fmt(p.b)} cabeças de gado bovino
          <br><span class="pop-fonte">IBGE, Pesquisa da Pecuária Municipal ${esc(M.referencia)}. O ponto fica na sede do município.</span>`).addTo(map);
      return;
    }
    const la = vis("lav") && map.getZoom() >= 4.5 ? map.queryRenderedFeatures(perto, { layers: ["lav", "lav-geral"].filter(l => map.getLayer(l)) }) : [];
    if (la.length) {
      const f = la.reduce((a, b) => b.properties.v > a.properties.v ? b : a), p = f.properties, M = DATA.lav.meta;
      new maplibregl.Popup({ closeButton: false, offset: 8, maxWidth: "300px" }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${esc(p.n)} · ${esc(p.u)}</b><br>Principal lavoura: ${esc(p.p)} (${reais(p.pv)}, ${fmt(Math.round(p.pv / p.v * 100))}% do valor)
          <br>Todas as lavouras: ${reais(p.v)}<br><span class="pop-fonte">IBGE, Produção Agrícola Municipal ${esc(M.referencia)}. O ponto fica na sede do município.</span>`).addTo(map);
      return;
    }
    /* celular: de perto (zoom 4,5), como o gado; a janelinha junta o sinal e o 5G do município, se os dois arquivos já chegaram */
    const ce = map.getZoom() >= 4.5 ? map.queryRenderedFeatures(perto, { layers: ["celm", "g5", "celm-ico", "g5-ico"].filter(vis) }) : [];
    if (ce.length) {
      const p = ce[0].properties, m = indice("celm")[p.c], g = indice("g5")[p.c];
      const lin = [];
      if (m) lin.push(`Sinal 4G ou 5G: ${fmt1(m[2])}% da população (estimativa da Anatel, IBC ${esc(DATA.celm.meta.referencia)})`);
      if (DATA.g5) lin.push(g ? `5G: ${esc(g[4])} (${esc(DATA.g5.meta.referencia)})` : `Sem 5G registrado em ${esc(DATA.g5.meta.referencia)}`);
      new maplibregl.Popup({ closeButton: false, offset: 8, maxWidth: "300px" }).setLngLat(ce[0].geometry.coordinates)
        .setHTML(`<b>${esc(p.n)} · ${esc(p.u)}</b><br>${lin.join("<br>")}<br><span class="pop-fonte">Anatel, dados abertos. O ponto fica na sede do município.</span>`).addTo(map);
      return;
    }
    /* pedágios federais: de perto (zoom 4,5), como os outros pontos por município */
    const pd = vis("pedagio") && DATA.pedagio && map.getZoom() >= 4.5 ? map.queryRenderedFeatures(perto, { layers: ["pedagio", "pedagio-ico"].filter(l => map.getLayer(l)) }) : [];
    if (pd.length) {
      const f = pd.reduce((a, b) => b.properties.v < a.properties.v ? b : a), M = DATA.pedagio.meta, p = DATA.pedagio.pracas[f.properties.i];
      const num = p[12] === 1 ? `Sem volume informado à ANTT em ${esc(M.referencia)}.`
        : p[12] === 2 ? "O volume informado à ANTT não fecha (mais de 40% aparece como motos); por isso o número não é mostrado."
        : `≈ ${fmt(p[8])} veículos por dia · ${fmt1(p[9])}% caminhões e ônibus<br>Média de ${p[10]} ${p[10] > 1 ? "meses" : "mês"} (${esc(p[11])}); conta os sentidos em que há cobrança.`;
      new maplibregl.Popup({ closeButton: false, offset: 8, maxWidth: "300px" }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${p[13] ? "Validador do pedágio" : "Praça de pedágio"} ${esc(p[2])}</b><br>${esc(p[3])} · ${esc(p[4])}, km ${esc(p[5])}<br>${esc(p[6])}${p[7] ? " (" + esc(p[7]) + ")" : ""}
          <br>${num}<br><span class="pop-fonte">ANTT, dados abertos (números informados pelas concessionárias)</span>`).addTo(map);
      return;
    }
    const cv = map.getLayer("capviz") ? map.queryRenderedFeatures([[px - 4, py - 4], [px + 4, py + 4]], { layers: ["capviz"] }) : [];
    if (cv.length) {
      const p = cv[0].properties;
      new maplibregl.Popup({ closeButton: false, offset: 10, maxWidth: "280px" }).setLngLat(cv[0].geometry.coordinates)
        .setHTML(`<b>${esc(p.n)}</b><br>${esc(p.d)}<br><span class="pop-fonte">Natural Earth (base aberta, domínio público)</span>`).addTo(map);
      return;
    }
    const pts = map.queryRenderedFeatures(e.point, { layers: ["portos", "aeroportos", "capitais"].filter(l => map.getLayoutProperty(l, "visibility") !== "none" && !(longe && l === "portos")) });
    const ae = pts.filter(f => f.layer.id === "aeroportos");
    if (ae.length && DATA.air && DATA.air.aeroportos) {
      const f = ae.reduce((a, b) => b.properties.p < a.properties.p ? b : a), a = DATA.air.aeroportos[f.properties.i], M = DATA.air.meta;
      new maplibregl.Popup({ closeButton: false, offset: 10, maxWidth: "300px" }).setLngLat(f.geometry.coordinates)
        .setHTML(`<b>${esc(a[3])} (${esc(a[2])})</b><br>Aeródromo público · ${esc(a[4])} (${esc(a[5])})
          <br>${a[6] >= 1000 ? `${passageiros(a[6])} em 12 meses (${esc(M.referencia)}), embarcados e desembarcados${a[7] >= 1 ? `<br>Carga e correio: ${fmt(a[7])} t` : ""}` : `Sem voos de passageiros nos dados estatísticos da ANAC (${esc(M.referencia)})`}
          <br><span class="pop-fonte">ANAC, dados abertos</span>`).addTo(map);
      return;
    }
    if (pts.length) {
      const f = pts[0], tipo = f.layer.id === "portos" ? "Porto" : f.layer.id === "aeroportos" ? "Aeroporto" : "Capital";
      const extra = f.layer.id === "portos" ? (f.properties.org == 1 ? "<br>Porto organizado" : "") + (f.properties.obra == 1 ? "<br>Em obras" : "") : "";
      new maplibregl.Popup({ closeButton: false, offset: 10 }).setLngLat(f.geometry.coordinates).setHTML(`<b>${tipo}</b><br>${esc(f.properties.n)}${extra}`).addTo(map);
      return;
    }
    /* versão de teste: fluxo (DNIT, VMDa) e pista dupla (SNV), de perto */
    const vm = vis("vmda") && map.getZoom() >= 5 ? map.queryRenderedFeatures([[px - 4, py - 4], [px + 4, py + 4]], { layers: ["vmda"] }) : [];
    if (vm.length && DATA.vmda) {
      const p = vm.reduce((a, b) => b.properties.v > a.properties.v ? b : a).properties, M = DATA.vmda.meta;
      new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "300px" }).setLngLat(e.lngLat)
        .setHTML(`<b>${p.br ? "BR-" + esc(p.br) : "Rodovia federal"}${p.u ? " (" + esc(p.u) + ")" : ""}</b><br>≈ ${fmt(p.v)} veículos por dia, nos dois sentidos
          ${p.p >= 0 ? `<br>Ônibus e caminhões: ${p.p}%` : ""}${p.r ? "<br>Trecho com contagem usada como referência" : ""}
          <br><span class="pop-fonte">${esc(M.fonte)}; ${esc(M.nota)}</span>`).addTo(map);
      return;
    }
    const du = map.getZoom() >= 6 ? map.queryRenderedFeatures([[px - 4, py - 4], [px + 4, py + 4]], { layers: ["dup", "dup-obra"].filter(vis) }) : [];
    if (du.length && DATA.dup) {
      const p = du[0].properties;
      new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "280px" }).setLngLat(e.lngLat)
        .setHTML(`<b>${esc(p.br)}${p.u ? " (" + esc(p.u) + ")" : ""}</b><br>${p.d == 1 ? "Pista dupla" : "Em obra de duplicação"}
          <br><span class="pop-fonte">${esc(DATA.dup.meta.fonte)}</span>`).addTo(map);
      return;
    }
    /* rodovias e ferrovias: de perto (zoom 6), para não atrapalhar o clique nos estados */
    const vias = map.getZoom() >= 6 ? map.queryRenderedFeatures([[px - 4, py - 4], [px + 4, py + 4]],
      { layers: ["lt", "dutos", "ferrovias", "ferrovias-obra", "rodovias", "rodovias-terra", "rodovias-est"].filter(vis) }) : [];
    if (vias.length) {
      const f = vias[0], p = f.properties, trem = f.layer.id.startsWith("ferrovias");
      if (f.layer.id === "dutos") {
        const TIPO = { transporte: "de transporte", transferencia: "de transferência", escoamento: "de escoamento da produção" };
        new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "300px" }).setLngLat(e.lngLat)
          .setHTML(`<b>${p.f === "gas" ? "Gasoduto" : "Oleoduto"} ${TIPO[p.t] || ""}</b>${p.n ? "<br>" + esc(p.n) : ""}${p.tr ? "<br>" + esc(p.tr) : ""}
            ${p.de || p.para ? `<br>${p.de ? "De " + esc(p.de) : ""}${p.para ? " para " + esc(p.para) : ""}` : ""}${p.fl && p.f !== "gas" ? "<br>Leva: " + esc(p.fl) : ""}
            ${p.pol || p.km ? `<br>${p.pol ? fmt1(+p.pol) + " polegadas" : ""}${p.pol && p.km ? " · " : ""}${p.km ? fmt1(+p.km) + " km" : ""}` : ""}${p.op ? "<br>" + esc(p.op) : ""}
            <br><span class="pop-fonte">ANP, servidor de mapas</span>`).addTo(map);
        return;
      }
      if (f.layer.id === "lt") {
        new maplibregl.Popup({ closeButton: false, offset: 6, maxWidth: "300px" }).setLngLat(e.lngLat)
          .setHTML(`<b>${esc(p.n) || "Linha de transmissão"}</b><br>${p.kv} kV${p.ano ? " · em operação desde " + p.ano : ""}${p.c ? "<br>" + esc(p.c) : ""}
            <br><span class="pop-fonte">EPE, Webmap (sistema elétrico existente)</span>`).addTo(map);
        return;
      }
      const html = trem
        ? `<b>Ferrovia${p.obra == 1 ? " em obras" : ""}</b><br>${esc(p.op)}${p.b ? "<br>Bitola " + esc(p.b).toLowerCase() : ""}${p.si == 1 ? "<br>A base não informa se está em operação" : ""}`
        : f.layer.id === "rodovias-est"
          ? `<b>${esc(p.s)}</b><br>Rodovia estadual pavimentada`
          : p.e == 1
            ? `<b>${esc(p.s)}</b><br>Trecho com sigla BR administrado pelo estado (rodovia estadual coincidente ou trecho delegado), ${p.p == 1 ? "pavimentado" : "sem pavimento"}`
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
    lav: "M12 21V9M12 9c0-3.5 2.5-6 6-6 0 3.5-2.5 6-6 6zM12 14c0-3-2-5-5-5 0 3 2 5 5 5zM8 21h8",
    "p-rod": "M8 21L10 3M16 21L14 3M12 6v2M12 11v2M12 16v2",
    rod: "M8 21L10 3M16 21L14 3M12 6v2M12 11v2M12 16v2",
    rodest: "M8 21L10 3M16 21L14 3M12 8v1M12 14v1",
    "p-ene": "M13 2L5 14h6l-1 8 8-12h-6z",
    usinas: "M13 2L5 14h6l-1 8 8-12h-6z",
    lt: "M12 2l-5 20M12 2l5 20M8 9h8M7 14h10M5 20h14",
    dutos: "M2 9h13a4 4 0 014 4v9M2 14h12M15 22h7M19 13h3",
    se: "M12 2l9 10-9 10-9-10zM12 7v10M8 12h8",
    refin: "M3 21V12l5 3v-3l5 3V8h3V4h3v17zM3 21h18",
    celm: "M12 10v11M8 21h8M9 7a4 4 0 016 0M6 4a8 8 0 0112 0",
    g5: "M12 10v11M8 21h8M9 7a4 4 0 016 0M6 4a8 8 0 0112 0",
    empdef: "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z",
    pedagio: "M5 21V8h3v13M8 11h12v3H8zM4 21h5"
  };
  const quando = id => { const m = DATA[id] && DATA[id].meta; return m && m.atualizado_em ? ` · ${m.referencia ? "ref. " + esc(m.referencia) + ", " : ""}atualizado em ${m.atualizado_em}` : ""; };
  const icon = id => ICON[id] ? `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICON[id]}"/></svg>` : `<span class="ico"></span>`;
  const mins = document.getElementById("mins");
  mins.insertAdjacentHTML("beforeend", [["todos", "Todos"], ...Object.entries(F.ministerios)]
    .map(([k, v]) => `<button class="tab" data-m="${k}" aria-pressed="${k === "todos"}">${v}</button>`).join(""));
  mins.querySelectorAll(".tab").forEach(b => b.onclick = () => {
    minF = b.dataset.m; guardadas = null;
    mins.querySelectorAll(".tab").forEach(x => x.setAttribute("aria-pressed", x === b));
    /* o filtro liga as camadas do ministério, menos as marcadas com "no_filtro": false (ficam na lista, desligadas) */
    LAYERS.forEach(l => { if (l.nivel !== "pendente") l.on = padrao(l); });
    proxima = "ligar";
    const p = PAINT.find(p => p.ministerio === minF && p.ok);
    paint = minF === "todos" ? "pop" : (p ? p.id : "none");
    const lz = LUZ.find(l => l.id === luz);
    if (lz && minF !== "todos" && lz.ministerio !== minF) definirLuz("off"); else render();
  });
  function controls() {
    /* pinturas marcadas "so_no_ministerio" (as lavouras) só aparecem com o filtro do ministério, para não lotar "Todos" */
    const pv = PAINT.filter(p => p.id === "none" || (minF === "todos" ? !p.so_no_ministerio : p.ministerio === minF));
    /* bolinha "camada ligada" no botão da pintura dona da camada, mesmo com outra pintura escolhida (pedido do Edu em
       25/10/2026). Quando várias pinturas têm a mesma camada (as lavouras), a bolinha fica na que ligou a camada; se essa
       não está na lista, na pintura escolhida ou na primeira da lista */
    const dono = l => { const ps = pv.filter(p => camadasDa(p.id).includes(l)).map(p => p.id);
      return ps.includes(l.dono) ? l.dono : ps.includes(paint) ? paint : ps[0]; };
    const comCamada = p => camadasDa(p.id).some(l => l.on && dono(l) === p.id);
    document.getElementById("paint").innerHTML = pv.map(p =>
      `<button class="chip" data-p="${p.id}" aria-pressed="${paint === p.id}"${comCamada(p) ? ' data-cam="1"' : ""} ${p.id !== "none" && !p.ok ? "disabled title=\"Em apuração\"" : ""}>${p.nome}</button>`).join("");
    /* dica: clicar de novo na pintura escolhida liga ou desliga as camadas dela */
    let dica = document.getElementById("paint-dica");
    if (!dica) { dica = document.createElement("p"); dica.id = "paint-dica"; dica.className = "note dica"; document.getElementById("paint").after(dica); }
    const Pa = PAINT.find(p => p.id === paint), cs = camadasDa(paint);
    dica.hidden = !cs.length;
    dica.textContent = cs.length ? `Clique de novo em “${Pa.nome}” para ${cs.every(l => l.on) ? "desligar" : "ligar também"} ${cs.length > 1 ? "as camadas" : "a camada"} ${cs.map(l => "“" + l.nome + "”").join(" e ")}.` : "";
    if (cs.some(l => NO_ESTADO.has(l.id))) dica.textContent += " Escolha um estado no mapa para ver os ícones dentro dele.";
    document.querySelectorAll("#paint .chip:not([disabled])").forEach(b => b.onclick = () => {
      /* 1º clique pinta os estados; os seguintes, na mesma pintura, ligam e desligam as camadas dela */
      const id = b.dataset.p, cs = camadasDa(id);
      if (paint !== id) paint = id;
      else if (cs.length) { const tudo = cs.every(l => l.on); cs.forEach(l => { l.on = !tudo; l.dono = id; }); }
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
      const explica = TESTE && L.id === "pop" ? "O brilho mostra quantas pessoas moram em cada pedaço do país, em quadrados de 1 km, inclusive na zona rural; os pontos são os municípios (clique num deles, de perto, para ver a população)." : L.explica;
      info.innerHTML = `<h2 style="margin-top:14px">Luzes à noite</h2><div class="luz-info"><p class="note"><b>${L.titulo}.</b> ${explica}</p>
        <div>${dd ? `${pill(dd.nivel)} <span class="note">${dd.fonte} · atualizado em ${dd.atualizado_em}. Posição: ${dd.posicao}.</span>`
             : `${pill(L.nivel)} <span class="note">${L.fonte}.</span>`}</div>
        ${TESTE && L.id === "pop" ? `<div>${pill("manual")} <span class="note">Brilho: IBGE, Grade Estatística do Censo Demográfico 2022, quadrados de 1 km (versão de 02/10/2025).</span></div>` : ""}
        <p class="note">Com as luzes acesas, os estados ficam sem cor; as rodovias e ferrovias se apagam, para não se confundirem com as luzes, e a Zona Econômica Exclusiva também, para deixar o mapa mais limpo (dá para religar em Camadas). Para apagar, clique de novo no botão da luz, no alto do mapa, ou escolha uma pintura acima.</p></div>`;
    }
    const lv = LAYERS.filter(l => minF === "todos" || l.ministerio === minF);
    document.getElementById("layers").innerHTML = lv.length ? lv.map(l => `
      <label class="layer ${l.nivel === "pendente" ? "pend" : ""}${l.on ? " on" : ""}" style="--cor:var(${l.cor || "--accent"})">
        <input type="checkbox" id="ly-${l.id}" ${l.on ? "checked" : ""} ${l.nivel === "pendente" ? "disabled" : ""}>${icon(l.id)}
        <span><span class="nm">${l.id === "rail" ? '<i class="key trilho"></i>' : l.cor ? `<i class="key" style="background:var(${l.cor})"></i>` : ""}${l.nome} ${pill(l.nivel)}</span>
        <span class="src">${l.fonte}${quando(l.id)} · ${F.ministerios[l.ministerio]}${l.baixando ? " · <b>carregando…</b>" : ""}${l.falhou ? " · <b>não foi possível carregar agora; tente de novo</b>" : ""}${NO_ESTADO.has(l.id) ? " · <b>ícones ao escolher um estado</b>" : ""}</span></span>
      </label>`).join("") : `<p class="note">Este ministério ainda não tem camadas de mapa.</p>`;
    lv.filter(l => l.nivel !== "pendente").forEach(l => document.getElementById("ly-" + l.id).onchange = e => { l.on = e.target.checked; render(); });
    /* ligar ou desligar de uma vez todas as camadas da lista (respeita o ministério escolhido) */
    const lig = lv.filter(l => l.nivel !== "pendente"), todas = document.getElementById("todas");
    if (todas) {
      const tudo = lig.length > 0 && lig.every(l => l.on);
      todas.hidden = !lig.length;
      if (proxima === "ligar" && tudo) proxima = "desligar";
      todas.textContent = { ligar: "Ligar todas", desligar: "Desligar todas", padrao: "Padrão" }[proxima];
      todas.title = proxima === "padrao" ? "Volta às camadas que começam ligadas" : "";
      /* ligar todas → desligar todas → padrão, nessa ordem */
      todas.onclick = () => {
        if (proxima === "ligar") { lig.forEach(l => { l.on = true; }); proxima = "desligar"; }
        else if (proxima === "desligar") { lig.forEach(l => { l.on = false; }); proxima = "padrao"; }
        else { lig.forEach(l => { l.on = padrao(l); }); proxima = "ligar"; }
        guardadas = null; render();
      };
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
    lav: ["lav", d => fc(d.municipios.map(m => ponto([m[0], m[1]], { v: m[2], g: m[3], p: m[4], pv: m[5], n: m[6], u: m[7] })))],
    oil: ["pocos", pocosFC], uep: ["uep", d => d], campos: ["campos", d => d], zc: ["zc", d => d], pce: ["pce", d => d], rodest: ["rodest", d => d],
    usinas: ["usinas", d => fc(d.usinas.map(u => ponto([u[0], u[1]], { kw: u[2], t: u[3], n: u[4], uf: u[5], a: u[6] || 0, d: u[7] || "", x: u[8] || "" })))],
    lt: ["lt", d => d], dutos: ["dutos", d => d], se: ["se", d => d],
    celm: ["celm", d => fc(d.municipios.map(m => ponto([m[0], m[1]], { s: m[2], n: m[3], u: m[4], c: m[5] })))],
    g5: ["g5", d => fc(d.municipios.map(m => ponto([m[0], m[1]], { n: m[2], u: m[3], o: m[4], c: m[5] })))],
    /* indústria de defesa: [lon, lat, município, UF, código do IBGE, [[empresa, EED ou ED], ...]]; a lista fica fora do mapa */
    empdef: ["empdef", d => fc(d.municipios.map(m => ponto([m[0], m[1]], { n: m[5].length, c: m[4] })))],
    vmda: ["vmda", d => d] };
  /* município (código do IBGE) → linha do arquivo, para a janelinha do celular juntar as duas camadas */
  const INDICE = {};
  const indice = id => DATA[id] ? (INDICE[id] || (INDICE[id] = Object.fromEntries(DATA[id].municipios.map(m => [m[5], m])))) : {};
  const indiceDef = () => DATA.empdef ? (INDICE.empdef || (INDICE.empdef = Object.fromEntries(DATA.empdef.municipios.map(m => [m[4], m])))) : {};
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
    /* ícones só no estado escolhido; sem estado escolhido, os círculos no Brasil todo */
    Object.values(ICO_ESTADO).forEach(([circ, ico, uf]) => {
      if (map.getLayer(ico)) map.setFilter(ico, ["==", ["get", uf], sel || ""]);
      if (map.getLayer(circ)) map.setFilter(circ, sel ? ["==", ["get", uf], ""] : null);
    });
    const P = PAINT.find(p => p.id === paint);
    let leg = "";
    const L = LUZ.find(l => l.id === luz);
    if (L) {
      if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color", ["case", ["boolean", ["feature-state", "hover"], false], "#ffffff", "#01050a"]);
      const cores = L.id === "pop" ? COR_POP_LEG : COR_NOITE_LEG;
      leg = `<span>${L.titulo}</span><span class="faixa"><span>${L.id === "pop" ? "menos gente" : "escuro"}</span>
        <span class="ramp">${cores.map(c => `<i style="background:${c}"></i>`).join("")}</span><span>${L.id === "pop" ? "mais gente" : "mais luz"}</span></span>`;
    } else if (P && P.val) {
      /* luz de fundo (do bege fosco ao ouro) e os dois cinzas; o relevo sombreado fica por cima (camadas "relevo-ouro" e "relevo") */
      const K = classesEscala(P, Object.keys(NAME)), vals = K.escala;
      const base = s => K.c[s] === "forte" ? cor("--sem-forte") : K.c[s] === "fraco" ? cor("--sem-fraco") : cor(RAMP[K.c[s]]);
      const m = ["match", ["get", "sigla"]];
      Object.keys(NAME).forEach(s => m.push(s, base(s)));
      m.push("rgba(0,0,0,0)");
      if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color", m);
      leg = `<span>${P.nome}${P.unidade ? " (" + P.unidade + ")" : ""}</span><span class="faixa"><span>${P.fmt(Math.min(...vals))}</span>
        <span class="ramp">${RAMP.map(c => `<i style="background:var(${c})"></i>`).join("")}</span><span>${P.fmt(Math.max(...vals))}</span></span>
        ${K.forte ? `<span><i class="key sq" style="background:var(--sem-forte)"></i>sem número</span>` : ""}
        ${K.fraco ? `<span><i class="key sq" style="background:var(--sem-fraco)"></i>${K.fraco}</span>` : ""}`;
      /* "Sem cor": os estados sem pintura, como os países vizinhos (o mapa natural); em volta do escolhido, escurecidos */
    } else if (map.getLayer("estados-fill")) map.setPaintProperty("estados-fill", "fill-color",
      ["case", ["boolean", ["feature-state", "fade"], false], "#02070b", ["boolean", ["feature-state", "hover"], false], "#ffffff", "rgba(0,0,0,0)"]);
    visualModo(L, P);
    /* legenda completa (escala de cores + símbolos das camadas ligadas): sempre no rodapé, ao lado dos níveis de confiança;
       sobre o mapa só quando o botão "Legenda no mapa" está ligado (bom para tela cheia) */
    const itens = LAYERS.filter(l => l.on && l.cor).map(l => `<span class="item">${(l.legenda || [{ nome: l.nome }]).map(k => {
      /* as lavouras com o medalhão do mapa */
      /* as camadas de pontos com o medalhão do mapa (icones.js, ICO_LEG) */
      const ic = ICO_LEG[l.id] && ICO_LEG[l.id](k.cor || l.cor);
      if (ic && ICONES[ic]) return `<span>${chaveIcone(ic, k.cor || l.cor)}${k.nome}</span>`;
      const forma = l.id === "rail" ? (k.forma === "tr" ? "trilho-obra" : "trilho") : l.id === "air" ? "aviao" : l.id === "cla" ? "foguete" : l.id === "boi" ? "boi" : k.forma || (k.hachura ? "hach" : ""), contorno = ["hach", "sqv", "tr", "anel", "dup"].includes(forma);
      return `<span><i class="key ${forma}" style="${contorno ? "color" : "background"}:var(${k.cor || l.cor})"></i>${k.nome}</span>`;
    }).join("")}</span>`).join("");
    document.getElementById("legend").innerHTML = legMapa ? leg + itens : "";
    const bl = document.getElementById("legenda-mapa");
    if (bl) bl.setAttribute("aria-pressed", legMapa);
    const lr = document.getElementById("legenda");
    if (lr) lr.innerHTML = (leg ? `<span class="item escala">${leg}</span>` : "") + (itens || `<span class="note">Nenhuma camada ligada. Escolha as camadas no painel.</span>`);
    document.getElementById("back").hidden = !sel;
    document.getElementById("where").textContent = sel ? `${NAME[sel]} · ${sel}` : "Brasil · 27 UFs";
    abas.querySelector('[data-aba="ficha"]').textContent = sel ? `Ficha · ${sel}` : "Ficha · Brasil";
  }
  /* ---------- luzes à noite ---------- */
  const FADE = ["boolean", ["feature-state", "fade"], false];
  const COR_POP_LEG = ["#6e370a", "#d77d23", "#ffbe50", "#ffe8aa", "#fffceb"];
  const COR_NOITE_LEG = ["#0a0c1c", "#2c2a44", "#a8823f", "#f2d083", "#fffbe8"];
  /* ---------- ouro sobre preto (escala B, escolha do Edu em 25/10/2026; no site normal desde o mesmo dia) ----------
     Com uma pintura, a "luz de fundo": cada estado acende conforme o valor, do bege fosco (pouco) ao ouro (muito), com o
     relevo sombreado por cima em tons quentes, e o planeta em azul-noite. Com a luz "População", a terra em ouro apagado,
     com as luzes por cima. Em "Sem cor" e na "Iluminação noturna" (a imagem da NASA), o mapa natural. */
  const RELEVO_NATURAL = { "hillshade-exaggeration": 0.5, "hillshade-shadow-color": "#04100a", "hillshade-highlight-color": "rgba(255,255,240,.55)", "hillshade-accent-color": "#0c2a18" };
  /* no ouro, o relevo de altitude mais suave (aparece de perto, onde a imagem do relevo da terra some) */
  const RELEVO_OURO = { "hillshade-exaggeration": 0.38, "hillshade-shadow-color": "#0b0603", "hillshade-highlight-color": "rgba(255,222,160,.2)", "hillshade-accent-color": "#140d06" };
  let emOuro = false;
  /* como a terra aparece em cada modo: com pintura, os estados opacos e o escolhido "levantado" (sem apagar os outros,
     pedido do Edu em 24/10/2026); com luzes ou "Sem cor", sem pintura, e os estados em volta do escolhido escurecidos
     (o realce do mouse é o contorno, não um clarão no estado) */
  function visualModo(L, P) {
    if (!map.getLayer("estados-fill")) return;
    const pinta = !L && !!(P && P.val), pop = !!L && L.id === "pop";
    if (pop) {   /* com a luz População, a terra em ouro apagado */
      map.setPaintProperty("estados-fill", "fill-color", "#1d1810");
      map.setPaintProperty("estados-fill", "fill-opacity", ["case", FADE, 0.35, 1]);
    } else map.setPaintProperty("estados-fill", "fill-opacity", pinta ? 1 : ["case", FADE, L ? 0.6 : 0.5, 0]);
    /* estado levantado: só com pintura e se o estado escolhido tem cor (sem dado, ele fica sem pintura e sem sombra) */
    const cs = map.getPaintProperty("estados-fill", "fill-color"), i = sel && Array.isArray(cs) ? cs.indexOf(sel) : -1;
    const levanta = pinta && !(i > 1 && cs[i + 1] === "rgba(0,0,0,0)");
    map.setPaintProperty("sel-fill", "fill-color", cs);
    for (const id of ["sel-fill", "sel-sombra"]) map.setLayoutProperty(id, "visibility", levanta ? "visible" : "none");
    visualOuro(L, pinta, pop);
  }
  /* planeta, divisas e relevo do ouro */
  function visualOuro(L, pinta, pop) {
    /* planeta "azul-noite" com o ouro: o natural, mais escuro e um pouco menos colorido (o quase preto foi reprovado
       pelo Edu em 23/10/2026); com a luz População, um pouco mais escuro, para as luzes aparecerem */
    map.setPaintProperty("nasa", "raster-brightness-max", pinta ? 0.42 : pop ? 0.32 : L ? 0.2 : 0.62);
    map.setPaintProperty("nasa", "raster-saturation", pinta ? -0.3 : pop ? -0.45 : L ? -0.55 : -0.15);
    /* divisas: escuras entre estados acesos; douradas sobre o mapa natural e sobre a terra apagada */
    map.setPaintProperty("estados-line", "line-color", pinta ? "rgba(18,11,4,.62)" : "rgba(240,200,130,.55)");
    emOuro = pinta || pop;
    if (map.getLayer("relevo-ouro")) map.setLayoutProperty("relevo-ouro", "visibility", emOuro ? "visible" : "none");
    relevoOuro();
  }
  /* o relevo sombreado chega depois da primeira imagem; em tons quentes sobre o ouro */
  function relevoOuro() {
    if (!map.getLayer("relevo")) return;
    Object.entries(emOuro ? RELEVO_OURO : RELEVO_NATURAL).forEach(([k, v]) => map.setPaintProperty("relevo", k, v));
    map.setLayoutProperty("relevo", "visibility", luz === "noite" ? "none" : "visible");
  }
  function linhasTrem() {
    const n = luz !== "off";
    for (const id of ["ferrovias", "ferrovias-obra", "ferrovias-borda", "ferrovias-obra-borda"]) map.setPaintProperty(id, "line-opacity", sel ? ["case", ["==", ["get", "uf"], sel], n ? 0.6 : 1, n ? 0.06 : 0.15] : (n ? 0.35 : 0.9));
  }
  function aplicarNoite() {
    if (!map.getLayer("estados-fill")) return;
    const n = luz !== "off";
    map.setPaintProperty("nasa", "raster-brightness-max", n ? 0.2 : 0.62);
    map.setPaintProperty("nasa", "raster-saturation", n ? -0.55 : -0.15);
    for (const id of ["rel-mundo", "rel-cor"]) if (map.getLayer(id)) map.setPaintProperty(id, "raster-brightness-max", n ? 0.2 : 0.55);
    if (map.getLayer("relevo")) map.setLayoutProperty("relevo", "visibility", n ? "none" : "visible");
    /* a opacidade dos estados fica com visualModo(), chamada pelo render() logo depois */
    map.setPaintProperty("estados-line", "line-opacity", n ? 0.55 : 1);
    map.setPaintProperty("rodovias", "line-opacity", n ? 0.22 : 0.92);
    map.setPaintProperty("rodovias-borda", "line-opacity", n ? 0.25 : 1);
    map.setPaintProperty("rodovias-terra", "line-opacity", n ? 0.18 : 0.5);
    map.setPaintProperty("rodovias-est", "line-opacity", n ? 0.18 : 0.5);
    linhasTrem();
  }
  function prepararLuzes() {
    if (luz === "noite" && !map.getSource("luz-noite")) {
      map.addSource("luz-noite", { type: "raster", tileSize: 256, maxzoom: 8, tiles: [LUZ.find(l => l.id === "noite").ladrilhos], attribution: "NASA Black Marble" });
      map.addLayer({ id: "luz-noite", type: "raster", source: "luz-noite", paint: { "raster-fade-duration": 300 } }, "paises-borda");
    }
    /* versão de teste: a população em quadrados de 1 km (IBGE, grade estatística do Censo 2022), no lugar do brilho
       espalhado dos municípios (scripts/gerar_grade_populacao.py; imagem em Mercator com os cantos do recorte) */
    if (TESTE && luz === "pop" && !map.getSource("luz-grade")) {
      map.addSource("luz-grade", { type: "image", url: D + "luzes/grade_populacao.webp", coordinates: [[-74.2, 5.6], [-28.6, 5.6], [-28.6, -34], [-74.2, -34]] });
      map.addLayer({ id: "luz-grade", type: "raster", source: "luz-grade", paint: { "raster-opacity": 0.95, "raster-fade-duration": 0, "raster-resampling": "linear" } }, "estados-line");
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
        "heatmap-opacity": 0.95 } }, "estados-line");
      /* um ponto de luz por município, do tamanho da população (raiz quadrada: área do ponto proporcional às pessoas) */
      const RAIO = ["interpolate", ["linear"], ["sqrt", ["get", "p"]], 0, 0.6, 100, 1.1, 300, 1.8, 1000, 3.4, 3500, 6.5];
      map.addLayer({ id: "luz-pop-ponto", type: "circle", source: "luz-pop", paint: {
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 3, ["*", 0.6, RAIO], 5, ["*", 0.9, RAIO], 8, ["*", 1.6, RAIO]],
        "circle-color": "#ffe4a8", "circle-blur": 0.6, "circle-opacity": TESTE ? 0.28 : 0.9 } }, "estados-line");
    }
    const vis = (id, on) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    vis("luz-noite", luz === "noite"); vis("luz-pop-calor", luz === "pop" && !TESTE); vis("luz-pop-ponto", luz === "pop");
    vis("luz-grade", luz === "pop");
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
    /* rodovias e ferrovias se apagam com as luzes (parecem estradas iluminadas) e voltam como estavam depois; a Zona
       Econômica Exclusiva também (pedido do Edu em 25/10/2026: o mar territorial e a zona contígua ficam) */
    const linhas = LAYERS.filter(l => ["rod", "rodest", "rail", "zee", "vmda", "dup"].includes(l.id) && l.nivel !== "pendente");
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
      ${pill(O.nivel)} <span class="note">${esc(O.fonte)}; média de ${esc(O.referencia)} · atualizado em ${O.atualizado_em}</span>${fichaInstalacoes(s)}</div>`;
  }
  /* refinarias, unidades de gás natural e terminais de GNL do estado (ANP, servidor de mapas) */
  function fichaInstalacoes(s) {
    const I = DATA.refin;
    if (!I) return "";
    const inst = I.features.map(f => f.properties).filter(p => p.uf === s);
    if (!inst.length) return "";
    const ref = inst.filter(p => p.k === "refinaria"), ug = inst.filter(p => p.k === "upgn"), gn = inst.filter(p => p.k === "gnl");
    return `${ref.length ? `<div class="kv" style="margin-top:8px"><span>Refinarias</span><span class="v">${ref.length}</span></div>
        <div class="list">${ref.map(p => esc(p.s || p.n) + (p.bbl ? ` (${fmt(Math.round(p.bbl / 1000))} mil barris/dia)` : "")).join(", ")}.</div>` : ""}
      ${ug.length ? `<div class="kv"><span>Unidades de processamento de gás natural</span><span class="v">${ug.length}</span></div>` : ""}
      ${gn.length ? `<div class="kv"><span>Terminais de GNL</span><span class="v">${gn.length}</span></div>` : ""}
      ${pill(I.meta.nivel)} <span class="note">ANP, servidor de mapas · atualizado em ${I.meta.atualizado_em}</span>`;
  }

  /* energia elétrica do estado (ANEEL, SIGA): potência instalada por fonte */
  function fichaEnergia(s) {
    const E = DATA.ene;
    if (!E) return "";
    const v = E.valores[s], fonte = `${pill(E.nivel)} <span class="note">${esc(E.fonte)}; ${esc(E.referencia)} · atualizado em ${E.atualizado_em}</span>`;
    if (!v) return `<div class="sec"><h3>Energia elétrica</h3><div class="list">Nenhuma usina deste estado no cadastro da ANEEL (geração centralizada).</div>${fonte}</div>`;
    const NOM = { hid: "Hidrelétricas", eol: "Eólicas", sol: "Solares", bio: "Térmicas a biomassa", fos: "Térmicas fósseis", nuc: "Nucleares" };
    const partes = [["hid", (v.uhe || 0) + (v.pch || 0) + (v.cgh || 0)], ["eol", v.eol], ["sol", v.sol], ["bio", v.bio], ["fos", v.fos], ["nuc", v.nuc]]
      .filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]);
    const rk = Object.entries(E.valores).sort((a, b) => b[1].valor - a[1].valor).findIndex(e => e[0] === s) + 1;
    return `<div class="sec"><h3>Energia elétrica</h3>
      <div class="kv"><span>Potência instalada</span><span class="v">${fmt(Math.round(v.valor))} MW</span></div>
      <div class="kv"><span>Posição no país</span><span class="v">${rk}º · ${fmt1(v.valor / E.total_mw * 100)}%</span></div>
      ${partes.map(([k, mw]) => `<div class="kv"><span>${NOM[k]}</span><span class="v">${fmt(Math.round(mw))} MW · ${mw / v.valor < 0.001 ? "menos de 0,1" : fmt1(mw / v.valor * 100)}%</span></div>`).join("")}
      <div class="list">${fmt(v.usinas)} usinas no cadastro da ANEEL (no mapa, só as de 1 MW ou mais). Só a geração centralizada: os painéis solares de telhado e a micro e minigeração distribuída não entram.</div>
      ${(v.obs || []).map(o => `<div class="list"><i>${esc(o)}</i></div>`).join("")}
      ${fonte}</div>`;
  }

  /* principais lavouras do estado (IBGE, PAM): as 5 de maior valor da produção, com a quantidade */
  const milhoes = x => `${fmt1(x)} ${x < 1.95 ? "milhão" : "milhões"}`;   /* 1,6 milhão; 2 milhões */
  const quant = (q, un) => q == null ? "" : un === "mil frutos" ? (q >= 1e3 ? `${milhoes(q / 1e3)} de frutos` : `${fmt(q)} mil frutos`)
    : q >= 1e6 ? `${milhoes(q / 1e6)} de t` : q >= 1e3 ? `${fmt1(q / 1e3)} mil t` : `${fmt(q)} t`;
  function fichaLavouras(s) {
    const L = DATA.soja || DATA.milho || DATA.cana || DATA.cafe, v = L && L.valores[s];
    if (!v || !v.principais || !v.principais.length) return "";
    return `<div class="list" style="margin-top:8px">Principais lavouras, pelo valor da produção:</div>
      ${v.principais.map(([n, mil, q, un]) => `<div class="kv"><span>${esc(n)}</span><span class="v">${reais(mil)}${q != null ? " · " + quant(q, un) : ""}</span></div>`).join("")}
      ${pill(L.nivel)} <span class="note">${esc(L.fonte)}, ref. ${esc(L.referencia)} · atualizado em ${L.atualizado_em}</span>`;
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

  /* versão de teste: pista dupla do estado (DNIT, SNV) */
  function fichaDupla(s) {
    if (!DATA.dup) return "";
    const M = DATA.dup.meta, k = M.km_por_uf[s];
    return `<div class="kv"><span>Pista dupla (rodovias federais)</span><span class="v">${k && k[0] ? "≈ " + fmt(k[0]) + " km" : "nenhuma"}</span></div>
      ${k && k[1] ? `<div class="list">Mais ≈ ${fmt(k[1])} km em obra de duplicação.</div>` : ""}
      ${pill(DATA.dup.nivel || "manual")} <span class="note">${esc(M.fonte)}.</span>`;
  }
  /* versão de teste: passagens de fronteira do estado (cidades gêmeas) */
  function fichaPassagens(s) {
    if (!DATA.passa) return "";
    const ps = DATA.passa.features.filter(f => f.properties.k === "passagem" && f.properties.br.includes("(" + s + ")"));
    if (!ps.length) return "";
    return `<div class="kv"><span>Passagens de fronteira</span><span class="v">${ps.length}</span></div>
      <div class="list">${ps.map(f => { const p = f.properties;
        return `${esc(p.br.replace(/ \([A-Z]{2}\)/g, ""))} ↔ ${esc(p.viz)}${p.lig ? ": " + esc(p.lig) : ""}`; }).join("<br>")}</div>
      ${pill("manual")} <span class="note">Cidades gêmeas: IBGE e Portaria MDR nº 2.507/2021; cidade do outro lado e ligação: artigos e reportagens (detalhes no clique, no mapa).</span>`;
  }
  /* aeroportos do estado (ANAC): aeródromos públicos, quantos têm voos de passageiros e os mais movimentados */
  const passageiros = n => n >= 1e6 ? `${milhoes(n / 1e6)} de passageiros` : `${fmt(Math.round(n / 1e3))} mil passageiros`;
  function fichaAeroportos(s) {
    const A = DATA.air, v = A && A.meta && A.meta.por_uf[s];
    if (!v) return "";
    return `<div class="kv" style="margin-top:8px"><span>Aeródromos públicos</span><span class="v">${fmt(v.aerodromos)}</span></div>
      <div class="list">${v.com_passageiros ? `${fmt(v.com_passageiros)} com voos de passageiros: ${passageiros(v.passageiros)} em 12 meses. Os mais movimentados: ${v.maiores.map(m => `${esc(m[0])} (${esc(m[1])}), ${passageiros(m[2])}`).join("; ")}.` : "Nenhum com voos de passageiros nos dados estatísticos da ANAC."}</div>
      ${pill(A.meta.nivel)} <span class="note">ANAC, aeródromos públicos e dados estatísticos do transporte aéreo, ${esc(A.meta.referencia)} · atualizado em ${A.meta.atualizado_em}. Embarcados e desembarcados.</span>`;
  }

  /* pedágios federais do estado (ANTT): quantas praças e a mais movimentada */
  function fichaPedagio(s) {
    const P = DATA.pedagio, v = P && P.meta.por_uf[s];
    if (!v) return "";
    const m = v.maior;
    return `<div class="kv" style="margin-top:8px"><span>Praças de pedágio federais</span><span class="v">${fmt(v.pracas)}</span></div>
      ${m ? `<div class="list">A mais movimentada: ${esc(m[0])} (${esc(m[2])}, km ${esc(m[3])}, ${esc(m[4])}), com ≈ ${fmt(m[1])} veículos por dia.</div>` : ""}
      ${pill(P.meta.nivel)} <span class="note">ANTT, média de ${esc(P.meta.referencia)} · atualizado em ${P.meta.atualizado_em}. Só as concessões federais.</span>`;
  }

  /* eletropostos do estado (ABVE e Tupi): o número do estado quando foi divulgado; se não, o total da região */
  function fichaEletropostos(s) {
    const E = DATA.evpc;
    if (!E) return "";
    const v = E.valores[s], R = Object.entries(E.regioes || {}).find(([, r]) => r.ufs.includes(s));
    const corpo = v
      ? `<div class="kv"><span>Pontos de recarga</span><span class="v">${fmt(v.valor)}</span></div>
        ${POP[s] ? `<div class="kv"><span>Por 100 mil habitantes</span><span class="v">${fmt1(v.valor / POP[s] * 1e5)}</span></div>` : ""}
        ${pill(E.nivel)} <span class="note">${esc(v.fonte)}, ${esc(v.referencia)}${v.via ? ` · via ${esc(v.via)}` : ""}. Pontos públicos e semipúblicos.</span>`
      : `<div class="kv"><span>Pontos de recarga</span><span class="v">—</span></div>
        <div class="list">A ABVE não divulgou o número deste estado.${R ? ` A região ${R[0]} inteira soma ${fmt(R[1].valor)} pontos (${esc(E.referencia)}).` : ""}</div>
        ${pill("pendente")} <span class="note">${R && E.regioes_fonte ? esc(E.regioes_fonte) : "Nenhum número publicado encontrado."}</span>`;
    return `<div class="sec"><h3>Mobilidade elétrica</h3>${corpo}</div>`;
  }

  /* defesa do estado: empresas credenciadas pelo Ministério da Defesa (EED e ED) e, no Maranhão, o Centro de Alcântara */
  function fichaDefesa(s) {
    const D = DATA.defesa, v = D && D.valores[s], cla = CLA && s === CLA.uf;
    if (!D && !cla) return "";
    let ind = "";
    if (D && v) {
      const pos = 1 + Object.values(D.valores).filter(x => x.valor > v.valor).length;   /* empate: mesma posição */
      const nos = v.municipios.reduce((a, b) => a + b[1], 0), resto = v.valor - v.sem_municipio - nos;
      ind = `<div class="kv"><span>Empresas credenciadas pelo Ministério da Defesa</span><span class="v">${fmt(v.valor)} · ${pos}º</span></div>
        <div class="kv"><span>Estratégicas de defesa (EED)</span><span class="v">${fmt(v.eed)}</span></div>
        <div class="kv"><span>De defesa (ED)</span><span class="v">${fmt(v.ed)}</span></div>
        ${v.municipios.length ? `<div class="list">Municípios com mais empresas: ${v.municipios.map(([n, q]) => `${esc(n)} (${q})`).join(", ")}${resto > 0 ? `; mais ${fmt(resto)} em outros municípios` : ""}.</div>` : ""}
        ${v.sem_municipio ? `<div class="list">${v.sem_municipio > 1 ? `${v.sem_municipio} empresas vêm` : "1 empresa vem"} na lista sem um município que dê para localizar (só o estado, um bairro comum a várias cidades ou cidade de outro estado) e ${v.sem_municipio > 1 ? "ficam" : "fica"} fora do mapa.</div>` : ""}
        <div class="list">EED: sede, produção e controle no Brasil, com tecnologia própria; pode usar o regime tributário especial da defesa (Lei 12.598/2012). ED: fabrica produtos de defesa ou faz parte da cadeia que os produz.</div>`;
    } else if (D) ind = `<div class="list">Nenhuma empresa deste estado na lista das credenciadas pelo Ministério da Defesa.</div>`;
    return `<div class="sec"><h3>Defesa</h3>${ind}
      ${D ? `${pill(D.nivel)} <span class="note">${esc(D.fonte)}, ${esc(D.referencia)} · atualizado em ${D.atualizado_em}</span>` : ""}
      ${cla ? `<div class="list" style="margin-top:8px">${CLA.nome}, base de lançamento de foguetes da Força Aérea.</div>${pill("calculado")} <span class="note">posição aproximada</span>` : ""}</div>`;
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
        ${DATA.agro ? `<div class="kv" style="margin-top:8px"><span>Produção agrícola</span><span class="v">${reais(Object.values(DATA.agro.valores).reduce((a, b) => a + b, 0))}</span></div>
          ${pill(DATA.agro.nivel)} <span class="note">IBGE, valor da produção das lavouras, ref. ${esc(DATA.agro.referencia)} · atualizado em ${DATA.agro.atualizado_em}</span>` : ""}
        ${DATA.oleo ? `<div class="kv" style="margin-top:8px"><span>Petróleo e gás</span><span class="v">${fmt1(DATA.oleo.total_boe_dia / 1e6)} milhões de boe/dia</span></div>
          ${pill(DATA.oleo.nivel)} <span class="note">ANP, média de ${esc(DATA.oleo.referencia)} · atualizado em ${DATA.oleo.atualizado_em}. boe = barril de óleo equivalente.</span>` : ""}
        ${DATA.ene ? `<div class="kv" style="margin-top:8px"><span>Energia elétrica</span><span class="v">${fmt(Math.round(DATA.ene.total_mw / 1000))} mil MW</span></div>
          ${pill(DATA.ene.nivel)} <span class="note">${esc(DATA.ene.fonte)}, potência instalada (${esc(DATA.ene.referencia)}) · atualizado em ${DATA.ene.atualizado_em}. Sem os painéis solares de telhado.</span>` : ""}
        ${DATA.cel && DATA.cel.cinco_g ? `<div class="kv" style="margin-top:8px"><span>Municípios com 5G</span><span class="v">${fmt(DATA.cel.cinco_g.municipios)} de ${fmt(DATA.cel.cinco_g.total)}</span></div>
          ${pill(DATA.cel.nivel)} <span class="note">Anatel, presença da telefonia móvel (RQUAL), ${esc(DATA.cel.cinco_g.referencia)} · atualizado em ${DATA.cel.cinco_g.atualizado_em}. Pelo menos uma operadora com 5G no município.</span>` : ""}
        ${DATA.defesa ? `<div class="kv" style="margin-top:8px"><span>Indústria de defesa</span><span class="v">${fmt(DATA.defesa.total)} empresas</span></div>
          ${pill(DATA.defesa.nivel)} <span class="note">Ministério da Defesa, empresas credenciadas: ${fmt(DATA.defesa.eed)} estratégicas de defesa (EED) e ${fmt(DATA.defesa.ed)} de defesa (ED); ${esc(DATA.defesa.referencia)} · atualizado em ${DATA.defesa.atualizado_em}</span>` : ""}
        ${DATA.evpc && DATA.evpc.brasil ? `<div class="kv" style="margin-top:8px"><span>Eletropostos</span><span class="v">≈ ${fmt1(DATA.evpc.brasil.valor / 1000)} mil</span></div>
          ${pill(DATA.evpc.nivel)} <span class="note">${esc(DATA.evpc.fonte)}, pontos públicos e semipúblicos, ${esc(DATA.evpc.referencia)}; ${esc(DATA.evpc.brasil.nota)} · atualizado em ${DATA.evpc.atualizado_em}</span>` : ""}
        <p class="lede">Clique num estado para aproximar. Arraste para girar o globo, role para aproximar e use o botão "Relevo 3D" para ver as montanhas em altura.</p>`;
      return;
    }
    const s = sel;
    const rk = Object.entries(POP).sort((a, b) => b[1] - a[1]).findIndex(e => e[0] === s) + 1;
    const Pt = (DATA.ports || []).filter(p => p.uf === s);
    /* ferrovias por estado: [existentes, em operação segundo o IBGE] (arquivo antigo: um número só) */
    const fv = DATA.rail ? DATA.rail.km_por_uf[s] || 0 : 0, fr = typeof fv === "number" ? [fv, fv] : fv;
    const kr = DATA.rod && DATA.rod.meta && DATA.rod.meta.km_por_uf ? DATA.rod.meta.km_por_uf[s] : null;
    const ag = DATA.agro && DATA.agro.valores[s];
    el.innerHTML = `
      <h2>${s} · ficha do estado</h2><div class="fname">${NAME[s]}</div>
      <div class="sec"><h3>População</h3>
        <div class="kv"><span>Habitantes</span><span class="v">${POP[s] ? fmt(POP[s]) : "—"}</span></div>
        <div class="kv"><span>Posição no país</span><span class="v">${rk}º · ${fmt1(POP[s] / popTot * 100)}%</span></div>${popInfo}</div>
      <div class="sec"><h3>Agricultura</h3>
        ${ag != null ? `<div class="kv"><span>${DATA.agro.titulo}</span><span class="v">${reais(ag)}</span></div>
          ${pill(DATA.agro.nivel)} <span class="note">${DATA.agro.fonte}, ref. ${DATA.agro.referencia} · atualizado em ${DATA.agro.atualizado_em}</span>`
        : `${pill("pendente")} <span class="note">O robô de atualização ainda não rodou.</span>`}
      ${fichaLavouras(s)}</div>
      ${fichaPecuaria(s)}
      <div class="sec"><h3>Logística</h3>
        ${kr ? `<div class="kv"><span>Rodovias federais</span><span class="v">≈ ${fmt(kr[0])} km</span></div>
          <div class="list">${fmt(kr[1])} km pavimentados, sob administração federal (inclusive concessões).${kr[2] ? ` Mais ≈ ${fmt(kr[2])} km com sigla BR administrados pelo estado (rodovias estaduais coincidentes ou trechos delegados), em outra cor no mapa.` : ""}</div>` : ""}
        <div class="kv"><span>Ferrovias</span><span class="v">${fr[0] ? "≈ " + fmt(fr[0]) + " km" : "nenhuma na base"}</span></div>
        ${fr[0] ? `<div class="list">${fr[1] ? `≈ ${fmt(fr[1])} km em operação segundo o IBGE${fr[1] < fr[0] ? `; nos outros ≈ ${fmt(fr[0] - fr[1])} km a base não informa` : ""}` : "A base do IBGE não informa se estão em operação"}.</div>` : ""}
        <div class="kv"><span>Portos e terminais</span><span class="v">${Pt.length}</span></div>
        ${Pt.length ? `<div class="list">${Pt.map(p => esc(p.n)).join(", ")}</div>` : ""}
        ${pill("manual")} <span class="note">IBGE, base cartográfica 1:250.000 (BC250, 2025); medidas no desenho do mapa.</span>
        ${fichaAeroportos(s)}
        ${fichaPedagio(s)}
        ${fichaDupla(s)}
        ${fichaPassagens(s)}</div>
      ${fichaOleo(s)}
      ${fichaEnergia(s)}
      ${fichaCelular(s)}
      ${fichaDefesa(s)}
      ${fichaEletropostos(s)}`;
  }

  const AP = F.apoio, apoio = document.getElementById("apoio");
  if (AP && AP.link) {
    /* botão retangular, mais largo, com moedas de ouro caindo no fim do texto (pedido do Edu em 24 e 25/10/2026), e um
       segundo botão igual no fim da página, embaixo do texto "Sobre o mapa" */
    const html = `<a class="apoiar" href="${AP.link}" target="_blank" rel="noopener"><span>${AP.texto}</span>${MOEDAS}</a>
      ${AP.nota ? `<span class="note">${AP.nota}</span>` : ""}`;
    apoio.innerHTML = html; apoio.hidden = false;
    const fim = document.getElementById("apoio-fim");
    if (fim) { fim.innerHTML = html; fim.hidden = false; }
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
    relevoOuro();
  });
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { ajustarCabecalho(); map.resize(); limitarZoom(); }, 150); });
  /* a legenda acompanha os créditos quando eles abrem ou fecham (botão i) e quando a própria legenda muda de tamanho */
  if (window.ResizeObserver) {
    const ro = new ResizeObserver(() => afastarLegenda());
    ro.observe(document.getElementById("legend"));
    const at = document.querySelector(".maplibregl-ctrl-attrib"); if (at) ro.observe(at);
  }
  window.__mapa = map;

  /* ---------- versão de teste: o globo se afasta ao rolar a página ----------
     Pedido do Edu em 25/10/2026: "quando rolar a tela para baixo fazer com que o globo se afaste e centralize, para que o
     efeito de lente fique visível na parte inferior e a tela não fique dividida". Enquanto a página rola o trecho
     --recuo (margem embaixo do palco, no CSS), o mapa fica preso na tela e a câmera vai de onde a pessoa deixou até o
     globo inteiro, menor, no meio da tela: sem inclinação, com o norte para cima e com o ponto que estava no meio da
     área livre (fora do painel) virado para a frente. Depois o mapa sobe junto com o rodapé, já pequeno e inteiro, sem
     ser cortado pela borda. Voltando ao topo, a câmera volta exatamente para onde estava. Com a página rolada, o mapa não
     responde ao mouse (a roda rola a página); no topo, com o globo já no zoom mínimo, rolar a roda para baixo sobre ele
     desce a página em vez de tentar afastar mais. */
  if (RECUO.ligado) recuoGlobo();
  function recuoGlobo() {
    const el = map.getContainer(), raiz = document.documentElement;
    let base = null, alvo = null, pedido = false, tVolta = 0;
    const suave = t => t * t * (3 - 2 * t);
    const giro = (de, para) => ((para - de + 540) % 360) - 180;            /* menor diferença entre dois ângulos */
    const trecho = () => largo() ? parseFloat(getComputedStyle(stage).marginBottom) || 0 : 0;
    /* zoom em que o contorno do globo tem raio r px, com o ponto c de frente e sem inclinação: o raio do globo em px é
       e = 512·2^zoom / (2π·cos lat) (MapLibre 5) e o contorno visto da câmera, a F px, é r = F·e / √(F² + 2F·e) */
    function zoomPara(r, c) {
      const F = map.transform.cameraToCenterDistance;
      const e = (r * r + r * Math.sqrt(r * r + F * F)) / F;
      return Math.log2(2 * Math.PI * e * Math.cos(c.lat * Math.PI / 180) / 512);
    }
    function centroVisto() {
      const f = folga(), cv = map.getCanvas(), w = cv.clientWidth, h = cv.clientHeight;
      try {
        const p = map.unproject([(f.left + w - f.right) / 2, (f.top + h - f.bottom) / 2]);
        if (p && isFinite(p.lat) && isFinite(p.lng)) return p;
      } catch (e) { /* ponto fora do globo: fica o centro atual */ }
      return map.getCenter();
    }
    function iniciar() {
      base = { center: map.getCenter(), zoom: map.getZoom(), pitch: map.getPitch(), bearing: map.getBearing() };
      const c = centroVisto(), cv = map.getCanvas();
      const r = Math.max(60, Math.min(0.31 * innerHeight, 0.3 * cv.clientWidth));
      alvo = { center: c, zoom: Math.max(-2, Math.min(base.zoom, zoomPara(r, c))) };
      RECUO.ativo = true;
      map.setMinZoom(-2);
      clearTimeout(tVolta); raiz.classList.add("recuo-ativo");
    }
    function restaurar() {
      map.jumpTo(base);
      RECUO.ativo = false; base = alvo = null;
      limitarZoom();
      /* o mapa volta a responder ao mouse quando a roda para (senão o resto do giro da roda aproximaria o globo) */
      clearTimeout(tVolta); tVolta = setTimeout(() => { if (!RECUO.ativo) raiz.classList.remove("recuo-ativo"); }, 350);
    }
    function aplicar() {
      pedido = false;
      const D = trecho(), s = D > 0 ? Math.max(0, -stage.getBoundingClientRect().top) : 0;
      if (s < 1) { if (RECUO.ativo) restaurar(); return; }
      if (!RECUO.ativo) iniciar();
      const t = suave(Math.min(1, s / (0.85 * D)));
      const lng = base.center.lng + giro(base.center.lng, alvo.center.lng) * t;
      const lat = base.center.lat + (alvo.center.lat - base.center.lat) * t;
      map.jumpTo({ center: [lng, lat], zoom: base.zoom + (alvo.zoom - base.zoom) * t,
        pitch: base.pitch * (1 - t), bearing: base.bearing + giro(base.bearing, 0) * t });
    }
    const pedir = () => { if (!pedido) { pedido = true; requestAnimationFrame(aplicar); } };
    addEventListener("scroll", pedir, { passive: true });
    /* mudou o tamanho da janela com a página rolada: refaz o alvo a partir da câmera de antes */
    map.on("resize", () => { if (RECUO.ativo) { restaurar(); pedir(); } });
    /* se o site mover a câmera com a página rolada (ex.: Centralizar, Relevo 3D, Recolher o painel), volta ao topo antes */
    for (const nome of ["easeTo", "flyTo", "fitBounds"]) {
      const orig = map[nome].bind(map);
      map[nome] = (...a) => {
        if (RECUO.ativo) { restaurar(); clearTimeout(tVolta); raiz.classList.remove("recuo-ativo"); scrollTo(0, 0); }
        return orig(...a);
      };
    }
    /* no topo, com o globo no zoom mínimo: a roda para baixo desce a página (o MapLibre nem recebe o giro) */
    el.addEventListener("wheel", ev => {
      if (RECUO.ativo || ev.ctrlKey || ev.deltaY <= 0 || !trecho()) return;
      if (map.getZoom() > map.getMinZoom() + 0.01) return;
      ev.stopPropagation();
    }, { capture: true, passive: true });
    map.once("load", pedir);
    pedir();
  }

  /* versão de teste: fundo B com distorção gravitacional em volta do globo (3d/fundo3d.js, carregado só aqui) */
  if (FUNDO === "funil" || FUNDO === "lente") {
    const sc = document.createElement("script"); sc.src = "3d/fundo3d.js?v=2";
    sc.onload = () => fundoGravidade(map, FUNDO); document.head.append(sc);
  }
})();
