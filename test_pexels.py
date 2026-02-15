
import os
import requests
import random
from dotenv import load_dotenv

load_dotenv()

def download_pexels_video(query: str, output_path: str = "background_video.mp4", orientation: str = "landscape"):
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        print("PEXELS_API_KEY not found.")
        return None
        
    print(f"Searching Pexels video for: {query} ({orientation})")
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation={orientation}"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Response status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response text: {response.text}")
            
        response.raise_for_status()
        data = response.json()
        
        if not data.get("videos"):
            print("No videos found.")
            return None
            
        video_data = random.choice(data["videos"])
        video_files = video_data.get("video_files", [])
        
        target_files = [f for f in video_files if f.get("width") >= 1280 and f.get("quality") == "hd"]
        if not target_files:
            target_files = video_files
            
        if not target_files:
            print("No suitable video files found.")
            return None
            
        best_file = sorted(target_files, key=lambda x: abs(x.get("width", 0) - 1920))[0]
        download_url = best_file.get("link")
        
        print(f"Downloading from: {download_url}")
        
        v_resp = requests.get(download_url, stream=True, timeout=30)
        v_resp.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in v_resp.iter_content(chunk_size=8192):
                f.write(chunk)
                
        print(f"Saved to: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error: {e}")
        return None

if __name__ == "__main__":
    download_pexels_video("Cyberpunk Abstract")
