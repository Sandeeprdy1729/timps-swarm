import { spawn, execSync } from 'child_process';
import { test } from 'node:test';
import assert from 'node:assert';
import { fileURLToPath } from 'url';
import { dirname, join, resolve } from 'path';
import { mkdtempSync, readFileSync, rmSync } from 'fs';
import { tmpdir } from 'os';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI = resolve(__dirname, '..', 'bin', 'timps-swarm.js');

test('--version prints version', async () => {
  const child = spawn('node', [CLI, '--version'], { stdio: 'pipe' });
  let output = '';
  child.stdout.on('data', (d) => output += d);
  await new Promise((resolve) => child.on('close', resolve));
  assert.ok(output.includes('2.2'));
});

test('--help prints help and exits 0', async () => {
  const child = spawn('node', [CLI, '--help'], { stdio: 'pipe' });
  let output = '';
  child.stdout.on('data', (d) => output += d);
  const { code } = await new Promise((resolve) => {
    child.on('close', (code) => resolve({ code }));
  });
  assert.strictEqual(code, 0);
  assert.ok(output.includes('Usage'));
});

test('unknown command exits non-zero', async () => {
  const child = spawn('node', [CLI, 'nonexistent-command'], { stdio: 'pipe' });
  let output = '';
  child.stderr.on('data', (d) => output += d);
  const { code } = await new Promise((resolve) => {
    child.on('close', (code) => resolve({ code }));
  });
  assert.notStrictEqual(code, 0);
});

test('install-mcp writes repo-aware config without backend setup', async () => {
  const home = mkdtempSync(join(tmpdir(), 'timps-cli-'));
  const repo = join(home, 'backend repo');
  try {
    const child = spawn(
      'node',
      [CLI, 'install-mcp', '--tool', 'claude-code', '--repo', repo, '--no-sub-agents'],
      { cwd: home, env: { ...process.env, HOME: home }, stdio: 'pipe' },
    );
    const { code } = await new Promise((resolve) => {
      child.on('close', (code) => resolve({ code }));
    });
    assert.strictEqual(code, 0);

    const config = JSON.parse(readFileSync(join(home, '.claude', 'mcp.json'), 'utf8'));
    const server = config.mcpServers['timps-swarm'];
    assert.strictEqual(server.command, 'npx');
    assert.deepStrictEqual(server.args, ['timps-swarm', 'mcp', '--repo', repo]);
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
