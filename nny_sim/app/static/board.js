/* 무대: 매트 보드 + 플레이어 막대 · 턴 · 체인 · 캡션 · 카드 상세 · 기록. 재생(replay)과 실시간 대전(live) 공용.
   기록 형식은 viewer/record.py (frames · states · cards). 매트 칸 좌표는 업로드 매트 이미지에서 잰 값(viewer/template.html 과 같음). */
(function () {
'use strict';
const SLOT = {x0: 160, dx: 224, y0: 318, dy: 304, w: 200, h: 280};
const HAND_Y = [1750, 100], HAND_X = [96, 1568];
const CH = 262, HAND_SCALE = 0.68;
const PHASES = ['준비', '진행', '전투', '정비', '종료'];
// 1× 재생의 기록 줄 사이 시간(ms) · 카드 이동 연출 시간 — 사람이 따라가기 쉽게 예전(발동 1000 · 이동 380)의 약 1.6배 (사용자 지시 2026-10-29)
const BASE_DELAY = {act: 1600, res: 1450, draw: 850, sys: 1100, turn: 1700, round: 3000, end: 3200, side: 2400, decision: 650, sync: 200};   // sync: 줄 없이 지금 필드만 보여 주는 프레임(Recorder.sync)
const SIDE_SWAP_DELAY = 600, SIDE_SWAP_DELAY_MAX = 6;   // 전략 덱 교체 화면: 교체 1장마다 더 보여 주는 시간(ms) · 그 장수 상한
const SWAP_CARD = {max: 188, min: 92, row: 1500, gap: 18};   // 교체 화면 카드 폭(보드 px) — 한 줄(뺌 · 넣음)의 종류 수에 맞춰 줄인다
const MOVE_MS = 640, MOVE_MS_MAX = 1100;
const TOKEN = {x: 1504, y: 926, d: 188};   // 매트의 「주인 토큰」 원(오른쪽 가운데) 중심 · 지름 — 공유 존 마커를 놓는 곳
const TOKEN_DROP = 300;                    // 마커를 처음 놓을 때 주인 쪽에서 날아오는 거리
const ARROW = {start: 80, end: 120, head: 64, bend: 0.16, bendMax: 150, min: 60};   // 화살표: 카드 중심에서 띄우는 길이 · 머리 크기 · 휘는 정도
const SVGNS = 'http://www.w3.org/2000/svg';
const FIT_PUSHED = 0.4;   // 무대 윗변이 화면 높이의 이 비율보다 아래면 「밀린」 것으로 본다
const COLOR = {'적색': '#c9403f', '녹색': '#3f9a5a', '청색': '#2f72b8', '황색': '#c99a2e', '자색': '#8d52c9', '백색': '#a9b0bd', '흑색': '#555b66'};
const PC = ['var(--p1)', 'var(--p2)'];
const ICON = {act: '▶', res: '↳', draw: '✋', sys: '✦', turn: '━', round: '█', end: '■', side: '⇄', decision: '·'};
const SPEEDS = [0.25, 0.5, 1, 2, 4, 8];
const slot = (c, r) => ({x: SLOT.x0 + SLOT.dx * c, y: SLOT.y0 + SLOT.dy * r});
// 존 배치(사용자 지시 2026-10-30): 몬스터 존 3칸 = 예전 1 · 3 · 5번 자리(열 1 · 3 · 5), 공유 존 2칸 = 예전 스킬 존 자리(가운데 줄 열 2 · 4),
// 스킬 존 = P1 시점 1 · 5번 몬스터 존 위(가운데 줄 열 1 = P2 · 열 5 = P1), 필드 존 = 예전 공유 존 자리(가운데). 예전 기록(몬스터 존 5칸 · 공유 존 1칸)도 그린다.
const MCOL = {3: [1, 3, 5], 5: [1, 2, 3, 4, 5]};   // 기록의 몬스터 존 수 → P1 쪽 열(P2 는 좌우 반대)
const Z = [
  {m: (i, n = 3) => slot(MCOL[n][i], 3), s: i => slot(1 + i, 4), grave: slot(6, 3), ban: slot(0, 3), main: slot(6, 4), upper: slot(0, 4), sk: slot(5, 2)},
  {m: (i, n = 3) => slot(6 - MCOL[n][i], 1), s: i => slot(5 - i, 0), grave: slot(0, 1), ban: slot(6, 1), main: slot(0, 0), upper: slot(6, 0), sk: slot(1, 2)},
];
const SHARED = [slot(2, 2), slot(4, 2)], FIELDZ = slot(3, 2);
const shList = v => Array.isArray(v) ? v : [v ?? null, null];   // 상태의 공유 존(sh · so · sc): 칸 목록, 예전 기록은 칸 하나
const esc = s => String(s ?? '').replace(/[&<>"]/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[ch]));

function typeLine(p) {
  if (!p) return '';
  if (p.type === '몬스터') return [p.race, p.attr && p.attr + '속성', p.level != null && 'Lv ' + p.level].filter(Boolean).join(' · ');
  return [p.type === '마법' ? '마법카드' : p.type === '필드' ? '필드카드' : p.type === '스킬' ? '스킬카드' : p.type, p.subtype].filter(Boolean).join(' · ');
}
function effText(pool, num) {
  if (!pool || !pool.text) return '';
  if (num === 0) return '마법 · 필드 카드를 발동해 필드에 놓는다.';
  const out = []; let on = false;
  for (const ln of pool.text.split('\n')) { const m = ln.match(/^(\d+)\.\s/); if (m) on = (+m[1] === num); if (on) out.push(ln); }
  return out.join('\n');
}
function genCard(p) {
  const cc = COLOR[p.color] || '#59627a';
  const st = p.type === '몬스터' ? `<div class="gs">공 ${esc(p.atk ?? 0)} / 수 ${esc(p.def ?? 0)}</div>` : '';
  return `<div class="gen" style="--cc:${cc}"><div class="gn">${esc(p.name)}</div><div class="gt">${esc(typeLine(p))}</div>${st}<div class="gx">${esc(p.text || '')}</div></div>`;
}

class Stage {
  constructor(host, opts) {
    this.o = opts; this.A = opts.assets; this.POOL = opts.pool;
    this.ratio = this.A.ratio; this.CW = Math.round(CH * this.ratio); this.DEF_SCALE = SLOT.w / CH;
    this.MW = this.A.mat_size[0]; this.MH = this.A.mat_size[1];
    host.innerHTML = this.html(); this.host = host; this.root = host.firstElementChild;
    const q = s => host.querySelector(s); this.q = q;
    this.arrange();
    this.board = q('.board'); this.wrap = q('.board-wrap'); this.logEl = q('.log');
    this.board.style.width = this.MW + 'px'; this.board.style.height = this.MH + 'px';
    this.board.style.backgroundImage = `url(${this.url(this.A.mat)})`;
    document.documentElement.style.setProperty('--ratio', this.ratio);
    this.reset(); this.buildStatic(); this.bind(); this.setSpeed(this.speed);
    this.tfs = 26; this.board.style.setProperty('--tfs', this.tfs + 'px');
    this.ro = new ResizeObserver(() => this.fit()); this.ro.observe(this.root);
    addEventListener('resize', () => this.fit());
  }
  url(rel) { return this.o.url ? this.o.url(rel) : '/cards/' + rel; }   // 단일 HTML 재생 파일은 이미지가 data URI(그대로)
  face(name) { const f = this.A.faces[name]; return f ? this.url(f) : null; }
  html() {
    return `<div class="stage"><div class="col colL"></div><div class="col colC"></div><div class="col colR"></div></div>
      <div class="stage-parts" hidden>
      <div class="pbar pb1" style="--pc:var(--p2)"></div><div class="pbar pb0" style="--pc:var(--p1)"></div>
      <div class="bcol"><div class="board-wrap"><div class="board">
        <svg class="fxl" viewBox="0 0 ${this.MW || 1664} ${this.MH || 1904}"><g class="arrows"></g></svg>
        ${SHARED.map((S, k) => `<div class="shz" data-k="${k}" style="left:${S.x - SLOT.w / 2 - 12}px;top:${S.y - SLOT.h / 2 - 12}px;width:${SLOT.w + 24}px;height:${SLOT.h + 24}px"><span class="shb"></span></div>`).join('')}
        ${SHARED.map((S, k) => { const d = TOKEN.d * 0.5, x = TOKEN.x + (k ? 1 : -1) * TOKEN.d * 0.26; return `<div class="token mini" data-k="${k}" style="left:${x - d / 2}px;top:${TOKEN.y - d / 2}px;width:${d}px;height:${d}px">
          <div class="coin"><div class="cf w"><b>${k + 1}</b><small>선공</small></div><div class="cf k"><b>${k + 1}</b><small>후공</small></div></div><div class="tl"></div></div>`; }).join('')}
        <div class="overlay"><div class="box"></div></div></div></div></div>
      <div class="controls ctl">
        <button data-a="prevTurn" title="이전 턴 (Shift+←)">⏮</button><button data-a="prev" title="한 단계 뒤로 (←)">◀</button>
        <button data-a="play" class="primary" title="재생 / 정지 (Space)">▶ 재생</button><button data-a="next" title="한 단계 앞으로 (→)">▶|</button>
        <button data-a="nextTurn" title="다음 턴 (Shift+→)">⏭</button>
        <select data-a="speed" title="속도">${SPEEDS.map(v => `<option value="${v}"${v === 1 ? ' selected' : ''}>${v}×</option>`).join('')}</select>
        <div class="scrub"><input type="range" min="0" max="0" value="0" aria-label="재생 위치"><span class="pos"></span></div>
        <span class="rounds"></span><span class="extra"></span>
        <button data-a="reveal" class="on" title="패 · 뒷면 카드를 앞면으로 보기">패 공개</button>
        <button data-a="dec" title="AI 판단 줄 보기">AI 판단</button>
      </div>
      <div class="dec"></div><div class="caption cap"></div>
      <div class="panel turn"><h2 class="sec">턴 · 단계</h2><div class="turninfo"></div><div class="phase"></div></div>
      <div class="panel chainp"><h2 class="sec">체인 <span class="cnt"></span><small>1번부터 쌓인 순서 · 처리는 아래에서 위로</small></h2><div class="chain"></div></div>
      <div class="panel detail"><h2 class="sec">카드</h2><div class="dbody"><div class="hint">보드의 카드나 묘지 · 제외 존을 누르면 여기에 크게 보입니다.</div></div></div>
      <div class="panel logp"><h2 class="sec">기록</h2><div class="log nodec"></div>
        <div class="legend">▶ 발동 · ↳ 체인 처리 · ⚔ 공격 · ✦ 결과 · ✋ 드로우 &nbsp;|&nbsp; 화살표 <i class="la atk"></i>공격 <i class="la tgt"></i>효과의 대상 <i class="la pick"></i>효과로 고른 카드</div></div></div>`;
  }
  arrange() {   // 넓은 화면 3열 · 중간 2열 · 좁은 화면 1열
    const W = innerWidth, mode = W >= 1360 ? 'wide' : W >= 1000 ? 'mid' : 'narrow';
    if (mode === this.mode) return; this.mode = mode;
    const q = s => this.host.querySelector(s);
    const parts = {pb1: q('.pb1'), pb0: q('.pb0'), bcol: q('.bcol'), ctl: q('.ctl'), dec: q('.dec'), cap: q('.cap'), turn: q('.turn'), chain: q('.chainp'), detail: q('.detail'), log: q('.logp')};
    const L = {wide: [['pb1', 'turn', 'dec', 'cap', 'pb0'], ['bcol', 'ctl'], ['chain', 'detail', 'log']],   // 체인은 화면 오른쪽(사용자 지시 2026-10-29)
               mid: [[], ['pb1', 'bcol', 'pb0', 'ctl'], ['dec', 'chain', 'cap', 'turn', 'detail', 'log']],
               narrow: [[], ['pb1', 'bcol', 'pb0', 'ctl', 'dec', 'cap', 'turn', 'chain', 'detail', 'log'], []]}[mode];
    ['.colL', '.colC', '.colR'].forEach((sel, k) => { const col = this.root.querySelector(sel); L[k].forEach(n => col.appendChild(parts[n])); });
    this.root.classList.toggle('narrow', mode === 'narrow');
  }
  reset() {
    if (this.els) this.els.forEach(e => e.el.remove());
    this.F = []; this.S = []; this.cards = {}; this.pool = {}; this.names = ['P1', 'P2']; this.meta = {decks: ['', ''], rounds: []};
    this.els = new Map(); this.cur = 0; this.lastRendered = -1; this.selected = null; this.rows = []; this.curRow = null;
    this.playing = false; clearTimeout(this.timer); this.speed = this.speed || 1; this.tokOwner = [null, null]; this.reveal = [true, true]; this.showDec = false;
    this.live = false; this.mask = null; this.hl = new Set(); this.WINS = []; this.TURNS = [];
    if (this.logEl) this.logEl.innerHTML = '';
  }
  // ── 불러오기 ──
  load(rec) {
    this.reset();
    this.F = rec.frames; this.S = rec.states; this.cards = rec.cards; this.pool = rec.pool || {}; this.meta = rec.meta; this.names = rec.meta.names;
    this.afterData(true); this.go(0, false);
  }
  startLive(names, meta, mask) {
    this.reset(); this.live = true; this.names = names; this.meta = Object.assign({decks: ['', ''], rounds: []}, meta); this.mask = mask || null;
    if (mask) this.reveal = [true, false];
    this.q('[data-a=reveal]').classList.toggle('on', this.reveal[1]);
    this.afterData(true); this.renderEmpty();
  }
  appendLive(d) {   // 서버 poll 결과
    if (d.f_from !== this.F.length || d.s_from !== this.S.length) return false;
    Object.assign(this.cards, d.cards); this.S.push(...d.states);
    const start = this.F.length; this.F.push(...d.frames);
    if (d.result) this.meta = Object.assign(this.meta, d.result);
    this.afterData(false, start);
    if (this.live && !this.playing && this.follow !== false && this.F.length) this.play(true);
    return true;
  }
  endLive() {   // 대전이 끝나면 숨겼던 정보를 모두 공개(복기)
    this.mask = null; this.reveal = [true, true]; this.q('[data-a=reveal]').classList.add('on');
    this.rebuildLog(); this.render(this.cur, false);
  }
  afterData(full, start = 0) {
    if (full) { this.WINS = []; this.TURNS = []; }
    let w = this.WINS.length ? this.WINS[this.WINS.length - 1].slice() : [0, 0];
    for (let i = this.WINS.length; i < this.F.length; i++) {
      const fr = this.F[i];
      if (fr.k === 'end') {
        const rr = (this.meta.rounds || [])[fr.r - 1];
        const win = rr ? rr.winner : this.endWinner(fr);
        if (win != null) w = w.map((x, s) => x + (win === s ? 1 : 0));
      }
      this.WINS.push(w.slice());
      if (fr.k === 'turn' || fr.k === 'round') this.TURNS.push(i);
    }
    if (full) this.rebuildLog(); else this.appendLog(start);
    const sc = this.q('.scrub input'); sc.max = Math.max(0, this.F.length - 1);
    this.roundButtons();
  }
  endWinner(fr) {   // 실시간: 라운드 결과 줄의 「승자: 이름」
    const m = fr.m.match(/승자: (.+?) \(/); if (!m) return null;
    const i = this.names.indexOf(m[1]); return i >= 0 ? i : null;
  }
  // ── 정적 요소 ──
  buildStatic() {
    const b = this.board, CW = this.CW;
    this.piles = [[], []]; this.zc = [[], []];
    for (const seat of [0, 1]) {
      for (const k of ['main', 'upper']) {
        const p = Z[seat][k]; const d = document.createElement('div'); d.className = 'pile'; d.style.setProperty('--pc', PC[seat]);
        Object.assign(d.style, {width: CW + 'px', height: CH + 'px', left: (p.x - CW / 2) + 'px', top: (p.y - CH / 2) + 'px', zIndex: 2});
        d.innerHTML = `<div class="stack">${[3, 2, 1, 0].map(i => `<img src="${this.url(this.A.back)}" alt="" style="left:${i * 4}px;top:${-i * 4}px">`).join('')}</div><div class="num"></div>`;
        d.title = `${k === 'main' ? '메인' : '상급'} 덱`; b.appendChild(d);
        this.piles[seat].push({k, d, num: d.querySelector('.num'), imgs: d.querySelectorAll('img')});
      }
      for (const k of ['grave', 'ban']) {
        const p = Z[seat][k];
        const hit = document.createElement('div'); hit.className = 'zonehit'; hit.style.left = (p.x - SLOT.w / 2) + 'px'; hit.style.top = (p.y - SLOT.h / 2) + 'px';
        hit.addEventListener('click', ev => { ev.stopPropagation(); this.showPile(seat, k); }); b.appendChild(hit);
        const c = document.createElement('div'); c.className = 'zcount'; c.style.setProperty('--pc', PC[seat]);
        c.style.left = (p.x + CW / 2 - 46) + 'px'; c.style.top = (p.y + CH / 2 - 46) + 'px'; b.appendChild(c); this.zc[seat].push({k, c});
      }
    }
  }
  bind() {
    const q = this.q;
    this.host.querySelectorAll('.ctl [data-a]').forEach(el => {
      const a = el.dataset.a;
      if (a === 'speed') el.onchange = () => this.setSpeed(+el.value);
      else el.onclick = () => this.action(a);
    });
    q('.scrub input').oninput = e => { this.stop(); this.go(+e.target.value, false); };
    this.logEl.addEventListener('click', ev => { const r = ev.target.closest('.row'); if (r) { this.stop(); this.follow = false; this.go(+r.dataset.i, false); } });
    this.board.addEventListener('click', () => { this.selected = null; this.els.forEach(e => e.el.classList.remove('sel')); });
  }
  action(a) {
    if (a === 'play') return this.playing ? this.stop() : this.play();
    this.stop(); if (this.live) this.follow = false;
    if (a === 'next') this.step(1); else if (a === 'prev') this.step(-1);
    else if (a === 'nextTurn') this.jumpTurn(1); else if (a === 'prevTurn') this.jumpTurn(-1);
    else if (a === 'reveal') { const v = !this.reveal[1] || !this.reveal[0]; if (this.mask) return; this.reveal = [v, v]; this.q('[data-a=reveal]').classList.toggle('on', v); this.render(this.cur, true); }
    else if (a === 'dec') { this.showDec = !this.showDec; this.q('[data-a=dec]').classList.toggle('on', this.showDec); this.logEl.classList.toggle('nodec', !this.showDec); this.drawLogCursor(this.cur); }
  }
  key(e) {
    if (e.target.closest && e.target.closest('input,select,textarea')) return;
    if (e.code === 'Space') { e.preventDefault(); this.action('play'); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); this.action(e.shiftKey ? 'nextTurn' : 'next'); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); this.action(e.shiftKey ? 'prevTurn' : 'prev'); }
  }
  roundButtons() {
    const rb = this.q('.rounds'); const rs = [...new Set(this.F.map(f => f.r))].filter(r => r > 0);
    if (rb.childElementCount === rs.length) return;
    rb.innerHTML = '';
    rs.forEach(r => { const b = document.createElement('button'); b.textContent = r + 'R'; b.title = `${r}라운드로`;
      b.onclick = () => { this.stop(); this.follow = false; this.go(this.F.findIndex(f => f.r === r), false); }; rb.appendChild(b); });
  }
  // ── 카드 ──
  info(uid) { const c = this.cards[uid]; if (!c) return null; const p = this.POOL[c[0]] || this.pool[c[0]] || {name: c[0]}; return {name: c[0], owner: c[1], pool: p}; }
  makeEl(uid) {
    const ci = this.info(uid); const p = ci ? ci.pool : {name: '?'}; const CW = this.CW;
    const el = document.createElement('div'); el.className = 'card'; el.style.width = CW + 'px'; el.style.height = CH + 'px'; el.style.opacity = 0;
    const src = this.face(p.name);
    el.innerHTML = `<div class="rot" style="width:${CW}px;height:${CH}px"><div class="glow"></div><div class="flip"><div class="face front">${src ? `<img src="${src}" alt="${esc(p.name)}">` : genCard(p)}</div><div class="face back"><img src="${this.url(this.A.back)}" alt="뒷면"></div></div></div>`;
    el.addEventListener('click', ev => { ev.stopPropagation(); this.select(uid); });
    this.board.appendChild(el);
    const o = {el, rot: el.firstChild, flip: el.querySelector('.flip'), tags: [], target: null};
    this.els.set(uid, o); return o;
  }
  pileHome(uid) { const ci = this.info(uid); if (!ci) return FIELDZ; return Z[ci.owner][ci.pool.deck === '상급' ? 'upper' : 'main']; }
  handSpots(n, seat) {
    const w = this.CW * HAND_SCALE, span = HAND_X[1] - HAND_X[0] - w;
    const step = n > 1 ? Math.min(w + 10, span / (n - 1)) : 0, x0 = 832 - step * (n - 1) / 2;
    return Array.from({length: n}, (_, i) => ({x: x0 + step * i, y: HAND_Y[seat]}));
  }
  layout(st, fx) {
    const L = new Map();
    const cell = (c, pos, seat, extra) => {
      if (!c) return; const ci = this.info(c.u); const def = !!c.p;
      L.set(c.u, Object.assign({x: pos.x, y: pos.y, rot: def ? 90 : 0, scale: def ? this.DEF_SCALE : 1, up: c.f !== 0, z: 20, cell: c, seat, stolen: ci && ci.owner !== seat}, extra || {}));
    };
    st.P.forEach((P, seat) => {
      this.handSpots(P.hand.length, seat).forEach((pos, i) => L.set(P.hand[i], {x: pos.x, y: pos.y, rot: 0, scale: HAND_SCALE, up: this.reveal[seat], z: 400 + i, hand: true, seat}));
      P.m.forEach((c, i) => cell(c, Z[seat].m(i, P.m.length), seat)); P.s.forEach((c, i) => cell(c, Z[seat].s(i), seat));
      if (P.sk) cell(P.sk, Z[seat].sk, seat);
      for (const k of ['grave', 'ban']) {
        const list = P[k], pos = Z[seat][k];
        list.forEach((u, i) => L.set(u, {x: pos.x, y: pos.y, rot: 0, scale: 1, up: true, z: 5 + i, pile: true, top: i === list.length - 1, seat}));
      }
    });
    const sc = shList(st.sc); shList(st.sh).forEach((c, k) => { if (c) cell(c, SHARED[k], sc[k] ?? 0, {ctl: sc[k]}); });
    if (st.fz) cell(st.fz, FIELDZ, st.fc ?? 0, {ctl: st.fc});
    for (const f of fx) { const u = f.u ?? f.a; const o = L.get(u); if (o && o.pile) { o.top = true; o.z = 300; } }
    return L;
  }
  statTag(c, pool) {
    if (!c || c.a == null || c.f === 0) return '';
    const ba = +(pool.atk || 0), bd = +(pool.def || 0), cls = (v, b) => v > b ? 'up' : v < b ? 'dn' : '';
    return `<span class="${cls(c.a, ba)}">${c.a}</span> / <span class="${cls(c.d, bd)}">${c.d}</span>`;
  }
  stateAt(i) { for (let j = i; j >= 0; j--) if (this.F[j] && this.F[j].s >= 0) return this.S[this.F[j].s]; return null; }
  renderEmpty() {
    this.els.forEach(e => e.el.remove()); this.els.clear();
    this.drawBars(null, {k: 'round', r: 0}, null, 0); this.drawTurn(null, {r: 0}); this.drawChain(null, []);
    this.q('.cap').innerHTML = '<div class="main">대전 준비 중…</div>';
  }
  render(i, animate) {
    const fr = this.F[i]; if (!fr) return;
    const CW = this.CW, tfs = this.tfs;
    this.board.classList.toggle('instant', !animate);
    let si = fr.s, dim = false;
    if (si < 0 && fr.k !== 'round') { for (let j = i - 1; j >= 0 && this.F[j].r === fr.r; j--) if (this.F[j].s >= 0) { si = this.F[j].s; break; } dim = true; }
    const st = si >= 0 ? this.S[si] : null, fx = fr.fx || [];
    const L = st ? this.layout(st, fx) : new Map();
    this.board.classList.toggle('dimmed', dim);
    const fxMap = new Map();
    for (const f of fx) if (f.t !== 'pick') fxMap.set(f.t === 'atk' ? f.a : f.u, f.t === 'act' ? 'fx-act' : f.t === 'res' ? 'fx-res' : f.t === 'des' ? 'fx-des' : 'fx-atk');
    const chainNo = this.chainNumbers(st, fx);
    for (const [uid, o] of L) {
      let e = this.els.get(uid);
      if (!e) { e = this.makeEl(uid); const h = this.pileHome(uid); e.el.style.transform = `translate(${h.x - CW / 2}px,${h.y - CH / 2}px)`; e.rot.style.transform = 'scale(.6)'; e.flip.classList.add('down'); void e.el.offsetWidth; }
      e.el.style.opacity = (o.pile && !o.top) ? 0 : 1;
      e.el.style.transform = `translate(${o.x - CW / 2}px,${o.y - CH / 2}px)`; e.el.style.zIndex = o.z;
      e.rot.style.transform = `rotate(${o.rot}deg) scale(${o.scale})`;
      const own = o.seat == null || this.reveal[o.seat];
      const peek = !o.up && own && !o.hand;
      e.flip.classList.toggle('down', !(o.up || peek));
      e.el.classList.toggle('peek', peek); e.el.classList.toggle('inpile', !!o.pile);
      e.el.classList.remove('fx-act', 'fx-res', 'fx-des', 'fx-atk'); if (fxMap.has(uid)) e.el.classList.add(fxMap.get(uid));
      e.el.classList.toggle('neg', !!(o.cell && o.cell.n)); e.el.classList.toggle('sel', this.selected === uid);
      const ci = this.info(uid); e.el.classList.toggle('hl', !!(ci && this.hl.has(ci.name) && o.seat === 0 && (o.up || own)) || !!(this.hlu && this.hlu.has(String(uid))));
      const c = o.cell, tags = [];
      const hh = CH * o.scale * (o.rot ? CW / CH : 1) / 2;
      if (!o.hand && !o.pile && c) {
        const s = this.statTag(c, ci.pool); if (s) tags.push(['stats', s, hh - tfs * .6]);
        const ctlTag = o.ctl != null || o.stolen; let top = -hh + tfs * (ctlTag ? 2.1 : .5);
        if (c.c) { tags.push(['cnt', Object.entries(c.c).map(([k, v]) => `${esc(k)} ×${v}`).join(' · '), top]); top += tfs * 1.6; }
        if (c.n) tags.push(['neg', '무효', top]);
        if (c.f === 0 && own) tags.push(['down', '뒷면', 0]);
        if (ctlTag) tags.push(['ctl', o.ctl != null ? `P${o.seat + 1}` : `P${o.seat + 1} 컨트롤`, -hh + tfs * .5, PC[o.seat]]);
      }
      const cn = chainNo.get(uid);   // 체인에 올라 있는 카드: 카드 위에 체인 번호(오른쪽 체인 패널과 같은 번호)
      if (cn && !(o.pile && !o.top)) tags.push(['chn', cn.map(n => `체인 ${n}`).join(' · '), -hh - tfs * .45]);
      const key = JSON.stringify(tags) + tfs;
      if (e.tagKey !== key) {
        e.tags.forEach(t => t.remove()); e.tags = [];
        for (const [cls, h, dy, tc] of tags) { const t = document.createElement('div'); t.className = 'tag ' + cls; t.innerHTML = h; t.style.top = (CH / 2 + dy - tfs * .7) + 'px'; if (tc) t.style.setProperty('--tc', tc); e.el.appendChild(t); e.tags.push(t); }
        e.tagKey = key;
      }
      e.target = o;
    }
    for (const [uid, e] of this.els) {
      if (L.has(uid) || !e.target) continue;
      const h = this.pileHome(uid); e.el.style.transform = `translate(${h.x - CW / 2}px,${h.y - CH / 2}px)`; e.el.style.opacity = 0; e.el.style.zIndex = 1;
      e.rot.style.transform = 'scale(.8)'; e.target = null; e.el.classList.remove('fx-act', 'fx-res', 'fx-des', 'fx-atk');
    }
    for (const seat of [0, 1]) {
      for (const p of this.piles[seat]) { const n = st ? st.P[seat][p.k] : 0; p.d.classList.toggle('zero', !n); p.num.textContent = n; const layers = Math.min(4, 1 + Math.floor(n / 10)); p.imgs.forEach((im, j) => im.style.display = (3 - j) < layers ? '' : 'none'); }
      for (const z of this.zc[seat]) { const n = st ? st.P[seat][z.k].length : 0; z.c.classList.toggle('zero', !n); z.c.textContent = n; }
    }
    this.drawToken(st, fr, animate); this.drawArrows(fx, st, L, i);
    const ov = this.q('.overlay'), box = this.q('.overlay .box');
    if (fr.k === 'round' || fr.k === 'end' || (dim && (fr.k === 'side' || fr.k === 'decision'))) {
      ov.classList.add('on');
      box.innerHTML = fr.k === 'round' ? `${fr.r}라운드<small>${this.nameHtml(esc(fr.m.replace(/█/g, '').trim().replace(/^\d+라운드\s*—\s*/, '')))}</small>`
        : fr.k === 'end' ? `${fr.r}라운드 종료<small>${this.nameHtml(esc(fr.m.replace(/^■\s*/, '').replace(/^라운드 종료 — /, '')))}</small>`
        : fr.k === 'side' ? this.sideHtml(fr)
        : `${fr.r}라운드 → ${fr.r + 1}라운드 준비<small>${this.nameHtml(esc(this.shortMsg(fr)))}</small>`;
      box.classList.toggle('swapbox', fr.k === 'side' && !this.sideHidden(fr) && this.swapsOf(fr).length > 0);
    } else ov.classList.remove('on');
    const prevSt = animate && this.lastRendered >= 0 && this.lastRendered < i ? this.stateAt(this.lastRendered) : null;
    this.drawBars(st, fr, prevSt, i); this.drawTurn(st, fr); this.drawChain(st, fx); this.drawCaption(i); this.drawLogCursor(i);
    this.q('.scrub input').value = i; this.q('.pos').textContent = `${i + 1} / ${this.F.length}`;
    this.lastRendered = i;
    if (this.selected != null) this.showCard(this.selected);
  }
  // ── 공유 존 마커 · 화살표 ──
  firstOf(st, r) {   // 그 라운드의 선공 자리 — 새 기록은 상태에 fp, 예전 기록은 매치 정보의 라운드 선공
    if (st && st.fp != null) return st.fp;
    const rr = (this.meta.rounds || [])[r - 1]; return rr && rr.first != null ? rr.first : 0;
  }
  drawToken(st, fr, animate) {
    // 공유 존 마커(양면 — 그 라운드 선공 쪽이 백, 후공 쪽이 흑)를 칸마다(공유 존 1 · 2 — 사용자 지시 2026-10-30) 매트의 주인 토큰 원에 놓고, 공유 존 칸에도 소유를 표시한다.
    // 마커는 라운드에서 그 칸에 처음 카드를 놓을 때 놓이고, 칸이 비어도 남으며, 상대가 쓰면 뒤집힌다(engine.Game — 사용자 재정 2026-09-30)
    const owners = shList(st ? st.so : null);
    SHARED.forEach((_, k) => {
      const tok = this.q(`.token[data-k="${k}"]`), shz = this.q(`.shz[data-k="${k}"]`), own = owners[k] ?? null;
      if (own == null) { tok.classList.remove('on', 'black', 'flipping'); shz.classList.remove('on', 'black'); this.tokOwner[k] = null; return; }
      const white = own === this.firstOf(st, fr.r);
      if (this.tokOwner[k] == null) tok.style.setProperty('--from', `${own === 0 ? TOKEN_DROP : -TOKEN_DROP}px`);
      else if (this.tokOwner[k] !== own && animate) { tok.classList.remove('flipping'); void tok.offsetWidth; tok.classList.add('flipping'); }
      this.tokOwner[k] = own;
      tok.classList.add('on'); tok.classList.toggle('black', !white);
      tok.querySelector('.tl').innerHTML = `<span class="nm${own}">P${own + 1}</span>`;
      tok.title = `공유 존 ${k + 1} 마커 — ${white ? '백(선공 쪽)' : '흑(후공 쪽)'} · P${own + 1} ${this.names[own]} 소유`;
      shz.classList.add('on'); shz.classList.toggle('black', !white);
      shz.title = `공유 존 ${k + 1} — P${own + 1} ${this.names[own]} 소유(마커 ${white ? '백' : '흑'})`;
    });
  }
  chainNumbers(st, fx) {   // 카드 → 체인 번호들 (처리 중인 고리는 남은 체인 다음 번호)
    const m = new Map(), add = (u, n) => m.set(u, (m.get(u) || []).concat(n));
    const links = st ? st.ch : []; links.forEach((lk, k) => add(lk[0], k + 1));
    const res = fx.find(f => f.t === 'res'); if (res) add(res.u, links.length + 1);
    return m;
  }
  drawArrows(fx, st, L, i) {
    // 방향이 있는 화살표: 공격(공격 몬스터 → 공격 대상 · 직접 공격은 상대 쪽), 효과의 대상(발동 · 처리 중인 카드 → 대상),
    // 효과로 고른 카드(코스트 · 처리 때 고름). 고른 카드가 이 줄에서 옮겨졌으면 옮기기 전 자리(직전 상태)를 가리킨다
    const g = this.q('.fxl .arrows'); g.innerHTML = '';
    if (!st || !fx.some(f => f.t === 'atk' || f.t === 'pick' || (f.t === 'res' && f.to))) return;
    const ps = i > 0 ? this.stateAt(i - 1) : null, PL = ps && ps !== st ? this.layout(ps, []) : null;
    const at = (u, before) => { const a = L.get(u), b = PL && PL.get(u); return before ? (b || a) : (a || b); };
    const out = [];
    for (const f of fx) {
      if (f.t === 'atk') {
        const a = at(f.a, false); if (!a) continue;
        const d = f.d != null ? at(f.d, true) : null;
        out.push(['atk', a, d || {x: 832, y: HAND_Y[1 - f.p]}, d ? '' : '직접 공격']);
      } else if (f.t === 'pick' || (f.t === 'res' && f.to)) {
        const a = at(f.u, false); if (!a) continue;
        for (const u of f.to) { const b = at(u, true); if (b) out.push([f.t === 'res' || f.tg ? 'tgt' : 'pick', a, b, '']); }
      }
    }
    out.forEach(([kind, a, b, label], k) => this.arrow(g, kind, a, b, label, k));
  }
  arrow(g, kind, a, b, label, k) {
    const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy); if (len < ARROW.min) return;
    const ux = dx / len, uy = dy / len, s0 = Math.min(ARROW.start, len * .25), s1 = Math.min(ARROW.end, len * .3);
    const x1 = a.x + ux * s0, y1 = a.y + uy * s0, tx = b.x - ux * s1, ty = b.y - uy * s1;
    const bend = Math.min(ARROW.bendMax, len * ARROW.bend) * (k % 2 ? -1 : 1);   // 여러 개면 번갈아 휘어 겹치지 않게
    const cx = (x1 + tx) / 2 - uy * bend, cy = (y1 + ty) / 2 + ux * bend;
    const hl = Math.hypot(tx - cx, ty - cy) || 1, hx = (tx - cx) / hl, hy = (ty - cy) / hl, H = ARROW.head * (kind === 'atk' ? 1.2 : 1), W = H * .62;
    const ex = tx - hx * H * .85, ey = ty - hy * H * .85;
    const path = document.createElementNS(SVGNS, 'path');
    path.setAttribute('d', `M${x1.toFixed(1)} ${y1.toFixed(1)} Q${cx.toFixed(1)} ${cy.toFixed(1)} ${ex.toFixed(1)} ${ey.toFixed(1)}`);
    path.setAttribute('class', 'ar ' + kind);
    const head = document.createElementNS(SVGNS, 'polygon');
    head.setAttribute('points', [[tx, ty], [ex - hy * W / 2, ey + hx * W / 2], [ex + hy * W / 2, ey - hx * W / 2]].map(p => p.map(v => v.toFixed(1)).join(',')).join(' '));
    head.setAttribute('class', 'ah ' + kind);
    g.append(path, head);
    path.style.setProperty('--len', Math.ceil(path.getTotalLength()) + 1);
    if (label) {
      const t = document.createElementNS(SVGNS, 'text'); t.setAttribute('x', tx.toFixed(1)); t.setAttribute('y', (ty + (b.y < a.y ? -30 : 70)).toFixed(1));
      t.setAttribute('class', 'al ' + kind); t.textContent = label; g.append(t);
    }
  }
  // ── 막대 · 턴 · 체인 · 캡션 ──
  nameHtml(s) { this.names.forEach((n, k) => { s = s.split(esc(n)).join(`<span class="nm${k}">${esc(n)}</span>`); }); return s; }
  drawBars(st, fr, prev, i) {
    for (const seat of [0, 1]) {
      const el = this.q('.pb' + seat); const P = st ? st.P[seat] : null; const hp = P ? P.hp : 5000;
      el.classList.toggle('turnon', !!(st && st.tp === seat && fr.k !== 'round'));
      const w = this.WINS[i] || [0, 0];
      const dk = (this.meta.decks || [])[seat] || '';
      el.innerHTML = `<div class="who"><span class="seat">P${seat + 1}</span><span class="name">${esc(this.names[seat])}</span><span class="wins" title="라운드 승">${[0, 1].map(k => `<i class="${w[seat] > k ? 'on' : ''}"></i>`).join('')}</span></div>
        <span class="num"><small>HP</small>${hp}</span><div class="bar"><b style="width:${Math.max(0, Math.min(100, hp / 50))}%"></b></div>
        <div class="counts">${dk && dk !== this.names[seat] ? `<span class="deckn">${esc(dk)}</span> · ` : ''}패 <b>${P ? P.hand.length : 0}</b> · 메인 <b>${P ? P.main : 0}</b> · 상급 <b>${P ? P.upper : 0}</b> · 묘지 <b>${P ? P.grave.length : 0}</b> · 제외 <b>${P ? P.ban.length : 0}</b></div>`;
      if (prev && P) { const d = P.hp - prev.P[seat].hp; if (d) { const f = document.createElement('div'); f.className = 'float ' + (d < 0 ? 'dmg' : 'heal'); f.textContent = (d > 0 ? '+' : '') + d; el.appendChild(f); } }
    }
  }
  drawTurn(st, fr) {
    this.q('.turninfo').innerHTML = st ? `${fr.r}라운드 · ${st.t}턴 · <span class="nm${st.tp}">${esc(this.names[st.tp])}</span>의 턴` : (fr.r ? `${fr.r}라운드` : '');
    this.q('.phase').innerHTML = PHASES.map(p => `<span class="${st && st.ph === p && st.t > 0 ? 'on' : ''}">${p}</span>`).join('');
  }
  drawChain(st, fx) {
    // 체인 순서: 1번(먼저 발동)이 맨 위, 아래로 이어진다. 처리는 마지막 고리부터 — 처리 중인 고리는 남은 체인 아래에 금색으로
    const res = fx.find(f => f.t === 'res'), act = fx.find(f => f.t === 'act'); const links = st ? st.ch : [];
    const rows = links.map(([u, n, p, neg, to], k) => this.chainRow(k + 1, u, n, p, neg, to, act && act.u === u && k === links.length - 1 ? 'new' : ''));
    if (res) rows.push(this.chainRow(links.length + 1, res.u, res.n, res.p, 0, res.to, 'res'));
    const box = this.q('.chain'); box.innerHTML = rows.join('') || '<div class="empty">쌓인 체인 없음</div>';
    this.q('.chainp .cnt').textContent = rows.length ? `${rows.length}` : '';
    this.q('.chainp').classList.toggle('busy', rows.length > 0);
    box.querySelectorAll('.lk').forEach(x => x.addEventListener('click', () => this.select(+x.dataset.u)));
  }
  chainRow(no, u, n, p, neg, to, cls) {
    const ci = this.info(u), name = ci ? ci.name : '?', src = ci && this.face(name);
    const tg = (to || []).map(x => { const c = this.info(x); return c ? esc(c.name) : '?'; });
    const state = cls === 'res' ? ' · 처리 중' : neg ? ' · 무효' : '';
    return `<div class="lk ${cls}${neg ? ' negd' : ''}" data-u="${u}"><b class="no">${no}</b><span class="th">${src ? `<img src="${src}" alt="">` : ''}</span>`
      + `<span class="tx"><span class="nm"><span class="chip p${p}">P${p + 1}</span>${esc(name)}</span><small>${n ? n + '번 효과' : '카드 발동'}${state}</small>`
      + `${tg.length ? `<small class="to">→ 대상: ${tg.join(', ')}</small>` : ''}</span></div>`;
  }
  hidden(fr) {   // 실시간 대전 중 상대(AI)의 비공개 정보
    if (!this.mask) return false;
    if (fr.k === 'decision') return fr.d ? fr.d.p === 1 || fr.m.startsWith(`판단[${this.names[1]}]`) : fr.m.startsWith(`판단[${this.names[1]}]`);
    return false;
  }
  // ── 라운드 사이 전략 덱 교체 ──
  // 실시간 대전 중에는 상대(AI)가 무엇을 빼고 넣었는지 감춘다(실제 게임에서도 상대의 교체 내용은 모른다) — 재생 기록에서는 카드 이미지로 보여 준다
  sideSeat(fr) { return [0, 1].find(s => fr.m.startsWith(`${this.names[s]} 전략 덱 교체`)) ?? null; }
  sideHidden(fr) { return !!this.mask && fr.k === 'side' && this.sideSeat(fr) === 1; }
  swapsOf(fr) { return (fr.d && fr.d.swaps) || []; }
  sideHtml(fr) {
    const head = `${fr.r}라운드 → ${fr.r + 1}라운드 준비`, seat = this.sideSeat(fr), sw = this.swapsOf(fr);
    if (this.sideHidden(fr) || !sw.length) return `${head}<small>${this.nameHtml(esc(this.shortMsg(fr)))}</small>`;
    const who = seat != null ? `<span class="chip p${seat}">P${seat + 1}</span>${esc(this.names[seat])}` : '';
    // 뺀 카드 줄 · 넣은 카드 줄(같은 카드는 한 장으로 ×장수) — 스킬 교체는 두 스킬 카드에 「스킬」 표시
    const tally = names => { const m = new Map(); names.forEach(n => m.set(n, (m.get(n) || 0) + 1)); return [...m]; };
    const outs = tally(sw.map(x => x[0])), ins = tally(sw.map(x => x[1]));
    const skill = new Set(sw.filter(x => x[2] === '스킬 교체').flatMap(x => [x[0], x[1]]));
    const w = Math.max(SWAP_CARD.min, Math.min(SWAP_CARD.max, Math.floor(SWAP_CARD.row / Math.max(outs.length, ins.length)) - SWAP_CARD.gap));
    const card = ([name, n], cls) => {
      const p = this.POOL[name] || this.pool[name] || {name}, src = this.face(name);
      return `<div class="sc ${cls}"><div class="im">${src ? `<img src="${src}" alt="${esc(name)}">` : genCard(p)}${n > 1 ? `<i class="cnt">×${n}</i>` : ''}${skill.has(name) ? '<i class="sk">스킬</i>' : ''}</div><span class="nm">${esc(name)}</span></div>`;
    };
    const row = (list, cls, lab) => `<div class="row ${cls}"><b class="lab">${lab}</b>${list.map(x => card(x, cls)).join('')}</div>`;
    return `${head}<small>${who} 전략 덱 교체 ${sw.length}장</small><div class="swaps" style="--sw:${w}px">${row(outs, 'out', '뺌')}${row(ins, 'in', '넣음')}</div>`;
  }
  maskMsg(fr, m) {
    if (this.sideHidden(fr)) return `${this.names[1]} 전략 덱 교체 — 무엇을 바꿨는지는 대전이 끝난 뒤 재생 기록에서 볼 수 있습니다`;
    if (!this.mask || !m.startsWith(this.names[1])) return m;
    if (/드로우|시작 패|멀리건|세트$/.test(m)) return m.replace(/「[^」]+」/g, '「?」');
    return m;
  }
  shortMsg(fr) {
    if (fr.k === 'decision' && fr.d && fr.d.q) {
      const who = fr.d.p != null ? this.names[fr.d.p] : (fr.m.match(/^판단\[(.+?)\]/) || [])[1] || '';
      return `${who} 판단 · ${fr.d.q} → ${fr.d.pick}`;
    }
    return this.maskMsg(fr, fr.m.replace(/[━█■]+/g, '').trim());
  }
  optsLine(d) { return (!d || !d.opts || d.opts.length < 2) ? '' : d.opts.map(([lab, v]) => `${esc(lab)} ${v}%`).join(' · '); }
  frameIcon(fr) { return (fr.fx || []).some(f => f.t === 'atk') ? '⚔' : (ICON[fr.k] || '·'); }
  drawCaption(i) {
    const fr = this.F[i]; let main = `${this.frameIcon(fr)} ${this.nameHtml(esc(this.shortMsg(fr)))}`, sub = '', eff = '';
    if (this.hidden(fr)) main = `· ${esc(this.names[1])} 생각 중…`;
    const act = (fr.fx || []).find(f => f.t === 'act' || f.t === 'res');
    if (act) { const ci = this.info(act.u); const t = ci && effText(ci.pool, act.n); if (t) eff = esc(t); }
    if (fr.k === 'decision' && !this.hidden(fr)) sub = this.optsLine(fr.d);
    else if (!this.mask) {
      const dec = [];
      for (let j = i - 1; j >= 0 && this.F[j].k === 'decision' && dec.length < 2; j--) if (this.F[j].d && this.F[j].d.q) dec.unshift(this.F[j]);
      if (dec.length) sub = '판단: ' + dec.map(d => `${esc(d.d.q)} → ${esc(d.d.pick)}`).join(' / ');
    }
    this.q('.cap').innerHTML = `<div class="main">${main}</div>${eff ? `<div class="eff">${eff}</div>` : ''}${sub ? `<div class="sub">${sub}</div>` : ''}`;
  }
  // ── 기록 ──
  rowHtml(fr) {
    const o = fr.k === 'decision' && !this.hidden(fr) ? this.optsLine(fr.d) : '';
    return `<span class="ic">${this.frameIcon(fr)}</span><span>${this.nameHtml(esc(this.shortMsg(fr)))}${o ? `<span class="opts">${o}</span>` : ''}</span>`;
  }
  rebuildLog() { this.logEl.innerHTML = ''; this.rows = []; this.curRow = null; this.appendLog(0); }
  appendLog(start) {
    const frag = document.createDocumentFragment();
    for (let i = start; i < this.F.length; i++) {
      const fr = this.F[i]; const r = document.createElement('div'); r.className = 'row k-' + fr.k; r.dataset.i = i;
      if (this.hidden(fr) || fr.k === 'sync') r.style.display = 'none';
      r.innerHTML = this.rowHtml(fr); frag.appendChild(r); this.rows[i] = r;
    }
    this.logEl.appendChild(frag);
  }
  drawLogCursor(i) {
    if (this.curRow) this.curRow.classList.remove('cur');
    let vis = this.rows[i]; for (let j = i; j > 0 && vis && !vis.offsetParent; j--) vis = this.rows[j - 1];
    if (!vis) return;
    this.curRow = vis; vis.classList.add('cur');
    const top = vis.offsetTop, h = this.logEl.clientHeight;
    if (top < this.logEl.scrollTop + 20 || top > this.logEl.scrollTop + h - 40) this.logEl.scrollTop = top - h / 3;
  }
  // ── 카드 상세 ──
  select(uid) { this.selected = uid; this.showCard(uid); this.els.forEach((e, u) => e.el.classList.toggle('sel', u === uid)); }
  cellOf(uid) {
    const st = this.stateAt(this.lastRendered); if (!st) return null;
    const cs = [...shList(st.sh), st.fz]; st.P.forEach(P => cs.push(...P.m, ...P.s, P.sk)); return cs.find(c => c && c.u === uid) || null;
  }
  showName(name, extra) {
    const p = this.POOL[name] || this.pool[name]; if (!p) return;
    const src = this.face(name);
    this.q('.dbody').innerHTML = `<div class="dwrap"><div>${src ? `<img class="big" src="${src}" alt="${esc(p.name)}">` : genCard(p)}</div>
      <div><div class="dn">${esc(p.name)}</div><div class="dm">${esc(p.code || '')} · ${esc(typeLine(p))}${p.type === '몬스터' ? ` · 공 ${esc(p.atk ?? 0)} / 수 ${esc(p.def ?? 0)}` : ''}${extra && extra.owner != null ? ` · 주인 P${extra.owner + 1}` : ''}</div>
      <div class="dx">${esc(p.text || '')}</div>${extra && extra.stat ? `<div class="st">${esc(extra.stat)}</div>` : ''}</div></div>`;
  }
  showCard(uid) {
    const ci = this.info(uid); if (!ci) return;
    const o = this.els.get(uid) && this.els.get(uid).target;
    if (o && o.seat != null && !this.reveal[o.seat] && (o.hand || (o.cell && o.cell.f === 0))) { this.q('.dbody').innerHTML = '<div class="hint">상대의 비공개 카드입니다.</div>'; return; }
    const c = this.cellOf(uid), stat = [];
    if (c) { if (c.f === 0) stat.push('뒷면'); if (c.a != null) stat.push(`현재 공 ${c.a} / 수 ${c.d}${c.p ? ' · 수비 표시' : ' · 공격 표시'}`); if (c.c) stat.push('카운터 ' + Object.entries(c.c).map(([k, v]) => `${k} ${v}`).join(', ')); if (c.n) stat.push('무효 상태'); }
    this.showName(ci.name, {owner: ci.owner, stat: stat.join(' · ')});
  }
  showPile(seat, k) {
    const st = this.stateAt(this.lastRendered); if (!st) return;
    const list = st.P[seat][k];
    const th = list.slice().reverse().map(u => { const ci = this.info(u); const src = this.face(ci.name); return `<div class="th" data-u="${u}" title="${esc(ci.name)}">${src ? `<img src="${src}" alt="${esc(ci.name)}">` : esc(ci.name)}</div>`; }).join('');
    this.q('.dbody').innerHTML = `<div class="dn">P${seat + 1} ${k === 'grave' ? '묘지' : '제외 존'} · ${list.length}장 <span class="dm">(앞이 최근)</span></div><div class="thumbs">${th || '<span class="hint">비어 있음</span>'}</div>`;
    this.q('.dbody').querySelectorAll('.th').forEach(x => x.addEventListener('click', () => this.select(+x.dataset.u)));
    this.selected = null;
  }
  // 놓을 존 고르기(사람 자리): 고를 수 있는 빈 존을 보드에 표시하고 누르면 onPick(후보 번호)
  setZonePick(zones, onPick) {
    this.clearZonePick();
    this.zp = zones.map((z, i) => {
      const pos = z.zone === 'shared' ? SHARED[z.i || 0] : z.zone === 'm' ? Z[z.seat].m(z.i) : Z[z.seat].s(z.i);
      const b = document.createElement('button'); b.className = 'zpick' + (z.zone === 'shared' ? ' sh' : '');
      Object.assign(b.style, {left: (pos.x - SLOT.w / 2) + 'px', top: (pos.y - SLOT.h / 2) + 'px', width: SLOT.w + 'px', height: SLOT.h + 'px'});
      b.innerHTML = `<span>${z.zone === 'shared' ? `공유 존 ${(z.i || 0) + 1}` : z.i + 1}</span>`; b.title = z.zone === 'shared' ? `공유 존 ${(z.i || 0) + 1}에 놓기` : `${z.zone === 'm' ? '몬스터' : '마법'} 존 ${z.i + 1}에 놓기`;
      b.onclick = ev => { ev.stopPropagation(); this.clearZonePick(); onPick(i); };
      this.board.appendChild(b); return b;
    });
  }
  clearZonePick() { (this.zp || []).forEach(b => b.remove()); this.zp = null; }
  setHighlight(names, uids) { this.hl = new Set(names); this.hlu = new Set((uids || []).map(String)); if (this.lastRendered >= 0) this.render(this.lastRendered, true); }
  // ── 재생 ──
  visible(i) { const fr = this.F[i]; return !this.hidden(fr) && (this.showDec || fr.k !== 'decision'); }
  nextIdx(i, dir) { let j = i + dir; while (j >= 0 && j < this.F.length && !this.visible(j)) j += dir; return Math.max(0, Math.min(this.F.length - 1, j)); }
  go(i, animate) { if (!this.F.length) return; i = Math.max(0, Math.min(this.F.length - 1, i)); this.cur = i; this.render(i, animate); }
  step(dir) { const j = this.nextIdx(this.cur, dir); if (j !== this.cur || this.lastRendered !== j) this.go(j, dir > 0 && j - this.cur <= 40); }
  jumpTurn(dir) { const j = dir > 0 ? this.TURNS.find(t => t > this.cur) : [...this.TURNS].reverse().find(t => t < this.cur); this.go(j ?? (dir > 0 ? this.F.length - 1 : 0), false); }
  delayOf(i) {
    const fr = this.F[i], sw = fr.k === 'side' && !this.sideHidden(fr) ? Math.min(this.swapsOf(fr).length, SIDE_SWAP_DELAY_MAX) : 0;
    return ((BASE_DELAY[fr.k] || 700) + sw * SIDE_SWAP_DELAY) / this.speed;
  }
  caughtUp() { return this.nextIdx(this.cur, 1) === this.cur || this.cur >= this.F.length - 1; }
  tick() {
    if (!this.playing) return;
    if (this.caughtUp()) {
      if (this.lastRendered !== this.cur) this.go(this.cur, true);
      if (this.live && !this.ended) { this.timer = setTimeout(() => this.tick(), 150); if (this.o.onCaughtUp) this.o.onCaughtUp(); return; }
      this.stop(); if (this.o.onEnd) this.o.onEnd(); return;
    }
    this.step(1); if (this.o.onFrame) this.o.onFrame(this.cur);
    this.timer = setTimeout(() => this.tick(), this.delayOf(this.cur));
  }
  play(auto) {
    if (!this.F.length) return;
    if (!auto && this.caughtUp() && !this.live) this.go(0, false);
    if (this.live) this.follow = true;
    this.playing = true; this.q('[data-a=play]').textContent = '⏸ 정지'; clearTimeout(this.timer); this.timer = setTimeout(() => this.tick(), 200 / this.speed);
  }
  stop() { this.playing = false; clearTimeout(this.timer); const b = this.q('[data-a=play]'); if (b) b.textContent = '▶ 재생'; }
  setSpeed(v) { this.speed = v; this.q('[data-a=speed]').value = String(v); document.documentElement.style.setProperty('--dur', Math.round(Math.min(MOVE_MS_MAX, MOVE_MS / Math.sqrt(v))) + 'ms'); }
  fit() {
    this.arrange();
    if (!this.root.offsetParent) return;
    const W = innerWidth, ctl = this.q('.ctl').offsetHeight + 24;
    let top = this.root.getBoundingClientRect().top + scrollY;
    if (top > innerHeight * FIT_PUSHED) {   // 위의 내용(재생 목록 등)이 길어 무대가 아래로 밀렸으면 남은 틈 대신 화면 한 장 높이에 맞춘다(스크롤해서 봄)
      top = [...document.querySelectorAll('header')].reduce((s, h) => s + (getComputedStyle(h).position === 'sticky' ? h.offsetHeight : 0), 0) + 12;
    }
    const bars = this.q('.pb0').offsetHeight + this.q('.pb1').offsetHeight + 20;
    const maxH = W >= 1360 ? innerHeight - top - ctl - 10 : W >= 1000 ? innerHeight - top - ctl - bars : Infinity;
    const w = Math.max(280, Math.min(this.wrap.parentElement.clientWidth, maxH * this.MW / this.MH));
    const s = w / this.MW;
    this.wrap.style.width = w + 'px'; this.wrap.style.height = (this.MH * s) + 'px'; this.board.style.transform = `scale(${s})`;
    const nt = Math.min(40, Math.max(26, 10.5 / s));
    if (nt !== this.tfs) { this.tfs = nt; this.board.style.setProperty('--tfs', nt + 'px'); if (this.lastRendered >= 0) this.render(this.cur, false); }
  }
}
window.NNY = {Stage, esc, effText, typeLine, genCard};
})();
