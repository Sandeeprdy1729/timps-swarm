import { spawn, execSync } from 'child_process';
import { test } from 'node:test';
import assert from 'node:assert';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

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
