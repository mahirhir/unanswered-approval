# unanswered-approval

Runnable reproductions of one defect class in three agent frameworks: **a value that is
neither an explicit yes nor an explicit no reaches the execute path of a human-approval
gate.**

Every script here is offline. No API key, no network, no model call. Each one installs
the framework from PyPI at a pinned version and drives that framework's own public API.
None of them monkeypatch the library, because a demo that patches the library proves
nothing about the library.

## What is measured

| framework | version | `None` | `''` | `[]` | `0` | `'no'` |
|:--|:--|:--|:--|:--|:--|:--|
| `pydantic-ai` | 2.39.0 | **runs** | no | no | no | no |
| `openai-agents` | 0.22.0 | **runs** | **runs** | **runs** | **runs** | no |
| `google-adk` | 2.8.0 | **runs** | **runs** | **runs** | **runs** | no |

"runs" means the guarded tool executed with no approval or confirmation obtained.
Measured 2026-09-04 on Python 3.12.3, Linux.

The three mechanisms are not the same, which is why one lint rule does not find them:

- **`pydantic-ai`** collides with a sentinel. `_call_tool` reads `tool_call_result is None`
  as "this call has no deferred result", which is the ordinary path for a tool that never
  needed approval. A host that supplies `None` is indistinguishable from it. Only `None`
  is affected; other stray values take a different branch.
- **`openai-agents`** coerces. `evaluate_needs_approval_setting` ends with
  `return bool(maybe_result)`, so the *falsiness* of an accidental value decides the
  direction. Every falsy value fails open.
- **`google-adk`** asserts without checking. `check_require_confirmation` returns
  `cast(bool, ...)`, and `typing.cast` does nothing at runtime, so the annotation says
  `bool` while the value stays whatever the predicate returned. Every falsy value fails open.

`''` is the realistic one in the second and third rows. "Return the objection, empty
string when there is none" is an ordinary way to write a policy function, and it silently
means "no approval needed". A truthy non-bool such as `'no'` lands in the safe direction,
which is why this does not surface in casual testing: the mistake that *looks* like a bug
behaves correctly, and the mistake that looks harmless does not.

## How to run one

```
python -m venv .venv && . .venv/bin/activate
pip install pydantic-ai-slim && python pydantic_ai_2_39_0.py
pip install openai-agents   && python openai_agents_0_22_0.py
pip install google-adk      && python google_adk_2_8_0.py
```

## How each script is built, and why

**Controls run before the trial and gate it.** Every script first drives an explicit
approve and an explicit deny. If approve does not run the tool, or deny does not block
it, the script prints `UNTESTABLE` and exits 2 rather than reporting the trial. A reading
with no established range is not evidence, and "could not measure" must not fold into
either a pass or a fail.

**Exit codes are three-valued**: `1` reproduced, `0` not reproduced on this version,
`2` untestable.

**The evidence is a side effect, not a return value.** Each guarded tool appends to a
module-level list. What an approval gate protects is a real write, and a return value can
be discarded while a write cannot.

**Versions are pinned in the filename** so a future reader can tell whether a "not
reproduced" result means the defect was fixed or the script drifted.

## Reports

- `pydantic/pydantic-ai` [#8060](https://github.com/pydantic/pydantic-ai/issues/8060)
- `openai/openai-agents-python` [#4845](https://github.com/openai/openai-agents-python/issues/4845)
- `google/adk-python` [#7010](https://github.com/google/adk-python/issues/7010)

## What this does not claim

These scripts test the axes named above and nothing else. They are not an audit of any of
these projects, and none of the results say anything about the rest of the codebase.

Four other frameworks were read for the same class on the same day and handle the
unanswered case correctly: `agno`, `goose`, `composio`, and the Rust `codex-rs` tree. Four
right to three wrong is the reason this is a judgement at each gate rather than a pattern
a scanner can decide. A search tool can narrow a tree to the sites worth reading; it
cannot tell you which of them is wrong.

Whether this class reaches production or sits behind a setting nobody turns on is not
measured here. Nothing in these scripts answers that.

## Licence

Apache-2.0.
