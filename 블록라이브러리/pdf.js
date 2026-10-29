// HTML → PDF (A4 — 페이지 크기는 HTML의 @page를 따른다): node pdf.js <절대경로.html> <출력.pdf>
const { chromium } = require('playwright');
(async () => {
  const [src, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + src, { waitUntil: 'networkidle' });
  await page.pdf({ path: out, preferCSSPageSize: true, printBackground: true });
  await browser.close();
})();
