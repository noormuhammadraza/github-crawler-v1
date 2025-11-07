import os, json, time, datetime
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
        createdAt
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
    if r.status_code >= 500:
        raise Exception(f"Server error: {r.status_code}")
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL errors: {data['errors']}")
    return data

def crawl_segment(conn, query, max_pages=10):
    after = None
    page = 0
    while page < max_pages:
        variables = {"q": query, "first": 100, "after": after}
        res = graphql_request({"query": GRAPHQL_QUERY, "variables": variables})
        data = res.get("data", {})
        if not data:
            break

        rate = data.get("rateLimit", {})
        remaining = rate.get("remaining")
        resetAt = rate.get("resetAt")

        if remaining is not None and remaining < 100:
            reset_ts = datetime.fromisoformat(resetAt.replace("Z", "+00:00")).timestamp()
            sleep_time = max(0, reset_ts - time.time()) + 10
            print(f"[Throttle] Sleeping {sleep_time:.0f}s (remaining={remaining})")
            time.sleep(sleep_time)

        search = data["search"]
        nodes = search["nodes"]
        if not nodes:
            break

        now = datetime.now(timezone.utc).isoformat()
        rows = []
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
        print(f"Inserted {len(rows)} rows from query='{query}', page={page+1}")

        pageInfo = search["pageInfo"]
        if not pageInfo["hasNextPage"]:
            break
        after = pageInfo["endCursor"]
        page += 1

        time.sleep(2)  # polite delay between pages

def generate_date_segments(start_year=2015, end_year=2025):
    segments = []
    for year in range(start_year, end_year):
        for month in range(1, 13):
            start = datetime(year, month, 1)
            if month == 12:
                end = datetime(year+1, 1, 1)
            else:
                end = datetime(year, month+1, 1)
            query = f"created:{start.date()}..{end.date()} is:public sort:stars-desc"
            segments.append(query)
    return segments

def main():
    conn = psycopg2.connect(DB_URL)
    segments = generate_date_segments(2015, 2025)

    for i, q in enumerate(segments):
        print(f"\n=== Segment {i+1}/{len(segments)}: {q} ===")
        try:
            crawl_segment(conn, q)
        except Exception as e:
            print(f"Error in segment {q}: {e}")
            continue

    conn.close()

if __name__ == "__main__":
    main()
