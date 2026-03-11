import requests

def test_api():
    url = "http://localhost:5001/api/notifications"
    headers = {"X-User-ID": "3"}
    try:
        r = requests.get(url, headers=headers)
        print(f"Status: {r.status_code}")
        print(f"Body: {r.json()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_api()
