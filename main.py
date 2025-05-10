import psutil
import sys
import os

# Aggiungi il percorso della directory agents al path di Python
sys.path.append(os.path.join(os.path.dirname(__file__), 'agents'))

# Importa l'agente
from agents.call_assistant_agent.agent import run


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


if __name__ == "__main__":
    apps = check_videocall_apps()
    if apps:
        print("Video call applications are running.")
        # Inizializza e avvia l'agente
        run()  # Utilizzo la funzione run() dell'agent
    else:
        print("No video call applications are running.")
