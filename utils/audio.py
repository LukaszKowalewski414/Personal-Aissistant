import hashlib, io, subprocess, wave

def md5_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()

def wav_duration_seconds(wav_bytes: bytes) -> int:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        frames = w.getnframes()
        rate = w.getframerate()
        return int(frames / float(rate))

def guess_quality(duration_sec: int) -> str:
    return "low" if duration_sec>3600 else "med"  # placeholder; rozbuduj później

def ensure_ffmpeg():
    try:
        subprocess.run(["ffmpeg","-version"], check=True, capture_output=True)
        return True
    except Exception:
        return False
