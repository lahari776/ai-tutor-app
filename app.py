import os
from flask import Flask, render_template, request, jsonify
import openai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up OpenAI with Groq
openai.api_key = os.getenv("GROQ_API_KEY")
openai.api_base = "https://api.groq.com/openai/v1"

app = Flask(__name__)

# Store conversation history
conversation_history = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    # Initialize conversation history for this session if it doesn't exist
    if session_id not in conversation_history:
        conversation_history[session_id] = [
            {"role": "system", "content": "You are an AI tutor specializing in education. Provide clear and helpful explanations."}
        ]
    
    # Add user message to history
    conversation_history[session_id].append({"role": "user", "content": user_input})
    
    try:
        # Get response from Groq
        response = openai.ChatCompletion.create(
            model="llama3-8b-8192",  # Change model if needed
            messages=conversation_history[session_id]
        )
        
        reply = response["choices"][0]["message"]["content"]
        
        # Add assistant response to history
        conversation_history[session_id].append({"role": "assistant", "content": reply})
        
        return jsonify({"reply": reply})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/reset', methods=['POST'])
def reset_conversation():
    data = request.json
    session_id = data.get('session_id', 'default')
    
    # Reset conversation for this session
    conversation_history[session_id] = [
        {"role": "system", "content": "You are an AI tutor specializing in education. Provide clear and helpful explanations."}
    ]
    
    return jsonify({"message": "Conversation reset successfully"})

if __name__ == '__main__':
    # Get port from environment variable or use 8080 as default
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, debug=True)