// How long a deleted profile stays recoverable (issue #50).
//
// Mirrors SOFT_DELETE_RETENTION_DAYS in src/api/health_profile.py. It is
// duplicated rather than fetched because it is only ever used in copy ("...for
// 30 days"), never in a calculation — every actual countdown comes from the
// server's computed days_remaining/expires_at. If the backend constant changes,
// change this one too; the countdowns stay correct either way, but the wording
// would be stale.
export const SOFT_DELETE_RETENTION_DAYS = 30;
