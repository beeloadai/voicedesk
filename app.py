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

# 2. Gestione API Keys
groq_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
elevenlabs_key = st.secrets.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY")

if not groq_key or not elevenlabs_key:
    st.error("⚠️ Inserisci GROQ_API_KEY e ELEVENLABS_API_KEY nei Secrets di Streamlit.")
    st.stop()

groq_client = Groq(api_key=groq_key.strip())
eleven_client = ElevenLabs(api_key=elevenlabs_key.strip())

# Rilevamento REALE dei modelli attivi sulla TUA API key
def get_available_groq_models():
    try:
        models = groq_client.models.list()
        # Prendiamo solo modelli idonei alla chat (escludiamo whisper, guard, vision, etc.)
        valid_chat_models = [
            m.id for m in models.data 
            if not any(x in m.id.lower() for x in ["whisper", "guard", "vision", "orpheus", "canopylabs"])
        ]
        return valid_chat_models
    except Exception:
        return []

available_models = get_available_groq_models()

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

# 5. Registratore Vocale
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
        with st.spinner("🎧 Trascrizione in corso..."):
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

# 6. Elaborazione Risposta + Sintesi Vocale
if prompt_da_elaborare:
    if not available_models:
        st.error("Nessun modello di chat risulta accessibile con questa API Key di Groq.")
        st.stop()
        
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    st.session_state.chat_history.append({"role": "user", "content": prompt_da_elaborare})
    
    # Seleziona il primo modello funzionante estratto direttamente dalla tua API
    selected_model = available_models[0]
    
    with st.spinner(f"BeeVoice sta rispondendo con {selected_model}..."):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=st.session_state.chat_history,
                model=selected_model,
                temperature=0.5,
                max_tokens=150
            )

            risposta_testo = chat_completion.choices[0].message.content.strip()
            st.session_state.chat_history.append({"role": "assistant", "content": risposta_testo})

            # Sintesi vocale con voce predefinita standard
            audio_generator = eleven_client.text_to_speech.convert(
                text=risposta_testo,
                voice_id="JBFqnCBsd6RMkjVDRZzb",
                model_id="eleven_multilingual_v2"
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

# 7. Sidebar
with st.sidebar:
    st.header("⚙️ Modelli Rilevati")
    if available_models:
        st.success(f"Modelli attivi trovati: {len(available_models)}")
        st.caption(f"In uso: `{available_models[0]}`")
    else:
        st.warning("Nessun modello valido rilevato.")
        
    st.write("---")
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata.")
