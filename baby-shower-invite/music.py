#!/usr/bin/env python3
"""
Soundtrack for the baby shower invitation.

A bright, celebratory setting of "Ah! vous dirai-je, maman" (the Twinkle
Twinkle Little Star melody, public domain), arranged in C major over a
I-V-vi-IV flavoured harmony at a walking 126 BPM.

Everything is synthesised from scratch, so nothing here is licensed:

  glockenspiel  struck bar, inharmonic partials, bright and short
  marimba       wooden bar, running eighth-note ostinato
  pluck         Karplus-Strong nylon string, chords on the beat
  bass          round sine with a little grit on the chord roots
  shaker        band-passed noise on the eighths
  clap          layered noise transients on beats two and four

The arrangement builds voice by voice across the six phrases so the film
lifts rather than sits still. Writes a 16-bit stereo WAV matched to the
length of the video.
"""
import math
import wave
import numpy as np

SR = 44100
DUR = 26.6
BPM = 126.0
BEAT = 60.0 / BPM          # 0.476 s
PHRASE = 8 * BEAT          # 3.81 s
START = 1.30               # the tune enters after a short curtain-raiser

rng = np.random.default_rng(913)
N = int(DUR * SR)
TAIL = SR * 3
left = np.zeros(N + TAIL)
right = np.zeros(N + TAIL)


def hz(name):
    """Scientific pitch name -> frequency."""
    steps = {'C': -9, 'D': -7, 'E': -5, 'F': -4, 'G': -2, 'A': 0, 'B': 2}
    letter = name[0]
    octv = int(name[-1])
    sharp = 1 if '#' in name else 0
    return 440.0 * 2 ** ((steps[letter] + sharp + (octv - 4) * 12) / 12.0)


def add(sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i < 0:
        sig, i = sig[-i:], 0
    j = min(i + len(sig), len(left))
    if j <= i:
        return
    seg = sig[: j - i] * gain
    left[i:j] += seg * math.sqrt((1.0 - pan) / 2.0)
    right[i:j] += seg * math.sqrt((1.0 + pan) / 2.0)


# ---------------------------------------------------------------------------
# instruments
# ---------------------------------------------------------------------------
def glock(freq, vel=1.0, damp=None):
    """Glockenspiel: a struck metal bar. Bright, bell-like, quick to fade."""
    length = 2.4 if damp is None else min(2.4, damp + 0.06)
    t = np.arange(int(length * SR)) / SR
    # partial ratios of a real struck bar are stretched, not harmonic
    partials = [(1.00, 1.00, 1.30), (2.76, 0.62, 0.85), (5.40, 0.34, 0.48),
                (8.93, 0.16, 0.28), (13.3, 0.07, 0.17)]
    out = np.zeros_like(t)
    for ratio, amp, decay in partials:
        f = freq * ratio
        if f > SR / 2.2:
            continue
        out += amp * np.exp(-t / decay) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    tick = int(0.008 * SR)
    out[:tick] += rng.normal(0, 1, tick) * np.exp(-np.linspace(0, 8, tick)) * 0.10
    out *= np.minimum(np.arange(len(t)) / (0.003 * SR), 1.0)
    if damp is not None:
        rel = int(0.05 * SR)
        i = min(len(out), int(damp * SR))
        if i > rel:
            out[i - rel:i] *= np.linspace(1, 0, rel) ** 1.3
        out[i:] = 0.0
    return out * (0.17 * vel)


def marimba(freq, vel=1.0):
    """Marimba: wooden bar, warm and short, for the running figure."""
    t = np.arange(int(0.55 * SR)) / SR
    partials = [(1.00, 1.00, 0.30), (3.93, 0.32, 0.13), (9.20, 0.10, 0.06)]
    out = np.zeros_like(t)
    for ratio, amp, decay in partials:
        f = freq * ratio
        if f > SR / 2.2:
            continue
        out += amp * np.exp(-t / decay) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    out *= np.minimum(np.arange(len(t)) / (0.004 * SR), 1.0)
    return out * (0.13 * vel)


def pluck(freq, dur=0.85, vel=1.0, bright=0.62):
    """
    Karplus-Strong nylon string.

    A burst of noise is fed into a delay line one period long with a gentle
    low-pass in the loop, which is what gives a plucked string its bright
    attack and its progressively duller decay. The loop is evaluated one
    period at a time rather than sample by sample, which keeps it fast.
    """
    D = max(2, int(round(SR / freq)))
    n = int(dur * SR)
    buf = np.zeros(n + 2 * D)
    exc = rng.uniform(-1, 1, D)
    # a duller excitation reads as a softer, more nylon-like pick
    for _ in range(int(6 * (1 - bright)) + 1):
        exc = (exc + np.roll(exc, 1)) * 0.5
    buf[D:2 * D] = exc
    a = 0.5 * 0.996                      # loop gain, just under unity
    k = 2 * D
    while k < len(buf):
        end = min(k + D, len(buf))
        m = end - k
        buf[k:end] = a * (buf[k - D:k - D + m] + buf[k - D - 1:k - D - 1 + m])
        k = end
    out = buf[D:D + n]
    out *= np.exp(-np.arange(n) / SR / (dur * 0.9))
    return out * (0.30 * vel)


def bass(freq, dur, vel=1.0):
    """Round bass: sine plus a touch of second harmonic for phone speakers."""
    t = np.arange(int((dur + 0.25) * SR)) / SR
    out = (np.sin(2 * np.pi * freq * t)
           + 0.30 * np.sin(2 * np.pi * freq * 2 * t)
           + 0.08 * np.sin(2 * np.pi * freq * 3 * t))
    env = np.exp(-t / (dur * 0.75))
    env *= np.minimum(np.arange(len(t)) / (0.006 * SR), 1.0)
    return out * env * (0.16 * vel)


def pad(freq, dur, vel=1.0):
    """A warm sustain under the arrangement — what keeps it from sounding
    like a toy. Two barely detuned sines plus a quiet octave, swelling in."""
    t = np.arange(int((dur + 0.7) * SR)) / SR
    v = (np.sin(2 * np.pi * freq * t)
         + 0.68 * np.sin(2 * np.pi * freq * 1.0018 * t + 1.1)
         + 0.22 * np.sin(2 * np.pi * freq * 2 * t + 0.4)
         + 0.09 * np.sin(2 * np.pi * freq * 3 * t + 2.2))
    env = np.ones_like(t)
    a = int(0.30 * SR)
    env[:a] = np.linspace(0, 1, a) ** 1.5
    r = int(0.65 * SR)
    env[-r:] *= np.linspace(1, 0, r) ** 1.3
    vib = 1.0 + 0.003 * np.sin(2 * np.pi * 4.6 * t)
    return v * env * vib * (0.030 * vel)


def triangle(vel=1.0):
    """A struck triangle on the downbeat: brighter and finer than a clap."""
    t = np.arange(int(1.1 * SR)) / SR
    out = np.zeros_like(t)
    for ratio, amp, dec in [(1.0, 1.0, 0.55), (2.41, 0.7, 0.42),
                            (4.17, 0.5, 0.30), (6.83, 0.3, 0.20)]:
        out += amp * np.exp(-t / dec) * np.sin(2 * np.pi * 3140 * ratio * t
                                               + rng.uniform(0, 6.28))
    out *= np.minimum(np.arange(len(t)) / (0.002 * SR), 1.0)
    return out * (0.030 * vel)


def shaker(vel=1.0):
    n = int(0.09 * SR)
    x = rng.normal(0, 1, n)
    # crude band-pass: difference twice for top end, then a short smooth
    x = np.diff(np.diff(np.concatenate([[0, 0], x])))
    # pull the very top off, or a shaker turns to hiss on a phone speaker
    x = np.convolve(x, np.ones(3) / 3.0, mode='same')
    x *= np.exp(-np.linspace(0, 16, len(x)))
    return x / (np.abs(x).max() + 1e-9) * (0.055 * vel)


def clap(vel=1.0):
    """Three quick noise transients, the way a real clap smears in a room."""
    n = int(0.30 * SR)
    out = np.zeros(n)
    for off, amp in [(0.000, 0.55), (0.011, 0.80), (0.023, 1.00)]:
        i = int(off * SR)
        burst = rng.normal(0, 1, n - i)
        burst = np.diff(np.concatenate([[0], burst]))
        burst *= np.exp(-np.linspace(0, 26, len(burst)))
        out[i:] += burst * amp
    out = np.convolve(out, np.ones(4) / 4.0, mode='same')
    return out / (np.abs(out).max() + 1e-9) * (0.085 * vel)


# ---------------------------------------------------------------------------
# the tune, and the harmony under it
# ---------------------------------------------------------------------------
T1 = ['C5', 'C5', 'G5', 'G5', 'A5', 'A5', 'G5*']
T2 = ['F5', 'F5', 'E5', 'E5', 'D5', 'D5', 'C5*']
T3 = ['G5', 'G5', 'F5', 'F5', 'E5', 'E5', 'D5*']
MELODY = [T1, T2, T3, T3, T1, T2]

# two beats per chord, four chords per phrase
CHORDS = [
    ['C', 'G', 'Am', 'F'],
    ['F', 'C', 'G', 'C'],
    ['C', 'F', 'C', 'G'],
    ['Am', 'F', 'C', 'G'],
    ['C', 'G', 'Am', 'F'],
    ['F', 'C', 'G', 'C'],
]
TRIAD = {'C': ['C', 'E', 'G'], 'G': ['G', 'B', 'D'],
         'Am': ['A', 'C', 'E'], 'F': ['F', 'A', 'C']}
ROOT = {'C': 'C3', 'G': 'G2', 'Am': 'A2', 'F': 'F2'}
SCALE = ['C', 'D', 'E', 'F', 'G', 'A', 'B']


def note_in(pitch, octave_hint=4):
    return pitch + str(octave_hint)


def third_above(name):
    """The note two scale steps up in C major — a bright, singable harmony."""
    letter, octv = name[0], int(name[-1])
    i = SCALE.index(letter) + 2
    return SCALE[i % 7] + str(octv + i // 7)


def chord_notes(ch, low_octave=3):
    """Voice a triad upward from the given octave."""
    out = []
    octv = low_octave
    prev = -1
    for p in TRIAD[ch]:
        i = SCALE.index(p)
        if i < prev:
            octv += 1
        prev = i
        out.append(p + str(octv))
    return out


# --------------------------------------------------------------------------
# lay the arrangement out phrase by phrase, adding a voice as it goes
# --------------------------------------------------------------------------
for pi, phrase in enumerate(MELODY):
    p0 = START + pi * PHRASE
    chords = CHORDS[pi]

    # ---- the tune, on glockenspiel -------------------------------------
    t = p0
    events = []
    for ni, note in enumerate(phrase):
        held = note.endswith('*')
        name = note.rstrip('*')
        beats = 2.0 if held else 1.0
        events.append((t, name, beats, ni))
        t += beats * BEAT
    for idx, (tt, name, beats, ni) in enumerate(events):
        # damp the tail when the same pitch is struck again, or the restrike
        # fights its own ringing predecessor and cancels instead of sounding
        damp = None
        for tt2, name2, _, _ in events[idx + 1:]:
            if name2 == name:
                damp = tt2 - tt
                break
        vel = 1.0 if ni % 2 == 0 else 0.90
        if beats == 2.0:
            vel = 1.08
        add(glock(hz(name), vel, damp), tt, pan=-0.10)
        # a third above joins for the last two phrases, to open the ending out
        if pi >= 4:
            add(glock(hz(third_above(name)), vel * 0.46, damp), tt, pan=0.26)

    # ---- marimba ostinato: four eighths per chord ----------------------
    for ci, ch in enumerate(chords):
        base = p0 + ci * 2 * BEAT
        voices = chord_notes(ch, 3)
        figure = [voices[0], voices[1], voices[2], voices[1]]
        for ei, nm in enumerate(figure):
            v = 0.95 if ei == 0 else 0.62
            add(marimba(hz(nm), v * (0.60 + 0.05 * pi)),
                base + ei * 0.5 * BEAT, pan=0.30 - 0.12 * ei)

    # ---- plucked chords, from phrase two onward ------------------------
    if pi >= 1:
        for ci, ch in enumerate(chords):
            base = p0 + ci * 2 * BEAT
            for beat_off, vel, spread in [(0.0, 1.0, 0.012), (1.5 * BEAT, 0.62, -0.010)]:
                for vi, nm in enumerate(chord_notes(ch, 3) + [chord_notes(ch, 4)[0]]):
                    add(pluck(hz(nm), 0.9, vel * (0.9 - 0.08 * vi)),
                        base + beat_off + vi * spread, pan=-0.34 + 0.17 * vi)

    # ---- bass, from phrase two onward ----------------------------------
    if pi >= 1:
        for ci, ch in enumerate(chords):
            base = p0 + ci * 2 * BEAT
            add(bass(hz(ROOT[ch]), 1.1, 1.0), base, pan=0.0)
            add(bass(hz(ROOT[ch]), 0.6, 0.55), base + 1.5 * BEAT, pan=0.0)

    # ---- shaker through the whole phrase -------------------------------
    for e in range(16):
        t_e = p0 + e * 0.5 * BEAT
        v = (1.0 if e % 2 == 0 else 0.55) * (0.38 + 0.07 * pi)
        add(shaker(v), t_e, pan=0.42 if e % 2 else -0.38)

    # ---- warm pad under the chords, from phrase three onward -----------
    if pi >= 2:
        for ci, ch in enumerate(chords):
            base = p0 + ci * 2 * BEAT
            for vi, nm in enumerate(chord_notes(ch, 3)):
                add(pad(hz(nm), 2 * BEAT, (1.0 - 0.10 * vi) * (0.7 + 0.1 * pi)),
                    base, pan=-0.40 + 0.40 * vi)

    # ---- a triangle marks the bar, from phrase three onward ------------
    if pi >= 2:
        for bar in range(2):
            add(triangle(0.75 + 0.06 * pi), p0 + bar * 4 * BEAT, pan=0.30)

    # ---- and only the last two phrases get hands ----------------------
    if pi >= 4:
        for bar in range(2):
            for b in (1, 3):
                add(clap(0.55), p0 + (bar * 4 + b) * BEAT, pan=0.0)

# ---- curtain-raiser: a rising marimba run into the first downbeat --------
for k, nm in enumerate(['C4', 'E4', 'G4', 'C5', 'E5']):
    add(marimba(hz(nm), 0.55 + 0.09 * k), START - (5 - k) * 0.5 * BEAT,
        pan=-0.3 + 0.15 * k)
for k in range(4):
    add(shaker(0.35), START - (4 - k) * 0.5 * BEAT, pan=0.3 if k % 2 else -0.3)

# ---- a sparkle where the confetti bursts (scene E, t = 22.0) -------------
for k, nm in enumerate(['C6', 'E6', 'G6', 'C7', 'E7']):
    add(glock(hz(nm), 0.70 - 0.07 * k), 22.00 + k * 0.085, pan=-0.34 + 0.17 * k)
add(triangle(1.35), 22.00, pan=0.0)
add(clap(0.6), 22.00, pan=0.0)

# ---- the last chord, left ringing ---------------------------------------
END = START + 6 * PHRASE                     # 24.16 s
for vi, nm in enumerate(['C3', 'E3', 'G3', 'C4', 'E4', 'G4', 'C5']):
    add(pluck(hz(nm), 2.2, 0.95 - 0.07 * vi), END + vi * 0.014, pan=-0.35 + 0.12 * vi)
add(bass(hz('C2'), 2.0, 0.9), END, pan=0.0)
add(glock(hz('C6'), 0.85), END + 0.02, pan=0.10)
add(glock(hz('E6'), 0.55), END + 0.10, pan=-0.18)
add(glock(hz('G6'), 0.45), END + 0.18, pan=0.24)


# ---------------------------------------------------------------------------
# a short, bright reverb, convolved with the FFT
# ---------------------------------------------------------------------------
def impulse(seconds=1.35, seed=7):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = r.normal(0, 1, n) * np.exp(-t * 4.4)
    pre = int(0.010 * SR)
    ir[:pre] *= np.linspace(0, 1, pre)
    k = np.exp(-np.linspace(0, 6, 40))     # shorter kernel keeps the tail bright
    k /= k.sum()
    ir = np.convolve(ir, k, mode='same')
    return ir / (np.abs(ir).sum() + 1e-12)


def convolve(sig, ir):
    n = 1 << (len(sig) + len(ir) - 1).bit_length()
    return np.fft.irfft(np.fft.rfft(sig, n) * np.fft.rfft(ir, n), n)[: len(sig)]


irL, irR = impulse(1.35, 7), impulse(1.35, 19)
WET = 0.22                                   # drier than a lullaby: keeps it perky
left = left + WET * convolve(left, irL)
right = right + WET * convolve(right, irR)
left, right = left[:N], right[:N]

# a gentle high shelf, for air
def lift(x, amount=0.14):
    hi = x - np.convolve(x, np.ones(9) / 9.0, mode='same')
    return x + amount * hi

left, right = lift(left), lift(right)

# ---------------------------------------------------------------------------
# fades and level
# ---------------------------------------------------------------------------
fi, fo = int(0.30 * SR), int(1.30 * SR)
env = np.ones(N)
env[:fi] = np.linspace(0, 1, fi) ** 1.3
env[-fo:] = np.linspace(1, 0, fo) ** 1.5
left *= env
right *= env

# soft-clip the peaks, then bring the whole thing back up to the ceiling, so
# the shaping buys loudness instead of quietly costing 2 dB of it
peak = max(np.abs(left).max(), np.abs(right).max())
left, right = left / peak, right / peak
drive = 1.4
left, right = np.tanh(left * drive), np.tanh(right * drive)
peak = max(np.abs(left).max(), np.abs(right).max())
gain = 10 ** (-1.0 / 20) / peak
left, right = left * gain, right * gain

stereo = np.empty(N * 2)
stereo[0::2] = left
stereo[1::2] = right
pcm = (np.clip(stereo, -1, 1) * 32767).astype('<i2')

with wave.open('out/music.wav', 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

both = np.concatenate([left, right])
rms = math.sqrt(float(np.mean(both ** 2)))
print('wrote out/music.wav  %.2fs  %.0f BPM  peak %.2f dBFS  rms %.1f dBFS'
      % (DUR, BPM, 20 * math.log10(float(np.abs(both).max())), 20 * math.log10(rms)))
print('tune ends at %.2fs, final chord rings to the fade' % END)
