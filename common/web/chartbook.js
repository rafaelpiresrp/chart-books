/* Chartbooks: gráficos interativos em SVG no estilo dos documentos em LaTeX
   (painel creme, texto preto, grade clara). Tipos: "tempo" (barras, barras empilhadas e linhas por mês)
   e "barras_h" (barras horizontais). Dicas com o mês e os valores, legenda que liga e desliga séries,
   setas do teclado, botões de período/visão, listas de séries e CSV gerado aqui mesmo.
   Dados e especificações: <script id="chartbook-dados" type="application/json">, montado em Python. */
(() => {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const fonteDados = document.getElementById('chartbook-dados');
  if (!fonteDados) return;
  const D = JSON.parse(fonteDados.textContent);
  const C = D.cores || {};
  const TINTA = '#000000';
  const GRADE = C.grade || '#D9D9D9';
  const EIXO = C.verde_esc || '#172119';
  const PAINEL = C.painel || '#F4F2EC';
  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];

  // ── números e datas (pt-BR) ──
  const finito = v => typeof v === 'number' && isFinite(v);
  function num(v, d = 2) {
    if (!finito(v)) return '–';
    const s = Math.abs(v).toFixed(d);
    const neg = v < 0 && Number(s) !== 0;
    const [i, f] = s.split('.');
    return (neg ? '−' : '') + i.replace(/\B(?=(\d{3})+(?!\d))/g, '.') + (f ? ',' + f : '');
  }
  const numCsv = v => finito(v) ? String(Number(v.toFixed(4))).replace('.', ',') : '';
  const mesIdx = ym => Number(ym.slice(0, 4)) * 12 + Number(ym.slice(5, 7)) - 1;
  const idxMes = k => Math.floor(k / 12) + '-' + String(k % 12 + 1).padStart(2, '0');
  const mesCurto = k => MESES[k % 12] + '/' + String(Math.floor(k / 12)).slice(2);
  const slug = s => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
    .replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');

  const svgEl = (nome, attrs = {}, texto) => {
    const n = document.createElementNS(NS, nome);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (texto !== undefined) n.textContent = texto;
    return n;
  };
  const htmlEl = (nome, attrs = {}, texto) => {
    const n = document.createElement(nome);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (texto !== undefined) n.textContent = texto;
    return n;
  };

  // largura de texto (margens dos eixos e rótulos)
  const ctx = document.createElement('canvas').getContext('2d');
  const familia = getComputedStyle(document.body).fontFamily || 'serif';
  function largura(t, px = 12, peso = '') {
    if (!ctx) return String(t).length * px * .56;
    ctx.font = `${peso} ${px}px ${familia}`;
    return ctx.measureText(String(t)).width;
  }

  // cor clara demais para o painel creme ganha um contorno discreto
  function luminancia(hex) {
    const h = hex.replace('#', '');
    const c = [0, 2, 4].map(i => parseInt(h.slice(i, i + 2), 16) / 255).map(x => x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4);
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2];
  }
  const LUM_PAINEL = luminancia(PAINEL);
  const contorno = cor => {
    if (!/^#[0-9a-f]{6}$/i.test(cor)) return null;
    const l = luminancia(cor), r = (Math.max(l, LUM_PAINEL) + .05) / (Math.min(l, LUM_PAINEL) + .05);
    return r < 1.35 ? 'rgba(0,0,0,.28)' : null;
  };

  // escala "redonda" mais justa: passos 1/2/2,5/5 x 10^k (como no notebook)
  function escala(vmin, vmax, zero = true, folga = .01, nMin = 4, nMax = 8) {
    if (!finito(vmin) || !finito(vmax)) { vmin = 0; vmax = 1; }
    let lo = vmin, hi = vmax;
    if (zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
    if (hi - lo < 1e-9) { lo -= .5; hi += .5; }
    const e0 = Math.floor(Math.log10(hi - lo));
    const busca = (a0, a1) => {
      let melhor = null;
      for (let e = e0 - 2; e < e0 + 2; e++) for (const m of [1, 2, 2.5, 5]) {
        const st = Number((m * 10 ** e).toPrecision(12));
        const a = Math.floor(lo / st + 1e-9) * st, b = Math.ceil(hi / st - 1e-9) * st, n = Math.round((b - a) / st);
        if (n < a0 || n > a1) continue;
        const ch = [Number((b - a).toFixed(10)), n];
        if (!melhor || ch[0] < melhor[0][0] || (ch[0] === melhor[0][0] && ch[1] < melhor[0][1])) melhor = [ch, a, b, st];
      }
      return melhor;
    };
    let a, b, st;
    const m = busca(nMin, nMax) || busca(2, 12);
    if (m) [, a, b, st] = m;
    else {
      const raw = (hi - lo) / 5, mag = 10 ** Math.floor(Math.log10(raw));
      st = [1, 2, 2.5, 5, 10].map(k => k * mag).find(k => k >= raw);
      a = Math.floor(lo / st) * st; b = Math.ceil(hi / st) * st;
    }
    const tol = folga * (b - a);
    if (b - vmax < tol && !(zero && vmax <= 0)) b += st;
    if (vmin - a < tol && !(zero && vmin >= 0)) a -= st;
    return [Number(a.toFixed(10)), Number(b.toFixed(10)), st];
  }
  const casasPasso = st => { for (let k = 0; k < 4; k++) if (Math.abs(Number(st.toFixed(k)) - st) < 1e-9) return k; return 2; };
  const marcas = (lo, hi, st) => { const t = []; for (let i = 0, v = lo; v <= hi + st * 1e-6; i++, v = lo + i * st) t.push(Number(v.toFixed(10))); return t; };

  // ── estado (escopos): botões e listas mudam o estado; gráficos e painéis do escopo se redesenham ──
  const ESC = D.escopos || {};
  const estados = {}, ouvintes = {};
  for (const [k, e] of Object.entries(ESC)) { estados[k] = Object.assign({}, e.estado || {}); ouvintes[k] = []; }

  function substituir(o, e) {
    if (typeof o === 'string') return o.replace(/\{(\w+)\}/g, (m, k) => (k in e ? e[k] : m));
    if (Array.isArray(o)) return o.map(x => substituir(x, e));
    if (o && typeof o === 'object') { const r = {}; for (const [k, v] of Object.entries(o)) r[k] = substituir(v, e); return r; }
    return o;
  }
  function resolver(base, e) {
    let s = Object.assign({}, base);
    for (const v of base.variantes || []) if (String(e[v.chave]) === String(v.valor)) s = Object.assign(s, v.spec);
    delete s.variantes;
    return substituir(s, e);
  }

  function atualizarEscopo(k) {
    const e = ESC[k], est = estados[k];
    for (const caixa of document.querySelectorAll(`[data-controles="${k}"]`)) {
      caixa.querySelectorAll('button[data-chave]').forEach(b => b.setAttribute('aria-pressed', String(String(est[b.dataset.chave]) === b.dataset.valor)));
      caixa.querySelectorAll('select[data-chave]').forEach(s => { s.value = est[s.dataset.chave]; });
      const nota = caixa.querySelector('.nota-escopo');
      if (nota && e.nota) nota.textContent = (e.nota.textos || {})[est[e.nota.por]] || '';
    }
    if (e.paineis) for (const p of document.querySelectorAll(`[data-paineis="${k}"] > [data-valor]`)) {
      p.hidden = p.dataset.valor !== String(est[e.paineis]);
      // tabelas largas no celular: começa mostrando os meses mais recentes
      if (!p.hidden) p.querySelectorAll('.tabela-rolagem').forEach(r => { r.scrollLeft = r.scrollWidth; });
    }
  }
  function mudar(k, chave, valor) {
    if (String(estados[k][chave]) === String(valor)) return;
    estados[k][chave] = valor;
    atualizarEscopo(k);
    for (const f of ouvintes[k]) f(true);
  }
  function montarControles(k) {
    const e = ESC[k];
    for (const caixa of document.querySelectorAll(`[data-controles="${k}"]`)) {
      for (const c of e.controles || []) {
        if (c.tipo === 'lista') {
          const id = `lista-${k}-${c.chave}`;
          const w = htmlEl('div', {class: 'controle-lista'});
          const sel = htmlEl('select', {id, 'data-chave': c.chave});
          for (const [valor, rotulo] of c.opcoes) sel.append(htmlEl('option', {value: valor}, rotulo));
          sel.addEventListener('change', () => mudar(k, c.chave, sel.value));
          w.append(htmlEl('label', {for: id}, c.rotulo), sel);
          caixa.append(w);
        } else {
          const g = htmlEl('div', {class: 'chart-period', role: 'group', 'aria-label': c.rotulo || c.chave});
          for (const [valor, rotulo] of c.opcoes) {
            const b = htmlEl('button', {type: 'button', 'data-chave': c.chave, 'data-valor': String(valor)}, rotulo);
            b.addEventListener('click', () => mudar(k, c.chave, valor));
            g.append(b);
          }
          caixa.append(g);
        }
      }
      if (e.nota) caixa.append(htmlEl('p', {class: 'nota-escopo', 'aria-live': 'polite'}));
    }
    atualizarEscopo(k);
  }

  // ── CSV ──
  function csvTexto(linhas) {
    const cel = x => { const s = String(x ?? ''); return /[;"\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
    return '﻿' + linhas.map(l => l.map(cel).join(';')).join('\r\n') + '\r\n';
  }
  function baixar(nome, linhas) {
    const blob = new Blob([csvTexto(linhas)], {type: 'text/csv;charset=utf-8'});
    const a = htmlEl('a', {href: URL.createObjectURL(blob), download: nome});
    a.hidden = true; document.body.append(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 2000);
  }
  const csvGraficos = {};

  // ── gráficos ──
  function montarGrafico(host) {
    const id = host.dataset.grafico, base = (D.graficos || {})[id];
    if (!base) return;
    const escopos = (base.escopos || [id]).filter(k => estados[k]);
    const estado = () => Object.assign({}, ...escopos.map(k => estados[k]));
    const oculto = new Set();
    const fig = host.closest('figure');
    const legenda = htmlEl('div', {class: 'chart-legend'});
    const canvas = htmlEl('div', {class: 'chart-canvas'});
    const vazio = htmlEl('p', {class: 'grafico-vazio'}); vazio.hidden = true;
    const dica = htmlEl('div', {class: 'chart-tooltip', role: 'status', 'aria-live': 'polite'}); dica.hidden = true;
    const ajuda = htmlEl('p', {class: 'sr-only', id: 'ajuda-' + id});
    canvas.append(dica);
    host.append(legenda, canvas, vazio, ajuda);
    host.classList.add('interativo');

    let spec, svg, sobre, W = 0, H = 0, area, ativo = null, n = 0, meses = [], series = [], dados = [], X, Y, banda;

    function legendaMontar(itens) {
      legenda.replaceChildren();
      if (itens.length < 2 || spec.legenda === false) return;
      for (const s of itens) {
        const b = htmlEl('button', {type: 'button', class: 'legend-item', 'aria-pressed': String(!oculto.has(s.nome))});
        const linha = s.tipo === 'linha';
        const sw = svgEl('svg', {width: linha ? 20 : 11, height: 11, 'aria-hidden': 'true'});
        if (linha) sw.append(svgEl('line', {x1: 0, x2: 20, y1: 5.5, y2: 5.5, stroke: s.cor, 'stroke-width': Math.min(3, s.largura || 1.8), 'stroke-dasharray': s.tracejado || ''}));
        else sw.append(svgEl('rect', {x: .5, y: .5, width: 10, height: 10, fill: s.cor, stroke: contorno(s.cor) || 'none'}));
        b.append(sw, document.createTextNode(s.nome));
        b.addEventListener('click', () => {
          if (oculto.has(s.nome)) oculto.delete(s.nome); else oculto.add(s.nome);
          b.setAttribute('aria-pressed', String(!oculto.has(s.nome)));
          desenhar(false);
        });
        legenda.append(b);
      }
    }

    function cabecalho() {
      if (!fig) return;
      const t = fig.querySelector('.fig-titulo-texto'), s = fig.querySelector('.fig-sub');
      if (t && spec.titulo) t.textContent = spec.titulo;
      if (s && spec.subtitulo !== undefined) { s.textContent = spec.subtitulo; s.hidden = !spec.subtitulo; }
    }

    function desenhar(mudouEstado) {
      spec = resolver(base, estado());
      cabecalho();
      if (mudouEstado) ativo = null;
      dica.hidden = true;
      if (svg) { svg.remove(); svg = null; }
      if (spec.vazio) {
        legenda.replaceChildren(); canvas.hidden = true; vazio.textContent = spec.vazio; vazio.hidden = false;
        return;
      }
      canvas.hidden = false; vazio.hidden = true;
      W = Math.max(260, Math.round(canvas.getBoundingClientRect().width || host.clientWidth || 600));
      ajuda.textContent = spec.tipo === 'barras_h' ? 'Use as setas para cima e para baixo para ler os valores.' : 'Use as setas para a esquerda e para a direita para ler os valores de cada mês.';
      if (spec.tipo === 'barras_h') desenharH(); else desenharTempo();
    }

    function novoSvg() {
      svg = svgEl('svg', {viewBox: `0 0 ${W} ${H}`, width: '100%', height: H, tabindex: '0', role: 'img',
        'aria-label': (fig && fig.querySelector('.fig-titulo') ? fig.querySelector('.fig-titulo').textContent : spec.titulo || ''), 'aria-describedby': ajuda.id});
      canvas.insertBefore(svg, dica);
      return svg;
    }
    const rotulo = (pai, x, y, texto, ancora = 'middle', classe = 'axis-label') => pai.append(svgEl('text', {x, y, 'text-anchor': ancora, class: classe}, texto));

    // séries por mês: barras, barras empilhadas e linhas no mesmo eixo
    function desenharTempo() {
      const estreito = W < 520, fs = estreito ? 11 : 12;
      H = spec.altura || (estreito ? 250 : 300);
      series = spec.series.map(s => {
        const t = D.tabelas[s.tabela], col = t && t.series[s.col];
        return Object.assign({}, s, {t, col, off: t ? mesIdx(t.inicio) : 0});
      });
      const comDados = series.filter(s => s.col);
      if (!comDados.length) { legenda.replaceChildren(); canvas.hidden = true; vazio.textContent = 'Sem dados para esta série.'; vazio.hidden = false; return; }
      const valor = (s, k) => { if (!s.col) return null; const j = k - s.off; return j >= 0 && j < s.t.n ? s.col[j] : null; };
      const ini = Math.max(spec.inicio ? mesIdx(spec.inicio) : -Infinity, Math.min(...comDados.map(s => s.off)));
      const fim = Math.max(...comDados.map(s => s.off + s.t.n - 1));
      let primeiro = ini;
      while (primeiro <= fim && series.every(s => !finito(valor(s, primeiro)))) primeiro++;
      const k0 = Math.max(ini, primeiro - (primeiro % 12));
      n = Math.max(1, fim - k0 + 1);
      meses = Array.from({length: n}, (_, j) => k0 + j);
      dados = series.map(s => meses.map(k => valor(s, k)));
      if (ativo === null || ativo >= n) ativo = n - 1;
      legendaMontar(series);
      const vis = series.map(s => !oculto.has(s.nome));

      // extremos com o que está visível
      let lo = Infinity, hi = -Infinity;
      const temPilha = series.some((s, i) => vis[i] && s.tipo === 'empilhada');
      for (let j = 0; j < n; j++) {
        let pos = 0, neg = 0;
        series.forEach((s, i) => {
          const v = dados[i][j];
          if (!vis[i] || !finito(v)) return;
          if (s.tipo === 'empilhada') { if (v >= 0) pos += v; else neg += v; }
          else { lo = Math.min(lo, v); hi = Math.max(hi, v); }
        });
        if (temPilha) { lo = Math.min(lo, neg); hi = Math.max(hi, pos); }
      }
      if (!finito(lo)) { lo = 0; hi = 1; }
      const [a, b, st] = escala(lo, hi, spec.zero !== false);
      const dec = casasPasso(st), ticks = marcas(a, b, st);
      const padL = Math.ceil(Math.max(...ticks.map(t => largura(num(t, dec), fs)))) + 9;
      area = {l: padL, r: W - (estreito ? 4 : 8), t: 8, b: H - 28};
      banda = (area.r - area.l) / n;
      X = j => area.l + (j + .5) * banda;
      Y = v => area.b - (v - a) / (b - a) * (area.b - area.t);

      novoSvg();
      const grade = svgEl('g'), plot = svgEl('g'), eixos = svgEl('g', {stroke: EIXO, 'stroke-width': .8, fill: 'none'});
      svg.append(grade, plot, eixos);
      for (const t of ticks) {
        if (t !== a) grade.append(svgEl('line', {x1: area.l, x2: area.r, y1: Y(t), y2: Y(t), stroke: GRADE, 'stroke-width': .7}));
        rotulo(svg, area.l - 6, Y(t) + 4, num(t, dec), 'end');
      }

      // eixo do tempo: rótulos por ano (ou por mês em janelas curtas)
      const larMes = largura('set/26', fs) + 12, larAno = largura('2026', fs) + 12;
      const passoMes = n <= 36 ? [1, 3, 6].find(p => p * banda >= larMes) : undefined;
      if (passoMes) {
        meses.forEach((k, j) => {
          if (k % passoMes) return;
          eixos.append(svgEl('line', {x1: X(j), x2: X(j), y1: area.b, y2: area.b + 4}));
          rotulo(svg, X(j), area.b + 17, mesCurto(k));
        });
      } else {
        const passoAno = [1, 2, 3, 4, 5, 10].find(p => p * 12 * banda >= larAno) || 10;
        meses.forEach((k, j) => {
          if (k % 12) return;
          const ano = Math.floor(k / 12), x = area.l + j * banda, com = ano % passoAno === 0;
          eixos.append(svgEl('line', {x1: x, x2: x, y1: area.b, y2: area.b + (com ? 4 : 2)}));
          if (com) rotulo(svg, x, area.b + 17, String(ano));
        });
      }

      // barras (empilhadas ou lado a lado)
      const lb = Math.max(.8, banda * (spec.largura_barra || .72));
      const base0 = Math.min(Math.max(0, a), b);
      const barras = series.map((s, i) => i).filter(i => vis[i] && series[i].tipo === 'barra');
      const pilha = series.map((s, i) => i).filter(i => vis[i] && series[i].tipo === 'empilhada');
      for (let j = 0; j < n; j++) {
        let pos = 0, neg = 0;
        for (const i of pilha) {
          const v = dados[i][j];
          if (!finito(v) || v === 0) continue;
          const de = v > 0 ? pos : neg, ate = de + v;
          if (v > 0) pos = ate; else neg = ate;
          const y1 = Y(Math.max(de, ate)), y2 = Y(Math.min(de, ate));
          const ct = contorno(series[i].cor);
          plot.append(svgEl('rect', Object.assign({x: X(j) - lb / 2, y: y1, width: lb, height: Math.max(.5, y2 - y1), fill: series[i].cor},
            ct ? {stroke: ct, 'stroke-width': .5} : {})));
        }
      }
      barras.forEach((i, q) => {
        const s = series[i], w = lb / barras.length;
        let ult = -1;
        if (s.ultima) for (let j = n - 1; j >= 0; j--) if (finito(dados[i][j])) { ult = j; break; }
        for (let j = 0; j < n; j++) {
          const v = dados[i][j];
          if (!finito(v)) continue;
          const y1 = Y(Math.max(v, base0)), y2 = Y(Math.min(v, base0));
          plot.append(svgEl('rect', {x: X(j) - lb / 2 + q * w, y: y1, width: w, height: Math.max(.5, y2 - y1), fill: j === ult ? s.ultima : s.cor}));
        }
      });
      if (a < 0 && b > 0) eixos.append(svgEl('line', {x1: area.l, x2: area.r, y1: Y(0), y2: Y(0), 'stroke-opacity': .7}));
      // linhas (com quebras onde falta valor)
      series.forEach((s, i) => {
        if (!vis[i] || s.tipo !== 'linha') return;
        let d = '', aberto = false;
        for (let j = 0; j < n; j++) {
          const v = dados[i][j];
          if (!finito(v)) { aberto = false; continue; }
          d += (aberto ? 'L' : 'M') + X(j).toFixed(2) + ',' + Y(v).toFixed(2);
          aberto = true;
        }
        if (d) plot.append(svgEl('path', {d, fill: 'none', stroke: s.cor, 'stroke-width': s.largura || 1.8, 'stroke-dasharray': s.tracejado || '', 'stroke-linejoin': 'round', 'stroke-linecap': 'round'}));
      });
      eixos.append(svgEl('line', {x1: area.l, x2: area.r, y1: area.b, y2: area.b}));
      ligarInteracao(true);
    }

    // barras horizontais (categorias de cima para baixo)
    function desenharH() {
      const fs = W < 520 ? 11 : 12;
      const itens = spec.itens;
      n = itens.length;
      if (ativo === null || ativo >= n) ativo = 0;
      legendaMontar([]);
      const casas = spec.casas ?? 2;
      const vals = itens.map(i => i.valor).filter(finito);
      // os rótulos de valor ficam fora da escala (margens próprias), então a folga é pequena
      const [a, b, st] = escala(Math.min(0, ...vals), Math.max(0, ...vals), true, .02, 3, 6);
      const dec = casasPasso(st), ticks = marcas(a, b, st);
      const larNomes = Math.ceil(Math.max(...itens.map(i => largura(i.rotulo, fs, i.destaque ? 'bold' : '')))) + 10;
      const estreito = larNomes > W * .4;   // nomes acima das barras quando não cabem ao lado
      const larVal = Math.ceil(Math.max(...itens.map(i => largura(num(i.valor, casas), fs, 'bold')))) + 8;
      const negativos = vals.some(v => v < 0);
      const linhaH = estreito ? 38 : 26;
      H = n * linhaH + 36;
      area = {l: (estreito ? 2 : larNomes) + (negativos ? larVal : 2), r: W - larVal, t: 6, b: H - 30};
      X = v => area.l + (v - a) / (b - a) * (area.r - area.l);
      Y = i => area.t + i * linhaH;
      novoSvg();
      const grade = svgEl('g'), plot = svgEl('g'), eixos = svgEl('g', {stroke: EIXO, 'stroke-width': .8, fill: 'none'});
      svg.append(grade, plot, eixos);
      for (const t of ticks) {
        grade.append(svgEl('line', {x1: X(t), x2: X(t), y1: area.t, y2: area.b, stroke: GRADE, 'stroke-width': .7}));
        eixos.append(svgEl('line', {x1: X(t), x2: X(t), y1: area.b, y2: area.b + 4}));
        rotulo(svg, X(t), area.b + 17, num(t, dec));
      }
      const alt = 14, z = X(0);
      itens.forEach((it, i) => {
        const topo = Y(i), yc = estreito ? topo + 26 : topo + linhaH / 2;
        if (estreito) rotulo(plot, area.l + 1, topo + 13, it.rotulo, 'start', 'axis-label' + (it.destaque ? ' forte' : ''));
        else rotulo(plot, area.l - 8, yc + 4, it.rotulo, 'end', 'axis-label' + (it.destaque ? ' forte' : ''));
        if (!finito(it.valor)) return;
        const x1 = Math.min(z, X(it.valor)), w = Math.max(.8, Math.abs(X(it.valor) - z));
        const ct = contorno(it.cor);
        plot.append(svgEl('rect', Object.assign({x: x1, y: yc - alt / 2, width: w, height: alt, fill: it.cor}, ct ? {stroke: ct, 'stroke-width': .5} : {})));
        const dir = it.valor >= 0;
        rotulo(plot, dir ? X(it.valor) + 5 : X(it.valor) - 5, yc + 4, num(it.valor, casas), dir ? 'start' : 'end', 'bar-label' + (it.destaque ? ' forte' : ''));
      });
      eixos.append(svgEl('line', {x1: z, x2: z, y1: area.t, y2: area.b, 'stroke-opacity': .8}));
      eixos.append(svgEl('line', {x1: area.l, x2: area.r, y1: area.b, y2: area.b}));
      ligarInteracao(false);
    }

    // dicas, ponteiro e teclado
    function ligarInteracao(tempo) {
      sobre = svgEl('g', {'pointer-events': 'none'});
      svg.append(sobre);
      const escolher = ev => {
        const box = svg.getBoundingClientRect();
        const px = (ev.clientX - box.left) * W / box.width, py = (ev.clientY - box.top) * H / box.height;
        if (tempo) ativo = Math.min(n - 1, Math.max(0, Math.floor((px - area.l) / banda)));
        else ativo = Math.min(n - 1, Math.max(0, Math.floor((py - area.t) / ((area.b - area.t) / n))));
        mostrar();
      };
      svg.addEventListener('pointermove', escolher);
      svg.addEventListener('pointerdown', escolher);
      svg.addEventListener('pointerleave', esconder);
      svg.addEventListener('blur', esconder);
      svg.addEventListener('focus', mostrar);
      svg.addEventListener('keydown', ev => {
        const ant = tempo ? 'ArrowLeft' : 'ArrowUp', prox = tempo ? 'ArrowRight' : 'ArrowDown';
        let k = null;
        if (ev.key === ant) k = ativo - 1; else if (ev.key === prox) k = ativo + 1;
        else if (ev.key === 'Home') k = 0; else if (ev.key === 'End') k = n - 1;
        else if (ev.key === 'Escape') { esconder(); return; }
        if (k === null) return;
        ev.preventDefault(); ativo = Math.min(n - 1, Math.max(0, k)); mostrar();
      });
    }
    function esconder() { dica.hidden = true; if (sobre) sobre.replaceChildren(); }
    function linhaDica(cor, linha, texto, valor) {
      const d = htmlEl('div', {class: 'dica-linha'});
      const i = htmlEl('i', {class: linha ? 'linha' : ''}); i.style.background = cor;
      d.append(i, htmlEl('span', {}, texto), htmlEl('b', {}, valor));
      dica.append(d);
    }
    function mostrar() {
      if (!svg || ativo === null) return;
      sobre.replaceChildren(); dica.replaceChildren();
      let x, y;
      if (spec.tipo === 'barras_h') {
        const it = spec.itens[ativo];
        dica.append(htmlEl('strong', {}, it.rotulo));
        linhaDica(it.cor, false, it.texto || 'Valor', finito(it.valor) ? num(it.valor, spec.casas ?? 2) + (it.unidade || '') : '–');
        const topo = Y(ativo), h = (area.b - area.t) / n;
        sobre.append(svgEl('rect', {x: 0, y: topo, width: W, height: h, fill: TINTA, 'fill-opacity': .05}));
        x = finito(it.valor) ? X(it.valor) : X(0); y = topo + h;
      } else {
        const j = ativo, vis = series.map(s => !oculto.has(s.nome));
        dica.append(htmlEl('strong', {}, mesCurto(meses[j])));
        const ordem = series.map((s, i) => i);
        if (spec.dica_primeiro) { const p = ordem.findIndex(i => series[i].nome === spec.dica_primeiro); if (p > 0) ordem.unshift(...ordem.splice(p, 1)); }
        const casas = spec.casas ?? 2;
        for (const i of ordem) {
          if (!vis[i]) continue;
          const s = series[i], v = dados[i][j];
          linhaDica(s.tipo === 'barra' && s.ultima && j === lastValid(i) ? s.ultima : s.cor, s.tipo === 'linha', s.nome, finito(v) ? num(v, s.casas ?? casas) + (s.unidade || '') : '–');
        }
        x = X(j); y = area.t + 4;
        if (banda >= 4) sobre.append(svgEl('rect', {x: x - banda / 2, y: area.t, width: banda, height: area.b - area.t, fill: TINTA, 'fill-opacity': .06}));
        sobre.append(svgEl('line', {x1: x, x2: x, y1: area.t, y2: area.b, stroke: TINTA, 'stroke-opacity': .45, 'stroke-width': .8, 'stroke-dasharray': '2 3'}));
        series.forEach((s, i) => {
          if (vis[i] && s.tipo === 'linha' && finito(dados[i][j])) sobre.append(svgEl('circle', {cx: x, cy: Y(dados[i][j]), r: 3.2, fill: s.cor, stroke: '#fff', 'stroke-width': 1}));
        });
      }
      dica.hidden = false; dica.style.left = '0px'; dica.style.top = '0px';
      const escalaPx = canvas.clientWidth / W, tw = dica.offsetWidth, th = dica.offsetHeight;
      const esquerda = x > W * .55 ? x * escalaPx - tw - 14 : x * escalaPx + 14;
      dica.style.left = Math.max(0, Math.min(canvas.clientWidth - tw, esquerda)) + 'px';
      dica.style.top = Math.max(0, Math.min(Math.max(0, H * escalaPx - th), y * escalaPx)) + 'px';
    }
    function lastValid(i) { for (let j = n - 1; j >= 0; j--) if (finito(dados[i][j])) return j; return -1; }

    // CSV do que o gráfico mostra (todas as séries da visão atual, no período escolhido)
    csvGraficos[id] = () => {
      if (!spec || spec.vazio) return;
      const nome = slug(spec.csv || id) + '.csv';
      if (spec.tipo === 'barras_h') {
        baixar(nome, [[spec.csv_rotulo || 'série', spec.csv_valor || 'valor'], ...spec.itens.map(i => [i.rotulo, numCsv(i.valor)])]);
      } else {
        const cab = ['data', ...series.map(s => s.nome)];
        baixar(nome, [cab, ...meses.map((k, j) => [idxMes(k), ...series.map((s, i) => numCsv(dados[i][j]))])]);
      }
    };

    for (const k of escopos) ouvintes[k].push(desenhar);
    let ultimaLargura = 0;
    new ResizeObserver(() => {
      const w = Math.round(canvas.getBoundingClientRect().width);
      if (w && w !== ultimaLargura) { ultimaLargura = w; desenhar(false); }
    }).observe(canvas);
    desenhar(false);
  }

  // CSV de tabelas já escritas no HTML (a visível, quando há várias)
  function csvTabela(sel) {
    const caixa = document.querySelector(sel);
    if (!caixa) return;
    const t = [...caixa.querySelectorAll('table')].find(x => !x.closest('[hidden]'));
    if (!t) return;
    const limpa = s => s.textContent.replace(/−/g, '-').replace(/\s+/g, ' ').trim();
    const linhas = [...t.querySelectorAll('tr')].map(tr => [...tr.children].map(limpa));
    baixar((t.dataset.csv || 'tabela') + '.csv', linhas);
  }

  // índice: marca a seção que está na tela
  function marcarIndice() {
    const links = [...document.querySelectorAll('.indice a[href^="#"]')];
    if (!links.length || !('IntersectionObserver' in window)) return;
    const alvo = new Map(links.map(a => [a.getAttribute('href').slice(1), a]));
    const io = new IntersectionObserver(entradas => {
      for (const e of entradas) if (e.isIntersecting) {
        links.forEach(a => a.removeAttribute('aria-current'));
        const a = alvo.get(e.target.id); if (a) a.setAttribute('aria-current', 'true');
      }
    }, {rootMargin: '-45% 0px -50% 0px'});
    for (const id of alvo.keys()) { const s = document.getElementById(id); if (s) io.observe(s); }
  }

  for (const k of Object.keys(ESC)) montarControles(k);
  for (const host of document.querySelectorAll('[data-grafico]')) montarGrafico(host);
  document.addEventListener('click', ev => {
    const b = ev.target.closest('button.baixar');
    if (!b) return;
    if (b.dataset.csvGrafico && csvGraficos[b.dataset.csvGrafico]) csvGraficos[b.dataset.csvGrafico]();
    else if (b.dataset.csvTabela) csvTabela(b.dataset.csvTabela);
  });
  marcarIndice();
})();
