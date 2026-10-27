/* Brasil em Camadas — ícones das camadas de pontos (desenhos em 24 × 24), usados no globo (3d/app3d.js)
   e na versão leve (2d/app.js), num medalhão escuro com aro na cor da camada. Lavouras, boi, usinas, poços, celular e pedágios:
   só no estado escolhido; portos, refinarias e unidades de gás no mapa todo. Desenhos gerados por
   scripts/estudos/icones_lavouras.py e scripts/estudos/icones_camadas.py.
   Cada ícone é uma lista de partes:
     ["f", caminho]     preenchido na cor da camada
     ["s", caminho, w]  preenchido, com um contorno escuro de w em volta (separa peças que se sobrepõem)
     ["h", caminho]     preenchido em escuro (janela, furo, raio da gota)
     ["x", caminho, w]  risco escuro de largura w (sulco, nó, grão marcado)
     ["l", caminho, w]  risco na cor da camada (haste, cabinho) */
"use strict";
/* desenho da aba do navegador (favicon), em teste desde 27/10/2026 (pedido do Edu): com ?teste aparece a opção F (três
   folhas com o Brasil, empilhadas); ?teste&icone=a ... f mostra as outras. Desenhos em site/aba/, feitos por
   scripts/estudos/icone_aba.py */
(() => {
  const q = new URLSearchParams(location.search), k = (q.get("icone") || "f").toLowerCase();
  if (!q.has("teste") || !/^[a-f]$/.test(k)) return;
  const raiz = new URL(".", document.currentScript ? document.currentScript.src : location.href).href;
  const l = document.createElement("link");
  l.rel = "icon"; l.type = "image/svg+xml"; l.href = raiz + "aba/icone_" + k + ".svg";
  document.head.appendChild(l);
})();
const MEDALHAO = "rgba(16,10,4,.88)", RISCO = "#100a04";
const ICONES = {
  /* soja: vagem com três grãos */
  soja: [
    ["f", "M9.51 18.31L18.31 9.51A2.7 2.7 0 0 0 14.49 5.69L5.69 14.49A2.7 2.7 0 0 0 9.51 18.31z"],
    ["f", "M4.25 16.4a3.35 3.35 0 1 0 6.7 0a3.35 3.35 0 1 0 -6.7 0z"],
    ["f", "M8.65 12a3.35 3.35 0 1 0 6.7 0a3.35 3.35 0 1 0 -6.7 0z"],
    ["f", "M13.05 7.6a3.35 3.35 0 1 0 6.7 0a3.35 3.35 0 1 0 -6.7 0z"],
    ["f", "M14.6 6.2L21 3 17.8 9.4z"],
    ["l", "M7 17L3.6 20.4", 1.5],
    ["x", "M9.9 14.1Q10.4 13.3 9.6 12.6", 0.9],
    ["x", "M14.3 9.7Q14.8 8.9 14 8.2", 0.9]],
  /* milho: espiga com os grãos marcados e duas palhas */
  milho: [
    ["f", "M16.4 9.6A4.4 7.3 0 1 0 7.6 9.6A4.4 7.3 0 1 0 16.4 9.6z"],
    ["x", "M7.8 6.6L16.2 6.6", 0.75],
    ["x", "M7.6 9.6L16.4 9.6", 0.75],
    ["x", "M8 12.6L16 12.6", 0.75],
    ["x", "M12 2.6L12 16", 0.75],
    ["x", "M9.6 3.6Q9 9.6 9.8 15.8", 0.65],
    ["x", "M14.4 3.6Q15 9.6 14.2 15.8", 0.65],
    ["s", "M12 21.6C8.4 21 5.4 17.6 4.6 10.6C7.8 13 9.8 15.6 12 21.6z", 1.3],
    ["s", "M12 21.6C15.6 21 18.6 17.6 19.4 10.6C16.2 13 14.2 15.6 12 21.6z", 1.3]],
  /* cana-de-açúcar: dois colmos com nós e folhas compridas */
  cana: [
    ["f", "M10.25 21.31L11.45 3.71A1.65 1.65 0 0 0 8.15 3.49L6.95 21.09A1.65 1.65 0 0 0 10.25 21.31z"],
    ["f", "M16.05 21.29L16.85 6.49A1.65 1.65 0 0 0 13.55 6.31L12.75 21.11A1.65 1.65 0 0 0 16.05 21.29z"],
    ["x", "M6.6 8.2L11.8 8", 0.85],
    ["x", "M6.8 13.4L12 13.2", 0.85],
    ["x", "M7 18.4L12.2 18.2", 0.85],
    ["x", "M12.6 11L17 10.8", 0.85],
    ["x", "M12.7 16L17.1 15.8", 0.85],
    ["s", "M10 6.4Q15.82 5.7 20.8 2.6Q14.18 1.04 10 6.4z", 1.1],
    ["s", "M15.2 10Q17.53 13.34 21.4 14.6Q20.02 9.98 15.2 10z", 1.1],
    ["s", "M9 11Q7.39 6.88 3 7.4Q5.43 10.14 9 11z", 1.1]],
  /* café: grão com o sulco em S */
  cafe: [
    ["f", "M17.16 15.61A6.3 8.7 35 1 0 6.84 8.39A6.3 8.7 35 1 0 17.16 15.61z"],
    ["x", "M16.1 5.8C12.4 8.6 14.6 11.4 12 12.6C9.4 13.8 11.4 16.6 7.9 18.2", 1.5]],
  /* mandioca: três raízes, com o corte (a polpa) na ponta grossa */
  mandioca: [
    ["f", "M11.58 3.63C5.79 8.38 3.36 11.76 3.2 14.6C5.8 14.41 9.2 12.09 14.82 7.17A2.4 2.4 0 0 0 11.58 3.63z"],
    ["s", "M15.04 6.33C7.42 12.18 4.15 16.41 3.8 20C7.09 19.81 11.54 16.95 18.96 10.87A3 3 0 0 0 15.04 6.33z", 1.1],
    ["s", "M17.72 11.79C11.64 15.73 8.97 18.77 8.6 21.6C11.19 21.8 14.75 19.96 20.68 15.81A2.5 2.5 0 0 0 17.72 11.79z", 1.1],
    ["x", "M15.5 8.6a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0 -3 0z", 0.9],
    ["x", "M18 13.8a1.2 1.2 0 1 0 2.4 0a1.2 1.2 0 1 0 -2.4 0z", 0.9],
    ["x", "M12.1 5.4a1.1 1.1 0 1 0 2.2 0a1.1 1.1 0 1 0 -2.2 0z", 0.9],
    ["x", "M9.8 11.4L11.4 13.6", 0.75],
    ["x", "M12.4 15.8L13.6 18", 0.75]],
  /* banana: duas, com o cabo */
  banana: [
    ["f", "M6.4 4.8C3.4 12.8 9.4 21.4 20.6 18.4L21 16.6C12.6 16.6 8.4 11 9.2 4.6z"],
    ["s", "M9.8 4.4C8.8 11.4 13.6 15.4 21 14L21.4 12.2C15 12.2 11.8 8.6 12.6 4z", 1.2],
    ["f", "M6.6 5L7.8 1.8h3.6l1.4 2.8z"]],
  /* feijão: dois grãos em forma de rim, com o olho */
  feijao: [
    ["f", "M10.03 13.36Q9.48 12.32 8.93 11.28Q8.37 10.24 9.19 8.99Q10 7.74 11.41 6.99Q12.82 6.24 14.22 5.5Q15.63 4.75 17.12 4.77Q18.62 4.8 19.17 5.84Q19.72 6.88 20.27 7.92Q20.83 8.96 20.14 10.14Q19.46 11.32 18.48 11.84Q17.51 12.36 16.92 11.85Q16.32 11.35 15.91 11.32Q15.49 11.28 15.29 11.64Q15.09 12.01 15.17 12.78Q15.26 13.55 14.28 14.07Q13.31 14.59 11.95 14.5Q10.58 14.4 10.03 13.36z"],
    ["s", "M3.73 17.33Q3.45 15.99 3.16 14.66Q2.88 13.32 4.18 12.19Q5.48 11.06 7.28 10.68Q9.09 10.3 10.89 9.91Q12.69 9.53 14.34 10.03Q15.99 10.54 16.27 11.87Q16.55 13.21 16.84 14.54Q17.12 15.88 15.98 16.97Q14.85 18.07 13.6 18.33Q12.36 18.6 11.86 17.85Q11.35 17.1 10.91 16.93Q10.46 16.75 10.12 17.09Q9.78 17.44 9.63 18.32Q9.47 19.21 8.23 19.47Q6.98 19.74 5.5 19.2Q4.01 18.66 3.73 17.33z", 1.2],
    ["x", "M11.67 17.53A1.3 0.62 -12 1 0 9.13 18.07A1.3 0.62 -12 1 0 11.67 17.53z", 0.9]],
  /* arroz: haste que se curva com os grãos e as folhas */
  arroz: [
    ["l", "M6 22C6.4 13 9.6 5.6 14.6 4.6C18.4 3.8 20.4 7 19.6 12.4", 1.2],
    ["f", "M13.38 7.58A2.3 1.05 -26 1 0 9.25 9.6A2.3 1.05 -26 1 0 13.38 7.58z"],
    ["f", "M11.81 2.44A2.3 1.05 -70.75 1 0 10.29 6.78A2.3 1.05 -70.75 1 0 11.81 2.44z"],
    ["f", "M16.64 6.35A2.3 1.05 4.26 1 0 12.05 6.01A2.3 1.05 4.26 1 0 16.64 6.35z"],
    ["f", "M19.05 2.16A2.3 1.05 -23.66 1 0 14.84 4A2.3 1.05 -23.66 1 0 19.05 2.16z"],
    ["f", "M18.4 8.82A2.3 1.05 66.36 1 0 16.56 4.61A2.3 1.05 66.36 1 0 18.4 8.82z"],
    ["f", "M22.52 7.26A2.3 1.05 30.02 1 0 18.53 4.96A2.3 1.05 30.02 1 0 22.52 7.26z"],
    ["f", "M17.51 11.25A2.3 1.05 108.6 1 0 18.97 6.89A2.3 1.05 108.6 1 0 17.51 11.25z"],
    ["f", "M22.4 12.88A2.3 1.05 60.43 1 0 20.13 8.88A2.3 1.05 60.43 1 0 22.4 12.88z"],
    ["f", "M19.18 15.27A2.3 1.05 98.43 1 0 19.85 10.72A2.3 1.05 98.43 1 0 19.18 15.27z"],
    ["s", "M6.2 21.6Q12.6 21.07 15.6 15.4Q10.09 17.26 6.2 21.6z", 1.0],
    ["s", "M6 21.6Q5.63 15.87 2.6 11Q2.01 17.03 6 21.6z", 1.0]],
  /* outras lavouras: muda com duas folhas */
  outras: [
    ["l", "M12 21.4L12 11.6", 1.8],
    ["s", "M12 14.6Q11.39 7.12 4 8.4Q5.34 14.93 12 14.6z", 1.0],
    ["s", "M12 11.8Q19.28 11.66 19.8 4.4Q11.69 3.67 12 11.8z", 1.0],
    ["l", "M7.6 21.4L16.4 21.4", 1.6]],
  /* ---- outras camadas de pontos (scripts/estudos/icones_camadas.py) ---- */
  /* hidrelétrica: gota com raio */
  hid: [
    ["f", "M12 2.4C12 2.4 4.6 10.6 4.6 15.4a7.4 7.4 0 0 0 14.8 0C19.4 10.6 12 2.4 12 2.4z"],
    ["h", "M13.4 8.8L8.6 15.6h3.1l-1.1 5.4 4.9-7.6h-3.2l1.1-4.6z"]],
  /* eólica: cata-vento de três pás */
  eol: [
    ["f", "M11.1 10.2h1.8l.9 11.4h-3.6z"],
    ["f", "M12 8.6Q15.07 4.8 12 1Q10.32 4.8 12 8.6z"],
    ["f", "M12 8.6Q13.75 13.16 18.58 12.4Q16.13 9.05 12 8.6z"],
    ["f", "M12 8.6Q7.17 7.84 5.42 12.4Q9.55 11.95 12 8.6z"],
    ["s", "M10.3 8.6a1.7 1.7 0 1 0 3.4 0a1.7 1.7 0 1 0 -3.4 0z", 0.8],
    ["l", "M7 21.8L17 21.8", 1.4]],
  /* solar: sol e painel */
  sol: [
    ["f", "M3.9 5.6a2.1 2.1 0 1 0 4.2 0a2.1 2.1 0 1 0 -4.2 0z"],
    ["l", "M9.1 5.6L10.4 5.6", 1.1],
    ["l", "M8.19 7.79L9.11 8.71", 1.1],
    ["l", "M6 8.7L6 10", 1.1],
    ["l", "M3.81 7.79L2.89 8.71", 1.1],
    ["l", "M2.9 5.6L1.6 5.6", 1.1],
    ["l", "M3.81 3.41L2.89 2.49", 1.1],
    ["l", "M6 2.5L6 1.2", 1.1],
    ["l", "M8.19 3.41L9.11 2.49", 1.1],
    ["f", "M6.4 11.2h11.4l4.4 8.2H10.8z"],
    ["x", "M10.2 11.2L14.6 19.4", 0.9],
    ["x", "M14 11.2L18.4 19.4", 0.9],
    ["x", "M8.6 15.3L20 15.3", 0.9],
    ["l", "M16.5 19.4L16.5 22.2", 1.5],
    ["l", "M12.5 22.4L20.5 22.4", 1.4]],
  /* térmica a biomassa: folha com nervuras */
  bio: [
    ["f", "M4.6 19.4Q18.48 17.88 20 4Q6.12 5.52 4.6 19.4z"],
    ["x", "M6.6 17.4L17.4 6.6", 1.0],
    ["x", "M10.4 13.6L9.4 10.2", 0.8],
    ["x", "M10.4 13.6L13.8 14.6", 0.8],
    ["x", "M13.8 10.2L12.8 6.8", 0.8],
    ["x", "M13.8 10.2L17.2 11.2", 0.8],
    ["l", "M3.2 20.8L5.6 18.4", 1.6]],
  /* térmica fóssil: fábrica com chaminé e fumaça */
  fos: [
    ["f", "M2.6 21.4V12.2l4.8 3V12.2l4.8 3V12.2l4.4 2.7v6.5z"],
    ["f", "M16.8 5.4h3.4v16h-3.4z"],
    ["h", "M4.6 17h2v2h-2zM9.4 17h2v2h-2zM14.1 17h1.6v2h-1.6z"],
    ["f", "M16.9 2.9a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0 -3 0z"],
    ["f", "M20 1.9a1 1 0 1 0 2 0a1 1 0 1 0 -2 0z"],
    ["l", "M2 21.6L22 21.6", 1.2]],
  /* nuclear: átomo */
  nuc: [
    ["l", "M21.6 12A9.6 3.5 0 1 0 2.4 12A9.6 3.5 0 1 0 21.6 12z", 1.35],
    ["l", "M16.8 20.31A9.6 3.5 60 1 0 7.2 3.69A9.6 3.5 60 1 0 16.8 20.31z", 1.35],
    ["l", "M16.8 3.69A9.6 3.5 -60 1 0 7.2 20.31A9.6 3.5 -60 1 0 16.8 3.69z", 1.35],
    ["f", "M10 12a2 2 0 1 0 4 0a2 2 0 1 0 -4 0z"]],
  /* poço de petróleo: torre de perfuração */
  poco: [
    ["l", "M12 2.6L6.1 21.4", 1.7],
    ["l", "M12 2.6L17.9 21.4", 1.7],
    ["l", "M10.18 8.4L13.82 8.4", 1.3],
    ["l", "M8.42 14L15.58 14", 1.3],
    ["l", "M6.79 19.2L17.21 19.2", 1.3],
    ["l", "M10.18 8.4L15.58 14", 0.9],
    ["l", "M13.82 8.4L8.42 14", 0.9],
    ["l", "M8.42 14L17.21 19.2", 0.9],
    ["l", "M15.58 14L6.79 19.2", 0.9],
    ["f", "M10.4 1.6h3.2v2.4h-3.2z"],
    ["l", "M3.6 21.6L20.4 21.6", 1.8]],
  /* celular: torre com ondas */
  antena: [
    ["f", "M10.2 7.6a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0 -3.6 0z"],
    ["l", "M12 9.4L12 21.6", 1.8],
    ["l", "M12 12.6L8.2 21.6", 1.3],
    ["l", "M12 12.6L15.8 21.6", 1.3],
    ["l", "M7.4 21.8L16.6 21.8", 1.4],
    ["l", "M15.22 4.9A4.2 4.2 0 0 1 15.22 10.3", 1.5],
    ["l", "M17.99 3.25A7.4 7.4 0 0 1 17.99 11.95", 1.5],
    ["l", "M8.78 10.3A4.2 4.2 0 0 1 8.78 4.9", 1.5],
    ["l", "M6.01 11.95A7.4 7.4 0 0 1 6.01 3.25", 1.5]],
  /* velocidade medida do celular: velocímetro com o ponteiro para o lado rápido */
  velocimetro: [
    ["l", "M4.73 19.2A8.4 8.4 0 1 1 19.27 19.2", 2.1],
    ["l", "M6.9 11.1L8.1 11.9M12 8.6V10M17.1 11.1L15.9 11.9", 1.3],
    ["l", "M12 15L16.3 9.9", 2.1],
    ["f", "M10.1 15a1.9 1.9 0 1 0 3.8 0a1.9 1.9 0 1 0 -3.8 0z"]],
  /* banda larga fixa: casa com o sinal do wi-fi */
  casa: [
    ["f", "M2.8 11.6L12 3.4l9.2 8.2-1.3 1.4-.9-.8V21H5V12.2l-.9.8z"],
    ["x", "M7.9 14.3a5.8 5.8 0 0 1 8.2 0", 1.6],
    ["x", "M9.9 16.6a3 3 0 0 1 4.2 0", 1.6],
    ["h", "M10.9 18.9a1.1 1.1 0 1 0 2.2 0a1.1 1.1 0 1 0 -2.2 0z"]],
  /* pedágio: cabine e cancela */
  pedagio: [
    ["f", "M2.6 8.6L6.2 5.6l3.6 3H8.8v12.8H3.6V8.6z"],
    ["h", "M4.6 10.4h3.2v3.2H4.6z"],
    ["f", "M9.8 11.6h12.2v2.8H9.8z"],
    ["h", "M12.2 11.6h1.8l-1 2.8h-1.8zM16 11.6h1.8l-1 2.8H15zM19.8 11.6h1.8l-1 2.8h-1.8z"],
    ["l", "M2 21.6L22 21.6", 1.4]],
  /* porto: âncora */
  ancora: [
    ["l", "M9.9 4.6a2.1 2.1 0 1 0 4.2 0a2.1 2.1 0 1 0 -4.2 0z", 1.6],
    ["l", "M12 6.7L12 20.8", 2],
    ["l", "M7.8 10L16.2 10", 1.9],
    ["l", "M4.8 13.6C5.2 18.6 8.6 21 12 21s6.8-2.4 7.2-7.4", 1.9],
    ["f", "M2.8 15.2l2-3.6 2.4 3.4z"],
    ["f", "M21.2 15.2l-2-3.6-2.4 3.4z"]],
  /* refinaria: torres de destilação e tanque */
  refinaria: [
    ["f", "M4.6 21.4V8.2a2 2 0 0 1 4 0v13.2z"],
    ["f", "M10.6 21.4V4.6a1.8 1.8 0 0 1 3.6 0v16.8z"],
    ["f", "M15.8 21.4v-5.4a3 3 0 0 1 6 0v5.4z"],
    ["x", "M4.6 12.4L8.6 12.4", 0.8],
    ["x", "M4.6 16.4L8.6 16.4", 0.8],
    ["x", "M10.6 9L14.2 9", 0.8],
    ["x", "M10.6 13.2L14.2 13.2", 0.8],
    ["x", "M10.6 17.4L14.2 17.4", 0.8],
    ["l", "M8.6 10.6L10.6 10.6", 1.1],
    ["l", "M14.2 13.6L17.6 13.6", 1.1],
    ["l", "M2.4 21.6L21.6 21.6", 1.4]],
  /* unidade de processamento de gás natural: chama */
  upgn: [
    ["f", "M12 2.2c.8 3.6 6.4 6.6 6.4 12.4a6.4 6.4 0 0 1-12.8 0c0-3.2 1.7-5.4 3.4-6.8.2 2.2 1 3.6 2.4 4.3C11.6 9.4 11 5.6 12 2.2z"],
    ["h", "M12 12.6c.5 2 3 3.2 3 5.8a3 3 0 0 1-6 0c0-1.6.8-2.7 1.6-3.4.2 1 .6 1.6 1.2 2-.3-1.6-.2-3 .2-4.4z"]],
  /* passagem de fronteira: duas setas em sentidos opostos cruzando a linha da fronteira (tracejada) */
  passagem: [
    ["l", "M12 2.6v3.4M12 10.9v2.2M12 17.9v3.5", 1.5],
    ["l", "M3.4 8.5h11.8", 2.1],
    ["f", "M14.4 5l6.2 3.5-6.2 3.5z"],
    ["l", "M20.6 15.5H8.8", 2.1],
    ["f", "M9.6 12l-6.2 3.5 6.2 3.5z"]],
  /* terminal de GNL: navio com os tanques esféricos */
  gnl: [
    ["f", "M1.8 14.2h20.4l-2.8 5.6H4.6z"],
    ["s", "M9.2 14.2A2.6 2.6 0 1 0 4 14.2A2.6 2.6 0 1 0 9.2 14.2z", 0.8],
    ["s", "M14.2 14.2A2.6 2.6 0 1 0 9 14.2A2.6 2.6 0 1 0 14.2 14.2z", 0.8],
    ["s", "M19.2 14.2A2.6 2.6 0 1 0 14 14.2A2.6 2.6 0 1 0 19.2 14.2z", 0.8],
    ["f", "M18.8 9.6h2.6v4.6h-2.6z"],
    ["l", "M2.4 22.2q2-1.4 4 0t4 0 4 0 4 0 4 0", 1.2]]
};
/* moradores com sinal 5G: quatro barras de sinal, cheias conforme a faixa (sinal0 = nenhuma cheia ... sinal4 = todas) */
for (let k = 0; k <= 4; k++) ICONES["sinal" + k] = [0, 1, 2, 3].map(i => {
  const x = 3.3 + i * 4.75, t = 16 - 4.1 * i, d = `M${x.toFixed(2)} 20.8V${t.toFixed(1)}h3.4V20.8z`;
  return i < k ? ["f", d] : ["l", d, 1.15];
});
/* desenha o ícone num canvas já posicionado (coordenadas de 24 × 24) */
function desenharIcone(x, partes, cor) {
  x.lineCap = "round"; x.lineJoin = "round";
  for (const [t, d, w] of partes) {
    const P = new Path2D(d);
    if (t === "s") { x.lineWidth = w * 2; x.strokeStyle = RISCO; x.stroke(P); }
    if (t === "f" || t === "s") { x.fillStyle = cor; x.fill(P); }
    else if (t === "h") { x.fillStyle = RISCO; x.fill(P); }
    else if (t === "x" || t === "l") { x.lineWidth = w; x.strokeStyle = t === "x" ? RISCO : cor; x.stroke(P); }
  }
}
/* medalhão de 64 px (32 px no tamanho 1 do mapa, nítido em tela fina) para o MapLibre */
function medalhaoCanvas(partes, cor) {
  const n = 64, c = document.createElement("canvas"); c.width = c.height = n;
  const x = c.getContext("2d");
  x.beginPath(); x.arc(32, 32, 29.5, 0, 2 * Math.PI); x.fillStyle = MEDALHAO; x.fill();
  x.lineWidth = 3; x.strokeStyle = cor; x.stroke();
  x.translate(10.4, 10.4); x.scale(1.8, 1.8); desenharIcone(x, partes, cor);
  return x.getImageData(0, 0, n, n);
}
/* o mesmo desenho em SVG (cor = "currentColor": quem usa define a cor com "color") */
function iconeSVG(partes) {
  return partes.map(([t, d, w]) => t === "f" ? `<path d="${d}" fill="currentColor"/>`
    : t === "h" ? `<path d="${d}" fill="${RISCO}"/>`
    : t === "s" ? `<path d="${d}" fill="currentColor" stroke="${RISCO}" stroke-width="${w * 2}" stroke-linejoin="round" paint-order="stroke"/>`
    : `<path d="${d}" fill="none" stroke="${t === "x" ? RISCO : "currentColor"}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`).join("");
}
/* chave da legenda: o medalhão pequeno, igual ao do mapa */
function chaveIcone(nome, corVar) {
  return `<svg class="key ico" viewBox="0 0 64 64" style="color:var(${corVar})" aria-hidden="true"><circle cx="32" cy="32" r="29.5" fill="${MEDALHAO}" stroke="currentColor" stroke-width="3"/>`
    + `<g transform="translate(10.4 10.4) scale(1.8)">${iconeSVG(ICONES[nome])}</g></svg>`;
}
/* desde 25/10/2026 (diretriz God's Eye View): nome da imagem no mapa (globo) e do padrão "pad-ico-<nome>"
   (versão leve) → [desenho, cor da camada] */
const IMG_ICO = { "us-hid": ["hid", "--hid"], "us-eol": ["eol", "--eol"], "us-sol": ["sol", "--sol"], "us-bio": ["bio", "--bio"], "us-fos": ["fos", "--fos"],
  "us-nuc": ["nuc", "--nuc"], poco: ["poco", "--oil"], "cel-1": ["antena", "--cel1"], "cel-2": ["antena", "--cel2"], "cel-3": ["antena", "--cel3"],
  "cel-4": ["antena", "--cel4"], "ped-0": ["pedagio", "--tr0"], "ped-1": ["pedagio", "--tr1"], "ped-2": ["pedagio", "--tr2"], "ped-3": ["pedagio", "--tr3"],
  "ped-4": ["pedagio", "--tr4"], porto: ["ancora", "--port"], "ref-refinaria": ["refinaria", "--refin"], "ref-upgn": ["upgn", "--upgn"], "ref-gnl": ["gnl", "--gnl"],
  passagem: ["passagem", "--fronteira"] };
/* velocidade (5 faixas), moradores com 5G (sem sinal + 4 faixas) e banda larga fixa (5 faixas), em teste desde 27/10/2026 */
for (let k = 1; k <= 5; k++) { IMG_ICO["vel-" + k] = ["velocimetro", "--vel" + k]; IMG_ICO["bl-" + k] = ["casa", "--bl" + k]; }
for (let k = 0; k <= 4; k++) IMG_ICO["s5g-" + k] = ["sinal" + k, "--c5g" + k];
/* chave da legenda com o medalhão do mapa: camada → desenho, pela cor do item da legenda */
const ICO_LEG = { lav: c => c.replace("--lav-", ""), usinas: c => ({ "--hid": "hid", "--eol": "eol", "--sol": "sol", "--bio": "bio", "--fos": "fos", "--nuc": "nuc" })[c],
  oil: () => "poco", refin: c => ({ "--refin": "refinaria", "--upgn": "upgn", "--gnl": "gnl" })[c], celm: () => "antena", pedagio: () => "pedagio", ports: () => "ancora",
  passa: c => c === "--fronteira" ? "passagem" : null,
  velm: c => /^--vel\d$/.test(c) ? "velocimetro" : null, g5c: c => /^--c5g\d$/.test(c) ? "sinal" + c.slice(-1) : null, blm: c => /^--bl\d$/.test(c) ? "casa" : null };
/* fundo inteiro na página toda, com profundidade (pedido do Edu em 25/10/2026; no site normal desde 26/10/2026). Padrão:
   lente (o fundo B, chão de hexágonos, com a lente gravitacional em volta do globo, desenhado pela placa de vídeo:
   3d/fundo3d.js; na versão leve, sem globo, fica a imagem do B). Para comparar, no endereço: ?fundo=a (facetas),
   b (só a imagem do chão de hexágonos), c (camadas de vidro) ou funil (o chão afunda embaixo do globo). O fundo fica parado atrás da página e anda um pouco ao rolar e ao mexer
   o mouse (paralaxe); quem pede menos movimento no sistema vê o fundo parado. Imagens em site/fundos/, geradas por
   scripts/estudos/fundos.py. Devolve a opção escolhida */
function fundoSite(base) {
  const k = (new URLSearchParams(location.search).get("fundo") || "lente").toLowerCase();
  if (!["a", "b", "c", "funil", "lente"].includes(k)) return null;
  const h = document.documentElement;
  h.classList.add("fundo");
  const img = ["funil", "lente"].includes(k) ? "b" : k;
  h.style.setProperty("--fundo-img", `url("${new URL(base + "fundos/fundo_" + img + ".webp", location.href).href}")`);
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return k;
  let mx = 0, my = 0, pendente = false;
  const aplicar = () => {
    pendente = false;
    h.style.setProperty("--fx", (mx * -18).toFixed(1) + "px");
    h.style.setProperty("--fy", (my * -12 + Math.max(-28, -scrollY * 0.035)).toFixed(1) + "px");
  };
  const pedir = () => { if (!pendente) { pendente = true; requestAnimationFrame(aplicar); } };
  addEventListener("pointermove", e => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; pedir(); }, { passive: true });
  addEventListener("scroll", pedir, { passive: true });
  return k;
}
/* moedas de ouro caindo (botão "Apoie este projeto"; pedido do Edu em 25/10/2026: quatro, em alturas diferentes, como se
   estivessem caindo). Cada moeda: [x, y, raio, giro em graus, achatamento] — achatamento 1 = de frente; menos = de lado,
   girando na queda; a borda grossa aparece embaixo da face */
const MOEDAS = (() => {
  const ESTRELA = "M0.00 -3.70L0.94 -1.29L3.52 -1.14L1.52 0.49L2.17 2.99L0.00 1.60L-2.17 2.99L-1.52 0.49L-3.52 -1.14L-0.94 -1.29z";
  const moeda = ([x, y, r, a, s]) => { const t = 1.3 + 2.2 * (1 - s);
    return `<g transform="translate(${x} ${y}) rotate(${a})">`
      + `<rect x="${-r}" y="0" width="${2 * r}" height="${t}" fill="#7a4806"/><ellipse cy="${t}" rx="${r}" ry="${r * s}" fill="#7a4806"/>`
      + `<g transform="scale(1 ${s})"><circle r="${r}" fill="#e3a12a"/><circle r="${r * 0.84}" fill="#f8cd5b"/>`
      + `<circle r="${r * 0.66}" fill="none" stroke="#c4861c" stroke-width="1"/><path d="${ESTRELA}" fill="#d9952a" transform="scale(${r / 8.6})"/>`
      + `<path d="M${-r * 0.7} ${-r * 0.34}a${r * 0.78} ${r * 0.78} 0 0 1 ${r * 0.47} ${-r * 0.44}" fill="none" stroke="#fff6d2" stroke-width="1.3" stroke-linecap="round"/></g></g>`; };
  return `<svg class="moedas" viewBox="0 0 66 30" aria-hidden="true">`
    + [[9, 19, 7.6, -12, 1], [24.5, 9.5, 7.2, 24, 0.55], [39.5, 20, 7.4, -8, 0.85], [56, 8, 6.8, -32, 0.42]].map(moeda).join("") + `</svg>`;
})();
/* selo "Dados atualizados em [data]" (diretriz God's Eye View; no site desde 25/10/2026): a data da última vez
   que um robô buscou dados com sucesso nos órgãos oficiais (arquivos robo*.json, gravados pelo robô do GitHub); cada
   camada continua com a própria data no painel. A data é a do registro do robô (em UTC), a mesma que o painel mostra.
   Ao criar um robô novo, acrescentar o arquivo dele em ROBOS */
const ROBOS = ["robo_ibge.json", "petroleo/robo.json", "energia/robo_aneel.json", "energia/robo.json", "celular/robo.json",
  "trafego/robo.json", "aeroportos/robo.json", "defesa/robo.json"];
async function seloDados(base) {
  const ler = async a => { try { const r = await fetch(base + a); return r.ok ? await r.json() : null; } catch (e) { return null; } };
  const rs = await Promise.all(ROBOS.map(ler));
  const datas = rs.filter(r => r && r.rodou_em && Object.values(r.passos || {}).some(v => String(v).startsWith("ok")))
    .map(r => r.rodou_em.slice(0, 10)).sort();
  const brand = document.querySelector(".brand");
  if (!datas.length || !brand) return;
  const d = datas[datas.length - 1].split("-").reverse().join("/");
  brand.insertAdjacentHTML("beforeend", `<span class="selo-dados" title="Última vez que o robô do site buscou os dados nos órgãos oficiais. Cada camada mostra a própria data no painel.">`
    + `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>Dados atualizados em ${d}</span>`);
}
