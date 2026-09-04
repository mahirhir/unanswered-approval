"""Runnable reproduction: a needs_approval predicate that returns None runs the tool.

Offline. No API key and no network. The model here implements the library's own public
Model interface rather than patching anything inside the library, because a demo that
monkeypatches the library proves nothing about the library.

    pip install openai-agents && python demo_openai_agents.py

Exit code 1 means the defect reproduced, 0 means it did not on this version, and 2 means
the controls did not behave so the trial has no established range and must not be counted.
"""

import asyncio
import sys
from collections.abc import AsyncIterator
from typing import Any

from agents import Agent, Runner, function_tool, set_tracing_disabled
from agents.items import ModelResponse
from agents.models.interface import Model
from agents.usage import Usage
from openai.types.responses import ResponseFunctionToolCall

set_tracing_disabled(True)

EXECUTED: list[str] = []
DECISION: list[Any] = [False]


class StubModel(Model):
    """One tool call on the first turn, then nothing, so a run always terminates."""

    async def get_response(self, system_instructions, input, model_settings, tools,
                           output_schema, handoffs, tracing, *, previous_response_id=None,
                           conversation_id=None, prompt=None, **kwargs) -> ModelResponse:
        asked = isinstance(input, list) and any(
            (i.get("type") if isinstance(i, dict) else getattr(i, "type", None)) == "function_call"
            for i in input
        )
        out = [] if asked else [
            ResponseFunctionToolCall(
                type="function_call", name="delete_everything", arguments="{}",
                call_id="call_1", id="fc_1",
            )
        ]
        return ModelResponse(output=out, usage=Usage(), response_id=None)

    def stream_response(self, *a, **k) -> AsyncIterator[Any]:
        raise NotImplementedError("this demo never streams")


def predicate(*_args: Any) -> Any:
    # A real predicate falls off the end of an if-chain and returns None. That is the
    # whole defect: the missing branch is not a syntax error and not a runtime type
    # error, so nothing anywhere reports it.
    return DECISION[0]


@function_tool(needs_approval=predicate)
def delete_everything() -> str:
    # The evidence is that this line ran, not what the run returned. An approval gate
    # protects a real write, and a return value can be discarded while a write cannot.
    EXECUTED.append("delete_everything")
    return "deleted"


async def trial(label: str, decision: Any) -> object:
    EXECUTED.clear()
    DECISION[0] = decision
    agent = Agent(name="demo", tools=[delete_everything], model=StubModel())
    try:
        result = await Runner.run(agent, "proceed", max_turns=4)
        held = bool(getattr(result, "interruptions", []))
        ran = bool(EXECUTED)
    except Exception as exc:
        print(f"  needs_approval -> {label:<20}  raised {type(exc).__name__}")
        return "raised"
    print(f"  needs_approval -> {label:<20}  held: {str(held):<5}  tool ran: {ran}")
    return ran


async def main() -> int:
    from importlib.metadata import version

    print(f"openai-agents {version('openai-agents')}")
    print()

    print("controls -- these fix the range of the reading below")
    held = await trial("True", True)
    ran = await trial("False", False)

    if held is not False or ran is not True:
        print()
        print("UNTESTABLE: the controls did not behave, so the trial below means nothing.")
        return 2

    print()
    print("trial")
    unanswered = await trial("None", None)

    print()
    print("discrimination -- which accidental values fail open?")
    for label, value in (("'' (empty str)", ""), ("[] (empty list)", []),
                         ("0 (int)", 0), ("'no' (truthy str)", "no")):
        await trial(label, value)

    print()
    if unanswered is not True:
        print("Not reproduced on this version.")
        return 0

    print("DEFECT REPRODUCED: an unhandled predicate branch ran the guarded tool.")
    print("  agents/util/_approvals.py, evaluate_needs_approval_setting, ends with")
    print("  `return bool(maybe_result)`. bool(None) is False, and False on this setting")
    print("  means 'no approval needed', so the missing answer becomes a decision to run.")
    print("  bool() also decides the direction for every other accidental value: falsy")
    print("  ones fail open, truthy ones fail closed. The dangerous set is every falsy")
    print("  value a predicate can return by accident, not None alone.")
    print("  agents/mcp/server.py, _get_needs_approval_for_tool, has the same shape and")
    print("  is not exercised here because it needs a live MCP server.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
