import argparse
import ast
from pathlib import Path


def collect_functions(py_path: Path):
    src = py_path.read_text(encoding="utf-8-sig")
    tree = ast.parse(src, filename=str(py_path))
    rows = []

    class V(ast.NodeVisitor):
        def __init__(self):
            self.scope = []

        def visit_ClassDef(self, node):
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_FunctionDef(self, node):
            scope = ".".join(self.scope) if self.scope else "<module>"
            end = getattr(node, "end_lineno", node.lineno)
            rows.append(
                {
                    "file": str(py_path),
                    "scope": scope,
                    "function": node.name,
                    "start": node.lineno,
                    "end": end,
                    "length": end - node.lineno + 1,
                }
            )
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        def visit_AsyncFunctionDef(self, node):
            self.visit_FunctionDef(node)

    V().visit(tree)
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="python/grace_pipeline")
    parser.add_argument("--top", type=int, default=25)
    args = parser.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Path not found: {root}")

    rows = []
    for py in root.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        rows.extend(collect_functions(py))

    rows.sort(key=lambda x: x["length"], reverse=True)
    print("== Longest Python Functions ==")
    print(f"{'Length':>6}  {'Start':>5}  {'End':>5}  {'Scope':<30}  {'Function':<30}  File")
    for r in rows[: max(1, args.top)]:
        print(
            f"{r['length']:>6}  {r['start']:>5}  {r['end']:>5}  "
            f"{r['scope']:<30}  {r['function']:<30}  {r['file']}"
        )


if __name__ == "__main__":
    main()

