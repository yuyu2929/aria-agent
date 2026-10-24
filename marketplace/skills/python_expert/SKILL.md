# Python Expert

Expert-level Python practices. Use when writing, reviewing, or refactoring Python code.

## Style

- Prefer explicit over implicit; code is read far more often than it is written.
- Functions do one thing. If you need "and" to describe it, split it.
- Use type hints on public interfaces; skip them inside obvious short helpers.

## Correctness

- Never mutate a default argument. Use None and create inside the function.
- Prefer `pathlib.Path` over string paths; never concatenate paths with "+".
- Open files with `with` blocks or `pathlib` helpers; never leak file handles.
- Catch specific exceptions. A bare `except:` hides bugs and swallows KeyboardInterrupt.

## Performance

- Measure before optimizing. Use `timeit` for micro-benchmarks, `cProfile` for the big picture.
- Prefer generators over materialized lists when streaming large data.
- String building in a loop: collect parts in a list, then `"".join(parts)`.

## Testing

- Test behavior, not implementation. One assertion concept per test.
- Name tests after the scenario: `test_rejects_negative_amount`, not `test_validate`.
- Fixtures over setup/teardown boilerplate; keep test data minimal and local.
