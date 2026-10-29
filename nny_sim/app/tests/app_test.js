// 화면 자동 시험(Playwright): 관전 재생 · 덱 편집 · 나 vs AI 대전(무작위 클릭). 서버를 먼저 띄운다 — PORT=8765 node app_test.js [폭] [높이]
const { chromium } = require('playwright');
(async () => {
  const [W, H] = [+process.argv[2] || 1600, +process.argv[3] || 1000];
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: W, height: H } });
  const errs = []; p.on('pageerror', e => errs.push('pageerror: ' + e.message)); p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('http://127.0.0.1:' + (process.env.PORT||8765) + '/'); await p.waitForTimeout(1500);
  await p.click('#w-stage [data-a=play]'); await p.waitForTimeout(4000);
  await p.screenshot({ path: `win_watch_${W}.png` });
  // 덱 편집
  await p.click('header .tab[data-v=deck]'); await p.waitForTimeout(500);
  await p.click('#d-list .item:nth-child(8)'); await p.waitForTimeout(800);
  await p.screenshot({ path: `win_deck_${W}.png` });
  // AI 대전
  await p.click('header .tab[data-v=play]'); await p.waitForTimeout(300);
  await p.selectOption('#g-deck', 'o:투기장의 규칙'); await p.selectOption('#g-ai', 'o:던전마스터 셔플!');
  await p.selectOption('#g-first', 'me');
  await p.evaluate(() => { document.querySelector('#g-stage [data-a=speed]').value = '8'; document.querySelector('#g-stage [data-a=speed]').dispatchEvent(new Event('change')); });
  await p.click('#g-start');
  let shot = false, clicks = 0, sides = 0; const t0 = Date.now();
  while (Date.now() - t0 < 240000) {
    const st = await p.textContent('#g-status');
    if (st.includes('대전 끝')) break;
    const sw = await p.$$('#g-stage .decision.side details:not([open]) summary');   // 전략 덱 교체: 넣을 카드 하나를 펼친다
    if (sw.length && Math.random() < 0.6) { await sw[Math.floor(Math.random() * sw.length)].click(); sides++; }
    const opts = await p.$$('#g-stage .decision .opt:visible');
    if (opts.length) {
      if (!shot && clicks > 6) { await p.screenshot({ path: `win_play_${W}.png` }); shot = true; }
      const texts = await Promise.all(opts.map(o => o.textContent()));
      let i = Math.floor(Math.random() * opts.length);
      const end = texts.findIndex(t => t.includes('끝내기') || t.includes('교체 끝')); if (end >= 0 && Math.random() < 0.35) i = end;
      await opts[i].click(); clicks++;
    }
    await p.waitForTimeout(120);
  }
  await p.waitForTimeout(800);
  await p.screenshot({ path: `win_end_${W}.png` });
  const status = await p.textContent('#g-status');
  await p.click('header .tab[data-v=learn]'); await p.waitForTimeout(800);
  await p.screenshot({ path: `win_learn_${W}.png` });
  console.log(JSON.stringify({ clicks, sides, status, errs: errs.slice(0, 10) }));
  await b.close();
})();
