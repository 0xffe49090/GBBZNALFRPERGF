#!/usr/bin/env python3
import argparse
import html
import re
import shutil
import subprocess
from pathlib import Path

COLORS = {
    "command_execution": ("#ff0000", 5),
    "memory_unsafe": ("#ff008c", 3),
    "heap": ("#ff8c00", 2),
    "input": ("#00aaff", 2),
    "output": ("#00ffff", 1),
    "filesystem": ("#ffff00", 2),
    "dynamic_loading": ("#a020f0", 3),
    "crypto": ("#00dc50", 1),
    "environment_privilege": ("#a0522d", 2),
}

FUNCTION_CATEGORIES = {
    "command_execution": {"system", "execve", "execv", "execl", "execlp", "execvp", "popen"},
    "memory_unsafe": {"gets", "strcpy", "strncpy", "strcat", "strncat", "sprintf", "vsprintf", "swprintf", "memcpy", "memmove", "bcopy"},
    "heap": {"malloc", "calloc", "realloc", "free", "mmap", "munmap"},
    "input": {"read", "recv", "recvfrom", "recvmsg", "fread", "scanf", "fscanf", "sscanf", "fgets", "getline", "getchar", "socket", "accept"},
    "output": {"write", "send", "sendto", "sendmsg", "fwrite", "printf", "fprintf", "puts", "putchar"},
    "filesystem": {"open", "fopen", "close", "fclose", "unlink", "rename"},
    "dynamic_loading": {"dlopen", "dlsym"},
    "crypto": {"AES_encrypt", "AES_decrypt", "EVP_EncryptInit", "EVP_DecryptInit", "SHA1", "SHA256", "SHA512", "MD5"},
    "environment_privilege": {"getenv", "setenv", "putenv", "setuid", "setgid", "seteuid", "setegid", "geteuid", "getegid"},
}

FUNC_RE = re.compile(r"^([0-9a-fA-F]+) <([^>]+)>:$")
CALL_RE = re.compile(r"^\s*([0-9a-fA-F]+):.*\b(call|callq)\b\s+([0-9a-fA-Fx]+)(?:\s+<([^>]+)>)?")
PLT_SECTION_RE = re.compile(r"^Disassembly of section \.plt")
SECTION_RE = re.compile(r"^Disassembly of section ")
RELOC_SYM_RE = re.compile(r"R_X86_64_JUMP_SLOT\s+[0-9a-fA-Fx]*\s*([A-Za-z_][A-Za-z0-9_@.]*)")


def cmd(args):
    return subprocess.run(args, text=True, capture_output=True, check=False)


def need(tool):
    if not shutil.which(tool):
        raise SystemExit(f"missing required tool: {tool}")


def normalize(sym):
    if not sym:
        return ""
    sym = sym.strip()
    sym = sym.split("@@")[0]
    sym = sym.split("@")[0]
    sym = re.sub(r"\+0x[0-9a-fA-F]+$", "", sym)
    return sym


def classify(sym):
    clean = normalize(sym)

    for category, names in FUNCTION_CATEGORIES.items():
        for name in names:
            # Exact only: avoids _system+0x10 matching system.
            if clean == name:
                color, score = COLORS[category]
                return category, name, color, score

    return None


def get_plt_base(binary):
    out = cmd(["objdump", "-d", "-M", "intel", str(binary)]).stdout
    in_plt = False

    for line in out.splitlines():
        if PLT_SECTION_RE.match(line):
            in_plt = True
            continue

        if in_plt and SECTION_RE.match(line):
            break

        if in_plt:
            m = FUNC_RE.match(line)
            if m:
                return int(m.group(1), 16)

    return None


def build_plt_map(binary):
    """
    x86_64 lazy PLT layout:
      .plt base entry is resolver
      first imported function is base + 0x10
      second is base + 0x20
      etc.

    readelf -rW gives JUMP_SLOT relocation order.
    """
    plt_base = get_plt_base(binary)
    if plt_base is None:
        return {}

    rel = cmd(["readelf", "-rW", str(binary)]).stdout
    syms = []

    for line in rel.splitlines():
        m = RELOC_SYM_RE.search(line)
        if m:
            syms.append(normalize(m.group(1)))

    return {
        plt_base + (idx + 1) * 0x10: sym
        for idx, sym in enumerate(syms)
    }


def parse_objdump(binary, plt_map):
    out = cmd(["objdump", "-d", "-M", "intel", str(binary)])
    if out.returncode != 0:
        raise SystemExit(out.stderr.strip() or "objdump failed")

    functions = []
    current = None

    for line in out.stdout.splitlines():
        mf = FUNC_RE.match(line)
        if mf:
            addr, name = mf.groups()
            current = {"name": normalize(name), "addr": int(addr, 16), "calls": []}
            functions.append(current)
            continue

        if current is None:
            continue

        mc = CALL_RE.match(line)
        if not mc:
            continue

        call_addr, _op, numeric_target, named_target = mc.groups()

        target_name = normalize(named_target) if named_target else None

        if not target_name:
            try:
                target_addr = int(numeric_target, 16)
                target_name = plt_map.get(target_addr)
            except ValueError:
                target_name = None

        if not target_name:
            continue

        current["calls"].append({
            "addr": int(call_addr, 16),
            "target": target_name,
        })

    return functions


def skip_function(f):
    name = f["name"]
    if name in {"_init", "_fini", "_start"}:
        return True
    if name.startswith(".plt") or name.endswith("@plt"):
        return True
    if name.startswith("__libc_"):
        return True
    return False


def analyze(functions):
    results = []

    for f in functions:
        if skip_function(f):
            continue

        score = 0
        hits = []

        for call in f["calls"]:
            c = classify(call["target"])
            if not c:
                continue

            category, matched, color, weight = c
            score += weight
            hits.append({
                "category": category,
                "matched": matched,
                "target": call["target"],
                "addr": call["addr"],
                "score": weight,
                "color": color,
            })

        if hits:
            results.append({
                "function": f["name"],
                "address": f["addr"],
                "score": score,
                "hits": hits,
            })

    return sorted(results, key=lambda r: r["score"], reverse=True)


def print_table(results):
    print(f"{'Score':>5}  {'Function':<24} {'Address':<12}")
    print("-" * 80)

    for r in results:
        print(f"{r['score']:>5}  {r['function']:<24} 0x{r['address']:x}")
        for h in r["hits"]:
            print(f"       0x{h['addr']:x}       {h['category']:<22} {h['target']} (+{h['score']})")
        print()


def write_html(results, binary, output):
    sections = []

    for r in results:
        hit_rows = []
        for h in r["hits"]:
            hit_rows.append(f"""
<tr>
  <td><span class="pill" style="background:{h['color']}">{html.escape(h['category'])}</span></td>
  <td>{html.escape(h['target'])}</td>
  <td><code>0x{h['addr']:x}</code></td>
  <td>+{h['score']}</td>
</tr>
""")

        sections.append(f"""
<section>
<h2>[{r['score']:02d}] {html.escape(r['function'])} <small>0x{r['address']:x}</small></h2>
<table>
<thead><tr><th>Category</th><th>Call</th><th>Address</th><th>Score</th></tr></thead>
<tbody>{''.join(hit_rows)}</tbody>
</table>
</section>
""")

    doc = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>DIWID Report</title>
<style>
body {{ font-family: system-ui, sans-serif; background:#111; color:#eee; margin:2rem; }}
section {{ background:#1b1b1b; border:1px solid #333; border-radius:8px; padding:1rem; margin:1rem 0; }}
table {{ border-collapse:collapse; width:100%; }}
th, td {{ border-bottom:1px solid #333; padding:.45rem; text-align:left; }}
small {{ color:#aaa; }}
code {{ color:#ddd; }}
.pill {{ color:#000; padding:.2rem .45rem; border-radius:.4rem; font-weight:700; }}
</style>
</head>
<body>
<h1>DIWID Report</h1>
<p>Binary: <code>{html.escape(str(binary))}</code></p>
<p>Interesting functions: {len(results)}</p>
{''.join(sections) if sections else '<p>No interesting calls found.</p>'}
</body>
</html>
"""

    Path(output).write_text(doc, encoding="utf-8")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("binary")
    p.add_argument("-o", "--output", default="diwid_report.html")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    need("objdump")
    need("readelf")

    binary = Path(args.binary)
    if not binary.exists():
        raise SystemExit(f"file not found: {binary}")

    plt_map = build_plt_map(binary)
    functions = parse_objdump(binary, plt_map)
    results = analyze(functions)

    if args.debug:
        print("[debug] PLT map:")
        for addr, sym in sorted(plt_map.items()):
            print(f"  0x{addr:x} -> {sym}")
        print(f"[debug] parsed functions: {len(functions)}")
        print(f"[debug] parsed calls: {sum(len(f['calls']) for f in functions)}")
        print()

    print_table(results)
    write_html(results, binary, args.output)
    print(f"[+] wrote {args.output}")


if __name__ == "__main__":
    main()