import os
from faster_whisper import WhisperModel

_model = None

def get_model():
    global _model
    if _model is None:
        _model = WhisperModel(os.getenv("WHISPER_MODEL","small"),
                              device=os.getenv("USE_CUDA","0")=="1" and "cuda" or "cpu",
                              compute_type="int8")
    return _model

def transcribe_file(path: str):
    """Zwraca (text, info_dict: {language, avg_logprob})"""
    model = get_model()
    segs, info = model.transcribe(path, vad_filter=True, beam_size=5)
    text = " ".join(s.text.strip() for s in segs)
    return text, {"language": getattr(info, "language", None),
                  "avg_logprob": getattr(info, "avg_log_prob", None)}
