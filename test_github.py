import os
import json
import urllib.request

token = os.getenv("GITHUB_TOKEN")

query = """
query {
  repository(owner: "psf", name: "requests") {
    nameWithOwner
    description
    stargazerCount
    forkCount
    defaultBranchRef {
      name
    }
  }
}
"""

request = urllib.request.Request(
    "https://api.github.com/graphql",
    data=json.dumps({"query": query}).encode(),
    headers={
        "Authorization": f"bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "SupplyRisk-Crawler",
    },
)

response = urllib.request.urlopen(request)
print(response.read().decode())
