// Fills the IPISB course template (design lifted verbatim from the client-approved
// ipisb-template-project) with a real course's published chapters.
// Usage: node generate_course_deck.js <input.json> <output.pptx>
//
// Input JSON shape:
// {
//   course: { title, code, filiere, annee, totalHours, date },
//   chapters: [{
//     order, title, objectives, hoursTheory, hoursPractice,
//     sections: [{ heading, text }],
//     keyTakeaways: [{ title, detail }],   // up to 3
//     imageBase64: "data:image/png;base64,..." | null,
//   }]
// }
const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');
const JSZip = require('jszip');

const [, , inputPath, outputPath] = process.argv;
if (!inputPath || !outputPath) {
  console.error('Usage: node generate_course_deck.js <input.json> <output.pptx>');
  process.exit(1);
}
const data = JSON.parse(fs.readFileSync(inputPath, 'utf8'));

// ─── design tokens (unchanged from the approved template) ─────────────────
const C = {
  ink: '17301F', forest: '1F5D3A', forestDeep: '15422A', teal: '0E6E6D', tealDeep: '0A4E4D',
  gold: 'BB9A4E', goldLight: 'E8D9AF', sand: 'FBF9F5', sage: 'EAF2EC', mist: 'EEF5F3',
  line: 'DEE6DF', gray: '69766D', grayLight: 'A9B4AC', white: 'FFFFFF',
};
const F_DISPLAY = 'Century Gothic';
const F_BODY = 'Calibri';
const logoData = 'image/png;base64,' + fs.readFileSync(path.join(__dirname, 'ipisb_logo.png')).toString('base64');

const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';
const ST = pres._shapeType;

function shadow(opts = {}) {
  return Object.assign({ type: 'outer', color: '123322', blur: 9, offset: 3, angle: 90, opacity: 0.16 }, opts);
}
function logo(s, x, y, w) { s.addImage({ data: logoData, x, y, w, h: w }); }
function ringMotif(s, cx, cy, d, color = C.gold, weight = 1.5, transparency = 78) {
  s.addShape(ST.ellipse, { x: cx - d / 2, y: cy - d / 2, w: d, h: d, fill: { type: 'none' }, line: { color, width: weight, transparency } });
}
function dotAccent(s, x, y, d, color, transparency = 0) {
  s.addShape(ST.ellipse, { x, y, w: d, h: d, fill: { color, transparency }, line: { color, transparency } });
}
function eyebrow(s, x, y, w, text, color = C.gold, align = 'left') {
  s.addText(text.toUpperCase(), { x, y, w, h: 0.28, fontFace: F_BODY, fontSize: 9.5, bold: true, color, charSpacing: 2.2, align });
}
function footer(s, code, title, xStart = 0.55) {
  const w = 9.45 - xStart;
  s.addShape(ST.rect, { x: xStart, y: 5.26, w, h: 0.011, fill: { color: C.line }, line: { color: C.line } });
  s.addText([
    { text: 'IPISB', options: { color: C.forest, fontSize: 7, bold: true, fontFace: F_BODY } },
    { text: '   ·   El Jadida   ·   ', options: { color: C.grayLight, fontSize: 7, fontFace: F_BODY } },
    { text: code, options: { color: C.gray, fontSize: 7, fontFace: F_BODY } },
    { text: '   ·   ', options: { color: C.grayLight, fontSize: 7, fontFace: F_BODY } },
    { text: title, options: { color: C.gray, fontSize: 7, fontFace: F_BODY } },
  ], { x: xStart, y: 5.32, w: w - 0.6, h: 0.2, align: 'left', margin: 0 });
}
function pageNum(s, n) {
  s.addText(String(n).padStart(2, '0'), { x: 9.1, y: 5.28, w: 0.6, h: 0.28, fontFace: F_BODY, fontSize: 8.5, bold: true, color: C.forest, align: 'right' });
}
function badge(s, x, y, text, w = 1.9) {
  s.addShape(ST.roundRect, { x, y, w, h: 0.46, fill: { color: C.forest }, line: { color: C.forest }, rectRadius: 0.23, shadow: shadow({ opacity: 0.18, blur: 6 }) });
  const cd = 0.2, cx = x + 0.2, cy = y + 0.23 - cd / 2;
  s.addShape(ST.ellipse, { x: cx, y: cy, w: cd, h: cd, fill: { type: 'none' }, line: { color: C.goldLight, width: 1.25 } });
  s.addShape(ST.rect, { x: cx + cd / 2 - 0.006, y: cy + cd * 0.18, w: 0.012, h: cd * 0.32, fill: { color: C.goldLight }, line: { color: C.goldLight } });
  s.addShape(ST.rect, { x: cx + cd / 2, y: cy + cd / 2 - 0.006, w: cd * 0.26, h: 0.012, fill: { color: C.goldLight }, line: { color: C.goldLight } });
  s.addText(text, { x: x + 0.34, y, w: w - 0.34, h: 0.46, fontFace: F_BODY, fontSize: 10.5, bold: true, color: C.white, align: 'center', valign: 'middle', margin: 0 });
}
function imageFrame(s, x, y, w, h, label = 'Emplacement visuel') {
  s.addShape(ST.roundRect, { x, y, w, h, fill: { color: C.white }, line: { color: C.grayLight, width: 1.25, dashType: 'dash' }, rectRadius: 0.1 });
  const gw = Math.min(w, h) * 0.34, gh = gw * 0.62;
  const gx = x + w / 2 - gw / 2, gy = y + h / 2 - gh / 2 - 0.06;
  s.addShape(ST.roundRect, { x: gx, y: gy, w: gw, h: gh, fill: { type: 'none' }, line: { color: C.grayLight, width: 1.75 }, rectRadius: 0.03 });
  const ld = gh * 0.62;
  s.addShape(ST.ellipse, { x: gx + gw / 2 - ld / 2, y: gy + gh / 2 - ld / 2, w: ld, h: ld, fill: { type: 'none' }, line: { color: C.grayLight, width: 1.75 } });
  s.addShape(ST.rect, { x: gx + gw * 0.16, y: gy - gh * 0.16, w: gw * 0.22, h: gh * 0.18, fill: { color: C.white }, line: { color: C.grayLight, width: 1.75 } });
  s.addText(label, { x, y: gy + gh + 0.12, w, h: 0.24, fontFace: F_BODY, fontSize: 8.5, color: C.grayLight, align: 'center', italic: true });
}
function imageOrFrame(s, x, y, w, h, base64, label) {
  if (base64) {
    s.addImage({ data: base64, x, y, w, h, sizing: { type: 'cover', w, h } });
  } else {
    imageFrame(s, x, y, w, h, label);
  }
}
function card(s, x, y, w, h, accent = C.forest) {
  s.addShape(ST.roundRect, { x, y, w, h, fill: { color: C.white }, line: { color: C.line, width: 0.75 }, rectRadius: 0.08, shadow: shadow() });
  s.addShape(ST.roundRect, { x: x + 0.02, y, w: w - 0.04, h: 0.05, fill: { color: accent }, line: { color: accent }, rectRadius: 0.02 });
}
function truncate(str, max) {
  if (!str) return '';
  return str.length > max ? str.slice(0, max - 1).trimEnd() + '…' : str;
}
function background(s) { s.addShape(ST.rect, { x: 0, y: 0, w: 10, h: 5.625, fill: { color: C.sand }, line: { color: C.sand } }); }

const course = data.course;
const chapters = data.chapters;

// ── Cover ──
{
  const s = pres.addSlide();
  background(s);
  ringMotif(s, 9.7, 0.0, 3.6, C.gold, 1.5, 75);
  ringMotif(s, 9.55, -0.15, 2.3, C.forest, 1.25, 82);
  dotAccent(s, 8.62, 0.62, 0.11, C.gold, 15);
  logo(s, 0.55, 0.55, 1.05);
  s.addText("Institut Privé d'Innovation\nen Santé et Bien-Être", { x: 1.75, y: 0.62, w: 4.2, h: 0.6, fontFace: F_BODY, fontSize: 13, bold: true, color: C.forest, valign: 'middle', lineSpacingMultiple: 1.15 });
  s.addText('El Jadida', { x: 1.75, y: 1.16, w: 4.2, h: 0.22, fontFace: F_BODY, fontSize: 9, italic: true, color: C.grayLight });
  eyebrow(s, 0.55, 2.15, 4, 'Type de document', C.gold);
  s.addText('Manuel de cours', { x: 0.55, y: 2.4, w: 4.5, h: 0.34, fontFace: F_BODY, fontSize: 14, color: C.ink });
  s.addShape(ST.rect, { x: 0.55, y: 3.02, w: 0.45, h: 0.045, fill: { color: C.gold }, line: { color: C.gold } });
  s.addText(course.code || '', { x: 0.55, y: 3.14, w: 5.2, h: 0.32, fontFace: F_BODY, fontSize: 12, bold: true, color: C.teal, charSpacing: 1 });
  s.addText(course.title || '', { x: 0.53, y: 3.44, w: 5.5, h: 1.35, fontFace: F_DISPLAY, fontSize: 32, bold: true, color: C.forest, valign: 'top' });
  s.addShape(ST.rect, { x: 0, y: 5.02, w: 10, h: 0.605, fill: { color: C.forestDeep }, line: { color: C.forestDeep } });
  s.addText(course.annee || '', { x: 0.55, y: 5.02, w: 1.6, h: 0.605, fontFace: F_BODY, fontSize: 10.5, bold: true, color: C.white, valign: 'middle' });
  s.addShape(ST.rect, { x: 2.2, y: 5.14, w: 0.012, h: 0.38, fill: { color: C.goldLight, transparency: 40 }, line: { color: C.goldLight } });
  s.addText(`Filière : ${course.filiere || ''}`, { x: 2.4, y: 5.02, w: 3.6, h: 0.605, fontFace: F_BODY, fontSize: 10.5, color: C.white, valign: 'middle' });
  imageFrame(s, 6.15, 0.55, 3.3, 4.25, 'Emplacement visuel de couverture');
  s.addText(`Version : ${course.date || ''}`, { x: 6.9, y: 5.15, w: 1.7, h: 0.25, fontFace: F_BODY, fontSize: 7, color: C.grayLight });
}

// ── Sommaire ──
{
  const s = pres.addSlide();
  background(s);
  s.addShape(ST.rect, { x: 0, y: 0, w: 3.7, h: 5.625, fill: { color: C.forest }, line: { color: C.forest } });
  s.addShape(ST.rect, { x: 3.7, y: 0, w: 0.035, h: 5.625, fill: { color: C.gold }, line: { color: C.gold } });
  ringMotif(s, 3.9, 5.8, 2.6, C.gold, 1.25, 65);
  ringMotif(s, -0.5, -0.5, 2.2, C.white, 1, 80);
  logo(s, 0.4, 0.4, 0.75);
  eyebrow(s, 0.4, 1.35, 3, 'Plan du document', C.goldLight);
  s.addText('Sommaire', { x: 0.38, y: 1.58, w: 3.1, h: 0.6, fontFace: F_DISPLAY, fontSize: 26, bold: true, color: C.white });
  s.addText(truncate(course.title || '', 70), { x: 0.4, y: 4.5, w: 3.0, h: 0.75, fontFace: F_BODY, fontSize: 9.5, italic: true, color: C.goldLight, lineSpacingMultiple: 1.3 });

  const n = chapters.length;
  const rowH = Math.min(0.62, (5.2) / Math.max(n, 1));
  let yp = 0.4;
  chapters.forEach((c, i) => {
    s.addText(String(c.order).padStart(2, '0'), { x: 4.05, y: yp, w: 0.6, h: rowH, fontFace: F_DISPLAY, fontSize: Math.min(18, rowH * 26), bold: true, color: C.gold, valign: 'middle' });
    s.addText(truncate(c.title, 80), { x: 4.65, y: yp, w: 4.95, h: rowH, fontFace: F_BODY, fontSize: Math.min(12, rowH * 18), bold: true, color: C.ink, valign: 'middle' });
    yp += rowH;
    if (i < n - 1) s.addShape(ST.rect, { x: 4.05, y: yp - 0.02, w: 5.4, h: 0.011, fill: { color: C.line }, line: { color: C.line } });
  });
}

let slideNum = 1;

chapters.forEach((chapter) => {
  const chapImage = chapter.imageBase64 || null;

  // ── Chapitre intro (divider) ──
  {
    const s = pres.addSlide();
    background(s);
    s.addShape(ST.rect, { x: 0, y: 0, w: 4.15, h: 5.625, fill: { color: C.teal }, line: { color: C.teal } });
    s.addShape(ST.rect, { x: 4.15, y: 0, w: 0.035, h: 5.625, fill: { color: C.gold }, line: { color: C.gold } });
    ringMotif(s, -0.4, 5.9, 2.6, C.white, 1, 82);
    logo(s, 0.4, 0.4, 0.72);
    imageOrFrame(s, 0.4, 1.35, 3.35, 3.85, chapImage, 'Illustration de chapitre');
    eyebrow(s, 4.55, 0.62, 4, `Chapitre ${String(chapter.order).padStart(2, '0')}`, C.gold);
    s.addText(chapter.title, { x: 4.53, y: 0.88, w: 5, h: 0.85, fontFace: F_DISPLAY, fontSize: 21, bold: true, color: C.teal, valign: 'top' });
    s.addShape(ST.rect, { x: 4.55, y: 1.78, w: 0.55, h: 0.04, fill: { color: C.gold }, line: { color: C.gold } });
    s.addText('Ce que vous allez apprendre :', { x: 4.55, y: 2.02, w: 4.8, h: 0.3, fontFace: F_BODY, fontSize: 11, bold: true, color: C.forest });
    s.addText(chapter.objectives || '', { x: 4.55, y: 2.4, w: 4.8, h: 1.9, fontFace: F_BODY, fontSize: 10.5, color: C.ink, valign: 'top', lineSpacingMultiple: 1.3 });
    const hoursText = [chapter.hoursTheory ? `${chapter.hoursTheory}h théorie` : null, chapter.hoursPractice ? `${chapter.hoursPractice}h pratique` : null].filter(Boolean).join(' · ');
    if (hoursText) badge(s, 7.85, 4.53, hoursText, 1.8);
    footer(s, course.code, course.title, 4.35); pageNum(s, slideNum++);
  }

  // ── Content slides — one per section, left = text, right = image (first section only) or placeholder ──
  const sections = (chapter.sections || []).length ? chapter.sections : [{ heading: chapter.title, text: '' }];
  sections.forEach((section, si) => {
    const s = pres.addSlide();
    s.addShape(ST.rect, { x: 0, y: 0, w: 10, h: 5.625, fill: { color: C.white }, line: { color: C.white } });
    logo(s, 0.5, 0.32, 0.55);
    s.addText(`Chapitre ${String(chapter.order).padStart(2, '0')}  ·  ${truncate(chapter.title, 40)}`, { x: 1.2, y: 0.3, w: 8, h: 0.24, fontFace: F_BODY, fontSize: 8, color: C.grayLight, charSpacing: 0.5 });
    s.addText(truncate(section.heading, 60), { x: 1.18, y: 0.5, w: 8.2, h: 0.5, fontFace: F_DISPLAY, fontSize: 18, bold: true, color: C.forest });
    s.addShape(ST.rect, { x: 0.5, y: 1.06, w: 9, h: 0.03, fill: { color: C.gold }, line: { color: C.gold } });
    s.addShape(ST.rect, { x: 0.5, y: 1.09, w: 9, h: 0.011, fill: { color: C.line }, line: { color: C.line } });

    s.addShape(ST.roundRect, { x: 0.5, y: 1.32, w: 4.35, h: 3.78, fill: { color: C.sand }, line: { color: C.line, width: 0.75 }, rectRadius: 0.08, shadow: shadow({ opacity: 0.08 }) });
    s.addShape(ST.rect, { x: 0.5, y: 1.32, w: 0.045, h: 3.78, fill: { color: C.forest }, line: { color: C.forest } });
    eyebrow(s, 0.78, 1.5, 3.8, 'Notions clés', C.forest);
    s.addText(truncate(section.text, 900), { x: 0.78, y: 1.82, w: 3.85, h: 3.15, fontFace: F_BODY, fontSize: 10, color: C.ink, valign: 'top', lineSpacingMultiple: 1.3 });

    s.addShape(ST.roundRect, { x: 5.15, y: 1.32, w: 4.35, h: 3.78, fill: { color: C.sand }, line: { color: C.line, width: 0.75 }, rectRadius: 0.08, shadow: shadow({ opacity: 0.08 }) });
    s.addShape(ST.rect, { x: 5.15, y: 1.32, w: 0.045, h: 3.78, fill: { color: C.teal }, line: { color: C.teal } });
    eyebrow(s, 5.43, 1.5, 3.8, 'Exemple · Schéma', C.teal);
    if (si === 0 && chapImage) {
      imageOrFrame(s, 5.43, 1.82, 3.85, 3.1, chapImage, 'Exemple · Schéma');
    } else {
      s.addText("[Exemple pratique, schéma illustratif, tableau, figure, ou cas d'application — à compléter]", { x: 5.43, y: 1.82, w: 3.85, h: 3.15, fontFace: F_BODY, fontSize: 10.5, italic: true, color: C.grayLight, valign: 'top', lineSpacingMultiple: 1.35 });
    }
    footer(s, course.code, course.title); pageNum(s, slideNum++);
  });

  // ── À retenir ──
  if (chapter.keyTakeaways && chapter.keyTakeaways.length) {
    const s = pres.addSlide();
    background(s);
    ringMotif(s, 9.8, 5.9, 2.6, C.gold, 1.25, 78);
    logo(s, 0.55, 0.4, 0.62);
    eyebrow(s, 1.3, 0.44, 4, 'Synthèse', C.gold);
    s.addText('À retenir', { x: 1.28, y: 0.64, w: 6, h: 0.55, fontFace: F_DISPLAY, fontSize: 22, bold: true, color: C.forest });
    s.addShape(ST.rect, { x: 0.55, y: 1.3, w: 8.9, h: 0.013, fill: { color: C.line }, line: { color: C.line } });
    const pts = chapter.keyTakeaways.slice(0, 3);
    const cw = 8.9 / pts.length - 0.15;
    pts.forEach((p, i) => {
      const cx = 0.55 + i * (cw + 0.15);
      card(s, cx, 1.6, cw, 3.6, i === 1 ? C.gold : C.forest);
      s.addText(String(i + 1).padStart(2, '0'), { x: cx + 0.2, y: 1.82, w: 1.4, h: 0.6, fontFace: F_DISPLAY, fontSize: 30, bold: true, color: i === 1 ? C.gold : C.forest });
      s.addShape(ST.rect, { x: cx + 0.22, y: 2.5, w: 0.5, h: 0.03, fill: { color: C.line }, line: { color: C.line } });
      s.addText(truncate(p.title, 70), { x: cx + 0.2, y: 2.62, w: cw - 0.4, h: 0.6, fontFace: F_BODY, fontSize: 12, bold: true, color: C.ink });
      s.addText(truncate(p.detail, 220), { x: cx + 0.2, y: 3.25, w: cw - 0.4, h: 1.85, fontFace: F_BODY, fontSize: 9.5, color: C.gray, lineSpacingMultiple: 1.35 });
    });
    footer(s, course.code, course.title); pageNum(s, slideNum++);
  }
});

async function fixPhantomContentTypes(filePath) {
  const zip = await JSZip.loadAsync(fs.readFileSync(filePath));
  const ctFile = zip.file('[Content_Types].xml');
  if (!ctFile) return;
  let ct = await ctFile.async('string');
  const overrideRe = /<Override PartName="([^"]+)"[^>]*\/>/g;
  let match, removed = 0;
  const toRemove = [];
  while ((match = overrideRe.exec(ct))) {
    const zipKey = match[1].replace(/^\//, '');
    if (!zip.file(zipKey)) toRemove.push(match[0]);
  }
  toRemove.forEach(entry => { ct = ct.replace(entry, ''); removed++; });
  if (removed > 0) {
    zip.file('[Content_Types].xml', ct);
    fs.writeFileSync(filePath, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
  }
}

pres.writeFile({ fileName: outputPath })
  .then(() => fixPhantomContentTypes(outputPath))
  .then(() => console.log('OK', outputPath, slideNum - 1, 'slides'))
  .catch(e => { console.error(e); process.exit(1); });
