import ast
import os 
import json

def names_in(target):
    """Return variable names from an assignment target (handles a, b = ...)."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for t in target.elts for n in names_in(t)]
    if isinstance(target, ast.Starred):                 # a, *rest = ...
        return names_in(target.value)
    if isinstance(target, ast.Attribute):               # self.x = ...
        return [ast.unparse(target)]
    return []


def params_of(args):
    """All parameter names: positional-only, normal, *args, keyword-only, **kwargs."""
    names = [a.arg for a in args.posonlyargs + args.args]
    if args.vararg:
        names.append("*" + args.vararg.arg)
    names += [a.arg for a in args.kwonlyargs]
    if args.kwarg:
        names.append("**" + args.kwarg.arg)
    return ", ".join(names)


def extract(source):
    tree = ast.parse(source)

    # Every category is a list of tuples. Schemas:
    #   imports         (lineno, end_lineno, module, name, alias)
    #   classes         (lineno, end_lineno, name, bases)
    #   methods         (lineno, end_lineno, class_name, name, params, decorators)
    #   functions       (lineno, end_lineno, name, params)          # lambdas -> "<lambda>"
    #   loops           (lineno, end_lineno, kind, target, iterable_or_condition)
    #   conditionals    (lineno, end_lineno, kind, condition)
    #   variables       (lineno, end_lineno, name, kind, annotation, value)
    #   exceptions      (lineno, end_lineno, exception_type, alias)
    #   with_statements (lineno, end_lineno, items)
    result = {k: [] for k in (
        "imports", "classes", "methods", "functions", "loops",
        "conditionals", "variables", "exceptions", "with_statements",
    )}

    # Step 1: classes and their methods
    method_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            result["classes"].append((node.lineno, node.end_lineno, node.name, bases))

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_nodes.add(item)
                    decorators = ", ".join(f"@{ast.unparse(d)}" for d in item.decorator_list)
                    result["methods"].append((
                        item.lineno, item.end_lineno, node.name,
                        item.name, params_of(item.args), decorators,
                    ))

    # Step 2: everything else
    for node in ast.walk(tree):

        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(
                    (node.lineno, node.end_lineno, None, alias.name, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for alias in node.names:
                result["imports"].append(
                    (node.lineno, node.end_lineno, module, alias.name, alias.asname))

        # Functions (methods already listed above)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node not in method_nodes:
                result["functions"].append(
                    (node.lineno, node.end_lineno, node.name, params_of(node.args)))
        elif isinstance(node, ast.Lambda):
            result["functions"].append(
                (node.lineno, node.end_lineno, "<lambda>", params_of(node.args)))

        # Loops
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            result["loops"].append((node.lineno, node.end_lineno, "for",
                                    ast.unparse(node.target), ast.unparse(node.iter)))
            for name in names_in(node.target):
                result["variables"].append(
                    (node.lineno, node.end_lineno, name, "loop variable", None, None))
        elif isinstance(node, ast.While):
            result["loops"].append((node.lineno, node.end_lineno, "while",
                                    None, ast.unparse(node.test)))
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for gen in node.generators:
                result["loops"].append((node.lineno, node.end_lineno,
                                        type(node).__name__,
                                        ast.unparse(gen.target), ast.unparse(gen.iter)))

        # Conditionals
        elif isinstance(node, ast.If):
            result["conditionals"].append(
                (node.lineno, node.end_lineno, "if", ast.unparse(node.test)))
        elif isinstance(node, ast.IfExp):
            result["conditionals"].append(
                (node.lineno, node.end_lineno, "ternary", ast.unparse(node.test)))
        elif isinstance(node, ast.Match):
            result["conditionals"].append(
                (node.lineno, node.end_lineno, "match", ast.unparse(node.subject)))

        # Variables
        elif isinstance(node, ast.Assign):
            value = ast.unparse(node.value)
            for target in node.targets:
                for name in names_in(target):
                    result["variables"].append(
                        (node.lineno, node.end_lineno, name, "assign", None, value))
        elif isinstance(node, ast.AnnAssign):
            value = ast.unparse(node.value) if node.value else None
            for name in names_in(node.target):
                result["variables"].append(
                    (node.lineno, node.end_lineno, name, "annotated",
                     ast.unparse(node.annotation), value))
        elif isinstance(node, ast.AugAssign):
            for name in names_in(node.target):
                result["variables"].append(
                    (node.lineno, node.end_lineno, name,
                     f"augmented ({type(node.op).__name__})", None, ast.unparse(node.value)))
        elif isinstance(node, ast.arg):
            result["variables"].append(
                (node.lineno, node.end_lineno, node.arg, "parameter",
                 ast.unparse(node.annotation) if node.annotation else None, None))

        # try / except  (TryStar = except*, Python 3.11+)
        elif isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            for h in node.handlers:
                result["exceptions"].append((
                    h.lineno, h.end_lineno,
                    ast.unparse(h.type) if h.type else "everything",
                    h.name))

        # with statements
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            items = ", ".join(ast.unparse(i) for i in node.items)
            result["with_statements"].append((node.lineno, node.end_lineno, items))

    # Sort each category by line number so output reads top-to-bottom
    for k in result:
        result[k].sort(key=lambda t: (t[0], t[1]))

    return result

def analyze_project_files(folder):
    files = {}      # module name -> relative path
    code_details = {}
    for root, dirs, names in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "__pycache__", "node_modules")]
        for name in names:
            if name.endswith(".py"):
                rel = os.path.relpath(os.path.join(root, name), folder)
                module = rel[:-3].replace(os.sep, ".")
                if module.endswith(".__init__"):
                    module = module[:-9]
                files[module] = rel

        for module, rel_path in files.items():
            full_path = os.path.join(folder, rel_path)
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    code_details[module] = extract(f.read() ) 
            except (UnicodeDecodeError, OSError) as e:
                print(f"Skipping {rel_path}: {e}")


    return code_details

def save_codebase_details(
    code_details,
    output_dir="code_details"
):

    os.makedirs(output_dir, exist_ok=True)

    files_to_save = {
        "code_details.json": code_details,
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





if __name__ == "__main__":
    details = analyze_project_files(r"D:\TM")
    save_codebase_details(
        code_details=details,
        output_dir= r"C:\Users\DELL\Downloads\graph-agent\codebase_data"
    )