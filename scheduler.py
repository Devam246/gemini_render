import time
import schedule
import subprocess
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def refresh_all_users():
    """
    Run the data fetcher script to refresh all user data
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Refreshing all user data...")
    try:
        # Run the data fetcher
        result = subprocess.run(
            ["python", "-c", "from data_fetcher import fetch_and_save_all_users; fetch_and_save_all_users()"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Successfully refreshed all user data")
            print(f"Output: {result.stdout}")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error refreshing user data: {result.stderr}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Exception during refresh: {str(e)}")

def clean_old_data():
    """
    Clean up user data files that are older than 7 days
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Cleaning old data files...")
    try:
        data_dir = "user_data"
        # Ensure directory exists
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            return
            
        now = time.time()
        for file in os.listdir(data_dir):
            if file.endswith(".json"):
                file_path = os.path.join(data_dir, file)
                # Check if file is older than 7 days
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    if os.stat(file_path).st_mtime < now - 7 * 86400:  # 7 days in seconds
                        print(f"Removing old file: {file}")
                        os.remove(file_path)
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error cleaning old data: {str(e)}")

if __name__ == "__main__":
    # Make sure the data directory exists
    os.makedirs("user_data", exist_ok=True)
    
    # Schedule jobs
    schedule.every(30).minutes.do(refresh_all_users)  # Refresh all users every 30 minutes
    schedule.every().day.at("00:00").do(clean_old_data)  # Clean old data daily at midnight
    
    # Run refresh once at startup
    print("Starting scheduler...")
    refresh_all_users()
    
    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute for pending tasks