import os
import json
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_user_data(user_id):
    """
    Fetches user data from Supabase and returns it as a dict
    """
    # Get current date in Asia/Kolkata timezone
    local_time = datetime.now(pytz.timezone("Asia/Kolkata"))
    today = local_time.date()
    three_days_ago = today - timedelta(days=3)
    
    # Format dates for database query
    today_str = today.isoformat()
    three_days_ago_str = three_days_ago.isoformat()
    
    try:
        # Fetch today's tasks
        tasks_res = supabase \
            .from_("Tasks") \
            .select("taskName,taskStatus,priority,date") \
            .eq("user_id", user_id) \
            .eq("date", today_str) \
            .execute()
        
        # If no tasks for today, try getting all tasks for the user
        if not tasks_res.data:
            tasks_res = supabase \
                .from_("Tasks") \
                .select("taskName,taskStatus,priority,date") \
                .eq("user_id", user_id) \
                .execute()
        
        # Fetch recent mood logs
        mood_res = supabase \
            .from_("Mood_Logs") \
            .select("*") \
            .eq("user_id", user_id) \
            .gte("created_at", three_days_ago_str) \
            .order("created_at", desc=True) \
            .limit(5) \
            .execute()
        
        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "today": today_str,
            "tasks": tasks_res.data,
            "moods": mood_res.data
        }
    
    except Exception as e:
        print(f"Error fetching data for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "error": str(e)
        }

def save_user_data(user_id, data):
    """
    Saves user data to a JSON file
    """
    # Create data directory if it doesn't exist
    data_dir = "user_data"
    os.makedirs(data_dir, exist_ok=True)
    
    # Save data to file
    filepath = os.path.join(data_dir, f"{user_id}.json")
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Data saved to {filepath}")
    return filepath

def fetch_and_save_all_users():
    """
    Fetches data for all users and saves it to JSON files
    """
    try:
        # Get all unique user IDs from Tasks table
        users_res = supabase \
            .from_("Tasks") \
            .select("user_id") \
            .execute()
        
        user_ids = set()
        for item in users_res.data:
            user_ids.add(item.get("user_id"))
        
        # Also check Mood_Logs table for any additional users
        mood_users_res = supabase \
            .from_("Mood_Logs") \
            .select("user_id") \
            .execute()
        
        for item in mood_users_res.data:
            user_ids.add(item.get("user_id"))
        
        print(f"Found {len(user_ids)} unique users")
        
        # Fetch and save data for each user
        results = []
        for user_id in user_ids:
            if not user_id:
                continue
                
            print(f"Fetching data for user {user_id}")
            user_data = fetch_user_data(user_id)
            filepath = save_user_data(user_id, user_data)
            results.append({
                "user_id": user_id,
                "status": user_data["status"],
                "filepath": filepath
            })
        
        return results
    
    except Exception as e:
        print(f"Error fetching all users: {str(e)}")
        return {"error": str(e)}

def fetch_and_save_user(user_id):
    """
    Fetches data for a specific user and saves it to a JSON file
    """
    print(f"Fetching data for user {user_id}")
    user_data = fetch_user_data(user_id)
    filepath = save_user_data(user_id, user_data)
    return {
        "user_id": user_id,
        "status": user_data["status"],
        "filepath": filepath,
        "data": user_data
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Fetch data for a specific user
        user_id = sys.argv[1]
        result = fetch_and_save_user(user_id)
        print(f"Result: {result}")
    else:
        # Fetch data for all users
        results = fetch_and_save_all_users()
        print(f"Results: {results}")