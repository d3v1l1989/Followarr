import requests
import sys
import os

def send_test_notification(show_id):
    # Sample payload that mimics a Tautulli webhook for a new episode
    payload = {
        "event": "media.added",
        "media_type": "episode",
        "tvdb_id": show_id,
        "title": "Test Show",
        "episode_name": "New Episode",
        "season_num": "1",
        "episode_num": "1",
        "summary": "This is a test episode notification",
        "air_date": "2024-04-08",
        "poster_url": "https://artworks.thetvdb.com/banners/posters/12345-1.jpg"
    }

    try:
        response = requests.post(
            "http://localhost:3000/webhook/tautulli",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_notification.py <show_id>")
        sys.exit(1)
    
    show_id = sys.argv[1]
    send_test_notification(show_id) 