import requests

print("Without user_id:")
r = requests.get('http://127.0.0.1:5001/api/attendance_graph_stats')
print(r.json())

print("\nWith user_id=2:")
r = requests.get('http://127.0.0.1:5001/api/attendance_graph_stats?user_id=2')
print(r.json())
