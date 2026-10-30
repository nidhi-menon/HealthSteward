-- Waitlist signups. Only what the signup form collects, plus proof of consent.
CREATE TABLE IF NOT EXISTS waitlist (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  email           TEXT NOT NULL UNIQUE,          -- lowercased
  first_name      TEXT,                          -- optional
  consent_version TEXT NOT NULL,                 -- which wording the person saw
  consented_at    TEXT NOT NULL                  -- ISO 8601, UTC
);

-- People who asked to be removed. Stores only a one-way hash, so a removed
-- person is not re-added if an old export is re-imported.
CREATE TABLE IF NOT EXISTS suppression (
  email_hash TEXT PRIMARY KEY,                   -- sha256(lowercased email)
  added_at   TEXT NOT NULL
);

-- Short-lived anti-abuse counters (hashed IP + time window). Purged after a day.
CREATE TABLE IF NOT EXISTS rate_limit (
  key    TEXT NOT NULL,
  window INTEGER NOT NULL,
  count  INTEGER NOT NULL,
  PRIMARY KEY (key, window)
);
