import requests
import json
import time

BASE_URL = "http://127.0.0.1:80"#"https://stageconversationalagent.cholamandalam.com"#
# query = "what is kredo"
session_id = "test_session"
user_question = "how to login?"
employee_id = "1234_test"
mobile_number = "1234567890"
zone = "head office"
url_query = f"{BASE_URL}/query"
headers_query = {
    'Content-Type': 'application/json',
    'Authorization': 'Basic MWY4NDM4OGIxZjViZWVmMmJjMjE1YzkyOGYxOWY1YjMxNzc4NzAzYWMzOGY4YjMwZDIxZGEwMGJmZjZmMmZmYTpjZTUzOTdiZDY1MWYxOGY0M2ZkMzZiZGNlMWFiYzQwNTgyNDQ1MjVhMDg0MjA2ZGI1YTg1NGI2Mjk3NWUwZWM4'
}

payload_query = {
    "user_question": user_question,
    "session_id": session_id,
    "employee_id": employee_id,
    "mobile_number": mobile_number,
    "zone": zone
}

st = time.time()
try:
    response_query = requests.post(url_query, headers=headers_query, json=payload_query)
    response_query.raise_for_status()
    print("Agent:", response_query.json(), "\n")
    end = time.time()
    print(end-st)
except Exception as e:
    print("Query failed:", e, "\n")

