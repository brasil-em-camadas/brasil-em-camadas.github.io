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
const reais = mil => mil >= 1e6 ? `R$ ${fmt1(mil / 1e6)} bi` : mil >= 1e3 ? `R$ ${fmt(Math.round(mil / 1e3))} mi` : `R$ ${fmt(Math.round(mil))} mil`;
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
  const DATA = {}, UNICO = {};
  /* camadas "sob_demanda" (arquivos grandes que começam desligados) só são baixadas quando alguém liga a camada */
  await Promise.all([...F.pintura, ...F.camadas].filter(l => l.arquivo && !l.sob_demanda).map(async l => {
    DATA[l.id] = await (UNICO[l.arquivo] || (UNICO[l.arquivo] = getJSON("../data/" + l.arquivo)));
    if (!DATA[l.id] && l.nivel) l.nivel = "pendente";
  }));
  /* camadas do mar: cada arquivo traz a área ("area"), as linhas de limite ("limite", "base") e os rótulos */
  const parte = (id, p) => DATA[id] && DATA[id].features ? DATA[id].features.filter(f => f.properties.parte === p) : [];
  ["zee", "mt", "presal"].forEach(id => parte(id, "area").forEach(rewind));   /* as camadas sob demanda acertam o sentido ao chegar */
  const POP = DATA.pop ? DATA.pop.valores : {};
  const popTot = Object.values(POP).reduce((a, b) => a + b, 0);

  const PAINT = [{ id: "none", nome: "Sem cor" }, ...F.pintura.map(p => ({
    ...p, ok: !!DATA[p.id],
    nivel: DATA[p.id] ? DATA[p.id].nivel : "pendente",
    val: !DATA[p.id] ? null
      : p.por === "per_capita" ? s => (DATA[p.id].valores[s] && POP[s]) ? DATA[p.id].valores[s].valor / POP[s] * 1e5 : null
      : s => { const v = DATA[p.id].valores[s]; return v == null ? null : (typeof v === "object" ? (v[p.campo || "valor"] ?? null) : v); },
    fmt: p.por === "per_capita" || p.por === "percentual" ? fmt1 : fmt,
    unidade: p.unidade || (DATA[p.id] && DATA[p.id].unidade) || ""
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
  /* camadas sob demanda (zona contígua, plataforma estendida, poços, plataformas, campos, rebanho): começam vazias
     e são desenhadas quando o arquivo chega (ver baixarSobDemanda e DESENHA, mais abaixo) */
  let pceA = gPce.selectAll("path.pce-area"), pceL = gPce.selectAll("path.pce-lim"), pceT = gPce.selectAll("text");
  function desenharPce() {
    parte("pce", "area").forEach(rewind);
    pceA = gPce.selectAll("path.pce-area").data(parte("pce", "area")).join("path").attr("class", d => "pce-area " + d.properties.status);
    pceA.append("title").text(d => `Plataforma continental estendida · ${d.properties.nome}: ${d.properties.situacao}. ` +
      `Área no desenho ≈ ${kmTxt(d.properties.area_km2)}; Marinha: ${d.properties.area_marinha}. ${d.properties.fonte_curta}. Sem valor legal.`);
    pceL = gPce.selectAll("path.pce-lim").data(parte("pce", "limite")).join("path").attr("class", d => "pce-lim " + d.properties.status);
    pceT = gPce.selectAll("text").data(parte("pce", "rotulo")).join("text").attr("class", "pce-lbl")
      .each(function (d) { const p = d.properties.texto.split("\n"); d3.select(this).selectAll("tspan").data(p).join("tspan").attr("x", 0).attr("dy", (_, i) => i ? "1.25em" : "-0.3em").text(t => t); });
  }
  const gZee = root.append("g");
  const zeeA = gZee.selectAll("path.zee-area").data(parte("zee", "area")).join("path").attr("class", "zee-area");
  const zeeL = gZee.selectAll("path.zee-lim").data(parte("zee", "limite")).join("path").attr("class", "zee-lim");
  const zeeTxt = gZee.append("text").attr("class", "zee-lbl").text("Zona Econômica Exclusiva · 200 milhas");
  const ilhas = gZee.append("g").selectAll("g").data(ROT.ilhas || []).join("g").attr("class", "ilha");
  ilhas.append("circle").attr("r", 2.4);
  ilhas.append("text").attr("x", d => d.dx).attr("y", d => d.dy).attr("text-anchor", d => d.a).text(d => d.n);
  ilhas.append("title").text(d => d.nome_completo);
  const gZc = root.append("g");
  let zcA = gZc.selectAll("path.zc-area"), zcL = gZc.selectAll("path.zc-lim");
  function desenharZc() {
    parte("zc", "area").forEach(rewind);
    zcA = gZc.selectAll("path.zc-area").data(parte("zc", "area")).join("path").attr("class", "zc-area");
    zcL = gZc.selectAll("path.zc-lim").data(parte("zc", "limite")).join("path").attr("class", "zc-lim");
  }
  const gMt = root.append("g");
  const mtA = gMt.selectAll("path.mt-area").data(parte("mt", "area")).join("path").attr("class", "mt-area");
  const mtL = gMt.selectAll("path.mt-lim").data([...parte("mt", "limite"), ...parte("mt", "base")]).join("path")
    .attr("class", d => d.properties.parte === "base" ? "mt-base" : "mt-lim");
  const MAR = () => [pceA, pceL, zeeA, zeeL, zcA, zcL, mtA, mtL];
  const states = root.append("g").selectAll("path").data(estados.features).join("path")
    .attr("class", "st").attr("tabindex", 0).attr("aria-label", d => d.properties.name)
    .on("click", (e, d) => { e.stopPropagation(); select(d.properties.sigla); })
    .on("keydown", (e, d) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(d.properties.sigla); } });
  const clipBr = defs.append("clipPath").attr("id", "clip-br").attr("clipPathUnits", "userSpaceOnUse").append("path");
  const imgSombra = REL && REL.sombra ? root.append("image").attr("class", "relevo-sombra").attr("href", "../data/relevo/" + REL.sombra.arquivo)
    .attr("preserveAspectRatio", "none").attr("clip-path", "url(#clip-br)") : null;
  states.append("title").text(d => d.properties.name);
  const gCampos = root.append("g");
  let camposP = gCampos.selectAll("path");
  function desenharCampos() {
    DATA.campos.features.forEach(rewind);
    camposP = gCampos.selectAll("path").data(DATA.campos.features).join("path").attr("class", "campo");
    camposP.append("title").text(d => { const p = d.properties;
      return `Campo ${p.nome} · ${p.etapa}${p.fluido ? " · " + p.fluido : ""}${p.operador ? ". Operador: " + p.operador : ""}${p.bacia ? ". Bacia " + p.bacia : ""}${p.inicio ? ", produção desde " + p.inicio : ""}. Fonte: ANP.`; });
  }
  const gPresal = root.append("g");
  const presalP = gPresal.selectAll("path").data(parte("presal", "area")).join("path").attr("class", "presal");
  const presalT = gPresal.selectAll("text").data(parte("presal", "rotulo")).join("text").attr("class", "presal-lbl").text(d => d.properties.texto);
  /* rodovias (IBGE, BC250): estaduais pavimentadas sob demanda, por baixo; federais com traço cheio (pavimentadas,
     ou tracejado (sem pavimento) */
  const gRodEst = root.append("g");
  let rodEstP = gRodEst.selectAll("path");
  function desenharRodEst() { rodEstP = gRodEst.selectAll("path").data(DATA.rodest.features).join("path").attr("class", "road est"); }
  const gRod = root.append("g");
  const roads = gRod.selectAll("path").data(DATA.rod ? DATA.rod.features : []).join("path")
    .attr("class", d => "road" + (d.properties.p ? "" : " terra") + (d.properties.e ? " est-adm" : ""));
  const RAIL = DATA.rail ? DATA.rail.trechos : [];
  const gRail = root.append("g");
  const rails = gRail.selectAll("path").data(RAIL).join("path").attr("class", d => "rail" + (d.obra ? " obra" : ""));
  rails.append("title").text(d => `Ferrovia${d.obra ? " em obras" : ""} · ${d.op}${d.b ? " · bitola " + d.b.toLowerCase() : ""}${d.si ? " · a base não informa se está em operação" : ""} (IBGE, BC250 2025)`);
  /* linhas de transmissão (EPE), sob demanda: mais grossas quanto maior a tensão */
  const gLt = root.append("g");
  let ltP = gLt.selectAll("path");
  function desenharLt() {
    ltP = gLt.selectAll("path").data(DATA.lt.features).join("path").attr("class", "lt")
      .style("stroke-width", d => (0.5 + Math.max(0, d.properties.kv - 230) / 570 * 1.5).toFixed(2));
  }
  /* subestações (EPE), sob demanda: losango, maior quanto mais alta a tensão */
  const gSe = root.append("g");
  let seP = gSe.selectAll("path");
  function desenharSe() {
    seP = gSe.selectAll("path").data(DATA.se.features.map(f => ({ ...f.properties, c: f.geometry.coordinates }))).join("path").attr("class", "se")
      .attr("d", d => d3.symbol(d3.symbolDiamond, d.kv >= 700 ? 46 : d.kv >= 440 ? 30 : 18)());
    seP.append("title").text(d => `${d.n} · subestação ${d.t} kV${d.ano ? ", em operação desde " + d.ano : ""}${d.c ? ". " + d.c : ""} (EPE).`);
  }
  /* gasodutos e oleodutos (ANP), sob demanda */
  const gDutos = root.append("g");
  let dutosP = gDutos.selectAll("path");
  function desenharDutos() {
    dutosP = gDutos.selectAll("path").data(DATA.dutos.features).join("path")
      .attr("class", d => "duto " + d.properties.f + (d.properties.t === "transporte" ? "" : " fino"));
  }
  /* poços em produção: [lon, lat, boe/dia, barris/dia, mil m³ de gás/dia, poço, campo, UF, mar/terra] */
  /* rebanho bovino por município: desenhado quando o arquivo chega (camada sob demanda) */
  const gBoi = root.append("g");
  let boiC = gBoi.selectAll("circle");
  const posBoi = () => boiC.attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
  function desenharBoi() {
    const M = DATA.boi;
    boiC = gBoi.selectAll("circle").data(M.municipios.map(m => ({ c: [m[0], m[1]], b: m[2], n: m[3], u: m[4],
      r0: Math.max(0.6, Math.min(8, 0.6 + Math.sqrt(m[2]) * 0.0045)) }))).join("circle").attr("class", "boi");
    boiC.on("click", (e, d) => { e.stopPropagation(); select(d.u); });   /* clicar num ponto abre o estado dele */
    boiC.append("title").text(d => `${d.n} · ${d.u}: ${fmt(d.b)} cabeças de gado bovino (IBGE, Pesquisa da Pecuária Municipal ${M.meta.referencia}). O ponto fica na sede do município.`);
  }
  /* principal lavoura de cada município (IBGE, PAM), sob demanda: cor pela lavoura, tamanho pelo valor de todas as lavouras */
  const gLav = root.append("g");
  let lavC = gLav.selectAll("circle");
  function desenharLav() {
    const M = DATA.lav;
    lavC = gLav.selectAll("circle").data(M.municipios.map(m => ({ c: [m[0], m[1]], v: m[2], g: m[3], p: m[4], pv: m[5], n: m[6], u: m[7],
      r0: Math.max(0.6, Math.min(9, 0.6 + Math.sqrt(m[2]) * 0.0028)) }))).join("circle").attr("class", d => "lav g-" + d.g);
    lavC.on("click", (e, d) => { e.stopPropagation(); select(d.u); });
    lavC.append("title").text(d => `${d.n} · ${d.u}: principal lavoura ${d.p} (${reais(d.pv)}, ${fmt(Math.round(d.pv / d.v * 100))}% do valor); todas as lavouras ${reais(d.v)} (IBGE, Produção Agrícola Municipal ${M.meta.referencia}). O ponto fica na sede do município.`);
  }
  /* usinas de energia (EPE), sob demanda: cor pela fonte, tamanho pela potência; clicar abre o estado */
  const gUsinas = root.append("g");
  let usinasC = gUsinas.selectAll("circle");
  function desenharUsinas() {
    const M = DATA.usinas.meta;
    usinasC = gUsinas.selectAll("circle").data(DATA.usinas.usinas.map(u => ({ c: [u[0], u[1]], kw: u[2], t: u[3], n: u[4], uf: u[5], a: u[6], d: u[7], x: u[8],
      r0: Math.max(0.8, Math.min(11, 0.8 + Math.sqrt(u[2]) * 0.0028)) }))).join("circle").attr("class", d => "usina t-" + d.t);
    usinasC.on("click", (e, d) => { e.stopPropagation(); if (d.uf) select(d.uf); });
    usinasC.append("title").text(d => `${d.n} · ${M.tipos[d.t]} · ${fmt1(d.kw / 1000)} MW${d.uf ? " · " + d.uf : ""}${d.a ? ". Em operação desde " + d.a : ""}`
      + `${(M.observacoes || {})[d.n] ? ". " + M.observacoes[d.n] : ""} (EPE, Webmap; ${M.referencia}).`);
  }
  /* telefonia celular (Anatel), sob demanda: sinal 4G/5G por município (cor pela faixa) e anel nos municípios com 5G;
     clicar num ponto abre o estado dele */
  const FAIXA = s => s >= 95 ? 4 : s >= 80 ? 3 : s >= 50 ? 2 : 1;
  const gCelm = root.append("g");
  let celmC = gCelm.selectAll("circle");
  function desenharCelm() {
    const M = DATA.celm;
    celmC = gCelm.selectAll("circle").data(M.municipios.map(m => ({ c: [m[0], m[1]], s: m[2], n: m[3], u: m[4], r0: 1.5 }))).join("circle")
      .attr("class", d => "celm f" + FAIXA(d.s));
    celmC.on("click", (e, d) => { e.stopPropagation(); select(d.u); });
    celmC.append("title").text(d => `${d.n} · ${d.u}: sinal 4G ou 5G para ${fmt1(d.s)}% da população (estimativa da Anatel, IBC ${M.meta.referencia}). O ponto fica na sede do município.`);
  }
  const gG5 = root.append("g");
  let g5C = gG5.selectAll("circle");
  function desenharG5() {
    const M = DATA.g5;
    g5C = gG5.selectAll("circle").data(M.municipios.map(m => ({ c: [m[0], m[1]], n: m[2], u: m[3], o: m[4], r0: 2.3 }))).join("circle").attr("class", "g5");
    g5C.on("click", (e, d) => { e.stopPropagation(); select(d.u); });
    g5C.append("title").text(d => `${d.n} · ${d.u}: 5G de ${d.o} (Anatel, ${M.meta.referencia}). Não quer dizer sinal 5G em todo o município.`);
  }
  /* indústria de defesa (Ministério da Defesa), sob demanda: escudo na sede do município, maior = mais empresas credenciadas;
     clicar abre o estado */
  const ESCUDO = { draw(c, size) { const r = Math.sqrt(size) / 2;
    c.moveTo(-r, -r); c.lineTo(r, -r); c.lineTo(r, r * 0.2); c.quadraticCurveTo(r * 0.9, r * 0.95, 0, r * 1.3); c.quadraticCurveTo(-r * 0.9, r * 0.95, -r, r * 0.2); c.closePath(); } };
  const gDef = root.append("g");
  let defP = gDef.selectAll("path");
  function desenharDef() {
    const M = DATA.empdef;
    /* os de mais empresas vêm primeiro no arquivo e ficam por baixo */
    defP = gDef.selectAll("path").data(M.municipios.map(m => ({ c: [m[0], m[1]], n: m[2], u: m[3], es: m[5] }))).join("path").attr("class", "edef")
      .attr("d", d => d3.symbol(ESCUDO, Math.pow(2.6 + 1.9 * Math.sqrt(d.es.length), 2))());
    defP.on("click", (e, d) => { e.stopPropagation(); select(d.u); });
    defP.append("title").text(d => { const eed = d.es.filter(x => x[1] === "EED").length, ed = d.es.length - eed;
      return `${d.n} · ${d.u}: ${d.es.length} ${d.es.length > 1 ? "empresas credenciadas" : "empresa credenciada"} pelo Ministério da Defesa (${eed} EED, ${ed} ED): `
        + d.es.slice(0, 8).map(x => x[0]).join("; ") + (d.es.length > 8 ? `; e mais ${d.es.length - 8}` : "")
        + `. ${M.meta.referencia}. O ponto fica na sede do município, não no endereço da empresa.`; });
  }
  const gPocos = root.append("g");
  let pocosC = gPocos.selectAll("circle");
  function desenharPocos() {
    const POCOS = DATA.oil.pocos.map(p => ({ c: [p[0], p[1]], b: p[2], o: p[3], g: p[4], n: p[5], campo: p[6], u: p[7], a: p[8],
      r0: Math.max(0.9, Math.min(9, 0.9 + Math.sqrt(p[2]) * 0.034)) }));
    pocosC = gPocos.selectAll("circle").data(POCOS).join("circle").attr("class", "poco");
    pocosC.append("title").text(d => `Poço ${d.n} · campo ${d.campo} · ${d.a === "M" ? "mar" : "terra"}${d.u ? " · " + d.u : ""}. Petróleo: ${fmt(Math.round(d.o))} barris/dia; gás: ${fmt1(d.g)} mil m³/dia; total ${fmt(Math.round(d.b))} boe/dia (ANP, média de ${DATA.oil.meta.referencia}).`);
  }
  const gUep = root.append("g");
  let uepR = gUep.selectAll("rect");
  function desenharUep() {
    uepR = gUep.selectAll("rect").data(DATA.uep.features).join("rect").attr("class", d => d.properties.prevista ? "uep prev" : "uep");
    uepR.append("title").text(d => { const p = d.properties;
      return `${p.nome} · ${p.tipo}${p.operador ? " · " + p.operador : ""}${p.prevista ? " · prevista" : ""}${p.atende ? ". Atende: " + p.atende : ""}${p.capacidade_bbl_dia ? ". Capacidade: " + fmt(p.capacidade_bbl_dia) + " barris de petróleo/dia" : ""}. Fonte: ANP.`; });
  }
  const DESENHA = { boi: desenharBoi, oil: desenharPocos, uep: desenharUep, campos: desenharCampos, zc: desenharZc, pce: desenharPce, rodest: desenharRodEst, usinas: desenharUsinas, lt: desenharLt,
    celm: desenharCelm, g5: desenharG5, lav: desenharLav, dutos: desenharDutos, se: desenharSe, empdef: desenharDef };
  /* refinarias (tamanho pela capacidade), unidades de gás natural e terminais de GNL (ANP); clicar abre o estado */
  const gRefin = root.append("g");
  const INST = { refinaria: "Refinaria", upgn: "Unidade de processamento de gás natural", gnl: "Terminal de GNL" };
  const refinC = gRefin.selectAll("circle").data(DATA.refin ? DATA.refin.features.map(f => ({ ...f.properties, c: f.geometry.coordinates,
      r0: f.properties.k === "refinaria" ? 3.2 + Math.sqrt(f.properties.bbl || 0) * 0.008 : 2.6 })) : []).join("circle").attr("class", d => "inst k-" + d.k);
  refinC.on("click", (e, d) => { e.stopPropagation(); if (d.uf) select(d.uf); });
  refinC.append("title").text(d => `${d.n}${d.s ? " (" + d.s + ")" : ""} · ${INST[d.k]} · ${d.m}/${d.uf}${d.bbl ? ". Capacidade: " + fmt(d.bbl) + " barris de petróleo por dia" : ""}${d.mi_m3 ? ". Capacidade: " + fmt(d.mi_m3) + " milhões de m³ de gás por dia" : ""} (ANP).`);
  const gPorts = root.append("g");
  const ports = gPorts.selectAll("circle").data(DATA.ports || []).join("circle").attr("class", "port");
  ports.append("title").text(d => d.n + (d.org ? " · porto organizado" : "") + (d.obra ? " · em obras" : "") + " (IBGE, BC250 2025)");
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
    oil: gPocos, uep: gUep, campos: gCampos, presal: gPresal, boi: gBoi, rodest: gRodEst, usinas: gUsinas, lt: gLt, celm: gCelm, g5: gG5, lav: gLav, dutos: gDutos, refin: gRefin, se: gSe, empdef: gDef };

  let proj, path, W, H, head = 0, k = 1;
  const zoom = d3.zoom().scaleExtent([0.8, 12]).on("zoom", e => {
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
    MAR().forEach(sel => sel.attr("d", path));
    camposP.attr("d", path); presalP.attr("d", path); dutosP.attr("d", path);
    pocosC.attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
    posBoi(); ltP.attr("d", path); usinasC.attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
    posCel(); raioPocos();
    roads.attr("d", path); rodEstP.attr("d", path);
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
  /* geometria das camadas sob demanda, depois que o arquivo chega (sem mexer no zoom atual) */
  function geoSobDemanda() {
    if (!path) return;
    MAR().forEach(sel => sel.attr("d", path));
    camposP.attr("d", path); rodEstP.attr("d", path); ltP.attr("d", path); dutosP.attr("d", path);
    usinasC.attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
    pocosC.attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
    posBoi(); posCel(); raioPocos(); place();
  }
  function posCel() { for (const c of [celmC, g5C, lavC]) c.attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]); }
  function raioPocos() {
    const s = 1 / Math.sqrt(k);
    for (const c of [pocosC, boiC, usinasC, celmC, g5C, lavC]) c.attr("r", d => d.r0 * s);
  }
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
    refinC.attr("r", d => d.r0 * s).attr("cx", d => proj(d.c)[0]).attr("cy", d => proj(d.c)[1]);
    seP.attr("transform", d => `translate(${proj(d.c)}) scale(${s})`);
    defP.attr("transform", d => `translate(${proj(d.c)}) scale(${s})`);
    airs.attr("transform", d => `translate(${proj(d.c)}) scale(${s})`);
    if (CLA) { const p = proj(CLA.ponto); gCla.selectAll("circle").attr("cx", 0).attr("cy", 0); gCla.attr("transform", `translate(${p}) scale(${s})`); }
  }
  /* enquadramento pelo continente: a "caixa" de cada estado não inclui as ilhas oceânicas (ver gerar_contorno_estados.py) */
  const limites = f => { const c = f.properties && f.properties.caixa; if (!c) return path.bounds(f);
    return [proj([c[0][0], c[1][1]]), proj([c[1][0], c[0][1]])]; };
  function zoomTo(feature, dur = 1100) {
    const [[x0, y0], [x1, y1]] = limites(feature);
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
    empdef: "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z"
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
    /* o filtro liga as camadas do ministério, menos as marcadas com "no_filtro": false (ficam na lista, desligadas) */
    LAYERS.forEach(l => { if (l.nivel !== "pendente") l.on = minF === "todos" ? !!l.ligada : l.ministerio === minF && l.no_filtro !== false; });
    const p = PAINT.find(p => p.ministerio === minF && p.ok);
    paint = minF === "todos" ? "pop" : (p ? p.id : "none");
    render();
  });

  function controls() {
    /* pinturas marcadas "so_no_ministerio" (as lavouras) só aparecem com o filtro do ministério, para não lotar "Todos" */
    const pv = PAINT.filter(p => p.id === "none" || (minF === "todos" ? !p.so_no_ministerio : p.ministerio === minF));
    document.getElementById("paint").innerHTML = pv.map(p =>
      `<button class="chip" data-p="${p.id}" aria-pressed="${paint === p.id}" ${p.id !== "none" && !p.ok ? "disabled title=\"Em apuração\"" : ""}>${p.nome}</button>`).join("");
    document.querySelectorAll("#paint .chip:not([disabled])").forEach(b => b.onclick = () => { paint = b.dataset.p; render(); });
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
      todas.onclick = () => { lig.forEach(l => { l.on = !tudo; }); render(); };
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
  /* ---------- desenho ---------- */
  /* camadas sob demanda: o arquivo é baixado na primeira vez que a camada é ligada */
  function baixarSobDemanda() {
    LAYERS.filter(l => l.on && l.sob_demanda && !DATA[l.id] && !l.baixando).forEach(async l => {
      l.baixando = true; l.falhou = false;
      const d = await getJSON("../data/" + l.arquivo);
      l.baixando = false;
      if (!d) { l.on = false; l.falhou = true; render(); return; }
      DATA[l.id] = d;
      if (DESENHA[l.id]) { DESENHA[l.id](); geoSobDemanda(); }
      render();
    });
  }
  function render() {
    baixarSobDemanda();
    controls();
    LAYERS.filter(l => G[l.id]).forEach(l => G[l.id].attr("display", l.on ? null : "none"));
    const P = PAINT.find(p => p.id === paint);
    let leg = "";
    if (P && P.val) {
      const vals = Object.keys(NAME).map(P.val).filter(v => v != null);
      const q = d3.scaleQuantile().domain(vals).range(RAMP);
      states.style("fill", d => { const v = P.val(d.properties.sigla); return v == null ? (P.vazio ? "var(--sem)" : null) : `var(${q(v)})`; });
      const D = DATA[P.id];
      leg = `<span>${P.nome}${P.unidade ? " (" + P.unidade + ")" : ""}</span><span class="faixa"><span>${P.fmt(d3.min(vals))}</span>
        <span class="ramp">${RAMP.map(c => `<i style="background:var(${c})"></i>`).join("")}</span><span>${P.fmt(d3.max(vals))}</span></span>
        ${vals.length < 27 ? (P.vazio ? `<span><i class="key sq" style="background:var(--sem)"></i>${P.vazio}</span>` : "<span>sem cor = sem dado</span>") : ""}`;
    } else states.style("fill", null);
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
          ${pill(DATA.ene.nivel)} <span class="note">EPE, potência instalada (${esc(DATA.ene.referencia)}) · atualizado em ${DATA.ene.atualizado_em}. Sem os painéis solares de telhado.</span>` : ""}
        ${DATA.cel && DATA.cel.cinco_g ? `<div class="kv" style="margin-top:8px"><span>Municípios com 5G</span><span class="v">${fmt(DATA.cel.cinco_g.municipios)} de ${fmt(DATA.cel.cinco_g.total)}</span></div>
          ${pill(DATA.cel.nivel)} <span class="note">Anatel, presença da telefonia móvel (RQUAL), ${esc(DATA.cel.cinco_g.referencia)} · atualizado em ${DATA.cel.cinco_g.atualizado_em}. Pelo menos uma operadora com 5G no município.</span>` : ""}
        ${DATA.defesa ? `<div class="kv" style="margin-top:8px"><span>Indústria de defesa</span><span class="v">${fmt(DATA.defesa.total)} empresas</span></div>
          ${pill(DATA.defesa.nivel)} <span class="note">Ministério da Defesa, empresas credenciadas: ${fmt(DATA.defesa.eed)} estratégicas de defesa (EED) e ${fmt(DATA.defesa.ed)} de defesa (ED); ${esc(DATA.defesa.referencia)} · atualizado em ${DATA.defesa.atualizado_em}</span>` : ""}
        <p class="lede">Clique num estado para aproximar. Cada camada mostra de onde veio o dado e seu nível de confiança. Arraste para mover e role para aproximar.</p>`;
      return;
    }
    const s = sel;
    const rk = Object.entries(POP).sort((a, b) => b[1] - a[1]).findIndex(e => e[0] === s) + 1;
    const Pt = (DATA.ports || []).filter(p => p.uf === s), A = (DATA.air || []).filter(a => a.uf === s);
    /* ferrovias por estado: [existentes, em operação segundo o IBGE] (arquivo antigo: um número só) */
    const fv = DATA.rail ? DATA.rail.km_por_uf[s] || 0 : 0, fr = typeof fv === "number" ? [fv, fv] : fv;
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
        <div class="kv" style="margin-top:8px"><span>Aeroportos na base</span><span class="v">${A.length}</span></div>
        ${A.length ? `<div class="list">${A.map(a => a.n + (a.i ? " (" + a.i + ")" : "")).join(", ")}</div>` : ""}
        ${pill("base")} <span class="note">Natural Earth, só os maiores. Ausência na base não significa ausência real.</span></div>
      ${fichaOleo(s)}
      ${fichaEnergia(s)}
      ${fichaCelular(s)}
      ${fichaDefesa(s)}
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
