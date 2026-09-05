# unanswered-approval

Runnable reproductions of one defect class in three agent frameworks: **a value that is
neither an explicit yes nor an explicit no reaches the execute path of a human-approval
gate.**

![The measured table and two of the runs behind it: on None the guarded tool executes in all three frameworks, on an empty string it executes in openai-agents and google-adk, and a truthy 'no' is safe in all three](demo.gif)

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
  — **closed as WONTFIX on 2026-09-05**, along with the four pull requests that
  implemented a fix. See the ruling below.
- `google/adk-python` [#7010](https://github.com/google/adk-python/issues/7010)

## What the openai-agents maintainer ruled

On 2026-09-05 an OpenAI maintainer closed #4845 and all four pull requests against it,
unmerged, with this reasoning:

> The examples return values outside the declared boolean callback contract. They
> establish the current truthiness behavior, but do not establish an SDK-owned untyped
> input boundary or a bypass with a supported callback result. Please keep approval
> decisions explicitly boolean in application code.

That position is defensible and I am not arguing with it. `needs_approval` is declared
`bool | Callable[..., bool]`, so a string or a null is the caller breaking the contract,
and whether a typed SDK should validate untyped input at that boundary is a design call
that belongs to its maintainers.

So read the `openai-agents` row as what it is: **a measurement of what the released
version does with an out-of-contract value, not a defect its maintainer accepts.** The
same caution applies to the other two rows until each project rules on its own.

The reopening bar he named is a concrete bypass using a *supported* callback result. I
have not found one. If I do, that is when this comes back.

What does not change is the reason a host hits this at all: approvals arrive from config
files, JSON payloads and database columns, where the type is not enforced by anything.
Whether that is the framework's problem or the application's is exactly the question the
ruling above answers, and it answers it in favour of the application. That makes the
application the thing worth auditing.

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

## Bound on the pydantic-ai row

`pydantic_ai_absent_key_control.py` asks a different question: what happens when the
decision is **never submitted**, so the tool call id is not a key in the map at all. That
is what a host produces when a reviewer decides one of two parallel calls and resumes.

```
trial -- the decision was never submitted
  approvals={}  (empty map)                    tool ran: False  output: raised UserError
  approvals={other_id: True}  (partial)        tool ran: False  output: raised UserError
```

An absent key raises `UserError`. That path fails closed and is handled correctly, so the
defect needs a host to write `None` as a **value**. Omitting the entry is safe; supplying
the null is not.

This bound is here because the row above would otherwise read as "unanswered approvals
execute", which is wider than what was measured.
