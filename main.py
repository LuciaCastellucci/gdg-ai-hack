import psutil
import sys
import os
import threading
import time
import json
import platform
import requests

# Aggiungi il percorso della directory agents al path di Python
sys.path.append(os.path.join(os.path.dirname(__file__), "agents"))

from audio import AudioMonitor, process
from synthesizer import synthesize_audio_folder
from gui import NotificationDot  # Importa la classe NotificationDot
from PySide6.QtWidgets import QApplication
from call_reports.reports import create_report  # Importa la funzione create_report
from agents.call_assistant_agent.agent import set_notification_callback  # Importa la funzione per impostare il callback

# Variabile globale per tenere traccia del monitor audio
audio_monitor = None
monitoring_active = False

# Variabili globali per la GUI
notification_dot = None
gui_active = False
last_videocall_status = False
videocall_check_interval = 5  # Controlla lo stato delle videochiamate ogni 5 secondi
app = None  # Istanza di QApplication

# Identifica il sistema operativo
SYSTEM = platform.system()

# Inizializza l'handler dei tasti appropriato in base al sistema operativo
if SYSTEM == "Windows":
    import keyboard

    def register_hotkey(callback):
        keyboard.add_hotkey("ctrl+alt+m", callback)
        print(
            "Listener per tasti avviato. Premi Ctrl+Alt+M per attivare/disattivare il monitoraggio audio."
        )
        keyboard.wait("esc")  # Termina il programma con il tasto Esc

elif SYSTEM == "Darwin":  # macOS
    from pynput import keyboard

    def register_hotkey(callback):
        def on_press(key):
            try:
                # Verifica se si tratta della combinazione ctrl+alt+m
                if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                    if hasattr(on_press, "ctrl_pressed"):
                        on_press.ctrl_pressed = True
                elif key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                    if hasattr(on_press, "alt_pressed"):
                        on_press.alt_pressed = True
                elif hasattr(key, "char") and key.char == "m":
                    if getattr(on_press, "ctrl_pressed", False) and getattr(
                        on_press, "alt_pressed", False
                    ):
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
            print(
                "Listener per tasti avviato. Premi Ctrl+Alt+M per attivare/disattivare il monitoraggio audio."
            )
            listener.join()
else:
    # Linux o altri sistemi
    print(
        f"Sistema operativo {SYSTEM} non completamente supportato. Le scorciatoie da tastiera potrebbero non funzionare."
    )

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
        
        # Resetta il callback globale quando il monitoraggio audio viene disattivato
        set_notification_callback(None)

        # Esegui la sintesi delle registrazioni audio dopo l'interruzione del monitoraggio
        print("\nAvvio della sintesi delle registrazioni audio...")
        try:
            timestamp = int(time.time())
            output_file = f"output/sintesi_{timestamp}.txt"

            # Ask if the user wants to save the synthesis to the database
            save_to_db = input(
                "\nVuoi salvare la sintesi nel database? (s/n): "
            ).lower() in ["s", "si", "sì", "yes", "y"]

            if save_to_db:
                # Get required information from the user
                topic = input("Inserisci l'argomento della chiamata: ")

                # Get participants as a comma-separated list
                participants_input = input(
                    "Inserisci i partecipanti (separati da virgola): "
                )
                participants = [
                    p.strip() for p in participants_input.split(",") if p.strip()
                ]

                # Validate input
                if not topic:
                    print("L'argomento è obbligatorio.")
                    topic = input("Inserisci l'argomento della chiamata: ")

                if not participants:
                    print("Almeno un partecipante è obbligatorio.")
                    participants_input = input(
                        "Inserisci i partecipanti (separati da virgola): "
                    )
                    participants = [
                        p.strip() for p in participants_input.split(",") if p.strip()
                    ]

                # Synthesize and save to database
                result = synthesize_audio_folder(
                    output_file=output_file,
                    save_to_db=True,
                    topic=topic,
                    participants=participants,
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
        
        # Funzione di notifica per file audio - con protezione anti-loop
        last_notification_time = [0]  # Usiamo una lista per mantenere lo stato
        
        def notify_audio(message):
            # Evita notifiche troppo frequenti (almeno 5 secondi tra una notifica e l'altra)
            current_time = time.time()
            if current_time - last_notification_time[0] < 5:
                return
                
            if notification_dot:
                notification_dot.set_notification(message)
                last_notification_time[0] = current_time
        
        # Configura il callback globale per gli agenti quando si attiva il monitoraggio audio
        set_notification_callback(notify_audio)
                
        audio_monitor = AudioMonitor(
            process_function=process,
            min_segment_duration=2.0,  # Imposta la durata minima del batch a 2 secondi
            notification_callback=notify_audio
        )
        audio_monitor.start_monitoring()
        monitoring_active = True


def check_videocall_apps() -> bool:
    keywords = ["teams", "zoom", "meet", "webex", "skype"]

    if SYSTEM == "Darwin":  # macOS
        # Su macOS utilizziamo un metodo diverso per controllare i processi
        try:
            import subprocess

            result = subprocess.run(["ps", "-A"], capture_output=True, text=True)
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


def manage_gui_state(videocall_running: bool):
    """Gestisce l'attivazione e la disattivazione della GUI in base allo stato delle videochiamate"""
    global notification_dot, gui_active, last_videocall_status, app
    
    # Inizializza l'applicazione Qt se non è già stato fatto
    if app is None:
        print("Inizializzazione dell'applicazione Qt...")
        if not QApplication.instance():
            app = QApplication(sys.argv)
    
    # Se è la prima volta o se lo stato è cambiato
    if notification_dot is None or videocall_running != last_videocall_status:
        if videocall_running:
            # Avvia la GUI
            print("Avvio della GUI - Videochiamata in corso")
            
            # Se non esiste l'istanza NotificationDot, creala
            if notification_dot is None:
                # Percorso dell'icona nella stessa directory del file Python principale
                icon_path = os.path.join(os.path.dirname(__file__), "call_assistant_icon.png")
                
                # Crea l'istanza di NotificationDot con l'icona personalizzata
                notification_dot = NotificationDot(icon_path)

            # Imposta il messaggio di notifica
            message = "Videochiamata in corso - Assistente attivo"
            notification_dot.set_notification(message)
            
            # Mostra la GUI
            notification_dot.show()
            gui_active = True
            
            # Funzione di callback per aggiornare la notifica con il report
            def notify_report(message):
                if notification_dot:
                    notification_dot.set_notification(message)
            
            # Configuriamo la funzione di callback per le notifiche degli agenti
            set_notification_callback(notify_report)
            
            # Chiamiamo il metodo create_report per generare report
            # ma solo una volta all'avvio della videochiamata
            if last_videocall_status == False:  # Solo quando passiamo da False a True
                try:
                    create_report(notification_callback=notify_report)
                except Exception as e:
                    print(f"Errore durante la generazione dei report: {e}")
                    
        elif not videocall_running and notification_dot is not None:
            # Disattiva la GUI
            print("Disattivazione della GUI - Nessuna videochiamata in corso")
            notification_dot.hide()  # Nasconde la GUI invece di distruggerla
            gui_active = False
            
            # Resetta il callback degli agenti quando la GUI è disattivata
            set_notification_callback(None)
        
        # Aggiorna lo stato
        last_videocall_status = videocall_running


def check_videocall_loop():
    """Verifica periodicamente lo stato delle applicazioni di videochiamata e gestisce la GUI di conseguenza"""
    global last_videocall_status
    
    while True:
        # Controlla lo stato attuale delle applicazioni di videochiamata
        videocall_running = check_videocall_apps()
        
        # Gestisci lo stato della GUI in base alla presenza di videochiamate
        manage_gui_state(videocall_running)
        
        # Attendi prima del prossimo controllo
        time.sleep(videocall_check_interval)


def start_keyboard_listener():
    """Avvia il listener per la combinazione di tasti"""
    register_hotkey(toggle_audio_monitoring)
    print("Applicazione terminata.")


if __name__ == "__main__":
    # Inizializzazione dell'applicazione Qt
    if not QApplication.instance():
        app = QApplication(sys.argv)
    
    # Verifica iniziale dello stato delle videochiamate
    apps = check_videocall_apps()
    print(f"Stato iniziale: {'Videochiamata in corso' if apps else 'Nessuna videochiamata in corso'}")
    
    # Gestisci lo stato della GUI in base allo stato iniziale
    manage_gui_state(apps)
    
    # Avvia il ciclo di controllo delle applicazioni di videochiamata in un thread separato
    videocall_thread = threading.Thread(target=check_videocall_loop, daemon=True)
    videocall_thread.start()
    
    # Avvia il listener per la combinazione di tasti in un thread separato (solo per Windows)
    if SYSTEM == "Windows":
        keyboard_thread = threading.Thread(target=start_keyboard_listener, daemon=True)
        keyboard_thread.start()
        
        try:
            # Se stiamo usando la GUI, esegui il loop di eventi Qt
            if gui_active:
                print("Esecuzione del loop di eventi Qt...")
                sys.exit(app.exec())
            else:
                # Altrimenti, mantieni il thread principale in esecuzione
                while True:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nProgramma interrotto dall'utente.")
            if audio_monitor and monitoring_active:
                audio_monitor.stop_monitoring()
    else:
        # Per macOS e altri sistemi eseguiamo direttamente il listener
        try:
            start_keyboard_listener()
        except KeyboardInterrupt:
            print("\nProgramma interrotto dall'utente.")
            if audio_monitor and monitoring_active:
                audio_monitor.stop_monitoring()
