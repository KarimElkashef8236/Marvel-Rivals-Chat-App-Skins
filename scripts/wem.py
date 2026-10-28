"""Turn wav clips into Wwise PCM .wem files, same layout as the ones in the original mod."""
import hashlib
import struct

import numpy as np

RATE = 44100


def read_wav(path):
    b = open(path, "rb").read()
    off, fmt, data = 12, None, None
    while off + 8 <= len(b):
        tag, size = struct.unpack_from("<4sI", b, off)
        if tag == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", b, off + 8)
        elif tag == b"data":
            data = b[off + 8:off + 8 + size]
        off += 8 + size + (size & 1)
    tag, ch, rate, _, _, bits = fmt
    if bits != 16 or rate != RATE:
        raise ValueError(f"{path}: need 16 bit {RATE}Hz, got {bits} bit {rate}Hz")
    a = np.frombuffer(data[:len(data) // (2 * ch) * 2 * ch], dtype="<i2").astype(np.float64).reshape(-1, ch)
    return a if ch == 2 else np.repeat(a, 2, axis=1)


def process(a, start=None, end=None, rms_db=-16.0, fade=0.02):
    """cut, trim silence, fade and level a stereo float clip"""
    if start is not None or end is not None:
        a = a[int((start or 0) * RATE):int(end * RATE) if end else None]
    level = np.abs(a).max(axis=1)
    loud = np.nonzero(level > level.max() * 0.02)[0]
    a = a[max(loud[0] - int(0.005 * RATE), 0):min(loud[-1] + int(0.05 * RATE), len(a))].copy()
    n = min(int(fade * RATE), len(a))
    a[-n:] *= np.linspace(1, 0, n)[:, None]
    return set_level(a, rms_db)


def set_level(a, rms_db, peak_db=-1.0, limit_db=0.0):
    """scale so the audible part sits at rms_db, never peaking over peak_db. With limit_db the
    peaks can be held down by up to that many dB so short, spiky clips still get loud enough."""
    body = a[np.abs(a).max(axis=1) > np.abs(a).max() * 0.02]
    ceiling = 10 ** (peak_db / 20) * 32768
    gain = 10 ** (rms_db / 20) * 32768 / np.sqrt((body ** 2).mean())
    over = gain * np.abs(a).max() / ceiling
    if over <= 1:
        return a * gain
    if limit_db <= 0:
        return a * (ceiling / np.abs(a).max())
    gain /= max(over / 10 ** (limit_db / 20), 1.0)  # never limit harder than limit_db
    return limit(a * gain, ceiling)


def limit(a, ceiling, attack=0.002, release=0.08):
    """peak limiter: look ahead by attack, recover over release, output never above ceiling"""
    need = np.minimum(1.0, ceiling / np.maximum(np.abs(a).max(axis=1), 1e-9))
    n = max(1, int(attack * RATE))
    ahead = np.lib.stride_tricks.sliding_window_view(np.concatenate([need, np.ones(n)]), n + 1).min(1)[:len(need)]
    coef = np.exp(-1.0 / (release * RATE))
    g = np.empty_like(ahead)
    cur = 1.0
    for i, v in enumerate(ahead):
        cur = v if v < cur else coef * cur + (1 - coef) * v
        g[i] = cur
    out = a * g[:, None]
    return out * min(1.0, ceiling / np.abs(out).max())


def repitch(a, cents):
    """shift pitch (and length, like the game does) by cents, band limited so nothing aliases"""
    if not cents:
        return a
    n = len(a)
    m = int(round(n / 2 ** (cents / 1200)))
    spec = np.fft.rfft(a, axis=0)
    out = np.zeros((m // 2 + 1, a.shape[1]), dtype=complex)
    k = min(len(spec), len(out))
    out[:k] = spec[:k]
    return np.fft.irfft(out, n=m, axis=0) * (m / n)


def to_pcm(a):
    return np.clip(np.round(a), -32768, 32767).astype("<i2").tobytes()


def wav_bytes(a):
    pcm = to_pcm(a)
    return struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(pcm), b"WAVE", b"fmt ", 16, 1, 2, RATE,
                       RATE * 4, 4, 16, b"data", len(pcm)) + pcm


def wem_bytes(a):
    # fmt (WAVE_FORMAT_EXTENSIBLE, Wwise channel config 2ch/std/FL+FR), hash, junk, JUNK, data at 108
    pcm = to_pcm(a)
    fmt = struct.pack("<HHIIHHHHI", 0xFFFE, 2, RATE, RATE * 4, 4, 16, 6, 0, 0x3102)
    chunks = [(b"fmt ", fmt), (b"hash", hashlib.md5(pcm).digest()), (b"junk", bytes(12)), (b"JUNK", bytes(4)),
              (b"data", pcm)]
    body = b"WAVE" + b"".join(struct.pack("<4sI", t, len(p)) + p for t, p in chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body
