import React, { useEffect, useState } from 'react';
import { Plug, Terminal, Copy, Check, CircleCheck, CircleAlert, ShieldCheck, ShieldAlert, BookOpen } from 'lucide-react';

interface McpStatus {
  mcp_installed: boolean;
  mcp_version: string | null;
  python_executable: string;
  server_command: string;
  server_args: string[];
  groq_configured?: boolean;
  groq_masked_key?: string | null;
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

interface ConfigSnippetEntry {
  file: string | null;
  snippet: any;
}

interface McpConfigSnippets {
  claude_desktop: ConfigSnippetEntry;
  cursor: ConfigSnippetEntry;
  claude_code_cli: ConfigSnippetEntry;
  vscode_cline_roo: ConfigSnippetEntry;
}

interface RuleEntry {
  rule_id: string;
  category: string;
  title: string;
  issue: string;
  impact: string;
  recommendation: string;
}

interface AgentIntegrationPanelProps {
  hasBackend?: boolean;
}

const HOST_LABELS: Record<keyof McpConfigSnippets, string> = {
  claude_desktop: 'Claude Desktop',
  cursor: 'Cursor',
  claude_code_cli: 'Claude Code (CLI)',
  vscode_cline_roo: 'VS Code (Cline / Roo-Code)',
};

function formatSnippet(entry: ConfigSnippetEntry): string {
  return typeof entry.snippet === 'string' ? entry.snippet : JSON.stringify(entry.snippet, null, 2);
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
  const [snippets, setSnippets] = useState<McpConfigSnippets | null>(null);
  const [rules, setRules] = useState<Record<string, RuleEntry> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [daxInput, setDaxInput] = useState('DIVIDE(SUM(Sales[Amount]), SUM(Sales[Units]))');
  const [daxOutput, setDaxOutput] = useState<any>(null);
  const [daxLoading, setDaxLoading] = useState(false);

  const handleTestGroq = async () => {
    if (!daxInput.trim()) return;
    setDaxLoading(true);
    try {
      const res = await fetch('/api/dax/rewrite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          rule_id: 'DAX_SUSPICIOUS_PATTERN',
          dax_expression: daxInput,
          evidence: 'Division without safe 3rd parameter fallback',
        }),
      });
      const data = await res.json();
      setDaxOutput(data);
    } catch (e: any) {
      setDaxOutput({ error: e.message || 'Failed to call Groq AI' });
    } finally {
      setDaxLoading(false);
    }
  };

  useEffect(() => {
    if (!hasBackend) return;

    (async () => {
      try {
        const [statusRes, toolsRes, snippetsRes, rulesRes] = await Promise.all([
          fetch('/api/mcp/status').then((r) => r.json()),
          fetch('/api/mcp/tools').then((r) => r.json()),
          fetch('/api/mcp/config-snippets').then((r) => r.json()),
          fetch('/api/mcp/rules').then((r) => r.json()),
        ]);
        setStatus(statusRes);
        setTools(toolsRes);
        setSnippets(snippetsRes);
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
            Run <code>pbiscan studio "path/to/your.pbip"</code> locally to see live tool status,
            copyable AI-agent config snippets, and the full rule catalog here.
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
          Connect an AI agent host (Claude Desktop, Cursor, Claude Code) to this deterministic engine over the
          Model Context Protocol. The core scanner remains 100% deterministic and AI-free — the agent only ever
          calls the same tools this panel inspects below.
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
                Groq AI DAX Optimization Engine
              </h3>
              <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                Model: <code>{status?.groq_model || 'openai/gpt-oss-120b'}</code>
              </div>
            </div>
          </div>
          {status?.groq_configured ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-bold" style={{ backgroundColor: 'var(--accent-glow)', color: 'var(--accent)' }}>
              <CircleCheck className="w-3.5 h-3.5" />
              <span>Connected ({status.groq_masked_key})</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px]" style={{ backgroundColor: 'var(--bg-canvas)', color: 'var(--text-muted)' }}>
              <span>Not Configured (.env)</span>
            </div>
          )}
        </div>

        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          Groq AI analyzes flagged DAX formulas on-demand to produce high-performance, non-visual-breaking rewrites.
        </p>

        {/* Live Interactive Test */}
        <div className="p-3 rounded border" style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-hairline)' }}>
          <div className="text-xs font-bold mb-1.5" style={{ color: 'var(--text-primary)' }}>
            Live DAX Rewrite Test:
          </div>
          <div className="flex gap-2 mb-2">
            <input
              type="text"
              value={daxInput}
              onChange={(e) => setDaxInput(e.target.value)}
              placeholder="e.g. DIVIDE(SUM(Sales[Amount]), SUM(Sales[Units]))"
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
              {daxLoading ? 'Rewriting with Groq...' : '⚡ Ask Groq to Rewrite'}
            </button>
          </div>

          {daxOutput && (
            <div
              className="p-3 rounded border text-xs mt-2 space-y-2"
              style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}
            >
              {daxOutput.recommendation && (
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--accent)' }}>
                    Suggested Rewrite:
                  </div>
                  <pre
                    className="p-2 rounded mt-1 overflow-x-auto font-mono text-xs"
                    style={{ backgroundColor: 'var(--bg-canvas)', color: 'var(--text-primary)' }}
                  >
                    {daxOutput.recommendation}
                  </pre>
                </div>
              )}
              {daxOutput.explanation && (
                <div>
                  <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                    Why this is better:
                  </div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                    {daxOutput.explanation}
                  </div>
                </div>
              )}
              {daxOutput.advisory_note && !daxOutput.explanation && (
                <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  {daxOutput.advisory_note}
                </div>
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

      {/* Config snippets */}
      <div className="p-4 rounded-lg border" style={{ backgroundColor: 'var(--bg-surface)', borderColor: 'var(--border-hairline)' }}>
        <h3 className="text-sm font-bold mb-3" style={{ color: 'var(--text-primary)' }}>Client Configuration</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {snippets &&
            (Object.keys(HOST_LABELS) as (keyof McpConfigSnippets)[]).map((key) => {
              const entry = snippets[key];
              const text = formatSnippet(entry);
              return (
                <div
                  key={key}
                  className="p-3 rounded border"
                  style={{ backgroundColor: 'var(--bg-canvas)', borderColor: 'var(--border-hairline)' }}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div>
                      <div className="text-xs font-bold" style={{ color: 'var(--text-primary)' }}>{HOST_LABELS[key]}</div>
                      {entry.file && (
                        <div className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{entry.file}</div>
                      )}
                    </div>
                    <CopyButton text={text} />
                  </div>
                  <pre
                    className="text-[10px] p-2 rounded overflow-x-auto"
                    style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--text-secondary)' }}
                  >
                    {text}
                  </pre>
                </div>
              );
            })}
        </div>
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
