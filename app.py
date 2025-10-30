import os, io, json, hashlib, tempfile
from datetime import datetime

import streamlit as st
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Table, ForeignKey, desc
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from audiorecorder import audiorecorder
from utils.audio import md5_bytes, wav_duration_seconds, guess_quality
from services.transcribe import transcribe_file
from services.summarize import summarize_meeting
from db import SessionLocal, Item, init_db

from pydub import AudioSegment
from pydub.utils import which

# -------------------------------------------------
# KONFIG + DB
# -------------------------------------------------
st.set_page_config(page_title="Personal AIssistant", page_icon="🗒️")
init_db(); db = SessionLocal()
st.title("Personal AIssistant")
# -------------------------------------------------
# PRZYCISK DO POBRANIA OPENAI_API_KEY
# -------------------------------------------------
with st.sidebar:
    ui_key = st.text_input("OPENAI_API_KEY", type="password", placeholder="sk-...")
    if ui_key:
        st.session_state["OPENAI_API_KEY_UI"] = ui_key.strip()
# -------------------------------------------------
# POPRAWKI WYGLĄDU
# -------------------------------------------------
# --- STYL PREMIUM ---
st.markdown("""
<style>
/* całe tło aplikacji */
.stApp {
    background: linear-gradient(180deg, #f8fafc 0%, #e8ecf8 100%);
}

/* główny kontener z zawartością */
.block-container {
    background-color: rgba(255, 255, 255, 0.9);
    border-radius: 18px;
    padding: 2.5rem 3rem;
    box-shadow: 0 8px 30px rgba(0,0,0,0.05);
    backdrop-filter: blur(6px);
}

/* karty/taby */
div[data-testid="stTabs"] > div[role="tablist"] {
    background-color: rgba(255,255,255,0.6);
    border-radius: 12px;
    padding: 0.4rem 0.8rem;
    margin-bottom: 1rem;
    box-shadow: inset 0 1px 3px rgba(0,0,0,0.05);
}

/* nagłówek */
h1 {
    font-weight: 700 !important;
    color: #1e293b !important;
    letter-spacing: -0.5px;
}

/* przyciski */
button[kind="primary"], div.stButton > button {
    background-color: #3b82f6;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 0.4rem 1.2rem;
    font-weight: 500;
    box-shadow: 0 3px 8px rgba(59,130,246,0.25);
    transition: all 0.2s ease-in-out;
}
button[kind="primary"]:hover, div.stButton > button:hover {
    background-color: #2563eb;
    transform: translateY(-1px);
}

/* audio player */
audio {
    filter: drop-shadow(0 1px 3px rgba(0,0,0,0.1));
}

/* expander (Meta) */
.streamlit-expanderHeader {
    font-weight: 500;
    color: #1e293b !important;
}

/* slider + form */
.css-1cpxqw2 {
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)
# --- DOSTOSOWANIE PRZYCISKU AUDIORECORDER ---
st.markdown("""
<style>
/* Naprawa wyglądu przycisku z audiorecorder */
button[title="Start"], button[title="Stop"] {
    background-color: #3b82f6 !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 0.4rem 1.2rem !important;
    font-weight: 500 !important;
    box-shadow: 0 3px 8px rgba(59,130,246,0.25) !important;
    transition: all 0.2s ease-in-out !important;
}
button[title="Start"]:hover, button[title="Stop"]:hover {
    background-color: #2563eb !important;
    transform: translateY(-1px);
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# STAN
# -------------------------------------------------
# cache: {'tx': {hash: text}, 'sum': {hash: data}}
st.session_state.setdefault("cache", {"tx": {}, "sum": {}})
st.session_state.setdefault("pending", None)     # {raw_bytes,tmp_path,duration_sec,file_hash}
st.session_state.setdefault("audio_hash", None)
st.session_state.setdefault("uploader_key", 0)
st.session_state.setdefault("transcript", None)
st.session_state.setdefault("meta", {})
st.session_state.setdefault("show_tx", False)    # czy pokazywać transkrypt w UI

def _md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()

def _set_pending(raw: bytes, name_hint: str):
    seg = AudioSegment.from_file(io.BytesIO(raw))
    duration_sec = int(seg.duration_seconds)
    _, ext = os.path.splitext(name_hint or "")
    with tempfile.NamedTemporaryFile(suffix=ext or ".wav", delete=False) as f:
        f.write(raw)
        tmp_path = f.name
    st.session_state["pending"] = {
        "raw_bytes": raw,
        "tmp_path": tmp_path,
        "duration_sec": duration_sec,
        "file_hash": _md5(raw),
    }
    st.session_state["audio_hash"] = st.session_state["pending"]["file_hash"]

# -------------------------------------------------
# NAWIGACJA: 3 karty
# -------------------------------------------------
tab_audio, tab_tx, tab_sum = st.tabs(["🎙️ Audio", "✍️ Transkrypcja", "🧠 Analiza"])

# =================================================
# 🎙️ AUDIO
# =================================================
with tab_audio:
    st.write("Nagraj lub wgraj plik, odsłuchaj i podejrzyj metadane.")

    col1, col2 = st.columns(2)
    with col1:
        st.caption("🎤 Nagraj")
        audio = audiorecorder("Start", "Stop")
    with col2:
        st.caption("📥 Wgraj plik")
        upl = st.file_uploader(
            "Plik audio", type=["mp3", "m4a", "wav"],
            key=f"upl_{st.session_state['uploader_key']}"
        )

    # --- LOGIKA „ostatni wygrywa” + antyduplikat ---
    if len(audio) > 0:
        buf = io.BytesIO(); audio.export(buf, format="wav")
        wav_bytes = buf.getvalue()
        h = _md5(wav_bytes)
        if h != st.session_state.get("audio_hash"):
            _set_pending(wav_bytes, "nagranie_mic.wav")

    if upl is not None:
        raw = upl.getvalue()
        h = _md5(raw)
        if h != st.session_state.get("audio_hash"):
            _set_pending(raw, upl.name)

    # --- Odtwarzacz + Meta ---
    p = st.session_state.get("pending")
    if p:
        st.audio(p["raw_bytes"])
        with st.expander("Meta", expanded=False):
            st.write(f"- Długość: **{p['duration_sec']}s**")
            st.write(f"- Plik tymczasowy: `{os.path.basename(p['tmp_path'])}`")
            st.write(f"- Hash: `{p['file_hash'][:10]}…`")

    # --- Wyczyść (bliżej audio) ---
    if st.button("🧹 Wyczyść audio i wyniki", help="Usuń aktualne audio i wyniki"):
        for k in ("pending", "audio_hash", "transcript", "meta", "summary_data"):
            st.session_state.pop(k, None)
        st.session_state["uploader_key"] += 1
        st.rerun()

# =================================================
# ✍️ TRANSKRYPCJA
# =================================================
with tab_tx:
    st.caption("Najpierw dodaj audio w zakładce *Audio*.")

    p = st.session_state.get("pending")
    h = p["file_hash"] if p else None

    col_tx = st.columns(2)[0]
    with col_tx:
        if st.button("Zrób transkrypcję"):
            if not p:
                st.warning("Najpierw nagraj lub wgraj plik audio.")
                st.stop()
            # cache po hash
            if h in st.session_state["cache"]["tx"]:
                text = st.session_state["cache"]["tx"][h]
                lang = (st.session_state.get("meta") or {}).get("language", "pl")
            else:
                with st.spinner("Transkrybuję..."):
                    text, info = transcribe_file(p["tmp_path"])
                st.session_state["cache"]["tx"][h] = text
                lang = info.get("language", "pl")

            st.session_state["transcript"] = text
            st.session_state["meta"] = {
                "duration_sec": p["duration_sec"],
                "file_hash": h,
                "language": lang,
            }
            st.session_state["show_tx"] = True
            st.rerun()

    # Wyświetl transkrypt tylko na żądanie
    if st.session_state.get("transcript") and st.session_state.get("show_tx"):
        st.success(f"Transkrypcja gotowa ✅ (język: {st.session_state['meta']['language']})")
        st.text_area("Podgląd transkryptu", st.session_state["transcript"], height=220, key="transcript_view")


# =================================================
# 🧠 ANALIZA
# =================================================
with tab_sum:
    st.caption("Szczegółowa analiza rozmowy sprzedażowej z sugestiami.")
    btn_summary = st.button("Zrób streszczenie")

    # --- jedyny wariant: transkrypcja w tle (jeśli brak) + analiza ---
    if btn_summary:
        p = st.session_state.get("pending")
        if not p:
            st.warning("Najpierw nagraj lub wgraj plik audio.")
            st.stop()
        h = p["file_hash"]

        # jeśli nie ma transkryptu – zrób po cichu
        if not st.session_state.get("transcript"):
            if h in st.session_state["cache"]["tx"]:
                text = st.session_state["cache"]["tx"][h]
                lang = (st.session_state.get("meta") or {}).get("language", "pl")
            else:
                with st.spinner("Transkrybuję..."):
                    text, info = transcribe_file(p["tmp_path"])
                st.session_state["cache"]["tx"][h] = text
                lang = info.get("language", "pl")

            st.session_state["transcript"] = text
            st.session_state["meta"] = {
                "duration_sec": p["duration_sec"],
                "file_hash": h,
                "language": lang,
            }
            st.session_state["show_tx"] = False  # nie pokazuj teraz

        # analiza (z cache)
        if h in st.session_state["cache"]["sum"]:
            data = st.session_state["cache"]["sum"][h]
        else:
            with st.spinner("Analizuję..."):
                data = summarize_meeting(st.session_state["transcript"])
            st.session_state["cache"]["sum"][h] = data

        st.session_state["summary_data"] = data
        st.toast("Streszczenie gotowe ✅")
        st.rerun()

    # --- Formularz edycji (gdy są dane) ---
    data = st.session_state.get("summary_data")
    if data:
        st.subheader("Streszczenie i akcje (edytowalne)")
        with st.form("summary_form"):
            topic        = st.text_input("Temat rozmowy", data.get("topic", ""))
            participants = st.text_input("Kto rozmawiał?", ", ".join(data.get("participants", [])))
            sales_score  = st.slider("Ocena jakości (0–100)", 0, 100, int(data.get("sales_score", 0)))
            summary      = st.text_area("Streszczenie (3–6 zdań)", data.get("summary", ""), height=140)
            improve      = st.text_area("Co można poprawić", "\n".join(data.get("improve", [])), height=100)
            reaction     = st.text_area("Co odpowiedzieć klientowi (follow-up)", data.get("reaction", ""), height=100)
            next_steps   = st.text_area("Akcje (po jednej w linii)", "\n".join([x.get("task", "") for x in data.get("next_steps", [])]), height=100)
            ideas        = st.text_area("Co jeszcze można zrobić", "\n".join(data.get("ideas", [])), height=80)
            tags         = st.text_input("Tagi do wyszukiwania (po przecinku)", ", ".join(data.get("tags", [])))

            if st.form_submit_button("Zapisz do bazy"):
                it = Item(
                    title=topic.strip() or "Rozmowa",
                    transcript=st.session_state.get("transcript", ""),
                    summary=summary,
                    language=st.session_state.get("meta", {}).get("language", "pl"),
                    sales_score=sales_score,
                    sales_comment=data.get("sales_comment", ""),
                    tags=tags,
                    happened_at=datetime.now(),
                    file_hash=st.session_state.get("meta", {}).get("file_hash"),
                )
                db.add(it); db.commit()
                st.success("Zapisano ✅")
