import os
import csv
import datetime
import shutil
import tempfile

DATA_DIR = "data"

def get_history_file_path(university):
    """
    Get the CSV file path for the given university.
    """
    uni_map = {
        "todai": "utokyo",
        "kyoto": "kyotou",
        "osaka": "osakau"
    }
    uni_suffix = uni_map.get(university, university)
    return os.path.join(DATA_DIR, f"history_{uni_suffix}.csv")

def ensure_history_file(university):
    """
    Ensure the history CSV file exists with the header.
    """
    file_path = get_history_file_path(university)
    if not os.path.exists(file_path):
        try:
            with open(file_path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                # Date, No, Title, Topic, YouTube_Status, VideoID
                writer.writerow(["Date", "No", "Title", "Topic", "YouTube_Status", "VideoID"])
        except Exception as e:
            print(f"Error initializing history file: {e}")
    return file_path

def get_next_episode_number(university):
    """
    Get the next episode number (No) for the university.
    Returns 1 if no history exists.
    """
    file_path = ensure_history_file(university)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            # Use manual parsing if DictReader is empty or malformed
            rows = list(reader)
            if not rows:
                return 1
            
            # Find the max No
            max_no = 0
            for row in rows:
                try:
                    no_str = row.get("No", "0")
                    if no_str and no_str.isdigit():
                        no = int(no_str)
                        if no > max_no:
                            max_no = no
                except ValueError:
                    continue
            return max_no + 1
    except Exception as e:
        print(f"Error reading history file: {e}")
        return 1

def get_past_topics(university):
    """
    Get a list of past topics for the university to avoid duplication.
    """
    file_path = ensure_history_file(university)
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [row["Topic"] for row in reader if row.get("Topic")]
    except Exception:
        return []

def save_exam_history(university, title, topic, youtube_status="Generated", video_id=""):
    """
    Save the generation history to the CSV file.
    """
    file_path = ensure_history_file(university)
    
    # Re-calculate next_no to be safe (concurrent writes are unlikely but good practice)
    next_no = get_next_episode_number(university)
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    try:
        # Check if header has VideoID, if not, we might need to migrate, 
        # but for simplicity, we just append if possible or rewrite.
        # However, 'a' mode just appends. If header is old, new row will have extra column.
        # This is messy. Let's check header first.
        has_videoid = False
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header and "VideoID" in header:
                has_videoid = True
        
        # If missing VideoID in header, we should probably rewrite the file or just append and hope for the best?
        # A cleaner way is to read all, add column, rewrite.
        if not has_videoid:
            # Migration logic
            temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, encoding="utf-8", newline="")
            with open(file_path, 'r', encoding="utf-8") as csvfile, temp_file:
                reader = csv.DictReader(csvfile)
                fieldnames = reader.fieldnames + ["VideoID"]
                writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
                writer.writeheader()
                for row in reader:
                    row["VideoID"] = ""
                    writer.writerow(row)
            shutil.move(temp_file.name, file_path)

        with open(file_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([today, next_no, title, topic, youtube_status, video_id])
        print(f"History saved for {university}: No.{next_no} - {title}")
        return next_no
    except Exception as e:
        print(f"Error saving history: {e}")
        return None

def update_history_status(university, title, new_status="Uploaded", video_id=None):
    """
    Update the YouTube_Status and optionally VideoID for a given title.
    """
    file_path = get_history_file_path(university)
    if not os.path.exists(file_path):
        return False

    temp_file = tempfile.NamedTemporaryFile(mode='w', delete=False, encoding="utf-8", newline="")
    updated = False
    
    try:
        with open(file_path, 'r', encoding="utf-8") as csvfile, temp_file:
            reader = csv.DictReader(csvfile)
            fieldnames = list(reader.fieldnames)
            
            # Ensure VideoID is in fieldnames
            if "VideoID" not in fieldnames:
                fieldnames.append("VideoID")
            
            writer = csv.DictWriter(temp_file, fieldnames=fieldnames)
            writer.writeheader()
            
            for row in reader:
                if row['Title'] == title:
                    row['YouTube_Status'] = new_status
                    if video_id:
                        row['VideoID'] = video_id
                    updated = True
                
                # Ensure VideoID key exists
                if "VideoID" not in row:
                    row["VideoID"] = ""
                    
                writer.writerow(row)
        
        shutil.move(temp_file.name, file_path)
        return updated
    except Exception as e:
        print(f"Error updating history: {e}")
        return False
