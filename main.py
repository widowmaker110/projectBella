import openai
import requests
import os
import speech_recognition as sr
from dotenv import load_dotenv
from tinydb import TinyDB, Query
import json
import time
import pygame

load_dotenv()

# Create a Recognizer object
recognizer = sr.Recognizer()

# Set your API keys here
openai.api_key = os.environ["openai_key"]
playht_api_key = "YOUR_PLAYHT_API_KEY"

db = TinyDB('conversation_history.json')

audio_directory = "audio_files"

def speech_to_text():
    # Use the default microphone as the audio source
    with sr.Microphone() as source:
        print("Say something...")
        audio = recognizer.listen(source)  # Listen for audio input

    try:
        # Recognize the speech using Google Web Speech API
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        print("Sorry, could not understand the audio.")
        return None
    except sr.RequestError as e:
        print(f"Could not request results from Google Web Speech API; {e}")
        return None


def generate_response(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant. You will be providing assistance to people who are scheduling an appointment. My free times are Monday 1PM EST to 3 PM EST."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def get_voices():
    url = "https://play.ht/api/v2/voices"

    headers = {"accept": "application/json",
               'Authorization': "Bearer " + os.environ["playht_secret"],
               'X-User-ID': os.environ["playht_user_id"],
               }

    response = requests.get(url, headers=headers)

    print(response.text)
    for item in json.loads(response.text):
        if item["accent"] == "american" and item["age"] == "adult" and item["gender"] == "female":
            print(item)

def text_to_audio(text):
    url = "https://play.ht/api/v2/tts"

    payload = {
        "quality": "high",
        "output_format": "mp3",
        "speed": 1,
        "sample_rate": 24000,
        "voice": "alphonso",
        "text": text
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        'Authorization': "Bearer " + os.environ["playht_secret"],
        'X-User-ID': os.environ["playht_user_id"]
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        return json.loads(response.text)
    else:
        return None

def get_playht_job(job_id):
    url = "https://play.ht/api/v2/tts/" + job_id

    headers = {
        "accept": "application/json",
        'Authorization':"Bearer " + os.environ["playht_secret"],
        'X-User-ID': os.environ["playht_user_id"],
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        json_value = json.loads(response.text)
        return json_value
    else:
        return None


def download_mp3(url, save_path):
    response = requests.get(url)

    if response.status_code == 200:
        with open(save_path, 'wb') as f:
            f.write(response.content)
        print(f"Downloaded and saved '{save_path}' successfully.")
    else:
        print(f"Failed to download from '{url}'. Status code: {response.status_code}")

def run_speech_detection():
    spoken_text = speech_to_text()

    if spoken_text is None:
        print('couldnt understand what was said')
        run_speech_detection()
    else:
        return spoken_text

def play_mp3(file_path):
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        continue

def main():

    if not os.path.exists(audio_directory):
        os.makedirs(audio_directory)

    # Step 1: Convert speech to text
    spoken_text = run_speech_detection()
    print('you said ', spoken_text)

    # Step 2: Generate response
    response_text = generate_response(spoken_text)
    print("Generated Response:", response_text)

    # Step 3: Convert response to audio
    response_audio = text_to_audio(response_text)
    audio_file = get_playht_job(response_audio["id"])

    while audio_file["output"] is None:
        time.sleep(2)
        audio_file = get_playht_job(response_audio["id"])

    audio_file_location = audio_file["output"]["url"]

    download_mp3(url=audio_file_location, save_path=os.path.join(audio_directory, "response_audio.mp3"))

    play_mp3(os.path.join(audio_directory, "response_audio.mp3"))

if __name__ == "__main__":
    main()
