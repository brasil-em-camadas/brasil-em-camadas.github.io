/* Brasil em Camadas — períodos do acervo nas pinturas: escolher o período e comparar dois (versão de teste, ?teste).
   Usado pelos dois mapas (3d/app3d.js e 2d/app.js), carregado antes deles, como o icones.js.

   De onde vêm os números: site/acervo/ (formato em acervo/README.md). A pintura que tem período no acervo diz qual
   conjunto e qual coluna no data/fontes.json ("acervo": {"conjunto", "coluna", "filtro"}). O mapa continua abrindo no
   período mais recente, com os arquivos de sempre (data/); só quando a pessoa escolhe outro período, ou uma comparação,
   o mapa baixa o conjunto.json do conjunto (a lista dos períodos) e o uf.csv e o brasil.csv de cada período escolhido.

   Comparação (variação de um período para o outro, sempre do mais antigo para o mais recente):
   - a conta é a razão entre os dois números (r = depois / antes); as faixas são simétricas na escala da razão, então
     "caiu 50%" (r = 1/2) espelha "subiu 100%" (r = 2) e "caiu 20%" espelha "subiu 25%";
   - três faixas de queda (azul) e três de alta (ouro), mais fortes quanto maior a mudança; os cortes acompanham os
     números (os terços da mudança de todos os estados, arredondados para os valores redondos da lista CORTES), para a
     comparação de um trimestre (mudanças de 1 a 5%) e a de décadas (de 10 a 50 vezes) mostrarem diferenças;
   - quem começou do zero vai para a faixa mais alta, quem parou para a mais baixa;
   - os dois cinzas de sempre: cinza frio = sem número num dos períodos; cinza escuro = nada nos dois (ou, nas pinturas
     de total, menos de 0,1% do Brasil nos dois períodos, em que a porcentagem não quer dizer muito);
   - cores conferidas com o validador de paletas: as duas rampas sobem de claridade sem saltos, e os passos mais fracos
     se distinguem dos dois cinzas também para quem não distingue vermelho de verde.
   Fluxo (ex.: produção) só se compara ano com ano ou trimestre com trimestre; posição (ex.: acessos) e taxas, qualquer
   par. Dinheiro vem no valor de cada ano, sem descontar a inflação, e o mapa avisa. */
"use strict";
const PERIODOS = (() => {
  const RAIZ = new URL(".", document.currentScript.src).href;           /* pasta do site (este arquivo fica nela) */
  const ACERVO = new URL("acervo/", RAIZ).href, DADOS = new URL("dados/", RAIZ).href;
  /* cores da comparação, da queda forte à alta forte (variáveis no style.css) */
  const CORES = ["--dv-c3", "--dv-c2", "--dv-c1", "--dv-s1", "--dv-s2", "--dv-s3"];
  /* cortes possíveis da razão (1,25 = +25% ou −20%; 2 = o dobro ou a metade) */
  const CORTES = [1.01, 1.02, 1.05, 1.1, 1.25, 1.5, 2, 3, 5, 10, 20, 50, 100];
  const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  const fmt = n => n.toLocaleString("pt-BR");
  const fmt1 = n => n.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const data = d => d ? d.split("-").reverse().join("/") : "";
  let aoMudar = () => {}, NIVEL = {};
  const CONJ = {}, TAB = {};       /* conjunto.json e tabelas de cada período: { carregando } → { ok, dados } ou { falhou } */
  const EST = {};                  /* por pintura: { a: "hoje" ou período; b: null (sem comparação), "hoje" ou período } */

  /* ---------- leitura ---------- */
  function csv(texto) {
    const linhas = [];
    let campo = "", linha = [], aspas = false;
    for (let i = 0; i < texto.length; i++) {
      const c = texto[i];
      if (aspas) {
        if (c === '"') { if (texto[i + 1] === '"') { campo += '"'; i++; } else aspas = false; }
        else campo += c;
      } else if (c === '"') aspas = true;
      else if (c === ",") { linha.push(campo); campo = ""; }
      else if (c === "\n") { linha.push(campo.replace(/\r$/, "")); linhas.push(linha); linha = []; campo = ""; }
      else campo += c;
    }
    if (campo || linha.length) { linha.push(campo); linhas.push(linha); }
    const [cab, ...resto] = linhas;
    return resto.filter(l => l.length > 1 || l[0]).map(l => Object.fromEntries(cab.map((k, i) => [k, l[i] ?? ""])));
  }
  function buscar(guarda, chave, url, ler) {
    if (!guarda[chave]) {
      guarda[chave] = { carregando: true };
      Promise.all([].concat(url).map(u => fetch(u).then(r => { if (!r.ok) throw new Error(r.status); return r.text(); })))
        .then(t => { guarda[chave] = { ok: true, dados: ler(...t) }; })
        .catch(() => { guarda[chave] = { falhou: true }; })
        .finally(() => aoMudar());
    }
    return guarda[chave];
  }
  const conjunto = id => buscar(CONJ, id, ACERVO + id + "/conjunto.json", t => JSON.parse(t));
  const tabela = (id, p) => buscar(TAB, id + "/" + p, [ACERVO + id + "/" + p + "/uf.csv", ACERVO + id + "/" + p + "/brasil.csv"],
    (uf, br) => ({ uf: csv(uf), br: csv(br) }));

  /* ---------- períodos ---------- */
  /* 2025 → 2025,999 (fim do ano); 2026-T3 → 2026,749 (fim do 3º trimestre); "ago/2026" → fim de agosto */
  function chave(p) {
    let m = /^(\d{4})(?:-T([1-4]))?$/.exec(p);
    if (m) return +m[1] + (m[2] ? m[2] / 4 : 1) - 0.001;
    m = /^([a-zç]{3})\/(\d{4})$/.exec(String(p).toLowerCase());
    if (m && MESES.includes(m[1])) return +m[2] + (MESES.indexOf(m[1]) + 1) / 12 - 0.001;
    m = /(\d{4})\D*$/.exec(String(p));
    return m ? +m[1] + 0.999 : 0;
  }
  const ordem = (a, b) => chave(a) - chave(b) || (a.length - b.length);
  const pacote = (C, p) => C.pacotes.find(x => x.periodo === p);
  const posicao = C => /^posi/i.test(C.medida || "");
  const MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  /* nome do período: posição (ex.: acessos) → o mês em que vale ("dez/2022", "set/2026"); fluxo e medianas → o ano
     ("2025") ou o trimestre ("3º tri 2026") */
  function curto(C, p) {
    const m = /^(\d{4})(?:-T([1-4]))?$/.exec(p);
    if (!m) return p;
    const q = m[2] ? +m[2] : 4;
    return posicao(C) ? `${MESES[q * 3 - 1]}/${m[1]}` : m[2] ? `${q}º tri ${m[1]}` : m[1];
  }
  function longo(C, p) {
    const m = /^(\d{4})(?:-T([1-4]))?$/.exec(p);
    if (!m) return p;
    const q = m[2] ? +m[2] : 4;
    return posicao(C) ? `${MESES_LONGOS[q * 3 - 1]} de ${m[1]}` : m[2] ? `${q}º trimestre de ${m[1]}` : m[1];
  }
  /* o período do acervo que é o mesmo do mapa de hoje (ex.: lavouras "2025"; velocidade "2º trimestre de 2026") */
  function doMapa(C, D) {
    if (!D) return null;
    if (pacote(C, String(D.referencia))) return String(D.referencia);
    const m = /(\d)º trimestre de (\d{4})/.exec(D.trimestre || "");
    return m && pacote(C, `${m[2]}-T${m[1]}`) ? `${m[2]}-T${m[1]}` : null;
  }
  /* os períodos com número nesta coluna; na posição, o 4º trimestre é o mesmo dezembro do ano e fica só o ano */
  const validos = (P, C) => C.pacotes.filter(x => !(x.sem_dado || []).includes(P.acervo.coluna)
    && !(posicao(C) && /-T4$/.test(x.periodo) && pacote(C, x.periodo.slice(0, 4)))).map(x => x.periodo);
  /* "1974 a 1993", "1º tri 2023 a 1º tri 2026": os períodos do conjunto sem esta coluna, em trechos seguidos */
  function lacunas(P, C) {
    const todos = C.pacotes.map(x => x.periodo).sort(ordem), trechos = [];
    const ok = new Set(C.pacotes.filter(x => !(x.sem_dado || []).includes(P.acervo.coluna)).map(x => x.periodo));
    let ini = null, fim = null;
    for (const p of todos) {
      if (!ok.has(p)) { if (ini == null) ini = p; fim = p; }
      else if (ini != null) { trechos.push([ini, fim]); ini = null; }
    }
    if (ini != null) trechos.push([ini, fim]);
    return trechos.map(([a, b]) => a === b ? curto(C, a) : `${curto(C, a)} a ${curto(C, b)}`);
  }
  /* quebras da série (conjunto.json, "quebras"): mudanças de método da fonte que valem para esta pintura */
  const quebras = (P, C) => (C.quebras || []).filter(q => (q.colunas || []).includes(P.acervo.coluna)
    && Object.entries(q.filtro || {}).every(([c, x]) => (P.acervo.filtro || {})[c] === x));
  const antesDe = (p, q) => chave(p) < chave(q.desde) - 0.999;   /* o período termina antes do começo de q.desde */
  const estado = P => EST[P.id] || (EST[P.id] = { a: "hoje", b: null });
  const ativo = P => { const e = estado(P); return e.a !== "hoje" || e.b != null; };
  const tem = P => !!(P && P.acervo && P.val);

  /* ---------- números de um período ---------- */
  const num = t => t === "" || t === "X" || t === ".." || t == null ? null : +t;
  /* um lado da comparação (ou o período escolhido): o mapa de hoje (arquivos de data/) ou um pacote do acervo */
  function lado(P, D, C, tok, ufs) {
    const M = doMapa(C, D);
    if (tok === "hoje" && !M) {
      const v = {};
      ufs.forEach(s => { const x = P.val(s); v[s] = x == null && P.vazio ? 0 : x; });
      const b = D && D.brasil ? (D.brasil[P.campo || "valor"] ?? D.brasil.valor) : null;
      return { ok: true, rotulo: String(D.referencia), chave: chave(D.referencia), mapa: true, v, marca: {},
        br: typeof b === "number" ? b : null, situacao: null, tipo: null };
    }
    const p = tok === "hoje" ? M : tok, k = pacote(C, p);
    const base = { rotulo: curto(C, p), longo: longo(C, p), periodo: p, chave: chave(p), situacao: k && k.situacao,
      consolida: k && k.consolida_em, versao: k && k.versao, tipo: k && k.tipo, hoje: p === M };
    if (!k) return { ...base, falhou: true };
    const T = tabela(P.acervo.conjunto, p);
    if (!T.ok) return { ...base, carregando: !!T.carregando, falhou: !!T.falhou };
    const f = P.acervo.filtro || {}, comFiltro = Object.keys(f).length > 0, col = P.acervo.coluna;
    const passa = r => Object.entries(f).every(([c, x]) => r[c] === x);
    const brs = T.dados.br.filter(passa), v = {}, marca = {};
    /* com filtro (lavouras): estado sem a linha = zero registrado pela fonte, se o item foi pesquisado no período
       (há a linha do Brasil); sem a linha do Brasil, o item não foi pesquisado naquele período */
    ufs.forEach(s => { v[s] = comFiltro ? 0 : null; });
    let unidade = null;
    T.dados.uf.filter(passa).forEach(r => {
      if (!(r.uf in v)) return;
      v[r.uf] = num(r[col]);
      if (r[col] === "X" || r[col] === "..") marca[r.uf] = r[col];
      if (col === "quantidade" && r.unidade_quantidade) unidade = r.unidade_quantidade;
    });
    if (!unidade && col === "quantidade" && brs[0] && brs[0].unidade_quantidade) unidade = brs[0].unidade_quantidade;
    return { ...base, ok: true, v, marca, br: brs.length ? num(brs[0][col]) : null, unidade, pesquisado: !comFiltro || brs.length > 0 };
  }

  /* ---------- a pintura de um período (sem comparação): a escala de sempre, com os números do período ----------
     Devolve { P } (a pintura de sempre), { P, carregando }, { P, erro } ou { P: pintura do período, A } */
  function pintura(P, D, ufs) {
    if (!tem(P) || !ativo(P) || estado(P).b != null) return { P };
    const C = conjunto(P.acervo.conjunto);
    if (!C.ok) return { P, carregando: !!C.carregando, falhou: !!C.falhou };
    const A = lado(P, D, C.dados, estado(P).a, ufs);
    if (!A.ok) return { P, carregando: !!A.carregando, falhou: !!A.falhou };
    if (A.pesquisado === false) return { P: { ...P, val: () => null }, erro: `A fonte não pesquisou ${P.nome.toLowerCase()} em ${A.rotulo}.` };
    /* sem o "vazio" da pintura: no acervo, zero é zero (cinza escuro) e célula vazia é sem número (cinza frio) */
    return { P: { ...P, val: s => A.v[s], vazio: undefined }, A, zero: P.vazio };
  }
  /* as faixas de sempre (classesEscala, de cada app) para a pintura de um período, com o nome certo do zero */
  function escala(R, ufs, classesEscala) {
    const K = classesEscala(R.P, ufs);
    if (R.zero) K.fraco = K.fraco.replace(/^zero/, R.zero);
    return K;
  }
  const sufixo = R => R.A ? ` · ${R.A.rotulo}${R.A.situacao === "preliminar" ? " (preliminar)" : ""}` : "";
  const aviso = R => R.erro ? `<span class="per-aviso">${esc(R.erro)}</span>`
    : R.carregando ? `<span class="per-aviso">carregando o período…</span>`
    : R.falhou ? `<span class="per-aviso">não foi possível carregar o período agora</span>` : "";

  /* ---------- comparação ---------- */
  function corta(x) {   /* o valor da lista CORTES mais perto de x, na escala da razão */
    let melhor = CORTES[0];
    CORTES.forEach(c => { if (Math.abs(Math.log(c / x)) < Math.abs(Math.log(melhor / x))) melhor = c; });
    return melhor;
  }
  const alta = f => f <= 2 ? `+${fmt(Math.round((f - 1) * 100))}%` : `×${fmt(f)}`;
  const queda = f => `−${fmt(Math.round((1 - 1 / f) * 100))}%`;
  /* null (sem comparação), { carregando }, { falhou }, { erro } ou { ok, A, B, c (faixa de cada estado), x, t1, t2, ... } */
  function comparacao(P, D, ufs) {
    if (!tem(P) || estado(P).b == null) return null;
    const C = conjunto(P.acervo.conjunto);
    if (!C.ok) return { carregando: !!C.carregando, falhou: !!C.falhou };
    let A = lado(P, D, C.dados, estado(P).a, ufs), B = lado(P, D, C.dados, estado(P).b, ufs);
    if (!A.ok || !B.ok) return { carregando: !!(A.carregando || B.carregando), falhou: !!(A.falhou || B.falhou) };
    if (A.chave > B.chave) [A, B] = [B, A];   /* sempre do mais antigo para o mais recente */
    if (A.chave === B.chave) return { erro: "Escolha dois períodos diferentes." };
    for (const X of [A, B]) if (X.pesquisado === false) return { erro: `A fonte não pesquisou ${P.nome.toLowerCase()} em ${X.rotulo}.` };
    if (A.unidade && B.unidade && A.unidade !== B.unidade)
      return { erro: `A unidade mudou de ${A.unidade} (${A.rotulo}) para ${B.unidade} (${B.rotulo}): não dá para comparar.` };
    const qb = quebras(P, C.dados).find(q => antesDe(A.periodo || String(A.rotulo), q) !== antesDe(B.periodo || String(B.rotulo), q));
    if (qb) return { erro: qb.aviso };
    if (/^fluxo/i.test(C.dados.medida || "") && A.tipo && B.tipo && A.tipo !== B.tipo)
      return { erro: "A produção é a soma do período: compare ano com ano, ou trimestre com trimestre." };
    const total = X => P.por === "total" ? ufs.reduce((t, s) => t + (X.v[s] > 0 ? X.v[s] : 0), 0) : 0;
    const tA = total(A), tB = total(B), x = {}, c = {};
    let forte = false, nada = false, pouco = false;
    ufs.forEach(s => {
      const a = A.v[s], b = B.v[s];
      if (a == null || b == null) { c[s] = "forte"; forte = true; return; }
      if (a === 0 && b === 0) { c[s] = "fraco"; nada = true; return; }
      if (P.por === "total" && a < tA * 0.001 && b < tB * 0.001) { c[s] = "fraco"; pouco = true; return; }
      x[s] = a === 0 ? Infinity : b === 0 ? -Infinity : Math.log(b / a);
    });
    const absx = Object.values(x).filter(Number.isFinite).map(Math.abs).sort((p, q) => p - q);
    const q = f => absx[Math.min(absx.length - 1, Math.floor(f * absx.length))];
    let t1 = absx.length ? corta(Math.exp(q(1 / 3))) : 1.1, t2 = absx.length ? corta(Math.exp(q(2 / 3))) : 2;
    if (t2 <= t1) t2 = CORTES[Math.min(CORTES.length - 1, CORTES.indexOf(t1) + 1)];
    if (t2 <= t1) t1 = CORTES[CORTES.indexOf(t2) - 1];
    const L1 = Math.log(t1), L2 = Math.log(t2);
    Object.entries(x).forEach(([s, v]) => { c[s] = v >= L2 ? 5 : v >= L1 ? 4 : v >= 0 ? 3 : v > -L1 ? 2 : v > -L2 ? 1 : 0; });
    const fraco = [nada ? `${P.vazio || "zero"} nos dois períodos` : "", pouco ? "menos de 0,1% do Brasil nos dois períodos" : ""]
      .filter(Boolean).join(" ou ");
    return { ok: true, A, B, c, x, t1, t2, forte, fraco, dinheiro: /reais|R\$/i.test(P.unidade || "") };
  }

  /* ---------- legenda da comparação ---------- */
  function legenda(P, K) {
    /* só os lados que aparecem no mapa (se nenhum estado caiu, a faixa mostra só a alta, a partir do zero) */
    const fx = Object.values(K.c).filter(v => typeof v === "number");
    const lo = fx.some(v => v < 3) || !fx.length ? 0 : 3, hi = fx.some(v => v >= 3) || !fx.length ? 5 : 2, n = hi - lo + 1;
    const cortes = ["", queda(K.t2), queda(K.t1), "0", alta(K.t1), alta(K.t2)];   /* corte k: entre as faixas k−1 e k */
    const marcas = [];
    for (let k = lo + 1; k <= hi; k++) marcas.push([cortes[k], (k - lo) * 100 / n]);
    if (lo === 3) marcas.unshift(["0", 0]);
    if (hi === 2) marcas.push(["0", 100]);
    return `<span>${esc(P.nome)}${P.unidade ? " (" + esc(P.unidade) + ")" : ""}: variação de ${esc(K.A.rotulo)} para ${esc(K.B.rotulo)}${K.dinheiro ? ", sem descontar a inflação" : ""}</span>
      <span class="faixa">${lo === 0 ? "<span>caiu</span>" : ""}<span class="ramp cmp">${CORES.slice(lo, hi + 1).map(c => `<i style="background:var(${c})"></i>`).join("")}${marcas.map(([m, x]) => `<b style="left:${x}%">${m}</b>`).join("")}</span>${hi === 5 ? "<span>subiu</span>" : ""}</span>
      ${K.forte ? `<span><i class="key sq" style="background:var(--sem-forte)"></i>sem número num dos períodos</span>` : ""}
      ${K.fraco ? `<span><i class="key sq" style="background:var(--sem-fraco)"></i>${esc(K.fraco)}</span>` : ""}`;
  }

  /* ---------- painel (embaixo das pinturas) ---------- */
  function opcoes(P, C, D, atual, nenhum) {
    const M = doMapa(C, D), ps = validos(P, C).sort((a, b) => ordem(b, a));
    const sit = p => { const k = pacote(C, p); return k && k.situacao === "preliminar" ? " · preliminar" : ""; };
    const op = p => `<option value="${esc(p === M ? "hoje" : p)}"${(p === M ? "hoje" : p) === atual ? " selected" : ""}>${esc(curto(C, p) + sit(p) + (p === M ? " · mapa de hoje" : ""))}</option>`;
    let h = nenhum ? `<option value=""${atual === "" ? " selected" : ""}>${esc(nenhum)}</option>` : "";
    if (!M && D) h += `<option value="hoje"${atual === "hoje" ? " selected" : ""}>${esc(D.referencia)} · mapa de hoje</option>`;
    if (C.pacotes.some(x => x.tipo === "trimestre") && C.pacotes.some(x => x.tipo === "ano"))
      [...new Set(ps.map(p => p.slice(0, 4)))].forEach(a => { h += `<optgroup label="${a}">` + ps.filter(p => p.slice(0, 4) === a).map(op).join("") + "</optgroup>"; });
    else h += ps.map(op).join("");
    return h;
  }
  function painel(el, P, D) {
    if (!el) return;
    let h = "";
    if (tem(P)) {
      const C = conjunto(P.acervo.conjunto), e = estado(P);
      if (!C.ok) h = `<p class="note">${C.falhou ? "Não foi possível carregar os períodos agora; tente de novo mais tarde." : "Carregando os períodos…"}</p>`;
      else {
        const Cd = C.dados, M = doMapa(Cd, D), soUm = validos(P, Cd).length + (M ? 0 : 1) < 2, lac = lacunas(P, Cd);
        const prel = [e.a, e.b].filter(t => t != null).map(t => t === "hoje" ? M : t).filter(Boolean)
          .map(p => pacote(Cd, p)).filter(k => k && k.situacao === "preliminar");
        const notas = [
          `${esc(Cd.fonte.titulo)}.`,
          Cd.medida ? esc(Cd.medida.charAt(0).toUpperCase() + Cd.medida.slice(1)) + "." : "",
          /reais|R\$/i.test(P.unidade || "") ? "Valores em reais de cada ano, sem descontar a inflação." : "",
          prel.length ? prel.map(k => `${curto(Cd, k.periodo)}: preliminar (a fonte ainda pode revisar; vira consolidado em ${data(k.consolida_em)})`).join("; ") + "." : "",
          lac.length ? `Sem este número no acervo: ${lac.join("; ")}.` : "",
          ...quebras(P, Cd).filter(q => [e.a, e.b].some(t => t != null && t !== "hoje" && antesDe(t, q))).map(q => esc(q.aviso)),
          soUm ? "Só um período no acervo por enquanto; os próximos entram quando a fonte publicar." : "",
          ativo(P) ? "As camadas por município continuam no período mais recente." : "",
        ].filter(Boolean);
        h = `<div class="per-linha"><label>Período <select data-per="a"${soUm ? " disabled" : ""}>${opcoes(P, Cd, D, e.a)}</select></label>
          <label>Comparar com <select data-per="b"${soUm ? " disabled" : ""}>${opcoes(P, Cd, D, e.b == null ? "" : e.b, "não comparar")}</select></label></div>
          <p class="note">${notas.join(" ")} <a href="${DADOS}${esc(P.acervo.conjunto)}/">Baixar estes dados</a></p>`;
      }
    }
    el.hidden = !h;
    if (el.dataset.h === h) return;   /* sem mudança: não refaz (um menu aberto não fecha sozinho) */
    el.dataset.h = h; el.innerHTML = h;
    if (!tem(P)) return;
    const e = estado(P);
    el.querySelectorAll("select").forEach(s => s.onchange = () => {
      if (s.dataset.per === "a") e.a = s.value; else e.b = s.value === "" ? null : s.value;
      if (e.b != null && e.b === e.a) e.b = null;
      aoMudar();
    });
  }

  /* ---------- ficha (estado escolhido, ou o Brasil) ---------- */
  function ficha(P, D, s, ufs) {
    if (!tem(P) || !ativo(P)) return "";
    const C = conjunto(P.acervo.conjunto);
    if (!C.ok) return "";
    const Cd = C.dados, colu = (Cd.colunas || []).find(c => c.name === P.acervo.coluna), rot = colu ? colu.title : P.nome;
    /* a unidade só quando o nome da coluna não a diz (ex.: "Densidade: acessos por 100 habitantes") */
    const comUn = P.unidade && !rot.toLowerCase().includes(P.unidade.toLowerCase());
    const un = (X, v) => v == null ? (X.marca && X.marca[s] === "X" ? "a fonte não mostra" : "sem número") : `${P.fmt(v)}${comUn ? " " + esc(P.unidade) : ""}`;
    const valor = X => s ? X.v[s] : X.br;
    const n = Object.values(NIVEL).find(x => x[1] === Cd.nivel_confianca);
    const selo = `<span class="pill ${n ? n[0] : "n-api"}">${esc(Cd.nivel_confianca)}</span>`;
    const quando = X => X.mapa ? `${esc(X.rotulo)}, o mapa de hoje` : `${esc(X.longo || X.rotulo)}, ${X.situacao}${X.versao > 1 ? ", versão " + X.versao : ""}`;
    const fonte = Xs => `${selo} <span class="note">${esc(Cd.fonte.titulo)}; ${Xs.map(quando).join(" e ")}${s ? "" : ". No Brasil, o total da própria fonte"} · <a href="${DADOS}${esc(P.acervo.conjunto)}/">baixar os dados</a></span>`;
    const caixa = (t, corpo) => `<div class="sec periodo-ficha"><h3>${t}</h3>${corpo}</div>`;
    const K = comparacao(P, D, ufs);
    if (K) {
      if (!K.ok) return K.erro ? caixa(esc(P.nome), `<div class="list">${esc(K.erro)}</div>`) : "";
      const a = valor(K.A), b = valor(K.B);
      let vari = "—";
      if (a != null && b != null) {
        if (a === 0 && b === 0) vari = "nada nos dois períodos";
        else if (a === 0) vari = "começou (era zero)";
        else if (b === 0) vari = "parou (ficou em zero)";
        else { const r = b / a; vari = `${r >= 1 ? "+" : "−"}${fmt1(Math.abs(r - 1) * 100)}%${r >= 2 ? ` (${fmt1(r)} vezes)` : ""}`; }
      }
      let pos = "";
      if (s && Number.isFinite(K.x[s]) && K.x[s] !== 0) {
        const mesmo = Object.values(K.x).filter(v => Math.sign(v) === Math.sign(K.x[s]));
        const k = mesmo.filter(v => Math.abs(v) > Math.abs(K.x[s])).length + 1;
        pos = K.x[s] > 0 ? ` · ${k}º maior aumento` : ` · ${k}ª maior queda`;
      } else if (s && typeof K.c[s] === "string") pos = K.c[s] === "forte" ? "" : ` · ${esc(K.fraco)}`;
      return caixa(`${esc(P.nome)}: ${esc(K.A.rotulo)} → ${esc(K.B.rotulo)}`, `<div class="list">${esc(rot)}${s ? "" : " (Brasil)"}</div>
        <div class="kv"><span>${esc(K.A.rotulo)}${K.A.mapa ? " (mapa de hoje)" : ""}</span><span class="v">${un(K.A, a)}</span></div>
        <div class="kv"><span>${esc(K.B.rotulo)}${K.B.mapa ? " (mapa de hoje)" : ""}</span><span class="v">${un(K.B, b)}</span></div>
        <div class="kv"><span>Variação</span><span class="v">${vari}${pos}</span></div>
        ${K.dinheiro ? `<div class="list">Em reais de cada ano, sem descontar a inflação: parte da alta é só a inflação do período.</div>` : ""}
        ${fonte([K.A, K.B])}`);
    }
    const R = pintura(P, D, ufs);
    if (!R.A) return R.erro ? caixa(esc(P.nome), `<div class="list">${esc(R.erro)}</div>`) : "";
    const A = R.A, v = valor(A);
    let pos = "";
    if (s && v != null && v > 0) {
      const todos = ufs.map(u => A.v[u]).filter(x => x != null), tot = todos.reduce((t, x) => t + (x > 0 ? x : 0), 0);
      pos = `<div class="kv"><span>Posição no país</span><span class="v">${todos.filter(x => x > v).length + 1}º${P.por === "total" && tot ? " · " + fmt1(v / tot * 100) + "%" : ""}</span></div>`;
    }
    return caixa(`${esc(P.nome)} em ${esc(A.longo || A.rotulo)}`, `
      <div class="kv"><span>${esc(rot)}</span><span class="v">${un(A, v)}</span></div>${pos}
      ${fonte([A])}`);
  }

  return {
    CORES, tem, ativo, pintura, escala, sufixo, aviso, comparacao, legenda, painel, ficha,
    iniciar: o => { aoMudar = o.aoMudar || aoMudar; NIVEL = o.NIVEL || NIVEL; },
  };
})();
