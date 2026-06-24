---
name: github-push
description: Push file changes to GitHub via REST API without 409 SHA conflicts. Use when updating files in a GitHub repo through the GitHub Contents API — especially when multiple files need to be updated or retried. Covers atomic fetch+push pattern, parallel multi-file updates, version bumps, CHANGELOG entries, and creating release tags.
---

# GitHub Push (Conflict-Free)

## The Core Rule

**Never store a SHA and reuse it later.** Always fetch the current SHA inside the same script that does the push. A SHA obtained even one commit ago will cause HTTP 409.

## Project Context

- Repo: `FTPLabs/FMailSender`
- Token secret name: `GITHUB_TOKEN` (check environment secrets; value starts with `ghp_`)
- Language: Node.js (`node /tmp/script.js`) — no Python available in this environment
- API base: `api.github.com`

## Pattern: Atomic Fetch → Patch → Push

Always one script per file. Never separate GET and PUT calls across different tool invocations.

```js
// /tmp/push_myfile.js
const https = require('https');
const TOKEN = process.env.GITHUB_TOKEN || 'ghp_...';
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

Files with shared commit history (e.g. CHANGELOG + version bump) can be sequential or parallel — GitHub accepts concurrent pushes to the same branch; each creates its own commit.

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
function apiPost(path, body) { /* same as apiPut but method: 'POST' */ }

async function createTag(headSha, version, message) {
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

// Get HEAD SHA
const branch = await apiGet(`/repos/${REPO}/git/ref/heads/main`);
await createTag(branch.object.sha, 'v4.4.9', 'Release 4.4.9 — description');
```

## Sequence for a Full Release

1. Write patched content to `/tmp/patch_X.js` for each changed file
2. Run file patches in parallel (`& wait`)
3. Fetch HEAD SHA → create tag
4. GitHub Actions auto-builds EXE (~10-15 min), appears in Releases

## Common Errors

| Error | Cause | Fix |
|---|---|---|
| HTTP 409 "is at SHA_A but expected SHA_B" | Stale SHA | Fetch SHA inside the same script |
| `Fix present: false` after splice | Cyrillic / quote escaping in inline JS | Write script to `/tmp/script.js` with heredoc, run `node /tmp/script.js` |
| Tag ref 422 "already exists" | Tag was already created | Skip or delete old tag first |
| `Buffer.from(...).toString('base64')` truncated | `f.content` has `\n` every 60 chars | Always `.replace(/\n/g, '')` before decoding |
