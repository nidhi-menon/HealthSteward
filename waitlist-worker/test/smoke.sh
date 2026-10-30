#!/usr/bin/env bash
# Local end-to-end check: duplicate, suppression, export, deletion, rate limit.
# Usage: cd waitlist-worker && bash test/smoke.sh   (needs a .dev.vars with HASH_SECRET=...)
set -u
cd "$(dirname "$0")/.."
PORT=8788; URL=http://localhost:$PORT/join; ORIGIN="Origin: https://healthstewardai.com"
SECRET=$(grep HASH_SECRET .dev.vars | cut -d= -f2-)
V=2026-10-29-v1
fail=0
ok(){ echo "PASS  $1"; }
bad(){ echo "FAIL  $1"; fail=1; }
q(){ npx wrangler d1 execute healthsteward-waitlist --local --json --command "$1" 2>/dev/null; }
count(){ q "SELECT count(*) AS n FROM waitlist WHERE email='$1'" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['results'][0]['n'])"; }
body(){ printf '{"email":"%s","first_name":"%s","consent_version":"%s"}' "$1" "${2:-}" "$V"; }
post(){ curl -s -o /dev/null -w "%{http_code}" -X POST "$URL" -H "$ORIGIN" -H "Content-Type: application/json" -d "$(body "$@")"; }
hash(){ printf 'email:%s' "$1" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $NF}'; }

rm -rf .wrangler
npx wrangler d1 execute healthsteward-waitlist --local --file=schema.sql >/dev/null 2>&1
(npx wrangler dev --port $PORT >/dev/null 2>&1 &)
trap 'pkill -f "wrangler dev" 2>/dev/null; rm -rf .wrangler' EXIT
for i in $(seq 1 40); do curl -s -o /dev/null -X OPTIONS "$URL" -H "$ORIGIN" && break; sleep 1; done

[ "$(post Dup@Example.com D)" = 200 ] && ok "signup accepted" || bad "signup accepted"
[ "$(count dup@example.com)" = 1 ] && ok "stored once, lowercased" || bad "stored once, lowercased"
[ "$(post dup@example.com)" = 200 ] && ok "duplicate returns same success" || bad "duplicate returns success"
[ "$(count dup@example.com)" = 1 ] && ok "duplicate not stored twice" || bad "duplicate not stored twice"

# a duplicate must not overwrite the original consent record
first=$(q "SELECT consented_at FROM waitlist WHERE email='dup@example.com'" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['results'][0]['consented_at'])")
sleep 1; post dup@example.com >/dev/null
again=$(q "SELECT consented_at FROM waitlist WHERE email='dup@example.com'" | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['results'][0]['consented_at'])")
[ "$first" = "$again" ] && ok "duplicate keeps original consent timestamp" || bad "duplicate overwrote consent"
big=$(python3 -c "print('x'*5000)")
[ "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$URL" -H "$ORIGIN" -H 'Content-Type: application/json' -d "{\"email\":\"$big@e.co\"}")" = 413 ] && ok "oversized body rejected (413)" || bad "oversized body"
[ "$(curl -s -o /dev/null -w '%{http_code}' -X GET "$URL" -H "$ORIGIN")" = 404 ] && ok "no read/export endpoint over HTTP" || bad "unexpected GET"

q "INSERT INTO suppression VALUES ('$(hash gone@example.com)','test')" >/dev/null
[ "$(post Gone@Example.com)" = 200 ] && ok "suppressed signup returns success" || bad "suppressed returns success"
[ "$(count gone@example.com)" = 0 ] && ok "suppressed address not stored" || bad "suppressed address not stored"

q "SELECT email, first_name, consent_version, consented_at FROM waitlist" | grep -q dup@example.com && ok "export query returns the row" || bad "export query"
# deletion + suppression workflow, as in the README
q "DELETE FROM waitlist WHERE email='dup@example.com'; INSERT OR IGNORE INTO suppression VALUES ('$(hash dup@example.com)', date('now'))" >/dev/null
[ "$(count dup@example.com)" = 0 ] && ok "deletion removes the row" || bad "deletion removes the row"
post dup@example.com >/dev/null
[ "$(count dup@example.com)" = 0 ] && ok "deleted person is not re-added" || bad "deleted person re-added"

# rate limit: the requests above already count toward this client's window of 5
last=0; for i in 1 2 3 4; do last=$(post "r$i@example.com"); done
[ "$last" = 429 ] && ok "rate limit returns 429" || bad "rate limit (got $last)"
[ $fail = 0 ] && echo "ALL PASSED" || { echo "SOME FAILED"; exit 1; }
