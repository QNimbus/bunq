#!/usr/bin/env -S python -W ignore

# func_call_analyzer.py

# Standard library imports
import ast
import argparse
import importlib
from typing import Set, Tuple, Dict, List

# Third-party imports
# ...

# Local application/library imports
# ...


def map_imports(node) -> Dict[str, str]:
    """
    Maps imported functions to their respective modules.

    Args:
        node: The AST node to analyze.

    Returns:
        Dict[str, str]: A dictionary mapping function names to module names.
    """
    imports = {}

    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import):
            for name in child.names:
                imports[name.name] = name.name
        elif isinstance(child, ast.ImportFrom):
            module = child.module if child.module else ""
            for name in child.names:
                imports[name.name] = module

    return imports


def is_builtin_function(name: str) -> bool:
    """
    Check if a function name is a built-in function.

    Args:
        name: The name of the function.

    Returns:
        bool: True if it's a built-in function, False otherwise.
    """
    return name in dir(__builtins__)


def find_function_calls_and_exceptions(node, internal_funcs: Set[str], imports: Dict[str, str], function_parameters: List[str]) -> Tuple[Set[str], Set[str], Set[str]]:
    """
    Recursively analyzes an abstract syntax tree (AST) node to find function calls and raised exceptions.

    Args:
        node (ast.AST): The AST node to analyze.
        internal_funcs (Set[str]): A set of internal function names.
        imports (Dict[str, str]): A dictionary mapping imported function names to their respective modules.
        function_parameters (List[str]): A list of function parameter names.

    Returns:
        Tuple[Set[str], Set[str], Set[str]]: A tuple containing three sets:
            - internal_calls: Set of internal function calls found in the AST.
            - external_calls: Set of external function calls found in the AST.
            - raised_exceptions: Set of raised exceptions found in the AST.
    """
    internal_calls = set()
    external_calls = set()
    raised_exceptions = set()

    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef):
            # Update function parameters for this new function scope
            new_function_parameters = [arg.arg for arg in child.args.args]
            child_internal, child_external, child_exceptions = find_function_calls_and_exceptions(child, internal_funcs, imports, new_function_parameters)
            internal_calls |= child_internal
            external_calls |= child_external
            raised_exceptions |= child_exceptions
        elif isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id in internal_funcs:
                internal_calls.add(child.func.id)
            elif child.func.id in function_parameters:
                # This is a callable variable, skip it
                continue
            else:
                if is_builtin_function(child.func.id):
                    external_calls.add(f"built-in.{child.func.id}")
                else:
                    module = imports.get(child.func.id, "unknown_module")
                    external_calls.add(f"{module}.{child.func.id}")
        elif isinstance(child, ast.Raise):
            if child.exc:
                if isinstance(child.exc, ast.Name):
                    raised_exceptions.add(child.exc.id)
                elif isinstance(child.exc, ast.Call) and isinstance(child.exc.func, ast.Name):
                    raised_exceptions.add(child.exc.func.id)
        else:
            # Recursively process other nodes
            child_internal, child_external, child_exceptions = find_function_calls_and_exceptions(child, internal_funcs, imports, function_parameters)
            internal_calls |= child_internal
            external_calls |= child_external
            raised_exceptions |= child_exceptions

    return internal_calls, external_calls, raised_exceptions


def analyze_function_calls(module_name: str, function_name: str) -> None:
    """
    Analyzes the function calls within a module and prints the internal and external function calls of a target function.

    Args:
        module_name (str): The name of the module to analyze.
        function_name (str): The name of the target function.

    Returns:
        None
    """
    module = importlib.import_module(module_name)

    with open(module.__file__, "r", encoding="utf-8") as file:
        module_ast = ast.parse(file.read())

    # Map imports
    imports = map_imports(module_ast)

    # Collect internal function names
    internal_funcs = {node.name for node in ast.walk(module_ast) if isinstance(node, ast.FunctionDef)}

    # Find the target function
    target_func = next((node for node in ast.walk(module_ast) if isinstance(node, ast.FunctionDef) and node.name == function_name), None)
    if not target_func:
        print(f"Function '{function_name}' not found in the module.")
        return

    # Find function calls and raised exceptions
    internal_calls, external_calls, raised_exceptions = find_function_calls_and_exceptions(target_func, internal_funcs, imports, [])

    # Print internal function calls in bulleted list format
    print(f"Internal function calls in '{function_name}':")
    for call in internal_calls:
        print(f"- {call}")

    # Print external function calls in bulleted list format
    print(f"External function calls in '{function_name}':")
    for call in external_calls:
        print(f"- {call}")

    print(f"Exceptions raised in '{function_name}':")
    for exception in raised_exceptions:
        print(f"- {exception}")


def main():
    parser = argparse.ArgumentParser(description="Analyze function calls within a specified function of a module.")
    parser.add_argument("module_path", type=str, help="Path to the module")
    parser.add_argument("function_name", type=str, help="Function name to analyze")
    args = parser.parse_args()

    analyze_function_calls(args.module_path, args.function_name)


if __name__ == "__main__":
    main()
