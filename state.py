
from typing import Annotated , TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

def merge_dicts( left : dict , right : dict ) -> dict:
    return {**(left or {}), **(right or {})}

def merge_unique(left: list, right: list) -> list:
    """Append new items, keep order, skip duplicates."""
    left = left or []
    return left + [x for x in (right or []) if x not in left]

def add_items(left, right):
    return (left or []) + (right or [])


class AgentState(TypedDict):
    messages : Annotated[list[AnyMessage] , add_messages]
    retrieved : Annotated[dict , merge_dicts] # holds the data like the code itself
    fetched : Annotated[list , merge_unique] # hold the function keys that are already stored in the retreived
    visited: Annotated[list[str], merge_unique]     # prevents loops and repeat work
    depth: Annotated[dict, merge_dicts]             # id -> hops from the target
    max_depth: int                                  # stop condition, e.g. 2 or 3
    # --- audit and safety (new) ---
    evidence: Annotated[list[dict], add_items]      # {"tool", "args", "result_ref"}
    steps: int                                      # loop counter to avoid runaway loops
    max_steps: int
    # ---------- current retreivals ------------#
    plan : dict
    history : Annotated[list[dict] , add_items]

