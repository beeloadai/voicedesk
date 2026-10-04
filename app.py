import os
import json
import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import io

# 1. Configurazione Pagina Streamlit
st.set_page_config(
    page_title="VoiceDesk | Beeload",
    page_icon="🎙️️",
    layout="centered"
)

st.title("🎙️ VoiceDesk — Agente Prenotazioni")
st.caption("Beeload AI R&D Lab — Assistente Vocale B2B")

# 2. Gestione e Validazione API Key
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("⚠️ Chiave API Gemini non trovata! Inserisci GEMINI_API_KEY nei Secrets di Streamlit.")
    st.stop()

genai.configure(api_key=api_key.strip())

# 3. Gestione Persistence (bookings.json)
BOOKINGS_FILE = "bookings.json"

def load_bookings():
    if os.path.exists(BOOKINGS_FILE):
        try:
            with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# 4. Inizializzazione Stato Sessione e Modello
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Buongiorno! Sono VoiceDesk di Beeload. Come posso aiutarla oggi?"}
    ]

# Configurazione Prompt di Sistema per tono naturale e non ripetitivo
SYSTEM_INSTRUCTION = """
Sei VoiceDesk, l'assistente vocale umano e professionale di Beeload per la gestione degli appuntamenti.
REGOLE DI CONVERSAZIONE:
1. Sii conciso, cortese e del tutto naturale (massimo 2-3 frasi per risposta).
2. Tieni conto dell'intera cronologia: non salutare di nuovo se vi siete già salutati, e NON richiedere informazioni che l'utente ti ha già fornito.
3. Se l'utente ti dà un'informazione (es. orario o nome), prendine atto e chiedi solo ciò che manca per completare la prenotazione.
"""

# Inizializza il modello Gemini
model = genai.GenerativeModel(
    model_name="gemini-3.8-flash",
    system_instruction=SYSTEM_INSTRUCTION
)

# Inizializza o recupera la sessione di chat Gemini
if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

# Visualizzazione Storico Chat
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# 5. Input Utente ed Elaborazione Gemini
user_input = st.chat_input("Scrivi un messaggio o una richiesta di appuntamento...")

if user_input:
    # Salva messaggio utente
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        with st.spinner("VoiceDesk sta elaborando..."):
            try:
                # Invia il messaggio mantenendo la memoria della conversazione
                response = st.session_state.chat_session.send_message(user_input)
                risposta_testo = response.text
                st.write(risposta_testo)

                # Generazione Audio gTTS
                tts = gTTS(text=risposta_testo, lang="it")
                audio_bytes = io.BytesIO()
                tts.write_to_fp(audio_bytes)
                audio_data = audio_bytes.getvalue()

                # Riproduci l'audio corrente
                st.audio(audio_data, format="audio/mp3", autoplay=True)

                # Salva nello storico sia il testo che l'audio
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": risposta_testo,
                    "audio": audio_data
                })

            except Exception as e:
                st.error(f"Errore durante l'elaborazione: {e}")

# 6. Sidebar — Registro Prenotazioni
with st.sidebar:
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata al momento.")
