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
function showOnline(list) {
  const el = $('online'); if (!el) return;
  el.textContent = '접속중 ' + list.length + '명'; el.title = list.map(c => c.name).join(', ');
}
showOnline(BOOT.online || []);

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
stages.watch = new Stage($('w-stage'), {assets, pool: POOL, onEnd: () => playlistNext(true),
  onMemo: (i, text, who, t) => {   // 저장된 기록을 보다가 단 메모는(이미 재생 기록 id 가 있으므로) 바로 저장
    if (!stages.watch.replayId) return;
    api('replay/memo', {id: stages.watch.replayId, memos: [{i, text, who, t}]}).catch(e => toast('메모 저장 실패: ' + e.message));
  }});
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
  return {t: r.title, s: `${r.source === 'library' ? '기본 제공' : r.kind === 'human' ? '내 대전' : '내 녹화'} · ${win}${score} · ${r.created || ''}`};
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
  stages.watch.replayId = id; stages.watch.viewerLabel = '복기';
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
  try { const j = await api('record', {pairs: [[$('r-a').value, $('r-b').value]], matches: +$('r-n').value || 1}); W.job = j.id; watchJob(); }
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
$('g-mode').onchange = () => {
  const mode = $('g-mode').value, human = mode !== 'ai';
  $('g-mylabel').textContent = mode === 'pvp' ? 'P1 덱(나)' : human ? '내 덱' : 'P1 덱';
  $('g-oplabel').textContent = mode === 'pvp' ? 'P2 덱(상대)' : mode === 'human' ? 'AI 덱' : 'P2 덱';
  $('g-learn').disabled = mode !== 'human'; $('g-hints').disabled = mode !== 'human';
};
const G = {id: null, pending: null, poll: null, busy: false, human: true, done: false, seat: null, key: null, spectating: false};
let lobbyRole = null, viaLobby = false;  // 로비(방) 참가 상태 — 매치 시작(로비) 로 시작했으면 상대가 매치 ID·키를 몰라도 스스로 들어온다
const decBox = () => $('g-stage').querySelector('.dec');
$('g-start').onclick = async () => {
  const auto = viaLobby; viaLobby = false;
  if (G.id && !G.done && !confirm('진행 중인 대전을 그만두고 새로 시작할까요?')) return;
  try {
    const mode = $('g-mode').value, humans = mode === 'pvp' ? [true, true] : mode === 'human' ? [true, false] : [false, false];
    const r = await api('match/start', {humans, deck: $('g-deck').value, ai_deck: $('g-ai').value, first: $('g-first').value,
                                        learn: $('g-learn').checked, hints: $('g-hints').checked});
    G.id = r.id; G.pending = null; G.done = false; G.human = humans[0] || humans[1]; G.spectating = false;
    G.seat = (0 in r.seats) ? 0 : null; G.key = G.seat != null ? r.seats[G.seat] : null;   // 사람 자리가 있으면 이 화면이 시작한 쪽은 항상 좌석0
    const lab = sel => sel.options[sel.selectedIndex].textContent.replace(/ — 규칙 오류$/, '');
    stages.play.ended = false;
    stages.play.viewerLabel = G.seat != null ? (r.names[G.seat] || '') : '';
    stages.play.startLive(r.names, {decks: [lab($('g-deck')), lab($('g-ai'))]}, G.seat);
    stages.play.fit(); decBox().innerHTML = ''; $('g-abort').disabled = false;
    $('g-status').textContent = `대전 중: ${r.title}` + (mode === 'human' && $('g-learn').checked ? ' · AI 학습 켜짐' : '');
    if (mode === 'pvp' && r.seats[1]) {
      $('g-pvpinfo').innerHTML = auto
        ? '로비 상대가 자동으로 들어옵니다(최대 20초 정도 걸릴 수 있습니다).'
        : `상대에게 매치 ID <code id="g-pvpid">${esc(r.id)}</code> 와 참가 키 <code id="g-pvpkey">${esc(r.seats[1])}</code> 를 알려 주세요(좌석1로 들어옵니다).`;
    } else { $('g-pvpinfo').textContent = ''; }
    clearTimeout(G.poll); pollLive();
  } catch (e) { toast(e.message, 6000); }
};
$('g-join').onclick = async () => {
  const id = $('g-join-id').value.trim(), key = $('g-join-key').value.trim();
  if (!id || !key) return toast('매치 ID와 참가 키를 입력하세요.');
  if (G.id && !G.done && !confirm('진행 중인 대전을 그만두고 참가할까요?')) return;
  try {
    const r = await api('match/join', {id, key});
    G.id = id; G.pending = null; G.done = false; G.human = true; G.seat = r.seat; G.key = r.key; G.spectating = false;
    stages.play.ended = false;
    stages.play.viewerLabel = r.names[G.seat] || '';
    stages.play.startLive(r.names, {decks: ['', '']}, G.seat);
    stages.play.fit(); decBox().innerHTML = ''; $('g-abort').disabled = false;
    $('g-pvpinfo').textContent = '';
    $('g-status').textContent = `참가함: ${r.title} · 내 좌석 ${r.seat}`;
    clearTimeout(G.poll); pollLive();
  } catch (e) { toast(e.message, 6000); }
};
$('g-abort').onclick = async () => { if (!confirm('대전을 그만둘까요? (끝낸 라운드까지는 기록 · 학습됩니다)')) return; await api('match/abort', {}); };

// ── 로비(방): 참가/관전/나가기 + 둘 다 모이면 자동 매치 연결 ──
function showRoom(r) {
  if (!r) return;
  $('lobby-list').textContent = r.members.length
    ? r.members.map(m => `${m.name}(${m.role === 'player' ? '참가' : '관전'})`).join(', ') : '방이 비었습니다.';
  $('lobby-start').disabled = !(lobbyRole === 'player' && r.players === 2);
}
function checkMyMatch(m) {
  if (!m || G.id === m.id) return;   // 이미 이 매치에 있으면(내가 시작한 쪽이거나 이미 들어온 뒤) 다시 건드리지 않음
  G.id = m.id; G.pending = null; G.done = false; G.human = true; G.seat = m.seat; G.key = m.key; G.spectating = false;
  stages.play.ended = false;
  stages.play.viewerLabel = m.names[G.seat] || '';
  stages.play.startLive(m.names, {decks: ['', '']}, G.seat);
  stages.play.fit(); decBox().innerHTML = ''; $('g-abort').disabled = false;
  $('g-pvpinfo').textContent = '';
  $('g-status').textContent = `참가함(로비): ${m.title} · 내 좌석 ${m.seat}`;
  clearTimeout(G.poll); pollLive();
}
function checkSpectate(li) {   // 관전(④): 로비에서 「관전」을 누른 뒤 매치가 떠 있으면(/api/boot·heartbeat 의 live_info) 양쪽 패를 가린 채 따라붙는다
  if (lobbyRole !== 'spectator' || !li || G.id === li.id) return;
  G.id = li.id; G.pending = null; G.done = false; G.human = false; G.seat = null; G.key = null; G.spectating = true;
  stages.play.ended = false;
  stages.play.viewerLabel = '관전';
  stages.play.startLive(li.names, {decks: ['', '']}, 'spectate');
  stages.play.fit(); decBox().innerHTML = ''; $('g-abort').disabled = true;
  $('g-pvpinfo').textContent = '';
  $('g-status').textContent = `관전 중: ${li.title}`;
  clearTimeout(G.poll); pollLive();
}
$('lobby-join').onclick = async () => {
  try { lobbyRole = 'player'; showRoom(await api('room/join', {name: $('lobby-name').value.trim(), role: 'player'})); }
  catch (e) { lobbyRole = null; toast(e.message); }
};
$('lobby-watch').onclick = async () => { lobbyRole = 'spectator'; showRoom(await api('room/join', {name: $('lobby-name').value.trim(), role: 'spectator'})); };
$('lobby-leave').onclick = async () => { lobbyRole = null; showRoom(await api('room/leave', {})); };
$('lobby-start').onclick = () => { viaLobby = true; $('g-mode').value = 'pvp'; $('g-mode').onchange(); $('g-start').click(); };
function beat() { api('heartbeat', {}).then(r => { showOnline(r.online || []); showRoom(r.room); checkMyMatch(r.my_match); checkSpectate(r.live_info); }).catch(() => {}); }
setInterval(beat, 20000); beat();
showRoom(BOOT.room); checkMyMatch(BOOT.my_match); checkSpectate(BOOT.live_info);

async function pollLive() {
  if (!G.id) return;
  const st = stages.play;
  try {
    let path = `match/poll?id=${G.id}&f=${st.F.length}&s=${st.S.length}&c=${Object.keys(st.cards).length}`;
    if (G.seat != null) path += `&seat=${G.seat}&key=${encodeURIComponent(G.key || '')}`;
    else if (G.spectating) path += '&spectate=1';
    const d = await api(path);
    if (d.status === 'none') return;
    st.appendLive(d);
    G.pending = d.pending;
    if (d.pending && st.caughtUp()) drawDecision();
    if (!d.pending && decBox().dataset.rid) { decBox().innerHTML = ''; delete decBox().dataset.rid; st.setHighlight([]); }
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
    + (d.replay_id ? ' · 재생 기록에 저장됨' : '') + (d.error ? `<pre class="err" style="white-space:pre-wrap">${esc(d.error)}</pre>` : '');
  const memos = st.memoList();   // 룰미스 메모(⑤) — 매치 중엔 클라이언트에만 쌓아 두고, 끝난 뒤 한 번에 재생 기록과 묶어 저장
  if (memos.length && d.replay_id) api('replay/memo', {id: d.replay_id, memos}).catch(e => toast('메모 저장 실패: ' + e.message));
  refreshBoot().catch(() => {});
}
// 판단 패널
const DEC_TITLE = [[/^진행 행동$/, '진행 단계 — 할 행동을 고르세요'], [/^정비 행동$/, '정비 단계 — 할 행동을 고르세요'], [/^우선권$/, '우선권 — 효과를 발동할까요?'],
  [/^대응$/, '체인 대응 — 응답할까요?'], [/^공격$/, '전투 — 공격할 몬스터와 대상'], [/^대상:(.+)$/, '대상 고르기 ($1)'], [/^트리거:(.+)#(\d+)$/, '「$1」 $2번 트리거 — 발동할까요?'],
  [/^멀리건:(.+)$/, '멀리건 — 「$1」을(를) 되돌릴까요?'], [/^드로우 덱/, '드로우할 덱'], [/^소환 표시 형식/, '소환 표시 형식'], [/^버릴 카드$/, '버릴 카드'], [/^서치:(.+)$/, '서치 — $1']];
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
  const opts = p.opts.map((o, i) => { const x = optText(o.label); const src = x.card && faceUrl(x.card);
    const eff = x.eff && x.card && POOL[x.card] ? effText(POOL[x.card], x.eff).split('\n')[0] : '';
    return `<button class="opt" data-i="${i}" data-card="${esc(x.card || '')}">${src ? `<img src="${src}" alt="">` : ''}<span class="t">${esc(x.t)}${x.s || eff ? `<small>${esc(x.s || '')}${eff ? ' — ' + esc(eff.replace(/^\d+\.\s*/, '')) : ''}</small>` : ''}</span>${o.v != null ? `<span class="v">${o.v}%</span>` : ''}</button>`; }).join('');
  box.innerHTML = `<div class="decision"><div class="q">${esc(decTitle(p.decision))}<small>${p.turn ? p.turn + '턴 · ' + esc(p.phase) : ''}</small></div><div class="opts">${opts}</div></div>`;
  box.querySelectorAll('.opt').forEach(b => {
    b.onmouseenter = () => { const c = b.dataset.card; if (c) { stages.play.showName(c); stages.play.setHighlight([c]); } };
    b.onmouseleave = () => stages.play.setHighlight([]);
    b.onclick = () => answerDec(p, box, +b.dataset.i);
  });
  stages.play.fit();
}
async function answerDec(p, box, i) {
  box.innerHTML = '<div class="decision wait"><div class="q">처리 중…</div></div>'; stages.play.setHighlight([]);
  try { await api('match/answer', {rid: p.id, idx: i, seat: G.seat, key: G.key}); } catch (e) { toast(e.message); }
  G.pending = null; delete box.dataset.rid; box.innerHTML = '';
}
// 라운드 사이 전략 덱 교체 — 서버가 보낸 할 수 있는 교체(opts)를 넣을 카드별로 묶어 보여 주고, 하나씩 고른다(고를 때마다 서버가 다시 계산)
function drawSide(p, box) {
  const cnt = Object.fromEntries(p.active), stc = Object.fromEntries(p.strategy);
  const btn = (o, i, t, s) => { const src = faceUrl(o.out); return `<button class="opt" data-i="${i}" data-card="${esc(o.out || '')}">${src ? `<img src="${src}" alt="">` : ''}<span class="t">${esc(t)}${s ? `<small>${esc(s)}</small>` : ''}</span></button>`; };
  const groups = {}; const order = [];
  p.opts.forEach((o, i) => { if (o.kind === 'card' || o.kind === 'skill') { const k = o.kind + ':' + o.in; if (!groups[k]) { groups[k] = []; order.push(k); } groups[k].push([o, i]); } });
  const grp = order.map(k => { const [o0] = groups[k][0]; const src = faceUrl(o0.in);
    const head = o0.kind === 'skill' ? `스킬 교체 → 「${o0.in}」` : `넣기: 「${o0.in}」`;
    const sub = o0.kind === 'skill' ? '' : `전략 덱 ${stc[o0.in] || 0}장 · 활성 덱 ${cnt[o0.in] || 0}장 · 뺄 카드 ${groups[k].length}종`;
    return `<details class="sw"><summary data-card="${esc(o0.in)}">${src ? `<img src="${src}" alt="">` : ''}<span class="t">${esc(head)}${sub ? `<small>${esc(sub)}</small>` : ''}</span></summary><div class="opts">`
      + groups[k].map(([o, i]) => btn(o, i, o.kind === 'skill' ? `「${o.out}」 대신 「${o.in}」` : `빼기: 「${o.out}」`, o.kind === 'skill' ? '' : `활성 덱 ${cnt[o.out] || 0}장`)).join('') + '</div></details>'; }).join('');
  const fixed = p.opts.map((o, i) => o.kind === 'done' || o.kind === 'reset' ? `<button class="opt ${o.kind}" data-i="${i}"><span class="t">${esc(o.label)}</span></button>` : '').join('');
  const done = p.swaps.length ? '바꾼 카드: ' + p.swaps.map(([a, b]) => `「${a}」 → 「${b}」`).join(', ') : '아직 바꾼 카드 없음';
  box.innerHTML = `<div class="decision side"><div class="q">${esc(p.decision)} — 승점 ${p.wins[0]}–${p.wins[1]}<small>내 스킬 「${esc(p.skill)}」 · 상대 스킬 「${esc(p.opp_skill)}」 · ${esc(done)}</small></div>`
    + (p.error ? `<div class="err">${esc(p.error)}</div>` : '') + `<div class="fixed">${fixed}</div>`
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
function allowed(name) {   // 덱 구축 기준: 스킬의 태그 또는 「공용」(deck.validate 와 같음)
  const sk = POOL[ED.deck['스킬']], c = POOL[name]; if (!sk || !c) return false;
  if (c.type === '스킬') return true;
  const tags = new Set([...(sk.skill_tags || []), ...(sk.no_common ? [] : ['공용'])]);
  return (c.tags || []).some(t => tags.has(t));
}
function countOf(sec, name) { const e = ED.deck[sec].find(x => x[1] === name); return e ? e[0] : 0; }
function totalIn(name) { return SECS.reduce((s, sec) => s + countOf(sec, name), 0); }
function addCard(name, toStrat) {
  const c = POOL[name]; if (!c) return;
  if (c.type === '스킬' && !toStrat) { ED.deck['스킬'] = name; ED.dirty = true; renderEditor(); return; }
  const sec = toStrat || c.type === '스킬' ? '전략' : (c.deck === '상급' ? '상급' : '메인');
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
  const list = Object.values(POOL).filter(p => (!th || p.theme === th) && (!ty || p.type === ty) && (!fit || allowed(p.name))
    && (!q || p.name.includes(q) || (p.text || '').includes(q))).sort((a, b) => (a.code || '').localeCompare(b.code || ''));
  $('p-grid').innerHTML = list.map(p => { const src = faceUrl(p.name); const n = totalIn(p.name) + (ED.deck['스킬'] === p.name ? 1 : 0);
    return `<div class="pc${allowed(p.name) ? '' : ' no'}" data-name="${esc(p.name)}" title="${esc(p.name)}">${src ? `<img src="${src}" alt="${esc(p.name)}" loading="lazy">` : esc(p.name)}${n ? `<span class="in">${n}</span>` : ''}</div>`; }).join('');
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
['p-q', 'p-theme', 'p-type', 'p-fit'].forEach(id => $(id).addEventListener(id === 'p-q' ? 'input' : 'change', renderPool));
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
  $('l-pushgames').checked = !!s.push_games;
  const gp = L.last_game_push; $('l-gamepush').textContent = gp ? `마지막 기보 수집(${gp.time}): ${gp.ok ? '성공' : '실패'} — ${gp.msg}` : '';
}
$('l-export').onclick = async () => { const r = await api('learning/export', {}); $('l-exported').textContent = r.ok ? '내보냄: ' + r.path : '아직 학습 기록이 없습니다.'; };
$('l-open').onclick = async () => { const r = await api('open', {what: 'export'}); if (!r.ok) toast('폴더를 열 수 없습니다.'); else toast('폴더: ' + r.path); };
$('l-savegit').onclick = async () => { BOOT.settings = await api('settings', {git_url: $('l-url').value.trim(), git_base: $('l-base').value.trim(), git_branch: $('l-branch').value.trim(), auto_push: $('l-auto').checked}); toast('저장했습니다.'); };
$('l-auto').onchange = async () => { BOOT.settings = await api('settings', {auto_push: $('l-auto').checked}); toast($('l-auto').checked ? '대전이 끝날 때마다 GitHub에 올립니다(인터넷 · git 필요).' : '자동 올리기를 껐습니다.'); };
$('l-pushgames').onchange = async () => { BOOT.settings = await api('settings', {push_games: $('l-pushgames').checked}); toast($('l-pushgames').checked ? '대전이 끝나거나 메모가 붙을 때마다 기보를 online/data-games 에 올립니다.' : '기보 자동 수집을 껐습니다.'); };
$('l-git').onclick = async () => {
  $('l-gitlog').textContent = '올리는 중…(인터넷이 필요합니다)';
  await api('settings', {git_url: $('l-url').value.trim(), git_base: $('l-base').value.trim(), git_branch: $('l-branch').value.trim()});
  const r = await api('learning/git', {}); $('l-gitlog').textContent = r.msg + '\n\n' + (r.log || []).join('\n\n');
};
$('g-learn').onchange = () => api('settings', {learn: $('g-learn').checked}).catch(() => {});
$('g-hints').onchange = () => api('settings', {hints: $('g-hints').checked}).catch(() => {});
stages.watch.fit();
})();
