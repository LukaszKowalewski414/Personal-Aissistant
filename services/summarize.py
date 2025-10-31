import os, json
import streamlit as st
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

def _get_api_key() -> str:
    key = (st.session_state.get("OPENAI_API_KEY_UI") or "").strip()
    if not key.startswith("sk-"):
        # komunikat pod ten właśnie przypadek
        raise RuntimeError("Wprowadź klucz OpenAI, aby przeprowadzić analizę rozmowy.")
    return key

_SYSTEM = (
    "Jesteś asystentem sprzedażowo-analitycznym. "
    "Na podstawie transkryptu rozmowy zwróć krótki, konkretny raport. "
    "Pisz po polsku. Odpowiedzi mają być rzeczowe, bez lania wody."
)


def summarize_meeting(transcript: str) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)

    prompt = f"""Przeanalizuj rozmowę i zwróć JSON o polach:

topic: krótki temat rozmowy (max 12 słów),
participants: lista imion/ról (np. ["Sprzedawca","Klient"]),
summary: 3–6 zdań streszczenia,
sales_score: liczba 0–100 (jakość rozmowy),
sales_comment: 1–3 zdania uzasadnienia oceny,
improve: lista 3–6 konkretnych rzeczy do poprawy,
reaction: co odpowiedzieć klientowi w follow-upie (2–5 zdań),
next_steps: lista obiektów {{"task": "...", "owner": "Sprzedawca/Klient", "due": "YYYY-MM-DD lub null"}},
ideas: lista krótkich pomysłów,
tags: lista 5–10 tagów do wyszukiwania (małe litery, bez #, jedno/dwuwyrazowe).

Zwróć **wyłącznie** poprawny JSON, bez komentarzy i bez markdownu.

TRANSKRYPT:
\"\"\"{transcript.strip()[:12000]}\"\"\""""
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
    )
    txt = resp.choices[0].message.content.strip()

    # awaryjne zdjęcie code-fence, gdyby model jednak je dodał
    def _strip_fence(s: str) -> str:
        if s.startswith("```"):
            # usuń trzy backticki + ewentualne 'json' w pierwszej linii
            s = s.split("\n", 1)[-1]
            if s.endswith("```"):
                s = s[:-3]
        return s

    clean = _strip_fence(txt)
    if not clean.strip().startswith("{"):
        import re
        m = re.search(r"\{.*\}", clean, flags=re.S)
        clean = m.group(0) if m else clean

    try:
        data = json.loads(clean)
    except Exception:
        # awaryjny szkielet – pokaż co przyszło w 'summary'
        data = {
            "topic": "",
            "participants": [],
            "summary": clean,
            "sales_score": 0,
            "sales_comment": "",
            "improve": [],
            "reaction": "",
            "next_steps": [],
            "ideas": [],
            "tags": [],
        }

    # --- sanity defaults + lekkie normalizacje (działa w obu ścieżkach) ---
    data.setdefault("topic", "Rozmowa")
    data.setdefault("participants", [])
    data.setdefault("summary", "")
    data.setdefault("sales_score", 0)
    data.setdefault("sales_comment", "")
    data.setdefault("improve", [])
    data.setdefault("reaction", "")
    data.setdefault("next_steps", [])
    data.setdefault("ideas", [])
    data.setdefault("tags", [])

    # normalizacja typów
    if isinstance(data["participants"], str):
        data["participants"] = [p.strip() for p in data["participants"].split(",") if p.strip()]
    if isinstance(data["improve"], str):
        data["improve"] = [x.strip() for x in data["improve"].split("\n") if x.strip()]
    if isinstance(data["ideas"], str):
        data["ideas"] = [x.strip() for x in data["ideas"].split("\n") if x.strip()]
    if isinstance(data["tags"], str):
        data["tags"] = [t.strip().lower() for t in data["tags"].split(",") if t.strip()]
    try:
        data["sales_score"] = int(data["sales_score"])
    except Exception:
        data["sales_score"] = 0

    return data

