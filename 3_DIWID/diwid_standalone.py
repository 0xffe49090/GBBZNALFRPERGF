#!/usr/bin/env python3
"""
DIWID Standalone (radare2 edition)

Discover Interesting, Weird, and Important Data in Linux ELF binaries.

Requirements:
    radare2
    Python 3.10+
    r2pipe

Install r2pipe:
    python3 -m pip install --user r2pipe

Usage:
    python3 diwid_r2.py ./binary
    python3 diwid_r2.py ./binary -o report.html --json report.json
    python3 diwid_r2.py ./binary --debug

Notes:
- Linux ELF binaries only.
- radare2 performs function discovery and structured instruction analysis.
- Imported API classification uses exact normalized symbol matching.
- "_system", "my_system", and similar names do not match "system".
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


VERSION = "0.3.0"

CATEGORY_INFO: dict[str, dict[str, Any]] = {
    "command_execution": {
        "label": "Command Execution",
        "color": "#ff4d4d",
        "score": 5,
        "functions": {
            "system",
            "popen",
            "execve",
            "execv",
            "execvp",
            "execvpe",
            "execl",
            "execlp",
            "execle",
            "posix_spawn",
            "posix_spawnp",
        },
    },
    "memory_unsafe": {
        "label": "Memory Unsafe",
        "color": "#ff4fa3",
        "score": 3,
        "functions": {
            "gets",
            "strcpy",
            "strncpy",
            "strcat",
            "strncat",
            "sprintf",
            "vsprintf",
            "swprintf",
            "vswprintf",
            "memcpy",
            "memmove",
            "bcopy",
        },
    },
    "heap": {
        "label": "Heap / Memory",
        "color": "#ff9f43",
        "score": 2,
        "functions": {
            "malloc",
            "calloc",
            "realloc",
            "reallocarray",
            "free",
            "aligned_alloc",
            "posix_memalign",
            "mmap",
            "mmap64",
            "munmap",
            "mprotect",
        },
    },
    "input": {
        "label": "Input",
        "color": "#4db8ff",
        "score": 2,
        "functions": {
            "read",
            "pread",
            "pread64",
            "readv",
            "recv",
            "recvfrom",
            "recvmsg",
            "recvmmsg",
            "fread",
            "fgets",
            "getline",
            "getdelim",
            "getchar",
            "scanf",
            "fscanf",
            "sscanf",
            "__isoc99_scanf",
            "__isoc99_fscanf",
            "__isoc99_sscanf",
            "accept",
            "accept4",
        },
    },
    "output": {
        "label": "Output",
        "color": "#50e3e6",
        "score": 1,
        "functions": {
            "write",
            "pwrite",
            "pwrite64",
            "writev",
            "send",
            "sendto",
            "sendmsg",
            "sendmmsg",
            "fwrite",
            "printf",
            "fprintf",
            "dprintf",
            "sprintf",
            "snprintf",
            "vprintf",
            "vfprintf",
            "vsnprintf",
            "puts",
            "putchar",
            "perror",
        },
    },
    "filesystem": {
        "label": "Filesystem",
        "color": "#ffe66d",
        "score": 2,
        "functions": {
            "open",
            "open64",
            "openat",
            "openat64",
            "creat",
            "fopen",
            "fopen64",
            "fdopen",
            "freopen",
            "close",
            "fclose",
            "unlink",
            "unlinkat",
            "remove",
            "rename",
            "renameat",
            "renameat2",
            "chmod",
            "fchmod",
            "chown",
            "fchown",
            "stat",
            "lstat",
            "fstat",
            "access",
            "realpath",
            "readlink",
            "readlinkat",
            "mkdir",
            "rmdir",
        },
    },
    "dynamic_loading": {
        "label": "Dynamic Loading",
        "color": "#b56cff",
        "score": 3,
        "functions": {
            "dlopen",
            "dlmopen",
            "dlsym",
            "dlvsym",
            "dlclose",
        },
    },
    "crypto": {
        "label": "Cryptography",
        "color": "#68e168",
        "score": 1,
        "functions": {
            "AES_encrypt",
            "AES_decrypt",
            "DES_encrypt1",
            "DES_decrypt3",
            "EVP_EncryptInit",
            "EVP_EncryptInit_ex",
            "EVP_EncryptUpdate",
            "EVP_EncryptFinal",
            "EVP_EncryptFinal_ex",
            "EVP_DecryptInit",
            "EVP_DecryptInit_ex",
            "EVP_DecryptUpdate",
            "EVP_DecryptFinal",
            "EVP_DecryptFinal_ex",
            "EVP_DigestInit",
            "EVP_DigestInit_ex",
            "EVP_DigestUpdate",
            "EVP_DigestFinal",
            "EVP_DigestFinal_ex",
            "SHA1",
            "SHA224",
            "SHA256",
            "SHA384",
            "SHA512",
            "MD5",
            "RAND_bytes",
        },
    },
    "environment_privilege": {
        "label": "Environment / Privilege",
        "color": "#c98b5f",
        "score": 2,
        "functions": {
            "getenv",
            "secure_getenv",
            "setenv",
            "unsetenv",
            "putenv",
            "setuid",
            "setgid",
            "seteuid",
            "setegid",
            "setreuid",
            "setregid",
            "setresuid",
            "setresgid",
            "geteuid",
            "getegid",
            "getuid",
            "getgid",
            "setcap",
            "cap_set_proc",
            "chroot",
            "setns",
            "unshare",
        },
    },
    "network": {
        "label": "Network",
        "color": "#5b8cff",
        "score": 2,
        "functions": {
            "socket",
            "socketpair",
            "connect",
            "bind",
            "listen",
            "shutdown",
            "getaddrinfo",
            "gethostbyname",
            "gethostbyaddr",
            "inet_aton",
            "inet_pton",
            "inet_ntoa",
            "inet_ntop",
        },
    },
}

SKIP_EXACT = {
    "_init",
    "_fini",
    "_start",
    "entry0",
    "frame_dummy",
    "register_tm_clones",
    "deregister_tm_clones",
    "__do_global_dtors_aux",
}

R2_PREFIXES = (
    "sym.imp.",
    "sym.",
    "imp.",
    "reloc.",
)

CALL_TYPES = {
    "call",
    "ucall",
    "rcall",
    "icall",
    "ccall",
}


@dataclass
class CallHit:
    address: int
    target: str
    raw_target: str
    category: str
    category_label: str
    score: int
    color: str
    opcode: str


@dataclass
class FunctionResult:
    name: str
    raw_name: str
    address: int
    size: int
    score: int
    hits: list[CallHit]
    unresolved_calls: int


def eprint(*args: object, **kwargs: object) -> None:
    print(*args, file=sys.stderr, **kwargs)


def require_dependencies() -> Any:
    if shutil.which("radare2") is None and shutil.which("r2") is None:
        raise SystemExit(
            "radare2 was not found in PATH.\n"
            "Install radare2, then run this tool again."
        )

    try:
        import r2pipe  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "Python package 'r2pipe' is not installed.\n"
            "Install it with:\n"
            "  python3 -m pip install --user r2pipe"
        ) from exc

    return r2pipe


def verify_elf(path: Path) -> None:
    try:
        magic = path.read_bytes()[:4]
    except OSError as exc:
        raise SystemExit(f"Unable to read {path}: {exc}") from exc

    if magic != b"\x7fELF":
        raise SystemExit(f"{path} is not an ELF binary.")


def normalize_symbol(name: Optional[str]) -> str:
    """
    Normalize wrappers added by radare2 and ELF symbol versioning.

    Deliberately uses exact matching after normalization:
      sym.imp.system       -> system
      system@@GLIBC_2.2.5  -> system
      system+0x10          -> system
      _system+0x10         -> _system  (does NOT match system)
      my_system            -> my_system (does NOT match system)
    """
    if not name:
        return ""

    value = str(name).strip()

    changed = True
    while changed:
        changed = False
        for prefix in R2_PREFIXES:
            if value.startswith(prefix):
                value = value[len(prefix):]
                changed = True

    value = value.split("@@", 1)[0]
    value = value.split("@", 1)[0]
    value = re.sub(r"\+0x[0-9a-fA-F]+$", "", value)

    return value.strip()


def classify_symbol(symbol: str) -> Optional[tuple[str, str, int, str]]:
    clean = normalize_symbol(symbol)
    if not clean:
        return None

    for category, info in CATEGORY_INFO.items():
        # Exact set membership is intentional. Never use substring matching.
        if clean in info["functions"]:
            return category, str(info["label"]), int(info["score"]), str(info["color"])

    return None


def first_int(mapping: dict[str, Any], keys: Iterable[str]) -> Optional[int]:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, int):
            return value
    return None


def first_text(mapping: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def build_address_name_map(
    functions: list[dict[str, Any]],
    imports: list[dict[str, Any]],
    symbols: list[dict[str, Any]],
    flags: list[dict[str, Any]],
) -> dict[int, str]:
    address_names: dict[int, str] = {}

    for item in imports + symbols + flags + functions:
        address = first_int(
            item,
            (
                "plt",
                "vaddr",
                "offset",
                "paddr",
            ),
        )
        name = first_text(
            item,
            (
                "name",
                "realname",
                "demname",
                "flagname",
            ),
        )

        if address is not None and name:
            # Prefer imported/flag names when multiple records share an address.
            existing = address_names.get(address, "")
            if not existing or "imp." in name or "@plt" in name:
                address_names[address] = name

    return address_names


def parse_symbol_from_opcode(opcode: str) -> str:
    """
    Conservative opcode fallback.

    Accepted examples:
      call sym.imp.system
      callq sym.imp.strcpy
      call 0x401030 <sym.imp.puts>

    Numeric-only targets are not classified here.
    """
    if not opcode:
        return ""

    angle = re.search(r"<([^>]+)>", opcode)
    if angle:
        return angle.group(1).strip()

    match = re.match(
        r"^\s*(?:call|callq)\s+([A-Za-z_.$][A-Za-z0-9_.$@+\-]*)",
        opcode,
    )
    if not match:
        return ""

    return match.group(1)


def resolve_flag_at(r2: Any, address: int) -> str:
    """
    Ask radare2 for the flag/symbol at an address.

    This is intentionally a fallback because different radare2 releases expose
    import/PLT addresses differently in iij/isj/fj JSON.
    """
    try:
        raw = (r2.cmd(f"fd @ {address}") or "").strip()
    except Exception:
        return ""

    if not raw:
        return ""

    # fd can occasionally return multiple lines; the first exact flag is best.
    return raw.splitlines()[0].strip()


def resolve_call_target(
    r2: Any,
    op: dict[str, Any],
    address_names: dict[int, str],
) -> tuple[str, str]:
    """
    Return (normalized target, raw target).

    Resolution order:
      1. jump/pointer target from the prebuilt address map
      2. radare2's live flag lookup (`fd @ address`)
      3. symbol rendered in opcode/disassembly text
    """
    for key in ("jump", "ptr"):
        address = op.get(key)
        if isinstance(address, int):
            raw = address_names.get(address, "")
            if not raw:
                raw = resolve_flag_at(r2, address)
                if raw:
                    address_names[address] = raw

            if raw:
                return normalize_symbol(raw), raw

    opcode = first_text(op, ("opcode", "disasm"))
    raw = parse_symbol_from_opcode(opcode)
    if raw:
        return normalize_symbol(raw), raw

    return "", ""


def should_skip_function(raw_name: str, normalized_name: str) -> bool:
    if raw_name in SKIP_EXACT or normalized_name in SKIP_EXACT:
        return True

    if raw_name.startswith(("sym.imp.", "imp.", "reloc.")):
        return True

    if normalized_name.startswith("__libc_"):
        return True

    if ".plt" in raw_name or raw_name.endswith("@plt"):
        return True

    return False


def get_function_ops(r2: Any, address: int) -> list[dict[str, Any]]:
    data = r2.cmdj(f"pdfj @ {address}") or {}
    if not isinstance(data, dict):
        return []

    ops = data.get("ops") or []
    if not isinstance(ops, list):
        return []

    return [op for op in ops if isinstance(op, dict)]


def get_xrefs_to(r2: Any, target: int | str) -> list[dict[str, Any]]:
    """
    Return cross-references to an address or flag.

    This approach is more robust than trying to infer call targets from pdfj
    operation fields, which differ across radare2 versions.
    """
    try:
        data = r2.cmdj(f"axtj @ {target}") or []
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def function_for_address(r2: Any, address: int) -> Optional[dict[str, Any]]:
    try:
        data = r2.cmdj(f"afij @ {address}") or []
    except Exception:
        return None

    if isinstance(data, list) and data and isinstance(data[0], dict):
        return data[0]

    if isinstance(data, dict):
        return data

    return None


def collect_import_targets(
    imports: list[dict[str, Any]],
    flags: list[dict[str, Any]],
) -> list[tuple[str, int | str]]:
    """
    Build (normalized_symbol, target) pairs.

    Prefer concrete PLT/import addresses. Fall back to radare2 flag names such
    as sym.imp.strcpy when an address is unavailable.
    """
    targets: dict[tuple[str, str], tuple[str, int | str]] = {}

    for item in imports:
        raw_name = first_text(item, ("name", "realname", "demname"))
        name = normalize_symbol(raw_name)
        if not name:
            continue

        address = first_int(item, ("plt", "vaddr", "offset", "paddr"))
        target: int | str = address if address is not None else f"sym.imp.{name}"
        targets[(name, str(target))] = (name, target)

    for item in flags:
        raw_name = first_text(item, ("name", "realname"))
        if not raw_name.startswith(("sym.imp.", "imp.", "reloc.")):
            continue

        name = normalize_symbol(raw_name)
        if not name:
            continue

        address = first_int(item, ("offset", "vaddr", "paddr"))
        target = address if address is not None else raw_name
        targets[(name, str(target))] = (name, target)

    return list(targets.values())


def analyze_binary(
    binary: Path,
    r2pipe_module: Any,
    debug: bool = False,
) -> tuple[list[FunctionResult], dict[str, Any]]:
    """
    Analyze imported APIs by asking radare2 for xrefs to each import/PLT entry.

    This avoids relying on version-specific pdfj call-operation fields.
    """
    r2 = r2pipe_module.open(str(binary), flags=["-2"])

    try:
        r2.cmd("e scr.color=0")
        r2.cmd("e anal.hasnext=true")
        r2.cmd("aaa")

        core_info = r2.cmdj("ij") or {}
        functions = r2.cmdj("aflj") or []
        imports = r2.cmdj("iij") or []
        flags = r2.cmdj("fj") or []

        if not isinstance(functions, list):
            functions = []
        if not isinstance(imports, list):
            imports = []
        if not isinstance(flags, list):
            flags = []

        functions = [x for x in functions if isinstance(x, dict)]
        imports = [x for x in imports if isinstance(x, dict)]
        flags = [x for x in flags if isinstance(x, dict)]

        import_targets = collect_import_targets(imports, flags)

        grouped: dict[int, FunctionResult] = {}
        total_xrefs = 0
        classified_xrefs = 0
        imports_considered = 0

        for symbol, target in import_targets:
            classification = classify_symbol(symbol)
            if classification is None:
                continue

            imports_considered += 1
            category, label, score, color = classification

            xrefs = get_xrefs_to(r2, target)

            # Some r2 builds know the flag but not the numeric target (or vice
            # versa), so try the canonical import flag as a fallback.
            if not xrefs:
                xrefs = get_xrefs_to(r2, f"sym.imp.{symbol}")

            for xref in xrefs:
                callsite = first_int(xref, ("from", "addr", "offset"))
                if callsite is None:
                    continue

                xref_type = str(xref.get("type") or "").lower()
                # Keep code/call xrefs; reject obvious data-only references.
                if xref_type and xref_type not in {
                    "call",
                    "code",
                    "c",
                    "j",
                    "jump",
                }:
                    continue

                total_xrefs += 1
                function = function_for_address(r2, callsite)
                if not function:
                    continue

                function_address = first_int(
                    function, ("offset", "addr", "vaddr", "paddr")
                )
                if function_address is None:
                    continue

                raw_name = first_text(function, ("name", "realname", "demname"))
                if not raw_name:
                    raw_name = f"fcn.{function_address:x}"

                name = normalize_symbol(raw_name) or f"sub_{function_address:x}"
                if should_skip_function(raw_name, name):
                    continue

                size = first_int(function, ("size", "realsz")) or 0
                opcode = (r2.cmd(f"pd 1 @ {callsite}") or "").strip()

                if function_address not in grouped:
                    grouped[function_address] = FunctionResult(
                        name=name,
                        raw_name=raw_name,
                        address=function_address,
                        size=size,
                        score=0,
                        hits=[],
                        unresolved_calls=0,
                    )

                hit = CallHit(
                    address=callsite,
                    target=symbol,
                    raw_target=str(target),
                    category=category,
                    category_label=label,
                    score=score,
                    color=color,
                    opcode=opcode,
                )

                # Avoid duplicate hits when both numeric and flag-based xref
                # lookups return the same call site.
                existing = grouped[function_address].hits
                if any(
                    old.address == hit.address
                    and old.target == hit.target
                    and old.category == hit.category
                    for old in existing
                ):
                    continue

                grouped[function_address].hits.append(hit)
                grouped[function_address].score += score
                classified_xrefs += 1

        results = sorted(
            grouped.values(),
            key=lambda item: (-item.score, item.address),
        )

        metadata = {
            "version": VERSION,
            "binary": str(binary.resolve()),
            "radare_info": core_info,
            "discovered_functions": len(functions),
            "address_map_entries": len(import_targets),
            "total_calls": total_xrefs,
            "resolved_calls": total_xrefs,
            "classified_calls": classified_xrefs,
            "interesting_functions": len(results),
        }

        if debug:
            eprint(f"[debug] discovered functions : {len(functions)}")
            eprint(f"[debug] imports              : {len(imports)}")
            eprint(f"[debug] flags                : {len(flags)}")
            eprint(f"[debug] import targets       : {len(import_targets)}")
            eprint(f"[debug] classified imports  : {imports_considered}")
            eprint(f"[debug] matching xrefs       : {total_xrefs}")
            eprint(f"[debug] classified callsites : {classified_xrefs}")
            eprint(f"[debug] interesting functions: {len(results)}")

            if classified_xrefs == 0:
                eprint("[debug] First import targets and xref counts:")
                for symbol, target in import_targets[:20]:
                    classification = classify_symbol(symbol)
                    marker = "classified" if classification else "ignored"
                    count = len(get_xrefs_to(r2, target))
                    if count == 0:
                        count = len(get_xrefs_to(r2, f"sym.imp.{symbol}"))
                    eprint(
                        f"[debug]   {symbol:<24} target={target!s:<18} "
                        f"xrefs={count:<3} {marker}"
                    )

        return results, metadata

    finally:
        try:
            r2.quit()
        except Exception:
            pass

def format_address(address: int) -> str:
    return f"0x{address:x}"


def print_console(results: list[FunctionResult], metadata: dict[str, Any]) -> None:
    print(f"DIWID Standalone {VERSION}")
    print(f"Binary: {metadata['binary']}")
    print(
        f"Functions: {metadata['discovered_functions']} discovered, "
        f"{metadata['interesting_functions']} interesting"
    )
    print(
        f"Calls: {metadata['resolved_calls']}/{metadata['total_calls']} resolved, "
        f"{metadata['classified_calls']} classified"
    )
    print()

    if not results:
        print("No interesting API calls were identified.")
        return

    print(f"{'Score':>5}  {'Address':<14}  {'Function':<32}  Findings")
    print("-" * 105)

    for result in results:
        print(
            f"{result.score:>5}  "
            f"{format_address(result.address):<14}  "
            f"{result.name:<32}  "
            f"{len(result.hits)}"
        )

        for hit in result.hits:
            print(
                f"       {format_address(hit.address):<14}  "
                f"{hit.category:<24} "
                f"{hit.target} (+{hit.score})"
            )
        print()


def metadata_summary(metadata: dict[str, Any]) -> dict[str, str]:
    core = metadata.get("radare_info")
    if not isinstance(core, dict):
        return {}

    bin_info = core.get("bin")
    if not isinstance(bin_info, dict):
        return {}

    wanted = {
        "format": bin_info.get("format"),
        "architecture": bin_info.get("arch"),
        "bits": bin_info.get("bits"),
        "endianness": bin_info.get("endian"),
        "operating_system": bin_info.get("os"),
        "machine": bin_info.get("machine"),
        "language": bin_info.get("lang"),
    }

    return {
        key: str(value)
        for key, value in wanted.items()
        if value not in (None, "")
    }


def write_json(
    results: list[FunctionResult],
    metadata: dict[str, Any],
    output: Path,
) -> None:
    payload = {
        "metadata": metadata,
        "results": [asdict(result) for result in results],
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_html(
    results: list[FunctionResult],
    metadata: dict[str, Any],
    output: Path,
) -> None:
    summary = metadata_summary(metadata)

    metadata_cards = "".join(
        f"""
        <div class="metric">
          <span class="metric-label">{html.escape(key.replace("_", " ").title())}</span>
          <strong>{html.escape(value)}</strong>
        </div>
        """
        for key, value in summary.items()
    )

    category_legend = "".join(
        f"""
        <span class="legend-item">
          <span class="legend-dot" style="background:{info['color']}"></span>
          {html.escape(str(info['label']))} (+{int(info['score'])})
        </span>
        """
        for info in CATEGORY_INFO.values()
    )

    sections: list[str] = []
    for result in results:
        rows: list[str] = []

        for hit in result.hits:
            rows.append(
                f"""
                <tr>
                  <td>
                    <span class="pill" style="--pill-color:{html.escape(hit.color)}">
                      {html.escape(hit.category_label)}
                    </span>
                  </td>
                  <td><code>{html.escape(hit.target)}</code></td>
                  <td><code>{html.escape(format_address(hit.address))}</code></td>
                  <td class="score-cell">+{hit.score}</td>
                  <td><code class="opcode">{html.escape(hit.opcode)}</code></td>
                </tr>
                """
            )

        sections.append(
            f"""
            <section class="function-card" data-score="{result.score}">
              <header class="function-header">
                <div>
                  <h2>{html.escape(result.name)}</h2>
                  <div class="function-meta">
                    <code>{html.escape(format_address(result.address))}</code>
                    <span>{result.size} bytes</span>
                    <span>{len(result.hits)} classified call(s)</span>
                  </div>
                </div>
                <div class="function-score">{result.score}</div>
              </header>

              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Category</th>
                      <th>Target</th>
                      <th>Call Site</th>
                      <th>Score</th>
                      <th>Instruction</th>
                    </tr>
                  </thead>
                  <tbody>
                    {''.join(rows)}
                  </tbody>
                </table>
              </div>
            </section>
            """
        )

    empty_state = """
        <section class="empty">
          <h2>No interesting API calls identified</h2>
          <p>
            DIWID analyzed the discovered functions but did not classify any
            resolved calls using the current ruleset.
          </p>
        </section>
    """

    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DIWID Report</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #0d1117;
      --panel: #161b22;
      --panel-2: #1c2128;
      --border: #30363d;
      --text: #e6edf3;
      --muted: #8b949e;
      --accent: #58a6ff;
    }}

    * {{ box-sizing: border-box; }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      line-height: 1.45;
    }}

    main {{
      width: min(1400px, calc(100% - 32px));
      margin: 32px auto 64px;
    }}

    .hero {{
      background:
        radial-gradient(circle at top right, rgba(88,166,255,.14), transparent 34%),
        var(--panel);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 20px;
    }}

    h1, h2, p {{ margin-top: 0; }}

    h1 {{
      margin-bottom: 6px;
      font-size: 30px;
      letter-spacing: -.03em;
    }}

    .subtitle {{
      color: var(--muted);
      margin-bottom: 18px;
      overflow-wrap: anywhere;
    }}

    code {{
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
    }}

    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin-top: 16px;
    }}

    .metric {{
      background: rgba(255,255,255,.025);
      border: 1px solid var(--border);
      border-radius: 9px;
      padding: 10px 12px;
    }}

    .metric-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .06em;
    }}

    .metric strong {{
      display: block;
      margin-top: 3px;
      font-size: 17px;
    }}

    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      margin-top: 18px;
      color: var(--muted);
      font-size: 13px;
    }}

    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}

    .legend-dot {{
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }}

    .function-card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin: 14px 0;
      overflow: hidden;
    }}

    .function-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 17px 19px;
      background: var(--panel-2);
      border-bottom: 1px solid var(--border);
    }}

    .function-header h2 {{
      margin-bottom: 5px;
      font-size: 19px;
    }}

    .function-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px 14px;
      color: var(--muted);
      font-size: 13px;
    }}

    .function-score {{
      display: grid;
      place-items: center;
      flex: 0 0 auto;
      width: 52px;
      height: 52px;
      border-radius: 50%;
      border: 2px solid var(--accent);
      color: var(--accent);
      font-size: 19px;
      font-weight: 800;
    }}

    .table-wrap {{
      overflow-x: auto;
    }}

    table {{
      border-collapse: collapse;
      width: 100%;
      min-width: 850px;
    }}

    th, td {{
      padding: 11px 13px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }}

    tr:last-child td {{
      border-bottom: 0;
    }}

    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .055em;
    }}

    tbody tr:hover {{
      background: rgba(255,255,255,.025);
    }}

    .pill {{
      display: inline-block;
      min-width: 126px;
      padding: 4px 8px;
      border: 1px solid color-mix(in srgb, var(--pill-color), white 12%);
      border-radius: 999px;
      background: color-mix(in srgb, var(--pill-color), transparent 78%);
      color: color-mix(in srgb, var(--pill-color), white 32%);
      font-size: 12px;
      font-weight: 750;
      text-align: center;
    }}

    .score-cell {{
      font-weight: 800;
    }}

    .opcode {{
      color: #c9d1d9;
      white-space: nowrap;
    }}

    .empty {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 24px;
      color: var(--muted);
    }}

    .footer {{
      margin-top: 22px;
      color: var(--muted);
      font-size: 12px;
      text-align: center;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>DIWID Standalone Report</h1>
      <p class="subtitle">
        Binary: <code>{html.escape(str(metadata['binary']))}</code>
      </p>

      <div class="metrics">
        <div class="metric">
          <span class="metric-label">Functions Discovered</span>
          <strong>{metadata['discovered_functions']}</strong>
        </div>
        <div class="metric">
          <span class="metric-label">Interesting Functions</span>
          <strong>{metadata['interesting_functions']}</strong>
        </div>
        <div class="metric">
          <span class="metric-label">Calls Resolved</span>
          <strong>{metadata['resolved_calls']} / {metadata['total_calls']}</strong>
        </div>
        <div class="metric">
          <span class="metric-label">Calls Classified</span>
          <strong>{metadata['classified_calls']}</strong>
        </div>
        {metadata_cards}
      </div>

      <div class="legend">
        {category_legend}
      </div>
    </section>

    {''.join(sections) if sections else empty_state}

    <div class="footer">
      Generated by DIWID Standalone {VERSION}
    </div>
  </main>
</body>
</html>
"""

    output.write_text(document, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Use radare2 analysis to score interesting functions in a Linux ELF binary."
        )
    )
    parser.add_argument("binary", type=Path, help="Linux ELF binary to analyze")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("diwid_report.html"),
        help="HTML report path (default: diwid_report.html)",
    )
    parser.add_argument(
        "--json",
        dest="json_output",
        type=Path,
        help="Optional JSON report path",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print analysis counters and troubleshooting details",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    binary = args.binary.expanduser()
    if not binary.is_file():
        eprint(f"File not found: {binary}")
        return 2

    verify_elf(binary)
    r2pipe_module = require_dependencies()

    try:
        results, metadata = analyze_binary(
            binary=binary,
            r2pipe_module=r2pipe_module,
            debug=args.debug,
        )
    except KeyboardInterrupt:
        eprint("\nAnalysis interrupted.")
        return 130
    except Exception as exc:
        eprint(f"Analysis failed: {exc}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

    print_console(results, metadata)

    try:
        write_html(results, metadata, args.output)
        print(f"[+] HTML report: {args.output.resolve()}")

        if args.json_output:
            write_json(results, metadata, args.json_output)
            print(f"[+] JSON report: {args.json_output.resolve()}")
    except OSError as exc:
        eprint(f"Unable to write report: {exc}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
