"""
Find relations using AST:
  1. Which function calls which (inside the file, outside the file, builtins)
  2. Which file imports / depends on which other file in a project

Usage:
    python ast_relations.py path/to/project_folder
    python ast_relations.py            # runs on a small demo project
"""
import ast
import builtins
import os
import json

BUILTINS = set(dir(builtins))
FUNC_TYPES = (ast.FunctionDef, ast.AsyncFunctionDef)


# ---------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------
def read_imports(tree, module_name):
    """Map the name used in code -> the full name it refers to.
       import numpy as np          ->  {'np': 'numpy'}
       from utils import helper    ->  {'helper': 'utils.helper'}"""
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    imports[a.asname] = a.name
                else:
                    top = a.name.split(".")[0]      # 'import os.path' binds 'os'
                    imports[top] = top
        elif isinstance(node, ast.ImportFrom):
           ''' base = node.module or ""
            if node.level:                          # relative import: from . import x
                parent = module_name.split(".")[:-1]
                parent = parent[:len(parent) - (node.level - 1)]
                base = ".".join(parent + ([node.module] if node.module else [])) '''
           for a in node.names:
                imports[a.asname or a.name] = f"{node.module}.{a.name}"
    return imports


def find_functions(tree):
    """Return {'name': (node, class_name)}; methods are named 'Class.method'."""
    funcs = {}
    for node in tree.body:
        if isinstance(node, FUNC_TYPES):
            funcs[node.name] = (node, None)
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, FUNC_TYPES):
                    funcs[f"{node.name}.{item.name}"] = (item, node.name)
    return funcs


def get_calls(nodes):
    """Return every call in the given nodes as text, e.g. 'self.save', 'os.path.join'."""
    calls = []
    for node in nodes:
        for n in ast.walk(node):
            if isinstance(n, ast.Call):
                calls.append(ast.unparse(n.func))
    return calls


def classify(call, cls, funcs, classes, imports):
    """Decide where a call goes: same file, another module, builtin or unknown."""
    first = call.split(".")[0]
    rest = call[len(first):]                        # '.path.join' or ''

    if cls and call.startswith("self.") and f"{cls}.{call[5:]}" in funcs:
        return "same-file", f"{cls}.{call[5:]}"     # self.method()
    if call in funcs:
        return "same-file", call                    # helper()
    if call in classes:
        return "same-file", f"{call} (class)"       # Dog()
    if first in imports:
        return "outside", imports[first] + rest     # os.path.join() / helper()
    if call in BUILTINS:
        return "builtin", call
    return "unknown", call                          # e.g. obj.append()


def match_project(name, modules):
    """If 'utils.helper' starts with a project module (utils), return (module, rest)."""
    parts = name.split(".")
    for i in range(len(parts), 0, -1):
        module = ".".join(parts[:i])
        if module in modules:
            return module, ".".join(parts[i:])
    return None


# ---------------------------------------------------------------
# Step 1: analyze one file
# ---------------------------------------------------------------
def analyze_file(path, module_name):
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read())

    imports = read_imports(tree, module_name)
    funcs = find_functions(tree)
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}

    calls = {}
    for name, (node, cls) in funcs.items():
        found = get_calls([node])
        calls[name] = [classify(c, cls, funcs, classes, imports) for c in found]

    # code that runs at the top level of the file (outside any function/class)
    top_level = [n for n in tree.body if not isinstance(n, FUNC_TYPES + (ast.ClassDef,))]
    found = get_calls(top_level)
    calls["<module>"] = [classify(c, None, funcs, classes, imports) for c in found]

    return {"imports": imports, "calls": calls}


# ---------------------------------------------------------------
# Step 2: analyze a whole folder
# ---------------------------------------------------------------
def analyze_project(folder):
    files = {}      # module name -> relative path
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules")]
        for name in names:
            if name.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, name), folder)
                module = rel[:-3].replace(os.sep, ".")
                if module.endswith(".__init__"):
                    module = module[:-9]
                files[module] = rel

    results = {}
    for module, rel in files.items():
        try:
            results[module] = analyze_file(os.path.join(folder, rel), module)
        except SyntaxError:
            print(f"Skipping {rel} (syntax error)")
    return files, results


# ---------------------------------------------------------------
# Output
# ---------------------------------------------------------------
def show_function_relations(files, results):
    print("=" * 60)
    print("FUNCTION RELATIONS  (who calls what)")
    print("=" * 60)

    function_relations = {}

    for module, info in results.items():

        for func, calls in info["calls"].items():

            function_key = f"{files[module]}::{func}"

            function_relations[function_key] = []

            for kind, target in dict.fromkeys(calls):

                target_file = None

                if kind == "outside":
                    hit = match_project(target, files)

                    if hit and hit[1]:
                        kind = "other-file"
                        target_file = files[hit[0]]

                function_relations[function_key].append({
                    "kind": kind,
                    "target": target,
                    "target_file": target_file
                })

    return function_relations


def show_file_relations(files, results):
    imports_map = {m: set() for m in results}      # file -> files it imports
    imported_by = {m: set() for m in results}      # file -> files that import it

    for module, info in results.items():
        for full_name in info["imports"].values():
            hit = match_project(full_name, files)
            if hit and hit[0] != module and hit[0] in results:
                imports_map[module].add(hit[0])
                imported_by[hit[0]].add(module)

    print("\n" + "=" * 60)
    print("FILE RELATIONS  (who imports whom)")
    print("=" * 60)
    file_relations = {}

    for module in results:
        file_relations[files[module]] = {
            "imports": sorted(files[m] for m in imports_map[module]),
            "imported_by": sorted(files[m] for m in imported_by[module])
        }

    return file_relations


def save_codebase_relation_details(
    function_relations,
    file_relations,
    output_dir="codebase_data"
):

    os.makedirs(output_dir, exist_ok=True)

    files_to_save = {
        "function_relations.json": function_relations,
        "file_relations.json": file_relations
    }

    for filename, new_data in files_to_save.items():

        file_path = os.path.join(output_dir, filename)

        # Load existing data if file exists
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = {}
        else:
            existing_data = {}

        # Merge new data with existing data
        existing_data.update(new_data)

        # Write updated data
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(existing_data, f, indent=4)

    print("Codebase details saved successfully.")

# ---------------------------------------------------------------
# Demo project (used when no folder is given)
# ---------------------------------------------------------------
if __name__ == "__main__":
    path = r"D:\TM"
    files, results = analyze_project(path)
    file_relations = show_file_relations(files , results)
    func_relations = show_function_relations(files , results)

    save_codebase_relation_details(
        function_relations=func_relations,
        file_relations=file_relations,
        output_dir=os.path.join(r"C:\Users\DELL\Downloads\graph-agent", "codebase_data")
    ) 