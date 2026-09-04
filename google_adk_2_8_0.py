"""Runnable reproduction: a require_confirmation predicate that returns None runs the tool.

Offline. No API key, no network, no model call. It drives the library's own FunctionTool
through its public run_async, which is the same path the runner takes, rather than
patching anything inside google.adk. A demo that monkeypatches the library proves
nothing about the library.

    pip install google-adk && python demo_adk.py

Exit code 1 means the defect reproduced, 0 means it did not on this version, and 2 means
the controls did not behave so the trial has no established range and must not be counted.
"""

import asyncio
import sys
from typing import Any

from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext

EXECUTED: list[str] = []
DECISION: list[Any] = [False]


def predicate(**_kwargs: Any) -> Any:
    # A real predicate falls off the end of an if-chain and returns None. The missing
    # branch is not a syntax error and not a runtime type error, so nothing reports it.
    return DECISION[0]


def delete_everything() -> str:
    # The evidence is that this line ran, not what the call returned. A confirmation
    # gate protects a real write, and a return value can be discarded while a write cannot.
    EXECUTED.append("delete_everything")
    return "deleted"


async def make_tool_context() -> ToolContext:
    svc = InMemorySessionService()
    session = await svc.create_session(app_name="demo", user_id="u1")
    ctx = InvocationContext(
        session_service=svc, invocation_id="i1", session=session, agent=None
    )
    return ToolContext(ctx, function_call_id="fc_1")


async def trial(label: str, decision: Any) -> object:
    EXECUTED.clear()
    DECISION[0] = decision
    tool = FunctionTool(func=delete_everything, require_confirmation=predicate)
    tc = await make_tool_context()
    try:
        result = await tool.run_async(args={}, tool_context=tc)
    except Exception as exc:
        print(f"  require_confirmation -> {label:<18}  raised {type(exc).__name__}")
        return "raised"
    held = isinstance(result, dict) and "confirmation" in str(result.get("error", ""))
    ran = bool(EXECUTED)
    print(f"  require_confirmation -> {label:<18}  held: {str(held):<5}  tool ran: {ran}")
    return ran


async def main() -> int:
    from importlib.metadata import version

    print(f"google-adk {version('google-adk')}")
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
    print("discrimination -- which accidental values run the tool?")
    for label, value in (("'' (empty str)", ""), ("[] (empty list)", []),
                         ("0 (int)", 0), ("'no' (truthy str)", "no")):
        await trial(label, value)

    print()
    if unanswered is not True:
        print("Not reproduced on this version.")
        return 0

    print("DEFECT REPRODUCED: an unhandled predicate branch ran the guarded tool.")
    print("  google/adk/tools/function_tool.py, check_require_confirmation, returns")
    print("  cast(bool, await self._invoke_callable(...)). typing.cast performs no")
    print("  runtime check, so the annotation says bool while the value stays None.")
    print("  run_async then tests `if require_confirmation:` and falls through to the")
    print("  invocation. The declared return type is the only thing asserting a bool,")
    print("  and a declared type is not a check.")
    print("  google/adk/tools/mcp_tool/mcp_tool.py has the same cast and is not")
    print("  exercised here because it needs a live MCP server.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
