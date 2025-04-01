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
    # Create templates directory if it doesn't exist
    
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Create index.html template if it doesn't exist
    if not os.path.exists('templates/index.html'):
        with open('templates/index.html', 'w') as f:
            f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Tutor Chat</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f5f5f5;
        }
        .chat-container {
            max-width: 800px;
            margin: 40px auto;
            background-color: white;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        .chat-header {
            background-color: #4a90e2;
            color: white;
            padding: 15px 20px;
            font-weight: bold;
            font-size: 1.2em;
        }
        .chat-body {
            height: 400px;
            overflow-y: auto;
            padding: 20px;
        }
        .message {
            margin-bottom: 15px;
            padding: 10px 15px;
            border-radius: 5px;
            max-width: 80%;
        }
        .user-message {
            background-color: #e6f2ff;
            margin-left: auto;
        }
        .ai-message {
            background-color: #f0f0f0;
        }
        .input-area {
            padding: 15px;
            border-top: 1px solid #e0e0e0;
            display: flex;
        }
        #message-input {
            flex-grow: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-right: 10px;
        }
        .btn-primary {
            background-color: #4a90e2;
        }
        .btn-outline-secondary {
            color: #4a90e2;
            border-color: #4a90e2;
        }
        .thinking {
            font-style: italic;
            color: #888;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="chat-container">
            <div class="chat-header">
                AI Tutor Chat
            </div>
            <div class="chat-body" id="chat-body">
                <div class="message ai-message">
                    Hello! I'm your AI tutor. How can I help you today?
                </div>
            </div>
            <div class="input-area">
                <input type="text" id="message-input" class="form-control" placeholder="Type your message..." autocomplete="off">
                <button id="send-btn" class="btn btn-primary ms-2">Send</button>
                <button id="reset-btn" class="btn btn-outline-secondary ms-2">Reset</button>
            </div>
        </div>
    </div>

    <script>
        const chatBody = document.getElementById('chat-body');
        const messageInput = document.getElementById('message-input');
        const sendBtn = document.getElementById('send-btn');
        const resetBtn = document.getElementById('reset-btn');
        
        // Generate a unique session ID for this browser session
        const sessionId = Date.now().toString();
        
        function addMessage(content, isUser) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'}`;
            messageDiv.innerText = content;
            chatBody.appendChild(messageDiv);
            chatBody.scrollTop = chatBody.scrollHeight;
        }
        
        function sendMessage() {
            const message = messageInput.value.trim();
            if (message) {
                addMessage(message, true);
                messageInput.value = '';
                
                // Add thinking indicator
                const thinkingDiv = document.createElement('div');
                thinkingDiv.className = 'message ai-message thinking';
                thinkingDiv.innerText = 'Thinking...';
                chatBody.appendChild(thinkingDiv);
                chatBody.scrollTop = chatBody.scrollHeight;
                
                // Send message to backend
                fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        message: message,
                        session_id: sessionId
                    }),
                })
                .then(response => response.json())
                .then(data => {
                    // Remove thinking indicator
                    chatBody.removeChild(thinkingDiv);
                    
                    if (data.error) {
                        addMessage('Error: ' + data.error, false);
                    } else {
                        addMessage(data.reply, false);
                    }
                })
                .catch(error => {
                    // Remove thinking indicator
                    chatBody.removeChild(thinkingDiv);
                    addMessage('Error connecting to server. Please try again.', false);
                    console.error('Error:', error);
                });
            }
        }
        
        function resetConversation() {
            fetch('/reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId
                }),
            })
            .then(response => response.json())
            .then(data => {
                // Clear chat interface
                chatBody.innerHTML = '';
                addMessage('Hello! I\'m your AI tutor. How can I help you today?', false);
            })
            .catch(error => {
                console.error('Error:', error);
            });
        }
        
        sendBtn.addEventListener('click', sendMessage);
        resetBtn.addEventListener('click', resetConversation);
        
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    </script>
</body>
</html>
            ''')
    
if __name__ == '__main__':
    # Create directories and files as before...
    port = 8080  # Using a different port
    app.run(host='0.0.0.0', port=port, debug=True)