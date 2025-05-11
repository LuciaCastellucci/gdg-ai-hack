import psutil
import sys
import os
import keyboard
import threading
import time
import json
import requests

# Aggiungi il percorso della directory agents al path di Python
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from audio import AudioMonitor, process
from synthesizer import synthesize_audio_folder

# Variabile globale per tenere traccia del monitor audio
audio_monitor = None
monitoring_active = False

def toggle_audio_monitoring():
    """Avvia o interrompe il monitoraggio dell'audio"""
    global audio_monitor, monitoring_active
    
    if monitoring_active:
        print("Interruzione del monitoraggio audio...")
        if audio_monitor:
            audio_monitor.stop_monitoring()
            audio_monitor = None
        monitoring_active = False
        
        # Esegui la sintesi delle registrazioni audio dopo l'interruzione del monitoraggio
        print("\nAvvio della sintesi delle registrazioni audio...")
        try:
            timestamp = int(time.time())
            output_file = f"output/sintesi_{timestamp}.txt"
            
            # Ask if the user wants to save the synthesis to the database
            save_to_db = input("\nVuoi salvare la sintesi nel database? (s/n): ").lower() in ['s', 'si', 'sì', 'yes', 'y']
            
            if save_to_db:
                # Get required information from the user
                topic = input("Inserisci l'argomento della chiamata: ")
                
                # Get participants as a comma-separated list
                participants_input = input("Inserisci i partecipanti (separati da virgola): ")
                participants = [p.strip() for p in participants_input.split(",") if p.strip()]
                
                # Validate input
                if not topic:
                    print("L'argomento è obbligatorio.")
                    topic = input("Inserisci l'argomento della chiamata: ")
                
                if not participants:
                    print("Almeno un partecipante è obbligatorio.")
                    participants_input = input("Inserisci i partecipanti (separati da virgola): ")
                    participants = [p.strip() for p in participants_input.split(",") if p.strip()]
                
                # Synthesize and save to database
                result = synthesize_audio_folder(
                    output_file=output_file,
                    save_to_db=True,
                    topic=topic,
                    participants=participants
                )
            else:
                # Just synthesize without saving to database
                result = synthesize_audio_folder(output_file=output_file)
            
            print("\nSINTESI DELLE REGISTRAZIONI:")
            print("=" * 70)
            print(result)
            print("=" * 70)
            print(f"\nLa sintesi è stata salvata nel file: {output_file}")
            if save_to_db:
                print("La sintesi è stata salvata anche nel database.")
        except Exception as e:
            print(f"Errore durante la sintesi: {e}")
    else:
        print("Avvio del monitoraggio audio...")
        audio_monitor = AudioMonitor(
            process_function=process,
            min_segment_duration=2.0,  # Imposta la durata minima del batch a 2 secondi
        )
        audio_monitor.start_monitoring()
        monitoring_active = True

def check_videocall_apps() -> bool:
    keywords = ["teams", "zoom", "meet", "webex", "skype"]
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"].lower()
            for keyword in keywords:
                if keyword in name:
                    return True
        except Exception as e:
            print(f"Error checking process: {e}")
    return False

def start_keyboard_listener():
    """Avvia il listener per la combinazione di tasti"""
    # Combinazione di tasti: Ctrl+Alt+M
    keyboard.add_hotkey('ctrl+alt+m', toggle_audio_monitoring)
    print("Listener per tasti avviato. Premi Ctrl+Alt+M per attivare/disattivare il monitoraggio audio.")
    
    # Mantieni il thread in esecuzione
    keyboard.wait('esc')  # Termina il programma con il tasto Esc
    print("Applicazione terminata.")

if __name__ == "__main__":
    apps = check_videocall_apps()
    if apps:
        print("Video call applications are running.")
        # Avvia il listener per la combinazione di tasti in un thread separato
        keyboard_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
        keyboard_thread.start()
        
        try:
            # Mantieni il thread principale in esecuzione
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nProgramma interrotto dall'utente.")
            if audio_monitor and monitoring_active:
                audio_monitor.stop_monitoring()
                # Esegui la sintesi delle registrazioni audio anche quando il programma viene interrotto
                try:
                    timestamp = int(time.time())
                    output_file = f"output/sintesi_{timestamp}.txt"
                    
                    # Ask if the user wants to save the synthesis to the database
                    save_to_db = input("\nVuoi salvare la sintesi nel database? (s/n): ").lower() in ['s', 'si', 'sì', 'yes', 'y']
                    
                    if save_to_db:
                        # Get required information from the user
                        topic = input("Inserisci l'argomento della chiamata: ")
                        
                        # Get participants as a comma-separated list
                        participants_input = input("Inserisci i partecipanti (separati da virgola): ")
                        participants = [p.strip() for p in participants_input.split(",") if p.strip()]
                        
                        # Validate input
                        if not topic:
                            print("L'argomento è obbligatorio.")
                            topic = input("Inserisci l'argomento della chiamata: ")
                        
                        if not participants:
                            print("Almeno un partecipante è obbligatorio.")
                            participants_input = input("Inserisci i partecipanti (separati da virgola): ")
                            participants = [p.strip() for p in participants_input.split(",") if p.strip()]
                        
                        # Synthesize and save to database
                        result = synthesize_audio_folder(
                            output_file=output_file,
                            save_to_db=True,
                            topic=topic,
                            participants=participants
                        )
                    else:
                        # Just synthesize without saving to database
                        result = synthesize_audio_folder(output_file=output_file)
                    
                    print("\nSINTESI DELLE REGISTRAZIONI:")
                    print("=" * 70)
                    print(result)
                    print("=" * 70)
                    print(f"\nLa sintesi è stata salvata nel file: {output_file}")
                    if save_to_db:
                        print("La sintesi è stata salvata anche nel database.")
                except Exception as e:
                    print(f"Errore durante la sintesi: {e}")
    else:
        print("No video call applications are running.")
    
    
