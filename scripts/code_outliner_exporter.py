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


def extract_signatures(file_path: Path, include_docstrings: bool = False) -> list:
    """
    Extracts the function and class signatures along with their docstrings from a given file.

    Args:
        file_path (Path): The path to the file.
        include_docstrings (bool): Whether to include docstrings in the signatures.

    Returns:
        list: A list of function and class signatures with docstrings.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        node = ast.parse(file.read())

    signatures = []

    for n in node.body:
        if isinstance(n, ast.FunctionDef):
            signatures.append(extract_function_signature(n, include_docstring=include_docstrings))

        elif isinstance(n, ast.ClassDef):
            class_header = f"class {n.name}:"
            if include_docstrings:
                docstring = ast.get_docstring(n)
                if docstring:
                    docstring = docstring.replace("\n", "\n    ")
                    class_header += f'\n    """\n    {docstring}\n    """'
            signatures.append(class_header)

            for m in n.body:
                if isinstance(m, ast.FunctionDef):
                    method_signature = extract_function_signature(m, class_name=n.name, include_docstring=include_docstrings)
                    signatures.append(method_signature)

    return signatures


def extract_function_signature(func_def, class_name=None, include_docstring=False) -> str:
    """
    Extracts the signature of a function or method.

    Args:
        func_def (ast.FunctionDef): The function definition node.
        class_name (Optional[str]): The name of the class if it's a method.

    Returns:
        str: The function or method signature.
    """
    # Function or method header
    prefix = f"{class_name}." if class_name else ""
    func_header = f"def {prefix}{func_def.name}("

    # Function header
    params = [ast.unparse(arg) for arg in func_def.args.args]
    func_header += ", ".join(params)
    if func_def.args.vararg:
        func_header += ", *" + func_def.args.vararg.arg
    if func_def.args.kwonlyargs:
        kwonlyargs = [ast.unparse(arg) for arg in func_def.args.kwonlyargs]
        func_header += ", " + ", ".join(kwonlyargs) if params else ", ".join(kwonlyargs)
    if func_def.args.kwarg:
        func_header += ", **" + func_def.args.kwarg.arg
    func_header += "):"

    # Append docstring if present
    if include_docstring:
        docstring = ast.get_docstring(func_def)
        if docstring:
            docstring = docstring.replace("\n", "\n    ")
            func_header += f'\n    """\n    {docstring}\n    """'

    return func_header


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
    parser.add_argument("-d", "--include-docstrings", action="store_true", help="Include docstrings")
    parser.add_argument("-o", "--output", type=str, help="Output Markdown file")
    args = parser.parse_args()

    python_file = args.python_file
    output_file = args.output if args.output else os.path.splitext(python_file)[0] + "_sigs.md"

    function_signatures = extract_signatures(python_file, include_docstrings=args.include_docstrings)
    write_to_markdown(function_signatures, output_file)
    print(f"Function signatures extracted to {output_file}")


if __name__ == "__main__":
    main()
