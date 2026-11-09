/* Brasil em Camadas — páginas de texto (scripts/gerar_paginas.py): "Excel em português" e "como citar".
   - Excel em português: com a opção marcada, o clique num CSV baixa o arquivo, troca a vírgula entre as colunas por
     ponto e vírgula e o ponto decimal por vírgula (o jeito que o Excel em português abre direto) e entrega a cópia, com a
     marca de UTF-8 no começo para os acentos saírem certos. O arquivo publicado continua o mesmo (o padrão dos programas).
   - Como citar: montado aqui, com o endereço desta página e a data de hoje (a ficha técnica não guarda o endereço do site,
     que pode mudar de domínio). */
"use strict";
(() => {
  const MES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez."];

  /* ---------- como citar ---------- */
  const citar = document.getElementById("citar");
  if (citar) {
    const hoje = new Date(), url = location.href.split(/[?#]/)[0];
    const texto = `${citar.dataset.texto} Disponível em: ${url}. Acesso em: ${hoje.getDate()} ${MES[hoje.getMonth()]} ${hoje.getFullYear()}.`;
    citar.textContent = texto;
    const bt = document.getElementById("copiar");
    if (bt) {
      bt.hidden = false;
      bt.onclick = async () => {
        try { await navigator.clipboard.writeText(texto); bt.textContent = "Copiado"; }
        catch (e) {
          const r = document.createRange(); r.selectNodeContents(citar);
          const s = getSelection(); s.removeAllRanges(); s.addRange(r); bt.textContent = "Texto selecionado: copie com Ctrl+C";
        }
        setTimeout(() => { bt.textContent = "Copiar"; }, 2500);
      };
    }
  }

  /* ---------- Excel em português ---------- */
  const aviso = document.getElementById("aviso-baixar");
  const excel = () => { const r = document.querySelector('input[name="formato"]:checked'); return r && r.value === "excel"; };
  function linhas(texto) {   /* CSV (vírgula, aspas) → linhas de campos */
    const out = [];
    let campo = "", linha = [], aspas = false;
    for (let i = 0; i < texto.length; i++) {
      const c = texto[i];
      if (aspas) {
        if (c === '"') { if (texto[i + 1] === '"') { campo += '"'; i++; } else aspas = false; }
        else campo += c;
      } else if (c === '"') aspas = true;
      else if (c === ",") { linha.push(campo); campo = ""; }
      else if (c === "\n") { linha.push(campo.replace(/\r$/, "")); out.push(linha); linha = []; campo = ""; }
      else campo += c;
    }
    if (campo || linha.length) { linha.push(campo); out.push(linha); }
    return out;
  }
  const NUM = /^-?\d+(\.\d+)?$/;
  function paraExcel(texto) {
    const campo = v => {
      if (NUM.test(v)) v = v.replace(".", ",");
      return /[;"\r\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v;
    };
    return "﻿" + linhas(texto).map(l => l.map(campo).join(";")).join("\r\n") + "\r\n";
  }
  document.addEventListener("click", async ev => {
    const a = ev.target.closest && ev.target.closest("a[data-csv]");
    if (!a || !excel()) return;
    ev.preventDefault();
    const nome = a.dataset.csv.replace(/\.csv$/, "") + "_excel.csv";
    if (aviso) aviso.textContent = `Preparando ${nome}…`;
    try {
      const r = await fetch(a.href);
      if (!r.ok) throw new Error(r.status);
      const blob = new Blob([paraExcel(await r.text())], { type: "text/csv;charset=utf-8" });
      const u = URL.createObjectURL(blob), b = document.createElement("a");
      b.href = u; b.download = nome; document.body.append(b); b.click(); b.remove();
      setTimeout(() => URL.revokeObjectURL(u), 10000);
      if (aviso) aviso.textContent = `${nome} pronto (ponto e vírgula entre as colunas, vírgula nos decimais).`;
    } catch (e) {
      if (aviso) aviso.textContent = "Não foi possível converter agora; baixe o CSV padrão e tente de novo mais tarde.";
    }
  });
  /* para os testes: a conversão sem baixar nada */
  window.BEC_PARA_EXCEL = paraExcel;
})();
