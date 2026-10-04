import os
import json
import streamlit as st
import google.generativeai as genai
from elevenlabs.client import ElevenLabs

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

# 4. Inizializzazione Stato Sessione e Modello
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Buongiorno! Sono VoiceDesk di Beeload. Come posso aiutarla oggi?"}
    ]

SYSTEM_INSTRUCTION = """
Sei VoiceDesk, l'assistente vocale umano e professionale di Beeload per la gestione degli appuntamenti.
REGOLE DI CONVERSAZIONE:
1. Rispondi SEMPRE in modo brevissimo e diretto (massimo 1 o 2 frasi concise).
2. Tieni conto dell'intera cronologia: non salutare di nuovo se vi siete già salutati e NON richiedere informazioni che l'utente ti ha già fornito.
3. Se l'utente ti fornisce un'informazione (es. orario o nome), confermala subito e chiedi solo il dato mancante.
"""

# Utilizziamo gemini-2.5-flash per evitare i limiti di quota
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
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

# 5. Registratore Vocale Nativo
st.write("---")
st.subheader("🗣️ Parla con VoiceDesk")

audio_input_file = st.audio_input("Registra un messaggio vocale")
user_text_input = st.chat_input("Oppure scrivi un messaggio...")

prompt_da_elaborare = None

# Gestione audio registrato
if audio_input_file is not None:
    audio_bytes = audio_input_file.read()
    
    if st.session_state.get("last_audio_bytes") != audio_bytes:
        st.session_state["last_audio_bytes"] = audio_bytes
        
        with st.spinner("🎧 Ascolto in corso..."):
            try:
                mime_type = audio_input_file.type if hasattr(audio_input_file, 'type') and audio_input_file.type else "audio/wav"
                
                audio_part = {
                    "mime_type": mime_type,
                    "data": audio_bytes
                }
                transcription_response = model.generate_content([
                    "Trascrivi in italiano questo messaggio vocale. Restituisci SOLO il testo:", 
                    audio_part
                ])
                prompt_da_elaborare = transcription_response.text.strip()
            except Exception as e:
                st.error(f"Errore trascrizione: {e}")

elif user_text_input:
    prompt_da_elaborare = user_text_input

# 6. Risposta Gemini + Generazione Voce Femminile Ultra-Veloce
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    
    with st.spinner("VoiceDesk sta rispondendo..."):
        try:
            response = st.session_state.chat_session.send_message(prompt_da_elaborare)
            risposta_testo = response.text

            # Generazione audio con modello a bassa latenza e voce femminile (Charlotte)
            audio_generator = eleven_client.text_to_speech.convert(
                text=risposta_testo,
                voice_id="XB0fDUnXU5powFXDhCwa",
                model_id="eleven_flash_v2_5"
            )
            
            audio_bytes_response = b"".join(audio_generator)

            st.session_state.messages.append({
                "role": "assistant", 
                "content": risposta_testo,
                "audio": audio_bytes_response
            })
            
            st.rerun()

        except Exception as e:
            st.error(f"Errore elaborazione: {e}")

# 7. Sidebar — Registro Prenotazioni
with st.sidebar:
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata al momento.")
