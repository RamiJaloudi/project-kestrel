# Local heartbeat publication recovery

24 November 2026. [OBSERVED LOCAL INCIDENT / NARROW FIX]

The Resources rollout found the prior supervisor had stopped. Retained evidence localizes the earlier failure to HTTPS status publication at 12:19:13 UTC: the old `https.54496.tmp` contains a complete ready record, the last published/logged pulse was 12:19:03, successful API responses continued through 12:19:25, and the supervisor failed closed for a stale heartbeat at 12:19:28. Other components still pulsed. No retained exception establishes the historical error type. A transient Windows replacement/sharing error is plausible, not proven. The original temporary record and logs remain intact.

The former status writer made one replace attempt; an ordinary write error escaped its daemon pulse. Fault injection reproduced that silent heartbeat-thread failure while the main component could remain alive. The earlier reader-side PermissionError test did not cover this writer boundary.

`scripts/console_runner.py` now serializes status writes, uses unique per-write temporary files and makes at most four attempts for transient write/replace errors with 25/50/100 ms waits. Exhaustion preserves the prior published timestamp and retained temporary evidence. Permanent storage failures are not retried. Pulse exceptions receive sanitized diagnostics and do not themselves kill the heartbeat loop. An unavailable diagnostics store also cannot terminate the next pulse. No component, job or provider request restarts automatically; prolonged absence still triggers the supervisor's unchanged stale-pulse failure.

Shutdown stops and joins the pulse before publishing terminal state. The writer checks the stop event while holding its lock, and the health probe uses a copied state, preventing a delayed probe from publishing ready after terminal failure. Finite retries do not solve an indefinitely blocked OS operation or console; stale-heartbeat containment remains the local fallback.

The focused supervisor suite passed **17 cases in 0.23 seconds**: prior reader/process checks plus transient writer recovery, bounded exhaustion without timestamp refresh, permanent failure, sanitized pulse survival, diagnostic failure, distinct concurrent temporary files, shutdown ordering and a late-probe race. These are deterministic temporary-file/fake-probe cases. They do not establish Azure service, long-duration availability or production recovery assurance. No database migration or retained business record changed.

Root reviewed the implementation and reran supervisor plus existing observability/governance checks together: **23 passed in 10.86 seconds**. A controlled Stop/Start then completed with exit0; all existing demo fixture decisions were preserved. The application remains local-only.
