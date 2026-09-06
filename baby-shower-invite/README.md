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

1. **Twinkle, twinkle** — a gold sparkle and the opening couplet.
2. **Pink or blue?** — two balloons and a question mark.
3. **The invitation** — a botanical wreath around *Baby Shower*, and the names.
4. **When & where** — the date lockup and the venue.
5. **Come celebrate with us** — a confetti burst and the closing card.

### Voice

Simran and Akshat send this themselves, so every line is written in their
voice, not a third party's. It reads *join us for **our** baby shower* and
*come celebrate with **us***, and the names sit at the foot of the card as the
hosts' signature rather than as the subject of someone else's announcement.
This matters if the wording is ever edited: keep the first person.

The soundtrack is a bright, celebratory setting of *Ah! vous dirai-je, maman* —
the Twinkle Twinkle Little Star melody, which is public domain — in C major at
126 BPM over a I-V-vi-IV flavoured harmony. Every instrument is synthesised
from scratch in `music.py`, so no licensed audio is used:

| Voice | How it is made |
|---|---|
| Glockenspiel | Struck metal bar: stretched, inharmonic partials. Carries the tune. |
| Marimba | Wooden bar, running eighth-note ostinato under the melody. |
| Plucked chords | Karplus-Strong nylon string. |
| Bass | Round sine with a little second harmonic, so it survives a phone speaker. |
| Shaker and claps | Shaped noise transients. |

The arrangement adds a voice per phrase, so the film lifts about 3 dB from the
first phrase to the last instead of sitting still.

## Files

| File | What it is |
|---|---|
| `invite.html` | The invitation itself. Open it in a browser and it plays. |
| `fonts.css` | Parisienne, Cormorant Garamond and Quicksand, embedded as base64 so nothing loads from the network. |
| `render.js` | Frame-accurate renderer: pauses the document timeline, seeks each frame, pipes PNGs into ffmpeg. |
| `music.py` | Synthesises the soundtrack to `out/music.wav`. |
| `build.sh` | Runs the whole pipeline end to end. |
| `out/simran-akshat-baby-shower.mp4` | The finished film, with the soundtrack. |
| `out/simran-akshat-baby-shower-no-audio.mp4` | The same film with no audio track, for adding your own music. |
| `out/poster.png` | A single still, for anywhere a static image is wanted. |

The silent version is not a separate render. Its audio is stripped from the
finished file with a stream copy, so the two share a bit-identical video
stream — the picture cannot drift between them.

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
