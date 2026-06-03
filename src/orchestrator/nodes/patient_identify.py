import json
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool

from src.orchestrator.call_state import CallState
from src.orchestrator.prompts import build_system_content
from src.orchestrator.routing import apply_lookup_routing
from src.orchestrator.tools.lookup_patient import lookup_patient

_NEW_PATIENT_HINTS = (
    "new patient",
    "i'm new",
    "im new",
    "first time",
    "never been",
    "new here",
)
_RETURNING_HINTS = (
    "returning",
    "been here before",
    "existing patient",
    "i've been",
    "ive been",
)


def infer_patient_type(text: str) -> str | None:
    normalized = (text or "").lower()
    if any(hint in normalized for hint in _NEW_PATIENT_HINTS):
        return "new"
    if any(hint in normalized for hint in _RETURNING_HINTS):
        return "returning"
    return None


def _make_lookup_tool(
    lookup_client: Any | None,
    on_lookup: Callable[[dict[str, Any], dict[str, Any]], None] | None = None,
) -> StructuredTool:
    def _run(
        first_name: str = "",
        last_name: str = "",
        dob: str = "",
        phone: str = "",
        full_name: str = "",
    ) -> str:
        result = lookup_patient(
            first_name=first_name,
            last_name=last_name,
            dob=dob,
            phone=phone,
            full_name=full_name,
            client=lookup_client,
        )
        if on_lookup is not None:
            on_lookup(
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "dob": dob,
                    "phone": phone,
                    "full_name": full_name,
                },
                result,
            )
        return json.dumps(result)

    return StructuredTool.from_function(
        func=_run,
        name="lookup_patient",
        description=(
            "Look up a patient by first name, last name, date of birth, and phone. "
            "Call only when all identity fields are collected."
        ),
    )


def make_patient_identify_node(
    llm: Any,
    lookup_client: Any | None = None,
) -> Callable[[CallState], CallState]:
    pending_identity: dict[str, Any] = {}
    pending_lookup: dict[str, Any] | None = None

    def _capture_identity(fields: dict[str, Any], result: dict[str, Any]) -> None:
        pending_identity.clear()
        pending_identity.update(fields)
        nonlocal pending_lookup
        pending_lookup = result

    tool = _make_lookup_tool(lookup_client, on_lookup=_capture_identity)
    bound_llm = llm.bind_tools([tool])

    def patient_identify(state: CallState) -> CallState:
        nonlocal pending_lookup
        pending_lookup = None
        pending_identity.clear()

        user_text = state.get("user_text") or ""
        inferred = infer_patient_type(user_text)
        if inferred and not state.get("patient_type"):
            state["patient_type"] = inferred

        messages = list(state.get("messages") or [])
        if user_text:
            messages.append(HumanMessage(content=user_text))
            state["utterance_count"] = int(state.get("utterance_count", 0)) + 1

        from langchain_core.messages import SystemMessage

        system_content = build_system_content("PATIENT_IDENTIFY")
        llm_messages: list[Any] = [SystemMessage(content=system_content)]
        for msg in messages:
            if isinstance(msg, SystemMessage):
                continue
            llm_messages.append(msg)

        response = bound_llm.invoke(llm_messages)
        messages.append(response)

        if getattr(response, "tool_calls", None):
            for call in response.tool_calls:
                if call.get("name") != "lookup_patient":
                    continue
                args = call.get("args") or {}
                result = lookup_patient(
                    first_name=args.get("first_name", ""),
                    last_name=args.get("last_name", ""),
                    dob=args.get("dob", ""),
                    phone=args.get("phone", ""),
                    full_name=args.get("full_name", ""),
                    client=lookup_client,
                )
                pending_identity.update(args)
                pending_lookup = result
                messages.append(
                    ToolMessage(
                        content=json.dumps(result),
                        tool_call_id=call["id"],
                    )
                )
                follow_up = bound_llm.invoke(
                    [SystemMessage(content=system_content)]
                    + [m for m in messages if not isinstance(m, SystemMessage)]
                )
                messages.append(follow_up)
                response = follow_up

        if pending_identity:
            identity = dict(state.get("identity_fields") or {})
            identity.update({k: v for k, v in pending_identity.items() if v})
            state["identity_fields"] = identity

        if pending_lookup is not None:
            state = apply_lookup_routing(state, pending_lookup)
            if state.get("active_node") != "PATIENT_IDENTIFY":
                system_content = build_system_content(state["active_node"])
                messages[0] = SystemMessage(content=system_content)

        content = ""
        if isinstance(response, AIMessage):
            content = (response.content or "").strip()
            if isinstance(content, list):
                content = " ".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                ).strip()
        state["last_reply"] = content
        state["messages"] = messages
        return state

    return patient_identify
