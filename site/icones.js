/* Brasil em Camadas — ícones das camadas por município (desenhos em 24 × 24), usados no globo (3d/app3d.js)
   e na versão leve (2d/app.js). Versão de teste: aparecem só dentro do estado escolhido, num medalhão escuro
   com aro na cor da camada. Gerados por scripts/estudos/icones_lavouras.py.
   Cada ícone é uma lista de partes:
     ["f", caminho]     preenchido na cor da camada
     ["s", caminho, w]  preenchido, com um contorno escuro de w em volta (separa peças que se sobrepõem)
     ["x", caminho, w]  risco escuro de largura w (sulco, nó, grão marcado)
     ["l", caminho, w]  risco na cor da camada (haste, cabinho) */
"use strict";
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
    ["l", "M7.6 21.4L16.4 21.4", 1.6]]
};
/* desenha o ícone num canvas já posicionado (coordenadas de 24 × 24) */
function desenharIcone(x, partes, cor) {
  x.lineCap = "round"; x.lineJoin = "round";
  for (const [t, d, w] of partes) {
    const P = new Path2D(d);
    if (t === "s") { x.lineWidth = w * 2; x.strokeStyle = RISCO; x.stroke(P); }
    if (t === "f" || t === "s") { x.fillStyle = cor; x.fill(P); }
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
    : t === "s" ? `<path d="${d}" fill="currentColor" stroke="${RISCO}" stroke-width="${w * 2}" stroke-linejoin="round" paint-order="stroke"/>`
    : `<path d="${d}" fill="none" stroke="${t === "x" ? RISCO : "currentColor"}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>`).join("");
}
/* chave da legenda: o medalhão pequeno, igual ao do mapa */
function chaveIcone(nome, corVar) {
  return `<svg class="key ico" viewBox="0 0 64 64" style="color:var(${corVar})" aria-hidden="true"><circle cx="32" cy="32" r="29.5" fill="${MEDALHAO}" stroke="currentColor" stroke-width="3"/>`
    + `<g transform="translate(10.4 10.4) scale(1.8)">${iconeSVG(ICONES[nome])}</g></svg>`;
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
