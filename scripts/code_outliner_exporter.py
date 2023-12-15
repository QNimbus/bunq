#!/usr/bin/env -S python -W ignore

# code_outliner_exporter.py

# Standard library imports
import os
import ast
import argparse
from pathlib import Path

# Third-party imports
# ...

# Local application/library imports
# ...


def extract_signatures(file_path: Path, exclude_docstrings: bool = False, escape_docstrings: bool = False) -> list:
    """
    Extracts the function and class signatures along with their docstrings from a given file.

    Args:
        file_path (Path): The path to the file.
        exclude_docstrings (bool): Whether to exclude docstrings or not.
        escape_docstrings (bool): Whether to escape docstrings with ''' instead of triple double-quotes.

    Returns:
        list: A list of function and class signatures with docstrings.
    """
    with open(file_path, "r", encoding="utf-8") as file:

        def extract_from_node(node, class_name=None, parent_func_name=None) -> list:
            signatures = []

            for n in node.body:
                if isinstance(n, ast.FunctionDef):
                    func_signature = extract_function_signature(n, class_name=class_name, parent_func_name=parent_func_name, exclude_docstrings=exclude_docstrings)
                    signatures.append(func_signature)

                    # Recursively search inside the function with the current function name as parent
                    signatures.extend(extract_from_node(n, class_name, parent_func_name=n.name))
                elif isinstance(n, ast.ClassDef) and class_name is None:  # Only top-level classes
                    class_header = f"class {n.name}:"
                    if not exclude_docstrings:
                        docstring = ast.get_docstring(n)
                        if docstring:
                            docstring = docstring.replace("\n", "\n    ")
                            class_header += f'\n    """\n    {docstring}\n    """'

                    signatures.append(class_header)

                    # Extract from class body
                    signatures.extend(extract_from_node(n, class_name=n.name))

            if escape_docstrings:
                signatures = [s.replace('"""', "'''") for s in signatures]

            return signatures

        # Use the recursive function
        return extract_from_node(ast.parse(file.read()))


def extract_function_signature(func_def, class_name: str = None, parent_func_name: str = None, exclude_docstrings: bool = False) -> str:
    """
    Extracts the signature of a function or method, including the return type if present.

    Args:
        func_def (ast.FunctionDef): The function definition node.
        class_name (Optional[str]): The name of the class if it's a method.
        parent_func_name (Optional[str]): The name of the parent function if it's a nested function.
        exclude_docstrings (bool): Whether to exclude docstrings or not.

    Returns:
        str: The function or method signature with return type.
    """
    # Process decorators
    decorators = [f"@{ast.unparse(decorator)}" for decorator in func_def.decorator_list]
    decorator_str = "\n".join(decorators) + "\n" if decorators else ""

    # Function header construction
    prefix = f"{class_name}." if class_name else ""
    nested_prefix = f"{parent_func_name} > " if parent_func_name else ""
    func_header = f"{nested_prefix}def {prefix}{func_def.name}("

    # Parameters construction
    params = [ast.unparse(arg) for arg in func_def.args.args]
    func_header += ", ".join(params)
    if func_def.args.vararg:
        func_header += ", *" + func_def.args.vararg.arg
    if func_def.args.kwonlyargs:
        kwonlyargs = [ast.unparse(arg) for arg in func_def.args.kwonlyargs]
        func_header += ", " + ", ".join(kwonlyargs) if params else ", ".join(kwonlyargs)
    if func_def.args.kwarg:
        func_header += ", **" + func_def.args.kwarg.arg

    # Append return type if present
    if func_def.returns:
        return_type = ast.unparse(func_def.returns)
        func_header += f") -> {return_type}:"
    else:
        func_header += "):"

    # Append docstring if present
    if not exclude_docstrings:
        docstring = ast.get_docstring(func_def)
        if docstring:
            docstring = docstring.replace("\n", "\n    ")
            func_header += f'\n    """\n    {docstring}\n    """'

    return decorator_str + func_header


def write_to_markdown(functions, output_file: Path):
    """Write the function signatures to a Markdown file."""
    with open(output_file, "w", encoding="utf-8") as file:
        file.write("```python\n")
        for func in functions:
            file.write(f"\n{func}\n")
        file.write("\n```\n\n")


def main():
    """
    Extracts Python function signatures and class definitions from a given Python file and writes them to a Markdown file.

    Usage:
        python_file: str - Python file to extract code outline from.
        output: str - Output Markdown file to write the function signatures to. If not provided, a default file name will be used.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Extract Python function signatures.")
    parser.add_argument("python_file", type=str, help="Python file to extract from")
    parser.add_argument("-n", "--no-docstrings", action="store_true", help="Exclude docstrings")
    parser.add_argument("-e", "--escape-docstrings", action="store_true", help="Escape docstrings with ''' instead of \"\"\"")
    parser.add_argument("-o", "--output", type=str, help="Output Markdown file")
    args = parser.parse_args()

    python_file = args.python_file
    output_file = args.output if args.output else os.path.splitext(python_file)[0] + "_sigs.md"

    function_signatures = extract_signatures(python_file, exclude_docstrings=args.no_docstrings, escape_docstrings=args.escape_docstrings)
    write_to_markdown(function_signatures, output_file)
    print(f"Function signatures extracted to {output_file}")


if __name__ == "__main__":
    main()
