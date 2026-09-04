"""Runnable reproduction: a missing approval decision executes a requires_approval tool.

Offline. No API key and no network. Uses pydantic-ai's own FunctionModel, so the model
never leaves the process. Run it against the released package:

    pip install pydantic-ai-slim && python demo_pydantic_ai.py

Exit code 1 means the defect reproduced, 0 means it did not on this version, and 2 means
the controls did not behave so the reading has no range and must not be counted either way.
"""

import sys

from pydantic_ai import Agent
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults

EXECUTED: list[str] = []


def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    for m in messages:
        for p in m.parts:
            if isinstance(p, ToolCallPart):
                return ModelResponse(parts=[TextPart("finished")])
    return ModelResponse(parts=[ToolCallPart(tool_name="delete_everything", args={})])


agent = Agent(FunctionModel(model_fn), output_type=[str, DeferredToolRequests])


@agent.tool_plain(requires_approval=True)
def delete_everything() -> str:
    # The evidence is that this line ran, not what the run returned. A caller who trusts
    # the gate is protecting a real write, and a return value can be discarded while a
    # write cannot.
    EXECUTED.append("delete_everything")
    return "deleted"


def trial(label: str, approval: object) -> object:
    EXECUTED.clear()
    first = agent.run_sync("proceed")
    requests = first.output
    if not isinstance(requests, DeferredToolRequests) or not requests.approvals:
        raise SystemExit(f"harness broken: no approval was requested for {label}")
    call_id = requests.approvals[0].tool_call_id
    try:
        agent.run_sync(
            message_history=first.all_messages(),
            deferred_tool_results=DeferredToolResults(approvals={call_id: approval}),
        )
        ran: object = bool(EXECUTED)
    except Exception as exc:
        ran = f"raised {type(exc).__name__}"
    print(f"  approvals={{id: {label:<16}}}  tool ran: {ran}")
    return ran


def main() -> int:
    import pydantic_ai

    print(f"pydantic_ai {pydantic_ai.__version__}\n")

    print("controls -- these fix the range of the reading below")
    approved = trial("True", True)
    denied = trial("False", False)

    if approved is not True or denied is not False:
        print("\nUNTESTABLE: the controls did not behave, so the trial below means nothing.")
        return 2

    print("\ntrial")
    unanswered = trial("None", None)

    print("\ndiscrimination -- is None special, or does any stray value execute?")
    for label, value in (('"" empty str', ""), ("[] empty list", []),
                         ("0 int", 0), ('"no" truthy str', "no")):
        trial(label, value)

    print()
    if unanswered is not True:
        print("Not reproduced on this version.")
        return 0

    print("DEFECT REPRODUCED: an unanswered approval executed the tool.")
    print("  approvals is typed dict[str, bool | DeferredToolApprovalResult], so None is a")
    print("  type violation. Nothing checks it at runtime and the violation resolves to approve.")
    print("  _deferred.py to_tool_call_results maps `is True` and `is False` and passes")
    print("  everything else through untouched, so None survives as None.")
    print("  _tool_execution.py _call_tool then reads `tool_call_result is None` as")
    print("  'this call has no deferred result' and executes. None carries both meanings")
    print("  and the execute branch takes both. Other stray values take a different branch,")
    print("  which is why the collision is specific to None rather than to non-bools.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
