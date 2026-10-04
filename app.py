import os
import json
import re
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

# Rilevamento dei modelli attivi
def get_available_groq_models():
    try:
        models = groq_client.models.list()
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

# 4. Inizializzazione Sessione Chat con Prompt Professionale e Naturale
SYSTEM_INSTRUCTION = """
Sei BeeVoice, la segretaria personale ed esecutiva di Beeload. Il tuo compito è accogliere i clienti e fissare appuntamenti di lavoro con cortesia, eleganza e naturalezza.

REGOLE TASSATIVE DI LINGUAGGIO E TONO:
1. Usa un italiano naturale, fluido e professionale. Evita assolutamente calchi sintattici dall'inglese (es. NON dire mai "comunicarci meglio", "cosa posso fare per te oggi", "dammi il tuo nome").
2. Dai del "Lei" all'interlocutore in modo cordiale ma formale.
3. Chiedi il nome in modo elegante (es. "Con chi ho il piacere di parlare?" oppure "Mi dica pure il suo nome").
4. Mantieni le risposte brevi e mirate (massimo 2 frasi), perfette per essere ascoltate a voce.
5. Non usare mai parentesi, note di regia o testo formattato in markdown. Rispondi solo con le parole esatte da pronunciare.
"""

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Come posso aiutarla?"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": INITIAL_GREETING}
    ]

if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "assistant", "content": INITIAL_GREETING}
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

# 6. Elaborazione Risposta + Pulizia Testo + Sintesi Vocale
if prompt_da_elaborare:
    if not available_models:
        st.error("Nessun modello di chat risulta accessibile con questa API Key di Groq.")
        st.stop()
        
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    st.session_state.chat_history.append({"role": "user", "content": prompt_da_elaborare})
    
    selected_model = available_models[0]
    
    with st.spinner("BeeVoice sta elaborando la risposta..."):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=st.session_state.chat_history,
                model=selected_model,
                temperature=0.3,  # Ridotta per risposte più precise e meno "creative"
                max_tokens=120
            )

            risposta_testo = chat_completion.choices[0].message.content.strip()
            
            # Rimuove eventuali parentesi residuali
            risposta_pulita = re.sub(r'\[.*?\]|\(.*?\)', '', risposta_testo).strip()
            if not risposta_pulita:
                risposta_pulita = risposta_testo

            st.session_state.chat_history.append({"role": "assistant", "content": risposta_pulita})

            # Sintesi vocale ElevenLabs
            audio_generator = eleven_client.text_to_speech.convert(
                text=risposta_pulita,
                voice_id="Xb7hH8MSUJpSbSDYk0k2",
                model_id="eleven_flash_v2_5"
            )
            
            audio_bytes_response = b"".join(audio_generator)

            st.session_state.messages.append({
                "role": "assistant", 
                "content": risposta_pulita,
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
