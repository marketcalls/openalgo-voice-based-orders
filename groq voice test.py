import pyaudio
import threading
import os
import queue
import time
from dotenv import load_dotenv
from word2number import w2n
from openalgo.orders import api
from groq import Groq
import tempfile
import wave
import string

# Load environment variables from .env file
load_dotenv()

# Configure the audio stream
audio = pyaudio.PyAudio()
stream = audio.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    frames_per_buffer=1024,
)

# Groq client setup
groq_client = Groq(api_key=os.getenv('GROQ_API_KEY'))

# OpenAlgo client setup
openalgo_client = api(api_key=os.getenv('OPENALGO_API_KEY'), host=os.getenv('OPENALGO_HOST'))

# Get the Voice Activation Command
voice_activate_command = os.getenv('VOICE_ACTIVATE_COMMAND')

# Command synonyms to handle speech recognition variations
command_synonyms = {
    "bhai": "BUY",  "bi": "BUY",
    "by": "BUY",    "bye": "BUY",
    "buy": "BUY",   "cell": "SELL",
    "cel": "SELL",  "self": "SELL",
    "sale": "SELL", "sel": "SELL",
    "sell": "SELL"
}

def save_audio_to_file(audio_data, filename):
    wf = wave.open(filename, 'wb')
    wf.setnchannels(1)
    wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
    wf.setframerate(16000)
    wf.writeframes(b''.join(audio_data))
    wf.close()

def read_audio_data(audio_queue, stop_event):
    try:
        while not stop_event.is_set():
            data = stream.read(1024, exception_on_overflow=False)
            audio_queue.put(data)
    except Exception as e:
        print(f"Error reading audio data: {str(e)}")

def remove_punctuation(text):
    # Create a translation table that maps all punctuation characters to None
    translator = str.maketrans('', '', string.punctuation)
    # Use the translation table to remove punctuation
    return text.translate(translator)

def transcribe_audio(audio_data):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        save_audio_to_file(audio_data, temp_file.name)
        with open(temp_file.name, "rb") as file:
            transcription = groq_client.audio.transcriptions.create(
                file=(temp_file.name, file.read()),
                model="whisper-large-v3",
                language="en",
                response_format="verbose_json",
            )
    os.unlink(temp_file.name)
    # Remove punctuation from the transcription text
    return remove_punctuation(transcription.text)

def parse_command(transcript):
    words = transcript.upper().split()
    try:
        if voice_activate_command in words:
            action_index = words.index(voice_activate_command) + 1
            action = command_synonyms.get(words[action_index].lower(), words[action_index])
            try:
                quantity = int(words[action_index + 1])
            except ValueError:
                quantity = w2n.word_to_num(words[action_index + 1].lower())
            if not words[-1]:
                print("Error: Trading symbol is missing from the command.")
                return None, None, None
            tradingsymbol = words[-1]
            print(f'Action : {action}')
            print(f'Quantity : {quantity}')
            print(f'Symbol : {tradingsymbol}')
            return action, quantity, tradingsymbol
    except ValueError as ve:
        print(f"Error parsing command, check format: {str(ve)}")
    except IndexError as ie:
        print(f"Error parsing command, parts of the command might be missing: {str(ie)}")
    return None, None, None

def handle_audio(audio_queue, stop_event):
    audio_buffer = []
    silence_threshold = 500  # Adjust this value to change sensitivity
    silence_duration = 0
    try:
        while not stop_event.is_set():
            if not audio_queue.empty():
                data = audio_queue.get()
                audio_buffer.append(data)
                if max(abs(int.from_bytes(data[i:i+2], byteorder='little', signed=True)) for i in range(0, len(data), 2)) < silence_threshold:
                    silence_duration += 1
                else:
                    silence_duration = 0
                
                if silence_duration > 30:  # About 1 second of silence
                    if len(audio_buffer) > 50:  # Ensure we have enough audio data
                        transcript = transcribe_audio(audio_buffer)
                        print(f"Transcribed: {transcript}")
                        action, quantity, tradingsymbol = parse_command(transcript)
                        if all([action, quantity, tradingsymbol]):
                            place_order(action, quantity, tradingsymbol)
                    audio_buffer = []
                    silence_duration = 0
            else:
                time.sleep(0.1)
    except Exception as e:
        print(f"Error handling audio: {str(e)}")

def place_order(action, quantity, tradingsymbol):
    response = openalgo_client.placeorder(
        strategy="VoiceOrder",
        symbol=tradingsymbol,
        action=action,
        exchange="NSE",
        price_type="MARKET",
        product="MIS",
        quantity=quantity
    )
    print(f"Order placed: {response}")

def main():
    stop_event = threading.Event()
    audio_queue = queue.Queue()
    audio_thread = threading.Thread(target=lambda: read_audio_data(audio_queue, stop_event), daemon=True)
    processing_thread = threading.Thread(target=lambda: handle_audio(audio_queue, stop_event), daemon=True)
    audio_thread.start()
    processing_thread.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Received KeyboardInterrupt, shutting down...")
        stop_event.set()
        audio_thread.join()
        processing_thread.join()
        stream.stop_stream()
        stream.close()
        audio.terminate()
        exit()

if __name__ == '__main__':
    main()