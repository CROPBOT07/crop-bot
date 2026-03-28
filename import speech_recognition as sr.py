import speech_recognition as sr
import pyttsx3
from datetime import datetime

# Initialize TTS
engine = pyttsx3.init()
engine.setProperty('rate', 160)

def speak(text):
    print("🤖:", text)
    engine.say(text)
    engine.runAndWait()

# Speech Recognition Setup
recognizer = sr.Recognizer()

def listen():
    with sr.Microphone() as source:
        print("🎤 Listening...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source)

    try:
        command = recognizer.recognize_google(audio, language="en-IN")
        print("👨‍🌾 You said:", command)
        return command.lower()
    except:
        return ""

# Smart AI Logic
def farming_ai(query):
    q = query.lower()

    # Exit
    if any(word in q for word in ["exit", "stop", "bye"]):
        return "Goodbye. Happy farming!"

    # Wheat / Crop Advice
    if "wheat" in q:
        return ("Wheat grows best in cool climates with well-drained loamy soil. "
                "Ideal sowing time is October to December.")

    if any(word in q for word in ["crop", "farming", "what to grow"]):
        return ("It depends on your soil and season. "
                "Right now you can consider seasonal crops like wheat, mustard, or vegetables.")

    # Fertilizer
    if "fertilizer" in q or "manure" in q:
        return ("Use a mix of organic compost and nitrogen-rich fertilizers. "
                "Soil testing can help you choose the right type.")

    # Pest Control
    if any(word in q for word in ["pest", "insect", "bugs", "disease"]):
        return ("You can use neem oil or bio-pesticides. "
                "Early detection is important to prevent spread.")

    # Irrigation
    if any(word in q for word in ["water", "irrigation"]):
        return ("Drip irrigation is efficient and saves water. "
                "Water early morning or late evening.")

    # Weather (placeholder for API integration)
    if "weather" in q:
        return ("I recommend checking today's local forecast before irrigation or spraying. "
                "I can be connected to live weather data soon.")

    # Time / smart touch
    if "time" in q:
        return f"The current time is {datetime.now().strftime('%I:%M %p')}"

    # Help
    if "help" in q:
        return ("You can ask me about crops, fertilizers, pests, irrigation, or weather.")

    return "Sorry, I don't have information on that yet. Try asking about crops or farming practices."

# Main Loop
def main():
    speak("Hello farmer. I am your smart farming assistant. How can I help you?")

    while True:
        query = listen()

        if not query:
            speak("Please say that again.")
            continue

        response = farming_ai(query)
        speak(response)

        if "goodbye" in response.lower():
            break

if __name__ == "__main__":
    main()