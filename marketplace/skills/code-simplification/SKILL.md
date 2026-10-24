# Code Simplification

Simplify and de-complicate code without changing behavior. Use on any "it works but it's ugly" code.

## Method

1. Write down what the code must do (behavior contract) before touching it.
2. Delete before you add. Every line you remove is a line that can't be wrong.
3. Collapse nested conditionals with early returns and guard clauses.
4. Name the "why" in a comment only when the code can't say it.

## Common wins

- Nested `if` pyramids → early return / guard clauses.
- Loops that build one value → `any()`, `all()`, `max()`, or a comprehension.
- Boolean flags threaded through five functions → split the function.
- Defensive `try/except` around code that can't actually fail → delete it.
- Config passed as six positional args → a small dataclass.

## Rules

- No behavior change without a test proving it. If there's no test, write one first.
- One simplification per commit, so a regression bisects to a single change.
- If the "simple" version is longer, you optimized the wrong thing.
