import requests
import json
import uuid

def test_send():
    url = "http://127.0.0.1:8000"
    recipe = {
        "recipe": "lava cheesecake"
    }
    headers = {
        "Content-Type": "application/json"
    }
    response = requests.post(url=url, data=json.dumps(recipe), headers=headers)
    print("Status code:", response.status_code)

    try:
        print("Response JSON:", response.json())
        return response.json()
    except json.JSONDecodeError:
        print("Response content is not valid JSON:", response.text)

if __name__ == "__main__":
    test_send()