// Builds the text a user pastes into an AI client to connect the pbiscan MCP server.
// Pure functions, so the exact strings are unit tested.

export type McpClient = 'claude-desktop' | 'claude-code' | 'cursor';

export interface Launch { command: string; args: string[] }

/** `python -m pbiscan mcp` works even when the `pbiscan` script is not on the client's PATH. */
export const DEFAULT_LAUNCH: Launch = { command: 'python', args: ['-m', 'pbiscan', 'mcp'] };

/** With the local engine connected we know the exact Python that runs pbiscan, which is the most reliable command. */
export function launchFromStatus(status?: { python_executable?: string } | null): Launch {
  const exe = status?.python_executable?.trim();
  return exe ? { command: exe, args: ['-m', 'pbiscan', 'mcp'] } : DEFAULT_LAUNCH;
}

/** The JSON every client reads. JSON.stringify doubles Windows backslashes, which JSON requires. */
export function configJson(launch: Launch): string {
  const args = `[${launch.args.map((a) => JSON.stringify(a)).join(', ')}]`;
  return [
    '{',
    '  "mcpServers": {',
    '    "pbiscan": {',
    `      "command": ${JSON.stringify(launch.command)},`,
    `      "args": ${args}`,
    '    }',
    '  }',
    '}',
  ].join('\n');
}

const quote = (s: string) => (/\s/.test(s) ? `"${s}"` : s);

/** `claude mcp add` for the Claude Code command line. */
export function cliAddCommand(launch: Launch): string {
  return `claude mcp add pbiscan -- ${[launch.command, ...launch.args].map(quote).join(' ')}`;
}

export const CONFIG_FILE: Record<McpClient, { label: string; where: string[] }> = {
  'claude-desktop': {
    label: 'Claude Desktop',
    where: ['Windows: %APPDATA%\\Claude\\claude_desktop_config.json', 'macOS: ~/Library/Application Support/Claude/claude_desktop_config.json'],
  },
  'claude-code': {
    label: 'Claude Code',
    where: ['.mcp.json in the project folder you open in Claude Code'],
  },
  cursor: {
    label: 'Cursor',
    where: ['.cursor/mcp.json in the project, or ~/.cursor/mcp.json for every project'],
  },
};
