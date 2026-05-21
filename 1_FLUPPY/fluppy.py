import asyncio
import re, time, argparse, sys, platform, os, json
from pathlib import Path
from collections import deque, Counter, defaultdict

try:
    import yaml
except Exception as e:
    print("[!] Missing PyYAML. Install yaml --> `pip install PyYAML`.")
    osx = """
    -- OSX NOTE --
    OSX doesn't allow breaking system packages any longer. Use a virtual environment:
        python3 -m venv venv
        source venv/bin/activate
        python3 -m pip install PyYAML

    Then run "python3 fluppy.py".
    """
    if platform.system() == "Darwin":
        print(osx)

    sys.exit(1)

try:
    import yara
except:
    print("Missing Yara. Install yara --> `pip install yara-python`.")
    sys.exit(1)

def pp(x, color='', strext=''):
    if platform.system() == "Windows":
        os.system('color')
    colors = {
            'r': f"\033[0;31m{x}\033[0m",
            'g': f"\033[0;92m{x}\033[0m",
            'b': f"\033[0;34m{x}\033[0m",
            'c': f"\033[0;96m{x}\033[0m",
            'm': f"\033[0;95m{x}\033[0m",
            'y': f"\033[0;93m{x}\033[0m",
            'k': f"\033[0;90m{x}\033[0m",
            'critical': f"\033[0;95m{x}\033[0m",
            'high': f"\033[0;31m{x}\033[0m",
            'medium': f"\033[0;93m{x}\033[0m",
            'low': f"\033[0;92m{x}\033[0m",
            'info': f"\033[0;34m{x}\033[0m",
            '': x
    }
    try:
        print(f'{colors[color]} {strext}')
    except:
        print(x)
        pass


async def watch(path: str, rules: list, mode="tail", verbose=False):
    if not os.path.exists(path):
        return

    compiled = [
        (
            r["name"],
            re.compile(r["regex"],re.IGNORECASE),
            r["threshold"],
            r["window"],
            r["severity"],
            r.get("cooldown", 60),
            defaultdict(deque),
            {}
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

            for name, rx, threshold, window, severity, cooldown, hitmap, last_alert in compiled:
                m = rx.search(line)
                if not m:
                    continue

                match = m.group(1) if m.lastindex else m.group(0)
                hitval = line.strip() if verbose else match

                if mode == "scan":
                    summary[(severity, name, Path(path).name, threshold, window)][hitval] += 1
                    continue

                hits = hitmap[match]
                hits.append(now)

                while hits and hits[0] < now - window:
                    hits.popleft()

                if len(hits) >= threshold:
                    alert_key = f"{name}:{match}"
                    last = last_alert.get(alert_key, 0)

                    if now - last >= cooldown:
                        pp(f"[{severity.upper()}] {name} in {Path(path).name}: threshold {threshold} hit in {window} seconds.", severity)
                        print(f"  >> match {hitval}")
                        last_alert[alert_key] = now

                    hits.clear()

        if mode == "scan":
            for (severity, name, file, threshold, window), counts in summary.items():
                
                total = sum(counts.values())

                if total < threshold:
                    continue

                pp(f"[{severity.upper()}] {name} in {file}: {total} total hits; threshold {threshold}", severity)

                for value, count in counts.most_common(10):
                    print(f"  {value} [{count}]")

async def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-c', '--config', default='config.yaml')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-h', '--help', action='store_true')

    banner = '''
     Everybody needs a fluppy dog! Fluppies got tails!

    @@@@@@@@ @@@      @@@  @@@ @@@@@@@  @@@@@@@  @@@ @@@
    @@!      @@!      @@!  @@@ @@!  @@@ @@!  @@@ @@! !@@
    @!!!:!   @!!      @!@  !@! @!@@!@!  @!@@!@!   !@!@!
    !!:      !!:      !!:  !!! !!:      !!:        !!:
    :        : ::.: :  :.:: :   :        :         .:

      ~~ hack like your credit rating depends on it ~~
    '''

    #args = parser.parse_args(args=None if sys.argv[1:] else ['--help',pp(banner,'g')])
    args = parser.parse_args()

    # bail on help
    if args.help:
         pp(banner,'g')
         parser.print_help()
         print('\n')
         sys.exit(0)
    
    # otherwise, go forth
    with open(args.config) as f:
        config = yaml.safe_load(f)

    sources = config["sources"]
    for s in sources:
        pp(f"[*] Watching {s.get('path')} with mode {s.get('mode')}.","k")
        
    await asyncio.gather(*[watch(s["path"], s["rules"], mode=s.get("mode", "tail"), verbose=args.verbose) for s in sources])

try:
    asyncio.run(main())
except KeyboardInterrupt:
    pp("\n\n[+] Woof! fluppy.. done!\n", "g")
