# PR Message

Write concise, high-signal pull request messages. Use when opening or reviewing a PR.

## Structure

- Title: what changed, under 70 chars, imperative mood. "Fix double-charge on retry", not "Fixes".
- First line of body: why this PR exists (the problem), not what it does (the diff shows that).
- Body: the decision you made and the alternatives you rejected. Reviewers review decisions, not lines.
- Testing: exactly how you verified it — commands run, cases covered.
- Risk: what breaks if this is wrong, and how to roll back.

## Rules

- If the PR needs a diagram to be understood, it should have been two PRs.
- Link the issue. If there is no issue, ask whether there should be.
- Never write "various fixes" or "misc updates". If you can't name it, split it.
- Screenshots for UI changes; before AND after, side by side.
- Keep it under 300 words. Long PRs get shallow reviews.
