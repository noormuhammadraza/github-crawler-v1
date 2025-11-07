CREATE TABLE IF NOT EXISTS repositories (
    repo_id BIGINT PRIMARY KEY,          -- GitHub numeric repo ID (not node_id)
    full_name TEXT NOT NULL,             -- owner/name
    owner_login TEXT,
    name TEXT,
    html_url TEXT,
    stargazers_count INT,
    primary_language TEXT,
    last_fetched_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_repos_stars ON repositories (stargazers_count);
CREATE INDEX IF NOT EXISTS idx_repos_owner ON repositories (owner_login);
