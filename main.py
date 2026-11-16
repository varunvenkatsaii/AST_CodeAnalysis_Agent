from AST_Extractor import save_codebase_details , analyze_project_files
from AST_relation import analyze_project , show_file_relations , show_function_relations , save_codebase_relation_details
from semantic_relation import generate_semantic_details
from llm import get_llm
import json
import os
from graph import compiled_graph
from langchain_core.messages import HumanMessage
llm = get_llm()


CODEBASE_ROOT = r"D:\TM"
METADATA_Storage = r"C:\Users\DELL\Downloads\graph-agent\codebase_data"
#------------------------------------ AST --------------------#
def Generate_AST_Facts():
    target_code_base = CODEBASE_ROOT
    details = analyze_project_files(target_code_base)
    save_codebase_details(
    code_details=details,
    output_dir=METADATA_Storage
    )

    files, results = analyze_project(CODEBASE_ROOT)
    file_relations = show_file_relations(files , results)
    func_relations = show_function_relations(files , results)
    save_codebase_relation_details(
            function_relations=func_relations,
            file_relations=file_relations,
            output_dir= METADATA_Storage
        ) 

    print("AST JSON files created successfully")


#---------------------------------semantic details generation-------------------------------


def generate_semantic_dict(folder = CODEBASE_ROOT):
    files_dict = {}
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules")]
        for name in names:
            if name.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, name), folder)
                module = rel[:-3].replace(os.sep, ".")
                if module.endswith(".__init__"):
                    module = module[:-9]
                files_dict[module] = rel

    results = []
    for filename, file in files_dict.items():
        result = ( generate_semantic_details(file , METADATA_Storage, llm) )
        while isinstance(result  , str):
            result = json.loads(result)
        results.append(result)

    semantic_path = os.path.join(METADATA_Storage , "semantic.json")
    with open(semantic_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)


#--------------------------------------------------------------Invoke agent--------------------------------------------
def create_agent():
    Generate_AST_Facts()
    generate_semantic_dict()
    agent = compiled_graph()
    return agent

agent = create_agent()

initial_state = {
    "messages": [HumanMessage(content=" what is the reranking logic used if i change it what all will be effected")],
    "targets": [], 
    "max_steps": 8,
    "max_depth": 4,
}

result = agent.invoke(initial_state, config={"recursion_limit": 30})




