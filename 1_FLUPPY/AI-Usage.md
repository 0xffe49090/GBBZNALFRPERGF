# AI Usage Notes

I used AI as a coding partner, but casually and intermittently. An example would be, "should I do this or that", or "give me an example of an implementation of something". I've also commented where I've used AI in the implementation of `fluppy`. 

I functionally use AI as an improved search engine. :)

---
**Prompt**

Why use asyncio over threads? Is there some reason I should go there when implementing a tool that will "watch" several log files?

**AI response below (Claude)**

For a log file watcher, asyncio is likely the right call. Here's why:

## The core difference

**Threads** give you true parallelism for CPU-bound work, but come with overhead: each thread has its own stack (~1–8 MB), OS scheduling costs, and locking headaches when sharing state.

**asyncio** is single-threaded but uses *cooperative multitasking* — tasks yield control when they're waiting (e.g., for I/O), letting other tasks run. No locks needed for shared state, and you can handle thousands of "watchers" with minimal memory.

## Why asyncio wins for log watching

Log watching is almost entirely **I/O-bound**: you're sitting idle waiting for new lines to appear. This is exactly asyncio's sweet spot.

- **No GIL friction** — Python's Global Interpreter Lock throttles threads doing concurrent work. asyncio sidesteps this entirely since only one coroutine runs at a time (by design).
- **Scales cheaply** — watching 500 log files with threads means 500 threads. With asyncio, it's 500 lightweight coroutines sharing one thread.
- **No race conditions on shared state** — if you're aggregating log lines into a shared buffer or counter, asyncio's single-threaded nature means no mutex needed.
- **Clean cancellation** — `asyncio.Task` has first-class cancellation, making it easy to stop watching a file or handle timeouts.

## Practical sketch

```python
import asyncio

async def watch_file(path: str):
    with open(path) as f:
        f.seek(0, 2)  # seek to end
        while True:
            line = f.readline()
            if line:
                print(f"[{path}] {line}", end="")
            else:
                await asyncio.sleep(0.1)  # yield control, don't busy-wait

async def main():
    log_files = ["/var/log/app.log", "/var/log/nginx.log", "/var/log/worker.log"]
    await asyncio.gather(*[watch_file(p) for p in log_files])

asyncio.run(main())
```

The `await asyncio.sleep(0.1)` is the key — when there's nothing to read, the coroutine yields, letting all the other watchers take their turn.

## When threads *would* make sense

- You need to call **blocking libraries** that have no async equivalent (e.g., a legacy DB driver) — here you'd use `asyncio.to_thread()` to bridge them
- You're doing **CPU-heavy log parsing** (regex on huge lines, etc.) and need real parallelism → consider `ProcessPoolExecutor`
- You want simplicity and only have **2–3 files** to watch — threads are fine then, complexity isn't worth it


**Bottom line:** for watching N log files where N > a handful, asyncio gives you simpler code, lower memory, and no locking headaches compared to threads.

---

## Fluppy's Experimental UI

I gave Claude the task to create a rudimentary status window for `fluppy`. I used the prompt below, and pasted in the existing `fluppy` code.

>> What's a Pythonic way to keep a simple status/dashboard (even just text) all while outputting below? It'd be cool to have something like.. <br/><br/>[CRITICAL] credential_leak in horrors.log: 18 total hits; threshold 1<br/>[MEDIUM] http_attack in access.log: 231297 total hits; threshold 30<br/>.....<br/>(output scrolling here)

Claude said:

>> Use rich. It is the least-pain Python answer.

Claude then produced what you can try out in `richfluppy.py`. I don't hate it, but I don't love it either. It moves a bit away from the really simple tool I wanted to create, and it added some underpinnings and probably other bugs I've not reviewed too closely. 