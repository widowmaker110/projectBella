import openai
import requests
import os
import speech_recognition as sr
from dotenv import load_dotenv
from tinydb import TinyDB, Query
import json
import time
import pygame
import uuid

load_dotenv()

# Create a Recognizer object
recognizer = sr.Recognizer()

# Set your API keys here
openai.api_key = os.environ["openai_key"]

# Set the NOSQL storage unit for the conversation
db = TinyDB('conversation_history.json')

# Directory for storing the audio
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


def generate_response_chatGPT(history):

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=history["messages"]
    )
    return response.choices[0].message.content.strip()


def text_to_audio(text):
    url = "https://play.ht/api/v2/tts"

    payload = {
        "quality": "premium",
        "output_format": "mp3",
        "speed": 1,
        "seed": 4,
        "sample_rate": 24000,
        "voice": "victor",
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
        'Authorization': "Bearer " + os.environ["playht_secret"],
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


def get_conversation_by_id(conversation_id):
    # Query the database to find the record with the given conversation_id
    conversation = Query()
    result = db.get(conversation.conversation_id == conversation_id)

    if result:
        return json.loads(json.dumps(result, indent=4))
    else:
        return None


def upsert_history(conversation_id, role, message):

    conversation = get_conversation_by_id(conversation_id)

    if conversation is None:
        conversation = {
            "conversation_id" : conversation_id,
            "messages": [{'role': 'system', 'content': os.environ["prompt_engineering"]}]
        }

    conversation["messages"].append({'role': role, 'content': message})

    item_query = Query()
    existing_item = db.get(item_query.conversation_id == conversation_id)

    if existing_item:
        db.update(conversation, item_query.conversation_id == conversation_id)
    else:
        db.insert(conversation)


def main():

    program_state = "Setting up"

    # Generate a UUID for the conversation
    conversation_id = str(uuid.uuid4())

    if not os.path.exists(audio_directory):
        os.makedirs(audio_directory)

    while True:
        # Step 1: Convert speech to text
        program_state = "Waiting on User input"
        spoken_text = run_speech_detection()
        print('%%% You said ', spoken_text)

        upsert_history(conversation_id, 'user', spoken_text)

        # Step 2: Generate response
        program_state = "Waiting on ChatGPT output"
        response_text = generate_response_chatGPT(get_conversation_by_id(conversation_id))
        print("%%% Generated Response:", response_text)

        # Step 3: Upsert local conversation history
        upsert_history(conversation_id, 'system', response_text)

        # Step 4: Convert response to audio
        program_state = "Converting text to audio"
        response_audio = text_to_audio(response_text)
        audio_file = get_playht_job(response_audio["id"])

        while audio_file["output"] is None:
            # higher the grade audio, the longer it takes to populate. Keep trying until you get it
            time.sleep(2)
            audio_file = get_playht_job(response_audio["id"])

        # Step 5: Download the audio
        program_state = "Downloading audio"
        audio_file_location = audio_file["output"]["url"]
        download_mp3(url=audio_file_location, save_path=os.path.join(audio_directory, "response_audio.mp3"))

        # Step 6: Play the audio to the end user
        program_state = "Playing audio"
        play_mp3(os.path.join(audio_directory, "response_audio.mp3"))

if __name__ == "__main__":
    main()
