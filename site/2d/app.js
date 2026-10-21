/* Brasil em Camadas — app.js
   Lê o registro data/fontes.json e os arquivos de cada camada. Nada de dado escrito aqui dentro. */
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
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
/* valores em mil R$ (padrão do IBGE) viram "R$ 71,3 bi" ou "R$ 251 mi" */
const kmTxt = a => a >= 1e6 ? `${(a / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} milhão de km²` : `${fmt(Math.round(a / 1e3))} mil km²`;
const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const reais = mil => mil >= 1e6 ? `R$ ${fmt1(mil / 1e6)} bi` : `R$ ${fmt(Math.round(mil / 1e3))} mi`;
const pill = n => `<span class="pill ${NIVEL[n][0]}">${NIVEL[n][1]}</span>`;

async function getJSON(p) {
  try { const r = await fetch(p); if (!r.ok) return null; return await r.json(); } catch { return null; }
}

function rewind(f) {
  const g = f.geometry || f;
  if ((g.type === "Polygon" || g.type === "MultiPolygon") && d3.geoArea(g) > 2 * Math.PI) {
    if (g.type === "Polygon") g.coordinates.forEach(r => r.reverse());
    else g.coordinates.forEach(p => p.forEach(r => r.reverse()));
  }
  return f;
}

(async function main() {
  const F = await getJSON("../data/fontes.json");
  const estados = await getJSON("../data/geo/estados.json");
  if (!F || !estados) {
    document.getElementById("ficha").innerHTML = `<p class="note">Não foi possível carregar os dados do mapa. Recarregue a página.</p>`;
    return;
  }
  estados.features.forEach(rewind);
  const viz = await getJSON("../data/geo/mundo.json");
  if (viz) viz.features.forEach(rewind);
  const NAME = {}; estados.features.forEach(f => NAME[f.properties.sigla] = f.properties.name);

  /* carrega cada camada; arquivo ausente vira "em apuração" */
  const DATA = {};
  await Promise.all([...F.pintura, ...F.camadas].filter(l => l.arquivo).map(async l => {
    DATA[l.id] = await getJSON("../data/" + l.arquivo);
    if (!DATA[l.id] && l.nivel) l.nivel = "pendente";
  }));
  /* camadas do mar: cada arquivo traz a área ("area"), as linhas de limite ("limite", "base") e os rótulos */
  const parte = (id, p) => DATA[id] && DATA[id].features ? DATA[id].features.filter(f => f.properties.parte === p) : [];
  ["zee", "mt", "zc", "pce", "presal"].forEach(id => parte(id, "area").forEach(rewind));
  if (DATA.campos) DATA.campos.features.forEach(rewind);
  const POP = DATA.pop ? DATA.pop.valores : {};
  const popTot = Object.values(POP).reduce((a, b) => a + b, 0);

  const PAINT = [{ id: "none", nome: "Sem cor" }, ...F.pintura.map(p => ({
    ...p, ok: !!DATA[p.id],
    nivel: DATA[p.id] ? DATA[p.id].nivel : "pendente",
    val: !DATA[p.id] ? null
      : p.por === "per_capita" ? s => (DATA[p.id].valores[s] && POP[s]) ? DATA[p.id].valores[s].valor / POP[s] * 1e5 : null
      : s => { const v = DATA[p.id].valores[s]; return v == null ? null : (typeof v === "object" ? v.valor : v); },
    fmt: p.por === "per_capita" ? fmt1 : fmt
  }))];
  const LAYERS = F.camadas.map(l => ({ ...l, on: !!l.ligada && l.nivel !== "pendente" }));

  let paint = "pop", sel = null, minF = "todos";

  /* ---------- mapa ---------- */
  const stage = document.getElementById("stage");
  const svg = d3.select("#map");
  const root = svg.append("g");
  /* textura de solo para os outros países, gerada na hora */
  const defs = svg.append("defs");
  (function terra() {
    const c = document.createElement("canvas"); c.width = c.height = 160;
    const x = c.getContext("2d"); x.fillStyle = "#2c2a1d"; x.fillRect(0, 0, 160, 160);
    for (let i = 0; i < 2600; i++) {
      const v = Math.random();
      x.fillStyle = v < .5 ? `rgba(70,64,40,${.25 + v * .4})` : v < .85 ? `rgba(28,30,20,${.3 + v * .3})` : `rgba(120,104,70,${.18})`;
      x.fillRect(Math.random() * 160, Math.random() * 160, 1 + Math.random() * 2.4, 1 + Math.random() * 2.4);
    }
    defs.append("pattern").attr("id", "terra").attr("patternUnits", "userSpaceOnUse").attr("width", 160).attr("height", 160)
      .append("image").attr("href", c.toDataURL()).attr("width", 160).attr("height", 160);
  })();
  /* hachura (listras diagonais) da plataforma continental ainda em análise na ONU */
  defs.append("pattern").attr("id", "hachura").attr("patternUnits", "userSpaceOnUse").attr("width", 5).attr("height", 5)
    .attr("patternTransform", "rotate(45)").append("line").attr("class", "hach-l").attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 5);
  const flowP = root.append("path").attr("class", "flow");
  const gGrat = root.append("path").attr("class", "grat");
  const vizP = root.append("g").selectAll("path").data(viz ? viz.features : []).join("path").attr("class", "viz");
  /* relevo: imagem colorida da região (oceano transparente) e sombra detalhada só no Brasil */
  const REL = await getJSON("../data/relevo/relevo.json");
  const imgMundo = REL && REL.mundo ? root.append("image").attr("class", "relevo-cor").attr("href", "../data/relevo/" + REL.mundo.arquivo).attr("preserveAspectRatio", "none") : null;
  const imgCor = REL && REL.cor ? root.append("image").attr("class", "relevo-cor").attr("href", "../data/relevo/" + REL.cor.arquivo).attr("preserveAspectRatio", "none") : null;
  const vizB = root.append("g").selectAll("path").data(viz ? viz.features : []).join("path").attr("class", "viz-borda");
  const ROTULOS = ["Argentina", "Uruguai", "Paraguai", "Bolívia", "Peru", "Colômbia", "Venezuela", "Chile", "Equador"];
  /* países pequenos do norte com posição ajustada à mão (a Guiana Francesa faz parte da França na base mundial); oceanos */
  const EXTRAS = [{ n: "Guiana", c: [-58.9, 5.7], peq: true }, { n: "Suriname", c: [-55.8, 4.4], peq: true }, { n: "Guiana\nFrancesa", c: [-53.1, 4.3], peq: true },
    { n: "Oceano Atlântico", c: [-26, -30], mar: true }, { n: "Oceano Pacífico", c: [-92, -12], mar: true }];
  const lbls = root.append("g").selectAll("text")
    .data([...(viz ? viz.features.filter(f => ROTULOS.includes(f.properties.NAME_PT)).map(f => ({ n: f.properties.NAME_PT, c: d3.geoCentroid(f) })) : []), ...EXTRAS])
    .join("text").attr("class", d => "viz-lbl" + (d.mar ? " mar" : "") + (d.peq ? " peq" : ""))
    .each(function (d) { const p = d.n.split("\n"); d3.select(this).selectAll("tspan").data(p).join("tspan").attr("x", 0).attr("dy", (_, i) => i ? "1.15em" : (p.length > 1 ? "-0.3em" : 0)).text(s => s); });
  const ROT = await getJSON("../data/geo/rotulos.json") || { capitais: [], estados: [], ilhas: [] };
  const gPce = root.append("g");
  const pceA = gPce.selectAll("path.pce-area").data(parte("pce", "area")).join("path").attr("class", d => "pce-area " + d.properties.status);
  pceA.append("title").text(d => `Plataforma continental estendida · ${d.properties.nome}: ${d.properties.situacao}. ` +
    `Área no desenho ≈ ${kmTxt(d.properties.area_km2)}; Marinha: ${d.properties.area_marinha}. ${d.properties.fonte_curta}. Sem valor legal.`);
  const pceL = gPce.selectAll("path.pce-lim").data(parte("pce", "limite")).join("path").attr("class", d => "pce-lim " + d.properties.status);
  const pceT = gPce.selectAll("text").data(parte("pce", "rotulo")).join("text").attr("class", "pce-lbl")
    .each(function (d) { const p = d.properties.texto.split("\n"); d3.select(this).selectAll("tspan").data(p).join("tspan").attr("x", 0).attr("dy", (_, i) => i ? "1.25em" : "-0.3em").text(t => t); });
  const gZee = root.append("g");
  const zeeA = gZee.selectAll("path.zee-area").data(parte("zee", "area")).join("path").attr("class", "zee-area");
  const zeeL = gZee.selectAll("path.zee-lim").data(parte("zee", "limite")).join("path").attr("class", "zee-lim");
  const zeeTxt = gZee.append("text").attr("class", "zee-lbl").text("Zona Econômica Exclusiva · 200 milhas");
  const ilhas = gZee.append("g").selectAll("g").data(ROT.ilhas || []).join("g").attr("class", "ilha");
  ilhas.append("circle").attr("r", 2.4);
  ilhas.append("text").attr("x", d => d.dx).attr("y", d => d.dy).attr("text-anchor", d => d.a).text(d => d.n);
  ilhas.append("title").text(d => d.nome_completo);
  const gZc = root.append("g");
  const zcA = gZc.selectAll("path.zc-area").data(parte("zc", "area")).join("path").attr("class", "zc-area");
  const zcL = gZc.selectAll("path.zc-lim").data(parte("zc", "limite")).join("path").attr("class", "zc-lim");
  const gMt = root.append("g");
  const mtA = gMt.selectAll("path.mt-area").data(parte("mt", "area")).join("path").attr("class", "mt-area");
  const mtL = gMt.selectAll("path.mt-lim").data([...parte("mt", "limite"), ...parte("mt", "base")]).join("path")
    .attr("class", d => d.properties.parte === "base" ? "mt-base" : "mt-lim");
  const MAR = [pceA, pceL, zeeA, zeeL, zcA, zcL, mtA, mtL];
  const states = root.append("g").selectAll("path").data(estados.features).join("path")
    .attr("class", "st").attr("tabindex", 0).attr("aria-label", d => d.properties.name)
    .on("click", (e, d) => { e.stopPropagation(); select(d.properties.sigla); })
    .on("keydown", (e, d) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(d.properties.sigla); } });
  const clipBr = defs.append("clipPath").attr("id", "clip-br").attr("clipPathUnits", "userSpaceOnUse").append("path");
  const imgSombra = REL && REL.sombra ? root.append("image").attr("class", "relevo-sombra").attr("href", "../data/relevo/" + REL.sombra.arquivo)
    .attr("preserveAspectRatio", "none").attr("clip-path", "url(#clip-br)") : null;
  states.append("title").text(d => d.properties.name);
  const gCampos = root.append("g");
  const camposP = gCampos.selectAll("path").data(DATA.campos ? DATA.campos.features : []).join("path").attr("class", "campo");
  camposP.append("title").text(d => { const p = d.properties;
    return `Campo ${p.nome} · ${p.etapa}${p.fluido ? " · " + p.fluido : ""}${p.operador ? ". Operador: " + p.operador : ""}${p.bacia ? ". Bacia " + p.bacia : ""}${p.inicio ? ", produção desde " + p.inicio : ""}. Fonte: ANP.`; });
  const gPresal = root.append("g");
  const presalP = gPresal.selectAll("path").data(parte("presal", "area")).join("path").attr("class", "presal");
  const presalT = gPresal.selectAll("text").data(parte("presal", "rotulo")).join("text").attr("class", "presal-lbl").text(d => d.properties.texto);
  const gRod = root.append("g");
  const roads = gRod.selectAll("path").data(DATA.rod ? DATA.rod.features : []).join("path")
    .attr("class", d => d.properties.type === "Major Highway" ? "road major" : "road");
  const RAIL = DATA.rail ? DATA.rail.trechos : [];
  const gRail = root.append("g");
  const rails = gRail.selectAll("path").data(RAIL).join("path").attr("class", "rail");
  /* poços em produção: [lon, lat, boe/dia, barris/dia, mil m³ de gás/dia, poço, campo, UF, mar/terra] */
  const POCOS = DATA.oil && DATA.oil.pocos ? DATA.oil.pocos.map(p => ({ c: [p[0], p[1]], b: p[2], o: p[3], g: p[4], n: p[5], campo: p[6], u: p[7], a: p[8],
    r0: Math.max(0.9, Math.min(9, 0.9 + Math.sqrt(p[2]) * 0.034)) })) : [];
  const gPocos = root.append("g");
  const pocosC = gPocos.selectAll("circle").data(POCOS).join("circle").attr("class", "poco");
  pocosC.append("title").text(d => `Poço ${d.n} · campo ${d.campo} · ${d.a === "M" ? "mar" : "terra"}${d.u ? " · " + d.u : ""}. Petróleo: ${fmt(Math.round(d.o))} barris/dia; gás: ${fmt1(d.g)} mil m³/dia; total ${fmt(Math.round(d.b))} boe/dia (ANP, média de ${DATA.oil.meta.referencia}).`);
  const gUep = root.append("g");
  const uepR = gUep.selectAll("rect").data(DATA.uep ? DATA.uep.features : []).join("rect").attr("class", d => d.properties.prevista ? "uep prev" : "uep");
  uepR.append("title").text(d => { const p = d.properties;
    return `${p.nome} · ${p.tipo}${p.operador ? " · " + p.operador : ""}${p.prevista ? " · prevista" : ""}${p.atende ? ". Atende: " + p.atende : ""}${p.capacidade_bbl_dia ? ". Capacidade: " + fmt(p.capacidade_bbl_dia) + " barris de petróleo/dia" : ""}. Fonte: ANP.`; });
  const gPorts = root.append("g");
  const ports = gPorts.selectAll("circle").data(DATA.ports || []).join("circle").attr("class", "port");
  ports.append("title").text(d => "Porto: " + d.n);
  const gAir = root.append("g");
  const airs = gAir.selectAll("path").data(DATA.air || []).join("path").attr("class", "air").attr("d", d3.symbol(d3.symbolTriangle, 40));
  airs.append("title").text(d => `Aeroporto: ${d.n}${d.i ? " (" + d.i + ")" : ""}`);
  const CLA = F.camadas.find(l => l.id === "cla");
  const gCla = root.append("g");
  gCla.append("circle").attr("class", "pulse").attr("r", 9);
  gCla.append("circle").attr("class", "cla").attr("r", 7);
  gCla.append("circle").attr("class", "cla-dot").attr("r", 2.5);
  gCla.append("title").text(CLA ? CLA.nome : "");
  /* nomes: sigla dos estados (nome completo com zoom) e capitais (nome com zoom) */
  const gNomes = root.append("g").attr("class", "nomes");
  const ufLbl = gNomes.selectAll("text.uf").data(ROT.estados).join("text").attr("class", d => "uf uf-" + d.s);
  ufLbl.append("tspan").attr("class", "s").text(d => d.s);
  ufLbl.append("tspan").attr("class", "n").text(d => d.n);
  const caps = gNomes.selectAll("g.cap").data(ROT.capitais).join("g").attr("class", d => d.pais ? "cap pais" : "cap");
  caps.append("circle").attr("r", d => d.pais ? 3.6 : 2.6);
  caps.append("text").attr("x", 6).attr("y", 4).text(d => d.n);
  const G = { zee: gZee, mt: gMt, zc: gZc, pce: gPce, rod: gRod, rail: gRail, ports: gPorts, air: gAir, cla: gCla,
    oil: gPocos, uep: gUep, campos: gCampos, presal: gPresal };

  let proj, path, W, H, head = 0, k = 1;
  const zoom = d3.zoom().scaleExtent([0.55, 12]).on("zoom", e => {
    root.attr("transform", e.transform); k = e.transform.k; place();
  }).on("end", raioPocos);   /* são milhares de poços: o tamanho deles só é refeito quando o zoom termina */
  svg.call(zoom).on("dblclick.zoom", null);

  /* painel lateral: pode ser recolhido no computador para ver só o mapa */
  const dock = document.querySelector(".dock"), unfold = document.getElementById("unfold");
  const espacoPainel = () => innerWidth > 900 && !dock.hidden ? dock.offsetWidth + 40 : 0;
  function mostrarPainel(abrir, refazer = true) {
    dock.hidden = !abrir; unfold.hidden = abrir;
    try { localStorage.setItem("bec-painel", abrir ? "aberto" : "recolhido"); } catch (e) {}
    if (refazer) layout();
    (abrir ? document.getElementById("fold") : unfold).focus({ preventScroll: true });
  }
  document.getElementById("fold").onclick = () => mostrarPainel(false);
  unfold.onclick = () => mostrarPainel(true);
  try { if (innerWidth > 900 && localStorage.getItem("bec-painel") === "recolhido") { dock.hidden = true; unfold.hidden = false; } } catch (e) {}

  function layout() {
    const r = svg.node().getBoundingClientRect();
    W = Math.max(320, r.width); H = Math.max(320, r.height);
    svg.attr("viewBox", `0 0 ${W} ${H}`);
    const wide = innerWidth > 900;
    if (!wide && dock.hidden) mostrarPainel(true, false);
    const dockW = espacoPainel();
    const pad = wide ? 30 : 12;
    head = wide ? document.getElementById("top").offsetHeight : 0;
    stage.style.setProperty("--head", (head + 4) + "px");
    const fc = { type: "FeatureCollection", features: [...estados.features, ...parte("zee", "area")] };
    proj = d3.geoMercator().fitExtent([[pad + (wide ? 40 : 0), head + (wide ? 44 : 24)], [W - dockW - pad, H - (wide ? 50 : 12)]], fc);
    path = d3.geoPath(proj);
    gGrat.datum(d3.geoGraticule().step([5, 5])()).attr("d", path);
    MAR.forEach(sel => sel.attr("d", path));
    camposP.attr("d", path); presalP.attr("d", path);
    pocosC.attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
    raioPocos();
    roads.attr("d", path);
    states.attr("d", path);
    vizP.attr("d", path); vizB.attr("d", path);
    clipBr.attr("d", path(estados));
    const encaixa = (img, r) => { if (!img) return; const [x0, y0] = proj([r.oeste, r.norte]), [x1, y1] = proj([r.leste, r.sul]);
      img.attr("x", x0).attr("y", y0).attr("width", x1 - x0).attr("height", y1 - y0); };
    if (REL) { encaixa(imgMundo, REL.mundo); encaixa(imgCor, REL.cor); encaixa(imgSombra, REL.sombra); }
    /* trava: não dá para arrastar além do mapa-múndi */
    const [[wx0, wy0], [wx1, wy1]] = path.bounds({ type: "FeatureCollection", features: [...(viz ? viz.features : []), ...estados.features] });
    zoom.translateExtent([[wx0 - 60, wy0 - 60], [wx1 + 60, wy1 + 60]]).extent([[0, 0], [W, H]]);
    flowP.attr("d", correntes());
    rails.attr("d", d => path({ type: "LineString", coordinates: d.l }));
    if (CLA) gCla.attr("data-x", proj(CLA.ponto)[0]).attr("data-y", proj(CLA.ponto)[1]);
    place();
    svg.call(zoom.transform, d3.zoomIdentity);
    if (sel) zoomTo(estados.features.find(f => f.properties.sigla === sel), 0);
  }
  /* correntes oceânicas decorativas: linhas que seguem um campo de ondas, só na região do Atlântico Sul */
  function correntes() {
    const a = proj([-105, 32]), b = proj([25, -62]);
    const ang = (x, y) => 1.9 * Math.sin(x * .0042 + Math.cos(y * .0061) * 1.7) + 1.1 * Math.cos(y * .0037 - x * .0021);
    let d = "", step = 7, gap = 46, rnd = d3.randomLcg(42);
    for (let y0 = a[1]; y0 < b[1]; y0 += gap) for (let x0 = a[0]; x0 < b[0]; x0 += gap) {
      let x = x0 + rnd() * gap, y = y0 + rnd() * gap; d += `M${x.toFixed(1)},${y.toFixed(1)}`;
      for (let i = 0; i < 26; i++) { const t = ang(x, y); x += Math.cos(t) * step; y += Math.sin(t) * step; d += `L${x.toFixed(1)},${y.toFixed(1)}`; }
    }
    return d;
  }
  function raioPocos() { const s = 1 / Math.sqrt(k); pocosC.attr("r", d => d.r0 * s); }
  /* pontos mantêm tamanho legível em qualquer zoom */
  function place() {
    const s = 1 / Math.sqrt(k);
    lbls.attr("transform", d => `translate(${proj(d.c)}) scale(${1 / k})`);
    const z = `scale(${1 / k})`;
    zeeTxt.attr("transform", `translate(${proj([-31.2, -15.5])}) rotate(-62) ${z}`);
    ilhas.attr("transform", d => `translate(${proj(d.c)}) ${z}`);
    pceT.attr("transform", d => `translate(${proj(d.geometry.coordinates)}) ${z}`);
    presalT.attr("transform", d => `translate(${proj(d.geometry.coordinates)}) ${z}`);
    const lu = 7 / Math.sqrt(k);
    uepR.attr("x", d => proj(d.geometry.coordinates)[0] - lu / 2).attr("y", d => proj(d.geometry.coordinates)[1] - lu / 2).attr("width", lu).attr("height", lu);
    ufLbl.attr("transform", d => `translate(${proj(d.c)}) ${z}`);
    caps.attr("transform", d => `translate(${proj(d.c)}) ${z}`);
    gNomes.classed("z-cap", k >= 1.9).classed("z-nome", k >= 3.2);
    ports.attr("r", 3.6 * s).attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
    airs.attr("transform", d => `translate(${proj(d.c)}) scale(${s})`);
    if (CLA) { const p = proj(CLA.ponto); gCla.selectAll("circle").attr("cx", 0).attr("cy", 0); gCla.attr("transform", `translate(${p}) scale(${s})`); }
  }
  function zoomTo(feature, dur = 1100) {
    const [[x0, y0], [x1, y1]] = path.bounds(feature);
    const usableW = W - espacoPainel();
    const s = Math.min(10, 0.8 / Math.max((x1 - x0) / usableW, (y1 - y0) / (H - head)));
    const t = d3.zoomIdentity.translate(usableW / 2, (H + head) / 2).scale(s).translate(-(x0 + x1) / 2, -(y0 + y1) / 2);
    svg.transition().duration(reduce ? 0 : dur).ease(d3.easeCubicInOut).call(zoom.transform, t);
  }
  function reset() {
    sel = null;
    svg.transition().duration(reduce ? 0 : 900).ease(d3.easeCubicInOut).call(zoom.transform, d3.zoomIdentity);
    render(); ficha();
  }
  function select(s) {
    if (sel === s) { reset(); return; }
    sel = s; zoomTo(estados.features.find(f => f.properties.sigla === s)); render(); ficha();
  }
  document.getElementById("back").onclick = reset;
  document.getElementById("center").onclick = () => {
    if (sel) zoomTo(estados.features.find(f => f.properties.sigla === sel), 800);
    else svg.transition().duration(reduce ? 0 : 800).ease(d3.easeCubicInOut).call(zoom.transform, d3.zoomIdentity);
  };
  svg.on("click", e => { if (e.target === svg.node() && sel) reset(); });

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
    "p-rod": "M8 21L10 3M16 21L14 3M12 6v2M12 11v2M12 16v2",
    "p-ene": "M13 2L5 14h6l-1 8 8-12h-6z"
  };
  const quando = id => { const m = DATA[id] && DATA[id].meta; return m && m.atualizado_em ? ` · ${m.referencia ? "ref. " + esc(m.referencia) + ", " : ""}atualizado em ${m.atualizado_em}` : ""; };
  const icon = id => ICON[id] ? `<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="${ICON[id]}"/></svg>` : `<span class="ico"></span>`;

  /* ---------- filtro por ministério ---------- */
  const mins = document.getElementById("mins");
  mins.insertAdjacentHTML("beforeend", [["todos", "Todos"], ...Object.entries(F.ministerios)]
    .map(([k, v]) => `<button class="tab" data-m="${k}" aria-pressed="${k === "todos"}">${v}</button>`).join(""));
  mins.querySelectorAll(".tab").forEach(b => b.onclick = () => {
    minF = b.dataset.m;
    mins.querySelectorAll(".tab").forEach(x => x.setAttribute("aria-pressed", x === b));
    LAYERS.forEach(l => { if (l.nivel !== "pendente") l.on = minF === "todos" ? !!l.ligada : l.ministerio === minF; });
    const p = PAINT.find(p => p.ministerio === minF && p.ok);
    paint = minF === "todos" ? "pop" : (p ? p.id : "none");
    render();
  });

  function controls() {
    const pv = PAINT.filter(p => p.id === "none" || minF === "todos" || p.ministerio === minF);
    document.getElementById("paint").innerHTML = pv.map(p =>
      `<button class="chip" data-p="${p.id}" aria-pressed="${paint === p.id}" ${p.id !== "none" && !p.ok ? "disabled title=\"Em apuração\"" : ""}>${p.nome}</button>`).join("");
    document.querySelectorAll("#paint .chip:not([disabled])").forEach(b => b.onclick = () => { paint = b.dataset.p; render(); });
    const lv = LAYERS.filter(l => minF === "todos" || l.ministerio === minF);
    document.getElementById("layers").innerHTML = lv.length ? lv.map(l => `
      <label class="layer ${l.nivel === "pendente" ? "pend" : ""}">
        <input type="checkbox" id="ly-${l.id}" ${l.on ? "checked" : ""} ${l.nivel === "pendente" ? "disabled" : ""}>${icon(l.id)}
        <span><span class="nm">${l.cor ? `<i class="key" style="background:var(${l.cor})"></i>` : ""}${l.nome} ${pill(l.nivel)}</span>
        <span class="src">${l.fonte}${quando(l.id)} · ${F.ministerios[l.ministerio]}</span></span>
      </label>`).join("") : `<p class="note">Este ministério ainda não tem camadas de mapa.</p>`;
    lv.filter(l => l.nivel !== "pendente").forEach(l => document.getElementById("ly-" + l.id).onchange = e => { l.on = e.target.checked; render(); });
  }

  /* ---------- desenho ---------- */
  function render() {
    controls();
    LAYERS.filter(l => G[l.id]).forEach(l => G[l.id].attr("display", l.on ? null : "none"));
    const P = PAINT.find(p => p.id === paint);
    let leg = "";
    if (P && P.val) {
      const vals = Object.keys(NAME).map(P.val).filter(v => v != null);
      const q = d3.scaleQuantile().domain(vals).range(RAMP);
      states.style("fill", d => { const v = P.val(d.properties.sigla); return v == null ? (P.vazio ? "var(--sem)" : null) : `var(${q(v)})`; });
      const D = DATA[P.id];
      leg = `<span>${P.nome}${D.unidade ? " (" + D.unidade + ")" : ""}</span><span>${P.fmt(d3.min(vals))}</span>
        <span class="ramp">${RAMP.map(c => `<i style="background:var(${c})"></i>`).join("")}</span><span>${P.fmt(d3.max(vals))}</span>
        ${vals.length < 27 ? (P.vazio ? `<span><i class="key sq" style="background:var(--sem)"></i>${P.vazio}</span>` : "<span>sem cor = sem dado</span>") : ""}`;
    } else states.style("fill", null);
    leg += LAYERS.filter(l => l.on && l.cor).map(l => (l.legenda || [{ nome: l.nome }]).map(k => {
      const forma = k.forma || (k.hachura ? "hach" : ""), contorno = ["hach", "sqv", "tr"].includes(forma);
      return `<span><i class="key ${forma}" style="${contorno ? "color" : "background"}:var(${k.cor || l.cor})"></i>${k.nome}</span>`;
    }).join("")).join("");
    document.getElementById("legend").innerHTML = leg;
    states.classed("sel", d => d.properties.sigla === sel).classed("fade", d => sel && d.properties.sigla !== sel);
    states.filter(".sel").raise();
    rails.classed("hi", d => sel && d.uf === sel).classed("off", d => sel && d.uf !== sel);
    document.getElementById("back").hidden = !sel;
    document.getElementById("where").textContent = sel ? `${NAME[sel]} · ${sel}` : "Brasil · 27 UFs";
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

  function ficha() {
    const el = document.getElementById("ficha");
    const popInfo = DATA.pop ? `${pill(DATA.pop.nivel)} <span class="note">${DATA.pop.fonte} · atualizado em ${DATA.pop.atualizado_em}</span>` : pill("pendente");
    if (!sel) {
      el.innerHTML = `<h2>Visão nacional</h2><div class="fname">Brasil</div>
        <div class="kv"><span>População</span><span class="v">${fmt(popTot)}</span></div>${popInfo}
        ${DATA.oleo ? `<div class="kv" style="margin-top:8px"><span>Petróleo e gás</span><span class="v">${fmt1(DATA.oleo.total_boe_dia / 1e6)} milhões de boe/dia</span></div>
          ${pill(DATA.oleo.nivel)} <span class="note">ANP, média de ${esc(DATA.oleo.referencia)} · atualizado em ${DATA.oleo.atualizado_em}. boe = barril de óleo equivalente.</span>` : ""}
        <p class="lede">Clique num estado para aproximar. Cada camada mostra de onde veio o dado e seu nível de confiança. Arraste para mover e role para aproximar.</p>`;
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
      ${fichaOleo(s)}
      ${CLA && s === CLA.uf ? `<div class="sec"><h3>Defesa</h3><div class="list">${CLA.nome}, base de lançamento de foguetes da Força Aérea.</div>${pill("calculado")} <span class="note">posição aproximada</span></div>` : ""}
      <div class="sec"><h3>Mobilidade elétrica</h3>
        <div class="kv"><span>Eletropostos</span><span class="v">${ev ? fmt(ev.valor) : "—"}</span></div>
        ${ev ? `${pill("entidade")} <span class="note">${ev.fonte}, ref. ${ev.referencia}</span>` : `${pill("pendente")} <span class="note">Nenhum número publicado encontrado.</span>`}</div>`;
  }

  /* botão de apoio no rodapé: só aparece quando há link em fontes.json */
  const AP = F.apoio, apoio = document.getElementById("apoio");
  if (AP && AP.link && apoio) {
    apoio.innerHTML = `<a class="apoiar" href="${esc(AP.link)}" target="_blank" rel="noopener"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.6-7 10-7 10z"/></svg>${esc(AP.texto)}</a>
      ${AP.nota ? `<span class="note">${esc(AP.nota)}</span>` : ""}`;
    apoio.hidden = false;
  }
  document.getElementById("tiers").innerHTML = Object.values(NIVEL)
    .map(([c, t, d]) => `<div><span><span class="pill ${c}">${t}</span></span><span>${d}</span></div>`).join("");

  /* ---------- abertura ---------- */
  layout(); render(); ficha();
  let rt; addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(layout, 150); });
  if (!reduce) {
    states.style("opacity", 0).transition().delay(d => 150 + path.centroid(d)[0] * 1.1).duration(700).style("opacity", 1)
      .on("end", function () { d3.select(this).style("opacity", null); });
    zeeL.each(function () {
      const el = d3.select(this), L = this.getTotalLength();
      el.style("stroke-dasharray", `${L} ${L}`).style("stroke-dashoffset", L)
        .transition().delay(500).duration(2200).ease(d3.easeCubicOut).style("stroke-dashoffset", 0)
        .on("end", () => el.style("stroke-dasharray", null).style("stroke-dashoffset", null));
    });
    rails.style("opacity", 0).transition().delay(1400).duration(900).style("opacity", 0.85)
      .on("end", function () { d3.select(this).style("opacity", null); });
  }
})();
