/* Relevo em ondas (estudo de 22/10/2026, testado e descartado pelo Edu: "não está ficando bom"; efeito pesado).
   Guardado só como referência. Era um trecho de site/3d/app3d.js (versão de teste): cada estado virava um morro liso,
   com a forma de uma lona presa na divisa (equação de Poisson, resolvida por SOR numa grade grossa e acertada numa fina),
   altura proporcional ao número da pintura, e os ladrilhos de altitude saíam do próprio navegador (maplibregl.addProtocol,
   formato de altitude do Mapbox). Para voltar a usar, precisa de: TESTE, estados, NAME, map, modo3d e da função render(). */
  /* ---------- versão de teste: estados em altura, como ondas ----------
     Cada estado vira um morro liso: o ponto mais alto fica no meio do estado, com altura proporcional ao número da pintura
     (o dobro do número, o dobro da altura), e o terreno desce até o chão nas divisas, sem paredes entre os estados.
     Em "Sem cor", o Brasil inteiro sobe como um morro só. A forma é a de uma lona presa na divisa e empurrada de baixo
     (equação de Poisson, ∇²u = −1, com u = 0 na divisa): lisa, sem quinas, mais alta onde o estado é mais "largo".
     É resolvida aqui mesmo, primeiro numa grade grossa (≈ 22 km) e depois acertada numa grade fina (≈ 5,5 km). Os ladrilhos
     de altitude saem da grade fina pelo endereço "altura://" (no formato de altitude do Mapbox, que passa de 32 km).
     Pontos, linhas e cores acompanham o relevo. */
  const ONDA = { oeste: -74.4, leste: -28.4, norte: 5.6, sul: -34.2, passo: 0.05, grosso: 0.2, max: 520000 };
  let onda = null, ondaChave = null, ondaVer = 0, ondaLigada = false, ondaEx = 1;
  /* os estados numa grade de passo p (graus): linha a linha, pela regra par-ímpar (o centro de cada quadradinho decide) */
  function rasterizar(p) {
    const W = Math.ceil((ONDA.leste - ONDA.oeste) / p), H = Math.ceil((ONDA.norte - ONDA.sul) / p), idx = new Uint8Array(W * H);
    const cruz = Array.from({ length: H }, () => []);
    estados.features.forEach((f, k) => {
      const g = f.geometry, usadas = [];
      for (const pl of (g.type === "Polygon" ? [g.coordinates] : g.coordinates)) for (const r of pl) for (let i = 0; i < r.length - 1; i++) {
        const xa = r[i][0], ya = r[i][1], xb = r[i + 1][0], yb = r[i + 1][1];
        if (ya === yb) continue;
        const j0 = Math.max(0, Math.ceil((ONDA.norte - Math.max(ya, yb)) / p - 0.5)), j1 = Math.min(H - 1, Math.floor((ONDA.norte - Math.min(ya, yb)) / p - 0.5));
        for (let j = j0; j <= j1; j++) {
          const lat = ONDA.norte - (j + 0.5) * p;
          if ((ya > lat) === (yb > lat)) continue;
          if (!cruz[j].length) usadas.push(j);
          cruz[j].push(xa + (lat - ya) * (xb - xa) / (yb - ya));
        }
      }
      for (const j of usadas) {
        const c = cruz[j].sort((a, b) => a - b);
        for (let m = 0; m + 1 < c.length; m += 2) {
          const i0 = Math.max(0, Math.ceil((c[m] - ONDA.oeste) / p - 0.5)), i1 = Math.min(W - 1, Math.ceil((c[m + 1] - ONDA.oeste) / p - 0.5) - 1);
          for (let i = i0; i <= i1; i++) idx[j * W + i] = k + 1;
        }
        cruz[j] = [];
      }
    });
    return { W, H, p, idx };
  }
  /* lona: ∇²u = −1 dentro de cada região (estado ou Brasil inteiro), por sobre-relaxação (SOR), varrendo para a frente e
     para trás. Os quadradinhos da divisa ficam presos no chão (u = 0) dos dois lados: assim o vale entre dois estados
     é contínuo, sem degrau. Distâncias em km; o passo leste-oeste encolhe com o cosseno da latitude */
  function lona(G, reg, u, voltas, omega) {
    const { W, H, p } = G, sy = 1 / (p * 110.6) ** 2, sx = new Float64Array(H);
    for (let j = 0; j < H; j++) sx[j] = 1 / (p * 111.3 * Math.cos((ONDA.norte - (j + 0.5) * p) * Math.PI / 180)) ** 2;
    const dentro = [];
    for (let q = 0; q < W * H; q++) {
      const a = reg[q];
      if (!a) { u[q] = 0; continue; }
      const i = q % W, j = (q - i) / W;
      if (i > 0 && i < W - 1 && j > 0 && j < H - 1 && reg[q - 1] === a && reg[q + 1] === a && reg[q - W] === a && reg[q + W] === a) dentro.push(q);
      else u[q] = 0;
    }
    const L = Int32Array.from(dentro), n = L.length;
    for (let v = 0; v < voltas; v++) {
      const frente = v % 2 === 0;
      for (let m = 0; m < n; m++) {
        const q = L[frente ? m : n - 1 - m], a = sx[(q / W) | 0];
        const gs = ((u[q - 1] + u[q + 1]) * a + (u[q - W] + u[q + W]) * sy + 1) / (2 * a + 2 * sy);
        u[q] += omega * (gs - u[q]);
      }
    }
    return u;
  }
  /* forma do morro em cada ponto da grade fina: 0 na divisa e 1 no ponto mais alto da lona; a meia onda de cosseno
     deixa o fundo dos vales e o topo dos morros arredondados */
  function formaOnda(F, C, regF, regC, voltasC, omegaC) {
    const uC = lona(C, regC, new Float64Array(C.W * C.H), voltasC, omegaC), uF = new Float64Array(F.W * F.H);
    /* chute inicial na grade fina: média dos quatro pontos vizinhos da grade grossa que são da mesma região */
    for (let j = 0; j < F.H; j++) {
      const gy = ((j + 0.5) * F.p) / C.p - 0.5, j0 = Math.floor(gy), fy = gy - j0;
      for (let i = 0; i < F.W; i++) {
        const q = j * F.W + i, a = regF[q];
        if (!a) continue;
        const gx = ((i + 0.5) * F.p) / C.p - 0.5, i0 = Math.floor(gx), fx = gx - i0;
        let s = 0, w = 0;
        const soma = (ii, jj, ww) => { if (ii < 0 || jj < 0 || ii >= C.W || jj >= C.H) return; const qc = jj * C.W + ii; if (regC[qc] !== a) return; s += uC[qc] * ww; w += ww; };
        soma(i0, j0, (1 - fx) * (1 - fy)); soma(i0 + 1, j0, fx * (1 - fy)); soma(i0, j0 + 1, (1 - fx) * fy); soma(i0 + 1, j0 + 1, fx * fy);
        uF[q] = w > 0 ? s / w : 0;
      }
    }
    lona(F, regF, uF, 40, 1.7);
    const mx = new Float64Array(256), out = new Float32Array(F.W * F.H);
    for (let q = 0; q < uF.length; q++) if (regF[q] && uF[q] > mx[regF[q]]) mx[regF[q]] = uF[q];
    for (let q = 0; q < uF.length; q++) if (regF[q]) out[q] = (1 - Math.cos(Math.PI * Math.min(1, uF[q] / mx[regF[q]]))) / 2;
    return out;
  }
  function prepararOnda() {
    if (onda) return onda;
    const t0 = performance.now(), F = rasterizar(ONDA.passo), C = rasterizar(ONDA.grosso);
    const brF = F.idx.map(a => a ? 1 : 0), brC = C.idx.map(a => a ? 1 : 0);
    onda = { W: F.W, H: F.H, idx: F.idx, ufs: estados.features.map(f => f.properties.sigla),
      fE: formaOnda(F, C, F.idx, C.idx, 260, 1.9), alt: new Float32Array(F.W * F.H),
      brasil: () => onda.fB || (onda.fB = formaOnda(F, C, brF, brC, 700, 1.96)) };
    onda.ms = Math.round(performance.now() - t0);
    return onda;
  }
  function alturasOnda(P) {
    const g = prepararOnda(), A = new Float32Array(29);
    let forma = g.fE;
    if (P && P.val) {
      const vals = Object.keys(NAME).map(P.val).filter(v => v != null), mx = Math.max(...vals, 0);
      g.ufs.forEach((s, k) => { const v = P.val(s); A[k + 1] = v == null || mx <= 0 ? 0 : ONDA.max * Math.max(0, v) / mx; });
    } else { forma = g.brasil(); A.fill(ONDA.max * 0.45); A[0] = 0; }
    for (let q = 0; q < g.alt.length; q++) g.alt[q] = A[g.idx[q]] * forma[q];
  }
  /* ladrilho de altitude (256 × 256) tirado da grade; fora do Brasil, altitude zero. Guardados por versão: o mapa pede
     o mesmo ladrilho para o terreno e para a sombra */
  const latTile = (y, z) => 180 / Math.PI * Math.atan(Math.sinh(Math.PI - 2 * Math.PI * y / 2 ** z));
  const guardaOnda = new Map();
  async function ladrilhoOnda(z, x, y) {
    const g = onda, T = 256, lonA = x / 2 ** z * 360 - 180, lonB = (x + 1) / 2 ** z * 360 - 180;
    const fora = !g || lonB < ONDA.oeste || lonA > ONDA.leste || latTile(y, z) < ONDA.sul || latTile(y + 1, z) > ONDA.norte;
    const cv = typeof OffscreenCanvas !== "undefined" ? new OffscreenCanvas(T, T) : Object.assign(document.createElement("canvas"), { width: T, height: T });
    const cx = cv.getContext("2d"), im = cx.createImageData(T, T), d = im.data;
    for (let jj = 0; jj < T; jj++) {
      const gy = (ONDA.norte - latTile(y + (jj + 0.5) / T, z)) / ONDA.passo - 0.5;
      for (let ii = 0; ii < T; ii++) {
        let h = 0;
        if (!fora) {
          const gx = (lonA + (ii + 0.5) / T * (lonB - lonA) - ONDA.oeste) / ONDA.passo - 0.5;
          if (gx >= 0 && gy >= 0 && gx < g.W - 1 && gy < g.H - 1) {
            const i0 = gx | 0, j0 = gy | 0, fx = gx - i0, fy = gy - j0, o = j0 * g.W + i0, A = g.alt;
            h = (A[o] * (1 - fx) + A[o + 1] * fx) * (1 - fy) + (A[o + g.W] * (1 - fx) + A[o + g.W + 1] * fx) * fy;
          }
        }
        /* formato do Mapbox: altitude = −10.000 m + (R·65.536 + G·256 + B) × 0,1 m */
        const v = Math.round((h + 10000) * 10), k = (jj * T + ii) * 4;
        d[k] = (v >> 16) & 255; d[k + 1] = (v >> 8) & 255; d[k + 2] = v & 255; d[k + 3] = 255;
      }
    }
    cx.putImageData(im, 0, 0);
    const blob = cv.convertToBlob ? await cv.convertToBlob({ type: "image/png" }) : await new Promise(r => cv.toBlob(r, "image/png"));
    return blob.arrayBuffer();
  }
  if (TESTE) maplibregl.addProtocol("altura", async params => {
    const m = /altura:\/\/v(\d+)\/(\d+)\/(\d+)\/(\d+)/.exec(params.url), chave = m.slice(1).join("/");
    if (!guardaOnda.has(chave)) guardaOnda.set(chave, ladrilhoOnda(+m[2], +m[3], +m[4]));
    return { data: (await guardaOnda.get(chave)).slice(0) };
  });
  /* de perto, os morros baixam (senão um morro de 520 km passaria por cima da câmera) */
  const exagero = () => { const z = map.getZoom(); return z <= 4.5 ? 1 : z >= 7.5 ? 0.12 : 1 - (z - 4.5) / 3 * 0.88; };
  map.on("zoomend", () => {
    if (!ondaLigada) return;
    const e = exagero();
    if (Math.abs(e - ondaEx) > 0.04) { ondaEx = e; map.setTerrain({ source: "altura", exaggeration: e }); }
  });
  function onda3d(P, L) {
    const on = elevado && !L;
    if (!on) {
      if (ondaLigada) { ondaLigada = false; if (!modo3d) map.setTerrain(null); map.setLayoutProperty("altura-sombra", "visibility", "none"); }
      return;
    }
    const chave = P && P.val ? P.id : "brasil", url = () => [`altura://v${ondaVer}/{z}/{x}/{y}`];
    if (chave !== ondaChave) {
      alturasOnda(P); ondaChave = chave; ondaVer++; guardaOnda.clear();
      if (map.getSource("altura")) for (const s of ["altura", "altura-hs"]) map.getSource(s).setTiles(url());
    }
    if (!map.getSource("altura")) {
      /* duas fontes iguais: uma para o terreno e outra para a sombra (o MapLibre pede separadas) */
      for (const s of ["altura", "altura-hs"]) map.addSource(s, { type: "raster-dem", tiles: url(), tileSize: 256, maxzoom: 7, encoding: "mapbox" });
      map.addLayer({ id: "altura-sombra", type: "hillshade", source: "altura-hs",
        paint: { "hillshade-exaggeration": 0.65, "hillshade-shadow-color": "rgba(2,8,12,.7)", "hillshade-highlight-color": "rgba(255,250,230,.28)",
          "hillshade-accent-color": "rgba(0,0,0,0)" } }, "zee-line");
    }
    map.setLayoutProperty("altura-sombra", "visibility", "visible");
    if (!ondaLigada) { ondaLigada = true; ondaEx = exagero(); map.setTerrain({ source: "altura", exaggeration: ondaEx }); }
  }

  /* ---------- luzes à noite ---------- */
