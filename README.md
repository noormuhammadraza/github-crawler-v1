# GitHub Stars Crawler — Take Home Assignment

**Status:** Completed ✅ — Workflow run(s) completed and produced the requested CSV artifact(s) with 100k+ unique repositories.

---

## Project summary (one-liner)
A GitHub Actions workflow that uses the GitHub GraphQL API to crawl public repositories, stores results in a PostgreSQL service container, and exports the collected repository metadata (including star counts) as a CSV artifact.

---

## Deliverables included
- `.github/workflows/crawl.yml` — GitHub Actions workflow that provisions PostgreSQL and runs the crawler.
- `crawl_stars.py` — Python crawler that:
  - Queries GitHub GraphQL `search` endpoint with pagination.
  - Handles rate limits (inspects `rateLimit` and sleeps until reset when needed).
  - Upserts results into Postgres using `repo_id` as primary key.
  - Supports segmented crawling by date range (arguments: start_year end_year).
- `create_tables.sql` — DB schema and indexes.
- `requirements.txt` — Python dependencies.
- `repos-csv` artifact(s) (available in the workflow run) — the resulting CSV export of the `repositories` table.
- `verify_repos.py` — verification script that computes counts, duplicates, and summary statistics (included in repo).

---

## How it works — high level
1. GitHub Actions workflow triggers (manually via **Run workflow** or scheduled).
2. A job runs on `ubuntu-latest` and starts a PostgreSQL service container (Postgres 15).
3. The job installs Python dependencies, creates DB schema, runs the crawler script.
4. The crawler:
   - Generates date-based segments (by month/year) to avoid the GitHub `search` 1,000-result limit per query.
   - Pages results with GraphQL cursors and requests `first:100` per call.
   - Observes `rateLimit` values and sleeps when remaining points are low.
   - Upserts repository rows into `repositories` table using `repo_id` as the primary key.
5. After crawling, the workflow dumps `repositories` table into `repos.csv` and uploads it as an artifact.

---

## Reproducibility & evidence (what to include in submission)
When you review the assignment, include these links/values:
- GitHub repository link: `https://github.com/<your-account>/<repo-name>`
- Actions run link(s): `https://github.com/<your-account>/<repo-name>/actions/runs/<run-id>`
- Artifact name(s): `repos-csv`, or `repos-csv-part1` / `repos-csv-part2`
- Verification report: `verification_report.md` (generated with `verify_repos.py` — attach or include its contents)
- Short sample of top items: paste the top 10 rows by `stargazers_count` (from the verification report).

These items are enough for a reviewer to verify the requirements easily.

---

## Quick run instructions (no local setup required)
1. Go to the repository → **Actions** → select **crawl-stars** workflow.
2. Click **Run workflow** → choose the segment input if prompted.
3. Wait for completion, then download the `repos-csv` artifact from the Actions run page.

---

## Verification (how the recruiter can check)
Use `verify_repos.py` to produce `verification_report.md`:

```bash
# Download repos-csv from Actions artifacts to your local machine
python verify_repos.py repos.csv
# Opens verification_report.md with counts and top results

