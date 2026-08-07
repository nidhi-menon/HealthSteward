---

## 56. Pre-Apply Diff Preview for Parsed AVS Items (#46)

**Date:** 2026-08-07

**Context:** `apply_items` reconciled parsed AVS data against existing records by fuzzy-matching a name and then overwriting fields in place — `existing_cond.severity = dx.severity`, `existing_med.dosage = med.strength`. The only guard was `_is_newer(visit_dt, record.updated_at)`, which stops an *older* visit clobbering a newer record but does nothing about a genuinely newer visit carrying a mis-parsed value. With no history table anywhere in `src/data/models.py`, a bad parse applied cleanly and the previous value was simply gone. Since parsing runs through a local LLM over OCR'd text (DEC-010), "the parse was wrong" is a routine case, not an exotic one.

**Scope: option 1 (preview) only; option 2 (history/audit trail) deliberately deferred.** The issue offered both. A `changed_from`/`changed_at` pair or a dedicated history table is the same substrate #12 (append-only claim rows), #54 (regenerate history), and #97 (cross-source reconciliation) will each want, and picking its shape unilaterally here means designing it three times or migrating it once. Deferred to be designed once, across those issues. The preview alone converts a blind "Apply" into a reviewed one, which is the bulk of the protection.

**What changed:** the reconciliation decisions were pulled out of the mutation. `_build_apply_plan` is a read-only function returning a list of `_PlanEntry` — `{entity_type, action: create|update|skip, label, entity_id, reason, changes[]}` — where `changes` carries per-field `old_value → new_value` and `reason` records *why* something is skipped (`"the existing record is newer than this visit"`, `"already recorded"`). `apply_items` no longer decides anything; it calls `_build_apply_plan` and then `_execute_apply_plan`, which only writes. A new `POST /{document_id}/apply/preview` returns the same plan without committing.

**Preview/apply drift is the failure mode this design is built against.** Two endpoints that must agree about what will change is exactly the kind of pair that silently diverges. They share `_build_apply_plan`, and the response totals come from `_plan_totals` — one function, used by both — so `counts`/`skipped` cannot disagree by construction. `test_preview_and_apply_agree_on_the_same_input` pins that end to end.

**Stale-preview guard (repo owner's call on the issue):** the preview returns a `plan_fingerprint`, a digest over the plan *including the stored values it read*. Confirm sends it back as `expected_plan_fingerprint`; apply re-derives the plan and returns `409` with the fresh plan attached if the fingerprint moved. Because the digest covers old values, an edit to a targeted record in another tab invalidates the preview even when the actions themselves look identical. The field is optional at the API layer so existing callers keep working; the UI always sends it.

**One intentional behaviour change:** within-document duplicates are now deduped deterministically. Previously two items in the same AVS that matched each other each created their own row — unless a `_find_or_create_doctor` call happened to flush mid-loop, in which case the second was skipped. Plan building tracks what it has already planned to create, so the outcome no longer depends on flush timing. Duplicates now land as `skip` with reason "already included earlier in this document".

**Frontend:** the confirm modal in `ParsedItemsReview.tsx` previously listed the items being sent — which is not the same thing as what would change. It now fetches the plan and renders it grouped into "Will be changed" / "Will be added" / "Will be left alone", with `old → new` per field, following the `changedFields` pattern already in `ProfileDetail.tsx` rather than inventing another. Fields whose incoming value matches what is stored are counted but not listed, so the diff shows only real edits. Skipped-because-newer items are now visible, which they never were before. A refused apply swaps in the re-derived plan behind a "this profile changed while you were reviewing" banner instead of making the user start over.

**Tests:** `tests/test_documents_apply.py` (new, 15 tests). Ten are characterisation tests written against the *pre-refactor* code and confirmed passing before any of it moved — create/overwrite/skip-because-newer for conditions, the four medication paths including the deliberately-uncounted matched-start refresh, dedup skips, vitals, undated appointments, doctor matching. Five cover the preview: field-level diff without writing, skip reasons, preview/apply agreement, the stale-plan 409 and recovery, and backwards compatibility without a fingerprint. Full suite: 314 passed, 25 skipped (up from 299). Frontend `tsc -b && vite build` green.

**Drive-by:** `frontend/src/components/PostAvsActionPanel.tsx` had two unused type imports that failed `tsc -b` on `main`, so the frontend build was already red before this change. Fixed here because the build had to be green to verify the frontend work; it is a two-line change unrelated to #46.

**No DEC entry:** this makes an existing behaviour visible rather than choosing a new architecture. The history table, when it happens, is the DEC-worthy part.

**Files changed:** `src/api/documents.py`, `src/models/schemas.py`, `tests/test_documents_apply.py`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `frontend/src/components/ParsedItemsReview.tsx`, `frontend/src/components/PostAvsActionPanel.tsx`, `frontend/src/pages/ProfileDetail.tsx`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #46, issue #135 (FHIR import reuses this parse→preview→apply flow), issue #97 (reconciliation, deferred), issue #12, issue #54, DEC-010, DEC-031.

---

## 57. Pre-Visit "What to Bring" Checklist (#110)

**Date:** 2026-08-07

**Context:** #110 came out of a product-strategy discussion as a small, concrete friction point: people turn up without their insurance card, the referral paperwork, the imaging disc, or the pharmacy address, and the visit is worse for it. The issue's own scope note called for deterministic rules rather than an LLM — "deterministic is fine and cheaper here" — which holds up: the things people forget are the same things every time, so a rules table gets this right more predictably than a prompt, costs nothing to run, and doesn't touch the LLM boundary (DEC-006), the anonymization path, or any prompt. No `PROMPT_CHANGELOG.md` bump, no eval re-run.

**Fixed rules for v1, not user-editable** — the issue's own open question, confirmed by the repo owner on the issue. User-added items need a table, a migration, and CRUD UI, which turns a Small into a Medium; deferred rather than half-built.

**What changed:** `src/services/visit_checklist.py` (new) holds the rules as data — a specialty table, a purpose-keyword table, a first-visit set, and three baseline items — plus `build_checklist`, a pure function over facts the caller has already loaded. No DB access, no clock, no I/O, so the rules are directly unit-testable and the endpoint stays a thin query-and-render layer. `GET /api/profiles/{profile_id}/appointments/{appointment_id}/checklist` does the queries and returns the result. Computed per request: nothing is stored, there is no new table and no migration, and a referral closed this morning drops off the list by itself.

**Rule inputs, all from data that already exists:** `Doctor.specialty` (substring-matched, since it's free text — "Interventional Cardiology" still has to match the cardiology rule); whether any *completed* appointment with this doctor already exists; keyword matches on `Appointment.purpose`; whether the profile has active medications, allergies, or generated prep questions; and the count of unresolved `Referral`/`LabOrder` rows. That last pair are the most concrete items on the list precisely because they aren't guesses — the profile already knows the paperwork is outstanding.

**"First visit" means no *completed* earlier visit with that doctor, not no earlier row.** You can book three appointments before attending any of them; the first one you actually walk into is still a first visit as far as the front desk is concerned. `COMPLETED_STATUSES` in `src/api/action_items.py` was made public (from `_COMPLETED_STATUSES`) so "still outstanding" means the same thing in the checklist as it does in the action-items list, rather than being defined twice.

**Every item carries a `why`, and the rules that produced it.** The `why` is not decoration — a checklist that explains itself gets followed, and it lets someone judge whether a rule actually applies to them. `sources` records which rules fired (`specialty:orthoped`, `purpose:mri`, `open_referral`), so a surprising entry can be traced instead of taken on faith. Items dedupe by id with sources merged, so a rule firing twice reads as one item with two reasons.

**Known weak spot, tracked not buried:** there is no structured visit-type field, so visit-shape rules keyword-match free text and will miss phrasings they don't know. `test_an_unrecognised_purpose_adds_nothing` asserts the empty result for unrecognised wording, so the gap is visible in the suite rather than implied. Filed as **#144** (add a structured `visit_type` to `Appointment`) at the repo owner's request on the issue, rather than left as prose here.

**Deliberately generic where the data doesn't exist:** there are no insurance fields in the schema, so the item is "bring your insurance card", not "bring your Aetna card". Adding insurance data overlaps #102, a cost/claims feature deliberately not touched.

**Frontend:** `VisitChecklistCard.tsx` (new), rendered on `VisitPrep.tsx` for not-yet-completed visits only — a "what to bring" list has no use after the visit. Grouped by category with a remaining count. Tick-off state lives in `localStorage` keyed by appointment id, not the database: it's a scratchpad for one visit, not health data worth a table and a migration, and localStorage failures (private browsing, quota) are swallowed rather than surfaced as an error, since failing to remember a ticked box shouldn't take the card down. Placement note: #43 reworks `VisitPrep` into a before/after hub, so this card will want re-placing when that lands.

**Tests:** `tests/test_visit_checklist.py` (new, 15 tests), split by what's worth pinning — nine call `build_checklist` directly (empty profile produces an empty list, baseline items, first-visit set, substring specialty matching, purpose keywords, the unrecognised-purpose gap, counted paperwork, dedupe-with-merged-sources, determinism), six exercise the endpoint (specialty and purpose read correctly, scheduled-vs-completed first-visit logic, resolved items excluded, active-vs-stopped medications, no-doctor appointments, 404s). Full suite: 314 passed, 25 skipped (up from 299).

**No DEC entry:** a rules table is not an architectural or technology choice. Flagged as such on the issue and not objected to.

**Files changed:** `src/services/visit_checklist.py`, `src/api/appointments.py`, `src/api/action_items.py`, `src/models/schemas.py`, `tests/test_visit_checklist.py`, `frontend/src/components/VisitChecklistCard.tsx`, `frontend/src/pages/VisitPrep.tsx`, `frontend/src/api/client.ts`, `frontend/src/types/index.ts`, `frontend/src/components/PostAvsActionPanel.tsx`, `docs/notes/DEVELOPMENT_LOG.md`.

Related: issue #110, issue #144 (visit_type follow-up), issue #43 (Visit Prep rework — placement), issue #102 (insurance/cost data, not touched), DEC-006, DEC-027.

---
