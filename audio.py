import pyaudio
import numpy as np
import time
import threading
import wave
from typing import Callable

# Non importiamo direttamente la funzione qui per evitare importazioni circolari,
# la importeremo solo dove necessario


class AudioMonitor:
    def __init__(
        self,
        process_function: Callable[[np.ndarray, int], None],
        silence_threshold: int = 500,  # Modificato per int16
        max_segment_duration: float = 20.0,  # 2 minuti in secondi
        min_segment_duration: float = 7.0,  # Lunghezza minima del batch in secondi
        sample_rate: int = 44100,
        chunk_size: int = 1024,
        channels: int = 1,
        notification_callback=None,
    ):
        self.process_function = process_function
        self.silence_threshold = silence_threshold
        self.max_segment_duration = max_segment_duration
        self.min_segment_duration = min_segment_duration  # Nuovo parametro
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.notification_callback = notification_callback

        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.current_buffer = np.array([], dtype=np.int16)
        self.last_active_time = 0
        self.recording = False
        self.last_process_time = time.time()
        self.recording_start_time = None

    def start_monitoring(self, device_index=None):
        """Avvia il monitoraggio audio dal microfono e dagli altoparlanti"""
        if self.recording:
            print("Monitoraggio audio già attivo")
            return

        self.recording = True
        self.recording_start_time = time.time()

        # Ottieni il dispositivo di input predefinito se non specificato
        if device_index is None:
            try:
                device_info = self.audio.get_default_input_device_info()
                device_index = device_info["index"]
            except:
                print(
                    "Impossibile ottenere il dispositivo di input predefinito. Utilizzo del dispositivo 0."
                )
                device_index = 0

        try:
            # Ottieni informazioni sul dispositivo per verificare i canali supportati
            device_info = self.audio.get_device_info_by_index(device_index)
            max_channels = int(device_info["maxInputChannels"])

            # Aggiusta il numero di canali se necessario
            if self.channels > max_channels:
                print(
                    f"Il dispositivo supporta solo {max_channels} canali, modificando da {self.channels}"
                )
                self.channels = max_channels

            # Verifica se il sample rate è supportato
            if self.sample_rate != int(device_info["defaultSampleRate"]):
                print(
                    f"Nota: Il sample rate predefinito del dispositivo è {int(device_info['defaultSampleRate'])}Hz"
                )

            # Apri lo stream audio per l'input
            self.stream = self.audio.open(
                format=pyaudio.paInt16,  # Modificato da paFloat32 a paInt16
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback,
            )

            print(
                f"Avviato monitoraggio audio sul dispositivo {device_index}: {device_info['name']}"
            )
            print(
                f"Utilizzo di {self.channels} canale/i, {self.sample_rate}Hz sample rate"
            )
            print(f"Lunghezza minima batch: {self.min_segment_duration} secondi")
            print(f"Lunghezza massima batch: {self.max_segment_duration} secondi")
            print("Premi Ctrl+C per interrompere.")

        except Exception as e:
            self.recording = False
            print(f"Errore nell'avvio dello stream audio: {e}")
            print(
                "Prova a eseguire monitor.list_devices() prima per verificare i dispositivi disponibili"
            )
            raise

    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Chiamato per ogni buffer audio catturato da PyAudio"""
        if not self.recording:
            return (None, pyaudio.paComplete)

        # Converti il buffer in un array numpy
        audio_data = np.frombuffer(in_data, dtype=np.int16)  # Modificato a int16

        # Aggiungi al buffer corrente
        self.current_buffer = np.append(self.current_buffer, audio_data)

        # Verifica se dovremmo processare in base al tempo o al silenzio
        self._check_for_processing()

        return (None, pyaudio.paContinue)

    def _check_for_processing(self):
        """Verifica se dobbiamo processare il buffer corrente in base al tempo o al silenzio"""
        current_time = time.time()

        # Calcola la durata attuale del buffer in secondi
        buffer_duration = len(self.current_buffer) / (self.sample_rate * self.channels)

        # Controlla il silenzio (forma d'onda piatta)
        if len(self.current_buffer) >= self.chunk_size:
            # Calcola RMS (root mean square) per rilevare il silenzio
            rms = np.sqrt(
                np.mean(
                    np.square(
                        self.current_buffer[-self.chunk_size :].astype(np.float32)
                    )
                )
            )

            # Se l'audio è attivo, aggiorna il tempo dell'ultima attività
            if rms > self.silence_threshold:
                self.last_active_time = current_time

            # Processa se rileviamo silenzio dopo attività E il buffer ha la durata minima richiesta
            silence_duration = current_time - self.last_active_time
            if (
                silence_duration > 0.5
                and rms <= self.silence_threshold
                and buffer_duration >= self.min_segment_duration
            ):
                self._process_current_buffer()

        # Processa in base alla durata massima del segmento
        time_since_last_process = current_time - self.last_process_time
        if (
            time_since_last_process >= self.max_segment_duration
            and buffer_duration >= self.min_segment_duration
        ):
            self._process_current_buffer()

    def _process_current_buffer(self):
        """Invia il buffer audio corrente alla funzione di elaborazione e reimposta il buffer"""
        if len(self.current_buffer) == 0:
            return

        # Calcola la durata del buffer in secondi
        buffer_duration = len(self.current_buffer) / (self.sample_rate * self.channels)

        # Controlla la durata minima
        if buffer_duration < self.min_segment_duration:
            # Se il buffer è troppo breve, non lo processiamo ancora
            return

        # Elabora i dati audio in un thread separato per evitare il blocco
        buffer_to_process = self.current_buffer.copy()
        threading.Thread(
            target=self.process_function, args=(buffer_to_process, self.sample_rate, self.notification_callback)
        ).start()

        # Reimposta il buffer e aggiorna il tempo dell'ultimo processo
        self.current_buffer = np.array([], dtype=np.int16)  # Modificato a int16
        self.last_process_time = time.time()

    def stop_monitoring(self):
        """Interrompi il monitoraggio audio"""
        if not self.recording:
            return

        self.recording = False

        # Elabora l'audio rimanente se soddisfa la lunghezza minima
        buffer_duration = len(self.current_buffer) / (self.sample_rate * self.channels)
        if (
            len(self.current_buffer) > 0
            and buffer_duration >= self.min_segment_duration
        ):
            self._process_current_buffer()

        # Chiudi lo stream e termina PyAudio
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        self.audio.terminate()
        print("Monitoraggio audio interrotto")


# Esempio di utilizzo
def process(audio_data: np.ndarray, sample_rate: int, notification_callback=None):
    """Funzione di esempio per l'elaborazione"""
    duration = len(audio_data) / (sample_rate)
    print(f"Elaborazione di {duration:.2f} secondi di dati audio")

    # Crea la directory file/audio se non esiste
    import os

    audio_dir = os.path.join("output", "audio")
    os.makedirs(audio_dir, exist_ok=True)

    # Salva come file WAV senza conversioni (già in formato int16)
    timestamp = int(time.time())
    filename = f"audio_segment_{timestamp}.wav"
    filepath = os.path.join(audio_dir, filename)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)  # Mono
        wf.setsampwidth(2)  # Int16 = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())

    print(f"Audio salvato come {filepath}")

    # Importiamo process_audio_file qui per evitare importazioni circolari
    from agents.call_assistant_agent.agent import process_audio_file
    
    # Processiamo il file audio (il callback globale è già impostato in main.py)
    process_audio_file(filepath)


if __name__ == "__main__":
    try:
        # Crea il monitor audio
        monitor = AudioMonitor(
            process_function=process,
            min_segment_duration=2.0,  # Imposta la durata minima del batch a 2 secondi
        )

        monitor.start_monitoring()

        # Mantieni il thread principale in esecuzione
        while True:
            time.time()
            time.sleep(0.1)

    except KeyboardInterrupt:
        print("\nInterruzione...")
        if "monitor" in locals():
            monitor.stop_monitoring()
