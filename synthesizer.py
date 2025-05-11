import os
import glob
from pathlib import Path
import base64
from typing import List, Optional
import time

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables from .env file
load_dotenv()

# Get Google API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Google API key not found. Make sure the .env file contains the GEMINI_API_KEY variable.")

def audio_to_base64(file_path: str) -> str:
    """Convert an audio file to base64 encoding."""
    with open(file_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode('utf-8')

def transcribe_audio_file(file_path: str) -> str:
    """Transcribe a single audio file using Gemini."""
    try:
        # Convert the audio file to base64
        base64_audio = audio_to_base64(file_path)
        
        # Use Gemini for transcription
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",  # Using appropriate model for audio processing
            google_api_key=GEMINI_API_KEY,
            temperature=0
        )
        
        response = llm.invoke([
            SystemMessage(content="Trascrivi dettagliatamente questo audio in italiano. Se c'è un discorso, cosa viene detto?"),
            HumanMessage(content=[
                {
                    "type": "media",
                    "mime_type": "audio/wav",
                    "data": base64_audio
                }
            ])
        ])
        
        return response.content
    except Exception as e:
        print(f"Errore nella trascrizione del file {file_path}: {e}")
        return f"[Impossibile trascrivere {os.path.basename(file_path)}: {str(e)}]"

def synthesize_audio_folder(folder_path: str = 'output/audio', output_file: Optional[str] = None) -> str:
    """
    Prende tutti i file audio nella cartella specificata, li trascrive e
    sintetizza il contenuto utilizzando Gemini.
    
    Args:
        folder_path: Percorso della cartella contenente i file audio (default: 'output/audio')
        output_file: Percorso del file dove salvare il risultato della sintesi (opzionale)
        
    Returns:
        Il testo sintetizzato
    """
    # Verifica che la cartella esista
    if not os.path.exists(folder_path):
        return f"Errore: La cartella {folder_path} non esiste."
    
    # Trova tutti i file WAV nella cartella
    audio_files = sorted(glob.glob(os.path.join(folder_path, "*.wav")))
    
    if not audio_files:
        return f"Nessun file audio trovato nella cartella {folder_path}."
    
    print(f"Trovati {len(audio_files)} file audio. Inizio trascrizione...")
    
    # Trascrivi ogni file audio
    transcriptions = []
    for i, audio_file in enumerate(audio_files):
        print(f"Trascrivendo file {i+1}/{len(audio_files)}: {os.path.basename(audio_file)}")
        transcription = transcribe_audio_file(audio_file)
        transcriptions.append({
            "file": os.path.basename(audio_file),
            "transcription": transcription
        })
    
    # Prepara il testo combinato da tutte le trascrizioni
    combined_text = ""
    for item in transcriptions:
        combined_text += f"File: {item['file']}\n"
        combined_text += f"Trascrizione: {item['transcription']}\n\n"
    
    print("Trascrizioni completate. Sintetizzando il contenuto...")
    
    # Usa Gemini per sintetizzare il contenuto delle trascrizioni
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        google_api_key=GEMINI_API_KEY,
        temperature=0.2  # Leggera creatività per una sintesi migliore
    )
    
    response = llm.invoke([
        SystemMessage(content="""
        Sintetizza il contenuto delle trascrizioni seguenti in un riassunto ben strutturato.
        Organizza il riassunto in sezioni logiche, evidenziando i punti chiave della conversazione.
        Includi citazioni importanti e informazioni rilevanti.
        """),
        HumanMessage(content=combined_text)
    ])
    
    synthesis = response.content
    
    # Salva su file se richiesto
    if output_file:
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(synthesis)
        print(f"Sintesi salvata nel file: {output_file}")
    
    return synthesis

if __name__ == "__main__":
    # Esempio di utilizzo
    timestamp = int(time.time())
    output_file = f"output/sintesi_{timestamp}.txt"
    result = synthesize_audio_folder(output_file=output_file)
    print("\nSINTESI:")
    print("=" * 50)
    print(result)
    print("=" * 50)