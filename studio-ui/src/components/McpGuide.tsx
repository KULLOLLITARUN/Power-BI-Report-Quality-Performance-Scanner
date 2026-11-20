import React, { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { CONFIG_FILE, cliAddCommand, configJson, type Launch, type McpClient } from '../lib/mcpConfig';
import { copyText, useToast } from './ui';

const CodeBlock: React.FC<{ text: string; label?: string }> = ({ text, label }) => {
  const toast = useToast();
  const [done, setDone] = useState(false);
  const copy = async () => {
    const ok = await copyText(text);
    toast(ok ? 'Copied.' : 'Copying is blocked here. Select the text instead.', ok ? 'info' : 'error');
    if (ok) { setDone(true); setTimeout(() => setDone(false), 1600); }
  };
  return (
    <div className="codecopy">
      {label && <div className="muted small">{label}</div>}
      <div className="codecopy-box">
        <pre className="code wrap">{text}</pre>
        <button className="btn btn-sm" onClick={copy} aria-label="Copy to clipboard">{done ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}{done ? 'Copied' : 'Copy'}</button>
      </div>
    </div>
  );
};

const Step: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
  <li className="gstep">
    <div className="gstep-body"><h3>{title}</h3>{children}</div>
  </li>
);

const PROMPTS = [
  'Use pbiscan to scan "C:\\path\\to\\your\\project" and summarise the findings.',
  'Show the lineage of the measure Total Value in that project.',
  'Plan fixes for that project. Do not apply anything.',
];

/** A step-by-step playbook for connecting the pbiscan MCP server to Claude and other MCP clients. */
export const McpGuide: React.FC<{ launch: Launch; exact: boolean }> = ({ launch, exact }) => {
  const [client, setClient] = useState<McpClient>('claude-desktop');
  const json = configJson(launch);
  const where = CONFIG_FILE[client].where;

  return (
    <section className="panel guide" aria-label="Connect pbiscan to Claude">
      <div className="panel-head">
        <h2>Connect pbiscan to Claude, step by step</h2><span className="grow" />
        <div className="seg" role="group" aria-label="Which app">
          {(Object.keys(CONFIG_FILE) as McpClient[]).map((c) => (
            <button key={c} aria-pressed={client === c} onClick={() => setClient(c)}>{CONFIG_FILE[c].label}</button>
          ))}
        </div>
      </div>
      <div className="panel-body">
        <p className="muted" style={{ margin: 0 }}>
          After this, you can ask Claude to scan a Power BI project, explain a measure's dependencies, and plan or apply fixes. The server runs on your computer and your files are not uploaded.
        </p>

        <ol className="gsteps">
          <Step title="Install pbiscan with MCP support">
            <p>You need Python 3.10 or newer. In a terminal (PowerShell on Windows):</p>
            <CodeBlock text={'pip install "pbiscan[mcp]"'} />
            <p>Check it worked. This should print <span className="mono">ok</span>:</p>
            <CodeBlock text={'python -c "import mcp, pbiscan; print(\'ok\')"'} />
          </Step>

          <Step title="Make a practice copy of a project">
            <p>Two of the tools change files: <span className="mono">apply_remediation</span> edits your model and <span className="mono">add_suppression</span> writes a suppressions file. Pbiscan backs up every file before it edits, but practise on a copy first.</p>
            <CodeBlock text={'Copy-Item -Recurse "C:\\path\\to\\your\\project" "C:\\path\\to\\practice-copy"'} label="PowerShell" />
          </Step>

          {client === 'claude-desktop' && (
            <>
              <Step title="Open Claude Desktop's config file">
                <p>In Claude Desktop, open <b>Settings → Developer → Edit Config</b>. That opens the folder with <span className="mono">claude_desktop_config.json</span>. Open it in any text editor. The file is here:</p>
                <ul>{where.map((w) => <li key={w} className="mono small">{w}</li>)}</ul>
              </Step>
              <Step title="Add pbiscan">
                <p>Paste this into the file. If the file already has an <span className="mono">"mcpServers"</span> section, add only the <span className="mono">"pbiscan"</span> part inside it. Do not create a second <span className="mono">"mcpServers"</span>.</p>
                <CodeBlock text={json} />
                <p className="muted small">{exact ? 'The command is the exact Python that is running Studio right now.' : 'If "python" is not found, use the full path to the Python where you installed pbiscan. In PowerShell, run Get-Command python to see it. Double every backslash in a Windows path.'}</p>
              </Step>
              <Step title="Restart Claude Desktop completely">
                <p>Closing the window is not enough. Quit it from the system tray icon (Windows) or <b>Claude → Quit</b> (macOS), then open it again.</p>
              </Step>
              <Step title="Check that it connected">
                <p>Open a new chat. Click the tools icon under the message box. You should see <b>pbiscan</b> with 8 tools. If it is missing, go to Troubleshooting below.</p>
              </Step>
            </>
          )}

          {client === 'claude-code' && (
            <>
              <Step title="Add pbiscan: command line">
                <p>If you use Claude Code in a terminal, run this once:</p>
                <CodeBlock text={cliAddCommand(launch)} />
                <CodeBlock text="claude mcp list" label="Then check it. pbiscan should show as connected:" />
              </Step>
              <Step title="Or: Claude Code in VS Code (no terminal command needed)">
                <p>Create a file named <span className="mono">.mcp.json</span> in the project folder you open in VS Code, with this content:</p>
                <CodeBlock text={json} />
                <p>Then press <b>Ctrl+Shift+P</b>, run <b>Developer: Reload Window</b>, and start a new Claude Code chat. If it asks you to enable the <b>pbiscan</b> project server, choose yes. Type <span className="mono">/mcp</span> to confirm it shows as connected.</p>
                <p className="muted small">Do not commit <span className="mono">.mcp.json</span> unless your team wants everyone to share it.</p>
              </Step>
            </>
          )}

          {client === 'cursor' && (
            <>
              <Step title="Add pbiscan to Cursor">
                <p>Create or open one of these files:</p>
                <ul>{where.map((w) => <li key={w} className="mono small">{w}</li>)}</ul>
                <p>Paste this in, adding only the <span className="mono">"pbiscan"</span> part if the file already has an <span className="mono">"mcpServers"</span> section:</p>
                <CodeBlock text={json} />
              </Step>
              <Step title="Turn it on">
                <p>Open <b>Customize</b> in Cursor's sidebar. <b>pbiscan</b> should be listed. Use its toggle to switch it on, then use it from Cursor's chat in agent mode. Menu names change between Cursor versions, so look for the page that lists your MCP servers. If pbiscan is not listed, restart Cursor. If it fails to start, open the Output panel (<b>Ctrl+Shift+U</b>) and choose <b>MCP Logs</b> to see why.</p>
              </Step>
            </>
          )}

          <Step title="Try it">
            <p>Start a new chat and paste these one at a time. Use your practice copy's path.</p>
            {PROMPTS.map((p) => <CodeBlock key={p} text={p} />)}
            <p>A good first result is a score and a list of findings that match what Studio shows for the same project. The last prompt only plans, so nothing is written.</p>
          </Step>

          <Step title="Let it change files, carefully">
            <p>When you are happy, ask: <span className="mono">Apply the planned fixes to the practice copy.</span> The apply and suppress tools change files, so Claude should ask before running them. Whether it asks depends on that app's permission settings. Choose "allow once", not "always allow", while you are testing. Afterwards, open the practice copy in Studio: the new score is on Overview and the entry is under Fixes → History.</p>
          </Step>
        </ol>

        <div className="gtrouble">
          <h3>Troubleshooting</h3>
          <dl className="kv" style={{ gridTemplateColumns: '1fr' }}>
            <dt>pbiscan does not appear, or shows an error</dt>
            <dd>Run the command by hand: <span className="mono">{[launch.command, ...launch.args].join(' ')}</span>. It should sit and wait without printing anything. Press Ctrl+C to stop it. If you see an error, that is the cause.</dd>
            <dt>"No module named mcp"</dt>
            <dd>Run <span className="mono">pip install "pbiscan[mcp]"</span> again, using the same Python as in the config.</dd>
            <dt>"No module named pbiscan", or "python not found"</dt>
            <dd>The app is starting a different Python than the one you installed pbiscan into. Put the full path of the right Python in <span className="mono">"command"</span>. In PowerShell, <span className="mono">Get-Command python</span> shows it.</dd>
            <dt>The config file will not load</dt>
            <dd>Check for a missing comma or a trailing comma, a second <span className="mono">"mcpServers"</span> block, or a single backslash in a Windows path. Paths need doubled backslashes: <span className="mono">C:\\Users\\you</span>.</dd>
            <dt>Nothing changed after editing the config</dt>
            <dd>Quit the app completely and reopen it. Claude Desktop only reads the file at start-up.</dd>
            <dt>Claude says the project path does not exist</dt>
            <dd>Give the full path to the project folder or the <span className="mono">.pbip</span> file, in quotes. Paths with spaces or an & sign must be quoted.</dd>
          </dl>
        </div>

        <p className="muted small" style={{ margin: 0 }}>
          Privacy: scanning, planning and applying all run on your computer. The only tool that can send anything out is <span className="mono">suggest_dax_rewrite</span>, and only if you have set your own <span className="mono">GROQ_API_KEY</span>. Without it, nothing is sent.
        </p>
      </div>
    </section>
  );
};
