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
