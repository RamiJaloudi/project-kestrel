# Profiles and test identities

[USER DECISION] Employee IDs are administrator-managed. A password change requires the current password, matching new passwords and revocation of other sessions. The profile includes UPN, employee ID, name, employer, roles and currently permitted clean-team memberships.

[IMPLEMENTED LOCAL] Every authenticated portal, including Administration, has the same upper-right profile menu. The UPN and employee ID remain visible while closed. Open it to copy the UPN, inspect memberships/session expiry, change password, sign out, or sign out all sessions. The public Portal Home and unauthenticated design previews do not assert an identity.

Administrators: open Administration → Accounts, select an existing account, edit its name and employee ID, and save. IDs retain leading zeros and must be unique within the employer. Existing accounts receive stable allocated IDs during migration 0021; newly provisioned accounts receive unique generated IDs that administrators may replace. Names and employee IDs are metadata, never authorization grants. Editing uses revision checks. UPNs, employer, roles, walls and membership cannot be changed through this form.

Passwords use the existing Argon2id hashing. Changes use HTTPS, exact Origin and CSRF protection, a current-password failure limit of five per fifteen minutes, and account-level locking. Success rotates the current cookie and CSRF token without extending the session expiry, revokes the old session and every other session for that account, and records a secret-free administrative audit event. Current passwords, new passwords and hashes are never returned to the browser or stored in profile metadata. New passwords must contain 15–256 characters.

Startup preserves customized passwords for demo accounts, including the named interviewers and owner. It also preserves revoked grants, existing memberships and metadata. An explicit operator demo-password reset remains available. Credential exports leave the password blank for customized accounts; the new password is not recoverable. Older exports may still contain the original shared password, which ceases to work for a changed account.

Tabs on the same hostname share the browser's cookie. Opening another same-host tab does not create an independent user. Use separate browser profiles/private browser sessions for parallel independent testers. The menu checks identity, session and authorization stamps on focus, visibility change and every fifteen seconds while visible. A detected change reloads the workspace, discarding stale in-memory views. This polling is a tester convenience: every protected API request still authorizes independently. It is not instantaneous remote erasure of data already seen. Unsaved edits can be lost when the account/access changes.

The existing Start/Stop launchers retain the same five real services; profile routes use the shared API. No new process or paid AI call is needed. Start performs the additive 0021 migration. Stop retains metadata, hashes, audit history and data; use Sign out all sessions to revoke browser sessions.

Verification covers profile privacy, metadata authorization/uniqueness/revision conflicts, CSRF, wrong-password throttling, token rotation, revocation, password persistence, export behavior and hiding walled clean-team scopes. Automated SQLite and isolated PostgreSQL tests are required alongside the frontend build. Native visual verification remains unavailable when Windows desktop access is denied.

Rollback: retain the encrypted pre-migration backup and all audit records. Roll back the application files if needed while retaining the additive account columns; avoid downgrading a populated live database or restoring old password hashes. Diagnose failures through the retained service logs. A database restore must remain a separately reviewed recovery action.


## Verification recorded 21 November 2026

- Full backend suite: 175 passed, 1 skipped (SQLite-isolated tests).
- Profile plus migration checks: 8 passed with isolated PostgreSQL schemas for the profile tests.
- TypeScript and Vite build passed.
- Pre-migration encrypted backup restored to an isolated database: 49 tables, 2,782 rows; schema and content verified.
- Normal launcher applied 0021 and restarted the five service consoles; HTTPS readiness passed; pgAdmin and owned psql reopened.
- Live HTTPS profile and Resources checks passed for Administration, Firm, Halden and Castlegate. Password rotation, other-session revocation and new-password login passed using a separate synthetic QA account, subsequently disabled with sessions revoked. Named tester passwords were unchanged.
- Native visual check could not run: Windows GetCursorPos returned Access is denied. No visual acceptance is claimed.
