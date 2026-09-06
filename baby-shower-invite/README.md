# Simran & Akshat — Baby Shower Invitation Video

An animated invitation film, rendered to a 1080 x 1920 (9:16) MP4 that is sized
for WhatsApp status, Instagram stories, and plain old sharing in a group chat.

## The film

| | |
|---|---|
| Duration | 26.6 s |
| Resolution | 1080 x 1920, 30 fps |
| Video | H.264 (high profile), `+faststart` |
| Audio | AAC 192 kbps stereo |

Five scenes, gender-neutral throughout since the baby's gender is a surprise:

1. **Twinkle, twinkle** — a gold star and the opening couplet.
2. **Pink or blue?** — two balloons and a question mark.
3. **The invitation** — a botanical wreath around *Baby Shower*, and the names.
4. **When & where** — the date lockup and the venue.
5. **Come shower them with love** — a confetti burst and the closing card.

The soundtrack is a music-box setting of *Ah! vous dirai-je, maman* — the
Twinkle Twinkle Little Star melody, which is public domain — over a soft sine
pad, synthesised from scratch in `music.py`. No licensed audio is used.

## Files

| File | What it is |
|---|---|
| `invite.html` | The invitation itself. Open it in a browser and it plays. |
| `fonts.css` | Parisienne, Cormorant Garamond and Quicksand, embedded as base64 so nothing loads from the network. |
| `render.js` | Frame-accurate renderer: pauses the document timeline, seeks each frame, pipes PNGs into ffmpeg. |
| `music.py` | Synthesises the soundtrack to `out/music.wav`. |
| `build.sh` | Runs the whole pipeline end to end. |
| `out/simran-akshat-baby-shower.mp4` | The finished film. |
| `out/poster.png` | A single still, for anywhere a static image is wanted. |

## Rebuilding

```bash
./build.sh
```

Everything is animated with CSS animations, which is what makes the render
deterministic: `render.js` pauses every animation on the page and sets
`currentTime` per frame, so the output is identical run to run and never
depends on how fast the machine happens to be.

Handy while editing:

```bash
node render.js --preview       # stills at nine points in the timeline
node render.js --poster 14.4   # one still at a chosen second
```

## Editing the details

All the wording lives in `invite.html`, in the five `<div class="scene">`
blocks. The scene timings are the `T` table in the script at the bottom of that
file; `window.TOTAL` is the length of the film and must cover the last scene.
