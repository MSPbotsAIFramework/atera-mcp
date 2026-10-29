# PRD-21196 · Code review

## Round 1 · 2026-10-29 · reviewed dev/PRD-21196 @ 46c1937 (base 9f60792)

Verdict: approved

### Scope

`git diff 9f60792...7f859db` (the implementation commit; `46c1937` on top of it only touches
`docs/tickets/PRD-21196.md` self-test/handoff sections, no code). Files touched: `README.md`,
`pyproject.toml`, `src/atera_mcp/server.py`, `src/atera_mcp/tools/_common.py`,
`src/atera_mcp/tools/billing.py` (new), `src/atera_mcp/tools/navigation.py`,
`tests/contract_types.json`, `tests/test_api_client.py`, `tests/test_tools.py`.

### Verification performed

- Re-ran the repo's own gate on `46c1937` (synced with `main @ 9f60792`, no drift since the dev
  round): `uv run pytest -q` → **380 passed, 0 failed, 1 warning** — matches the `[DEV]` stub's
  claim exactly.
- `grep -rnP '[\x{4e00}-\x{9fff}]' --exclude-dir=.git --exclude-dir=.venv .` → no output (no
  Chinese characters in the repo).
- Diffed the repo's "MSPbots Connector" README section (lines 13–85) against
  `~/.claude/skills/vendor-mcp-development/reference/readme-connector-section.md`: only trailing
  blank-line whitespace differs, and that whitespace is identical on both sides of this ticket's
  diff (`git show 9f60792:README.md` vs. working tree) — pre-existing, not touched by this change,
  not a finding against this ticket.
- Read `src/atera_mcp/api_client.py`, `src/atera_mcp/tools/_common.py`,
  `src/atera_mcp/tools/contacts.py` (the copied template) and `src/atera_mcp/server.py` in full
  to confirm the five new tools reuse the shared client, pagination, envelope and
  credential-isolation machinery verbatim rather than re-implementing any of it.
- Confirmed `docs/tickets/PRD-21196.ac.json`: the three manual cases (TC-ATB-003/006/007) are
  recorded `"result": "untested"` with a "needs a real vendor account" note, not claimed as
  passed; the thirteen automated cases map to real, currently-passing tests referenced by file
  and test id.

### Findings

No must-fix findings.

1. [suggestion] `README.md:198-201` ("Delivery notes" or nearby) — not inspected in detail; the
   Handoff section of `docs/tickets/PRD-21196.md` already flags that this merge takes the server
   to 25 tools, above the SOP §14 "≤ 20 tools, curated" guidance, and explains why (four prior
   tickets grew it the same way, this ticket closes a named capability gap). Logged here only so
   it is visible in the review record too — not a reason to withhold approval, since the
   deviation pre-dates this ticket and the ticket's own scope doesn't add an unrelated tool.

### Review against `references/mcp-track.md` §4.3 and `legs/review.md` R3

- **Credentials**: unchanged `X-Atera-Api-Key` → `contextvars` path; the five new tools add no
  credential handling of their own (`billing.py` only calls `client_factory()` via `run_tool`,
  same as every other domain). `test_concurrent_billing_calls_do_not_share_credentials` exercises
  isolation for the new tools specifically rather than assuming it from the other five domains.
- **Tool/param/error contract**: `billing.py`'s five tools match the tech design's Data & API
  contract table exactly (names, required params, Atera paths). Errors route through the same
  `run_tool` → `AteraError.to_envelope()` → `classify_status` path every existing tool uses; no
  new error type introduced.
- **Tests follow the change**: `EXPECTED_TOOLS` (`tests/test_tools.py:44-49`) and
  `tests/contract_types.json` both got the five new entries; `test_api_client.py` gained 18
  billing-specific tests plus three new entries in the shared `PAGED_TOOLS` parametrized suite.
- **README Connector section**: verbatim match modulo pre-existing whitespace (see above).
- **No Chinese in the repo**: confirmed.
- **Cross-repo header compatibility (§1.2)**: not applicable — single repo, no new header, no
  cross-repo dependency (tech design "Rollout & rollback": `release order: any`).
- **Reuse & no duplication**: no new HTTP client, retry, or pagination logic; `AteraClient.get`
  and `_common.py`'s helpers are reused unchanged, exactly as the tech design's Reuse & cleanup
  section states.
- **Range**: strictly additive — no existing tool name, parameter, or behavior changed;
  `tests/test_contract_types.py`'s baseline (76 cases covering the pre-existing 20 tools) passes
  unmodified, confirming AC10.

### Conclusion

Implementation matches the tech design and acceptance criteria. Gates pass on code already
synced with the default branch (`main @ 9f60792`, unchanged since the design pass). Frozen for
merge into `main`, INT publish, and connector wiki check in this same review round.

Status: frozen @ 46c1937
