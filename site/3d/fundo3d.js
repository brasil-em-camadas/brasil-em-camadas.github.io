/* Brasil em Camadas — fundo do globo com distorção gravitacional (versão de teste; pedido do Edu em 25/10/2026: "gostei
   mais do B, e pensei como ficaria se na parte em torno do globo tivesse o efeito da distorção gravitacional? com essas
   mesmas linhas?"). O chão de hexágonos do fundo B é desenhado pela placa de vídeo (WebGL2), atrás da página toda, e se
   deforma em volta do globo:
     funil  o chão afunda embaixo do globo, como na imagem clássica do espaço-tempo curvado pela massa de um planeta;
     lente  as linhas e o brilho do horizonte se curvam em volta do contorno do globo, como a luz em volta de um buraco
            negro (lente gravitacional: cada ponto do fundo aparece deslocado para longe do centro). Escolhida pelo
            Edu em 25/10/2026; o desvio no contorno é menor que o raio, para não formar o anel ("auréola") em volta.
   O efeito acompanha a posição, o tamanho e a inclinação do globo (aproximar, afastar, relevo 3D) e some quando o globo
   enche a tela. Só redesenha quando algo muda (globo, tamanho da janela, rolagem, mouse). Sem WebGL2, fica a imagem do
   fundo B (icones.js, fundoTeste). Carregado só na versão de teste, por app3d.js. */
"use strict";
function fundoGravidade(map, modo) {
  const cv = document.createElement("canvas");
  cv.className = "fundo-vivo";
  cv.setAttribute("aria-hidden", "true");
  const gl = cv.getContext("webgl2", { alpha: false, antialias: false, depth: false, stencil: false, powerPreference: "low-power" });
  if (!gl) return false;
  const VS = `#version 300 es
in vec2 p;
void main() { gl_Position = vec4(p, 0.0, 1.0); }`;
  const FS = `#version 300 es
precision highp float;
uniform vec2 uRes;      // tamanho da tela (px CSS)
uniform float uDpr;
uniform vec2 uOff;      // paralaxe (px CSS)
uniform vec3 uG;        // globo: centro x, y e raio (px CSS, na tela); com a câmera inclinada, raio na horizontal
uniform float uQ;       // contorno do globo inclinado: altura / largura (1 = círculo)
uniform float uK;       // força do efeito (0 a 1)
uniform int uModo;      // 0 = só o chão, 1 = funil, 2 = lente
out vec4 cor;
const float HC = 1.0;   // altura da câmera sobre o chão
const float HEX = 0.554; // largura do hexágono (de lado a lado), em unidades do chão
const vec3 CEU0 = vec3(2.0, 6.0, 11.0) / 255.0, CEU1 = vec3(13.0, 38.0, 51.0) / 255.0;
const vec3 CHAO0 = vec3(11.0, 34.0, 46.0) / 255.0, CHAO1 = vec3(3.0, 9.0, 15.0) / 255.0;
const vec3 BRILHO = vec3(58.0, 107.0, 114.0) / 255.0, OURO = vec3(242.0, 192.0, 105.0) / 255.0, LINHA = vec3(230.0, 180.0, 80.0) / 255.0;
float H, F, CX, A, S;
vec2 W;
float hexDist(vec2 p) { p = abs(p); return max(dot(p, vec2(0.5, 0.8660254)), p.x); }
vec2 hexLocal(vec2 uv) {
  const vec2 r = vec2(1.0, 1.7320508), h = r * 0.5;
  vec2 a = mod(uv, r) - h, b = mod(uv - h, r) - h;
  return dot(a, a) < dot(b, b) ? a : b;
}
// altura do chão (o funil é uma depressão com a forma 1/(1 + r²), mais funda no centro)
float altura(vec2 xz) {
  if (uModo != 1) return 0.0;
  vec2 d = xz - W;
  return -A / (1.0 + dot(d, d) / (S * S));
}
// ponto do chão visto no pixel s: (X, Z, achou)
vec3 chao(vec2 s) {
  vec3 d = vec3((s.x - CX) / F, -(s.y - H) / F, 1.0);
  if (uModo != 1 || A < 1e-3) {
    if (d.y >= -1e-5) return vec3(0.0);
    float t = HC / -d.y;
    return vec3(t * d.x, t, 1.0);
  }
  // só marcha o raio quando a trilha dele no chão passa perto do funil; longe dele, o chão é plano
  if (d.y < -1e-5) {
    float tf = HC / -d.y;
    vec2 a0 = vec2(0.0), a1 = vec2(tf * d.x, tf), ab = a1 - a0;
    float u = clamp(dot(W - a0, ab) / dot(ab, ab), 0.0, 1.0);
    if (length(W - (a0 + ab * u)) > 3.5 * S) return vec3(tf * d.x, tf, 1.0);
  }
  float t0 = 0.3, t1 = 90.0, ta = t0, tb = -1.0;
  for (int i = 1; i <= 56; i++) {
    float t = t0 * pow(t1 / t0, float(i) / 56.0);
    vec3 P = vec3(t * d.x, HC + t * d.y, t);
    if (P.y < altura(P.xz)) { tb = t; break; }
    ta = t;
  }
  if (tb < 0.0) return vec3(0.0);
  for (int j = 0; j < 8; j++) {
    float tm = 0.5 * (ta + tb);
    vec3 P = vec3(tm * d.x, HC + tm * d.y, tm);
    if (P.y < altura(P.xz)) tb = tm; else ta = tm;
  }
  return vec3(tb * d.x, tb, 1.0);
}
vec3 cena(vec2 s) {
  float Ht = uRes.y, Wt = uRes.x;
  vec3 c;
  if (s.y <= H) c = mix(CEU0, CEU1, pow(clamp(s.y / H, 0.0, 1.0), 2.2));
  else c = mix(CHAO0, CHAO1, pow(clamp((s.y - H) / (Ht - H), 0.0, 1.0), 0.7));
  // brilho do horizonte (azul) e o fio dourado no meio dele
  float gy = (s.y - H) / (0.05 * Ht), gx = (s.x - CX) / (0.55 * Wt);
  c += BRILHO * 0.3 * exp(-gy * gy) * exp(-gx * gx);
  float oy = (s.y - H) / (0.012 * Ht), ox = (s.x - CX) / (0.35 * Wt);
  c += OURO * 0.10 * exp(-oy * oy) * exp(-ox * ox);
  vec3 q = chao(s);
  if (q.z > 0.5) {
    vec2 xz = q.xy;
    float fundo = uModo == 1 ? clamp(-altura(xz) / max(A, 1e-3), 0.0, 1.0) : 0.0;
    c *= mix(1.0, 0.62, fundo);                       // o fundo do funil mais escuro
    vec2 uv = xz / HEX;
    float e = 0.5 - hexDist(hexLocal(uv));
    float w = max(fwidth(e), 1e-5);
    float lw = mix(2.2, 0.9, clamp(xz.y / 12.0, 0.0, 1.0)) * 0.5;
    float linha = 1.0 - smoothstep((lw - 0.5) * w, (lw + 0.5) * w, e);
    float longe = pow(clamp(1.15 - xz.y / 34.0, 0.0, 1.0), 1.3);
    float lado = exp(-pow((s.x - CX) / (0.75 * Wt), 2.0));
    float perto = clamp((s.y - H) / (0.03 * Ht), 0.0, 1.0);
    if (uModo == 1) perto = max(perto, fundo);
    float moire = 1.0 - smoothstep(0.12, 0.35, length(fwidth(uv)));
    float a = linha * longe * lado * perto * moire * 0.62 * (1.0 + 0.7 * fundo);
    c = mix(c, LINHA, clamp(a, 0.0, 1.0));
  }
  return c;
}
void main() {
  vec2 p = vec2(gl_FragCoord.x, uRes.y * uDpr - gl_FragCoord.y) / uDpr;
  H = 0.6 * uRes.y; F = 1.15 * uRes.x; CX = uG.z > 0.0 ? uG.x - uOff.x : 0.4 * uRes.x;
  A = 0.0; S = 1.0; W = vec2(0.0);
  if (uModo == 1 && uK > 0.0 && uG.z > 0.0) {
    // o centro do funil fica no chão, embaixo do globo; o tamanho do funil acompanha o raio do globo
    float yb = max(uG.y - uOff.y + 0.85 * uG.z, H + 12.0);
    float zw = clamp(HC * F / (yb - H), 3.0, 12.0);
    W = vec2((uG.x - uOff.x - CX) * zw / F, zw);
    float rw = clamp(uG.z * zw / F, 0.3, 2.6);
    A = 1.05 * rw * uK; S = 1.35 * rw;
  }
  vec2 s = p - uOff;
  if (uModo == 2 && uK > 0.0 && uG.z > 0.0) {
    // lente: o fundo visto no pixel p vem do ponto β = θ − α(θ), na mesma direção a partir do centro do globo.
    // α(θ) = 0,9·R·(R/θ)^0,6: no contorno o desvio é 0,9 do raio (menor que o raio, então o anel de Einstein, a
    // "auréola" em volta do globo, fica escondido atrás dele) e cai devagar com a distância, para as linhas
    // continuarem curvadas longe do globo (pedido do Edu em 25/10/2026: tirar o arco luminoso atrás do globo)
    // Com o relevo 3D (câmera inclinada), o contorno é uma elipse um pouco mais alta que larga: a conta é feita com a
    // altura encolhida (uQ), como se fosse um círculo, e depois volta ao normal
    vec2 v = p - uG.xy;
    v.y /= uQ;
    float rho = max(length(v), 1.0);
    float te = 0.9 * uG.z * uK;
    float beta = rho - te * pow(uG.z / rho, 0.6);
    vec2 d = v / rho * beta;
    d.y *= uQ;
    s = uG.xy + d - uOff;
  }
  vec3 c = cena(s);
  float d = length(p / uRes - 0.5) / 0.7071;
  c *= 1.0 - 0.45 * pow(clamp(d, 0.0, 1.0), 2.2);
  cor = vec4(c, 1.0);
}`;
  const sh = (tipo, src) => {
    const s = gl.createShader(tipo); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) { console.warn("fundo: " + gl.getShaderInfoLog(s)); return null; }
    return s;
  };
  const vs = sh(gl.VERTEX_SHADER, VS), fs = sh(gl.FRAGMENT_SHADER, FS);
  if (!vs || !fs) return false;
  const pr = gl.createProgram(); gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
  if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) { console.warn("fundo: " + gl.getProgramInfoLog(pr)); return false; }
  gl.useProgram(pr);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  const loc = gl.getAttribLocation(pr, "p"); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
  const U = {}; for (const n of ["uRes", "uDpr", "uOff", "uG", "uQ", "uK", "uModo"]) U[n] = gl.getUniformLocation(pr, n);
  gl.uniform1i(U.uModo, modo === "funil" ? 1 : modo === "lente" ? 2 : 0);
  document.body.prepend(cv);
  document.documentElement.classList.add("fundo-vivo");
  const menos = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let mx = 0, my = 0, ultimo = "", pedido = false;
  /* contorno do globo na tela, pela câmera do MapLibre 5 (globo): a câmera fica a F px do ponto central, olhando para
     ele, inclinada pelo ângulo φ (pitch); o centro da esfera fica e px abaixo desse ponto (e = raio do globo em px).
     Visto da câmera, o contorno é um cone de meia-abertura a, com o eixo inclinado b para baixo:
       tan b = e·sen φ / (F + e·cos φ),  sen a = e / √(F² + 2F·e·cos φ + e²)
     Na tela vira uma elipse em pé, com topo em F·tan(b − a) e base em F·tan(b + a) (medidos do centro da projeção, para
     baixo) e meia-largura tirada do mesmo cone. Sem inclinação (b = 0), é o círculo de raio F·e / √(F² + 2F·e).
     Antes de 25/10/2026 o efeito sumia com o relevo 3D ligado (o Edu notou); agora acompanha a inclinação. */
  function globo() {
    try {
      const c = map.getCenter(), r = map.getContainer().getBoundingClientRect(), tr = map.transform;
      const p0 = map.project(c);                       /* centro da projeção: o ponto central fica sempre no eixo da câmera */
      const F = tr.cameraToCenterDistance;
      const e = tr.worldSize / (2 * Math.PI) / Math.cos(c.lat * Math.PI / 180);
      const fi = map.getPitch() * Math.PI / 180;
      const b = Math.atan2(e * Math.sin(fi), F + e * Math.cos(fi));
      const a = Math.asin(Math.min(1, e / Math.sqrt(F * F + 2 * F * e * Math.cos(fi) + e * e)));
      if (!(F > 0 && e > 0) || b + a > Math.PI / 2 - 0.03) return [0, 0, 0, 0, 1];   /* globo aberto embaixo: enche a tela */
      const y0 = F * Math.tan(b - a), y1 = F * Math.tan(b + a), yc = (y0 + y1) / 2;
      const w = (yc * Math.sin(b) + F * Math.cos(b)) / Math.cos(a);
      const Rx = Math.sqrt(Math.max(1, w * w - yc * yc - F * F)), q = Math.max(1, (y1 - y0) / 2 / Rx);
      const m = Rx / Math.min(innerWidth, innerHeight), gy = r.top + p0.y + yc;
      let k = 1 - Math.max(0, Math.min(1, (m - 0.75) / 0.55));
      /* globo saindo pelo alto da tela (página rolada até o rodapé): o efeito some aos poucos */
      k *= 1 - Math.max(0, Math.min(1, -(gy + Rx * q) / (1.5 * Rx)));
      return [r.left + p0.x, gy, Rx, k, q];
    } catch (err) { return [0, 0, 0, 0, 1]; }
  }
  function desenhar() {
    pedido = false;
    const dpr = Math.min(devicePixelRatio || 1, 1.5), w = innerWidth, h = innerHeight;
    const [gx, gy, R, k, q] = globo();
    const ox = menos ? 0 : mx * -18, oy = menos ? 0 : my * -12 + Math.max(-28, -scrollY * 0.035);
    const chave = [w, h, dpr, gx, gy, R, k, q * 50, ox, oy].map(v => Math.round(v * 2)).join(",");
    if (chave === ultimo) return;
    ultimo = chave;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
    gl.viewport(0, 0, cv.width, cv.height);
    gl.uniform2f(U.uRes, w, h); gl.uniform1f(U.uDpr, dpr); gl.uniform2f(U.uOff, ox, oy);
    gl.uniform3f(U.uG, gx, gy, R); gl.uniform1f(U.uQ, q); gl.uniform1f(U.uK, k);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  const pedir = () => { if (!pedido) { pedido = true; requestAnimationFrame(desenhar); } };
  map.on("move", pedir); map.on("resize", pedir); map.on("load", pedir);
  addEventListener("resize", pedir);
  addEventListener("scroll", pedir, { passive: true });
  if (!menos) addEventListener("pointermove", e => { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; pedir(); }, { passive: true });
  /* se a placa de vídeo descartar o desenho, volta a imagem do fundo B */
  cv.addEventListener("webglcontextlost", () => { cv.remove(); document.documentElement.classList.remove("fundo-vivo"); });
  pedir();
  window.__fundo = { desenhar: () => { ultimo = ""; desenhar(); }, globo };
  return true;
}
