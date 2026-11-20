import React, { useEffect, useState } from 'react';
import { ChevronRight, CircleCheck, CircleAlert, ShieldAlert, ShieldCheck, Terminal } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { copyText, useToast } from '../components/ui';
import { errorMessage } from '../lib/errors';
import { McpGuide } from '../components/McpGuide';
import { DEFAULT_LAUNCH, configJson, launchFromStatus } from '../lib/mcpConfig';

interface McpStatus { mcp_installed: boolean; mcp_version: string | null; python_executable: string; server_command: string; server_args: string[]; groq_configured?: boolean; groq_model?: string }
interface McpTool { name: string; description: string; read_only: boolean; destructive: boolean }
interface RuleEntry { rule_id: string; category: string; title: string; issue: string; impact: string; recommendation: string }

export const AgentScreen: React.FC<{ hasBackend: boolean; onRuleCount?: (n: number) => void }> = ({ hasBackend, onRuleCount }) => {
  const toast = useToast();
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [tools, setTools] = useState<{ live: boolean; message?: string; tools: McpTool[] } | null>(null);
  const [rules, setRules] = useState<RuleEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasBackend) return;
    (async () => {
      try {
        const [s, t, r] = await Promise.all([
          apiFetch('/api/mcp/status').then((x) => x.json()),
          apiFetch('/api/mcp/tools').then((x) => x.json()),
          apiFetch('/api/mcp/rules').then((x) => x.json()),
        ]);
        setStatus(s); setTools(t);
        const list: RuleEntry[] = Object.values(r.rules || {});
        setRules(list); onRuleCount?.(list.length);
      } catch (e) {
        setError(errorMessage(e) || 'Could not load the MCP details.');
      }
    })();
  }, [hasBackend, onRuleCount]);

  const launch = launchFromStatus(status);
  const config = status ? configJson(launch) : '';

  if (!hasBackend) {
    return (
      <>
        <div className="page-head"><div><p>pbiscan can run as a Model Context Protocol server, so coding agents can scan projects and read findings.</p></div></div>
        <div className="notice"><Terminal aria-hidden="true" /><div className="grow"><strong>Tool status needs the local engine.</strong> Start the MCP server with:
          <pre className="code" style={{ marginTop: 8 }}>pip install "pbiscan[mcp]"{'\n'}pbiscan mcp</pre></div></div>
        <McpGuide launch={DEFAULT_LAUNCH} exact={false} />
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <div><p>Every scan and rule is deterministic. Agents get the same deterministic results through the tools below. The DAX rewrite advisor, the only part that can call a language model, is on the Measures screen.</p></div>
        <div className="actions">
          {tools && <span className="chip">{tools.tools.length} tools</span>}
          {rules.length > 0 && <span className="chip">{rules.length} rules</span>}
        </div>
      </div>
      {error && <div className="notice error"><CircleAlert aria-hidden="true" /><span className="grow">{error}</span></div>}

      <McpGuide launch={launch} exact={!!status?.python_executable} />

      <div className="grid-2">
        <section className="panel">
          <div className="panel-head"><h2>Connect an agent</h2><span className="grow" />{status && (status.mcp_installed ? <span className="chip good">ready</span> : <span className="chip warn">not installed</span>)}</div>
          <div className="panel-body">
            {!status ? <p className="muted" style={{ margin: 0 }}>Loading…</p> : status.mcp_installed ? (
              <>
                <p className="ink-2" style={{ margin: 0, fontSize: 13 }}><CircleCheck size={14} style={{ verticalAlign: -2, color: 'var(--good)' }} aria-hidden="true" /> <span className="mono">mcp</span> {status.mcp_version ? `v${status.mcp_version}` : ''} is installed. Add this to your agent's MCP config:</p>
                <pre className="code">{config}</pre>
                <div className="actions"><button className="btn btn-sm" onClick={async () => toast((await copyText(config)) ? 'Copied the MCP config.' : 'Copying is blocked here.')}>Copy config</button></div>
              </>
            ) : (
              <>
                <p className="ink-2" style={{ margin: 0, fontSize: 13 }}>Install the MCP extra, then run <span className="mono">pbiscan mcp</span>.</p>
                <pre className="code">pip install "pbiscan[mcp]"</pre>
              </>
            )}
          </div>
        </section>

        <section className="panel">
          <div className="panel-head"><h2>Tools</h2><span className="grow" />{tools && !tools.live && <span className="muted small">static list</span>}{tools && tools.live && <span className="muted small">{tools.tools.filter((t) => !t.destructive).length} read only, {tools.tools.filter((t) => t.destructive).length} change files</span>}</div>
          <div className="table-wrap"><table className="tbl" aria-label="MCP tools">
            <thead><tr><th scope="col">Tool</th><th scope="col">Access</th></tr></thead>
            <tbody>
              {(tools?.tools || []).map((t) => (
                <tr key={t.name}>
                  <td><span className="mono">{t.name}</span><div className="muted small">{t.description}</div></td>
                  <td className="nowrap">{t.destructive ? <span className="chip hot"><ShieldAlert size={13} aria-hidden="true" />Changes files</span> : <span className="muted"><ShieldCheck size={13} aria-hidden="true" style={{ verticalAlign: -2, color: 'var(--good)' }} /> Read only</span>}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head"><h2>Rule catalog</h2><span className="grow" /><span className="muted small">{rules.length} rules, also at <span className="mono">pbiscan://rules</span></span></div>
        {rules.map((r) => (
          <details key={r.rule_id} className="disclosure" style={{ borderBottom: '1px solid var(--line)' }}>
            <summary style={{ padding: '10px 16px' }}><ChevronRight aria-hidden="true" /><span className="mono" style={{ fontSize: 12.5 }}>{r.rule_id}</span><span className="muted" style={{ fontSize: 12 }}>{r.category}</span></summary>
            <dl className="kv" style={{ padding: '0 16px 14px 38px' }}>
              <dt>issue</dt><dd>{r.issue}</dd><dt>impact</dt><dd>{r.impact}</dd><dt>fix</dt><dd>{r.recommendation}</dd>
            </dl>
          </details>
        ))}
      </section>
    </>
  );
};
