# VoiceDesk — B2B AI Voice Booking Agent

**VoiceDesk** è un agente di intelligenza artificiale sviluppato da **Beeload | AI R&D Lab** per automatizzare la gestione delle prenotazioni e l'assistenza clienti vocale.

## Stack Tecnologico
* **Interfaccia Web**: [Streamlit](https://streamlit.io/)
* **Engine LLM**: Google Gemini API via SDK `google-genai`
* **Text-to-Speech (TTS)**: gTTS (Google Text-to-Speech)
* **Hosting**: Streamlit Community Cloud

## Configurazione
Per eseguire l'applicazione occorre impostare la variabile d'ambiente o il secret di Streamlit:
```toml
GEMINI_API_KEY = "la_tua_chiave_api"
