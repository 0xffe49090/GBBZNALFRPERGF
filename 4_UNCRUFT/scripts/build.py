#!/usr/bin/env python3
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]; SRC=ROOT/"src"; DIST=ROOT/"dist"
for target in ("chromium","firefox"):
    out=DIST/target
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    for item in SRC.iterdir():
        if item.name.startswith("manifest."): continue
        shutil.copytree(item,out/item.name) if item.is_dir() else shutil.copy2(item,out/item.name)
    shutil.copy2(SRC/f"manifest.{target}.json",out/"manifest.json")
