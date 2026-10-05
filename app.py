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

# 3. Rilevamento / Fallback Automatico Modello Groq
PREFERRED_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.2-11b-vision-preview",
    "llama3-70b-8192",
    "mixtral-8x7b-32768"
]

def get_working_model():
    try:
        available_models = [m.id for m in groq_client.models.list().data]
        for model in PREFERRED_MODELS:
            if model in available_models:
                return model
        return available_models[0] if available_models else "llama-3.3-70b-versatile"
    except Exception:
        return "llama-3.3-70b-versatile"

ACTIVE_MODEL = get_working_model()

# 4. System Prompt per il Flusso Conversazionale
SYSTEM_INSTRUCTION = """
Sei BeeVoice, l'assistente vocale esecutiva di Beeload.
Il tuo obiettivo è organizzare un appuntamento raccogliendo:
1. Nome dell'interlocutore
2. Giorno
3. Orario
4. Motivo dell'incontro

REGOLE ESSENZIALI:
- Rispondi SEMPRE in italiano, dando del "Lei" e in modo estremamente professionale e naturale.
- Mantieni le risposte brevi (1-2 frasi) ideali per un assistente vocale.
- Consulta sempre la cronologia della conversazione ed evita di richiedere informazioni che l'utente ha già fornito.
- Non inserire formattazioni speciali, Markdown o testo tra parentesi.
"""

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Come posso esserle utile?"

# Inizializzazione Session State
if "chat_history" not in st.session_state:
    st.session_state.chat_history = [
        {"role": "system", "content": SYSTEM_INSTRUCTION},
        {"role": "assistant", "content": INITIAL_GREETING}
    ]

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": INITIAL_GREETING}
    ]

if "processed_audio_hash" not in st.session_state:
    st.session_state.processed_audio_hash = None

# 5. Visualizzazione Messaggi
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# 6. Registrazione Input Vocale e Testuale
st.write("---")
st.subheader("🗣️ Parla con BeeVoice")

audio_input_file = st.audio_input("Registra un messaggio vocale")
user_text_input = st.chat_input("Oppure scrivi un messaggio...")

prompt_da_elaborare = None

if audio_input_file is not None:
    audio_bytes = audio_input_file.read()
    current_hash = hash(audio_bytes)
    
    if st.session_state.processed_audio_hash != current_hash:
        st.session_state.processed_audio_hash = current_hash
        with st.spinner("🎧 Ascolto in corso..."):
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

# 7. Generazione della Risposta
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    st.session_state.chat_history.append({"role": "user", "content": prompt_da_elaborare})

    with st.spinner("BeeVoice sta rispondendo..."):
        try:
            completion = groq_client.chat.completions.create(
                messages=st.session_state.chat_history,
                model=ACTIVE_MODEL,
                temperature=0.3,
                max_tokens=100
            )

            risposta_testo = completion.choices[0].message.content.strip()
            
            # Pulizia caratteri speciali
            risposta_pulita = re.sub(r'\[.*?\]|\(.*?\)', '', risposta_testo).strip()
            risposta_pulita = risposta_pulita.replace("*", "").replace("#", "")

            st.session_state.chat_history.append({"role": "assistant", "content": risposta_pulita})

            # Sintesi Vocale ElevenLabs
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
            st.error(f"Errore nell'elaborazione: {e}")

# 8. Sidebar
with st.sidebar:
    st.header("⚙️ Modello Attivo")
    st.code(ACTIVE_MODEL)

    if st.button("🔄 Nuova Conversazione"):
        st.session_state.chat_history = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "assistant", "content": INITIAL_GREETING}
        ]
        st.session_state.messages = [{"role": "assistant", "content": INITIAL_GREETING}]
        st.session_state.processed_audio_hash = None
        st.rerun()
