"""Decode any audio file Windows can play (wma, m4a, mp3, wav...) to PCM with Media Foundation.

    python scripts/mf_decode.py <input> <output.wav>
"""
import ctypes
import struct
import sys
import uuid
from ctypes import POINTER, byref, c_uint32, c_uint64, c_void_p, c_int64, c_ulong

mf = ctypes.WinDLL("mfplat")
mfr = ctypes.WinDLL("mfreadwrite")
ole = ctypes.WinDLL("ole32")


def guid(s):
    return (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID(s).bytes_le)


MF_MT_MAJOR_TYPE = guid("48eba18e-f8c9-4687-bf11-0a74c9f96a8f")
MF_MT_SUBTYPE = guid("f7e34c9a-42e8-4714-b74b-cb29d72c35e5")
MF_MT_AUDIO_NUM_CHANNELS = guid("37e48bf5-645e-4c5b-89de-ada9e29b696a")
MF_MT_AUDIO_SAMPLES_PER_SECOND = guid("5faeeae7-0290-4c31-9e8a-c534f68d9dba")
MF_MT_AUDIO_BITS_PER_SAMPLE = guid("f2deb57f-40fa-4764-aa33-ed4f2d1ff669")
MFMediaType_Audio = guid("73647561-0000-0010-8000-00aa00389b71")
MFAudioFormat_PCM = guid("00000001-0000-0010-8000-00aa00389b71")
FIRST_AUDIO = 0xFFFFFFFD
END_OF_STREAM = 0x2


def call(obj, index, *args, argtypes=()):
    vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    fn = ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, *argtypes)(vtbl[index])
    return fn(obj, *args)


def release(obj):
    vtbl = ctypes.cast(obj, POINTER(POINTER(c_void_p))).contents
    ctypes.WINFUNCTYPE(c_ulong, c_void_p)(vtbl[2])(obj)


def decode(path):
    ole.CoInitializeEx(None, 0)
    mf.MFStartup(0x20070, 0)
    reader = c_void_p()
    mfr.MFCreateSourceReaderFromURL(ctypes.c_wchar_p(path), None, byref(reader))
    mt = c_void_p()
    mf.MFCreateMediaType(byref(mt))
    gp = POINTER(ctypes.c_byte * 16)
    call(mt, 24, byref(MF_MT_MAJOR_TYPE), byref(MFMediaType_Audio), argtypes=(gp, gp))  # SetGUID
    call(mt, 24, byref(MF_MT_SUBTYPE), byref(MFAudioFormat_PCM), argtypes=(gp, gp))
    call(reader, 7, FIRST_AUDIO, None, mt, argtypes=(c_uint32, c_void_p, c_void_p))  # SetCurrentMediaType
    release(mt)
    cur = c_void_p()
    call(reader, 6, FIRST_AUDIO, byref(cur), argtypes=(c_uint32, POINTER(c_void_p)))  # GetCurrentMediaType
    info = {}
    for key, g in (("ch", MF_MT_AUDIO_NUM_CHANNELS), ("rate", MF_MT_AUDIO_SAMPLES_PER_SECOND),
                   ("bits", MF_MT_AUDIO_BITS_PER_SAMPLE)):
        v = c_uint32()
        call(cur, 7, byref(g), byref(v), argtypes=(gp, POINTER(c_uint32)))  # GetUINT32
        info[key] = v.value
    release(cur)
    pcm = bytearray()
    while True:
        idx, flags, ts, sample = c_uint32(), c_uint32(), c_int64(), c_void_p()
        call(reader, 9, FIRST_AUDIO, 0, byref(idx), byref(flags), byref(ts), byref(sample),
             argtypes=(c_uint32, c_uint32, POINTER(c_uint32), POINTER(c_uint32), POINTER(c_int64), POINTER(c_void_p)))
        if sample:
            buf = c_void_p()
            call(sample, 41, byref(buf), argtypes=(POINTER(c_void_p),))  # ConvertToContiguousBuffer
            ptr, maxlen, curlen = c_void_p(), c_uint32(), c_uint32()
            call(buf, 3, byref(ptr), byref(maxlen), byref(curlen),
                 argtypes=(POINTER(c_void_p), POINTER(c_uint32), POINTER(c_uint32)))  # Lock
            pcm += ctypes.string_at(ptr, curlen.value)
            call(buf, 4)  # Unlock
            release(buf)
            release(sample)
        if flags.value & END_OF_STREAM:
            break
    release(reader)
    return info["ch"], info["rate"], info["bits"], bytes(pcm)


def wav_bytes(ch, rate, bits, pcm):
    align = ch * bits // 8
    return struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(pcm), b"WAVE", b"fmt ", 16, 1, ch, rate,
                       rate * align, align, bits, b"data", len(pcm)) + pcm


if __name__ == "__main__":
    ch, rate, bits, pcm = decode(sys.argv[1])
    open(sys.argv[2], "wb").write(wav_bytes(ch, rate, bits, pcm))
    print(f"{sys.argv[1]}: {ch}ch {rate}Hz {bits}bit {len(pcm) / (rate * ch * bits // 8):.2f}s")
