import React, { useEffect, useState } from 'react';
import { ChevronRight, CircleCheck, CircleAlert, ShieldAlert, ShieldCheck, Sparkles, Terminal } from 'lucide-react';
import { apiFetch } from '../utils/api';
import { DaxCode } from '../lib/dax';
import { copyText, useToast } from '../components/ui';

interface McpStatus { mcp_installed: boolean; mcp_version: string | null; python_executable: string; server_command: string; server_args: string[]; groq_configured?: boolean; groq_model?: string }
interface McpTool { name: string; description: string; read_only: boolean; destructive: boolean }
interface RuleEntry { rule_id: string; category: string; title: string; issue: string; impact: string; recommendation: string }
interface Rewrite { ai_generated: boolean; ai_model?: string; suggested_rewrite?: string; rewrite_explanation?: string; recommendation?: string; advisory_note?: string; error?: string }

export const AgentScreen: React.FC<{ hasBackend: boolean; onRuleCount?: (n: number) => void }> = ({ hasBackend, onRuleCount }) => {
  const toast = useToast();
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [tools, setTools] = useState<{ live: boolean; message?: string; tools: McpTool[] } | null>(null);
  const [rules, setRules] = useState<RuleEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dax, setDax] = useState('CALCULATE ( SUM ( Sales[Amount] ), FILTER ( ALL ( Sales ), Sales[Amount] > 1000 ) )');
  const [rewrite, setRewrite] = useState<Rewrite | null>(null);
  const [asking, setAsking] = useState(false);

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
      } catch (e: any) {
        setError(e.message || 'Could not load the MCP details.');
      }
    })();
  }, [hasBackend, onRuleCount]);

  const ask = async () => {
    setAsking(true); setRewrite(null);
    try {
      const res = await apiFetch('/api/dax/rewrite', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rule_id: 'DAX_SUSPICIOUS_PATTERN', dax_expression: dax, evidence: '' }),
      });
      setRewrite(await res.json());
    } catch (e: any) {
      setRewrite({ ai_generated: false, error: e.message || 'The rewrite request failed.' });
    } finally {
      setAsking(false);
    }
  };

  const config = status ? JSON.stringify({ mcpServers: { pbiscan: { command: status.server_command, args: status.server_args } } }, null, 2) : '';

  if (!hasBackend) {
    return (
      <>
        <div className="page-head"><div><h2>Agent &amp; MCP</h2><p>pbiscan can run as a Model Context Protocol server, so coding agents can scan projects and read findings.</p></div></div>
        <div className="notice"><Terminal aria-hidden="true" /><div className="grow"><strong>Tool status needs the local engine.</strong> Start the MCP server with:
          <pre className="code" style={{ marginTop: 8 }}>pip install "pbiscan[mcp]"{'\n'}pbiscan mcp</pre></div></div>
      </>
    );
  }

  return (
    <>
      <div className="page-head"><div><h2>Agent &amp; MCP</h2><p>Every scan and rule is deterministic. The optional DAX rewrite advisor below is the only feature that calls a language model, and its output is text for you to review.</p></div></div>
      {error && <div className="notice error"><CircleAlert aria-hidden="true" /><span className="grow">{error}</span></div>}

      <div className="grid-2">
        <section className="panel">
          <div className="panel-head"><h3>MCP server</h3><span className="spacer" />{status && (status.mcp_installed ? <span className="chip good">ready</span> : <span className="chip warn">not installed</span>)}</div>
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
          <div className="panel-head"><h3>Tools</h3><span className="spacer" />{tools && !tools.live && <span className="label">static list</span>}</div>
          {(tools?.tools || []).map((t) => (
            <div key={t.name} className="trans" style={{ gridTemplateColumns: '18px minmax(0,1fr) auto' }}>
              {t.destructive ? <ShieldAlert size={15} style={{ color: 'var(--sev-high)' }} aria-hidden="true" /> : <ShieldCheck size={15} style={{ color: 'var(--good)' }} aria-hidden="true" />}
              <span className="t mono" style={{ fontSize: 12.5 }}>{t.name}</span>
              <span className={`chip ${t.destructive ? 'warn' : ''}`}>{t.destructive ? 'writes files · host confirms' : 'read-only'}</span>
              <span className="s" style={{ fontFamily: 'var(--f-body)' }}>{t.description}</span>
            </div>
          ))}
        </section>
      </div>

      <section className="panel">
        <div className="panel-head"><Sparkles size={16} aria-hidden="true" /><h3>DAX rewrite advisor</h3><span className="spacer" />
          {status?.groq_configured ? <span className="chip good">{status.groq_model}</span> : <span className="chip">GROQ_API_KEY not set · static guidance</span>}
        </div>
        <div className="panel-body">
          <label className="label" htmlFor="dax-in">DAX to review</label>
          <textarea id="dax-in" className="input mono" rows={3} value={dax} onChange={(e) => setDax(e.target.value)} style={{ resize: 'vertical' }} />
          <div className="actions"><button className="btn btn-primary" onClick={ask} disabled={asking || !dax.trim()}>{asking ? 'Asking…' : 'Suggest a rewrite'}</button></div>
          {rewrite && (rewrite.error ? <div className="notice error"><CircleAlert aria-hidden="true" /><span className="grow">{rewrite.error}</span></div>
            : rewrite.ai_generated && rewrite.suggested_rewrite ? (
              <>
                <div className="label">Suggested rewrite · {rewrite.ai_model} · review before using</div>
                <DaxCode code={rewrite.suggested_rewrite} />
                {rewrite.rewrite_explanation && <p className="ink-2" style={{ margin: 0, fontSize: 13.5 }}>{rewrite.rewrite_explanation}</p>}
              </>
            ) : <div className="notice"><span className="grow"><strong>Static guidance:</strong> {rewrite.recommendation}</span></div>)}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head"><h3>Rule catalog</h3><span className="spacer" /><span className="label">{rules.length} rules · pbiscan://rules</span></div>
        {rules.map((r) => (
          <details key={r.rule_id} className="disclosure" style={{ borderBottom: '1px solid var(--rule)' }}>
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
