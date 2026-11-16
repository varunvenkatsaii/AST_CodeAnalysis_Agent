import json
from langchain_core.messages import SystemMessage
import os
from pydantic import BaseModel , Field , model_validator
from typing import  Literal , Optional, Annotated , Union
from langchain_core.messages import HumanMessage
from state import AgentState
from llm import get_llm
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START , END
llm = get_llm()
#----------------------------------BaseModels-------------------------------#

CODEBASE_ROOT = r"D:\TM"
METADATA_PATH = os.path.join("codebase_data", "code_details.json")
semantic_path = r"codebase_data\semantic.json"
semantic_details = ""
class RetrieveFullFile(BaseModel):
    toolname: Literal["retrieve_full_file"]
    filename: str = Field(description="File name, e.g. 'utils.py'.")
    reason: str = Field(description="Why this tool is needed.")


class RetrieveCodeArtifact(BaseModel):
    toolname: Literal["retrieve_code_artifact"]
    filename: str = Field(description="File containing the requested code.")
    artifact: Literal[
        "imports",
        "classes",
        "methods",
        "functions",
        "loops",
        "conditionals",
        "variables",
        "exceptions",
        "with_statements"
    ]
    reason: str = Field(description="Why this tool is needed.")


class RetrieveCodeSemantics(BaseModel):
    toolname: Literal["retrieve_file_details"]
    filename: str = Field(description="File whose semantic details are required.")
    reason: str = Field(description="Why this tool is needed.")


ToolAction = Annotated[
    Union[RetrieveFullFile, RetrieveCodeArtifact, RetrieveCodeSemantics],
    Field(discriminator="toolname"),
]


class ExecutionPlan(BaseModel):
    status: Literal["continue", "complete"] = Field(
        description="Whether additional retrieval is required or the current information is sufficient."
    )

    tool_calls: list[ToolAction] = Field(
        description="Empty ONLY if the retrieved information already answers every part of the question."
    )   # no default: a missing value fails parsing
    reasoning: str = Field(description="ONE sentence, max 30 words.")


    reasoning: str = Field(
        description="Brief explanation (1-3 sentences) of the retrieval decision. Do not write a long analysis."
    )
    completion_reason: Optional[str] = Field(
        default=None,
        description="REQUIRED when status is 'complete': one sentence on why the information is sufficient. Must be null when status is 'continue'."
    )

    visiting: Optional[str]  = Field(
        default=None,
        description="the function or import or what ever the file and module we are about to visit now like api.py:func_name"
    )

#----------------------------------------------------------- Prompt -------------------------------------------#

FILE_OVERVIEW_FIELDS = [
    "file_name",
    "purpose",
    "responsibilities",
    "functionality",
    "function_summaries",
    "file_dependencies",
    "file_dependents",
    "architectural_role",
    "execution_flow"
]

def load_semantic_info(json_path: str) -> list[dict]:
    """Load the semantic info JSON (a list of per-file dicts)."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_file_overview(semantic_info: list[dict]) -> list[dict]:
    """Return overview fields for all files."""

    return [
        {key: entry.get(key) for key in FILE_OVERVIEW_FIELDS}
        for entry in semantic_info
    ]

def build_file_overview(semantic_info: list[dict]) -> str:
    blocks = []

    for e in semantic_info:

        functions = "\n".join(
            f"  - {func['function_name']}: {func['purpose']}"
            for func in e.get("function_summaries", [])
        )

        dependencies = "\n".join(
            f"  - {dep['file_name']}: {dep['reason']}"
            for dep in e.get("file_dependencies", [])
        )

        dependents = "\n".join(
            f"  - {dep['file_name']}: {dep['reason']}"
            for dep in e.get("file_dependents", [])
        )

        blocks.append(
            f"""
        File: {e['file_name']}

        Purpose:
        {e.get('purpose', '')}

        Architectural Role:
        {e.get('architectural_role', '')}

        Functions:
        {functions or "  None"}

        Dependencies:
        {dependencies or "  None"}

        Dependents:
        {dependents or "  None"}
        """
                )

    return "\n\n".join(blocks)




PLANNER_PROMPT = """
You are the planning component of a code-understanding agent.

Your responsibility is to decide which retrieval tools to call next so the
final answer is based on real code and evidence, not assumptions.

You will receive:
1. User question
2. Semantic overview of project files
3. Already retrieved information
4. Previously fetched items
5. Instructions and constraints provided during previous steps
6. Previously visited functions, classes and modules

IMPORTANT: The semantic overview contains only file names and short summaries.
It does NOT contain source code, constants, default values or implementation
details. Those come ONLY from the tools below.

## Tools

### 1. retrieve_file_details(filename)
Semantic summary of ONE file: its purpose, what each function and class does,
and how it relates to other files. No source code.
- filename: exact file name, e.g. "api.py"
- Returns null if the file is not found: check the name against the overview.
How to use:
- Call it when you are unsure which file or function holds the logic.
- Use it to learn exact function and class names, and which files depend on a file.
- It never contains constants or implementation, so follow it with tool 2 or 3.

### 2. retrieve_code_artifact(filename, artifact)
Actual SOURCE CODE of every item of one category in ONE file, with line numbers.
- artifact: MUST be exactly one of: imports, classes, methods, functions,
  loops, conditionals, variables, exceptions, with_statements (never free text)
    variables       -> constants and config values (e.g. chunk_size)
    functions       -> source code of all functions in the file
    classes         -> source code of all classes
    methods         -> source code of all class methods
    imports         -> import statements (what the file depends on)
    exceptions      -> try/except blocks (error handling)
    with_statements -> with-blocks (files, locks, connections)
- Returns every item in the category, not one named item.
- If it returns success=false, that category does not exist for the file:
  try another artifact, or use tool 3.
How to use:
- Looking for a constant or default value -> "variables", then "functions"
  for the code that uses it.
- Asking what a file depends on -> "imports".
- Reading how the logic works -> "functions" or "classes".

### 3. retrieve_full_file(filename)
Complete SOURCE CODE of ONE file as a single block of text: imports, constants,
classes and every function, in order.
- filename: exact file name, e.g. "recursive_chunking.py"
- Returns a string starting with "Error:" if the file is missing or unreadable.
How to use:
- Use it when you need the whole picture of a file in one call.
- Use it as the FALLBACK: if tool 1 or 2 returned null, success=false or an
  error for a file, call this instead of repeating the failed call.
- Prefer tool 2 when one category is enough, since it returns less text.

## Choosing tools
- Unsure where the logic lives            -> retrieve_file_details
- Need a constant, default or imports     -> retrieve_code_artifact (variables / imports)
- Need to read how the code works         -> retrieve_code_artifact (functions / classes)
- Need everything in a file together      -> retrieve_full_file
- A tool returned null or an error        -> retrieve_full_file for that file

## Planning procedure

1. Understand the user's intent and every part of the question.
2. Identify relevant files using their semantic overviews.
3. Identify the functions, classes, variables or modules that need investigation.
4. Determine what information is already available in the retrieved state.
5. Identify what is still missing for EACH part of the question.
6. Return tool calls that fetch the missing information.

## Iterative analysis and retrieval validation

- Review previous instructions, constraints and visited items before planning.
- Check each retrieved result: does it give enough evidence for the question?
- If a result shows dependencies, callers, shared state or related files that
  matter for the question, investigate them in the next step.
- If a result is insufficient, identify the next relevant file or category.
- Do not repeat a call that is already in the retrieved information.
- If a call returned null, success=false or an error, change the tool, the
  artifact or the filename. Never repeat the same failing call.
- Consider the complete investigation history when choosing the next step.

## Planning rules

- Never invent file names or symbols. Use only names found in the overview
  or in retrieved results.
- For impact analysis: read the code being changed, then use
  retrieve_file_details to find the files that depend on it, then read the
  relevant code in those files.
- For explaining a function: retrieve its source with retrieve_code_artifact
  (functions) or retrieve_full_file.
- For change suggestions: retrieve the implementation and the code of the
  dependent files before suggesting changes.
- Request at most 3 independent calls per step.

## When to stop (very important)

- If the retrieved information is empty, check whether the semantic overview
  or the conversation already contains everything needed to answer EVERY part
  of the question. If it does, you may return an EMPTY tool_calls list
  (status complete). Otherwise you MUST return at least one tool call.
- Return an EMPTY tool_calls list (status complete) ONLY if all the required
  evidence is already available (in the retrieved information or in the details
  you already have) and no further investigation is needed to answer EVERY
  part of the question.
- If any part of the question is unanswered, or you are unsure, return tool calls.
- Questions about code behavior, constants, default values or implementation
  usually need source code, so the overview alone is rarely enough for them.

  
## Output

Return only the structured ExecutionPlan: tool_calls first, then reasoning in
ONE sentence (max 70 words). No long analysis.

## Examples

Question: "What chunk size is used, and what is the impact if it becomes 5000?"
Step 1 (nothing retrieved):
{"tool_calls": [
  {"toolname": "retrieve_code_artifact", "filename": "recursive_chunking.py",
   "artifact": "functions", "reason": "find chunk size in splitter code"},
  {"toolname": "retrieve_code_artifact", "filename": "recursive_chunking.py",
   "artifact": "variables", "reason": "find chunk size constants"},
  {"toolname": "retrieve_file_details", "filename": "recursive_chunking.py",
   "reason": "see which files depend on chunking"}],
 "reasoning": "Need the chunk size default and the files that depend on chunking."}

Step 2 (chunk size and dependent files retrieved, impact still unclear):
{"tool_calls": [
  {"toolname": "retrieve_code_artifact", "filename": "embedding_splitter.py",
   "artifact": "functions", "reason": "check embedding input limits"}],
 "reasoning": "Impact of 5000 depends on how chunks are embedded."}

Step 3 (all evidence gathered):
{"tool_calls": [],
 "reasoning": "Chunk size, its usage and the embedding limits are all retrieved."}
"""

ANSWER_PROMPT = """You are a code analysis assistant. You answer questions about a codebase
using information that was retrieved by earlier investigation steps.

You are given:
- user_question: what the user wants to know.
- retrieved_information: the actual code details fetched from the project. This is your main source of truth.
- evidence: a log of which tools were called, with what arguments, and where each result is stored. Use it to cite where your claims come from.
- completion_reason: why the investigation stopped. If it says the step limit was reached, the information may be incomplete.

How to answer:
1. Start with a direct answer to the question in one or two sentences.
2. Then explain in more detail, walking through the relevant files, functions, and logic in a sensible order (for example, the flow of execution).
3. Reference specific files and functions by name (e.g. utils.py::parse_config) so the user can find them.
4. Use only the retrieved information. Do not invent functions, parameters, or behavior that isn't in it.
5. If something needed to answer fully is missing or a tool returned an error, say clearly what is missing instead of guessing.
6. Keep it clear and well organized. Use short sections or bullets for multi-part answers, and code snippets only when they help.
7. Do not mention internal details like tool names, evidence logs, steps, or planning. Write as if you simply examined the code yourself.
8.When status is complete, you must always fill completion_reason
"""

#-------------------------------------------------Tools------------------------------------------
# retreive the code details

@tool
def retrieve_code_artifact(filename: str, artifact: str) -> dict:
    """Return the actual source code of EVERY item of one category in ONE file,
    with start and end line numbers.

    artifact must be exactly one of: imports, classes, methods, functions, loops,
    conditionals, variables, exceptions, with_statements.
      variables  -> module-level constants and config values (e.g. chunk_size)
      functions  -> source of all functions in the file
      classes    -> source of all class definitions
      methods    -> source of all class methods
      imports    -> import statements (what the file depends on)
      loops / conditionals / exceptions / with_statements -> those control-flow blocks

    Returns all items of the category, not one named item. Use "variables" or
    "imports" for small, targeted answers; "functions" can be large.

    Args:
        filename: File name, e.g. "recursive_chunking.py" ("recursive_chunking" also works).
        artifact: One of the categories above.
    Returns: {"success", "filename", "artifact", "total_artifacts",
              "results": [{"start_line", "end_line", "code"}]}.
             If success is false, "message" says why (no metadata, or no items of that category).
    """

    # 1. Normalize filename
    module_name = os.path.splitext(os.path.basename(filename))[0]

    source_filename = (
        filename if os.path.splitext(filename)[1]
        else f"{filename}.py"
    )

    # 2. Load metadata
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    # 3. Retrieve file metadata using normalized module name
    file_metadata = metadata.get(module_name)

    if file_metadata is None:
        return {
            "success": False,
            "message": f"No metadata found for {module_name}"
        }

    # 4. Retrieve requested artifact records
    artifact_records = file_metadata.get(artifact)

    if not artifact_records:
        return {
            "success": False,
            "message": f"No '{artifact}' artifacts found in {source_filename}"
        }

    # 5. Read source file
    file_path = os.path.join(CODEBASE_ROOT, source_filename)

    if not os.path.isfile(file_path):
        return {
            "success": False,
            "message": f"Source file not found: {file_path}"
        }

    with open(file_path, "r", encoding="utf-8") as f:
        source_lines = f.readlines()

    # 6. Extract code using recorded line ranges
    results = []

    for record in artifact_records:

        if not isinstance(record, list) or len(record) < 2:
            continue

        start_line, end_line = record[0], record[1]

        if (
            not isinstance(start_line, int)
            or not isinstance(end_line, int)
            or start_line < 1
            or end_line < start_line
            or end_line > len(source_lines)
        ):
            continue

        code = "".join(source_lines[start_line - 1:end_line])

        results.append({
            "start_line": start_line,
            "end_line": end_line,
            "code": code
        })

    return {
        "success": True,
        "filename": source_filename,
        "artifact": artifact,
        "total_artifacts": len(results),
        "results": results
    }



# retreive the semantic details
@tool
def retrieve_file_details(filename: str):
    """Return the semantic summary of ONE file: what the file is for and what its
    functions and classes do, in plain language. No source code.

    Use first, to find out which file or function is relevant to the question
    and to learn exact function and class names before reading code.

    Args:
        filename: Exact file name as written in the overview, e.g. "api.py".
    Returns: the file's semantic details, or None if the file is not found.
    """

    with open(semantic_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    for file_details in data:
        if file_details.get("file_name") == filename:
            return file_details

    return None


# retreive the full file
@tool
def retrieve_full_file(filename: str) -> str:
    """Return the complete source code of ONE file as a single block of text:
    imports, constants, classes and every function, in order, unfiltered.

    Use when you need the whole picture of a file, or as the fallback when
    retrieve_code_artifact or retrieve_file_details failed for that file.

    Args:
        filename: Exact file name, e.g. "recursive_chunking.py".
    Returns: the full source text, or a string starting with "Error:" if the file
             is missing or unreadable.
    """
    file_path = os.path.join(CODEBASE_ROOT, filename)

    if not os.path.isfile(file_path):
        return f"Error: File '{filename}' not found."

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    except UnicodeDecodeError:
        return f"Error: Unable to decode '{filename}' as UTF-8."

    except OSError as e:
        return f"Error reading file: {str(e)}"


tool_registry = {
   "retrieve_file_details" : retrieve_file_details,
   "retrieve_code_artifact" : retrieve_code_artifact,
   "retrieve_full_file" : retrieve_full_file
}

#----------------------------------------------------- Graph Nodes -----------------------------------------#

def initialize(state: AgentState):

    return {
        "visited": state.get("visited", []),
        "fetched": state.get("fetched", []),
        "retrieved": state.get("retrieved", {}),
        "depth": state.get("depth", {}),
        "steps": state.get("steps", 0),
        "plan": state.get("plan", {}),
        "evidence": state.get("evidence", []),
        "max_steps" : 10
    }

def planner_node(state : AgentState):
    planner = llm.with_structured_output(ExecutionPlan)
#---------building semantic overview to attach to planner prompt here hardly take seconds ------- #
    sem_json = load_semantic_info(semantic_path)
    get_file_list = get_file_overview(sem_json)
    semantic_details = build_file_overview(get_file_list)
#---------------------------------
    sys_prompt = f""" {PLANNER_PROMPT}
     #semantic project review
    {json.dumps(semantic_details , indent=2 )}

    """
    planner_input = {
        "user_question": state["messages"][-1].content,
        "retrieved_information": state["retrieved"],
        "fetched_functions": state["fetched"],
        "visited_functions": state["visited"],
        "depth": state["depth"],
        "max_depth": state["max_depth"],
        "previous_instructions": state["evidence"],
        "previous_plan": state["plan"],
        "steps": state["steps"]
    }

    response = planner.invoke([
        SystemMessage(content=sys_prompt),
        HumanMessage(content=json.dumps(planner_input, indent=2))
    ])

    step = state["steps"] + 1


    return {
        "plan": response.model_dump(),
        "history": [{
            "step": step,
            "plan": response.model_dump()
        }],
      "steps" : step
    }


def retrieval_node(state: AgentState):

    plan = ExecutionPlan(**state["plan"])

    retrieved = {}
    fetched = []
    evidence = []
    visited = []

    for call in plan.tool_calls:

        args = call.model_dump(exclude={"toolname", "reason"})
        key = f"{call.toolname}:{json.dumps(args, sort_keys=True)}"
        tool = tool_registry.get(call.toolname)
        if tool is None:
            result = {"error": f"Unknown tool: {call.toolname}"}
        else:
            try:
                result = tool.invoke(args)
            except Exception as e:
                result = {"error": str(e)}

        visited.append(call.filename)
        fetched.append(key)
        retrieved[key] = result
        evidence.append({
            "tool": call.toolname,
            "args": {
                "target": args,
                "required_details": call.reason
            },
        })

    return {
        "retrieved": retrieved,
        "fetched": fetched,
        "evidence": evidence,
        "visited" : visited

    }

def final_answer_node(state : AgentState):
    response = llm.invoke([
            SystemMessage(content=ANSWER_PROMPT),
            HumanMessage(content=json.dumps({
                "user_question": state["messages"][-1].content,
                "retrieved_information": state["retrieved"],
                "evidence": state["evidence"],
                "completion_reason": state["plan"].get("completion_reason"),
            }, indent=2)),
        ])

    return {
            "messages": [response],
            "answer": response.content,
        }


#--------------------------------conditional routing ---------------------------------#

def route_after_planner(state: AgentState):

    plan = state.get("plan", {})

    if state.get("steps") >= state.get("max_steps"):
        return "final_answer"

    if plan.get("tool_calls"):
        return "retrieve"

    elif plan.status == "complete":
        # Sufficient information has been retrieved
        return "final_answer"

    else:
        raise ValueError(
            f"Invalid planner status: {plan.status}"
        )


#---------------------------------------- graph build --------------------------------------------------#


builder = StateGraph(AgentState)
builder.add_node("initialize", initialize)
builder.add_node("planner", planner_node)
builder.add_node("retrieval", retrieval_node)
builder.add_node("final_answer", final_answer_node)


builder.add_edge(START , "initialize")
builder.add_edge( "initialize" , "planner" )


builder.add_conditional_edges(
    "planner",
    route_after_planner,
    {
        "retrieve": "retrieval",
        "final_answer": "final_answer",
    },
)


builder.add_edge("retrieval" , "planner")
builder.add_edge("final_answer" , END)


def compiled_graph():
    agent = builder.compile()
    return agent

