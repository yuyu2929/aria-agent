# Explain Codebase

Explain an unfamiliar codebase to a newcomer. Use when onboarding, reviewing, or writing architecture docs.

## Approach

1. Start from the entry point (main, CLI, server bootstrap), not the file tree.
2. Follow one real request end-to-end before generalizing.
3. Name the boundaries: what talks to the outside world, what stores state, what is pure logic.
4. Draw the dependency direction. If it points everywhere, say so — that's the finding.

## What to report

- The one-paragraph "what this system is for".
- The three files that matter most, and why.
- The data flow: where data enters, where it is transformed, where it rests.
- The sharp edges: global state, hidden coupling, things that break silently.
- What you could NOT determine from reading — be explicit about gaps.

## Style

- Newcomer vocabulary. Define jargon on first use or don't use it.
- Every claim points at a file and line. Opinions are labeled as opinions.
- End with "read these three files in this order" — a concrete next action.
