/* 게임 화면: 관전 · 재생 목록 / AI 대전 / 덱 편집 / 학습 */
(async function () {
'use strict';
const {Stage, esc, effText, typeLine, genCard} = window.NNY;
const TOKEN = document.querySelector('meta[name=nny-token]').content;
const $ = id => document.getElementById(id);
async function api(path, body) {
  const r = await fetch('/api/' + path, {method: body ? 'POST' : 'GET', headers: {'X-NNY-Token': TOKEN, 'Content-Type': 'application/json'},
                                        body: body ? JSON.stringify(body) : undefined});
  let j = null; try { j = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error((j && j.error) || ('HTTP ' + r.status));
  return j;
}
let toastT = null;
function toast(msg, ms = 3200) {
  let t = document.querySelector('.toast'); if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t); }
  t.textContent = msg; t.style.display = ''; clearTimeout(toastT); toastT = setTimeout(() => t.style.display = 'none', ms);
}

let BOOT = await api('boot'); const POOL = await api('pool');
$('ver').textContent = 'v' + BOOT.version;
const assets = BOOT.assets;
const faceUrl = name => assets.faces[name] ? '/cards/' + assets.faces[name] : null;
const NAMES_SORTED = Object.keys(POOL).sort((a, b) => b.length - a.length);
function cardIn(label) { for (const n of NAMES_SORTED) if (label.includes(n)) return n; return null; }
setInterval(() => api('heartbeat', {}).catch(() => {}), 20000); api('heartbeat', {}).catch(() => {});

// ── 탭 ──
let stages = {};
function showView(v) {
  document.querySelectorAll('header .tab').forEach(t => t.classList.toggle('on', t.dataset.v === v));
  document.querySelectorAll('.view').forEach(s => s.classList.toggle('on', s.id === 'v-' + v));
  activeStage = v === 'watch' ? stages.watch : v === 'play' ? stages.play : null;
  if (activeStage) setTimeout(() => activeStage.fit(), 0);
  if (v === 'learn') refreshLearning();
  if (v === 'deck' && !ED.loaded) newDeck();
}
let activeStage = null;
document.querySelectorAll('header .tab').forEach(t => t.onclick = () => showView(t.dataset.v));
document.addEventListener('keydown', e => { if (activeStage) activeStage.key(e); });
$('quit').onclick = async () => { if (!confirm('프로그램을 끌까요?')) return; await api('quit', {}).catch(() => {}); document.body.innerHTML = '<p style="padding:40px">프로그램을 껐습니다. 이 창을 닫아도 됩니다.</p>'; };

function deckOptions(sel, withOfficialFirst = true, keep) {
  const prev = keep ?? sel.value;
  const og = BOOT.decks.filter(d => d.kind === 'official'), ug = BOOT.decks.filter(d => d.kind === 'user');
  const opt = d => `<option value="${esc(d.id)}" ${d.valid ? '' : 'disabled'}>${esc(d.kind === 'official' ? d.skill : d.name + ' (' + d.skill + ')')}${d.valid ? '' : ' — 규칙 오류'}</option>`;
  sel.innerHTML = `<optgroup label="기본 덱">${og.map(opt).join('')}</optgroup>` + (ug.length ? `<optgroup label="내 덱">${ug.map(opt).join('')}</optgroup>` : '');
  if (prev && [...sel.options].some(o => o.value === prev)) sel.value = prev;
}
async function refreshBoot() { BOOT = await api('boot'); ['r-a', 'r-b', 'g-deck', 'g-ai'].forEach(id => deckOptions($(id))); renderReplays(); renderDeckList(); }

// ═══════════════ 관전 · 재생 목록 ═══════════════
stages.watch = new Stage($('w-stage'), {assets, pool: POOL, onEnd: () => playlistNext(true)});
activeStage = stages.watch;
const W = {sel: new Set(), pl: {name: '', items: []}, idx: -1, playing: false};
$('w-stage').querySelector('.extra').innerHTML = '<button data-x="prevm" title="이전 매치">⏪ 이전 매치</button><button data-x="nextm" title="다음 매치">다음 매치 ⏩</button>';
$('w-stage').querySelector('[data-x=prevm]').onclick = () => playlistGo(W.idx - 1);
$('w-stage').querySelector('[data-x=nextm]').onclick = () => playlistGo(W.idx + 1);
function setLists(show) { $('w-lists').style.display = show ? '' : 'none'; $('w-toggle').textContent = show ? '목록 접기' : '목록 펼치기'; setTimeout(() => stages.watch.fit(), 0); }
$('w-toggle').onclick = () => setLists($('w-lists').style.display === 'none');
function repLabel(r) {
  const win = r.winner == null ? (r.status === 'done' ? '무승부' : r.status) : (r.names[r.winner] + ' 승');
  const score = r.rounds && r.rounds.length ? ` (${r.rounds.filter(x => x[0] === 0).length}–${r.rounds.filter(x => x[0] === 1).length})` : '';
  // 학습표 AI가 아닌 AI가 둔 매치는 AI 종류를 덧붙인다(meta.ai = P1 · meta.ai2 = P2 — session.LiveMatch)
  const kinds = [...new Set([r.kind === 'human' ? null : r.ai, r.ai2].filter(k => k && k !== 'table'))].map(k => k === 'heuristic' ? '휴리스틱 AI' : k.startsWith('nn') ? '신경망 AI' : k);
  return {t: r.title, s: `${r.source === 'library' ? '기본 제공' : r.kind === 'human' ? '내 대전' : '내 녹화'}${kinds.length ? ' · ' + kinds.join(' · ') : ''} · ${win}${score} · ${r.created || ''}`};
}
function repById(id) { return BOOT.replays.find(r => r.id === id); }
function renderReplays() {
  const q = $('w-filter').value.trim(), src = $('w-src').value;
  const list = BOOT.replays.filter(r => (!src || r.source === src) && (!q || r.title.includes(q) || r.decks.join(' ').includes(q)));
  $('w-replays').innerHTML = list.map(r => { const l = repLabel(r); return `<div class="item${W.sel.has(r.id) ? ' on' : ''}" data-id="${esc(r.id)}">
    <input type="checkbox" ${W.sel.has(r.id) ? 'checked' : ''}><div class="grow">${esc(l.t)}<small>${esc(l.s)}</small></div><button class="btn sm" data-play>▶</button></div>`; }).join('') || '<div class="hint">재생 기록이 없습니다.</div>';
  $('w-replays').querySelectorAll('.item').forEach(el => {
    const id = el.dataset.id;
    el.querySelector('input').onclick = ev => { ev.stopPropagation(); W.sel.has(id) ? W.sel.delete(id) : W.sel.add(id); el.classList.toggle('on', W.sel.has(id)); };
    el.querySelector('[data-play]').onclick = ev => { ev.stopPropagation(); playSingle(id); };
    el.onclick = () => { el.querySelector('input').click(); };
  });
}
$('w-filter').oninput = renderReplays; $('w-src').onchange = renderReplays;
$('w-selall').onclick = () => { $('w-replays').querySelectorAll('.item').forEach(el => W.sel.add(el.dataset.id)); renderReplays(); };
$('w-addsel').onclick = () => { const add = BOOT.replays.filter(r => W.sel.has(r.id)).map(r => r.id); W.pl.items.push(...add); renderPlaylist(); toast(`${add.length}개를 재생 목록에 넣었습니다(저장하려면 「저장」).`); };
$('w-del').onclick = async () => {
  const ids = [...W.sel].filter(id => id.startsWith('u:')); if (!ids.length) return toast('지울 수 있는 내 기록이 없습니다.');
  if (!confirm(`내 기록 ${ids.length}개를 지울까요?`)) return;
  for (const id of ids) await api('replay/delete', {id});
  W.sel.clear(); await refreshBoot(); toast('지웠습니다.');
};
async function loadReplay(id) {
  $('w-now').textContent = '불러오는 중…';
  const rec = await api('replay?id=' + encodeURIComponent(id));
  stages.watch.load(rec); stages.watch.fit();
  const r = repById(id); $('w-now').textContent = r ? `재생 중: ${r.title}` + (W.idx >= 0 && W.pl.items.length ? ` · 재생 목록 ${W.idx + 1}/${W.pl.items.length}` : '') : '';
}
async function playSingle(id) { W.idx = -1; setLists(false); await loadReplay(id); stages.watch.play(); }
// 재생 목록
function renderPlaylistSelect() {
  $('pl-select').innerHTML = '<option value="">— 저장된 재생 목록 —</option>' + BOOT.playlists.map((p, i) => `<option value="${i}">${esc(p.name)} (${p.items.length})</option>`).join('');
}
function renderPlaylist() {
  $('pl-name').value = W.pl.name;
  $('pl-items').innerHTML = W.pl.items.map((id, i) => { const r = repById(id); const l = r ? repLabel(r) : {t: '(지워진 기록)', s: id};
    return `<div class="item${i === W.idx ? ' on' : ''}" data-i="${i}"><b class="muted">${i + 1}</b><div class="grow">${esc(l.t)}<small>${esc(l.s)}</small></div>
      <button class="btn sm" data-a="up" title="위로">▲</button><button class="btn sm" data-a="down" title="아래로">▼</button><button class="btn sm" data-a="rm" title="빼기">✕</button></div>`; }).join('')
    || '<div class="hint">왼쪽에서 기록을 골라 「재생 목록에 추가」하세요.</div>';
  $('pl-items').querySelectorAll('.item').forEach(el => {
    const i = +el.dataset.i;
    el.onclick = ev => { const a = ev.target.dataset.a; if (!a) return playlistGo(i);
      const it = W.pl.items;
      if (a === 'up' && i > 0) [it[i - 1], it[i]] = [it[i], it[i - 1]];
      if (a === 'down' && i < it.length - 1) [it[i + 1], it[i]] = [it[i], it[i + 1]];
      if (a === 'rm') it.splice(i, 1);
      renderPlaylist(); };
  });
}
$('pl-select').onchange = () => { const i = $('pl-select').value; if (i === '') return; const p = BOOT.playlists[+i]; W.pl = {name: p.name, items: [...p.items], saved: +i}; W.idx = -1; renderPlaylist(); };
$('pl-new').onclick = () => { W.pl = {name: '', items: []}; W.idx = -1; $('pl-select').value = ''; renderPlaylist(); };
$('pl-save').onclick = async () => {
  W.pl.name = $('pl-name').value.trim() || '재생 목록'; const pls = [...BOOT.playlists];
  const i = pls.findIndex(p => p.name === W.pl.name); const item = {name: W.pl.name, items: W.pl.items};
  if (i >= 0) pls[i] = item; else pls.push(item);
  BOOT.playlists = await api('playlists', {playlists: pls}); renderPlaylistSelect(); $('pl-select').value = String(BOOT.playlists.findIndex(p => p.name === W.pl.name)); toast('재생 목록을 저장했습니다.');
};
$('pl-delete').onclick = async () => {
  const i = BOOT.playlists.findIndex(p => p.name === $('pl-name').value.trim()); if (i < 0) return toast('저장된 재생 목록이 아닙니다.');
  if (!confirm('이 재생 목록을 지울까요?')) return;
  const pls = BOOT.playlists.filter((_, k) => k !== i); BOOT.playlists = await api('playlists', {playlists: pls}); renderPlaylistSelect(); $('pl-new').click();
};
$('pl-play').onclick = () => { setLists(false); playlistGo(0); };
async function playlistGo(i) {
  if (!W.pl.items.length) return toast('재생 목록이 비어 있습니다.');
  if (i < 0) i = 0;
  if (i >= W.pl.items.length) { if ($('pl-loop').checked) i = 0; else { toast('재생 목록 끝입니다.'); return; } }
  W.idx = i; renderPlaylist();
  try { await loadReplay(W.pl.items[i]); stages.watch.play(); } catch (e) { toast('불러오지 못했습니다: ' + e.message); playlistNext(true); }
}
function playlistNext(auto) { if (W.idx < 0 || !$('pl-auto').checked) return; setTimeout(() => playlistGo(W.idx + 1), auto ? 1500 : 0); }
// 녹화
['r-a', 'r-b'].forEach(id => deckOptions($(id)));
$('r-b').selectedIndex = Math.min(1, $('r-b').options.length - 1);
let jobT = null;
$('r-go').onclick = async () => {
  try { const j = await api('record', {pairs: [[$('r-a').value, $('r-b').value]], matches: +$('r-n').value || 1, ai_kind: $('r-ai').value}); W.job = j.id; watchJob(); }
  catch (e) { toast(e.message); }
};
$('r-stop').onclick = () => W.job && api('jobs/stop', {id: W.job});
function watchJob() {
  clearInterval(jobT);
  jobT = setInterval(async () => {
    const js = await api('jobs'); const j = js.find(x => x.id === W.job); if (!j) return;
    $('r-bar').style.width = (100 * j.done / j.total) + '%'; $('r-msg').textContent = `${j.done} / ${j.total} 매치 녹화` + (j.status === 'running' ? ' — 진행 중' : ' — 끝');
    if (j.status !== 'running') { clearInterval(jobT); await refreshBoot(); toast('녹화가 끝났습니다. 재생 기록 목록(내 기록)에 있습니다.'); }
  }, 1500);
}
renderReplays(); renderPlaylistSelect(); renderPlaylist();
if (BOOT.replays.length) { loadReplay(BOOT.replays[0].id).catch(() => {}); }

// ═══════════════ AI 대전 ═══════════════
stages.play = new Stage($('g-stage'), {assets, pool: POOL, onCaughtUp: () => drawDecision(), onFrame: () => {}});
['g-deck', 'g-ai'].forEach(id => deckOptions($(id)));
$('g-ai').selectedIndex = Math.min(1, $('g-ai').options.length - 1);
$('g-learn').checked = !!BOOT.settings.learn; $('g-hints').checked = !!BOOT.settings.hints;
$('g-mode').onchange = () => { const h = $('g-mode').value === 'human'; $('g-mylabel').textContent = h ? '내 덱' : 'P1 덱'; $('g-learn').disabled = !h; $('g-hints').disabled = !h; };
const G = {id: null, pending: null, poll: null, busy: false, human: true, done: false};
const decBox = () => $('g-stage').querySelector('.dec');
$('g-start').onclick = async () => {
  if (G.id && !G.done && !confirm('진행 중인 대전을 그만두고 새로 시작할까요?')) return;
  try {
    const human = $('g-mode').value === 'human';
    const r = await api('match/start', {mode: human ? 'human' : 'ai', deck: $('g-deck').value, ai_deck: $('g-ai').value, first: $('g-first').value,
                                        learn: $('g-learn').checked, hints: $('g-hints').checked, ai_kind: $('g-aikind').value});
    G.id = r.id; G.pending = null; G.done = false; G.human = human;
    const lab = sel => sel.options[sel.selectedIndex].textContent.replace(/ — 규칙 오류$/, '');
    stages.play.ended = false;
    stages.play.startLive(r.names, {decks: [lab($('g-deck')), lab($('g-ai'))]}, human);
    stages.play.fit(); decBox().innerHTML = ''; $('g-abort').disabled = false;
    const kind = $('g-aikind').value;
    $('g-status').textContent = `대전 중: ${r.title}` + (kind === 'nn' ? ` · 신경망 AI(${BOOT.nn && BOOT.nn.using === 'local' ? '내 모델' : '기본 모델'})` : kind === 'heuristic' ? ' · 휴리스틱 AI' : '')
      + (human && $('g-learn').checked ? ' · AI 학습 켜짐' : '');
    clearTimeout(G.poll); pollLive();
  } catch (e) { toast(e.message, 6000); }
};
$('g-abort').onclick = async () => { if (!confirm('대전을 그만둘까요? (끝낸 라운드까지는 기록 · 학습됩니다)')) return; await api('match/abort', {}); };
async function pollLive() {
  if (!G.id) return;
  const st = stages.play;
  try {
    const d = await api(`match/poll?id=${G.id}&f=${st.F.length}&s=${st.S.length}&c=${Object.keys(st.cards).length}`);
    if (d.status === 'none') return;
    st.appendLive(d);
    G.pending = d.pending;
    if (d.pending && st.caughtUp()) drawDecision();
    if (!d.pending && decBox().dataset.rid) { decBox().innerHTML = ''; delete decBox().dataset.rid; st.setHighlight([]); st.clearZonePick(); }
    if (d.result && !G.done) {
      if (st.caughtUp()) { finishLive(d); return; }
    }
  } catch (e) { $('g-status').textContent = '연결 오류: ' + e.message; }
  G.poll = setTimeout(pollLive, G.pending ? 400 : 250);
}
function finishLive(d) {
  G.done = true; const st = stages.play; st.ended = true; st.endLive(); $('g-abort').disabled = true; decBox().innerHTML = '';
  const res = d.result, names = d.names;
  const w = [0, 1].map(s => res.rounds.filter(r => r.winner === s).length);
  const msg = d.status === 'done' ? (res.winner == null ? `무승부 (${w[0]}–${w[1]})` : `${names[res.winner]} 승 (${w[0]}–${w[1]})`)
            : d.status === 'aborted' ? '그만둠' : d.status === 'stalled' ? '1000턴 안전장치로 중단' : '오류로 중단';
  $('g-status').innerHTML = `대전 끝: <b>${esc(msg)}</b>` + (d.learned ? ` · AI가 이 매치의 판단 ${d.learned}개를 학습했습니다(다음 대전부터 반영)` : '')
    + (d.nn_saved ? ` · 신경망 표본 ${d.nn_saved}개 저장(「🧠 신경망 학습」에서 학습)` : '')
    + (d.replay_id ? ' · 재생 기록에 저장됨' : '') + (d.error ? `<pre class="err" style="white-space:pre-wrap">${esc(d.error)}</pre>` : '');
  refreshBoot().catch(() => {});
}
// 판단 패널
const DEC_TITLE = [[/^진행 행동$/, '진행 단계 — 할 행동을 고르세요'], [/^정비 행동$/, '정비 단계 — 할 행동을 고르세요'], [/^우선권$/, '우선권 — 효과를 발동할까요?'],
  [/^대응$/, '체인 대응 — 응답할까요?'], [/^공격$/, '전투 — 공격할 몬스터와 대상'], [/^대상:(.+)$/, '대상 고르기 ($1)'], [/^트리거:(.+)#(\d+)$/, '「$1」 $2번 트리거 — 발동할까요?'],
  [/^멀리건:(.+)$/, '멀리건 — 「$1」을(를) 되돌릴까요?'], [/^시작 패 배분\((선공|후공)\)$/, '시작 패($1) — 메인 덱 · 상급 덱에서 몇 장씩 뽑을까요?'], [/^시작 패 재배분\((선공|후공)·(\d+)장·.*\)$/, '멀리건($1) — 되돌린 $2장을 메인 · 상급에서 몇 장씩 다시 뽑을까요? (처음과 달라도 됩니다)'], [/^드로우 덱/, '드로우할 덱'], [/^소환 표시 형식:(일반|특수)$/, '$1소환 — 표시 형식(앞면 공격 · 앞면 수비)'], [/^놓을 존:(.+)$/, '「$1」을(를) 놓을 존 — 보드에서 빛나는 칸을 누르거나 아래에서 고르세요'], [/^버릴 카드$/, '버릴 카드'], [/^서치:(.+)$/, '서치 — $1']];
function decTitle(q) { for (const [re, t] of DEC_TITLE) if (re.test(q)) return q.replace(re, t); return q; }
function optText(lab) {
  let m;
  if ((m = lab.match(/^발동:(.+)#(\d+)$/))) return {t: `발동 · ${m[1]}`, s: `${m[2]}번 효과`, card: m[1], eff: +m[2]};
  if ((m = lab.match(/^(.+)#(\d+)$/))) return {t: `발동 · ${m[1]}`, s: `${m[2]}번 효과`, card: m[1], eff: +m[2]};
  if ((m = lab.match(/^소환:(.+)$/))) return {t: `일반소환 · ${m[1]}`, card: m[1]};
  if ((m = lab.match(/^세트:(.+)$/))) return {t: `세트 · ${m[1]}`, card: m[1]};
  if ((m = lab.match(/^(.+)→직접$/))) return {t: `${m[1]} → 직접공격`, card: m[1]};
  if ((m = lab.match(/^(.+)→(.+)$/))) return {t: `${m[1]} → ${m[2]} 공격`, card: m[1], card2: m[2]};
  if ((m = lab.match(/^([자상]):(.+)@(\w+)$/))) return {t: `${m[1] === '자' ? '자신' : '상대'} · ${m[2]}`, s: {m: '몬스터 존', s: '마법 존', shared: '공유 존', fieldz: '필드 존', hand: '패', grave: '묘지'}[m[3]] || m[3], card: m[2]};
  if (lab === '종료') return {t: '이 단계 끝내기'};
  if (lab === '패스') return {t: '패스(응답하지 않음)'};
  const c = cardIn(lab); return {t: lab, card: c};
}
function drawDecision() {
  const p = G.pending, box = decBox();
  if (!p || G.done) return;
  if (box.dataset.rid === String(p.id)) return;
  box.dataset.rid = String(p.id);
  if (p.kind === 'side') { drawSide(p, box); return; }
  // o.sub: 같은 이름 카드를 구별하는 칸 설명(「자신 몬스터 존 1 → 상대 몬스터 존 3」), o.u: 빛낼 카드(기록기 번호) — 사람 자리 HumanAI._ask
  const opts = p.opts.map((o, i) => { const x = optText(o.label); const src = x.card && faceUrl(x.card);
    const eff = x.eff && x.card && POOL[x.card] ? effText(POOL[x.card], x.eff).split('\n')[0] : '';
    const sub = [o.sub, x.s].filter(Boolean).join(' · ');
    return `<button class="opt" data-i="${i}" data-card="${esc(x.card || '')}" data-u="${esc((o.u || []).join(','))}">${src ? `<img src="${src}" alt="">` : ''}<span class="t">${esc(x.t)}${sub || eff ? `<small>${esc(sub)}${eff ? ' — ' + esc(eff.replace(/^\d+\.\s*/, '')) : ''}</small>` : ''}</span>${o.v != null ? `<span class="v">${o.v}%</span>` : ''}</button>`; }).join('');
  box.innerHTML = `<div class="decision"><div class="q">${esc(decTitle(p.decision))}<small>${p.turn ? p.turn + '턴 · ' + esc(p.phase) : ''}</small></div><div class="opts">${opts}</div></div>`;
  box.querySelectorAll('.opt').forEach(b => {
    b.onmouseenter = () => { const c = b.dataset.card, u = b.dataset.u ? b.dataset.u.split(',') : [];
      if (c) stages.play.showName(c);
      if (u.length) stages.play.setHighlight([], u); else if (c) stages.play.setHighlight([c]); };   // 칸이 정해진 후보는 그 카드만 빛낸다
    b.onmouseleave = () => stages.play.setHighlight([]);
    b.onclick = () => answerDec(p, box, +b.dataset.i);
  });
  if (p.zones) { stages.play.setZonePick(p.zones, i => answerDec(p, box, i)); if (p.card) stages.play.showName(p.card); }   // 놓을 존: 보드에서 눌러 고르기
  stages.play.fit();
}
async function answerDec(p, box, i) {
  box.innerHTML = '<div class="decision wait"><div class="q">처리 중…</div></div>'; stages.play.setHighlight([]); stages.play.clearZonePick();
  try { await api('match/answer', {rid: p.id, idx: i}); } catch (e) { toast(e.message); }
  G.pending = null; delete box.dataset.rid; box.innerHTML = '';
}
// 라운드 사이 전략 덱 교체 — 서버가 보낸 할 수 있는 교체(opts)를 넣을 카드별로 묶어 보여 주고, 하나씩 고른다(고를 때마다 서버가 다시 계산)
function drawSide(p, box) {
  const cnt = Object.fromEntries(p.active), stc = Object.fromEntries(p.strategy);
  const btn = (o, i, t, s) => { const src = faceUrl(o.out); return `<button class="opt${o.misfit ? ' misfit' : ''}" data-i="${i}" data-card="${esc(o.out || '')}">${src ? `<img src="${src}" alt="">` : ''}<span class="t">${esc(t)}${s ? `<small>${esc(s)}</small>` : ''}</span></button>`; };
  const groups = {}; const order = [];
  p.opts.forEach((o, i) => { if (o.kind === 'card' || o.kind === 'skill') { const k = o.kind + ':' + o.in; if (!groups[k]) { groups[k] = []; order.push(k); } groups[k].push([o, i]); } });
  const grp = order.map(k => { const [o0] = groups[k][0]; const src = faceUrl(o0.in);
    const head = o0.kind === 'skill' ? `스킬 교체 → 「${o0.in}」` : `넣기: 「${o0.in}」`;
    const sub = o0.kind === 'skill' ? '' : `전략 덱 ${stc[o0.in] || 0}장 · 활성 덱 ${cnt[o0.in] || 0}장 · 뺄 카드 ${groups[k].length}종`;
    return `<details class="sw"><summary data-card="${esc(o0.in)}">${src ? `<img src="${src}" alt="">` : ''}<span class="t">${esc(head)}${sub ? `<small>${esc(sub)}</small>` : ''}</span></summary><div class="opts">`
      + groups[k].map(([o, i]) => btn(o, i, o.kind === 'skill' ? `「${o.out}」 대신 「${o.in}」` : `빼기: 「${o.out}」`, o.kind === 'skill' ? '바꾼 뒤 새 스킬 태그에 맞지 않는 메인 · 상급 카드는 전략 덱으로 보내야 진행할 수 있습니다' : `활성 덱 ${cnt[o.out] || 0}장${o.misfit ? ' · 스킬 태그 안 맞음 → 전략 덱으로' : ''}`)).join('') + '</div></details>'; }).join('');
  const mis = (p.misfit || []).length ? `<div class="misfit">스킬 「${esc(p.skill)}」의 태그에 맞지 않는 메인 · 상급 카드 — 모두 전략 덱으로 보내야 진행할 수 있습니다: `
    + p.misfit.map(([n, k]) => `「${esc(n)}」×${k}`).join(', ') + '</div>' : '';
  const fixed = p.opts.map((o, i) => o.kind === 'done' || o.kind === 'reset' ? `<button class="opt ${o.kind}" data-i="${i}"><span class="t">${esc(o.label)}</span></button>` : '').join('');
  const done = p.swaps.length ? '바꾼 카드: ' + p.swaps.map(([a, b]) => `「${a}」 → 「${b}」`).join(', ') : '아직 바꾼 카드 없음';
  box.innerHTML = `<div class="decision side"><div class="q">${esc(p.decision)} — 승점 ${p.wins[0]}–${p.wins[1]}<small>내 스킬 「${esc(p.skill)}」 · 상대 스킬 「${esc(p.opp_skill)}」 · ${esc(done)}</small></div>`
    + (p.error ? `<div class="err">${esc(p.error)}</div>` : '') + mis + `<div class="fixed">${fixed}</div>`
    + `<div class="opts">${grp || '<small class="muted">지금 덱에서 할 수 있는 교체가 없습니다</small>'}</div></div>`;
  box.querySelectorAll('[data-card]').forEach(b => {
    b.onmouseenter = () => { const c = b.dataset.card; if (c) { stages.play.showName(c); stages.play.setHighlight([c]); } };
    b.onmouseleave = () => stages.play.setHighlight([]);
  });
  box.querySelectorAll('.opt').forEach(b => { b.onclick = () => answerDec(p, box, +b.dataset.i); });
  stages.play.fit();
}

// ═══════════════ 덱 편집 ═══════════════
const ED = {id: null, deck: null, loaded: false, dirty: false};
const SECS = ['메인', '상급', '전략'];
$('d-skill').innerHTML = BOOT.skills.map(s => `<option>${esc(s)}</option>`).join('');
const themes = [...new Set(Object.values(POOL).map(p => p.theme).filter(Boolean))];
$('p-theme').innerHTML = '<option value="">테마 전체</option>' + themes.map(t => `<option>${esc(t)}</option>`).join('');
function renderDeckList() {
  $('d-list').innerHTML = BOOT.decks.map(d => `<div class="item${ED.id === d.id ? ' on' : ''}" data-id="${esc(d.id)}"><div class="grow">${esc(d.kind === 'official' ? d.skill : d.name)}
    <small>${d.kind === 'official' ? '기본 덱' : '내 덱 · ' + esc(d.skill)} · 메인 ${d.counts['메인']} · 상급 ${d.counts['상급']} · 전략 ${d.counts['전략']}${d.valid ? '' : ' · 규칙 오류'}</small></div></div>`).join('');
  $('d-list').querySelectorAll('.item').forEach(el => el.onclick = () => openDeck(el.dataset.id));
}
async function openDeck(id) {
  if (ED.dirty && !confirm('저장하지 않은 변경이 있습니다. 다른 덱을 열까요?')) return;
  const r = await api('deck?id=' + encodeURIComponent(id));
  const d = r.deck; ED.deck = {이름: d['이름'], 스킬: d['스킬'], 메인: d['메인'].map(x => [...x]), 상급: d['상급'].map(x => [...x]), 전략: d['전략'].map(x => [...x])};
  if (id.startsWith('o:')) { ED.id = null; ED.deck['이름'] = d['스킬'] + ' 복사'; $('d-state').textContent = '기본 덱의 복사본입니다 — 저장하면 내 덱이 됩니다.'; }
  else { ED.id = id; $('d-state').textContent = ''; }
  ED.loaded = true; ED.dirty = false; renderEditor(); renderDeckList();
}
function newDeck() { ED.id = null; ED.deck = {이름: '새 덱', 스킬: BOOT.skills[0], 메인: [], 상급: [], 전략: []}; ED.loaded = true; ED.dirty = false; $('d-state').textContent = ''; renderEditor(); renderDeckList(); }
$('d-new').onclick = () => { if (ED.dirty && !confirm('저장하지 않은 변경이 있습니다. 새 덱을 만들까요?')) return; newDeck(); };
$('d-name').oninput = () => { ED.deck['이름'] = $('d-name').value; ED.dirty = true; };
$('d-skill').onchange = () => { ED.deck['스킬'] = $('d-skill').value; ED.dirty = true; renderEditor(); };
function skillTags(sk) { return sk ? [...(sk.skill_tags || []), ...(sk.no_common ? [] : ['공용'])] : []; }
function allowed(name, sec) {   // 덱 구축 기준(deck.validate 와 같음): 메인 · 상급 = 주 스킬의 태그 또는 「공용」, 전략 = 주 스킬 또는 전략 덱의 스킬 카드 태그
  const c = POOL[name]; if (!POOL[ED.deck['스킬']] || !c) return false;
  if (c.type === '스킬') return true;
  const tags = new Set(skillTags(POOL[ED.deck['스킬']]));
  if (sec === '전략') ED.deck['전략'].forEach(([, n]) => { if (POOL[n] && POOL[n].type === '스킬') skillTags(POOL[n]).forEach(t => tags.add(t)); });
  return (c.tags || []).some(t => tags.has(t));
}
const poolSec = () => $('p-strat').checked ? '전략' : '메인';
function countOf(sec, name) { const e = ED.deck[sec].find(x => x[1] === name); return e ? e[0] : 0; }
function totalIn(name) { return SECS.reduce((s, sec) => s + countOf(sec, name), 0); }
function addCard(name, toStrat) {
  const c = POOL[name]; if (!c) return;
  if (c.type === '스킬' && !toStrat) { ED.deck['스킬'] = name; ED.dirty = true; renderEditor(); return; }
  const sec = toStrat || c.type === '스킬' ? '전략' : (c.deck === '상급' ? '상급' : '메인');
  const MAXC = BOOT.max_copies || 3, group = sec === '전략' ? ['전략'] : ['메인', '상급'];   // 동명 카드 상한: 메인 · 상급 합계 / 전략 덱 (deck.validate)
  if (group.reduce((s, x) => s + countOf(x, name), 0) >= MAXC) {
    toast(`「${name}」는 ${sec === '전략' ? '전략 덱에' : '메인 · 상급 덱에'} 이미 ${MAXC}장 있습니다 — 같은 이름의 카드는 ${MAXC}장까지 넣을 수 있습니다.`); return;
  }
  const lst = ED.deck[sec]; const e = lst.find(x => x[1] === name);
  if (e) e[0] += 1; else lst.push([1, name]);
  ED.dirty = true; renderEditor();
}
function removeCard(name, sec) {
  for (const s of sec ? [sec] : ['전략', '상급', '메인']) {
    const lst = ED.deck[s]; const i = lst.findIndex(x => x[1] === name);
    if (i >= 0) { lst[i][0] -= 1; if (lst[i][0] <= 0) lst.splice(i, 1); ED.dirty = true; break; }
  }
  renderEditor();
}
let valT = null;
function renderEditor() {
  const d = ED.deck; $('d-name').value = d['이름']; $('d-skill').value = d['스킬'];
  $('d-delete').disabled = !ED.id;
  $('d-secs').innerHTML = SECS.map(sec => {
    const tot = d[sec].reduce((s, x) => s + x[0], 0), [lo, hi] = BOOT.limits[sec];
    const rows = d[sec].slice().sort((a, b) => (POOL[a[1]]?.code || '').localeCompare(POOL[b[1]]?.code || '')).map(([n, name]) => { const src = faceUrl(name);
      return `<div class="deckrow" data-name="${esc(name)}" data-sec="${sec}">${src ? `<img src="${src}" alt="">` : ''}<span class="nm">${esc(name)}</span>
        <button class="btn sm" data-a="minus">−</button><span class="n">${n}</span><button class="btn sm" data-a="plus">+</button></div>`; }).join('') || '<div class="hint">비어 있음</div>';
    return `<div class="secttl">${sec} 덱<span class="cnt${tot < lo || tot > hi ? ' bad' : ''}">${tot}장 (허용 ${lo}~${hi})</span></div><div class="deckrows">${rows}</div>`;
  }).join('');
  $('d-secs').querySelectorAll('.deckrow').forEach(el => {
    const name = el.dataset.name, sec = el.dataset.sec;
    el.querySelector('[data-a=minus]').onclick = () => removeCard(name, sec);
    el.querySelector('[data-a=plus]').onclick = () => addCard(name, sec === '전략');
    el.querySelector('.nm').onclick = () => showPoolCard(name);
  });
  renderPool();
  clearTimeout(valT); valT = setTimeout(validate, 200);
}
async function validate() {
  const r = await api('deck/validate', ED.deck).catch(e => ({errs: [e.message], warns: []}));
  $('d-msgs').innerHTML = r.errs.map(e => `<div class="err">✕ ${esc(e)}</div>`).join('') + r.warns.map(e => `<div class="warn">! ${esc(e)}</div>`).join('')
    + (r.errs.length ? '' : '<div class="ok">✓ 덱 규칙을 지켰습니다 — 저장하면 AI 대전에 쓸 수 있습니다.</div>');
}
function renderPool() {
  const q = $('p-q').value.trim(), th = $('p-theme').value, ty = $('p-type').value, fit = $('p-fit').checked;
  const list = Object.values(POOL).filter(p => (!th || p.theme === th) && (!ty || p.type === ty) && (!fit || allowed(p.name, poolSec()))
    && (!q || p.name.includes(q) || (p.text || '').includes(q))).sort((a, b) => (a.code || '').localeCompare(b.code || ''));
  $('p-grid').innerHTML = list.map(p => { const src = faceUrl(p.name); const n = totalIn(p.name) + (ED.deck['스킬'] === p.name ? 1 : 0);
    return `<div class="pc${allowed(p.name, poolSec()) ? '' : ' no'}" data-name="${esc(p.name)}" title="${esc(p.name)}">${src ? `<img src="${src}" alt="${esc(p.name)}" loading="lazy">` : esc(p.name)}${n ? `<span class="in">${n}</span>` : ''}</div>`; }).join('');
  $('p-grid').querySelectorAll('.pc').forEach(el => {
    const name = el.dataset.name;
    el.onclick = () => addCard(name, $('p-strat').checked);
    el.oncontextmenu = ev => { ev.preventDefault(); removeCard(name); };
    el.onmouseenter = () => showPoolCard(name);
  });
}
function showPoolCard(name) {
  const p = POOL[name]; const src = faceUrl(name);
  $('p-detail').innerHTML = `<div class="dwrap"><div>${src ? `<img class="big" src="${src}" alt="">` : ''}</div><div><div class="dn">${esc(p.name)}</div>
    <div class="dm">${esc(p.code || '')} · ${esc(typeLine(p))}${p.type === '몬스터' ? ` · 공 ${esc(p.atk ?? 0)} / 수 ${esc(p.def ?? 0)}` : ''} · ${esc((p.tags || []).join(', '))}</div><div class="dx">${esc(p.text || '')}</div></div></div>`;
}
['p-q', 'p-theme', 'p-type', 'p-fit', 'p-strat'].forEach(id => $(id).addEventListener(id === 'p-q' ? 'input' : 'change', renderPool));
async function saveDeck(asNew) {
  const r = await api('deck/save', {deck: ED.deck, id: asNew ? null : ED.id});
  if (!r.ok) { $('d-msgs').innerHTML = r.errs.map(e => `<div class="err">✕ ${esc(e)}</div>`).join(''); return toast('덱 규칙 오류로 저장하지 못했습니다.'); }
  ED.id = r.id; ED.dirty = false; $('d-state').textContent = '저장했습니다.'; await refreshBoot(); toast('덱을 저장했습니다. AI 대전에서 고를 수 있습니다.');
}
$('d-save').onclick = () => saveDeck(false);
$('d-saveas').onclick = () => { const n = prompt('새 덱 이름', ED.deck['이름'] + ' 2'); if (!n) return; ED.deck['이름'] = n; saveDeck(true); };
$('d-delete').onclick = async () => { if (!ED.id || !confirm('이 덱을 지울까요?')) return; await api('deck/delete', {id: ED.id}); ED.dirty = false; newDeck(); await refreshBoot(); };
renderDeckList();

// ═══════════════ 학습 ═══════════════
async function refreshLearning() {
  const L = await api('learning'); const s = BOOT.settings;
  const rows = Object.entries(L.by_matchup || {}).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="n">${v.matches}</td><td class="n">${v.wins}</td><td class="n">${v.updates}</td></tr>`).join('');
  $('l-stats').innerHTML = `<div class="bigtxt">학습한 매치 <b>${L.matches}</b>개 · 판단 기록 <b>${L.updates}</b>개 · 파일 ${(L.size / 1024).toFixed(1)}KB<br><span class="muted">${esc(L.path)}</span></div>
    ${rows ? `<table class="t" style="margin-top:8px"><tr><th>대전(내 덱 vs AI 덱)</th><th>매치</th><th>내 승</th><th>판단 기록</th></tr>${rows}</table>` : '<div class="hint" style="margin-top:8px">아직 학습한 대전이 없습니다. AI 대전에서 「AI 학습」을 켜고 두어 보세요.</div>'}`;
  $('l-url').value = s.git_url || ''; $('l-base').value = s.git_base || ''; $('l-branch').value = s.git_branch || ''; $('l-auto').checked = !!s.auto_push;
  const lp = L.last_push; $('l-last').textContent = lp ? `마지막 자동 올리기(${lp.time}): ${lp.ok ? '성공' : '실패'} — ${lp.msg}` : '';
}
$('l-export').onclick = async () => { const r = await api('learning/export', {}); $('l-exported').textContent = r.ok ? '내보냄: ' + r.path : '아직 학습 기록이 없습니다.'; };
$('l-open').onclick = async () => { const r = await api('open', {what: 'export'}); if (!r.ok) toast('폴더를 열 수 없습니다.'); else toast('폴더: ' + r.path); };
$('l-savegit').onclick = async () => { BOOT.settings = await api('settings', {git_url: $('l-url').value.trim(), git_base: $('l-base').value.trim(), git_branch: $('l-branch').value.trim(), auto_push: $('l-auto').checked}); toast('저장했습니다.'); };
$('l-auto').onchange = async () => { BOOT.settings = await api('settings', {auto_push: $('l-auto').checked}); toast($('l-auto').checked ? '대전이 끝날 때마다 GitHub에 올립니다(인터넷 · git 필요).' : '자동 올리기를 껐습니다.'); };
$('l-git').onclick = async () => {
  $('l-gitlog').textContent = '올리는 중…(인터넷이 필요합니다)';
  await api('settings', {git_url: $('l-url').value.trim(), git_base: $('l-base').value.trim(), git_branch: $('l-branch').value.trim()});
  const r = await api('learning/git', {}); $('l-gitlog').textContent = r.msg + '\n\n' + (r.log || []).join('\n\n');
};
$('g-learn').onchange = () => api('settings', {learn: $('g-learn').checked}).catch(() => {});
// ── 신경망 학습 (머리 막대의 「🧠 신경망 학습」 — 홈 화면을 포함한 모든 화면에서 연다) ──
const NN = {st: BOOT.nn, timer: null};
const pct = v => v == null ? '–' : (v * 100).toFixed(1) + '%';
const num = v => v == null ? '–' : (+v).toFixed(3);
function nnAvail() { const o = $('g-aikind').querySelector('option[value=nn]'); o.disabled = !(NN.st && NN.st.available); if (o.disabled && $('g-aikind').value === 'nn') $('g-aikind').value = 'table'; }
function nnMetrics(t, title) {
  if (!t) return '';
  const row = (lab, a, b, f, tip) => `<tr title="${tip}"><td>${lab}</td><td class="n">${f(a)}</td><td class="n">${f(b)}</td></tr>`;
  const bf = t.before && (t.before.val || t.before.train), af = t.after && (t.after.val || t.after.train);
  if (!bf || !af) return '';
  return `<div class="muted" style="margin:6px 0 4px">${title} — ${t.after.val ? '검증 표본(학습에 쓰지 않은 매치)' : '학습 표본'} 기준</div>
    <table class="t"><tr><th></th><th class="n">학습 전(기본 모델)</th><th class="n">학습 후</th></tr>
    ${row('내 학습표와 최선 후보 일치', bf.teacher_agree, af.teacher_agree, pct, '로컬 학습표가 가장 높게 보는 후보를 신경망도 가장 높게 보는 비율')}
    ${row('내 학습표와의 차이(KL)', bf.kl_teacher, af.kl_teacher, num, '작을수록 내 학습표의 판단에 가까움')}
    ${row('기본 모델과의 차이(KL)', bf.kl_base, af.kl_base, num, '학습으로 기본 모델에서 얼마나 바뀌었는지')}
    ${row('이긴 라운드 선택의 로그 확률', bf.win_logp, af.win_logp, num, '클수록(0에 가까울수록) 이긴 라운드의 선택을 더 고름')}
    ${row('손실', bf.loss, af.loss, num, '학습 목표(작을수록 좋음)')}</table>`;
}
function nnRender() {
  const st = NN.st; if (!st) return;
  const sm = st.samples || {};
  const mu = Object.entries(sm.by_matchup || {}).sort((a, b) => b[1].samples - a[1].samples).slice(0, 6)
    .map(([k, v]) => `<div class="muted" style="font-size:12px">${esc(k)} · 매치 ${v.matches} · 판단 ${v.samples}</div>`).join('');
  $('nn-samples').innerHTML = `<div class="nnbig">${sm.samples || 0}<small>판단</small> ${sm.matches || 0}<small>매치</small></div>${mu}
    <div class="muted" style="font-size:12px;margin-top:6px">학습에는 최소 ${st.min_samples}개가 필요합니다. 학습표 기록(「학습」 화면)과 따로 쌓입니다.</div>`;
  const base = st.base, loc = st.local;
  const ev = base && base.eval ? Object.entries(base.eval).map(([k, v]) => `${k === 'table' ? '학습표 AI' : k === 'heuristic' ? '휴리스틱 AI' : k} 상대 ${v.win}% ±${v.ci95}`).join(' · ') : '';
  const npm = st.numpy || {};
  $('nn-model').innerHTML = npm.ok === null ? `<div class="muted">${esc(npm.msg || 'numpy 확인 중…')}</div>`
    : !npm.ok ? `<div class="err">이 컴퓨터에서 numpy를 불러올 수 없어 신경망 기능(표본 기록 · 신경망 AI · 학습)을 끕니다. 나머지 기능은 그대로 쓸 수 있습니다.</div><div class="muted" style="font-size:12px">${esc(npm.msg || '')}</div>`
    : !st.available ? '<div class="err">기본 신경망 모델이 없습니다(배포본을 확인하세요).</div>'
    : `<div class="nnbig">${st.using === 'local' ? '내 모델' : '기본 모델'}<small>대전에 쓰는 모델</small></div>
       ${loc ? `<div class="muted" style="font-size:12px">내 모델: ${esc(loc.created || '')} 학습 · 매치 ${loc.matches ?? '–'} · 판단 ${loc.samples ?? '–'}</div>` : '<div class="muted" style="font-size:12px">아직 내 모델이 없습니다 — 기본 모델로 대전합니다.</div>'}
       <div class="muted" style="font-size:12px">기본 모델: 학습표를 교사로 모방 학습 + 자기 대국${ev ? ` (단판 평가 ${ev})` : ''}</div>`;
  const j = st.job; const run = !!(j && j.status === 'running');
  $('nn-train').disabled = run || !st.available; $('nn-stop').disabled = !run; $('nn-reset').disabled = run || !loc;
  $('nn-bar').style.width = ((j ? j.progress : 0) * 100).toFixed(1) + '%';
  $('nn-msg').innerHTML = j ? `<span class="${j.status === 'error' ? 'err' : ''}">${esc(j.msg || '')}</span>` : '';
  $('nn-result').innerHTML = (j && j.log) ? nnMetrics(j.log, '방금 학습') : (loc && loc.after ? nnMetrics(loc, '내 모델') : '');
  nnAvail();
}
async function nnRefresh() {
  try { NN.st = await api('nn/status'); BOOT.nn = NN.st; } catch (e) { return; }
  nnRender();
  clearTimeout(NN.timer);
  if ((NN.st.job && NN.st.job.status === 'running') || (NN.st.numpy && NN.st.numpy.ok === null)) NN.timer = setTimeout(nnRefresh, 1000);
}
$('nn-open').onclick = () => { $('nn-modal').hidden = false; nnRefresh(); };
$('nn-close').onclick = () => { $('nn-modal').hidden = true; };
$('nn-modal').onclick = e => { if (e.target === $('nn-modal')) $('nn-modal').hidden = true; };
$('nn-train').onclick = async () => {
  try { await api('nn/train', {epochs: +$('nn-epochs').value}); } catch (e) { return toast(e.message, 6000); }
  nnRefresh();
};
$('nn-stop').onclick = async () => { await api('nn/stop', {}); nnRefresh(); };
$('nn-reset').onclick = async () => {
  if (!confirm('내 모델을 지우고 기본 모델로 되돌릴까요? (지운 모델은 폴더의 backups 에 남습니다)')) return;
  try { NN.st = await api('nn/reset', {}); BOOT.nn = NN.st; nnRender(); toast('기본 모델로 되돌렸습니다.'); } catch (e) { toast(e.message); }
};
$('nn-folder').onclick = async () => { const r = await api('open', {what: 'nn'}); toast(r.ok ? '폴더: ' + r.path : '폴더를 열 수 없습니다.'); };
$('nn-export').onclick = async () => {
  const r = await api('nn/export', {}).catch(e => ({ok: false, err: e.message}));
  $('nn-share').textContent = r.ok ? `내보냄: ${r.path}\nGitHub 웹에서 저장소의 nny_sim/learned/drl/human_nn/ 폴더에 이 파일을 올려 주세요.` : (r.err || '아직 신경망 표본이 없습니다.');
};
$('nn-git').onclick = async () => {
  $('nn-git').disabled = true; $('nn-share').textContent = 'GitHub에 올리는 중…';
  try { const r = await api('nn/git', {}); $('nn-share').textContent = r.msg + (r.ok ? '' : (r.log ? '\n' + r.log.slice(-2).join('\n').slice(-600) : '')); }
  catch (e) { $('nn-share').textContent = e.message; }
  finally { $('nn-git').disabled = false; }
};
$('nn-exdir').onclick = async () => { const r = await api('open', {what: 'export'}); toast(r.ok ? '폴더: ' + r.path : '폴더를 열 수 없습니다.'); };
nnAvail(); if (NN.st && NN.st.numpy && NN.st.numpy.ok === null) setTimeout(nnRefresh, 1500);   // numpy 확인이 끝나면 AI 종류 선택을 다시 정한다
$('g-hints').onchange = () => api('settings', {hints: $('g-hints').checked}).catch(() => {});
stages.watch.fit();
})();
