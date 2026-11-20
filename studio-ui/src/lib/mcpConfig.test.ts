import { describe, expect, it } from 'vitest';
import { DEFAULT_LAUNCH, cliAddCommand, configJson, launchFromStatus } from './mcpConfig';

describe('launchFromStatus', () => {
  it('falls back to python -m pbiscan when the engine is not connected', () => {
    expect(launchFromStatus(null)).toEqual(DEFAULT_LAUNCH);
    expect(launchFromStatus({ python_executable: '  ' })).toEqual(DEFAULT_LAUNCH);
  });

  it('uses the exact Python the engine runs on', () => {
    expect(launchFromStatus({ python_executable: 'C:\\Users\\me\\python 3.11\\python.exe' })).toEqual({
      command: 'C:\\Users\\me\\python 3.11\\python.exe', args: ['-m', 'pbiscan', 'mcp'],
    });
  });
});

describe('configJson', () => {
  it('produces valid JSON with the server under mcpServers.pbiscan', () => {
    const parsed = JSON.parse(configJson(DEFAULT_LAUNCH));
    expect(parsed).toEqual({ mcpServers: { pbiscan: { command: 'python', args: ['-m', 'pbiscan', 'mcp'] } } });
  });

  it('keeps Windows backslashes valid by doubling them', () => {
    const text = configJson({ command: 'C:\\Python311\\python.exe', args: ['-m', 'pbiscan', 'mcp'] });
    expect(text).toContain('C:\\\\Python311\\\\python.exe');
    expect(JSON.parse(text).mcpServers.pbiscan.command).toBe('C:\\Python311\\python.exe');
  });
});

describe('cliAddCommand', () => {
  it('builds the claude mcp add command', () => {
    expect(cliAddCommand(DEFAULT_LAUNCH)).toBe('claude mcp add pbiscan -- python -m pbiscan mcp');
  });

  it('quotes a command path that has spaces', () => {
    expect(cliAddCommand({ command: 'C:\\Users\\me\\python 3.11\\python.exe', args: ['-m', 'pbiscan', 'mcp'] }))
      .toBe('claude mcp add pbiscan -- "C:\\Users\\me\\python 3.11\\python.exe" -m pbiscan mcp');
  });
});
