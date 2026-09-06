# Simran & Akshat — Baby Shower Invitation Video

An animated invitation film, rendered to a 1080 x 1920 (9:16) MP4 that is sized
for WhatsApp status, Instagram stories, and plain old sharing in a group chat.

## The film

| | |
|---|---|
| Duration | 29.6 s |
| Resolution | 1080 x 1920, 30 fps |
| Video | H.264 (high profile), `+faststart` |
| Audio | AAC 192 kbps stereo |

Six scenes, gender-neutral throughout since the baby's gender is a surprise:

1. **Twinkle, twinkle** — a gold sparkle and the opening couplet.
2. **Pink or blue?** — two balloons and a question mark.
3. **The invitation** — a botanical wreath around *Baby Shower*, and the names.
4. **The portrait** — Simran and Akshat standing in the scene, pushing in slowly.
5. **When & where** — the date lockup and the venue.
6. **Come celebrate with us** — a confetti burst and the closing card.

The length is deliberate. At 29.6 s the film posts as a single WhatsApp status
rather than being cut in two at the thirty-second mark, so the scenes are timed
against that ceiling rather than allowed to sprawl.

The portrait (`couple.png`) is a cutout with a real alpha channel, so Simran
and Akshat stand in the scene rather than sitting in a frame: feet on the
ground, a soft contact shadow so they are planted rather than floating, and —
on the meadow theme — a third layer of flowers drawn *above* the scenes so they
stand among the blooms instead of behind all of them.

It is tinted toward whichever look is running, with the tint masked to the
silhouette by the cutout itself so it cannot show up as a rectangle, and on the
dark theme it is brought down in brightness as well, since a bright photograph
on navy reads as a hole rather than a picture. Both are theme tokens
(`--photo-tint`, `--photo-filter`).

Three nested wrappers carry the figure: placement, entrance, and the slow
push-in. They cannot share one element, because each needs its own `transform`.
The push-in grows from `50% 100%`, so their feet stay planted as it scales.

### Voice

Simran and Akshat send this themselves, so every line is written in their
voice, not a third party's. It reads *join us for **our** baby shower* and
*come celebrate with **us***, and the names sit at the foot of the card as the
hosts' signature rather than as the subject of someone else's announcement.
This matters if the wording is ever edited: keep the first person.

### Soundtrack

A bright, celebratory setting of *Ah! vous dirai-je, maman* — the Twinkle
Twinkle Little Star melody, which is public domain — in C major at 126 BPM over
a I-V-vi-IV flavoured harmony, seven phrases long. Every instrument is
synthesised from scratch in `music.py`, so no licensed audio is used:

| Voice | How it is made |
|---|---|
| Glockenspiel | Struck metal bar: stretched, inharmonic partials. Carries the tune. |
| Marimba | Wooden bar, running eighth-note ostinato under the melody. |
| Plucked chords | Karplus-Strong nylon string. |
| Bass | Round sine with a little second harmonic, so it survives a phone speaker. |
| Triangle | Struck bar at 3.1 kHz, marking each bar. |
| Shaker and claps | Shaped noise transients. |

The arrangement adds a voice per phrase, so the film lifts about 3 dB from the
first phrase to the last instead of sitting still. The tune itself is six
phrases; the seventh is its last line said once more, which gives the film an
ending rather than a stop. The confetti burst is placed on a chord change
rather than near one, so the picture and the music land together.

## Themes

The film ships in seven looks. Six are pure palette swaps over the same
animation. The seventh, `meadow`, also brings its own decorative layer.

**Simran chose `meadow`, and it is the default** — `invite.html` and
`render.js` both fall back to it, so a plain `node render.js` renders the
chosen film. The rest are kept because they cost nothing to keep.

| Key | Look |
|---|---|
| `meadow` | **Chosen.** Watercolour Meadow. Warm cream and apricot over a mint field, a clothesline of baby clothes overhead, a wildflower meadow underfoot, butterflies, and pink and blue footprints in place of the question mark. No gold frame: the botanicals do that job. |
| `blue-pink` | Blue & Pink. Cool blue on one side, warm pink on the other, and a wreath that alternates blue-grey foliage with pink blossom. |
| `ivory-sage` | Ivory & Sage. Cream paper, green wreath, gold rule. |
| `blush-gold` | Blush & Gold. Warm rose and peach with champagne. |
| `powder-mint` | Powder & Mint. Fresh aqua and green. |
| `lilac-butter` | Lilac & Butter. Lavender with soft yellow. |
| `midnight-gold` | Midnight & Gold. Deep navy, ivory lettering, gold rule and a sky of stars. |

A theme is one entry in the `THEMES` table at the foot of `invite.html`: the
CSS custom properties for the palette, plus the colour sets the decorative
generators draw from (balloons, petals, confetti, stars, wreath). Nothing else
in the file hard-codes a colour, so a new palette is a new entry and nothing
more.

Two optional keys go further. `decor: 'meadow'` switches on the clothesline,
the wildflower meadow, the butterflies, the softer painted balloons and the
footprints; `frame: false` drops the gold rule for a theme whose own
botanicals frame the page. Everything they add is gated on those keys, so the
other six render exactly as they did before.

One trap worth knowing if you extend this: a CSS `transform` on an SVG element
overrides that element's `transform` attribute rather than composing with it.
Anything placed with an attribute and animated with CSS therefore needs two
nested groups — placement outside, motion inside. The wreath, the frame
corners, the hanging clothes and every stem in the meadow are all built that
way.

Preview one in a browser with `invite.html?theme=blue-pink`, or render it with
`./build.sh blue-pink`. A full run also writes `out/theme-comparison.jpg`,
which puts all six side by side for choosing between them.

## Files

| File | What it is |
|---|---|
| `invite.html` | The invitation itself. Open it in a browser and it plays. |
| `fonts.css` | Parisienne, Cormorant Garamond and Quicksand, embedded as base64 so nothing loads from the network. |
| `couple.png` | The portrait cutout used in scene four. Alpha channel required. |
| `render.js` | Frame-accurate renderer: pauses the document timeline, seeks each frame, pipes JPEG frames into ffmpeg. |
| `music.py` | Synthesises the soundtrack to `out/music.wav`. |
| `build.sh` | Runs the whole pipeline end to end. |
| `out/simran-akshat-baby-shower-<theme>.mp4` | The finished film, with the soundtrack. |
| `out/simran-akshat-baby-shower-<theme>-no-audio.mp4` | The same film with no audio track, for adding your own music. |
| `out/poster-<theme>.jpg` | A single still, for anywhere a static image is wanted. |

The silent version is not a separate render. Its audio is stripped from the
finished file with a stream copy, so the two share a bit-identical video
stream — the picture cannot drift between them.

## Rebuilding

```bash
./build.sh                # every theme
./build.sh blue-pink      # just one
```

Everything is animated with CSS animations, which is what makes the render
deterministic: `render.js` pauses every animation on the page and sets
`currentTime` per frame, so the output is identical run to run and never
depends on how fast the machine happens to be.

Handy while editing:

```bash
node render.js --preview       # stills across the timeline
node render.js --poster 12.5   # one still at a chosen second
```

## Editing the details

All the wording lives in `invite.html`, in the six `<div class="scene">`
blocks. The scene timings are the `T` table in the script at the bottom of that
file; `window.TOTAL` is the length of the film and must cover the last scene.
If you lengthen it, keep the total under 30 s or WhatsApp will split the status
in two, and remember that `music.py` is timed to the same number.
