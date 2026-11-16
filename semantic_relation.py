import json
import os , re
from llm import get_llm
from pydantic import BaseModel, Field
from typing import List


class FunctionSummary(BaseModel):
    function_name: str
    purpose: str
    responsibilities: List[str]
    inputs: List[str]
    operations: List[str]
    internal_dependencies: List[str]
    external_dependencies: List[str]
    side_effects: List[str]


class FileDependency(BaseModel):
    file_name: str
    reason: str


class CodeFileUnderstanding(BaseModel):
    file_name: str
    purpose: str

    responsibilities: List[str]
    functionality: List[str]

    architectural_role: str

    function_summaries: List[FunctionSummary]

    file_dependencies: List[FileDependency]
    file_dependents: List[FileDependency]

    execution_flow: List[str]
    state_management: List[str]

    uncertainties: List[str]
    derived_assumptions: List[str]




def get_file_details(file_name, directory):

    json_files = {
        "file_relations": "file_relations.json",
        "function_relations": "function_relations.json",
        "code_facts": "code_details.json"
    }

    result = {
        "file_name": file_name,
        "file_relations": {},
        "function_relations": {},
        "code_facts": {}
    }

    code_key = os.path.splitext(file_name)[0]

    for category, json_name in json_files.items():

        path = os.path.join(directory, json_name)

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if category == "function_relations":

            result[category] = {
                key: value
                for key, value in data.items()
                if key.startswith(f"{file_name}::")
            }

        elif category == "code_facts":

            result[category] = data.get(code_key, {})

        else:

            result[category] = data.get(file_name, {})

    return result




def create_semantic_prompt(file_details):

    context = json.dumps(file_details, indent=2)

    prompt = f""" You are a senior software architect analyzing a Python file.

    FILE CONTEXT (AST facts and dependency relationships):
    {context}

    TASK:
    Write semantic understanding of this file. Copy structural details (names, inputs, dependencies) directly from the context. Write your own words only for purposes, responsibilities, functionality, architectural role, operations, reasons, and uncertainties.

    Return ONLY a valid JSON object with exactly this structure:

    {{
        "file_name": "",
        "purpose": "one sentence",
        "responsibilities": ["up to 4 short items"],
        "functionality": ["up to 5 short items"],
        "architectural_role": "one sentence",
        "function_summaries": [
            {{
                "function_name": "",
                "purpose": "one sentence",
                "responsibilities": ["up to 2 short items"],
                "inputs": [],
                "operations": ["up to 4 short steps"],
                "internal_dependencies": [],
                "external_dependencies": [],
                "side_effects": []
            }}
        ],
        "file_dependencies": [
            {{
                "file_name": "",
                "reason": "short phrase"
            }}
        ],
        "file_dependents": [
            {{
                "file_name": "",
                "reason": "short phrase"
            }}
        ],
        "execution_flow": ["up to 5 short steps"],
        "state_management": [],
        "uncertainties": [],
        "derived_assumptions": []
    }}

    RULES:
    1. Take names, inputs, and dependencies exactly as they appear in the context. Do not rename or add any.
    2. Use function_relations for function-to-function calls and file_relations for file-level dependencies and dependents.
    3. Classify each call as same-file, other-file, external library, built-in, or unknown, based only on the context.
    4. Do not infer what a call does unless the context supports it. Do not invent implementations, return values, parameters, or execution order.
    5. Keep every text item under 15 words. Use [] for any list with nothing supported by the context.
    6. If something is unclear, add it to "uncertainties" instead of guessing.
    7. Base architectural_role on evidence in the context only.
    8. Output only the JSON object, with no markdown, code fences, or extra text."""

    return prompt


def generate_semantic_details(file_name, directory, llm):

    # Gather information from all three JSON files
    file_details = get_file_details(file_name, directory)

    # Generate LLM prompt
    prompt = create_semantic_prompt(file_details)
    print("LLM Invoked")
    # Invoke LLM
    structured_llm_output = llm.with_structured_output(
        CodeFileUnderstanding,
        method = "json_schema"
    )
    response = structured_llm_output.invoke(prompt)

    formatted_json = response.model_dump_json(indent = 2)

    while isinstance(formatted_json  , str):
        result = json.loads(formatted_json)

    return result
    '''   # Parse JSON response
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]

    semantic_details = json.loads(content)

    return semantic_details '''

llm = get_llm()
path = r"C:\Users\DELL\Downloads\graph-agent\codebase_data"
files_dict = {}
results =  []

for filename, file in files_dict.items():
  result = ( generate_semantic_details(file , r"/content/" , llm) )
  while isinstance(result  , str):
    result = json.loads(result)
  results.append(result)


with open("/content/semantic.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)