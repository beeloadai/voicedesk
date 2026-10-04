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

# Selezione Modello di Chat Ottimale (Predilige Llama-3.3-70b se disponibile, altrimenti Llama-3.1)
def select_best_groq_model():
    try:
        models = groq_client.models.list()
        model_ids = [m.id for m in models.data]
        
        # Priorità a modelli con elevata capacità di ragionamento in italiano
        for preferred in ["llama-3.3-70b-versatile", "llama3-70b-8192", "llama-3.1-8b-instant"]:
            if preferred in model_ids:
                return preferred
                
        # Fallback su primo modello chat valido
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

# 4. Inizializzazione Sessione e Memoria di Stato
if "booking_slots" not in st.session_state:
    st.session_state.booking_slots = {
        "nome": None,
        "giorno": None,
        "orario": None,
        "motivo": None
    }

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Come posso esserle utile?"

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": INITIAL_GREETING}
    ]

# 5. Modulo di Estrazione Dati Strategico (JSON Extractor)
def extract_and_update_slots(user_text):
    current = st.session_state.booking_slots
    
    extraction_prompt = f"""
    Sei un modulo di analisi del testo. Estrai le informazioni per una prenotazione dal messaggio dell'utente.
    
    STATO ATTUALE SLOT:
    - Nome: {current['nome']}
    - Giorno: {current['giorno']}
    - Orario: {current['orario']}
    - Motivo: {current['motivo']}
    
    MESSAGGIO UTENTE: "{user_text}"
    
    Estrai SOLO i nuovi dati presenti nel messaggio utente e restituisci un JSON valido con i campi:
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
        
        # Aggiornamento slot di memoria
        for key in current:
            if extracted.get(key) and str(extracted[key]).lower() != "null":
                st.session_state.booking_slots[key] = extracted[key]
    except Exception:
        pass

# 6. Generazione Risposta Umana Naturale (Conversational Engine)
def generate_natural_response(user_text):
    slots = st.session_state.booking_slots
    
    # Determina l'obiettivo corrente della conversazione
    missing_slots = [k for k, v in slots.items() if v is None]
    
    if not missing_slots:
        # Tutti i dati raccolti: salva e genera conferma
        save_booking(slots)
        system_instruction = f"""
        Sei BeeVoice, la segretaria esecutiva di Beeload.
        Tutti i dati dell'appuntamento sono stati raccolti con successo:
        - Nome: {slots['nome']}
        - Giorno: {slots['giorno']}
        - Orario: {slots['orario']}
        - Motivo: {slots['motivo']}

        Comunica la conferma dell'appuntamento in modo caldo, umano e professionale in italiano fluido.
        Ringrazia e augura una buona giornata con estrema naturalezza. Massimo 2 frasi.
        """
    else:
        next_target = missing_slots[0]
        target_descriptions = {
            "nome": "chiedere con cortesia il nome dell'interlocutore",
            "giorno": f"confermare l'attenzione verso {slots['nome']} e chiedere per quale giorno desidera fissare l'incontro",
            "orario": f"confermare la disponibilità per {slots['giorno']} e chiedere l'orario o fascia oraria preferita",
            "motivo": "chiedere brevemente di cosa desidera trattare o l'argomento della riunione"
        }
        
        system_instruction = f"""
        Sei BeeVoice, la segretaria esecutiva di Beeload.
        Stai conducendo una conversazione telefonica reale per fissare un appuntamento.
        
        DATI CONFERMATI FINORA:
        - Nome: {slots['nome']}
        - Giorno: {slots['giorno']}
        - Orario: {slots['orario']}
        - Motivo: {slots['motivo']}
        
        OBIETTIVO CORRENTE: Il tuo unico obiettivo ora è {target_descriptions[next_target]}.
        
        REGOLE TASSATIVE PER LA NATURALEZZA:
        1. Parla in modo spontaneo, fluido e professionale, come una vera segretaria di direzione italiana.
        2. DAI SEMPRE E SOLO DEL "LEI". Mai usare il "tu".
        3. Riconosci in modo caldo l'ultimo dato fornito dall'utente e fai la domanda successiva in modo fluido.
        4. NON usare MAI traduzioni letterali dall'inglese (VIETATE frasi come: "non esiti a chiedere", "richieste di assistenza", "come posso aiutarti", "il nostro utente").
        5. Mantieni la risposta brevissima (massimo 1 o 2 frasi naturali, perfette da pronunciare a voce).
        6. NON usare parentesi, maiuscole per urlare o formattazione Markdown. Genera solo il testo da pronunciare.
        """

    messages = [{"role": "system", "content": system_instruction}]
    
    # Inserisci le ultime battute per mantenere la coerenza
    for msg in st.session_state.messages[-4:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
        
    messages.append({"role": "user", "content": user_text})

    completion = groq_client.chat.completions.create(
        messages=messages,
        model=ACTIVE_MODEL,
        temperature=0.3,
        max_tokens=90
    )
    
    raw_response = completion.choices[0].message.content.strip()
    clean_response = re.sub(r'\[.*?\]|\(.*?\)', '', raw_response).strip()
    clean_response = clean_response.replace("*", "").replace("#", "")
    return clean_response

# 7. Rendering Interfaccia Storico Chat
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

# Trascrizione audio tramite Whisper
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

# 9. Pipeline di Elaborazione Principale
if prompt_da_elaborare:
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    
    with st.spinner("BeeVoice sta rispondendo..."):
        try:
            # Step 1: Estrazione dati e aggiornamento stato
            extract_and_update_slots(prompt_da_elaborare)
            
            # Step 2: Generazione risposta fluida e naturale
            risposta_testo = generate_natural_response(prompt_da_elaborare)

            # Step 3: Sintesi vocale ElevenLabs
            audio_generator = eleven_client.text_to_speech.convert(
                text=risposta_testo,
                voice_id="Xb7hH8MSUJpSbSDYk0k2",
                model_id="eleven_flash_v2_5"
            )
            
            audio_bytes_response = b"".join(audio_generator)

            # Step 4: Registrazione messaggi e aggiornamento UI
            st.session_state.messages.append({
                "role": "assistant", 
                "content": risposta_testo,
                "audio": audio_bytes_response
            })
            
            st.rerun()

        except Exception as e:
            st.error(f"Errore nell'elaborazione: {e}")

# 10. Sidebar Informativa e Monitoraggio Stato
with st.sidebar:
    st.header("⚙️ Configurazione")
    st.caption(f"Modello LLM attivo: `{ACTIVE_MODEL}`")
    
    st.write("---")
    st.header("📊 Stato Dati Incontro")
    st.json(st.session_state.booking_slots)
    
    st.write("---")
    st.header("📋 Registro Prenotazioni")
    prenotazioni = load_bookings()
    if prenotazioni:
        st.dataframe(prenotazioni, use_container_width=True)
    else:
        st.info("Nessuna prenotazione salvata.")
