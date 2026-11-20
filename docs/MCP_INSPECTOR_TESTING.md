# Testing the MCP server in the browser (MCP Inspector)

**Verification status: the checklist below passes through the Inspector CLI. Still not done: the browser UI click-through, the Groq check, and the Claude Desktop and Cursor steps.**

Verified on 2026-11-20:
- The automated MCP tests pass (`tests/unit/test_mcp_server.py` and
  `tests/integration/test_mcp_client_e2e.py`, which now includes applying a whole multi-file plan
  with a suppression that has to survive the apply).
- A scripted MCP client drove all 8 tools over stdio against a copy of a real project: scan,
  lineage, plan, suppress, apply (score 54.1 to 98.7) and diff, plus a fake patch id (no change), a
  missing path and an unknown measure (clean errors).
- A real agent (Claude Code in VS Code, with the server added through a project `.mcp.json`) scanned,
  planned and applied fixes, and Studio then showed the same score, history entry and counts.

Also verified on 2026-11-20: checks 2 and 6 to 15 in the checklist below, run through the Inspector's
own command-line client (`--cli`, Inspector v0.15.0), which is the same MCP client the browser UI uses.
It drove `pbiscan mcp` over stdio against copies of `test_bidirectional`.

Not verified: clicking through the Inspector's browser UI, the optional check 16 (it needs your own
Groq key), and the Claude Desktop and Cursor set-up steps on the Agent & MCP screen. The guide's steps
were compared with Claude's and Cursor's current documentation, but not run in the apps.

MCP Inspector is the official browser UI for MCP servers. It starts `pbiscan mcp` as a separate
process and lets you call each tool by hand, the same way an agent such as Claude or Cursor would.

---

## Before you start

| Need | How to check | Expected |
|---|---|---|
| Node.js 18 or later | `node --version` | `v20.18.0` or later |
| pbiscan installed with the MCP extra | `pip install -e ".[mcp]"` from the repo root | No errors |
| `pbiscan` on PATH | `where.exe pbiscan` | `C:\Users\TARUN\python 3.11\Scripts\pbiscan.exe` |

Run every command in **PowerShell**: press **Win**, type `powershell` and press **Enter**. VS Code's
**Terminal → New Terminal** also works.

---

## Step 1: Make test copies of a fixture

`apply_remediation` and `add_suppression` change files on disk. Never point them at the golden
fixtures in the repo or at a real report.

```powershell
$src = "D:\Projects\Powerbi\Power_BI_Report_Quality_&_Performance_Scanner\tests\golden\test_bidirectional"
Copy-Item -Recurse $src C:\Users\TARUN\mcp-test
Copy-Item -Recurse $src C:\Users\TARUN\mcp-test-suppress
```

`test_bidirectional` is a small model with one table pair, `Sales` and `Customer`, joined by a
both-directions relationship, plus one measure, `Total Revenue`.

## Step 2: Start the Inspector

Start it from your home folder, not from the repo. The `&` in the repo path breaks `npx`.

```powershell
cd C:\Users\TARUN
npx @modelcontextprotocol/inspector pbiscan mcp
```

- Type `y` if npx asks to install the package.
- The terminal prints a URL such as `http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=...`. The browser
  usually opens it by itself. If it doesn't, copy the **whole** URL, including the token.
- Keep this PowerShell window open while you test. Press **Ctrl+C** in it when you finish.

## Step 3: Connect

In the left panel of the Inspector:

| Field | Value |
|---|---|
| Transport Type | `STDIO` |
| Command | `pbiscan` |
| Arguments | `mcp` |

Click **Connect**. The status turns green and the server name shows as **PBIP Sentinel**.

## Step 4: Check that the tools, resources and prompts are listed

- **Tools** tab → **List Tools**: 8 tools.
  - Read-only: `scan_model`, `diff_models`, `get_measure_lineage`, `plan_remediation`,
    `list_suppressions`, `suggest_dax_rewrite`.
  - Writes files: `apply_remediation`, `add_suppression`.
- **Resources** tab → **List Resources**: open `pbiscan://rules`. You get the JSON rule catalog.
  Also try the template `pbiscan://rules/{rule_id}` with `rule_id` = `MODEL_BIDIRECTIONAL`.
- **Prompts** tab → **List Prompts**: `audit-model`, `remediate-safely`, `inspect-dax-measure`.
  Open `audit-model` with `path` = `C:\Users\TARUN\mcp-test`. You get the prompt text back.

## Step 5: Call the read-only tools

Select a tool, fill in its fields and click **Run Tool**. The JSON result appears underneath.

| Tool | Inputs | Expected result |
|---|---|---|
| `scan_model` | `path` = `C:\Users\TARUN\mcp-test` | `scores.overall` = **98.7**. One finding: `MODEL_BIDIRECTIONAL` (WARNING) at `Sales[CustomerID] ↔ Customer[CustomerID]` |
| `get_measure_lineage` | `path` = `C:\Users\TARUN\mcp-test`, `measure_name` = `Total Revenue` | `expression` = `SUM(Sales[Amount])`, `is_reachable_from_visual` = `true`, used by visual `Sales Overview.barChart` |
| `list_suppressions` | `path` = `C:\Users\TARUN\mcp-test` | `total_suppressions` = `0` |
| `diff_models` | `baseline_path` and `current_path` both = `C:\Users\TARUN\mcp-test` | Score drift of 0 |
| `plan_remediation` | `path` = `C:\Users\TARUN\mcp-test` | `total_proposals` = 1, `validation.accepted` = `true`, `before_score` 98.7 → `after_score` **100.0**. The patch ID starts with `REM-MODEL_BIDIRECTIONAL-Sales_Customer-`. **Copy it** for Step 6 |
| `suggest_dax_rewrite` | `rule_id` = `DAX_IFERROR`, `dax_expression` = `IFERROR(1/0, 0)` | Without a `GROQ_API_KEY`, an advisory result with a generic recommendation. It must not return an error |

After these calls, `C:\Users\TARUN\mcp-test` must be unchanged. No `.bak_` folder should appear next to it.

## Step 6: Call the tools that write files

The Inspector does **not** ask you to confirm before running these tools. Only agent apps act on the
"writes files, host confirms" label.

**`apply_remediation`**

- `path` = `C:\Users\TARUN\mcp-test`
- `patch_ids` = `["REM-MODEL_BIDIRECTIONAL-Sales_Customer-xxxxxxxx"]`, the ID you copied in Step 5

Expected:

- `status` = `APPLIED`, `applied_count` = 1, score 98.7 → 100.0.
- A `manifest_id` starting with `MAN-`.
- A `backup_location` folder `C:\Users\TARUN\mcp-test.bak_<timestamp>` that exists on disk.
- Running `scan_model` again gives `overall` = 100.0 and no findings.
- Running `plan_remediation` again gives 0 proposals.

**`add_suppression`** (on the second copy)

- `path` = `C:\Users\TARUN\mcp-test-suppress`
- `rule_id` = `MODEL_BIDIRECTIONAL`
- `location` = `Sales[CustomerID] ↔ Customer[CustomerID]`. Copy it from the `scan_model` output for
  this folder; the `↔` must match exactly.
- `reason` = `Testing suppression via MCP Inspector`

Expected:

- `C:\Users\TARUN\mcp-test-suppress\pbiscan.suppressions.json` now exists.
- `list_suppressions` returns `total_suppressions` = 1.
- `scan_model` no longer reports the finding as active.

## Step 7: Check the error handling

| Call | Expected |
|---|---|
| `scan_model` with `path` = `C:\does-not-exist` | A clear error message. The server keeps running |
| `get_measure_lineage` with `measure_name` = `No Such Measure` | A "not found" style result, not a crash |
| `apply_remediation` with `patch_ids` = `["REM-FAKE"]` | Nothing applied, and no `.bak_` folder created |

After each of these calls, the Inspector should still show the server as connected.

## Step 8 (optional): The DAX rewrite advisor with Groq

1. Press **Ctrl+C** in the Inspector's PowerShell window.
2. Set the key: `$env:GROQ_API_KEY = "gsk_..."`.
3. Start the Inspector again as in Step 2.
4. Run `suggest_dax_rewrite` as in Step 5. The recommendation should now be specific to the DAX you
   passed in, and the result should still include the advisory note.

## Step 9: Clean up

```powershell
Remove-Item -Recurse -Force C:\Users\TARUN\mcp-test, C:\Users\TARUN\mcp-test-suppress
Remove-Item -Recurse -Force C:\Users\TARUN\mcp-test.bak_*
```

---

## Verification checklist

**Status: PASSED through the Inspector CLI (headless, same MCP client). Not done: clicking through the Inspector browser UI, and the optional check 16 (needs your own Groq key).**

| # | Check | Status |
|---|---|---|
| 1 | Inspector starts and connects; the server shows as **PBIP Sentinel** | ✅ Passed (2026-10-07, Inspector v0.15.0, Node 20.18) |
| 2 | 8 tools listed with correct read-only and writes-files annotations | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 3 | `pbiscan://rules` and `pbiscan://rules/MODEL_BIDIRECTIONAL` return JSON | ✅ Passed (after the `%20` fix; see Notes) |
| 4 | 3 prompts listed, and `audit-model` renders | ✅ Passed |
| 5 | `scan_model` returns 98.7 and one `MODEL_BIDIRECTIONAL` finding | ✅ Passed (overall 98.7, model 97, dax 100, report 100) |
| 6 | `get_measure_lineage` shows `Total Revenue` used by a visual | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 7 | `list_suppressions` returns 0 | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 8 | `diff_models` of a folder against itself shows no drift | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 9 | `plan_remediation` proposes 1 accepted patch (98.7 → 100.0) | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 10 | Read-only calls left `mcp-test` unchanged, with no `.bak_` folder | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 11 | `suggest_dax_rewrite` without a key returns an advisory result, not an error | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 12 | `apply_remediation` applies the patch, creates a backup and writes a manifest | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 13 | A rescan after the apply shows 100.0, and a new plan has 0 proposals | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 14 | `add_suppression` writes `pbiscan.suppressions.json`, and the finding stops showing as active | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 15 | Bad inputs return errors without crashing the server | ✅ Passed (2026-11-20, Inspector CLI v0.15.0, headless) |
| 16 | (Optional) `suggest_dax_rewrite` with a Groq key returns a specific rewrite | ⏳ Pending |

Mark each row ✅ Passed or ❌ Failed. For a failure, add a note below with the tool, the inputs you
used and the response you got.

### Notes

- Check 1: after connecting, "Error output from MCP server" showed red text starting
  `C:\Users\TARUN\python...`. Confirmed: it is pydantic_settings'
  `IncompleteFieldDefinitionWarning: Field 'lifespan' has an incomplete definition`, raised when the
  `mcp` package loads (the test suite shows the same warning). It comes from a dependency, not from
  pbiscan, and is harmless: stdio servers write logs to stderr, and the connection stayed up.
- Check 3: a stray trailing space in the template's `rule_id` box reached the server as
  `MODEL_BIDIRECTIONAL%20` and returned "Rule not found". The MCP library passes template values
  through still percent-encoded. **Fixed:** `get_rule_detail_json` in `pbiscan/mcp/resources.py`
  now URL-decodes the id before trimming it, and a unit test covers this. Restart the server and
  re-run check 3.
- Check 3: the `rule_id` box shows "No results found" while you type. The server does not offer
  suggestions for this field yet, so the list is empty, but the value you type is still used.
  Optional improvement: suggest the 13 rule ids.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `spawn pbiscan ENOENT` when you click Connect | Set **Command** to the full path `C:\Users\TARUN\python 3.11\Scripts\pbiscan.exe` |
| `MCP server failed to start ... Install the MCP extra` | Run `pip install -e ".[mcp]"` from the repo root |
| npx reports an unsupported Node version | Run `npx @modelcontextprotocol/inspector@0.14.0 pbiscan mcp`, or upgrade Node to 22 |
| npx fails with odd path errors | Make sure you're not inside the repo folder; `cd C:\Users\TARUN` first |
| The browser asks for a proxy token | Open the full URL printed in the terminal, including `?MCP_PROXY_AUTH_TOKEN=...` |
| A tool call hangs | Check the **Server Notifications** / **History** panes at the bottom of the Inspector, then restart it |
