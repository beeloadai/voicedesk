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

# 3. Selezione Sicura del Modello Chat (Escludendo modelli non chat/terze parti)
def get_safe_chat_model():
    try:
        available_models = [m.id for m in groq_client.models.list().data]
        
        # Filtro restrittivo: solo modelli Meta Llama stabili per testo
        safe_list = [
            "llama-3.3-70b-versatile",
            "llama3-70b-8192",
            "llama-3.1-8b-instant"
        ]
        
        for m in safe_list:
            if m in available_models:
                return m
                
        # Se nessuno dei preferiti c'è, filtra la lista escludendo i modelli problematici
        filtered = [
            m for m in available_models 
            if not any(bad in m.lower() for bad in ["whisper", "guard", "vision", "orpheus", "canopylabs", "safetensors"])
        ]
        return filtered[0] if filtered else "llama-3.3-70b-versatile"
    except Exception:
        return "llama-3.3-70b-versatile"

ACTIVE_MODEL = get_safe_chat_model()

# 4. System Prompt Elegante e Naturale
SYSTEM_INSTRUCTION = """
Sei BeeVoice, la segretaria esecutiva di Beeload. Rispondi al telefono per conto dell'azienda in modo estremamente professionale, naturale, caldo e fluido.

OBIETTIVO:
Organizzare un appuntamento raccogliendo con garbo: Nome dell'interlocutore, Giorno, Orario e Motivo dell'incontro.

REGOLE TASSATIVE DI CONVERSAZIONE:
1. Dai SEMPRE e SOLO del "Lei".
2. Parla in italiano perfetto e spontaneo, come un'assistente di direzione reale.
3. Rispondi in modo conciso (massimo 1-2 frasi brevi per l'ascolto vocale).
4. Guarda sempre la cronologia della conversazione: NON ripetere mai domande a cui l'utente ha già risposto.
5. Quando l'utente ti fornisce un dato (es. il suo nome), accoglilo con cortesia e fai la domanda successiva in modo naturale.
6. DIVIETO ASSOLUTO di formule innaturali o tradotte dall'inglese ("non esiti a chiedere", "nostro utente", "richieste di assistenza", "cosa posso assisterti").
7. Rispondi SOLO con il testo parlato (nessun uso di parentesi, maiuscole o formattazione Markdown).
"""

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Come posso esserle utile?"

# Inizializzazione Storico Chat
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

# 5. Visualizzazione Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# 6. Registratore Vocale / Input Testo
st.write("---")
st.subheader("🗣️️ Parla con BeeVoice")

audio_input_file = st.audio_input("Registra un messaggio vocale")
user_text_input = st.chat_input("Oppure scrivi un messaggio...")

prompt_da_elaborare = None

# Gestione Audio con anti-loop
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

# 7. Generazione Risposta Conversazionale
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    st.session_state.chat_history.append({"role": "user", "content": prompt_da_elaborare})

    with st.spinner("BeeVoice sta rispondendo..."):
        try:
            completion = groq_client.chat.completions.create(
                messages=st.session_state.chat_history,
                model=ACTIVE_MODEL,
                temperature=0.3,
                max_tokens=90
            )

            risposta_testo = completion.choices[0].message.content.strip()
            
            # Pulizia caratteri non pronunciabili
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
