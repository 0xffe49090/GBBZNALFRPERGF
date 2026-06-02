'''
    This is an experimental UI. I fed fluppy to AI, and gave it the prompt
    to give me a status window. YMMV!

    Claude also deleted all of my comments.. and probably did other stuff.
    
'''
import asyncio
import re
import time
import argparse
import sys
import platform
import os
import json
from pathlib import Path
from collections import deque, Counter, defaultdict

try:
    import yaml
except Exception:
    print("[!] Missing PyYAML. Install yaml --> `pip install PyYAML`.")
    if platform.system() == "Darwin":
        print("""
-- OSX NOTE --
Use a virtual environment:
    python3 -m venv venv
    source venv/bin/activate
    python3 -m pip install PyYAML rich

Then run:
    python3 fluppy.py
""")
    sys.exit(1)

try:
    from rich.console import Console
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from collections import deque
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except Exception:
    print("[!] Missing rich. Install it --> `pip install rich`.")
    sys.exit(1)


console = Console()

SEV_STYLE = {
    "critical": "bold magenta",
    "high": "bold red",
    "medium": "bold yellow",
    "low": "green",
    "info": "blue",
    "r": "red",
    "g": "green",
    "b": "blue",
    "c": "cyan",
    "m": "magenta",
    "y": "yellow",
    "k": "dim",
    "": "",
}


def pp(x, color="", strext=""):
    style = SEV_STYLE.get(str(color).lower(), "")
    console.print(f"{x} {strext}", style=style)

class FluppyUI:
    def __init__(self, max_events=25):
        self.rows = {}
        self.events = deque(maxlen=max_events)
        self.live = None

    def dashboard(self):
        table = Table(expand=True)
        table.add_column("Severity")
        table.add_column("Rule")
        table.add_column("File")
        table.add_column("Hits", justify="right")
        table.add_column("Threshold", justify="right")
        table.add_column("Window", justify="right")

        for (severity, name, file), data in sorted(self.rows.items()):
            style = SEV_STYLE.get(str(severity).lower(), "")
            table.add_row(
                str(severity).upper(),
                str(name),
                str(file),
                str(data["hits"]),
                str(data["threshold"]),
                str(data["window"]),
                style=style,
            )

        return Panel(table, title="🐶 fluppy status", border_style="cyan")

    def output(self):
        text = Text()
        for msg, style in self.events:
            text.append(str(msg) + "\n", style=style)
        return Panel(text, title="output", border_style="dim")

    def render(self):
        layout = Layout()
        layout.split_column(
            Layout(self.dashboard(), name="dashboard", size=10),
            Layout(self.output(), name="output"),
        )
        return layout

    def refresh(self):
        if self.live:
            self.live.update(self.render())

    def update_rule(self, severity, name, file, hits, threshold, window):
        self.rows[(severity, name, file)] = {
            "hits": hits,
            "threshold": threshold,
            "window": window,
        }
        self.refresh()

    def print(self, msg, style=""):
        self.events.append((msg, style))
        self.refresh()


def writeJsonLog(event, logfile="results.json"):
    with open(logfile, "a") as f:
        f.write(json.dumps(event) + "\n")


async def watch(path: str, rules: list, outputlogfile, ui, mode="tail", verbose=False):
    if path == outputlogfile:
        ui.print(f"[!] Cyclical read. Cannot monitor {path} as the output file. Ignoring that.", "red")
        return

    compiled = [
        (
            r["name"],
            re.compile(r["regex"], re.IGNORECASE),
            r["threshold"],
            r["window"],
            r["severity"],
            r.get("cooldown", 60),
            r.get("redact", False),
            defaultdict(deque),
            {},
        )
        for r in rules
    ]

    summary = defaultdict(Counter)

    with open(path, errors="ignore") as f:
        if mode == "tail":
            f.seek(0, 2)

        while True:
            line = f.readline()

            if not line:
                if mode == "scan":
                    break
                await asyncio.sleep(0.1)
                continue

            now = time.monotonic()

            for name, rx, threshold, window, severity, cooldown, redact, hitmap, last_alert in compiled:
                m = rx.search(line)
                if not m:
                    continue

                match = m.group(1) if m.lastindex else m.group(0)
                hitval = " ".join(line.strip().split()) if verbose else match

                if redact:
                    hitval = "--REDACTED--"

                file_name = Path(path).name

                if mode == "scan":
                    summary[(severity, name, file_name, threshold, window)][hitval] += 1
                    continue

                hits = hitmap[match]
                hits.append(now)

                while hits and hits[0] < now - window:
                    hits.popleft()

                ui.update_rule(
                    severity=severity,
                    name=name,
                    file=file_name,
                    hits=len(hits),
                    threshold=threshold,
                    window=window,
                )

                if len(hits) >= threshold:
                    alert_key = f"{name}:{match}"
                    last = last_alert.get(alert_key, 0)

                    if now - last >= cooldown:
                        event = (
                            f"[{severity.upper()}] {name} in {file_name}: "
                            f"threshold {threshold} hit in {window} seconds."
                        )

                        ui.print(event, SEV_STYLE.get(str(severity).lower(), ""))
                        ui.print(f"  {hitval}", "dim")

                        logevent = {
                            "event_id": time.time(),
                            "mode": mode,
                            "severity": severity,
                            "rule": name,
                            "source": file_name,
                            "alert": event,
                            "match": hitval,
                            "threshold": threshold,
                            "window": window,
                        }

                        writeJsonLog(logevent, outputlogfile)
                        last_alert[alert_key] = now

                    hits.clear()

        if mode == "scan":
            now = time.time()

            for (severity, name, file_name, threshold, window), counts in summary.items():
                total = sum(counts.values())

                if total < threshold:
                    continue

                event = (
                    f"[{severity.upper()}] {name} in {file_name}: "
                    f"{total} total hits; threshold {threshold}"
                )

                ui.update_rule(severity, name, file_name, total, threshold, window)
                ui.print(event, SEV_STYLE.get(str(severity).lower(), ""))

                stack = []

                for value, count in counts.most_common(10):
                    ui.print(f"  {value} [{count}]", "dim")
                    stack.append(f"{value} [{count}/{total}]")

                if stack:
                    logevent = {
                        "event_id": now,
                        "mode": mode,
                        "severity": severity,
                        "rule": name,
                        "source": file_name,
                        "alert": event,
                        "match": stack[0],
                        "total": total,
                    }
                    writeJsonLog(logevent, outputlogfile)

                if verbose:
                    for s in stack:
                        logevent = {
                            "event_id": now,
                            "mode": mode,
                            "severity": severity,
                            "rule": name,
                            "source": file_name,
                            "alert": event,
                            "match": s,
                            "total": total,
                        }
                        writeJsonLog(logevent, outputlogfile)


async def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("-c", "--config", default="config.yaml", help="The YAML configuration to read rules from.")
    parser.add_argument("-o", "--output", default="results.json", help="Takes filename, writes JSONL.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show verbose output to CLI.")
    parser.add_argument("-h", "--help", action="store_true", help="This help message.")

    banner = """
 Everybody needs a fluppy dog! Fluppies got tails!

@@@@@@@@ @@@      @@@  @@@ @@@@@@@  @@@@@@@  @@@ @@@
@@!      @@!      @@!  @@@ @@!  @@@ @@!  @@@ @@! !@@
@!!!:!   @!!      @!@  !@! @!@@!@!  @!@@!@!   !@!@!
!!:      !!:      !!:  !!! !!:      !!:        !!:
:        : ::.: :  :.:: :   :        :         .:

 ~~ monitor like your credit rating depends on it ~~
"""

    args = parser.parse_args()

    if args.help:
        pp(banner, "g")
        parser.print_help()
        print()
        sys.exit(0)

    outputlogfile = args.output or "results.json"

    try:
        with open(args.config) as f:
            config = yaml.safe_load(f)
    except Exception:
        pp("[-] No config.yaml found. Ensure that config.yaml is in the same folder as this tool.", "r")
        sys.exit(1)

    sources = config.get("sources", [])

    valid_sources = []

    for s in sources:
        path = s.get("path")

        if not path or not os.path.exists(path):
            pp(f"[-] Log source not found {path}.", "r")
            continue

        if os.path.abspath(path) == os.path.abspath(outputlogfile):
            pp(f"[!] Refusing to watch output file {path}.", "r")
            continue

        if args.verbose:
            pp(f"[*] Watching {path} with mode {s.get('mode', 'tail')}.", "k")

        valid_sources.append(s)

    if not valid_sources:
        pp("[-] No valid log sources found. Exiting.", "r")
        sys.exit(1)

    ui = FluppyUI()

    with Live(
        ui.render(),
        console=console,
        refresh_per_second=6,
        transient=False,
        screen=True,
    ) as live:
        ui.live = live

        await asyncio.gather(*[
            watch(
                s["path"],
                s["rules"],
                outputlogfile,
                ui,
                mode=s.get("mode", "tail"),
                verbose=args.verbose,
            )
            for s in valid_sources
        ])

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pp("\n[+] Woof! fluppy.. done!\n", "g")