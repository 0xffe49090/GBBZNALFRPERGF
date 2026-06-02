import asyncio
import re, time, argparse, sys, platform, os, json, logging
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

# PLANNED
# try:
#     import yara
# except:
#     print("Missing Yara. Install yara --> `pip install yara-python`.")
#     sys.exit(1)

def pp(x, color='', strext=''):
    '''
        Just a color hack. 
    '''
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

def hilariousTmux(logfile):
    import subprocess

    cmd = (
        f'tmux new-session -d -s fluppy "{sys.executable} {sys.argv[0]} --no-tmux"; '
        f'tmux split-window -h -t fluppy "tail -f {logfile}"; '
        f'tmux attach -t fluppy'
    )

    subprocess.run(cmd, shell=True)

def writeJsonLog(jsondict, logfile="results.json"):
    with open(logfile,"a") as f:
        f.write(f"{jsondict}\n")

# async def watch(path: str, rules: list, outputlogfile="results.json", mode="tail", verbose=False):
async def watch(path: str, rules: list, outputlogfile, mode="tail", verbose=False):
    '''
        The main function to watch the defined log files.

    '''
    # check for the source file
    # if not os.path.exists(path):
    #     pp(f"[-] Log source not found {path}.","r")
    #     return

    if path == outputlogfile:
        pp(f"[!] Cyclical read. Cannot monitor {path} as the output file. Ignoring that..","r")
        return

    # get yaml elements
    compiled = [
        (
            r["name"],
            # complile the regex for speed
            re.compile(r["regex"],re.IGNORECASE),
            r["threshold"],
            r["window"],
            r["severity"],
            r.get("cooldown", 60),
            r.get("redact", False),
            # AI suggested - automatically creates an empty deque if the key doesn't exist yet
            defaultdict(deque),
            {}
        )
        for r in rules
    ]

    # dict to hold threshold/counters
    summary = defaultdict(Counter)

    # open the log file
    with open(path, errors="ignore") as f:
        # in tail mode, go to the end of the file
        if mode == "tail":
            f.seek(0, 2)

        # loop until user exit..
        while True:
            line = f.readline()

            if not line:
                if mode == "scan":
                    break
                await asyncio.sleep(0.1)
                continue

            # forward-only clock
            now = time.monotonic()

            # for each node in the YAML
            for name, rx, threshold, window, severity, cooldown, redact, hitmap, last_alert in compiled:
                # search with the regex
                m = rx.search(line)
                if not m:
                    continue

                # AI's suggested group matching
                match = m.group(1) if m.lastindex else m.group(0)
                
                # little hack to compress extra spaces, this is our match
                hitval = " ".join(line.strip().split()) if verbose else match

                # make a basic attempt to not put sensitive details
                # back into the log we're generating
                if redact:
                    hitval = "--REDACTED--"

                # scan mode, increment hits for summary
                if mode == "scan":
                    summary[(severity, name, Path(path).name, threshold, window)][hitval] += 1
                    continue

                # update match counts
                hits = hitmap[match]
                hits.append(now)

                # pop the hits off the collections queue
                while hits and hits[0] < now - window:
                    hits.popleft()

                # alert if we hit our threshold
                if len(hits) >= threshold:
                    alert_key = f"{name}:{match}"
                    last = last_alert.get(alert_key, 0)

                    # respect the cooldown and print the results
                    if now - last >= cooldown:
                        event = f"[{severity.upper()}] {name} in {Path(path).name}: threshold {threshold} hit in {window} seconds."
                        pp(event,severity)
                        logevent = {"event_id":now,"mode":mode,"alert":event,"match":hitval}
                        writeJsonLog(json.dumps(logevent),outputlogfile)
                        print(f"  {hitval}")
                        last_alert[alert_key] = now

                    # reset 
                    hits.clear()

        # scan mode, essentially look at a dead file and find whatever pattern is defined
        if mode == "scan":
            for (severity, name, file, threshold, window), counts in summary.items():
                total = sum(counts.values())

                if total < threshold:
                    continue

                # print the summarized results
                #pp(f"[{severity.upper()}] {name} in {file}: {total} total hits; threshold {threshold}", severity)
                event = f"[{severity.upper()}] {name} in {file}: {total} total hits; threshold {threshold}"
                pp(event,severity)

                # AI suggested improvement to counting
                stack = []
                for value, count in counts.most_common(10):
                    print(f"  {value} [{count}]")
                    stack.append(f"{value} [{count}/{total}]")

                # option 1                
                logevent = {"event_id":now,"mode":mode,"alert":event,"match":f"{value} [{count}/{total}]"}
                writeJsonLog(json.dumps(logevent),outputlogfile)

                # option 2 
                if verbose:
                    for s in stack:
                        logevent = {"event_id":now,"mode":mode,"alert":event,"match":s}
                        writeJsonLog(json.dumps(logevent),outputlogfile)


async def main():
    '''
        Provides the user with arguments to supply at the command line.
        Runs automatically expecting a "config.yaml" local to this tool.

    '''
    # argument processing I want my own help here
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('-c', '--config', default='config.yaml', help="The YAML configuration to read rules from.")
    parser.add_argument('-o', '--output', default='results.json', help="Takes filename, writes JSONL.")
    parser.add_argument('-v', '--verbose', action='store_true', help="Show verbose output to CLI.")
    parser.add_argument('-t', '--tmux', action='store_true', help="Launch this in tmux for some reason.")
    parser.add_argument('-h', '--help', action='store_true', help="This help message.")

    # sweet banner
    # "monitor" just fit better for this tool
    banner = '''
     Everybody needs a fluppy dog! Fluppies got tails!

    @@@@@@@@ @@@      @@@  @@@ @@@@@@@  @@@@@@@  @@@ @@@
    @@!      @@!      @@!  @@@ @@!  @@@ @@!  @@@ @@! !@@
    @!!!:!   @!!      @!@  !@! @!@@!@!  @!@@!@!   !@!@!
    !!:      !!:      !!:  !!! !!:      !!:        !!:
    :        : ::.: :  :.:: :   :        :         .:

     ~~ monitor like your credit rating depends on it ~~
    '''

    args = parser.parse_args()

    # bail on help
    if args.help:
         pp(banner,'g')
         parser.print_help()
         print('\n')
         sys.exit(0)
    
    # otherwise, go forth
    try:
        with open(args.config) as f:
            config = yaml.safe_load(f)
    except:
        pp("[-] No config.yaml found. Ensure that config.yaml is in the same folder as this tool.","r")
        sys.exit(1)

    sources = config["sources"]
    
    if args.output:
        outputlogfile = args.output or "results.json"
        if os.path.exists(outputlogfile):
            pp(f"[-] Cowardly refusing to overwrite {outputlogfile}. Exiting.")
            sys.exit(1)

    # AI suggested improvement was to look for valid source here
    # a minor adjustment to ensure no invalid files are passed to the program. 
    # This makes for a better user experience and keeps the source reporting
    # in one place. 
    valid_sources = []

    for s in sources:
        if not os.path.exists(s.get("path")):
            pp(f"[-] Log source not found {s.get('path')}.", "r")
            continue
        if args.verbose:
            pp(f"[*] Watching {s.get('path')} with mode {s.get('mode')}.", "k")
        valid_sources.append(s)

    # okay now send each source to the program for searching
    await asyncio.gather(*[
        watch(
            s["path"],
            s["rules"],
            outputlogfile,
            mode=s.get("mode", "tail"),
            verbose=args.verbose
        )
        for s in valid_sources
    ])

try:
    # the main event async
    asyncio.run(main())
except KeyboardInterrupt:
    # report exit on control-c
    pp("\n\n[+] Woof! fluppy.. done!\n", "g")
