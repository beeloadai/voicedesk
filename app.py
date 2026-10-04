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

# 3. Persistence (bookings.json)
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

# 4. Inizializzazione Stato Conversazione
if "booking_slots" not in st.session_state:
    st.session_state.booking_slots = {
        "nome": None,
        "giorno": None,
        "orario": None,
        "motivo": None
    }

if "completed" not in st.session_state:
    st.session_state.completed = False

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Con chi ho il piacere di parlare?"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": INITIAL_GREETING}
    ]

# 5. Parsing Dati Avanzato (con Fallback e Protezione Blocco Loop)
def parse_and_update_slots(user_text):
    current = st.session_state.booking_slots
    
    prompt = f"""
    Estrai i dati da questo testo per una prenotazione.
    STATO ATTUALE: {json.dumps(current, ensure_ascii=False)}
    TESTO UTENTE: "{user_text}"

    Restituisci ESCLUSIVAMENTE un JSON con questi campi esatti:
    {{
        "nome": "nome e cognome se presente, altrimenti null",
        "giorno": "data o giorno se presente, altrimenti null",
        "orario": "ora o fascia oraria se presente, altrimenti null",
        "motivo": "motivo o argomento se presente, altrimenti null"
    }}
    """
    
    extracted = {}
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        extracted = json.loads(completion.choices[0].message.content)
    except Exception:
        extracted = {}

    # Aggiornamento slot tramite JSON estratto
    for key in ["nome", "giorno", "orario", "motivo"]:
        val = extracted.get(key)
        if val and str(val).strip().lower() not in ["null", "none", "", "non specificato"]:
            st.session_state.booking_slots[key] = str(val).strip()

    # FALLBACK DETERMINISTICO: Evita che il sistema si blocchi se il JSON restituisce null
    slots = st.session_state.booking_slots
    clean_input = user_text.strip()
    
    # Se il nome è ancora vuoto e l'utente ha inserito 1-3 parole, salva direttamente l'input come Nome
    if not slots["nome"] and len(clean_input.split()) <= 4 and not any(char.isdigit() for char in clean_input):
        st.session_state.booking_slots["nome"] = clean_input.title()
    elif slots["nome"] and not slots["giorno"] and ("lun" in clean_input.lower() or "mar" in clean_input.lower() or "mer" in clean_input.lower() or "gio" in clean_input.lower() or "ven" in clean_input.lower() or "sab" in clean_input.lower() or "dom" in clean_input.lower() or "domani" in clean_input.lower() or "oggi" in clean_input.lower()):
        st.session_state.booking_slots["giorno"] = clean_input
    elif slots["nome"] and slots["giorno"] and not slots["orario"] and (any(char.isdigit() for char in clean_input) or ":" in clean_input or "pomeriggio" in clean_input.lower() or "mattina" in clean_input.lower()):
        st.session_state.booking_slots["orario"] = clean_input
    elif slots["nome"] and slots["giorno"] and slots["orario"] and not slots["motivo"]:
        st.session_state.booking_slots["motivo"] = clean_input

# 6. Generazione della Risposta
def get_next_response():
    slots = st.session_state.booking_slots

    if not slots["nome"]:
        return "Mi dica pure, con chi ho il piacere di parlare?"
    if not slots["giorno"]:
        return f"Piacere di conoscerla, Signor {slots['nome']}. Per quale giorno desidera fissare l'appuntamento?"
    if not slots["orario"]:
        return f"Perfetto per {slots['giorno']}. A che ora le sarebbe più comodo?"
    if not slots["motivo"]:
        return "Ottimo. Di cosa desidera trattare durante l'incontro?"

    # Tutti i dati completati
    if not st.session_state.completed:
        booking_record = {
            "nome": slots["nome"],
            "giorno": slots["giorno"],
            "orario": slots["orario"],
            "motivo": slots["motivo"]
        }
        save_booking(booking_record)
        st.session_state.completed = True

    return f"Benissimo, Signor {slots['nome']}. Ho registrato il suo appuntamento per {slots['giorno']} alle ore {slots['orario']} con oggetto {slots['motivo']}. La ringrazio e le auguro una buona giornata."

# 7. Visualizzazione Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# 8. Input Vocale e Testuale
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

# 9. Pipeline di Esecuzione
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})

    with st.spinner("BeeVoice sta elaborando..."):
        try:
            # 1. Parsing e aggiornamento sicuro degli slot
            parse_and_update_slots(prompt_da_elaborare)

            # 2. Selezione della frase di risposta
            risposta_testo = get_next_response()

            # 3. Sintesi Vocale ElevenLabs
            audio_generator = eleven_client.text_to_speech.convert(
                text=risposta_testo,
                voice_id="Xb7hH8MSUJpSbSDYk0k2",
                model_id="eleven_flash_v2_5"
            )
            audio_bytes_response = b"".join(audio_generator)

            # 4. Salvataggio messaggio ed esecuzione rerun
            st.session_state.messages.append({
                "role": "assistant",
                "content": risposta_testo,
                "audio": audio_bytes_response
            })

            st.rerun()

        except Exception as e:
            st.error(f"Errore nell'elaborazione: {e}")

# 10. Sidebar - Monitoraggio
with st.sidebar:
    st.header("📊 Stato Dati Incontro")
    st.json(st.session_state.booking_slots)

    if st.button("🔄 Reset Conversazione"):
        st.session_state.booking_slots = {"nome": None, "giorno": None, "orario": None, "motivo": None}
        st.session_state.completed = False
        st.session_state.messages = [{"role": "assistant", "content": INITIAL_GREETING}]
        st.rerun()

    st.write("---")
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata.")
