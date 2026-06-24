---
name: github-push
description: Push file changes to GitHub via REST API without 409 SHA conflicts. Use when updating files in a GitHub repo through the GitHub Contents API — especially when multiple files need to be updated or retried. Covers atomic fetch+push pattern, parallel multi-file updates, version bumps, CHANGELOG entries, and creating release tags.
---

# GitHub Push (Conflict-Free)

## When to Use vs Other Skills

| Need | Use |
|---|---|
| Write/update files in FTPLabs/FMailSender | **This skill** |
| Search GitHub for open-source libraries | `github-solution-finder` |
| Read GitHub issues, PRs, or data via Replit OAuth | `query-integration-data` |
| Connect a GitHub account via Replit OAuth | `integrations` |

## The Core Rule

**Never store a SHA and reuse it later.** Always fetch the current SHA inside the same script that does the push. A SHA obtained even one commit ago will cause HTTP 409.

## Project Context

- Repo: `FTPLabs/FMailSender`
- Token: stored as Replit secret `GITHUB_TOKEN` — use `process.env.GITHUB_TOKEN`
- If `GITHUB_TOKEN` is missing, use the `environment-secrets` skill to request it from the user
- Language: Node.js (`node /tmp/script.js`) — no Python available in this environment
- API base: `api.github.com`

## Pattern: Atomic Fetch → Patch → Push

Always one script per file. Never separate GET and PUT calls across different tool invocations.

```js
// /tmp/push_myfile.js
const https = require('https');
const TOKEN = process.env.GITHUB_TOKEN;
if (!TOKEN) { console.error('GITHUB_TOKEN not set'); process.exit(1); }
const REPO  = 'FTPLabs/FMailSender';

function apiGet(path) {
  return new Promise((resolve, reject) => {
    https.get({
      hostname: 'api.github.com', path,
      headers: { Authorization: 'token ' + TOKEN, 'User-Agent': 'fix/1.0' }
    }, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => resolve(JSON.parse(d)));
    }).on('error', reject);
  });
}

function apiPut(path, body) {
  return new Promise((resolve, reject) => {
    const b = JSON.stringify(body);
    const req = https.request({
      hostname: 'api.github.com', path, method: 'PUT',
      headers: {
        Authorization: 'token ' + TOKEN,
        'Content-Type': 'application/json',
        'User-Agent': 'fix/1.0',
        'Content-Length': Buffer.byteLength(b)
      }
    }, res => {
      let d = ''; res.on('data', c => d += c);
      res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(d) }));
    });
    req.on('error', reject); req.write(b); req.end();
  });
}

async function main() {
  // 1. Fetch current file — get fresh SHA + content in one call
  const f = await apiGet(`/repos/${REPO}/contents/path/to/file.py`);
  const currentSha = f.sha;
  const current = Buffer.from(f.content.replace(/\n/g, ''), 'base64').toString('utf8');

  // 2. Check if change already applied (idempotency guard)
  if (current.includes('MARKER_UNIQUE_TO_THIS_CHANGE')) {
    console.log('Already applied — skip'); return;
  }

  // 3. Patch content
  const patched = current.replace('OLD_STRING', 'NEW_STRING');

  // 4. Push using the SHA we just fetched
  const r = await apiPut(`/repos/${REPO}/contents/path/to/file.py`, {
    message: 'fix: describe the change',
    content: Buffer.from(patched).toString('base64'),
    sha: currentSha                          // <-- always from step 1, never cached
  });
  console.log('Push:', r.status, r.body.content?.sha ?? r.body.message);
}
main().catch(e => { console.error(e.message); process.exit(1); });
```

Run with: `node /tmp/push_myfile.js`

## Creating a New File (no existing SHA)

```js
// Omit sha field entirely for new files
const r = await apiPut(`/repos/${REPO}/contents/path/to/newfile.md`, {
  message: 'docs: add new file',
  content: Buffer.from(content).toString('base64'),
  // no sha — GitHub creates the file
});
// Returns 201 on success
```

## Patching by Line Number (when string replace fails)

When the content has Cyrillic or complex quotes, `String.replace` may silently fail. Use line-number splicing instead:

```js
const lines = current.split('\n');

// Find target line from the bottom (avoids off-by-one with earlier inserts)
let idx = -1;
for (let i = lines.length - 1; i >= 0; i--) {
  if (lines[i].includes('UNIQUE_ANCHOR')) { idx = i; break; }
}
if (idx === -1) { console.error('Anchor not found'); process.exit(1); }

// Insert new lines before idx (or replace: splice(idx, 1, ...newLines))
lines.splice(idx, 0, ...newLines);
const patched = lines.join('\n');
```

**Verify after patching** — always check the marker is present before pushing:
```js
console.log('Fix present:', patched.includes('UNIQUE_MARKER'));
// If false, stop — do not push a broken file
```

## Parallel Multi-File Push

Push independent files concurrently. Each gets its own atomic script:

```bash
node /tmp/push_file_a.js &
node /tmp/push_file_b.js &
wait
```

## Version Bump Pattern

```js
const ver = 'APP_VERSION = "4.4.9"\nAPP_NAME = "FMail Sender"\n';
// push to core/_version.py
```

## CHANGELOG Entry Pattern

Prepend new entry to existing content:

```js
const newEntry = `## [4.4.9] — 2026-06-24\n\n  ### Fix\n  - Description\n\n`;
const patched  = newEntry + current;   // prepend, never append
```

## Creating a Release Tag (triggers GitHub Actions build)

```js
function apiPost(path, body) {
  return new Promise((resolve, reject) => {
    const b = JSON.stringify(body);
    const req = https.request({
      hostname: 'api.github.com', path, method: 'POST',
      headers: { Authorization: 'token ' + TOKEN, 'Content-Type': 'application/json', 'User-Agent': 'fix/1.0', 'Content-Length': Buffer.byteLength(b) }
    }, res => { let d = ''; res.on('data', c => d += c); res.on('end', () => resolve({ status: res.statusCode, body: JSON.parse(d) })); });
    req.on('error', reject); req.write(b); req.end();
  });
}

async function createTag(version, message) {
  const branch = await apiGet(`/repos/${REPO}/git/ref/heads/main`);
  const headSha = branch.object.sha;

  // Step 1: create annotated tag object
  const tagObj = await apiPost(`/repos/${REPO}/git/tags`, {
    tag: version, message, object: headSha, type: 'commit'
  });
  if (tagObj.status !== 201) throw new Error('Tag object: ' + tagObj.body.message);

  // Step 2: create the ref
  const ref = await apiPost(`/repos/${REPO}/git/refs`, {
    ref: 'refs/tags/' + version,
    sha: tagObj.body.sha
  });
  console.log('Tag ref:', ref.status, ref.body.ref ?? ref.body.message);
}

// Usage:
await createTag('v4.4.9', 'Release 4.4.9 — description');
```

## Sequence for a Full Release

1. Check `GITHUB_TOKEN` secret is set (use `environment-secrets` skill if not)
2. Write patched content to `/tmp/patch_X.js` for each changed file
3. Run file patches in parallel (`& wait`)
4. Fetch HEAD SHA → create tag
5. GitHub Actions auto-builds EXE (~10-15 min), appears in Releases

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| HTTP 409 "is at SHA_A but expected SHA_B" | Stale SHA | Fetch SHA inside the same script |
| `Fix present: false` after splice | Cyrillic / quote escaping in inline JS | Write script to `/tmp/script.js` with heredoc, run `node /tmp/script.js` |
| Tag ref 422 "already exists" | Tag was already created | Skip or delete old tag first |
| `Buffer.from(...).toString('base64')` truncated | `f.content` has `\n` every 60 chars | Always `.replace(/\n/g, '')` before decoding |
| `process.env.GITHUB_TOKEN` is undefined | Secret not set | Use `environment-secrets` skill to request `GITHUB_TOKEN` |
