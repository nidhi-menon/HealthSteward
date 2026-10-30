// HealthSteward waitlist: POST /join {email, first_name?, consent_version, website?}
// Single step, no confirmation email. Stores only email, optional first name and consent proof.

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MAX_EMAIL = 254;
const MAX_NAME = 60;
const MAX_BODY = 2048;          // bytes; a valid signup is well under 1 KB
const RATE_LIMIT = 5;           // requests ...
const RATE_WINDOW_SEC = 600;    // ... per 10 minutes per client
const KNOWN_CONSENT_VERSIONS = new Set(["2026-10-29-v1"]);

export default {
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(sendWeeklyDigest(controller, env));
  },

  async fetch(request, env) {
    const url = new URL(request.url);
    const cors = corsHeaders(request, env);

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    if (url.pathname !== "/join" || request.method !== "POST") {
      return json({ ok: false, error: "not_found" }, 404, cors);
    }
    if (!cors["Access-Control-Allow-Origin"]) {
      return json({ ok: false, error: "forbidden_origin" }, 403, cors);
    }

    if (Number(request.headers.get("Content-Length") || 0) > MAX_BODY) {
      return json({ ok: false, error: "too_large" }, 413, cors);
    }
    let body;
    try {
      const text = await request.text();
      if (text.length > MAX_BODY) return json({ ok: false, error: "too_large" }, 413, cors);
      body = JSON.parse(text);
    } catch {
      return json({ ok: false, error: "invalid_json" }, 400, cors);
    }

    // Honeypot: real people never fill this hidden field. Pretend success so bots learn nothing.
    if (typeof body.website === "string" && body.website.trim() !== "") {
      return json({ ok: true }, 200, cors);
    }

    const email = String(body.email ?? "").trim().toLowerCase();
    if (email.length > MAX_EMAIL || !EMAIL_RE.test(email)) {
      return json({ ok: false, error: "invalid_email" }, 400, cors);
    }
    const firstName = String(body.first_name ?? "").trim().slice(0, MAX_NAME) || null;
    const consentVersion = String(body.consent_version ?? "");
    if (!KNOWN_CONSENT_VERSIONS.has(consentVersion)) {
      return json({ ok: false, error: "invalid_consent" }, 400, cors);
    }

    if (!env.HASH_SECRET) {
      console.error("HASH_SECRET is not set");
      return json({ ok: false, error: "server_error" }, 500, cors);
    }

    try {
      const ip = request.headers.get("CF-Connecting-IP") || "unknown";
      if (await isRateLimited(env, ip)) {
        return json({ ok: false, error: "rate_limited" }, 429, { ...cors, "Retry-After": "60" });
      }

      const suppressed = await env.DB
        .prepare("SELECT 1 FROM suppression WHERE email_hash = ?")
        .bind(await keyedHash(env.HASH_SECRET, `email:${email}`))
        .first();
      if (!suppressed) {
        // Same response whether or not the address already exists, so the form can't be
        // used to check who is on the list.
        await env.DB
          .prepare(
            "INSERT INTO waitlist (email, first_name, consent_version, consented_at) " +
              "VALUES (?, ?, ?, ?) ON CONFLICT(email) DO NOTHING"
          )
          .bind(email, firstName, consentVersion, new Date().toISOString())
          .run();
      }
      return json({ ok: true }, 200, cors);
    } catch (err) {
      console.error("join failed", err && err.message);
      return json({ ok: false, error: "server_error" }, 500, cors);
    }
  },
};

function corsHeaders(request, env) {
  const origin = request.headers.get("Origin") || "";
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const headers = {
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Max-Age": "86400",
    "Vary": "Origin",
  };
  if (allowed.includes(origin) || allowed.includes("*")) {
    headers["Access-Control-Allow-Origin"] = allowed.includes("*") ? "*" : origin;
  }
  return headers;
}

async function isRateLimited(env, ip) {
  const now = Math.floor(Date.now() / 1000);
  const window = Math.floor(now / RATE_WINDOW_SEC);
  const key = await keyedHash(env.HASH_SECRET, `ip:${ip}`);
  // Opportunistic cleanup, so no IP-derived value outlives roughly a day.
  if (Math.random() < 0.05) {
    await env.DB.prepare("DELETE FROM rate_limit WHERE window < ?")
      .bind(window - Math.ceil(86400 / RATE_WINDOW_SEC)).run();
  }
  await env.DB
    .prepare(
      "INSERT INTO rate_limit (key, window, count) VALUES (?, ?, 1) " +
        "ON CONFLICT(key, window) DO UPDATE SET count = count + 1"
    )
    .bind(key, window)
    .run();
  const row = await env.DB
    .prepare("SELECT count FROM rate_limit WHERE key = ? AND window = ?")
    .bind(key, window)
    .first();
  return (row?.count ?? 0) > RATE_LIMIT;
}

// Keyed hash (HMAC-SHA-256). A plain hash of an IP address or email can be reversed by
// guessing, so both are keyed with a secret (HASH_SECRET) that never leaves Cloudflare.
async function keyedHash(secret, text) {
  const key = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(text));
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function json(obj, status, headers = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store", ...headers },
  });
}

// ---- Weekly digest -------------------------------------------------------------------------
// Cron triggers run in UTC only, and Friday 10pm Pacific is Sat 05:00 UTC in daylight time and
// Sat 06:00 UTC in standard time. wrangler.toml fires at both hours; this check lets only the
// one that is 10pm Pacific through, so the digest lands at 10pm Pacific all year.
const DIGEST_DAYS = 7;
const DIGEST_MAX_ROWS = 100;
const PT = "America/Los_Angeles";

function pacificParts(date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: PT, weekday: "short", hour: "numeric", hourCycle: "h23",
  }).formatToParts(date);
  const get = (t) => parts.find((p) => p.type === t)?.value;
  return { weekday: get("weekday"), hour: Number(get("hour")) };
}

function fmtPacific(iso) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: PT, month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  }).format(new Date(iso));
}

async function sendWeeklyDigest(controller, env) {
  const scheduled = new Date(controller.scheduledTime);
  const { weekday, hour } = pacificParts(scheduled);
  if (!(weekday === "Fri" && hour === 22)) return;          // the other cron hour: skip

  if (!env.EMAIL || !env.DIGEST_TO || !env.DIGEST_FROM) {
    console.error("digest not configured (EMAIL binding, DIGEST_TO, DIGEST_FROM)");
    return;
  }
  try {
    const since = new Date(scheduled.getTime() - DIGEST_DAYS * 86400 * 1000).toISOString();
    const total = (await env.DB.prepare("SELECT count(*) AS n FROM waitlist").first()).n;
    const { results } = await env.DB
      .prepare("SELECT email, first_name, consented_at FROM waitlist WHERE consented_at >= ? ORDER BY consented_at")
      .bind(since)
      .all();
    const shown = results.slice(0, DIGEST_MAX_ROWS);
    const lines = shown.map((r) =>
      `${fmtPacific(r.consented_at)} PT  ${r.email}${r.first_name ? `  (${r.first_name})` : ""}`);
    if (results.length > shown.length) lines.push(`...and ${results.length - shown.length} more`);

    const text =
      `HealthSteward waitlist, week ending ${fmtPacific(scheduled.toISOString())} PT\n\n` +
      `New this week: ${results.length}\nTotal on the list: ${total}\n\n` +
      (lines.length ? `New signups:\n${lines.join("\n")}\n` : "No new signups this week.\n") +
      `\nTo remove someone, see waitlist-worker/README.md.`;

    await env.EMAIL.send({
      to: env.DIGEST_TO,
      from: env.DIGEST_FROM,
      subject: `HealthSteward waitlist: ${results.length} new this week (${total} total)`,
      text,
    });
  } catch (err) {
    console.error("digest failed", err && (err.code || err.message));
  }
}
