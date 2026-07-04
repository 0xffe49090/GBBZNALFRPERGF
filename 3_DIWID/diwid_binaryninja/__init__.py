# DIWID
# Discover Interesting, Weird, and Important Data within binaries to help reverse engineers. :)
#
from binaryninja import (
    PluginCommand,
    HighlightColor,
    MediumLevelILOperation,
    SymbolType,
    log_info,
    log_warn,
)

from binaryninja.interaction import show_message_box
PLUGIN_NAME = "DIWID"

'''
    Some custom colors to use for the categories we will define below.

'''
COLORS = {
    "critical": HighlightColor(red=255, green=0,   blue=0),     # Red
    "danger":   HighlightColor(red=255, green=0,   blue=140),   # Hot Pink
    "heap":     HighlightColor(red=255, green=140, blue=0),     # Orange
    "input":    HighlightColor(red=0,   green=170, blue=255),   # Sky Blue
    "output":   HighlightColor(red=0,   green=255, blue=255),   # Cyan
    "file":     HighlightColor(red=255, green=255, blue=0),     # Yellow
    "loader":   HighlightColor(red=160, green=32,  blue=240),   # Purple
    "crypto":   HighlightColor(red=0,   green=220, blue=80),    # Bright Green
    "priv":     HighlightColor(red=160, green=82,  blue=45),    # Brown
    "network":  HighlightColor(red=30,  green=144, blue=255),   # Dodger Blue
}

'''
    This section defines the colors, scoring, and functions to hunt. 
    Feel free to add/adjust and then restart binja.

'''
FUNCTION_CATEGORIES = {
    "command_execution": {
        "color": COLORS['critical'],
        "score": 5,
        "functions": {
            "system", "execve", "execv", "execl", "execlp", "execvp",
            "popen", "CreateProcessA", "CreateProcessW",
            "ShellExecuteA", "ShellExecuteW", "WinExec",
        },
    },

    "memory_unsafe": {
        "color": COLORS['danger'],
        "score": 3,
        "functions": {
            "gets", "strcpy", "strncpy", "strcat", "strncat",
            "sprintf", "vsprintf", "swprintf",
            "memcpy", "memmove", "bcopy",
        },
    },

    "heap": {
        "color": COLORS['heap'],
        "score": 2,
        "functions": {
            "malloc", "calloc", "realloc", "free",
            "operator new", "operator delete",
            "HeapAlloc", "HeapFree",
            "VirtualAlloc", "VirtualFree",
            "mmap", "munmap",
        },
    },

    "input": {
        "color": COLORS['input'],
        "score": 2,
        "functions": {
            "read", "recv", "recvfrom", "recvmsg",
            "fread", "scanf", "fscanf", "sscanf",
            "fgets", "getline", "getchar",
            "socket", "accept",
            "ReadFile",
        },
    },

    "output": {
        "color": COLORS['output'],
        "score": 1,
        "functions": {
            "write", "send", "sendto", "sendmsg",
            "fwrite", "printf", "fprintf",
            "puts", "putchar",
            "WriteFile",
        },
    },

    "filesystem": {
        "color": COLORS['file'],
        "score": 2,
        "functions": {
            "open", "fopen", "close", "fclose",
            "unlink", "rename",
            "CreateFileA", "CreateFileW",
        },
    },

    "dynamic_loading": {
        "color": COLORS['loader'],
        "score": 3,
        "functions": {
            "dlopen", "dlsym",
            "LoadLibraryA", "LoadLibraryW",
            "GetProcAddress",
        },
    },

    "crypto": {
        "color": COLORS['crypto'],
        "score": 1,
        "functions": {
            "AES_encrypt", "AES_decrypt",
            "EVP_EncryptInit", "EVP_DecryptInit",
            "EVP_EncryptUpdate", "EVP_DecryptUpdate",
            "CryptEncrypt", "CryptDecrypt",
            "SHA1", "SHA256", "SHA512",
            "MD5",
        },
    },

    "environment_privilege": {
        "color": COLORS['priv'],
        "score": 2,
        "functions": {
            "getenv", "setenv", "putenv",
            "setuid", "setgid",
            "seteuid", "setegid",
            "geteuid", "getegid",
        },
    },
}


def is_user_function(func):
    '''
    Makes an attempt to skip libc, etc., functions.

    '''
    if not func:
        return False

    # some attempt to find if this is imported or
    # a library
    if func.symbol:
        if func.symbol.type in {
            SymbolType.ImportedFunctionSymbol,
            SymbolType.LibraryFunctionSymbol,
        }:
            return False

    if func.view.get_segment_at(func.start) is None:
        return False

    # some small set of the usual suspects
    bad_prefixes = (
        "j_",
        "__imp_",
        "plt_",
        "sub_plt",
        "_init",
        "_fini",
        "__libc_",
    )

    # ignore bad_prefixes
    if func.name.startswith(bad_prefixes):
        return False

    return True


def normalize_name(name):
    '''
        Little hack to fix up some function naming.

    '''
    if not name:
        return ""

    return (
        name.replace("__imp_", "")
        .replace("j_", "")
        .replace("@plt", "")
        .replace(".plt", "")
        .strip()
    )


def classify_call(name):
    '''
    

    '''
    clean = normalize_name(name)

    for category, meta in FUNCTION_CATEGORIES.items():
        for needle in meta["functions"]:
            if needle == clean or needle in clean:
                return category, meta, needle

    return None, None, None


def resolve_call_name(func, dest):
    """
    Resolves Binja intermediary languages stuff into useful function names.
    --> https://docs.binary.ninja/dev/bnil-mlil.html

    """
    try:
        if not hasattr(dest, "constant"):
            return None

        addr = dest.constant
        bv = func.view

        # symbol address, get name
        sym = bv.get_symbol_at(addr)
        if sym:
            return sym.name
        
        # get function, name
        target = bv.get_function_at(addr)
        if target:
            return target.name

    # ehh, u fail
    except Exception as e:
        log_warn(f"[-] {PLUGIN_NAME}: failed resolving call in {func.name}: {e}")

    return None


def score_function(func):
    '''
        Some attempt to score functions.

    '''
    score = 0
    reasons = []

    if not func.mlil:
        return score, reasons

    for block in func.mlil.basic_blocks:
        for insn in block:
            if insn.operation != MediumLevelILOperation.MLIL_CALL:
                continue

            name = resolve_call_name(func, insn.dest)
            if not name:
                continue

            category, meta, matched = classify_call(name)
            if not meta:
                continue

            score += meta["score"]

            reason = {
                "category": category,
                "call": name,
                "matched": matched,
                "address": insn.address,
                "score": meta["score"],
            }

            # tack it on so we can report it
            reasons.append(reason)

            # set the function to the defined color we set
            func.set_auto_instr_highlight(
                insn.address,
                meta["color"],
            )

    return score, reasons


def run(bv):
    '''
        Do the main thing.

    '''
    log_info("-"*64)
    log_info(f"{PLUGIN_NAME}: Loaded! Discover Interesting, Weird, and Important Data.")
    log_info("-"*64)

    # list to hold results
    results = []

    for func in bv.functions:
        # skip lib functions, etc.
        if not is_user_function(func):
            continue
        
        score, reasons = score_function(func)

        # algorithm caught something, so let's note it
        if score > 0:
            results.append((score, func, reasons))

    # sadness! nothing found
    if not results:
        show_message_box(PLUGIN_NAME, "No interesting calls found. :(")
        log_info(f"[-] {PLUGIN_NAME}: Sad panda! No interesting calls found.")
        return

    # sort the results
    results.sort(key=lambda x: x[0], reverse=True)

    # log identified functions
    for score, func, reasons in results:
        log_info("")
        log_info(f"[{score:02d}] {func.name} @ {hex(func.start)}")

        # record reasons, calls, addresses for log output
        seen = set()
        for r in reasons:
            key = (r["category"], r["call"], r["address"])
            if key in seen:
                continue
            seen.add(key)

            log_info(
                f"     {r['category']:<15} "
                f"{r['call']:<15} "
                f"@ {hex(r['address'])} "
                f"(+{r['score']})"
            )

    # little dialog doodad to appease some
    show_message_box(
        PLUGIN_NAME,
        f"found {len(results)} interesting functions.\n"
    )

    # TO THE LOG I SAY!
    log_info(f"{PLUGIN_NAME} found {len(results)} interesting functions.\n")


# not really used, mostly here for my debugging
def sanitycheck():
    #log_info()
    #show_message_box(PLUGIN_NAME, "DIWID loaded.")
    #log_info(f"[+] {PLUGIN_NAME}: started.")
    log_info(' ')


# required stuff to make the plugin do its thing
PluginCommand.register(
    "Diwid\\Analyze Functions",
    "Discover Interesting, Weird, and Important Data.",
    run,
)