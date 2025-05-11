import os
import glob
from pathlib import Path
import base64
from typing import List, Optional
import time
import requests
import json
from datetime import datetime

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables from .env file
load_dotenv()

# Get Google API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError(
        "Google API key not found. Make sure the .env file contains the GEMINI_API_KEY variable."
    )

# API endpoint for saving call logs
API_BASE_URL = "http://localhost:8000"


def audio_to_base64(file_path: str) -> str:
    """Convert an audio file to base64 encoding."""
    with open(file_path, "rb") as audio_file:
        return base64.b64encode(audio_file.read()).decode("utf-8")


def transcribe_audio_file(file_path: str) -> str:
    """Transcribe a single audio file using Gemini."""
    try:
        # Convert the audio file to base64
        base64_audio = audio_to_base64(file_path)

        # Use Gemini for transcription
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",  # Using appropriate model for audio processing
            google_api_key=GEMINI_API_KEY,
            temperature=0,
        )

        response = llm.invoke(
            [
                SystemMessage(
                    content="Trascrivi dettagliatamente questo audio in italiano. Se c'è un discorso, cosa viene detto?"
                ),
                HumanMessage(
                    content=[
                        {
                            "type": "media",
                            "mime_type": "audio/wav",
                            "data": base64_audio,
                        }
                    ]
                ),
            ]
        )

        return response.content
    except Exception as e:
        print(f"Errore nella trascrizione del file {file_path}: {e}")
        return f"[Impossibile trascrivere {os.path.basename(file_path)}: {str(e)}]"


def save_synthesis_to_db(synthesis: str, topic: str, participants: List[str]) -> dict:
    """
    Save the synthesis to the database using the API

    Args:
        synthesis: The synthesized text
        topic: The topic of the call
        participants: List of participant names

    Returns:
        The response from the API as a dictionary
    """
    try:
        # Get current date in the required format (YYYY-MM-DD)
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Prepare data for the API call
        call_log_data = {
            "date": current_date,
            "topic": topic,
            "participants": participants,
            "report": synthesis
        }

        # Make the API call
        response = requests.post(
            f"{API_BASE_URL}/call-logs",
            json=call_log_data,
            headers={"Content-Type": "application/json"},
        )

        # Check if the request was successful
        if response.status_code == 201:
            print(
                f"Successfully saved synthesis to database with ID: {response.json().get('_id')}"
            )
            return response.json()
        else:
            print(
                f"Failed to save synthesis: HTTP {response.status_code} - {response.text}"
            )
            return {"error": f"HTTP {response.status_code}", "message": response.text}

    except Exception as e:
        print(f"Error saving synthesis to database: {e}")
        return {"error": str(e)}


def synthesize_audio_folder(
    folder_path: str = "output/audio",
    output_file: Optional[str] = None,
    save_to_db: bool = False,
    topic: Optional[str] = None,
    participants: Optional[List[str]] = None,
) -> str:
    """
    Prende tutti i file audio nella cartella specificata, li trascrive e
    sintetizza il contenuto utilizzando Gemini.

    Args:
        folder_path: Percorso della cartella contenente i file audio (default: 'output/audio')
        output_file: Percorso del file dove salvare il risultato della sintesi (opzionale)
        save_to_db: Indica se salvare la sintesi nel database (default: False)
        topic: Argomento della chiamata (necessario se save_to_db è True)
        participants: Lista dei partecipanti alla chiamata (necessario se save_to_db è True)

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
        print(
            f"Trascrivendo file {i + 1}/{len(audio_files)}: {os.path.basename(audio_file)}"
        )
        transcription = transcribe_audio_file(audio_file)
        transcriptions.append(
            {"file": os.path.basename(audio_file), "transcription": transcription}
        )

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
        temperature=0.2,  # Leggera creatività per una sintesi migliore
    )

    response = llm.invoke(
        [
            SystemMessage(
                content="""
        Sintetizza il contenuto delle trascrizioni seguenti in un riassunto ben strutturato.
        Organizza il riassunto in sezioni logiche, evidenziando i punti chiave della conversazione.
        Includi citazioni importanti e informazioni rilevanti.
        """
            ),
            HumanMessage(content=combined_text),
        ]
    )

    synthesis = response.content

    # Salva su file se richiesto
    if output_file:
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(synthesis)
        print(f"Sintesi salvata nel file: {output_file}")

    # Salva nel database se richiesto
    if save_to_db:
        if not topic or not participants:
            raise ValueError(
                "Topic e participants sono richiesti per salvare nel database."
            )
        save_synthesis_to_db(synthesis, topic, participants)

    return synthesis


def synthesize_report_content(file_contents: List[str], call_reports: List[str]) -> str:
    """
    Synthesize the content of files and call reports using LLM.
    
    Args:
        file_contents: List of strings containing the text of the files
        call_reports: List of strings containing the call reports
        
    Returns:
        A string containing the synthesis of the content
    """
    print("Synthesizing the content of files and reports...")
    
    combined_text = ""
    
    if file_contents:
        combined_text += "# FILE CONTENTS\n\n"
        for i, content in enumerate(file_contents):
            combined_text += f"--- File {i+1} ---\n"
            combined_text += f"{content}\n\n"
    
    if call_reports:
        combined_text += "# CALL REPORTS\n\n"
        for i, report in enumerate(call_reports):
            combined_text += f"--- Report {i+1} ---\n"
            combined_text += f"{report}\n\n"
    
    if not combined_text:
        return "No content to synthesize."
    
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro",
            google_api_key=GEMINI_API_KEY,
            temperature=0.2,  # Slight creativity for a better synthesis
        )
        
        response = llm.invoke(
            [
                SystemMessage(
                    content="""
            Synthesize the following material into a well-structured summary.
            Organize the summary into logical sections, highlighting the main concepts.
            Identify and connect related information across different contents.
            Highlight points of uncertainty or contradictions, if present.
            Include important quotes and relevant information.
            """
                ),
                HumanMessage(content=combined_text),
            ]
        )
        
        return response.content
    except Exception as e:
        print(f"Error during content synthesis: {e}")
        return f"Synthesis error: {str(e)}"


if __name__ == "__main__":
    # Esempio di utilizzo
    timestamp = int(time.time())
    output_file = f"output/sintesi_{timestamp}.txt"
    result = synthesize_audio_folder(
        output_file=output_file,
        save_to_db=True,
        topic="Meeting di progetto",
        participants=["Alice", "Bob", "Charlie"],
    )
    print("\nSINTESI:")
    print("=" * 50)
    print(result)
    print("=" * 50)
