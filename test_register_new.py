import requests
import json
import random

url = "http://127.0.0.1:5001/register"
suffix = random.randint(1000, 9999)
payload = {
    "username": f"testuser{suffix}",
    "email": f"test{suffix}@example.com",
    "phone": f"90000{suffix}",
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
