# Contributing to Voxhelm Avatar

Thanks for your interest in contributing. This document covers how to get set
up, what we expect from a change, and how review works.

By participating you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).
Security problems go through [SECURITY.md](SECURITY.md), **not** the issue
tracker.

## Getting set up

```bash
python -m venv .venv
.venv/bin/pip install -e ".[all]"
```

See the [README](README.md#environment-variables) for the API keys you will
need. Generation features need credentials for the relevant provider; you can
work on most of the codebase without them, and tests that require a live
provider are skipped when the key is absent.

## Making a change

Work on a feature branch — never directly on `main`. Keep pull requests
focused on one thing.

### Tests

Run the full suite before pushing:

```bash
.venv/bin/pytest tests/ -v --tb=short
```

All tests must pass before you:

- push a branch or open a pull request
- ask anyone to verify behaviour by hand

If a test fails, fix it — do not skip, delete, or comment it out. A failing
test is a bug.

New code needs tests. Bug fixes need a regression test that fails before the
fix and passes after it. Avoid tests that pass without asserting anything
meaningful.

### Things worth knowing

- **Avatar generation is non-deterministic.** Tests that exercise a real model
  should assert on structure and invariants (viseme count, valid SVG, identity
  lock) rather than exact output.
- **There are 15 OVR visemes per character**, and that set is load-bearing —
  the Flutter widget and the viseme cache both assume it. Changing it is a
  breaking change.
- **`star-vector/` is a dead-end spike** and is gitignored. Don't build on it.

## Opening a pull request

PR title follows conventional commits:

```
feat(#12): add viseme interpolation
fix(#34): handle empty audio buffer
docs(#56): document the photo mode workflow
```

The body should say what changed, how to test it, and close the issue with
`Closes #N`.

Update the README and anything in `docs/` that your change makes stale, in the
same PR.

## Licence

By contributing, you agree that your contributions will be licensed under the
[MIT Licence](LICENSE) that covers this project.
