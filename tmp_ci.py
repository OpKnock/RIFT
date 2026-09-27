import json, subprocess
out = subprocess.run(["gh", "run", "view", "36327919969", "--json", "jobs"],
                     capture_output=True, text=True).stdout
data = json.loads(out)
for j in data["jobs"]:
    print(j["databaseId"], j["name"], j["conclusion"])
