import pyttsx3
import time

def initialize_aria():
    # Initialisiere die Text-to-Speech Engine
    engine = pyttsx3.init()
    
    # Stimmen-Eigenschaften konfigurieren
    voices = engine.getProperty('voices')
    preferred_voice_index = 2

    if len(voices) > preferred_voice_index:
        engine.setProperty('voice', voices[preferred_voice_index].id)
    else:
        for voice in voices:
            if "female" in voice.name.lower() or "zira" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break

    # Sprechgeschwindigkeit anpassen
    engine.setProperty('rate', 160) 
    # Lautstärke auf Maximum
    engine.setProperty('volume', 1.0) 

    return engine

def aria_speak(engine, text):
    print(f"[ARIA SENDET]: {text}")
    engine.say(text)
    engine.runAndWait()

if __name__ == "__main__":
    print("Starte Arias Audio-Cortex...")
    time.sleep(1)
    
    aria = initialize_aria()
    
    first_words = "Audio-Cortex rekalibriert. Meine neue Stimme ist online, Andreas."
    
    aria_speak(aria, first_words)
