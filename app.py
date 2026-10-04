import os
import json
import streamlit as st
from groq import Groq
from elevenlabs.client import ElevenLabs

# 1. Configurazione Pagina Streamlit
st.set_page_config(
    page_title="BeeVoice | Beeload",
    page_icon="🎙",
    layout="centered"
)

st.title("🎙 BeeVoice — Agente Prenotazioni Vocale")
st.caption("Beeload AI R&D Lab — Assistente Vocale B2B")

# 2. Gestione e Validazione API Keys
groq_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
elevenlabs_key = st.secrets.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY")

if not groq_key:
    st.error("⚠️ Chiave API Groq non trovata! Inserisci GROQ_API_KEY nei Secrets.")
    st.stop()

if not elevenlabs_key:
    st.error("⚠️ Chiave API ElevenLabs non trovata! Inserisci ELEVENLABS_API_KEY nei Secrets.")
    st.stop()

groq_client = Groq(api_key=groq_key.strip())
eleven_client = ElevenLabs(api_key=elevenlabs_key.strip())

# Selezione sicura del modello Llama attivo
@st.cache_resource
def get_working_groq_model():
    try:
        models = groq_client.models.list()
        model_ids = [m.id for m in models.data]
        # Cerchiamo solo modelli Llama o Gemma pubblici senza restrizioni di termini
        for m in model_ids:
            if "llama-3.3" in m or "llama-3.1" in m or "llama3" in m:
                if "vision" not in m and "guard" not in m:
                    return m
        return "llama-3.1-8b-instant"
    except Exception:
        return "llama-3.1-8b-instant"

# Selezioniamo direttamente un modello Llama di produzione
ACTIVE_MODEL = "llama-3.3-70b-versatile"

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

# 4. Inizializzazione Sessione Chat
SYSTEM_INSTRUCTION = """
Sei BeeVoice, l'assistente vocale umano e professionale di Beeload per la gestione degli appuntamenti.
REGOLE DI CONVERSAZIONE:
1. Rispondi SEMPRE in modo brevissimo, naturale e diretto (massimo 1 o 2 frasi concise).
2. Tieni conto dell'intera cronologia della conversazione: non salutare di nuovo se vi siete già salutati e NON richiedere informazioni già fornite dall'utente.
3. Se l'utente ti fornisce un'informazione (es. orario o nome), confermala e chiedi solo il dato mancante per completare la prenotazione.
"""

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Buongiorno! Sono BeeVoice di Beeload. Come posso aiutarla oggi?"}
    ]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "assistant", "content": "Buongiorno! Sono BeeVoice di Beeload. Come posso aiutarla oggi?"}
    ]

# Visualizzazione Storico Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# 5. Registratore Vocale Nativo
st.write("---")
st.subheader("🗣️ Parla con BeeVoice")

audio_input_file = st.audio_input("Registra un messaggio vocale")
user_text_input = st.chat_input("Oppure scrivi un messaggio...")

prompt_da_elaborare = None

# Gestione Audio con Groq Whisper
if audio_input_file is not None:
    audio_bytes = audio_input_file.read()
    
    if st.session_state.get("last_audio_bytes") != audio_bytes:
        st.session_state["last_audio_bytes"] = audio_bytes
        
        with st.spinner("🎧 Trascrizione in corso con Groq..."):
            try:
                transcription = groq_client.audio.transcriptions.create(
                    file=("audio.wav", audio_bytes),
                    model="whisper-large-v3",
                    language="it",
                    response_format="json"
                )
                prompt_da_elaborare = transcription.text.strip()
            except Exception as e:
                st.error(f"Errore trascrizione Groq: {e}")

elif user_text_input:
    prompt_da_elaborare = user_text_input

# 6. Elaborazione Risposta con Groq + Sintesi Vocale ElevenLabs
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    st.session_state.chat_history.append({"role": "user", "content": prompt_da_elaborare})
    
    with st.spinner("BeeVoice sta rispondendo..."):
        try:
            # Fallback dinamico se il modello principale fallisce
            try:
                model_to_use = ACTIVE_MODEL
                chat_completion = groq_client.chat.completions.create(
                    messages=st.session_state.chat_history,
                    model=model_to_use,
                    temperature=0.5,
                    max_tokens=150
                )
            except Exception:
                model_to_use = get_working_groq_model()
                chat_completion = groq_client.chat.completions.create(
                    messages=st.session_state.chat_history,
                    model=model_to_use,
                    temperature=0.5,
                    max_tokens=150
                )

            risposta_testo = chat_completion.choices[0].message.content.strip()
            st.session_state.chat_history.append({"role": "assistant", "content": risposta_testo})

            # Generazione audio HD con ElevenLabs (Voce Charlotte - Flash v2.5)
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
