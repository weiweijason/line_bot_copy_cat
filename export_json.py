import json

with open('src/secret2.json') as f:
    json_content = json.load(f)

json_string = json.dumps(json_content)
print(json_string)