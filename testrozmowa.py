from openai import OpenAI
import wave
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

dialogue = """
Halo, tu firma SolarTech, chcemy Panu sprzedać panele słoneczne.
Eee… ja nic nie zamawiałem.
Ale to teraz się bardzo opłaca, rachunki za prąd są ogromne.
No tak, ale ja nie planowałem takiej inwestycji.
No ale jak wszyscy montują, to chyba Pan też by chciał?
Nie wiem, musiałbym się zastanowić.
Ale naprawdę warto, mamy promocję do końca tygodnia, jak Pan dziś się zdecyduje, to dostanie Pan rabat pięćset złotych.
Nie, ja nie podejmuję decyzji przez telefon.
To może chociaż zapiszę Pana dane i ktoś przyjedzie.
Wolałbym nie podawać nic, dziękuję.
No dobra, ale proszę pamiętać, że potem będzie drożej, bo materiały idą w górę.
Dobrze, do widzenia.
Aha, no, do widzenia.
"""

response = client.audio.speech.create(
    model="gpt-4o-mini-tts",
    voice="alloy",  # męski, naturalny ton
    input=dialogue,
    response_format="wav"
)

with open("rozmowa_sprzedazowa_dobra.wav", "wb") as f:
    f.write(response.read())

print("Plik zapisany jako rozmowa_sprzedazowa.wav ✅")
