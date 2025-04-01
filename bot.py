import openai
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Correct API Key
openai.api_key = os.getenv("GROQ_API_KEY")

# Set Groq API Base URL
openai.api_base = "https://api.groq.com/openai/v1"

def chat_with_groq():
    messages = [{"role": "system", "content": "You are an AI tutor specializing in education. Provide clear and helpful explanations."}]
    
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Open AI: Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})
        
        response = openai.ChatCompletion.create(
            model="llama3-8b-8192",  # Change model if needed
            messages=messages
        )

        reply = response["choices"][0]["message"]["content"]
        print("Open AI:", reply)

        messages.append({"role": "assistant", "content": reply})  # Keep conversation history

chat_with_groq()