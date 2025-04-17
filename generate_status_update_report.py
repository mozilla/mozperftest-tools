import requests
import re
import json
from datetime import datetime, timedelta

# Configuration
results = {}
BUGZILLA_URL = "https://bugzilla.mozilla.org/rest/bug"
threshold = 15
patern_lines = r"(?<=## Repository breakdown:)(.*?)(?=## Table)"
pattern_numbers = r":\s*(\d+)"
DAYS_BACK = 7  # Number of days to look back
# Calculate the date for one week ago
last_week = datetime.now() - timedelta(days=DAYS_BACK)
# Query parameters for Bugzilla
params = {
    "product": "Testing",
    "keywords": "intermittent-failure",
    "keywords_type": "allwords",
    "resolution": "---",
    "component": ["AWSY", "mozperftest", "Performance", "Raptor", "Talos"],
    "include_fields": "id,summary"
}
# Fetch bugs from Bugzilla
response = requests.get(BUGZILLA_URL, params=params).json()
# Check if bugs are returned
if "bugs" in response and response["bugs"]:
    bugs = response["bugs"]
    print(f"Found {len(bugs)} bugs matching the query.")
    for bug in bugs:
        bug_id = bug['id']
        print(f"Checking comments for Bug {bug_id} - {bug['summary']}")
        # Fetch comments for each bug
        comments_url = f"{BUGZILLA_URL}/{bug_id}/comment"
        comments_response = requests.get(comments_url).json()
        if "bugs" in comments_response and str(bug_id) in comments_response["bugs"]:
            comments = comments_response["bugs"][str(bug_id)]["comments"]
            for comment in reversed(comments):
                # Convert the comment's creation date to a datetime object
                comment_date = datetime.strptime(comment["creation_time"], "%Y-%m-%dT%H:%M:%SZ")
                # Check if the comment is recent and matches the author
                if comment_date >= last_week and comment["author"] == "orangefactor@bots.tld":
                    match = re.search(patern_lines, comment["text"], re.DOTALL)
                    if match:
                        lines = match.group(1).strip()
                        numbers_failures = re.findall(pattern_numbers, lines)
                        total_numbers_failures = sum([int(num) for num in numbers_failures])

                        if total_numbers_failures > threshold:
                            results.setdefault(str(bug_id), []).append(total_numbers_failures)

        else:
            print("No comments found for this bug.")
else:
    print("No bugs found matching the query.")

print(f"\n ### A TOTAL OF {len(results)} BUGS HAVE BEEN FOUND ### \n")

for i in results:
    summary = next((bug["summary"] for bug in bugs if str(bug.get("id")) == i), None)
    results[i] = {"id": i, "link": f"https://bugzilla.mozilla.org/show_bug.cgi?id={i}",
                  "number_failures": max(results[i]), "summary": summary}
json_formatted_str = json.dumps(results, indent=2)

print(json_formatted_str)
