import os, json, time
import requests
import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timezone
from tenacity import retry, stop_after_attempt, wait_exponential

GITHUB_API = "https://api.github.com/graphql"
HEADERS = {"Authorization": f"bearer {os.environ.get('GITHUB_TOKEN')}"}
DB_URL = os.environ["DATABASE_URL"]

GRAPHQL_QUERY = """
query($q:String!, $first:Int!, $after:String) {
  rateLimit { limit cost remaining resetAt }
  search(query: $q, type: REPOSITORY, first: $first, after: $after) {
    repositoryCount
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Repository {
        databaseId
        nameWithOwner
        name
        url
        stargazerCount
        primaryLanguage { name }
        owner { login }
      }
    }
  }
}
"""

def upsert_repos(conn, rows):
    sql = """
    INSERT INTO repositories (repo_id, full_name, owner_login, name, html_url, stargazers_count, primary_language, last_fetched_at, metadata)
    VALUES %s
    ON CONFLICT (repo_id) DO UPDATE
      SET stargazers_count = EXCLUDED.stargazers_count,
          last_fetched_at = EXCLUDED.last_fetched_at
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=60))
def graphql_request(payload):
    r = requests.post(GITHUB_API, json=payload, headers=HEADERS)
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL error: {data['errors']}")
    return data

def crawl_segment(conn, query):
    after = None
    page = 0
    while page < 3:  # limit pages per run for safety
        variables = {"q": query, "first": 50, "after": after}
        res = graphql_request({"query": GRAPHQL_QUERY, "variables": variables})
        nodes = res["data"]["search"]["nodes"]
        rate = res["data"]["rateLimit"]
        print(f"Remaining: {rate['remaining']}")

        rows = []
        now = datetime.now(timezone.utc).isoformat()
        for n in nodes:
            rows.append((
                n["databaseId"],
                n["nameWithOwner"],
                n["owner"]["login"] if n.get("owner") else None,
                n["name"],
                n["url"],
                n["stargazerCount"],
                n["primaryLanguage"]["name"] if n.get("primaryLanguage") else None,
                now,
                json.dumps(n)
            ))
        upsert_repos(conn, rows)
        print(f"Inserted {len(rows)} rows, page {page+1}")

        pageInfo = res["data"]["search"]["pageInfo"]
        if not pageInfo["hasNextPage"]:
            break
        after = pageInfo["endCursor"]
        page += 1
        time.sleep(2)

def main():
    conn = psycopg2.connect(DB_URL)
    queries = ["stars:>10000 sort:stars-desc", "stars:5000..9999 sort:stars-desc"]
    for q in queries:
        crawl_segment(conn, q)
    conn.close()

if __name__ == "__main__":
    main()
