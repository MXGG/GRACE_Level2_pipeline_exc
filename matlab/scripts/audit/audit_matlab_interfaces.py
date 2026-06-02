import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


KEYWORDS = {
    "if",
    "else",
    "elseif",
    "end",
    "for",
    "while",
    "switch",
    "case",
    "otherwise",
    "try",
    "catch",
    "break",
    "continue",
    "return",
    "function",
    "classdef",
    "methods",
    "properties",
    "events",
    "global",
    "persistent",
    "parfor",
    "spmd",
    "true",
    "false",
}


@dataclass
class MatlabFile:
    path: Path
    module: str
    line_count: int
    primary_name: str | None
    inputs: int
    outputs: int
    has_varargin: bool
    has_varargout: bool


def detect_module(path: Path, root: Path) -> str:
    rel = path.relative_to(root)
    return rel.parts[0] if rel.parts else "root"


def parse_signature(line: str) -> tuple[str | None, int, int]:
    s = line.strip()
    if not s.lower().startswith("function"):
        return None, 0, 0
    s = s[len("function") :].strip()
    lhs = ""
    rhs = s
    if "=" in s:
        lhs, rhs = s.split("=", 1)
        lhs = lhs.strip()
        rhs = rhs.strip()
    m_name = re.match(r"([A-Za-z]\w*)\s*(?:\(([^)]*)\))?", rhs)
    if not m_name:
        return None, 0, 0
    name = m_name.group(1)
    in_args = m_name.group(2) or ""
    inputs = len([x for x in (a.strip() for a in in_args.split(",")) if x])
    outputs = 0
    if lhs:
        if lhs.startswith("[") and lhs.endswith("]"):
            out_args = lhs[1:-1]
            outputs = len([x for x in (a.strip() for a in out_args.split(",")) if x])
        else:
            outputs = 1
    return name, inputs, outputs


def read_primary_signature(lines: list[str]) -> tuple[str | None, int, int]:
    for raw in lines[:120]:
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if line.lower().startswith("function"):
            return parse_signature(line.split("%", 1)[0].rstrip())
        break
    return None, 0, 0


def collect_files(root: Path) -> list[MatlabFile]:
    rows: list[MatlabFile] = []
    for p in sorted(root.rglob("*.m")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        lines = txt.splitlines()
        name, nin, nout = read_primary_signature(lines)
        rows.append(
            MatlabFile(
                path=p,
                module=detect_module(p, root),
                line_count=len(lines),
                primary_name=name,
                inputs=nin,
                outputs=nout,
                has_varargin=("varargin" in txt),
                has_varargout=("varargout" in txt),
            )
        )
    return rows


def find_cross_module_calls(files: list[MatlabFile]) -> list[tuple[str, str, str, str]]:
    name_to_module: dict[str, str] = {}
    for f in files:
        if f.primary_name:
            name_to_module.setdefault(f.primary_name, f.module)

    edges: list[tuple[str, str, str, str]] = []
    token_re = re.compile(r"\b([A-Za-z]\w*)\b")
    for f in files:
        src_module = f.module
        txt = f.path.read_text(encoding="utf-8", errors="ignore")
        stripped = "\n".join(line.split("%", 1)[0] for line in txt.splitlines())
        seen: set[tuple[str, str]] = set()
        for token in token_re.findall(stripped):
            if token in KEYWORDS:
                continue
            if token == f.primary_name:
                continue
            dst_module = name_to_module.get(token)
            if not dst_module or dst_module == src_module:
                continue
            k = (token, dst_module)
            if k in seen:
                continue
            seen.add(k)
            edges.append((src_module, dst_module, token, str(f.path)))
    return edges


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="src")
    ap.add_argument("--max-lines", type=int, default=300)
    ap.add_argument("--max-args", type=int, default=8)
    ap.add_argument("--report", default="")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        raise SystemExit(f"Path not found: {root}")

    files = collect_files(root)
    by_module = Counter(f.module for f in files)

    mismatch = []
    for f in files:
        if not f.primary_name:
            continue
        if f.path.stem != f.primary_name:
            mismatch.append(f)

    dup = defaultdict(list)
    for f in files:
        if f.primary_name:
            dup[f.primary_name].append(f)
    duplicates = {k: v for k, v in dup.items() if len(v) > 1}

    long_files = [f for f in files if f.line_count > args.max_lines]
    high_arity = [f for f in files if max(f.inputs, f.outputs) > args.max_args]
    with_varargs = [f for f in files if f.has_varargin or f.has_varargout]

    edges = find_cross_module_calls(files)
    non_main_calls_main = [e for e in edges if e[0] != "main" and e[1] == "main"]

    out = []
    out.append("== MATLAB Interface Audit ==")
    out.append(f"Root: {root}")
    out.append("")
    out.append("-- Files By Module --")
    for mod, cnt in sorted(by_module.items()):
        out.append(f"{mod:12} {cnt}")
    out.append("")
    out.append(f"-- Filename/Primary Function Mismatch ({len(mismatch)}) --")
    for f in mismatch[:50]:
        out.append(f"{f.path} -> {f.primary_name}")
    out.append("")
    out.append(f"-- Duplicate Primary Function Names ({len(duplicates)}) --")
    for name, rows in sorted(duplicates.items()):
        out.append(f"{name} ({len(rows)})")
        for r in rows[:5]:
            out.append(f"  {r.path}")
    out.append("")
    out.append(f"-- Long Files > {args.max_lines} lines ({len(long_files)}) --")
    for f in sorted(long_files, key=lambda x: x.line_count, reverse=True)[:30]:
        out.append(f"{f.line_count:5}  {f.path}")
    out.append("")
    out.append(f"-- High Arity Signatures > {args.max_args} args ({len(high_arity)}) --")
    for f in sorted(high_arity, key=lambda x: (max(x.inputs, x.outputs), x.path.name), reverse=True)[:30]:
        out.append(f"in={f.inputs}, out={f.outputs}  {f.path}")
    out.append("")
    out.append(f"-- Varargin/Varargout Usage ({len(with_varargs)}) --")
    for f in with_varargs[:30]:
        flags = []
        if f.has_varargin:
            flags.append("varargin")
        if f.has_varargout:
            flags.append("varargout")
        out.append(f"{','.join(flags):18} {f.path}")
    out.append("")
    out.append(f"-- Non-main Modules Calling main/* ({len(non_main_calls_main)}) --")
    for src, dst, fn, path in non_main_calls_main[:80]:
        out.append(f"{src} -> {dst} via {fn}  ({path})")
    out.append("")
    out.append("Audit completed.")

    text = "\n".join(out)
    print(text)
    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
