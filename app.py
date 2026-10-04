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

def save_booking(booking_data):
    bookings = load_bookings()
    bookings.append(booking_data)
    with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)

# 4. Inizializzazione Stato della Prenotazione
if "booking_slots" not in st.session_state:
    st.session_state.booking_slots = {
        "nome": None,
        "giorno": None,
        "orario": None,
        "motivo": None
    }

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Con chi ho il piacere di parlare?"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": INITIAL_GREETING}
    ]

# Funzione per estrarre informazioni strutturate dal testo dell'utente tramite Groq
def extract_booking_info(user_text, current_slots):
    prompt = f"""
    Sei un estrattore di dati. Analizza il messaggio dell'utente e la situazione attuale.
    DATI ATTUALI: {json.dumps(current_slots, ensure_ascii=False)}
    MESSAGGIO UTENTE: "{user_text}"

    Estrai i nuovi dati eventualmente forniti dall'utente e restituisci ESCLUSIVAMENTE un oggetto JSON con queste chiavi:
    - "nome": (stringa con il nome dell'utente o null)
    - "giorno": (stringa con il giorno/data o null)
    - "orario": (stringa con l'orario o fascia oraria o null)
    - "motivo": (stringa con l'argomento/motivo dell'incontro o null)

    Rispondi SOLO ed ESCLUSIVAMENTE con il JSON valido. Nessun altro testo.
    """
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        data = json.loads(completion.choices[0].message.content)
        return data
    except Exception:
        return {}

# Generatore di risposte naturali deterministiche
def get_next_response():
    slots = st.session_state.booking_slots
    
    if not slots["nome"]:
        return "Mi dica pure, con chi ho il piacere di parlare?"
    if not slots["giorno"]:
        return f"Perfetto {slots['nome']}. In quale giorno preferisce fissare l'appuntamento?"
    if not slots["orario"]:
        return f"Ottimo per {slots['giorno']}. Che orario le sarebbe più comodo?"
    if not slots["motivo"]:
        return "Perfetto. Di cosa desidera trattare durante l'incontro?"
    
    # Se tutti i dati sono presenti, salva e conferma
    booking_record = {
        "nome": slots["nome"],
        "giorno": slots["giorno"],
        "orario": slots["orario"],
        "motivo": slots["motivo"]
    }
    save_booking(booking_record)
    
    return f"Benissimo, {slots['nome']}. Ho registrato il suo appuntamento per {slots['giorno']} alle ore {slots['orario']} con oggetto {slots['motivo']}. Un cordiale saluto e a presto!"

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

if audio_input_file is not None:
    audio_bytes = audio_input_file.read()
    if st.session_state.get("last_audio_bytes") != audio_bytes:
        st.session_state["last_audio_bytes"] = audio_bytes
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

# 6. Elaborazione Risposta + Sintesi Vocale
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    
    with st.spinner("BeeVoice sta elaborando..."):
        try:
            # 1. Estraggo i dati dal messaggio dell'utente
            extracted = extract_booking_info(prompt_da_elaborare, st.session_state.booking_slots)
            
            # 2. Aggiorno lo stato dei dati
            for k, v in extracted.items():
                if v and str(v).lower() != "null" and k in st.session_state.booking_slots:
                    st.session_state.booking_slots[k] = v

            # 3. Determino la frase successiva (100% italiana, naturale e corretta)
            risposta_testo = get_next_response()

            # 4. Sintesi vocale con ElevenLabs
            audio_generator = eleven_client.text_to_speech.convert(
                text=risposta_testo,
                voice_id="Xb7hH8MSUJpSbSDYk0k2",
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

# 7. Sidebar — Stato Prenotazione e Registro
with st.sidebar:
    st.header("📊 Stato Dati Incontro")
    st.json(st.session_state.booking_slots)
    
    st.write("---")
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata.")
