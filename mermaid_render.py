#!/usr/bin/env python3
"""
mermaid_render.py
─────────────────
Reads Mermaid code blocks from .md files and renders them as
high-resolution PNG / SVG diagrams.

Render engines (tried in order):
  1. mmdc  — Mermaid CLI via Node.js  (best quality, needs npm install -g @mermaid-js/mermaid-cli)
  2. mermaid.ink — free public API    (no install, needs internet)

Usage
─────
  # Render all .md files in current folder
  python mermaid_render.py

  # Render a specific file
  python mermaid_render.py FIG1_System_Overview.md

  # Render multiple files, SVG output, custom output dir
  python mermaid_render.py FIG1_System_Overview.md FIG2_Agent_Architecture.md -f svg -o diagrams/

  # Use mermaid.ink only (skip mmdc)
  python mermaid_render.py --engine ink

  # High-DPI PNG (scale 3x)
  python mermaid_render.py --scale 3

  # List diagrams found without rendering
  python mermaid_render.py --dry-run

Options
───────
  files           .md files to process (default: all *.md in cwd)
  -o, --outdir    output directory (default: diagrams/)
  -f, --format    png | svg  (default: png)
  -s, --scale     pixel scale multiplier for PNG, 1-4 (default: 2)
  --engine        auto | mmdc | ink  (default: auto)
  --theme         default | dark | forest | neutral (default: default)
  --bg            background colour hex, e.g. ffffff (default: ffffff)
  --dry-run       list diagrams found, do not render
  --open          open output folder when done (Windows/macOS)
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.progress import (BarColumn, Progress, SpinnerColumn,
                           TaskProgressColumn, TextColumn, TimeElapsedColumn)
from rich.table import Table
from rich import print as rprint

import io
# Force UTF-8 on Windows terminals that default to cp1252
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

console = Console(highlight=False, emoji=False)

# ─────────────────────────────────────────────────────────────
# Mermaid block extraction
# ─────────────────────────────────────────────────────────────

def extract_diagrams(md_path: Path) -> list[dict]:
    """
    Parse a .md file and return all mermaid code blocks with metadata.
    Each entry: {index, heading, code, file}
    """
    text     = md_path.read_text(encoding="utf-8")
    diagrams = []
    heading  = md_path.stem    # fallback heading = filename
    last_h   = heading
    idx      = 0

    # Walk line by line to track headings and capture fenced blocks
    lines   = text.splitlines()
    i       = 0
    while i < len(lines):
        line = lines[i]

        # Track the last heading seen
        m = re.match(r"^#{1,4}\s+(.+)", line)
        if m:
            last_h = m.group(1).strip()
            i += 1
            continue

        # Opening mermaid fence
        if re.match(r"^```mermaid\s*$", line.strip()):
            block_lines = []
            i += 1
            while i < len(lines) and not re.match(r"^```\s*$", lines[i].strip()):
                block_lines.append(lines[i])
                i += 1
            code = "\n".join(block_lines).strip()
            if code:
                idx += 1
                slug = re.sub(r"[^\w\-]", "_", last_h)[:60].strip("_")
                diagrams.append({
                    "index":   idx,
                    "heading": last_h,
                    "slug":    slug,
                    "code":    code,
                    "file":    md_path,
                })
        i += 1

    return diagrams


# ─────────────────────────────────────────────────────────────
# Engine detection
# ─────────────────────────────────────────────────────────────

def detect_mmdc() -> str | None:
    """Return path to mmdc if available, else None."""
    for candidate in ["mmdc", "mmdc.cmd"]:
        path = shutil.which(candidate)
        if path:
            return path
    # Also check common npm global paths on Windows
    npm_prefix = subprocess.run(
        ["npm", "root", "-g"], capture_output=True, text=True
    ).stdout.strip()
    if npm_prefix:
        p = Path(npm_prefix).parent / "mmdc.cmd"
        if p.exists():
            return str(p)
    return None


# ─────────────────────────────────────────────────────────────
# Render via mmdc
# ─────────────────────────────────────────────────────────────

def render_mmdc(diagram: dict, out_path: Path, fmt: str,
                scale: int, theme: str, bg: str) -> bool:
    mmdc = detect_mmdc()
    if not mmdc:
        return False

    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd",
                                     delete=False, encoding="utf-8") as f:
        f.write(diagram["code"])
        tmp = f.name

    cfg = {"theme": theme}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                      delete=False, encoding="utf-8") as cf:
        json.dump(cfg, cf)
        cfg_path = cf.name

    cmd = [
        mmdc,
        "-i", tmp,
        "-o", str(out_path),
        "-t", theme,
        "-b", f"#{bg}",
        "--configFile", cfg_path,
    ]
    if fmt == "png":
        cmd += ["--scale", str(scale)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0
    except Exception:
        return False
    finally:
        os.unlink(tmp)
        os.unlink(cfg_path)


# ─────────────────────────────────────────────────────────────
# Render via mermaid.ink API
# ─────────────────────────────────────────────────────────────

def render_ink(diagram: dict, out_path: Path, fmt: str,
               scale: int, theme: str, bg: str) -> bool:
    encoded = base64.urlsafe_b64encode(diagram["code"].encode()).decode()

    if fmt == "svg":
        url = f"https://mermaid.ink/svg/{encoded}?theme={theme}&bgColor={bg}"
    else:
        url = f"https://mermaid.ink/img/{encoded}?theme={theme}&bgColor={bg}&scale={scale}"

    try:
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            return False
        out_path.write_bytes(r.content)

        # Upscale PNG via Pillow if scale > 1 and mmdc wasn't used
        if fmt == "png" and scale > 1:
            img = Image.open(out_path)
            w, h = img.size
            img = img.resize((w * scale, h * scale), Image.LANCZOS)
            img.save(out_path, dpi=(96 * scale, 96 * scale))

        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────
# Output filename
# ─────────────────────────────────────────────────────────────

def out_filename(diagram: dict, fmt: str) -> str:
    stem = diagram["file"].stem
    return f"{stem}__{diagram['index']:02d}__{diagram['slug']}.{fmt}"


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="mermaid_render",
        description="Render Mermaid diagrams from .md files as hi-res PNG/SVG",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="*",
                        help=".md files (default: all *.md in current dir)")
    parser.add_argument("-o", "--outdir", default="diagrams",
                        help="output directory (default: diagrams/)")
    parser.add_argument("-f", "--format", choices=["png","svg"], default="png",
                        help="output format (default: png)")
    parser.add_argument("-s", "--scale", type=int, default=2, choices=[1,2,3,4],
                        help="PNG scale multiplier (default: 2)")
    parser.add_argument("--engine", choices=["auto","mmdc","ink"], default="auto",
                        help="render engine (default: auto)")
    parser.add_argument("--theme",
                        choices=["default","dark","forest","neutral"],
                        default="default")
    parser.add_argument("--bg", default="ffffff",
                        help="background hex colour (default: ffffff)")
    parser.add_argument("--dry-run", action="store_true",
                        help="list diagrams found, do not render")
    parser.add_argument("--open", action="store_true",
                        help="open output folder when done")
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold cyan]Mermaid Diagram Renderer[/bold cyan]\n"
        "[dim]Reads .md files and exports hi-res PNG / SVG[/dim]",
        border_style="cyan"
    ))

    # ── Resolve input files ───────────────────────────────────
    if args.files:
        md_files = [Path(f) for f in args.files]
    else:
        md_files = sorted(Path(".").glob("*.md"))

    md_files = [f for f in md_files if f.exists() and f.suffix == ".md"]
    if not md_files:
        console.print("[red]No .md files found.[/red]")
        sys.exit(1)

    # ── Extract all diagrams ──────────────────────────────────
    all_diagrams = []
    for f in md_files:
        found = extract_diagrams(f)
        all_diagrams.extend(found)

    if not all_diagrams:
        console.print("[yellow]No mermaid code blocks found in the selected files.[/yellow]")
        sys.exit(0)

    # ── Summary table ─────────────────────────────────────────
    tbl = Table(title=f"Found {len(all_diagrams)} diagram(s)",
                border_style="cyan", show_lines=True)
    tbl.add_column("#",       style="dim",    width=4,  justify="right")
    tbl.add_column("File",    style="cyan",   width=28)
    tbl.add_column("Heading", style="white",  width=40)
    tbl.add_column("Type",    style="yellow", width=16)
    for d in all_diagrams:
        kind = d["code"].split()[0] if d["code"] else "?"
        tbl.add_row(str(d["index"]), d["file"].name, d["heading"], kind)
    console.print(tbl)

    if args.dry_run:
        console.print("[dim]Dry run — no files written.[/dim]")
        return

    # ── Detect engine ─────────────────────────────────────────
    mmdc_path  = detect_mmdc()
    use_mmdc   = args.engine in ("auto", "mmdc") and mmdc_path is not None
    use_ink    = args.engine in ("auto", "ink")

    if use_mmdc:
        console.print(f"[green]Engine:[/green] mmdc  ({mmdc_path})")
    elif use_ink:
        console.print("[green]Engine:[/green] mermaid.ink  (API)")
    else:
        console.print("[red]No render engine available. "
                      "Install mmdc:  npm install -g @mermaid-js/mermaid-cli[/red]")
        sys.exit(1)

    console.print(f"[green]Format:[/green] {args.format.upper()}  "
                  f"[green]Scale:[/green] {args.scale}x  "
                  f"[green]Theme:[/green] {args.theme}  "
                  f"[green]Output:[/green] {args.outdir}/\n")

    # ── Output directory ──────────────────────────────────────
    out_dir = Path(args.outdir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Render loop ───────────────────────────────────────────
    ok = fail = 0
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Rendering...", total=len(all_diagrams))

        for d in all_diagrams:
            fname    = out_filename(d, args.format)
            out_path = out_dir / fname
            label    = f"[{d['index']:02d}/{len(all_diagrams):02d}] {d['file'].name} → {fname}"
            progress.update(task, description=label)

            success = False
            if use_mmdc:
                success = render_mmdc(d, out_path, args.format,
                                      args.scale, args.theme, args.bg)
            if not success and use_ink:
                success = render_ink(d, out_path, args.format,
                                     args.scale, args.theme, args.bg)
                if use_mmdc and not success:
                    time.sleep(0.5)   # brief pause between API calls

            if success:
                ok  += 1
                progress.console.print(f"  [green]OK[/green] {fname}")
            else:
                fail += 1
                progress.console.print(f"  [red]FAIL[/red] {fname}  [dim](render failed)[/dim]")

            progress.advance(task)

    # ── Final summary ─────────────────────────────────────────
    console.print()
    if fail == 0:
        console.print(Panel(
            f"[bold green]All {ok} diagram(s) saved to [cyan]{out_dir}/[/cyan][/bold green]",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[green]{ok} succeeded[/green]  [red]{fail} failed[/red]\n"
            f"Output: [cyan]{out_dir}/[/cyan]",
            border_style="yellow"
        ))

    if args.open and ok > 0:
        if sys.platform == "win32":
            os.startfile(str(out_dir.resolve()))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(out_dir.resolve())])
        else:
            subprocess.run(["xdg-open", str(out_dir.resolve())])


if __name__ == "__main__":
    main()
