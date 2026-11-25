# XLSX hidden-content parity and retained-release containment

24 November 2026. [BOUNDED SECURITY FIX] The read-only gate audit in docs80 found that XLSX used the earlier literal parser without XLSM's row/column visibility and metadata scan. A visible sheet's hidden row or column could therefore enter the flattened disclosure text. Root authorized this corrective slice. No model, migration, live source, classification, approval, provider call or restart was changed by the implementation agent.

## Prospective extraction and intake

New XLSX and XLSM intake uses the same bounded literal OOXML safety scan. XLSX extractor version is `literal-workbook-xml-3`; XLSM is `literal-xlsm-inert-2`. Retained metadata includes all worksheet names/states, hidden row numbers and column ranges (including empty hidden ranges), exact literal cells, separate nonexecuting formulas/caches, defined names, comments/person attributes and opaque local relationships/active-part hashes. Macro/active bytes are not interpreted or executed. XLSX continues to reject macro/active package parts under its existing guard.

All relationship targets must resolve to bounded local package members; external, missing, escaping or malformed targets fail. Known workbook/style/theme/property relationships do not themselves classify an ordinary workbook as sensitive. Other relationship types are retained as opaque path/type/target/hash evidence and require protective handling, rather than being followed, rendered or fetched.

The first retained unit contains a versioned `workbook_safety` receipt binding original byte hash, exact visibility/metadata hash, sensitivity and formula presence. Hidden or opaque content sets `sensitive_hidden`, so existing intake now requires explicitly declared scoped clean-team handling and current named source membership. The same protection applies to Halden uploads; an ordinary own-upload request is not a bypass. A normal workbook with no detected hidden/opaque material remains eligible for ordinary intake.

This marker is protective input handling, not automatic legal classification or a source-access grant. It does not assign a user, approve a label, create a finding or release anything.

## Reconstruction and exact historical coordinates

`adapters/workbook_safety.py` reparses immutable original bytes when a workbook disclosure is proposed, reviewed, built or read. It compares retained row text to the safe literal scan, without rewriting source JSON, numbers, offsets or hashes. An old rounded/otherwise incompatible extraction fails closed and requires explicit new-version intake.

The flattened transcript omits whole source row units containing a hidden cell, all hidden-sheet units, formula/cache rows and workbook metadata units. Dropping the whole affected row is deliberately conservative; visible neighbours in that row are not silently reinterpreted or assigned new original offsets. Automatic omission does not rewrite the user's selected removal ranges. The rebuilt output remains a text-only PDF, not an original/native Office container.

Hidden cell values, defined-name literals, comments/person values and formula/cache literals also enter the existing conservative repeated-removed-text validation. They cannot be reintroduced through a title or another surviving unit merely because the new PDF container contains no native objects. The pre-existing lexical threshold still applies to that duplicate-token heuristic; exact physical omission of the selected/hidden units does not depend on it. Human review remains responsible for semantic inference and explicit output meaning.

New workbook artifacts retain the exact fresh visibility receipt in their immutable manifest. Sensitive workbooks require the existing independently reviewed scoped source, complete whole-source review, independent plan review, exact rebuilt-output SME decision and separate antitrust counsel approval. The successful new-workbook acceptance test proves that these controls still permit an appropriately reviewed sanitized transcript; the correction does not merely deny all workbooks.

## Conservative compatibility denials

Existing source bytes, extraction JSON, source snapshots, artifact bytes/JSON, financial facts, releases and decision rows remain untouched.

- A legacy sensitive/formula workbook without the retained safety receipt cannot obtain a new disclosure through an old ordinary/unscanned source. Explicit new-version intake and genuine reviewed handling are required. This fix does not automatically retag or approve that source.
- Current integrity checks deny legacy workbook artifacts lacking the required reviewed safety evidence, or whose stored transcript differs from current safe reconstruction. A previously approved unsafe artifact does not become entitled merely because its old approval is still retained.
- Released financial fact reads and cached citations that depend on that artifact are consequently denied. Financial query/table counts exclude those facts. Original facts and approval history are retained; no amount is replaced or silently reverified.
- External original-source PDP checks require a valid retained workbook safety receipt. An existing named-Halden grant cannot treat absent scan evidence as cleared content. The old grant remains recorded; future reader/download emission is denied. A newly scanned scoped original remains available to its expressly named eligible recipient through the independent existing grant process.
- A legacy workbook artifact without hidden/formula hazards can remain compatible only when the fresh scan and exact sanitized reconstruction establish safety. This is distinct from external access to an unscanned original, which remains closed.

The scoped original-source reader remains the place for a currently authorized firm lawyer to inspect retained evidence and decide whether to create a new version. No live source was scanned into a new persisted row, reclassified or rereleased by this change.

## Files and verification

Production scope: `adapters/spreadsheet_source.py`, `adapters/extraction.py`, `adapters/disclosure.py`, new `adapters/workbook_safety.py`, `services/disclosures.py`, `services/policy.py` and `services/workflow.py`. The latter two include the subsequent shared processing correction below.

New adversarial suite: `tests/test_xlsx_hidden_content.py`. The existing financial-cell fixture intentionally contains a very-hidden sheet; its integration test now obtains real synthetic named clean-team membership and declares that handling instead of relying on the previously permissive ordinary path. Its exact numeric and header-evidence assertions remain unchanged.

Verified before the final complete parity rerun:

- SQLite boundary run: **54 passed in 84.41s**, covering the first15 parity cases plus existing source-cell/disclosure/converter regressions.
- Expanded SQLite financial/converter/context/named-source boundary run: **74 passed in 65.47s**, including20 parity cases.
- PostgreSQL parity/disclosure/named-source/source-cell boundary run: **30 passed in 27.39s**, including20 parity cases in disposable schemas.
- Added positive scanned-workbook/separate-counsel release proof: SQLite **1 passed in4.64s**, PostgreSQL **1 passed in3.68s**.

Before the subsequent processing correction, the complete parity suite passed **21/21 on SQLite in15.09s** and **21/21 with PostgreSQL fixtures in14.34s**. The suite includes pure adapter checks and disposable-database workflow checks. The later results below supersede that module's earlier hash and final count.

These runs overlap; they are not additive unique test totals. No full integrated suite after this source change is inferred from a root suite that started before it. The code is ready for that coordinated regression and controlled restart; neither was performed by this agent.

Coverage includes hidden rows/columns on visible sheets, hidden/very-hidden sheets, empty hidden ranges, comment/name/opaque retention, ordinary intake refusal, named scope, client-upload refusal, unchanged historical offsets/bytes, omitted formulas/caches, duplicate-secret title refusal, fail-closed malformed scan, old-source new-plan denial, already-approved artifact containment through bank reader/download/released financial query/table/cached citation, unchanged original retained records, named-Halden original grant containment and successful current-source release after separate counsel.

This is bounded OOXML visibility/metadata handling, not arbitrary concealment detection, malware scanning, Excel formula compatibility, full native layout redaction, automatic incident investigation or production OS isolation. The broader financial/converter/specialist/public gates in docs80 remain partial.

## Subsequent shared processing boundary

Root identified that the first canonical workbook receipt guard ran only for external actors. A real isolated semantic-service adversarial test confirmed the missing boundary: under an otherwise approved cloud-processing policy, a retained legacy hidden-row workbook with ordinary source handling returned201 and invoked the mocked `embeddings.send` spy **once**. No actual provider call/key was used. The newly scanned safe ordinary workbook positive case also succeeded, demonstrating this was a processing eligibility gap rather than an unavailable provider.

The corrected shared boundary is:

- `workbook_safety.processing` requires retained visibility evidence for any workbook processing, plus explicitly reviewed scoped handling when the scan is protective. Missing evidence causes processing refusal; it does not change source classification.
- Canonical `policy.evaluate(..., action='analyze')` applies this requirement for **internal and external** actors before analysis authority is returned.
- `workflow.processing_allowed` independently walks the complete original lineage and checks every underlying workbook before applying environment-policy permission. A published environment policy cannot override missing workbook visibility evidence. This covers callers such as jobs, semantic search, paid answer synthesis, report synthesis, intelligence embeddings and DDR evidence/revalidation that already use these shared services.
- Internal source read/triage remains available under its existing canonical source authority for inspection and recovery. No legacy source, role, classification or approval is automatically retagged or changed. A legacy ordinary workbook without a receipt is conservatively blocked from processing even if a fresh scan finds no hidden values; explicit reviewed new-version intake establishes retained evidence.
- Sanitized-document authorization already refuses `analyze` (`DISCLOSURE_READ_ONLY`). The shared processing check also follows its original lineage, so a derived/report caller cannot use a sanitized policy object to skip the original workbook guard. The retained-artifact adversarial case exercises both refusals.

Post-fix real semantic-service evidence: the legacy unsafe source returns409 with **zero send calls**, no citations and no protected marker; internal reader/read/triage still succeeds and source bytes/ordinary classification remain unchanged. The newly scanned safe ordinary source returns201 with **one mocked send call** and the expected semantic route. Direct source analyze and shared processing checks exercise the independent guards as well.

Final verification after this correction: **40/40 SQLite tests passed in41.80s** across the now23-case parity suite, retrieval, full-AI review and DDR evidence suites. The complete parity suite with disposable PostgreSQL fixtures passed **23/23 in19.66s**. All fixture schemas cleaned up; no PostgreSQL tests remained active at handoff. Current test-module SHA256: `8d3ae5d5894af4654444ee21783ea717705001e06b0867ef1be82ab0f2a7ab65`. These are component/boundary results, not a substitute for root's subsequent frozen-source integrated regression and controlled restart.
