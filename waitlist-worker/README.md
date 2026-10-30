# HealthSteward waitlist Worker

A tiny Cloudflare Worker + D1 database behind the consumer-app waitlist form on
`healthstewardai.com`. Single-step signup (no confirmation email). Stores only the email,
an optional first name, and proof of consent (wording version + timestamp). No analytics,
no third-party scripts.

## Deploy (one time)

```bash
cd waitlist-worker
npm install
npx wrangler login
npx wrangler d1 create healthsteward-waitlist --jurisdiction=us   # set at creation, cannot be changed later; copy the database_id it prints
# paste that id into wrangler.toml (database_id)
npx wrangler d1 execute healthsteward-waitlist --remote --file=schema.sql
npx wrangler deploy                                # creates waitlist.healthstewardai.com
```

Then set the secret that keys the hashes (required; the Worker refuses signups without it):

```bash
openssl rand -hex 32          # generate a random value and store it in your password manager
npx wrangler secret put HASH_SECRET   # paste that value
```

Keep a copy: the suppression list is only useful while you still have the same secret.

## Day-to-day

```bash
# how many people
npx wrangler d1 execute healthsteward-waitlist --remote --command "SELECT count(*) FROM waitlist"
# export (CSV-ish JSON)
npx wrangler d1 execute healthsteward-waitlist --remote --json --command "SELECT email, first_name, consent_version, consented_at FROM waitlist"
```

## Remove someone (deletion or unsubscribe request)

```bash
EMAIL=person@example.com                       # lowercase
HASH=$(printf 'email:%s' "$EMAIL" | openssl dgst -sha256 -hmac "$HASH_SECRET" | awk '{print $NF}')
npx wrangler d1 execute healthsteward-waitlist --remote --command "DELETE FROM waitlist WHERE email='$EMAIL'; INSERT OR IGNORE INTO suppression VALUES ('$HASH', date('now'))"
```

Deletion and suppression are separate steps. Deleting the row erases the person's details.
The suppression row keeps only a keyed hash (HMAC, not practically reversible without the secret) so the
person is not re-added by the form or by re-importing an old export. Keep suppression
rows only as long as the waitlist exists; delete them when you shut it down. When you later
load the list into an email tool, exclude anyone in `suppression` and anyone who has
unsubscribed there.

## Weekly digest

Every Friday at 10pm Pacific the Worker emails the owner a summary: new signups this week
(email, first name, time), the total, and 0-new weeks too. Cron triggers run in UTC only (and
weekdays count from Sunday=1), so `wrangler.toml` fires Saturday 05:00 and 06:00 UTC and the Worker
sends only on the run that is 10pm Pacific, which keeps it at 10pm through daylight-saving changes.

- Sent with the Cloudflare Email Service `send_email` binding (`EMAIL`) from `DIGEST_FROM`
  (`waitlist@healthstewardai.com`) to the secret `DIGEST_TO` (keeps the address out of this public
  repo): `npx wrangler secret put DIGEST_TO`.
- Failures are only visible with `npx wrangler tail` (request logging is off). Test locally with
  `bash test/digest.sh`.
- The email contains signup addresses, so it goes to the owner only.

## Behavior

- `POST /join` with JSON `{email, first_name?, consent_version, website?}`; `website` is a
  hidden honeypot field that must stay empty.
- Same success response whether or not the address already exists.
- 5 requests per client per 10 minutes (counters keyed with an HMAC of the IP, purged within a day; the raw IP is never stored).
- CORS limited to `ALLOWED_ORIGINS` in `wrangler.toml`.
- Changing the consent wording on the site: add a new version string to
  `KNOWN_CONSENT_VERSIONS` in `src/index.js` and in the form, then redeploy.

## Local test

Create a `.dev.vars` file containing `HASH_SECRET=any-local-value` (it is git-ignored), then:

```bash
bash test/smoke.sh   # duplicate, suppression, export, deletion, rate limit
```

The exact consent wording for each `consent_version` lives in `consent-versions.md`.

## Data location and retention (verified against Cloudflare's docs, Oct 2026)

- `--jurisdiction=us` makes D1 run and store the database in the United States. It does not
  restrict where Workers run or where requests are answered, and it can't be changed after
  the database is created. (If a location hint is also given, the jurisdiction wins.)
- D1 Time Travel is always on: the database can be restored to any point in the last 7 days
  on the free plan (30 on paid). It restores the whole database, not single rows, so a row you
  deleted can exist in that history until it ages out.
