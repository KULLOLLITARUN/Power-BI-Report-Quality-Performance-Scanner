import React, { useEffect, useState } from 'react';
import { Plug, Terminal, Copy, Check, CircleCheck, CircleAlert, ShieldCheck, ShieldAlert, BookOpen } from 'lucide-react';

interface McpStatus {
  mcp_installed: boolean;
  mcp_version: string | null;
  python_executable: string;
  server_command: string;
  server_args: string[];
  groq_configured?: boolean;
  groq_model?: string;
}

interface McpTool {
  name: string;
  description: string;
  read_only: boolean;
  destructive: boolean;
}

interface McpToolsResponse {
  live: boolean;
  message?: string;
  tools: McpTool[];
}

interface RuleEntry {
  rule_id: string;
  category: string;
  title: string;
  issue: string;
  impact: string;
  recommendation: string;
}

interface DaxRewriteResult {
  ai_generated: boolean;
  ai_model?: string;
  suggested_rewrite?: string;
  rewrite_explanation?: string;
  recommendation?: string;
  advisory_note?: string;
  error?: string;
}

interface AgentIntegrationPanelProps {
  hasBackend?: boolean;
}

const CopyButton: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="flex items-center gap-1.5 px-2.5 py-1 rounded border text-[11px] font-mono font-medium transition"
      style={{
        backgroundColor: 'var(--bg-canvas)',
        borderColor: 'var(--border-hairline)',
        color: copied ? 'var(--accent)' : 'var(--text-secondary)',
      }}
    >
      {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
      <span>{copied ? 'Copied' : 'Copy'}</span>
    </button>
  );
};

export const AgentIntegrationPanel: React.FC<AgentIntegrationPanelProps> = ({ hasBackend = false }) => {
  const [status, setStatus] = useState<McpStatus | null>(null);
  const [tools, setTools] = useState<McpToolsResponse | null>(null);
  const [rules, setRules] = useState<Record<string, RuleEntry> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [daxInput, setDaxInput] = useState('SUM(Sales[Amount]) / SUM(Sales[Units])');
  const [daxOutput, setDaxOutput] = useState<DaxRewriteResult | null>(null);
  const [daxLoading, setDaxLoading] = useState(false);

  const handleTestGroq = async () => {
    if (!daxInput.trim()) return;
    setDaxLoading(true);
    setDaxOutput(null);
    try {
      const res = await fetch('/api/dax/rewrite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rule_id: 'DAX_SUSPICIOUS_PATTERN',
          dax_expression: daxInput,
          evidence: '',
        }),
      });
      const data = await res.json();
      setDaxOutput(data);
    } catch (e: any) {
      setDaxOutput({ ai_generated: false, error: e.message || 'Failed to call Groq' });
    } finally {
      setDaxLoading(false);
    }
  };

  useEffect(() => {
    if (!hasBackend) return;

    (async () => {
      try {
        const [statusRes, toolsRes, rulesRes] = await Promise.all([
          fetch('/api/mcp/status').then((r) => r.json()),
          fetch('/api/mcp/tools').then((r) => r.json()),
          fetch('/api/mcp/rules').then((r) => r.json()),
        ]);
        setStatus(statusRes);
        setTools(toolsRes);
        setRules(rulesRes.rules);
      } catch (err: any) {
        setError(err.message || 'Failed to load Agent / MCP integration data');
      }
    })();
  }, [hasBackend]);

  if (!hasBackend) {
    return (
      <div className="space-y-5 font-mono">
        <div
          className="p-5 rounded-lg border"
          style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}
        >
          <div className="flex items-center gap-2 mb-2">
            <Plug className="w-5 h-5" style={{ color: 'var(--accent)' }} />
            <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
              Agent / MCP Integration
            </h2>
          </div>
          <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
            [Web Workbench Mode] MCP server configuration requires a local Python backend.
            Run <code>pbiscan studio "path/to/your.pbip"</code> locally to see live tool status
            and the Groq-backed DAX rewrite advisor here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 font-mono">
      {/* Header */}
      <div
        className="p-5 rounded-lg border"
        style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}
      >
        <div className="flex items-center gap-2 mb-2">
          <Plug className="w-5 h-5" style={{ color: 'var(--accent)' }} />
          <h2 className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>
            Agent / MCP Integration
          </h2>
        </div>
        <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>
          Run <code>pbiscan mcp</code> to expose this deterministic engine over the Model Context Protocol.
          The core scanner remains 100% deterministic and AI-free — Groq is used only by the one advisory
          tool inspected below, and only when a <code>GROQ_API_KEY</code> is configured.
        </p>
      </div>

      {error && (
        <div
          className="p-4 rounded border text-xs"
          style={{ backgroundColor: 'var(--severity-critical-bg)', borderColor: 'var(--severity-critical-border)', color: 'var(--severity-critical)' }}
        >
          {error}
        </div>
      )}

      {/* Groq AI DAX Advisor Card */}
      <div
        className="p-4 rounded-lg border"
        style={{
          backgroundColor: 'var(--bg-surface)',
          borderColor: status?.groq_configured ? 'var(--accent)' : 'var(--border-hairline)',
        }}
      >
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-base">⚡</span>
            <div>
              <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
                Groq DAX Rewrite Advisor
              </h3>
              <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Model: <code>{status?.groq_model || 'openai/gpt-oss-120b'}</code>
              </div>
            </div>
          </div>
          {status?.groq_configured ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold" style={{ backgroundColor: 'var(--accent-glow)', color: 'var(--accent)' }}>
              <CircleCheck className="w-3.5 h-3.5" />
              <span>Configured</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px]" style={{ backgroundColor: 'var(--bg-canvas)', color: 'var(--text-muted)' }}>
              <span>Not configured — set GROQ_API_KEY in .env</span>
            </div>
          )}
        </div>

        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          This is the only place AI touches pbiscan: an advisory, read-only suggestion for a flagged DAX
          expression. Nothing here is ever applied automatically — it's text for you to review.
        </p>

        {/* Live interactive test */}
        <div className="p-3 rounded border" style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-hairline)' }}>
          <div className="text-xs font-bold mb-1.5" style={{ color: 'var(--text-primary)' }}>
            Try a DAX Rewrite
          </div>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={daxInput}
              onChange={(e) => setDaxInput(e.target.value)}
              placeholder="e.g. SUM(Sales[Amount]) / SUM(Sales[Units])"
              className="flex-1 px-2.5 py-1.5 text-xs rounded border bg-transparent font-mono"
              style={{ borderColor: 'var(--border-hairline)', color: 'var(--text-primary)' }}
            />
            <button
              onClick={handleTestGroq}
              disabled={daxLoading}
              className="px-3 py-1.5 rounded text-xs font-bold transition"
              style={{
                backgroundColor: 'var(--accent)',
                color: '#000',
                opacity: daxLoading ? 0.7 : 1,
              }}
            >
              {daxLoading ? 'Asking Groq...' : '⚡ Suggest Rewrite'}
            </button>
          </div>

          {daxOutput && (
            <div
              className="p-3 rounded border text-xs mt-2 space-y-2"
              style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}
            >
              {daxOutput.error && (
                <div style={{ color: 'var(--severity-critical)' }}>{daxOutput.error}</div>
              )}

              {daxOutput.ai_generated && daxOutput.suggested_rewrite ? (
                <>
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
                      Suggested Rewrite ({daxOutput.ai_model})
                    </div>
                    <pre
                      className="p-2 rounded mt-1 overflow-x-auto font-mono text-xs"
                      style={{ backgroundColor: 'var(--bg-canvas)', color: 'var(--text-primary)' }}
                    >
                      {daxOutput.suggested_rewrite}
                    </pre>
                  </div>
                  {daxOutput.rewrite_explanation && (
                    <div>
                      <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                        Why this is better
                      </div>
                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                        {daxOutput.rewrite_explanation}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                !daxOutput.error && (
                  <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                      {status?.groq_configured ? 'Groq unavailable — static guidance' : 'Static guidance (Groq not configured)'}
                    </div>
                    <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                      {daxOutput.recommendation}
                    </div>
                  </div>
                )
              )}
            </div>
          )}
        </div>
      </div>

      {/* Environment status */}
      <div className="p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}>
        <div className="flex items-center gap-2 mb-3">
          <Terminal className="w-4 h-4" style={{ color: 'var(--accent)' }} />
          <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Environment</h3>
        </div>
        {status ? (
          <div className="flex items-center gap-2 text-xs">
            {status.mcp_installed ? (
              <>
                <CircleCheck className="w-4 h-4" style={{ color: 'var(--accent)' }} />
                <span style={{ color: 'var(--text-secondary)' }}>
                  <code>mcp</code> package installed{status.mcp_version ? ` (v${status.mcp_version})` : ''} — ready to run <code>pbiscan mcp</code>.
                </span>
              </>
            ) : (
              <>
                <CircleAlert className="w-4 h-4" style={{ color: 'var(--severity-high)' }} />
                <span style={{ color: 'var(--text-secondary)' }}>
                  <code>mcp</code> package not installed.
                </span>
                <CopyButton text="pip install 'pbiscan[mcp]'" />
              </>
            )}
          </div>
        ) : (
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Loading...</span>
        )}
      </div>

      {/* Tool safety matrix */}
      <div className="p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>Tool Safety Matrix</h3>
          {tools && !tools.live && (
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{tools.message}</span>
          )}
        </div>
        <div className="space-y-1.5">
          {tools?.tools.map((t) => (
            <div
              key={t.name}
              className="flex items-center justify-between px-3 py-2 rounded border text-xs"
              style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-hairline)' }}
            >
              <div className="flex items-center gap-2">
                {t.destructive ? (
                  <ShieldAlert className="w-3.5 h-3.5" style={{ color: 'var(--severity-high)' }} />
                ) : (
                  <ShieldCheck className="w-3.5 h-3.5" style={{ color: 'var(--accent)' }} />
                )}
                <span className="font-bold" style={{ color: 'var(--text-primary)' }}>{t.name}</span>
              </div>
              <span
                className="text-[10px] px-2 py-0.5 rounded border font-bold"
                style={{
                  borderColor: t.destructive ? 'var(--severity-high)' : 'var(--border-hairline)',
                  color: t.destructive ? 'var(--severity-high)' : 'var(--accent)',
                }}
              >
                {t.destructive ? 'DESTRUCTIVE — host confirms first' : 'READ-ONLY'}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Rule catalog explorer */}
      <div className="p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}>
        <div className="flex items-center gap-2 mb-3">
          <BookOpen className="w-4 h-4" style={{ color: 'var(--accent)' }} />
          <h3 className="text-sm font-bold" style={{ color: 'var(--text-primary)' }}>
            Rule Catalog Resource (<code>pbiscan://rules</code>)
          </h3>
        </div>
        <div className="space-y-1 max-h-96 overflow-y-auto">
          {rules &&
            Object.values(rules).map((r) => (
              <details key={r.rule_id} className="px-3 py-2 rounded border text-xs" style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-hairline)' }}>
                <summary className="font-bold cursor-pointer" style={{ color: 'var(--text-primary)' }}>
                  {r.rule_id} <span className="font-normal" style={{ color: 'var(--text-muted)' }}>({r.category})</span>
                </summary>
                <div className="mt-2 space-y-1" style={{ color: 'var(--text-secondary)' }}>
                  <div><strong>Issue:</strong> {r.issue}</div>
                  <div><strong>Impact:</strong> {r.impact}</div>
                  <div><strong>Recommendation:</strong> {r.recommendation}</div>
                </div>
              </details>
            ))}
        </div>
      </div>
    </div>
  );
};
