import psutil
import sys
import os
import threading
import time
import json
import platform
import requests

# Aggiungi il percorso della directory agents al path di Python
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from audio import AudioMonitor, process
from synthesizer import synthesize_audio_folder

# Variabile globale per tenere traccia del monitor audio
audio_monitor = None
monitoring_active = False

# Identifica il sistema operativo
SYSTEM = platform.system()

# Inizializza l'handler dei tasti appropriato in base al sistema operativo
if SYSTEM == "Windows":
    import keyboard
    
    def register_hotkey(callback):
        keyboard.add_hotkey('ctrl+alt+m', callback)
        print("Listener per tasti avviato. Premi Ctrl+Alt+M per attivare/disattivare il monitoraggio audio.")
        keyboard.wait('esc')  # Termina il programma con il tasto Esc
        
elif SYSTEM == "Darwin":  # macOS
    from pynput import keyboard
    
    def register_hotkey(callback):
        def on_press(key):
            try:
                # Verifica se si tratta della combinazione ctrl+alt+m
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    if hasattr(on_press, 'ctrl_pressed'):
                        on_press.ctrl_pressed = True
                elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                    if hasattr(on_press, 'alt_pressed'):
                        on_press.alt_pressed = True
                elif hasattr(key, 'char') and key.char == 'm':
                    if getattr(on_press, 'ctrl_pressed', False) and getattr(on_press, 'alt_pressed', False):
                        callback()
            except AttributeError:
                pass
            
        def on_release(key):
            if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                on_press.ctrl_pressed = False
            elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                on_press.alt_pressed = False
            elif key == keyboard.Key.esc:
                # Fermati quando si preme Esc
                return False
                
        # Inizializza le variabili di stato
        on_press.ctrl_pressed = False
        on_press.alt_pressed = False
        
        # Avvia il listener
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            print("Listener per tasti avviato. Premi Ctrl+Alt+M per attivare/disattivare il monitoraggio audio.")
            listener.join()
else:
    # Linux o altri sistemi
    print(f"Sistema operativo {SYSTEM} non completamente supportato. Le scorciatoie da tastiera potrebbero non funzionare.")
    
    def register_hotkey(callback):
        # Implementazione minimale per altri sistemi
        print("Hotkey non disponibile. Premi Ctrl+C per terminare.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

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
    
    if SYSTEM == "Darwin":  # macOS
        # Su macOS utilizziamo un metodo diverso per controllare i processi
        try:
            import subprocess
            result = subprocess.run(['ps', '-A'], capture_output=True, text=True)
            process_list = result.stdout.lower()
            for keyword in keywords:
                if keyword in process_list:
                    return True
        except Exception as e:
            print(f"Error checking processes on macOS: {e}")
    else:
        # Approccio standard per Windows e Linux
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
    register_hotkey(toggle_audio_monitoring)
    print("Applicazione terminata.")

if __name__ == "__main__":
    apps = check_videocall_apps()
    if apps:
        print("Video call applications are running.")
        # Avvia il listener per la combinazione di tasti in un thread separato
        if SYSTEM == "Windows":
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
                    # ...codice per la sintesi quando il programma viene interrotto...
        else:
            # Per macOS e altri sistemi eseguiamo direttamente il listener
            try:
                start_keyboard_listener()
            except KeyboardInterrupt:
                print("\nProgramma interrotto dall'utente.")
                if audio_monitor and monitoring_active:
                    audio_monitor.stop_monitoring()
                    # ...codice per la sintesi quando il programma viene interrotto...
    else:
        print("No video call applications are running.")