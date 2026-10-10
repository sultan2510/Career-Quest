import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createContext, Script } from 'node:vm';
import test from 'node:test';
import ts from 'typescript';

const root = fileURLToPath(new URL('../', import.meta.url));
const nativeRequire = createRequire(import.meta.url);

// Run the real TypeScript clients with a controlled HTTP boundary; no backend or browser secrets are needed.
function client(fetch, storage = new Map()) {
  const context = createContext({
    fetch, AbortController, DOMException, URL, setTimeout, clearTimeout,
    process: { env: {} },
    window: { localStorage: {
      getItem: key => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: key => storage.delete(key),
    } },
  });
  const cache = new Map();
  const load = filename => {
    const path = resolve(root, filename);
    if (cache.has(path)) return cache.get(path).exports;
    const module = { exports: {} };
    cache.set(path, module);
    const source = ts.transpileModule(readFileSync(path, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2017 },
      fileName: path,
    }).outputText;
    const localRequire = name => {
      if (name.startsWith('@/')) return load(`${name.slice(2)}.ts`);
      if (name.startsWith('.')) return load(resolve(dirname(path), `${name}.ts`));
      return nativeRequire(name);
    };
    new Script(`(function(exports, require, module) { ${source}\n})`, { filename: path })
      .runInContext(context)(module.exports, localRequire, module);
    return module.exports;
  };
  return load;
}

const response = (data, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => data });
const deferred = () => {
  let resolvePromise;
  const promise = new Promise(resolve => { resolvePromise = resolve; });
  return { promise, resolve: resolvePromise };
};

test('mentor sends fresh quest evidence and DNA with first-party session cookies', async () => {
  let request;
  const load = client(async (url, init) => {
    request = { url, ...init, body: JSON.parse(init.body) };
    return response({ status: 'ok', mode: 'generated', answer: 'Try a project.', sources: [] });
  });
  const { emptyProgress } = load('lib/types.ts');
  const progress = emptyProgress();
  progress.character = 2;
  progress.answers = [0, 1, 2];
  progress.tasks = { software: ['week-1'] };
  progress.journal = [{ id: 'latest', at: '2026-10-10', prompt: 'Today', text: 'I enjoyed the design exercise.' }];
  progress.dna.answers = { '1.1': 'A' };
  await load('lib/rag.ts').askYuki('What should I try next?', progress);

  assert.equal(request.url, '/api/rag/ask');
  assert.equal(request.credentials, 'include');
  assert.equal(request.method, 'POST');
  assert.equal(request.headers['Content-Type'], 'application/json');
  assert.deepEqual(request.body.progress, JSON.parse(JSON.stringify(progress)));
  assert.match(request.body.profile, /Top strengths:/);
  assert.equal(request.body.question, 'What should I try next?');
});

test('an unanswered mentor request ends with a useful timeout instead of permanent loading', async () => {
  const load = client((_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  }));
  const { api, ApiError } = load('lib/api.ts');
  await assert.rejects(api('/rag/ask', { timeoutMs: 5 }), error => error instanceof ApiError && error.code === 'timeout');
});

test('canceling a question aborts the HTTP request and preserves cancellation', async () => {
  const load = client((_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true });
  }));
  const controller = new AbortController();
  const pending = load('lib/api.ts').api('/rag/ask', { signal: controller.signal });
  controller.abort();
  await assert.rejects(pending, error => error.name === 'AbortError');
});

test('whole-progress writes finish in order so an older response cannot overwrite the latest snapshot', async () => {
  const older = deferred();
  const olderStarted = deferred();
  const writes = [];
  let serverProgress;
  const load = client(async (_url, init) => {
    const snapshot = JSON.parse(init.body);
    writes.push(snapshot);
    if (snapshot.answers.length === 1) { olderStarted.resolve(); await older.promise; }
    serverProgress = snapshot;
    return response(snapshot);
  });
  const { emptyProgress } = load('lib/types.ts');
  const { saveProgress } = load('lib/storage.ts');
  const queue = load('lib/save-queue.ts').createSaveQueue();
  const first = { ...emptyProgress(), answers: [0] };
  const latest = { ...emptyProgress(), answers: [0, 2] };
  const savingFirst = queue(() => saveProgress('signed-in-user', first));
  await olderStarted.promise;
  const savingLatest = queue(() => saveProgress('signed-in-user', latest));
  await Promise.resolve();
  assert.equal(writes.length, 1, 'the latest snapshot waits for the old write to finish');
  older.resolve();
  await Promise.all([savingFirst, savingLatest]);
  assert.deepEqual(serverProgress.answers, latest.answers);
});

test('a failed save is reported and does not prevent saving later changes', async () => {
  let calls = 0;
  const load = client(async () => ++calls === 1 ? response({ detail: 'Unavailable' }, 503) : response({}));
  const { saveProgress } = load('lib/storage.ts');
  const { emptyProgress } = load('lib/types.ts');
  const queue = load('lib/save-queue.ts').createSaveQueue();
  const first = queue(() => saveProgress('signed-in-user', emptyProgress()));
  const latest = queue(() => saveProgress('signed-in-user', { ...emptyProgress(), answers: [1] }));
  await assert.rejects(first);
  await latest;
  assert.equal(calls, 2);
});

test('superseded snapshots waiting behind an active save are skipped', async () => {
  const held = deferred();
  const started = deferred();
  const load = client(async () => response({}));
  const queue = load('lib/save-queue.ts').createSaveQueue();
  const written = [];
  const first = queue(async () => { started.resolve(); await held.promise; written.push('first'); });
  await started.promise;
  let stillCurrent = true;
  const superseded = queue(async () => { written.push('superseded'); }, () => stillCurrent);
  stillCurrent = false;
  const latest = queue(async () => { written.push('latest'); });
  held.resolve();
  await Promise.all([first, superseded, latest]);
  assert.deepEqual(written, ['first', 'latest']);
});

test('browser storage failures are surfaced for guest progress too', async () => {
  const storage = { get: () => null, set: () => { throw new Error('Storage full'); }, delete: () => {} };
  const load = client(async () => { throw new Error('Guests should not send progress to the server'); }, storage);
  await assert.rejects(load('lib/storage.ts').saveProgress('guest', load('lib/types.ts').emptyProgress()), /could not save/);
});
