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

# Selezione Modello di Chat Ottimale
def select_best_groq_model():
    try:
        models = groq_client.models.list()
        model_ids = [m.id for m in models.data]
        
        for preferred in ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"]:
            if preferred in model_ids:
                return preferred
                
        valid_models = [m for m in model_ids if not any(x in m.lower() for x in ["whisper", "guard", "vision"])]
        return valid_models[0] if valid_models else "llama-3.1-8b-instant"
    except Exception:
        return "llama-3.1-8b-instant"

ACTIVE_MODEL = select_best_groq_model()

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

# 4. Inizializzazione Stato e Memoria
if "booking_slots" not in st.session_state:
    st.session_state.booking_slots = {
        "nome": None,
        "giorno": None,
        "orario": None,
        "motivo": None
    }

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Come posso aiutarla?"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": INITIAL_GREETING}
    ]

# 5. Estrazione Dati Strutturati
def extract_and_update_slots(user_text):
    current = st.session_state.booking_slots
    
    extraction_prompt = f"""
    Sei un estrattore di informazioni. Analizza l'ultimo messaggio dell'utente per aggiornare i dati di prenotazione.
    
    STATO ATTUALE:
    - Nome: {current['nome']}
    - Giorno: {current['giorno']}
    - Orario: {current['orario']}
    - Motivo: {current['motivo']}
    
    MESSAGGIO UTENTE: "{user_text}"
    
    Restituisci unicamente un oggetto JSON valido con i dati estratti (usa null se non menzionati):
    {{"nome": string/null, "giorno": string/null, "orario": string/null, "motivo": string/null}}
    """
    
    try:
        completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": extraction_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        extracted = json.loads(completion.choices[0].message.content)
        
        for key in current:
            if extracted.get(key) and str(extracted[key]).lower() != "null":
                st.session_state.booking_slots[key] = extracted[key]
    except Exception:
        pass

# 6. Generazione Risposta Naturale tramite Esempi Reali
def generate_natural_response(user_text):
    slots = st.session_state.booking_slots
    missing_slots = [k for k, v in slots.items() if v is None]
    
    if not missing_slots:
        save_booking(slots)
        return f"Perfetto, Signor {slots['nome']}. Ho confermato il suo appuntamento per {slots['giorno']} alle ore {slots['orario']} per {slots['motivo']}. La ringrazio e le auguro una buona giornata!"

    # System Instruction basata su Few-Shot Prompting in italiano naturale
    system_instruction = """
Sei BeeVoice, una segretaria di direzione italiana reale, professionale e cordiale.
Stai gestendo una telefonata per fissare un appuntamento di lavoro.

REGOLE DI CONVERSAZIONE:
- Rispondi con MASSIMO 1 O 2 FRASI brevi (ideali da ascoltare a voce).
- Dai SEMPRE del "Lei".
- Sii spontanea, accogliente e naturale.
- VIETATI BANALI CALCHI DALL'INGLESE ("non esitare a chiedere", "nostro utente", "come posso assisterti", "assistenza").

ESEMPI DI CONVERSAZIONE REALE:
Utente: Vorrei fissare un appuntamento.
Assistente: Molto volentieri. Mi dica pure, con chi ho il piacere di parlare?

Utente: Mario Rossi.
Assistente: Piacere di conoscerla, Signor Rossi. Per quale giorno desidera fissare l'incontro?

Utente: Giovedì prossimo.
Assistente: Perfetto per giovedì. Che orario le sarebbe più comodo?

Utente: Verso le tre del pomeriggio.
Assistente: Benissimo, registrato per le quindici. Di cosa desidera trattare nello specifico durante l'incontro?
"""

    messages = [{"role": "system", "content": system_instruction}]
    
    # Manteniamo la cronologia recente
    for msg in st.session_state.messages[-4:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    messages.append({"role": "user", "content": user_text})

    completion = groq_client.chat.completions.create(
        messages=messages,
        model=ACTIVE_MODEL,
        temperature=0.2,
        max_tokens=80
    )
    
    raw_response = completion.choices[0].message.content.strip()
    clean_response = re.sub(r'\[.*?\]|\(.*?\)', '', raw_response).strip()
    clean_response = clean_response.replace("*", "").replace("#", "")
    return clean_response

# 7. Visualizzazione Storico Chat
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if "audio" in msg:
            st.audio(msg["audio"], format="audio/mp3")

# 8. Registratore Vocale e Input
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

# 9. Elaborazione Risposta + Sintesi Vocale
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    
    with st.spinner("BeeVoice sta rispondendo..."):
        try:
            extract_and_update_slots(prompt_da_elaborare)
            risposta_testo = generate_natural_response(prompt_da_elaborare)

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
            st.error(f"Errore nell'elaborazione: {e}")

# 10. Sidebar
with st.sidebar:
    st.header("⚙️ Modello Attivo")
    st.caption(f"`{ACTIVE_MODEL}`")
    
    st.write("---")
    st.header("📊 Dati Raccolti")
    st.json(st.session_state.booking_slots)
    
    st.write("---")
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata.")
