import os
import json
import streamlit as st
import google.generativeai as genai
from elevenlabs.client import ElevenLabs
from streamlit_mic_recorder import mic_recorder

# 1. Configurazione Pagina Streamlit
st.set_page_config(
    page_title="VoiceDesk | Beeload",
    page_icon="🎙",
    layout="centered"
)

st.title("🎙 VoiceDesk — Agente Prenotazioni Vocale")
st.caption("Beeload AI R&D Lab — Assistente Vocale B2B")

# 2. Gestione e Validazione API Keys
gemini_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")
elevenlabs_key = st.secrets.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY")

if not gemini_key:
    st.error("⚠️ Chiave API Gemini non trovata! Inserisci GEMINI_API_KEY nei Secrets.")
    st.stop()

if not elevenlabs_key:
    st.error("⚠️ Chiave API ElevenLabs non trovata! Inserisci ELEVENLABS_API_KEY nei Secrets.")
    st.stop()

genai.configure(api_key=gemini_key.strip())
eleven_client = ElevenLabs(api_key=elevenlabs_key.strip())

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

# 4. Inizializzazione Sessione e Modello
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Buongiorno! Sono VoiceDesk di Beeload. Come posso aiutarla oggi?"}
    ]

SYSTEM_INSTRUCTION = """
Sei VoiceDesk, l'assistente vocale umano e professionale di Beeload per la gestione degli appuntamenti.
REGOLE DI CONVERSAZIONE:
1. Sii conciso, cortese e del tutto naturale (massimo 2-3 frasi per risposta).
2. Tieni conto dell'intera cronologia: non salutare di nuovo se vi siete già salutati, e NON richiedere informazioni che l'utente ti ha già fornito.
3. Se l'utente ti dà un'informazione (es. orario o nome), prendine atto e chiedi solo ciò che manca per completare la prenotazione.
"""

model = genai.GenerativeModel(
    model_name="gemini-3.8-flash",
    system_instruction=SYSTEM_INSTRUCTION
)

if "chat_session" not in st.session_state:
    st.session_state.chat_session = model.start_chat(history=[])

# Visualizzazione Storico Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# 5. Sezione Microfono e Input
st.write("---")
st.markdown("### 🗣️ Interagisci con VoiceDesk")

# Pulsante di registrazione vocale dedicato
audio_record = mic_recorder(
    start_prompt="🎙️ Clicca qui per Parlare",
    stop_prompt="⏹️ Clicca qui per Fermare e Inviare",
    key='mic_input',
    use_container_width=True
)

user_text_input = st.chat_input("Oppure scrivi un messaggio...")

prompt_da_elaborare = None

# Elaborazione Audio Registrato
if audio_record and isinstance(audio_record, dict) and 'bytes' in audio_record and audio_record['bytes']:
    audio_bytes_recorded = audio_record['bytes']
    
    # Evitiamo di ri-elaborare lo stesso audio al refresh
    if st.session_state.get("last_audio_bytes") != audio_bytes_recorded:
        st.session_state["last_audio_bytes"] = audio_bytes_recorded
        
        with st.spinner("🎧 Trascrizione dell'audio in corso..."):
            try:
                audio_part = {
                    "mime_type": "audio/wav",
                    "data": audio_bytes_recorded
                }
                transcription_response = model.generate_content([
                    "Trascrivi fedelmente questo messaggio vocale in italiano. Restituisci ESCLUSIVAMENTE il testo trascritto:", 
                    audio_part
                ])
                prompt_da_elaborare = transcription_response.text.strip()
            except Exception as e:
                st.error(f"Errore nella trascrizione audio: {e}")

elif user_text_input:
    prompt_da_elaborare = user_text_input

# 6. Risposta e Generazione Voce ElevenLabs
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    
    with st.spinner("VoiceDesk sta rispondendo..."):
        try:
            response = st.session_state.chat_session.send_message(prompt_da_elaborare)
            risposta_testo = response.text

            # Generazione Audio HD con ElevenLabs
            audio_generator = eleven_client.generate(
                text=risposta_testo,
                voice="JBFqnCBsd6RMkjVDRZzb",
                model="eleven_multilingual_v2"
            )
            
            audio_bytes_response = b"".join(audio_generator)

            st.session_state.messages.append({
                "role": "assistant", 
                "content": risposta_testo,
                "audio": audio_bytes_response
            })
            
            st.rerun()

        except Exception as e:
            st.error(f"Errore nell'elaborazione della risposta: {e}")

# 7. Sidebar — Registro Prenotazioni
with st.sidebar:
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata al momento.")
