# Git Guardian

Guard against destructive git mistakes. Use before any command that rewrites history or deletes work.

## Never run without explicit confirmation

- `git push --force` on a shared branch. Use `--force-with-lease` at minimum.
- `git reset --hard` with uncommitted changes — commit or stash first, always.
- `git clean -fd` — deleted untracked files are gone, no reflog entry.
- `git rebase -i` on anything already pushed.
- `git checkout -- .` / `git restore .` — silently discards all local changes.

## Safe habits

- Branch before you experiment: `git switch -c wip/thing`.
- Commit early, squash later. A messy history beats a lost afternoon.
- Before force-pushing: `git log --oneline origin/main..HEAD` to see exactly what you'd rewrite.
- `git stash push -u` beats hoping untracked files survive.
- Recover a "lost" commit with `git reflog` — it's almost never lost until gc.

## Recovery kit

- Undid a commit? `git reset --soft HEAD~1` keeps your changes staged.
- Wrong branch? `git switch -c rescue && git switch - && git reset --hard HEAD~1`.
- Deleted a file? Check `git reflog` and `git fsck --lost-found` before rewriting it.
