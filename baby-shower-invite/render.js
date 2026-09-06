/*
 * Frame-accurate renderer for the baby shower invitation.
 *
 * The invite is animated entirely with CSS animations, so the whole thing can
 * be paused and seeked: for every frame we set `currentTime` on every running
 * animation and grab a screenshot. Frames are piped straight into ffmpeg, so
 * nothing large ever touches the disk.
 *
 * Frames are captured as quality-100 JPEG rather than PNG. Chromium's PNG
 * encoder costs ~1.3 s per 1080x1920 frame against ~0.26 s for JPEG, and since
 * the MP4 is yuv420p the 4:2:0 chroma subsampling dominates either way: measured
 * against a PNG reference, a PNG capture through 4:2:0 lands at 40.9 dB and a
 * JPEG q100 capture at 40.7 dB. The 0.2 dB buys a five-fold faster render.
 *
 *   node render.js                       -> renders the full MP4
 *   node render.js --theme blue-pink     -> the same, in another palette
 *   node render.js --preview             -> stills for review
 *   node render.js --poster 12.4         -> a single still at t = 12.4s
 *
 * Theme keys are the keys of THEMES in invite.html. Every output is suffixed
 * with the theme, so the palettes never overwrite one another.
 */
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const DIR = __dirname;
const OUT = path.join(DIR, 'out');
const FPS = 30;
const WIDTH = 1080;
const HEIGHT = 1920;
const FFMPEG = process.env.FFMPEG_BIN ||
  '/usr/local/lib/python3.11/dist-packages/imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2';

function argValue(flag, fallback) {
  const i = process.argv.indexOf(flag);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}
const THEME = argValue('--theme', 'ivory-sage');

async function openInvite(browser) {
  const page = await browser.newPage({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1,
  });
  await page.goto('file://' + path.join(DIR, 'invite.html') + '?theme=' + THEME);
  await page.waitForFunction('window.__ready === true', null, { timeout: 30000 });
  await page.evaluate(() => document.body.classList.add('seek'));
  await page.waitForTimeout(400); // let fonts/filters settle
  const applied = await page.evaluate(() => window.THEME);
  if (applied !== THEME) {
    throw new Error(`theme "${THEME}" is not defined in invite.html (page fell back to "${applied}")`);
  }
  console.log(`theme: ${THEME} (${await page.evaluate(() => window.THEME_LABEL)})`);
  return page;
}

async function seek(page, t) {
  await page.evaluate((ms) => {
    for (const a of document.getAnimations()) {
      a.pause();
      a.currentTime = ms;
    }
  }, t * 1000);
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ args: ['--force-color-profile=srgb', '--font-render-hinting=none'] });
  const page = await openInvite(browser);
  const total = await page.evaluate(() => window.TOTAL);

  const posterFlag = process.argv.indexOf('--poster');
  if (posterFlag > -1) {
    const t = parseFloat(process.argv[posterFlag + 1]);
    await seek(page, t);
    const name = `poster-${THEME}.png`;
    await page.screenshot({ path: path.join(OUT, name) });
    console.log(`${name} written at t=${t}`);
    await browser.close();
    return;
  }

  if (process.argv.includes('--preview')) {
    const marks = [1.6, 3.2, 7.4, 12.6, 14.4, 18.2, 20.6, 23.4, 25.6];
    for (const t of marks) {
      await seek(page, t);
      await page.screenshot({ path: path.join(OUT, `preview-${THEME}-${t.toFixed(1)}.png`) });
    }
    console.log('previews written for t =', marks.join(', '));
    await browser.close();
    return;
  }

  const frames = Math.round(total * FPS);
  const silent = path.join(OUT, `silent-${THEME}.mp4`);
  const ff = spawn(FFMPEG, [
    '-y', '-hide_banner', '-loglevel', 'error',
    '-f', 'image2pipe', '-framerate', String(FPS), '-i', 'pipe:0',
    '-an',
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '19',
    '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-level', '4.2',
    '-movflags', '+faststart',
    silent,
  ]);
  ff.stderr.on('data', (d) => process.stderr.write(d));

  const done = new Promise((res, rej) => {
    ff.on('close', (c) => (c === 0 ? res() : rej(new Error('ffmpeg exited ' + c))));
  });

  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    await seek(page, i / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality: 100 });
    if (!ff.stdin.write(buf)) {
      await new Promise((r) => ff.stdin.once('drain', r));
    }
    if (i % 60 === 0 || i === frames - 1) {
      const el = (Date.now() - t0) / 1000;
      console.log(
        `frame ${i + 1}/${frames}  t=${(i / FPS).toFixed(2)}s  elapsed=${el.toFixed(0)}s  ` +
        `eta=${(el / (i + 1) * (frames - i - 1)).toFixed(0)}s`
      );
    }
  }
  ff.stdin.end();
  await done;
  await browser.close();
  console.log('wrote ' + silent);
})().catch((e) => { console.error(e); process.exit(1); });
