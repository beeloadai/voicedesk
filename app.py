import os
import json
import re
import streamlit as st
from groq import Groq
from elevenlabs.client import ElevenLabs

# -----------------------------------------------------------------------------
# 1. CONFIGURAZIONE PAGINA & CLIENTS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="BeeVoice | Beeload",
    page_icon="🎙",
    layout="centered"
)

st.title("🎙 BeeVoice — Agente Prenotazioni Vocale")
st.caption("Beeload AI R&D Lab — Architettura Deterministica B2B")

groq_key = st.secrets.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
elevenlabs_key = st.secrets.get("ELEVENLABS_API_KEY") or os.environ.get("ELEVENLABS_API_KEY")

if not groq_key or not elevenlabs_key:
    st.error("⚠️ Configura GROQ_API_KEY e ELEVENLABS_API_KEY nei Secrets di Streamlit.")
    st.stop()

groq_client = Groq(api_key=groq_key.strip())
eleven_client = ElevenLabs(api_key=elevenlabs_key.strip())

# -----------------------------------------------------------------------------
# 2. PERSISTENZA DATI
# -----------------------------------------------------------------------------
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

# -----------------------------------------------------------------------------
# 3. STATO DELLA CONVERSAZIONE
# -----------------------------------------------------------------------------
if "step" not in st.session_state:
    st.session_state.step = "GET_NAME"  # STEP: GET_NAME -> GET_DATE -> GET_TIME -> GET_REASON -> COMPLETED

if "booking_data" not in st.session_state:
    st.session_state.booking_data = {
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

if "processed_audio_hash" not in st.session_state:
    st.session_state.processed_audio_hash = None

# -----------------------------------------------------------------------------
# 4. NLU: ESTRAZIONE ENTITÀ IN BACKGROUND (NO GENERAZIONE TESTO)
# -----------------------------------------------------------------------------
def extract_entity_with_llm(user_input, current_step):
    """
    Usa l'LLM esclusivamente come estrattore di informazioni in formato JSON.
    """
    prompt = f"""
    Sei un sistema NLU di estrazione dati per un centralino.
    Analizza la frase dell'utente in base alla richiesta attuale.
    
    RICHIESTA ATTUALE: {current_step}
    FRASE UTENTE: "{user_input}"
    
    Restituisci ESCLUSIVAMENTE un JSON con la chiave "extracted_value".
    Se l'utente ha fornito l'informazione richiesta, inserisci il valore pulito in italiano.
    Se l'utente non ha fornito l'informazione o ha detto una frase irrilevante, imposta "extracted_value" a null.
    """
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        res = json.loads(completion.choices[0].message.content)
        val = res.get("extracted_value")
        if val and str(val).lower() not in ["null", "none", ""]:
            return str(val).strip()
    except Exception:
        pass
    return None

# -----------------------------------------------------------------------------
# 5. MACCHINA A STATI DETERMINISTICA (RISPOSTE CERTIFICATE)
# -----------------------------------------------------------------------------
def process_conversation(user_input):
    step = st.session_state.step
    data = st.session_state.booking_data

    if step == "GET_NAME":
        extracted_name = extract_entity_with_llm(user_input, "Nome e Cognome della persona")
        # Fallback diretto se l'input è breve
        val = extracted_name or (user_input if len(user_input.split()) <= 4 else None)
        
        if val:
            data["nome"] = val.title()
            st.session_state.step = "GET_DATE"
            return f"Piacere di conoscerla, Signor {data['nome']}. Per quale giorno desidera fissare l'appuntamento?"
        else:
            return "Per poteri assistere, potrei gentilmente avere il suo nome e cognome?"

    elif step == "GET_DATE":
        extracted_date = extract_entity_with_llm(user_input, "Data o giorno della settimana")
        val = extracted_date or user_input
        
        if val:
            data["giorno"] = val
            st.session_state.step = "GET_TIME"
            return f"Perfetto per {data['giorno']}. A che ora le sarebbe più comodo?"
        else:
            return "Quale giorno le sarebbe più comodo per l'incontro?"

    elif step == "GET_TIME":
        extracted_time = extract_entity_with_llm(user_input, "Orario o fascia oraria")
        val = extracted_time or user_input
        
        if val:
            data["orario"] = val
            st.session_state.step = "GET_REASON"
            return "Ottimo. Di quale argomento desidera trattare durante l'incontro?"
        else:
            return "A che ora preferisce fissare l'appuntamento?"

    elif step == "GET_REASON":
        extracted_reason = extract_entity_with_llm(user_input, "Motivo o argomento della riunione")
        val = extracted_reason or user_input
        
        if val:
            data["motivo"] = val
            st.session_state.step = "COMPLETED"
            save_booking(data)
            return f"Perfetto, Signor {data['nome']}. Ho registrato il suo appuntamento per {data['giorno']} alle ore {data['orario']} con oggetto {data['motivo']}. La ringrazio e le auguro una buona giornata."
        else:
            return "Può indicarmi brevemente l'oggetto della riunione?"

    elif step == "COMPLETED":
        return f"Il suo appuntamento è già stato confermato per {data['giorno']} alle ore {data['orario']}. Desidera effettuare una nuova prenotazione?"

    return "Come posso esserle utile?"

# -----------------------------------------------------------------------------
# 6. RENDERING INTERFACCIA
# -----------------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

st.write("---")
st.subheader("🗣️ Parla con BeeVoice")

audio_input_file = st.audio_input("Registra un messaggio vocale")
user_text_input = st.chat_input("Oppure scrivi un messaggio...")

prompt_da_elaborare = None

# Gestione Input Audio senza duplicazioni
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

# -----------------------------------------------------------------------------
# 7. PIPELINE DI ESECUZIONE
# -----------------------------------------------------------------------------
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})

    with st.spinner("BeeVoice sta elaborando..."):
        try:
            # 1. Calcolo risposta deterministica in base allo stato attuale
            risposta_testo = process_conversation(prompt_da_elaborare)

            # 2. Generazione Audio ElevenLabs
            audio_generator = eleven_client.text_to_speech.convert(
                text=risposta_testo,
                voice_id="Xb7hH8MSUJpSbSDYk0k2",
                model_id="eleven_flash_v2_5"
            )
            audio_bytes_response = b"".join(audio_generator)

            # 3. Registrazione messaggio
            st.session_state.messages.append({
                "role": "assistant",
                "content": risposta_testo,
                "audio": audio_bytes_response
            })

            st.rerun()

        except Exception as e:
            st.error(f"Errore nell'elaborazione: {e}")

# -----------------------------------------------------------------------------
# 8. SIDEBAR & MONITORAGGIO STATO
# -----------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Stato della Conversazione")
    st.info(f"Fase attuale: **{st.session_state.step}**")
    st.json(st.session_state.booking_data)

    if st.button("🔄 Nuova Conversazione"):
        st.session_state.step = "GET_NAME"
        st.session_state.booking_data = {"nome": None, "giorno": None, "orario": None, "motivo": None}
        st.session_state.messages = [{"role": "assistant", "content": INITIAL_GREETING}]
        st.session_state.processed_audio_hash = None
        st.rerun()

    st.write("---")
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata.")
