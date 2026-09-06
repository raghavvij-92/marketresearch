#!/usr/bin/env python3
"""
Soundtrack for the baby shower invitation.

A music-box setting of "Ah! vous dirai-je, maman" (the Twinkle Twinkle Little
Star melody, public domain) over a soft sine pad, with a plate-style reverb
built from a synthetic impulse response. Writes a 16-bit stereo WAV matched to
the length of the video.
"""
import math
import wave
import numpy as np

SR = 44100
DUR = 26.6
BPM = 110.0
BEAT = 60.0 / BPM
LEAD_IN = 0.20

rng = np.random.default_rng(913)
N = int(DUR * SR)
left = np.zeros(N + SR * 3)
right = np.zeros(N + SR * 3)


def hz(name):
    """Scientific pitch name -> frequency."""
    steps = {'C': -9, 'D': -7, 'E': -5, 'F': -4, 'G': -2, 'A': 0, 'B': 2}
    letter, octv = name[0], int(name[-1])
    semis = steps[letter] + (1 if '#' in name else 0) + (octv - 4) * 12
    return 440.0 * 2 ** (semis / 12.0)


def add(buf_l, buf_r, sig, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i < 0:
        sig, i = sig[-i:], 0
    j = min(i + len(sig), len(buf_l))
    if j <= i:
        return
    seg = sig[: j - i] * gain
    buf_l[i:j] += seg * math.sqrt((1.0 - pan) / 2.0)
    buf_r[i:j] += seg * math.sqrt((1.0 + pan) / 2.0)


def music_box(freq, dur, vel=1.0, damp=None):
    """A struck metal tine: inharmonic partials, fast attack, long decay.

    `damp` cuts the tail short, the way a tine is stopped when the same note is
    struck again. Without it a repeated note interferes with its own ringing
    predecessor and the restrike can cancel rather than sound.
    """
    length = min(dur + 2.2, 3.6)
    if damp is not None:
        length = min(length, damp + 0.07)
    t = np.arange(int(length * SR)) / SR
    partials = [(1.00, 1.00, 1.75), (2.01, 0.42, 1.15), (3.03, 0.26, 0.80),
                (4.21, 0.14, 0.52), (5.45, 0.085, 0.36), (7.12, 0.045, 0.24)]
    out = np.zeros_like(t)
    for ratio, amp, decay in partials:
        f = freq * ratio
        if f > SR / 2.2:
            continue
        # a touch of random phase keeps repeated notes from sounding cloned
        out += amp * np.exp(-t / decay) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28))
    # the felt hammer
    click = rng.normal(0, 1, int(0.012 * SR)) * np.exp(-np.linspace(0, 9, int(0.012 * SR)))
    out[: len(click)] += click * 0.05
    attack = np.minimum(np.arange(len(t)) / (0.004 * SR), 1.0)
    out = out * attack
    if damp is not None:
        rel = int(0.06 * SR)
        i = min(len(out), int(damp * SR))
        if i > rel:
            out[i - rel:i] *= np.linspace(1, 0, rel) ** 1.4
        out[i:] = 0.0
    return out * (0.20 * vel)


def pad_note(freq, dur, vel=1.0):
    """Warm, breathy sustain — two slightly detuned sines plus an octave."""
    t = np.arange(int((dur + 0.9) * SR)) / SR
    v = (np.sin(2 * np.pi * freq * t)
         + 0.7 * np.sin(2 * np.pi * freq * 1.0015 * t + 1.1)
         + 0.28 * np.sin(2 * np.pi * freq * 2 * t + 0.4))
    # slow swell in, gentle release out
    env = np.ones_like(t)
    a = int(0.55 * SR)
    env[:a] = np.linspace(0, 1, a) ** 1.6
    r = int(0.9 * SR)
    env[-r:] *= np.linspace(1, 0, r) ** 1.4
    vib = 1.0 + 0.004 * np.sin(2 * np.pi * 4.3 * t)
    return v * env * vib * (0.035 * vel)


# --------------------------------------------------------------------------
# melody: six four-bar phrases of the tune, quarter notes with a half at the
# end of each phrase
# --------------------------------------------------------------------------
P1 = ['C5', 'C5', 'G5', 'G5', 'A5', 'A5', 'G5*']
P2 = ['F5', 'F5', 'E5', 'E5', 'D5', 'D5', 'C5*']
P3 = ['G5', 'G5', 'F5', 'F5', 'E5', 'E5', 'D5*']
PHRASES = [P1, P2, P3, P3, P1, P2]

# one chord per two beats, under each phrase
CHORDS = [
    ['C', 'C', 'F', 'C'], ['F', 'C', 'G', 'C'], ['C', 'G', 'C', 'G'],
    ['C', 'G', 'C', 'G'], ['C', 'C', 'F', 'C'], ['F', 'C', 'G', 'C'],
]
VOICING = {
    'C': ['C3', 'E3', 'G3', 'C4'],
    'F': ['F3', 'A3', 'C4', 'F4'],
    'G': ['G3', 'B3', 'D4', 'G4'],
}

schedule = []
t = LEAD_IN
phrase_starts = []
for pi, phrase in enumerate(PHRASES):
    phrase_starts.append(t)
    for ni, note in enumerate(phrase):
        held = note.endswith('*')
        name = note.rstrip('*')
        beats = 2.0 if held else 1.0
        # breathe: a touch softer on the answering note of each pair
        vel = 1.0 if ni % 2 == 0 else 0.92
        if held:
            vel = 1.05
        if pi >= 4:
            vel *= 0.92          # the reprise sits back a little
        pan = -0.28 + 0.56 * ((ni % 3) / 2.0)
        schedule.append({'t': t, 'name': name, 'beats': beats, 'vel': vel, 'pan': pan})
        t += beats * BEAT

for i, ev in enumerate(schedule):
    damp = None
    for nxt in schedule[i + 1:]:
        if nxt['name'] == ev['name']:
            damp = nxt['t'] - ev['t']
            break
    add(left, right,
        music_box(hz(ev['name']), ev['beats'] * BEAT, ev['vel'], damp),
        ev['t'], ev['pan'])

for pi, phrase_start in enumerate(phrase_starts):
    # the harmony underneath
    for ci, ch in enumerate(CHORDS[pi]):
        ct = phrase_start + ci * 2 * BEAT
        for vi, n in enumerate(VOICING[ch]):
            add(left, right, pad_note(hz(n), 2 * BEAT, 1.0 - 0.12 * vi),
                ct, pan=-0.45 + 0.30 * vi)

# a rising sparkle where the confetti bursts (scene E)
for k, n in enumerate(['C6', 'E6', 'G6', 'C7']):
    add(left, right, music_box(hz(n), 0.5, 0.62 - 0.06 * k),
        22.05 + k * 0.115, pan=-0.3 + 0.2 * k)

# a low bell to open, so the film does not start from nothing
add(left, right, music_box(hz('C3'), 2.0, 0.55), 0.05, pan=0.0)


# --------------------------------------------------------------------------
# reverb: exponentially decaying noise, convolved via FFT
# --------------------------------------------------------------------------
def impulse(seconds=2.1, seed=7):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    tt = np.arange(n) / SR
    ir = r.normal(0, 1, n) * np.exp(-tt * 3.1)
    ir[: int(0.012 * SR)] *= np.linspace(0, 1, int(0.012 * SR))  # pre-delay
    # roll the top end off so the tail stays soft
    k = np.exp(-np.linspace(0, 6, 96))
    k /= k.sum()
    ir = np.convolve(ir, k, mode='same')
    return ir / np.abs(ir).sum() * 1.0


def convolve(sig, ir):
    n = 1 << (len(sig) + len(ir) - 1).bit_length()
    out = np.fft.irfft(np.fft.rfft(sig, n) * np.fft.rfft(ir, n), n)
    return out[: len(sig)]


irL, irR = impulse(2.1, 7), impulse(2.1, 19)
wet = 0.34
left = left + wet * convolve(left, irL)
right = right + wet * convolve(right, irR)

left, right = left[:N], right[:N]

# --------------------------------------------------------------------------
# fades and level
# --------------------------------------------------------------------------
fi, fo = int(0.5 * SR), int(1.5 * SR)
env = np.ones(N)
env[:fi] = np.linspace(0, 1, fi) ** 1.5
env[-fo:] = np.linspace(1, 0, fo) ** 1.6
left *= env
right *= env

peak = max(np.abs(left).max(), np.abs(right).max())
gain = 10 ** (-1.5 / 20) / peak          # leave ~1.5 dB of headroom
left, right = left * gain, right * gain
left, right = np.tanh(left * 1.06) / 1.06, np.tanh(right * 1.06) / 1.06

stereo = np.empty(N * 2)
stereo[0::2] = left
stereo[1::2] = right
pcm = (np.clip(stereo, -1, 1) * 32767).astype('<i2')

with wave.open('out/music.wav', 'wb') as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

rms = math.sqrt(float(np.mean(np.concatenate([left, right]) ** 2)))
print('wrote out/music.wav  %.2fs  peak %.2f dBFS  rms %.1f dBFS'
      % (DUR, 20 * math.log10(peak * gain), 20 * math.log10(rms)))
