# GitHub Push — Git Tree API

  ## ALWAYS use Git Tree API for multi-file commits

  Parallel PUT /contents/{path} causes SHA conflicts. Tree API = one atomic commit.

  ## Pattern

  ```javascript
  const h = { "Authorization": `token ${token}`, "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json" };
  // 1. GET HEAD
  const headSha = (await (await fetch(`https://api.github.com/repos/${REPO}/git/refs/heads/main`, {headers:h})).json()).object.sha;
  const baseTree = (await (await fetch(`https://api.github.com/repos/${REPO}/git/commits/${headSha}`, {headers:h})).json()).tree.sha;
  // 2. Create blobs (parallel)
  const items = await Promise.all(files.map(async ({path, content}) => {
    const sha = (await (await fetch(`https://api.github.com/repos/${REPO}/git/blobs`,{method:'POST',headers:h,body:JSON.stringify({content,encoding:'utf-8'})})).json()).sha;
    return {path, mode:'100644', type:'blob', sha};
  }));
  // To DELETE a file: set sha: null in items array
  // 3. Create tree
  const treeSha = (await (await fetch(`https://api.github.com/repos/${REPO}/git/trees`,{method:'POST',headers:h,body:JSON.stringify({base_tree:baseTree,tree:items})})).json()).sha;
  // 4. Commit
  const commitSha = (await (await fetch(`https://api.github.com/repos/${REPO}/git/commits`,{method:'POST',headers:h,body:JSON.stringify({message:'feat:...',tree:treeSha,parents:[headSha]})})).json()).sha;
  // 5. Update branch
  await fetch(`https://api.github.com/repos/${REPO}/git/refs/heads/main`,{method:'PATCH',headers:h,body:JSON.stringify({sha:commitSha})});
  ```
  