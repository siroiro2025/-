import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';
import sharp from 'sharp';

const execFileP = promisify(execFile);

// Tagging backends that run without per-token API billing:
//   ollama — local LLM (vision model, e.g. qwen2.5vl / llava)
//   claude — Claude Code CLI, runs inside a Claude subscription
//   codex  — Codex CLI, runs inside a ChatGPT subscription
const BACKEND = process.env.MIRU_TAGGER ?? 'ollama';
const MODEL = process.env.MIRU_TAGGER_MODEL ?? defaultModel(BACKEND);
const OLLAMA_URL = process.env.OLLAMA_URL ?? 'http://localhost:11434';
const TIMEOUT_MS = 120_000;

const PROMPT =
  'You are an image tagger for an image library. Look at the image and output ' +
  'ONLY a JSON array of 3-8 short lowercase English tags describing its subject, ' +
  'style and dominant colors. Example: ["portrait","watercolor","warm tones","woman"]. ' +
  'No prose, no markdown fence — just the JSON array.';

function defaultModel(backend) {
  if (backend === 'claude') return 'haiku';
  if (backend === 'codex') return ''; // codex CLI picks its own default
  return 'qwen2.5vl';
}

export function taggerInfo() {
  return { backend: BACKEND, model: MODEL || '(default)' };
}

// Downscale before sending — vision tokens are priced by pixels.
async function makeSmallCopy(imagePath) {
  const tmp = path.join(os.tmpdir(), `miru-tag-${process.pid}-${path.basename(imagePath)}.jpg`);
  await sharp(imagePath).resize({ width: 768, withoutEnlargement: true }).jpeg({ quality: 80 }).toFile(tmp);
  return tmp;
}

function extractTags(text) {
  const match = text.match(/\[[\s\S]*?\]/);
  if (!match) throw new Error(`no JSON array in tagger output: ${text.slice(0, 200)}`);
  const arr = JSON.parse(match[0]);
  if (!Array.isArray(arr)) throw new Error('tagger output is not an array');
  const tags = arr
    .map((t) => String(t).trim().toLowerCase())
    .filter((t) => t.length > 0 && t.length <= 40);
  return [...new Set(tags)].slice(0, 10);
}

async function tagWithOllama(smallPath) {
  const image = fs.readFileSync(smallPath).toString('base64');
  const res = await fetch(`${OLLAMA_URL}/api/generate`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ model: MODEL, prompt: PROMPT, images: [image], stream: false }),
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!res.ok) throw new Error(`ollama ${res.status}: ${await res.text()}`);
  const data = await res.json();
  return extractTags(data.response ?? '');
}

async function tagWithClaude(smallPath) {
  const args = ['-p', `Read the image at ${smallPath} and then respond. ${PROMPT}`,
    '--model', MODEL, '--allowedTools', 'Read', '--output-format', 'text'];
  const { stdout } = await execFileP('claude', args, { timeout: TIMEOUT_MS });
  return extractTags(stdout);
}

async function tagWithCodex(smallPath) {
  const args = ['exec', '--skip-git-repo-check', '-i', smallPath];
  if (MODEL) args.push('--model', MODEL);
  args.push(PROMPT);
  const { stdout } = await execFileP('codex', args, { timeout: TIMEOUT_MS });
  return extractTags(stdout);
}

export async function autoTag(imagePath) {
  const smallPath = await makeSmallCopy(imagePath);
  try {
    if (BACKEND === 'ollama') return await tagWithOllama(smallPath);
    if (BACKEND === 'claude') return await tagWithClaude(smallPath);
    if (BACKEND === 'codex') return await tagWithCodex(smallPath);
    throw new Error(`unknown MIRU_TAGGER backend: ${BACKEND}`);
  } finally {
    fs.rmSync(smallPath, { force: true });
  }
}
