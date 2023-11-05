# POST to indexing
import requests
import json

# URL
url = "https://localhost:8080/pipeline/zzV2PM3UvyCL1/task?token=RigL0Y9qoZKajqKksaQ6eASxiHc4ZDy1eb8Bxt6V"

# Define the file and JSON data
files = {'document': ('animate.pdf', open('./documents/hn_test.pdf', 'rb'), 'application/pdf')}
json_data = json.dumps({'text': ["This is a file about thermodynamics."]})

# Send the request with both file and JSON data
response = requests.post(url, files=files, data=json_data, headers={'Content-Type': 'application/json'})

if response.status_code == 200:
    print(response.text)
else:
    print(response.status_code)
