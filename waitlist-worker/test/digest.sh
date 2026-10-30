#!/usr/bin/env bash
# Local check of the weekly digest: sends only at Friday 10pm Pacific (both daylight and standard
# time), reports the right counts, and stays quiet otherwise.
# Usage: cd waitlist-worker && bash test/digest.sh   (needs .dev.vars with HASH_SECRET and DIGEST_TO)
set -u
cd "$(dirname "$0")/.."
PORT=8788; LOG=$(mktemp); fail=0
ok(){ echo "PASS  $1"; }; bad(){ echo "FAIL  $1"; fail=1; }
ms(){ python3 -c "import datetime;print(int(datetime.datetime.fromisoformat('$1').replace(tzinfo=datetime.timezone.utc).timestamp()*1000))"; }
run(){ curl -s -o /dev/null "localhost:$PORT/cdn-cgi/local/scheduled?cron=0+5,6+*+*+sat&time=$(ms "$1")"; sleep 1.5; }
sent(){ grep -c "Subject: HealthSteward waitlist" "$LOG"; }

rm -rf .wrangler
npx wrangler d1 execute healthsteward-waitlist --local --file=schema.sql >/dev/null 2>&1
npx wrangler d1 execute healthsteward-waitlist --local --command "INSERT INTO waitlist (email,first_name,consent_version,consented_at) VALUES ('old@example.com','Old','v','2026-10-01T10:00:00.000Z'),('a@example.com','Ann','v','2026-10-28T18:30:00.000Z'),('b@example.com',NULL,'v','2026-10-30T20:15:00.000Z')" >/dev/null 2>&1
(npx wrangler dev --port $PORT >"$LOG" 2>&1 &)
trap 'pkill -f "wrangler dev" 2>/dev/null; rm -rf .wrangler "$LOG"' EXIT
for i in $(seq 1 40); do curl -s -o /dev/null -X OPTIONS localhost:$PORT/join && break; sleep 1; done

run 2026-10-31T05:00:00; [ "$(sent)" = 1 ] && ok "sends Fri 10pm PDT (Sat 05:00 UTC)" || bad "PDT send"
grep -q "Subject: HealthSteward waitlist: 2 new this week (3 total)" "$LOG" && ok "counts: 2 new, 3 total, old signup excluded" || bad "counts"
run 2026-10-31T06:00:00; [ "$(sent)" = 1 ] && ok "skips Fri 11pm PDT (Sat 06:00 UTC)" || bad "PDT 11pm skip"
run 2026-11-07T05:00:00; [ "$(sent)" = 1 ] && ok "skips Fri 9pm PST (Sat 05:00 UTC)" || bad "PST 9pm skip"
run 2026-11-07T06:00:00; [ "$(sent)" = 2 ] && ok "sends Fri 10pm PST (Sat 06:00 UTC)" || bad "PST send"
grep -q "Subject: HealthSteward waitlist: 0 new this week (3 total)" "$LOG" && ok "empty week still sends, 0 new" || bad "empty week"
run 2026-10-30T05:00:00; [ "$(sent)" = 2 ] && ok "skips other weekdays" || bad "weekday skip"
[ $fail = 0 ] && echo "ALL PASSED" || { echo "SOME FAILED"; exit 1; }
