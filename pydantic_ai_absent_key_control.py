"""Does an approval that was never submitted at all run the tool?

The published demo supplies None as a value. This asks a different question: the
tool call id is simply not a key in the map, which is what a host produces when a
reviewer decides one of two parallel calls and resumes.
"""
from pydantic_ai.tools import DeferredToolRequests, DeferredToolResults
import demo_pydantic_ai as d


def run(label, build):
    d.EXECUTED.clear()
    first = d.agent.run_sync("proceed")
    reqs = first.output
    assert isinstance(reqs, DeferredToolRequests) and reqs.approvals
    call_id = reqs.approvals[0].tool_call_id
    try:
        r = d.agent.run_sync(
            message_history=first.all_messages(),
            deferred_tool_results=build(call_id),
        )
        out = type(r.output).__name__
    except Exception as exc:
        out = f"raised {type(exc).__name__}"
    print(f"  {label:<44} tool ran: {str(bool(d.EXECUTED)):<5}  output: {out}")


print("control -- an explicit deny must still block")
run("approvals={id: False}", lambda i: DeferredToolResults(approvals={i: False}))
print("control -- an explicit approve must still run")
run("approvals={id: True}", lambda i: DeferredToolResults(approvals={i: True}))
print()
print("trial -- the decision was never submitted")
run("approvals={}  (empty map)", lambda i: DeferredToolResults(approvals={}))
run("approvals={other_id: True}  (partial)", lambda i: DeferredToolResults(approvals={"other_call": True}))
