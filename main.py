import os
import json
from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import google.generativeai as genai
from datetime import datetime, timedelta
import pytz
import subprocess
import time

# Import the data fetcher module
from data_fetcher import fetch_and_save_user

# Load environment variables
load_dotenv()

# Store chat sessions
chat_sessions = {}

# Gemini API setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

# FastAPI app
app = FastAPI(title="Task Assistant API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    user_id: str

# System prompt
system_prompt = """
You are a friendly, motivating assistant. You help the user manage their tasks and emotions.
Speak like a supportive friend:
- Be kind, energetic, and inspiring.
- If the user is overwhelmed, offer small steps and cheer them up.
- If they're doing well, celebrate them!
Do not write big messages as reply keep it short and friendly.
"""

def get_user_data_from_json(user_id):
    """
    Read user data from JSON file
    """
    data_dir = "user_data"
    filepath = os.path.join(data_dir, f"{user_id}.json")
    
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                data = json.load(f)
                
            # Check if the data is fresh (less than 10 minutes old)
            timestamp = datetime.fromisoformat(data.get("timestamp", ""))
            now = datetime.now()
            
            # If data is more than 10 minutes old, return None to trigger refresh
            if (now - timestamp).total_seconds() > 600:  # 10 minutes
                print(f"Data for user {user_id} is stale, will refresh")
                return None
                
            return data
        else:
            return None
    except Exception as e:
        print(f"Error reading user data from JSON: {str(e)}")
        return None

def refresh_user_data_background(user_id):
    """
    Background task to refresh user data
    """
    try:
        fetch_and_save_user(user_id)
        print(f"User data refreshed for {user_id}")
    except Exception as e:
        print(f"Error refreshing user data: {str(e)}")

@app.post("/chat")
async def chat(req: ChatRequest, background_tasks: BackgroundTasks):
    """
    Handle chat requests from users
    """
    user_id = req.user_id
    
    # Try to get user data from JSON file
    user_data = get_user_data_from_json(user_id)
    
    if not user_data:
        # If no data file exists or data is stale, fetch data synchronously the first time
        try:
            result = fetch_and_save_user(user_id)
            user_data = result.get("data")
        except Exception as e:
            print(f"Error fetching user data: {str(e)}")
            user_data = {
                "status": "error",
                "tasks": [],
                "moods": []
            }
    else:
        # If data file exists, trigger background refresh for next time
        background_tasks.add_task(refresh_user_data_background, user_id)
    
    # Format tasks for display
    if user_data and user_data.get("status") == "success":
        tasks = user_data.get("tasks", [])
        moods = user_data.get("moods", [])
        
        # Format tasks string
        if tasks:
            tasks_str = "\n".join([
                f"- {task['taskName']} ({'✅ Done' if task.get('taskStatus', False) else '❌ Not done'}) "
                f"[Priority: {task.get('priority', 'Normal')}]"
                for task in tasks
            ])
        else:
            tasks_str = "No tasks scheduled for today."
        
        # Format moods string
        if moods:
            moods_str = "\n".join([
                f"- {log.get('mood', 'Unknown')} (Intensity: {log.get('intensity', 'Unknown')}) "
                f"on {log.get('created_at', '')[:10]}"
                for log in moods
            ])
        else:
            moods_str = "No mood logs in the past 3 days."
    else:
        tasks_str = "Could not retrieve tasks at this time."
        moods_str = "Could not retrieve mood logs at this time."
    
    # Create or get chat session
    if user_id not in chat_sessions:
        chat_sessions[user_id] = model.start_chat()
        print(f"Created new chat session for user {user_id}")
    else:
        # Check if session is too old (30+ minutes) and refresh if needed
        if hasattr(chat_sessions[user_id], 'last_used') and time.time() - chat_sessions[user_id].last_used > 1800:
            chat_sessions[user_id] = model.start_chat()
            print(f"Refreshed chat session for user {user_id}")
    
    chat = chat_sessions[user_id]
    # Add timestamp to track session age
    chat.last_used = time.time()

    # Add dynamic context
    context_prompt = f"""
{system_prompt}

Your recent mood check-ins:
{moods_str}

Your tasks for today:
{tasks_str}

User says:
{req.message}
"""

    try:
        # Send message to Gemini
        response = chat.send_message(
            context_prompt, 
            generation_config={
                "max_output_tokens": 100,
                "temperature": 0.7,
                "top_p": 0.95,
            }
        )
        return {"reply": response.text}
    except Exception as e:
        print(f"Gemini error: {str(e)}")
        return {"reply": f"I'm having trouble connecting to my brain right now. Please try again in a moment!"}

@app.get("/refresh-data/{user_id}")
async def refresh_data(user_id: str):
    """
    Manually refresh data for a user
    """
    try:
        result = fetch_and_save_user(user_id)
        return {
            "status": "success",
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/refresh-all-users")
async def refresh_all_users(background_tasks: BackgroundTasks):
    """
    Manually trigger a refresh for all users
    """
    # Run the data fetcher script in the background
    background_tasks.add_task(
        lambda: subprocess.run(["python", "-c", "from data_fetcher import fetch_and_save_all_users; fetch_and_save_all_users()"])
    )
    
    return {
        "status": "success",
        "message": "Refreshing all user data in the background"
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }

# Create the user_data directory
os.makedirs("user_data", exist_ok=True)

# This is for local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)