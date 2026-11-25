# One-click launch — all local surfaces

Double-click `C:\Freshfields-Takehome\START_KESTREL.bat` (the handoff-root Start file works too).

Cold start launches the dedicated PostgreSQL database, builds the frontend with retained output, and starts the visible HTTP/HTTPS backend CMD consoles. Windows may host the CMD consoles in Windows Terminal.

After service readiness, the default browser receives 25 tabs:
- Launch page.
- Admin, Firm, Halden and Castlegate authenticated portal/login pages.
- Four corresponding read-only design previews.
- Full Swagger on each portal host.
- Every API-specific Swagger group, discovered from the actual backend group inventory.

The Python inventory helper reads literal Swagger metadata without importing/running the backend. Adding another Swagger group automatically adds a launch target. No passwords, tokens or automatic sign-in are involved. Separate tabs are views of the same shared API, not duplicate backend deployments.

A second Start checks readiness and reopens every surface without duplicating healthy services. If the recorded project is unhealthy, clicking Start is an explicit manual restart request: only its validated owned process tree is restarted, with database/logs retained. There is no automatic background recovery. Browser-open failures are printed and cause a failing exit code; batch wrappers preserve that exit code. Stop remains project-scoped.

HTTPS self-signed certificate warnings are not bypassed or trusted automatically. The user must handle those prompts. Browser/default-app preferences determine tab versus window placement. `-NoOpen` remains an internal diagnostic option; the double-click batch does not use it.

Verification: PowerShell parser check passed; all 25 distinct URLs returned HTTP 200 using loopback transport and their correct Host headers; the actual Start batch invoked the default browser for all 25 targets successfully. Warm start preserved the existing services. Existing cold-start console/service lifecycle had already been verified; the common browser-opening function is now called by both cold and warm branches. No broad application test rerun was required for this launcher-only change.
