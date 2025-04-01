import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, MessageHandler, filters, CallbackContext, CallbackQueryHandler, CommandHandler
import openai
import asyncio
import json
import re

# Load API keys from .env file
load_dotenv()
openai.api_key = os.getenv("GROQ_API_KEY")
openai.api_base = "https://api.groq.com/openai/v1"
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Max messages to retain in history
MAX_HISTORY = 10

# Keywords to filter out button responses
IGNORE_BUTTONS = {"hello", "hi", "hey"}

# Store active quizzes
active_quizzes = {}

async def chat_with_groq(update: Update, context: CallbackContext) -> None:
    user_input = update.message.text.lower().strip()
    user_id = update.message.chat_id  # Unique user ID
    
    # Retrieve or initialize user chat history
    user_history = context.user_data.get("messages", {})
    
    if user_id not in user_history:
        user_history[user_id] = [{"role": "system", "content": "You are an AI tutor specializing in education. Provide clear and helpful explanations."}]
    
    # Add user message to history
    user_history[user_id].append({"role": "user", "content": user_input})
    
    # Keep only last MAX_HISTORY messages
    user_history[user_id] = user_history[user_id][-MAX_HISTORY:]
    
    try:
        response = await openai.ChatCompletion.acreate(
            model="llama3-8b-8192",
            messages=user_history[user_id]
        )
        reply = response["choices"][0]["message"]["content"]
        
        # Add AI response to history
        user_history[user_id].append({"role": "assistant", "content": reply})
        context.user_data["messages"] = user_history  # Save updated history
        
    except Exception as e:
        reply = f"Error: {str(e)}"
    
    # Send AI response
    await update.message.reply_text(reply)
    
    # Only show Resources and Quiz buttons if the message is NOT a simple greeting
    if user_input not in IGNORE_BUTTONS:
        keyboard = [
            [InlineKeyboardButton("📚 Resources", callback_data=f"resources_{user_input}")],
            [InlineKeyboardButton("❓ Quiz", callback_data=f"quiz_{user_input}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Would you like learning resources or a quiz on this topic?", reply_markup=reply_markup)

async def handle_buttons(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    
    # Parse the callback data
    callback_data = query.data
    
    # Handle different button types
    if callback_data.startswith("resources_"):
        # Format: resources_topic
        topic = callback_data[10:]
        await generate_resources(query, topic)
        
    elif callback_data.startswith("quiz_"):
        # Format: quiz_topic
        topic = callback_data[5:]
        await generate_quiz(query, context, topic)
        
    elif callback_data.startswith("answer_"):
        # Format: answer_quizId_questionNumber_optionLetter
        parts = callback_data.split("_")
        if len(parts) >= 4:
            quiz_id = parts[1]
            question_number = int(parts[2])
            selected_option = parts[3]
            await check_answer(query, context, quiz_id, question_number, selected_option)
        else:
            await query.message.reply_text("Invalid quiz selection. Please try again.")

async def generate_resources(query, topic):
    try:
        print(f"Fetching resources for topic: {topic}")
        response = await openai.ChatCompletion.acreate(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": f"Provide useful learning resources for {topic}."}
            ]
        )
        resources_text = response["choices"][0]["message"]["content"]
    except Exception as e:
        resources_text = f"Error fetching resources: {str(e)}"
    
    await query.message.reply_text(f"📚 Recommended resources for {topic}:\n{resources_text}")

async def generate_quiz(query, context, topic):
    user_id = query.message.chat_id
    
    # Send a message that the quiz is being generated
    await query.message.reply_text(f"Generating a quiz about {topic}... Please wait a moment.")
    
    try:
        print(f"Generating quiz for topic: {topic}")
        response = await openai.ChatCompletion.acreate(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a quiz creator. Create a quiz with 3 multiple-choice questions."},
                {"role": "user", "content": f"""Create a quiz about {topic} with 3 multiple-choice questions. 
                Each question should have 4 options labeled A, B, C, D with exactly one correct answer. 
                Return ONLY valid JSON with this structure:
                {{
                    "questions": [
                        {{
                            "question": "Question text",
                            "options": ["A. Option A", "B. Option B", "C. Option C", "D. Option D"],
                            "correct": "A"
                        }}
                    ]
                }}"""}
            ]
        )
        
        quiz_text = response["choices"][0]["message"]["content"]
        
        # Extract JSON from the response - handle potential text before/after JSON
        quiz_json = extract_json(quiz_text)
        quiz_data = json.loads(quiz_json)
        
        # Generate unique quiz ID
        quiz_id = f"quiz{user_id}{len(active_quizzes)}"
        
        # Store quiz in memory
        active_quizzes[quiz_id] = {
            "topic": topic,
            "questions": quiz_data["questions"],
            "user_score": 0,
            "current_question": 0,
            "total_questions": len(quiz_data["questions"])
        }
        
        # Send first question
        await send_question(query.message, context, quiz_id, 0)
        
    except Exception as e:
        error_message = f"Error generating quiz: {str(e)}"
        print(error_message)
        await query.message.reply_text(error_message)

def extract_json(text):
    """Extract JSON from text that might contain explanatory text before/after the JSON."""
    try:
        # Try to parse the whole text as JSON first
        json.loads(text)
        return text
    except:
        # If that fails, try to extract JSON object using regex
        json_pattern = r'({[\s\S]*})'
        match = re.search(json_pattern, text)
        if match:
            potential_json = match.group(1)
            try:
                # Verify it's valid JSON
                json.loads(potential_json)
                return potential_json
            except:
                pass
        
        # If regex approach fails, try manual extraction
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > 0:
            potential_json = text[start:end]
            try:
                # Verify it's valid JSON
                json.loads(potential_json)
                return potential_json
            except:
                raise ValueError("Found JSON-like structure but it's not valid JSON")
        
        raise ValueError("No valid JSON found in the response")

async def send_question(message, context, quiz_id, question_number):
    quiz = active_quizzes.get(quiz_id)
    
    if not quiz or question_number >= len(quiz["questions"]):
        await message.reply_text(f"Quiz completed! Your score: {quiz['user_score']}/{quiz['total_questions']}")
        return
    
    question_data = quiz["questions"][question_number]
    question_text = question_data["question"]
    options = question_data["options"]
    
    # Create inline keyboard with options
    keyboard = []
    for option in options:
        # Extract just the letter (A, B, C, D) for the callback data
        option_letter = option[0]
        keyboard.append([InlineKeyboardButton(option, callback_data=f"answer_{quiz_id}_{question_number}_{option_letter}")])
    
    markup = InlineKeyboardMarkup(keyboard)
    
    # Send question with options as buttons
    question_message = f"Question {question_number + 1}/{quiz['total_questions']}:\n\n{question_text}"
    await message.reply_text(question_message, reply_markup=markup)
    print(f"Sent question: {question_message} with keyboard: {keyboard}")

async def check_answer(query, context, quiz_id, question_number, selected_option):
    quiz = active_quizzes.get(quiz_id)
    
    if not quiz:
        await query.message.reply_text("This quiz is no longer active.")
        return
    
    question_data = quiz["questions"][question_number]
    correct_option = question_data["correct"]
    
    # Check if answer is correct
    is_correct = selected_option == correct_option
    
    # Update the quiz message to show the selection was processed
    try:
        await query.edit_message_reply_markup(reply_markup=None)
    except Exception as e:
        print(f"Could not edit message: {e}")
    
    if is_correct:
        quiz["user_score"] += 1
        await query.message.reply_text("✅ Correct!")
    else:
        await query.message.reply_text(f"❌ Incorrect. The correct answer is {correct_option}.")
    
    # Move to next question
    next_question = question_number + 1
    
    if next_question < quiz["total_questions"]:
        await send_question(query.message, context, quiz_id, next_question)
    else:
        # Quiz completed
        final_score = quiz["user_score"]
        total_questions = quiz["total_questions"]
        
        # Final results message
        results_message = f"🎓 Quiz completed!\nYour final score: {final_score}/{total_questions}"
        
        # Add feedback based on score
        if final_score == total_questions:
            results_message += "\n\nPerfect score! Excellent work!"
        elif final_score >= total_questions * 0.7:
            results_message += "\n\nGreat job! You have a good understanding of this topic."
        else:
            results_message += "\n\nKeep learning! Try reviewing the resources and taking the quiz again."
        
        await query.message.reply_text(results_message)
        
        # Delete the quiz from active quizzes to free up memory
        if quiz_id in active_quizzes:
            del active_quizzes[quiz_id]

async def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Welcome to the Educational Bot! Ask me any question, and I'll provide information. "
        "You can also get learning resources and take quizzes on various topics."
    )

def main():
    app = Application.builder().token(TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_with_groq))
    app.add_handler(CallbackQueryHandler(handle_buttons))
    
    print("Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()