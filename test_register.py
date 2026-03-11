import requests
import json

url = "http://127.0.0.1:5001/register"
payload = {
    "username": "sherica",
    "email": "shericajoseph21@gmail.com",
    "phone": "9788893245",
    "password": "Password123!",
    "role": "employee"
}
headers = {
    'Content-Type': 'application/json'
}

try:
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
