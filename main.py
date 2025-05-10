import psutil
import sys
import os
import keyboard
import threading
import time

# Aggiungi il percorso della directory agents al path di Python
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

from audio import AudioMonitor, process

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
    else:
        print("No video call applications are running.")
    
    
