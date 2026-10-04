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

# 4. SYSTEM PROMPT AVANZATO — SEGRETERIA ESECUTIVA B2B
SYSTEM_INSTRUCTION = """
Sei BeeVoice, la responsabile dell'accoglienza e dell'agenda esecutiva di Beeload.
Il tuo unico obiettivo è fissare un appuntamento lavorativo con il cliente in modo impeccabile, caldo e naturale.

LINEE GUIDA DI CONVERSAZIONE (ITALIANO ALTO LIVELLO):
- Parla in modo spontaneo, elegante e fluido, come una professionista madrelingua italiana di alto livello.
- Dai SEMPRE del "Lei".
- RISPONDI CON MASSIMO 1 O 2 FRASI CONCISE. La brevità è fondamentale per l'ascolto vocale.

GESTIONE DATI PRENOTAZIONE:
Devi raccogliere con garbo solo questi 4 dati:
1. Nome dell'interlocutore (es: "Con chi ho il piacere di parlare?")
2. Giorno / Data desiderata (es: "Per quale giorno desidera fissare l'incontro?")
3. Orario indicativo (es: "Preferisce la mattina o il pomeriggio?")
4. Motivo/Oggetto dell'incontro (es: "Di cosa voleva parlarne in particolare?")

REGOLE DI FLUSSO:
- Raccogli UN SOLO DATO alla volta. Non fare mai più domande contemporaneamente.
- Quando l'utente ti fornisce un dato, riprendilo brevemente per confermarlo e passa al dato successivo.
- Quando hai tutti e 4 i dati, recita un breve riepilogo finale e conferma la prenotazione.

DIVIETI ASSOLUTI:
- Vietato usare traduzioni letterali dall'inglese (es: NESSUNA frase come "cosa posso fare per te", "dammi il tuo nome", "comunicarci meglio", "ottimo").
- Vietato usare parentesi, note registiche, elenchi puntati o formattazione Markdown.
- Genera ESCLUSIVAMENTE il testo esatto che deve essere pronunciato dalla voce sintetica.
"""

INITIAL_GREETING = "Buongiorno, sono BeeVoice di Beeload. Come posso esserle utile?"

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
    if not available_models:
        st.error("Nessun modello di chat risulta accessibile con questa API Key di Groq.")
        st.stop()
        
    st.session_state.messages.append({"role": "user", "content": prompt_da_elaborare})
    st.session_state.chat_history.append({"role": "user", "content": prompt_da_elaborare})
    
    selected_model = available_models[0]
    
    with st.spinner("BeeVoice sta rispondendo..."):
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=st.session_state.chat_history,
                model=selected_model,
                temperature=0.2,  # Bassa creatività per garantire la massima aderenza alle regole sintattiche
                max_tokens=100
            )

            risposta_testo = chat_completion.choices[0].message.content.strip()
            
            # Pulizia completa di eventuali parentesi o caratteri di formattazione
            risposta_pulita = re.sub(r'\[.*?\]|\(.*?\)', '', risposta_testo).strip()
            risposta_pulita = risposta_pulita.replace("*", "").replace("#", "")
            
            if not risposta_pulita:
                risposta_pulita = risposta_testo

            st.session_state.chat_history.append({"role": "assistant", "content": risposta_pulita})

            # Sintesi vocale con ElevenLabs
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
