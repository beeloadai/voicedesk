import os
import json
import streamlit as st
import google.generativeai as genai
from gtts import gTTS
import io

# ---------------------------------------------------------
# 1. Configurazione Pagina & Interfaccia Streamlit
# ---------------------------------------------------------
st.set_page_config(
    page_title="VoiceDesk | Beeload",
    page_icon="🎙️",
    layout="centered"
)

st.title("🎙️ VoiceDesk — Agente Prenotazioni")
st.caption("Beeload AI R&D Lab — Assistente Vocale B2B")

# ---------------------------------------------------------
# 2. Gestione API Key (Streamlit Secrets / Environment)
# ---------------------------------------------------------
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("⚠️ Chiave API Gemini non trovata! Inseriscila nei Secrets di Streamlit Cloud.")
    st.stop()

# Inizializzazione Client Gemini con SDK ufficiale google-generativeai
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-1.5-flash")

# ---------------------------------------------------------
# 3. Gestione Persistence (bookings.json)
# ---------------------------------------------------------
BOOKINGS_FILE = "bookings.json"

def load_bookings():
    if os.path.exists(BOOKINGS_FILE):
        try:
            with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

# ---------------------------------------------------------
# 4. Inizializzazione Stato della Sessione
# ---------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Buongiorno! Sono VoiceDesk. Come posso aiutarla con la sua prenotazione oggi?"}
    ]

# ---------------------------------------------------------
# 5. Visualizzazione Storico Chat
# ---------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ---------------------------------------------------------
# 6. Input Utente e Elaborazione Gemini
# ---------------------------------------------------------
user_input = st.chat_input("Scrivi un messaggio o una richiesta di appuntamento...")

if user_input:
    # Mostra messaggio utente
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    system_instruction = """
    Sei VoiceDesk, un assistente virtuale B2B sviluppato da Beeload per la gestione delle prenotazioni.
    Il tuo obiettivo è aiutare i clienti a fissare un appuntamento in modo cortese, professionale e sintetico.
    Rispondi sempre in italiano in modo breve e chiaro, adatto ad essere ascoltato a voce.
    """

    with st.chat_message("assistant"):
        with st.spinner("VoiceDesk sta elaborando..."):
            try:
                prompt_completo = f"{system_instruction}\n\nUtente: {user_input}"
                response = model.generate_content(prompt_completo)
                risposta_testo = response.text
                st.write(risposta_testo)

                # Sintesi Vocale (gTTS)
                tts = gTTS(text=risposta_testo, lang="it")
                audio_bytes = io.BytesIO()
                tts.write_to_fp(audio_bytes)
                audio_bytes.seek(0)
                
                # Riproduttore Audio integrato
                st.audio(audio_bytes, format="audio/mp3", autoplay=True)

                st.session_state.messages.append({"role": "assistant", "content": risposta_testo})

            except Exception as e:
                st.error(f"Errore durante l'elaborazione: {e}")

# ---------------------------------------------------------
# 7. Sidebar — Gestione e Registro Prenotazioni
# ---------------------------------------------------------
with st.sidebar:
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata al momento.")
