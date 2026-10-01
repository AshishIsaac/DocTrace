"""Search UI for your indexed files.

    python search_app.py                       # open the web UI (http://127.0.0.1:7860)
    python search_app.py --query "normalization in DBMS"   # one-off search in the terminal
    python search_app.py --share               # temporary public Gradio link

The UI also has an "Update index" button, so after the first setup you rarely
need the terminal: add files to the data folder and click it.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import inspect
import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from doctrace.config import ConfigError, Settings, load_settings
from doctrace.indexer import IngestError, run_ingest
from doctrace.llm import Ollama, context_hits
from doctrace.search import FileResult, Hit, SearchEngine
from doctrace.store import fts_query

ALL = "All folders"
SNIPPET_CHARS = 420

CSS = """
.doctrace-card {border:1px solid var(--border-color-primary); border-radius:10px;
           padding:12px 14px; margin:10px 0; background:var(--background-fill-secondary);}
.doctrace-head {display:flex; gap:8px; align-items:baseline; flex-wrap:wrap; font-size:1.02em;}
.doctrace-num {font-weight:700; opacity:.6;}
.doctrace-name {font-weight:600; word-break:break-word;}
.doctrace-tag {font-size:.75em; padding:1px 7px; border-radius:99px;
          border:1px solid var(--border-color-primary); opacity:.8;}
.doctrace-path {font-family:var(--font-mono); font-size:.82em; opacity:.75;
           margin:4px 0 6px; word-break:break-all;}
.doctrace-hit {border-top:1px dashed var(--border-color-primary); padding-top:6px; margin-top:6px;}
.doctrace-loc {font-weight:600; font-size:.85em;}
.doctrace-score {font-size:.78em; opacity:.65; margin-left:6px;}
.doctrace-snip {white-space:pre-wrap; font-size:.9em; line-height:1.45; margin-top:3px;}
.doctrace-snip mark {padding:0 2px; border-radius:3px;}
"""


# ------------------------------------------------------------------ rendering
def _terms(query: str) -> list[str]:
    return [t.strip('"') for t in fts_query(query).split(" OR ") if t]


def _snippet(text: str, terms: list[str]) -> str:
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    if len(text) > SNIPPET_CHARS:
        lower = text.lower()
        pos = min((p for p in (lower.find(t) for t in terms) if p >= 0), default=0)
        start = max(0, min(pos - SNIPPET_CHARS // 3, len(text) - SNIPPET_CHARS))
        text = ("..." if start else "") + text[start:start + SNIPPET_CHARS].strip() + "..."
    out = html.escape(text)
    if terms:
        pattern = re.compile("|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)), re.I)
        out = pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", out)
    return out


def _match_label(h: Hit) -> str:
    parts = []
    if h.similarity is not None:
        parts.append(f"{max(h.similarity, 0) * 100:.0f}% semantic")
    if h.keyword:
        parts.append("keyword")
    return " + ".join(parts)


def render_results(files: list[FileResult], query: str) -> str:
    if not files:
        return "<p>No matching files found. Try other words, or check the folder filter.</p>"
    terms = _terms(query)
    cards = []
    for i, f in enumerate(files, start=1):
        name = html.escape(Path(f.path).name)
        folder = html.escape(" / ".join(Path(f.path).parent.parts) or "(top level)")
        if f.source == "gdrive":
            name = f'<a href="{html.escape(f.uri)}" target="_blank" rel="noopener">{name}</a>'
        tag = "Google Drive" if f.source == "gdrive" else Path(f.path).suffix.lstrip(".").upper()
        hits = "".join(
            f'<div class="doctrace-hit"><span class="doctrace-loc">{html.escape(h.chunk.location or "match")}</span>'
            f'<span class="doctrace-score">{_match_label(h)}</span>'
            f'<div class="doctrace-snip">{_snippet(h.chunk.text, terms)}</div></div>'
            for h in f.hits
        )
        cards.append(
            f'<div class="doctrace-card"><div class="doctrace-head"><span class="doctrace-num">{i}</span>'
            f'<span class="doctrace-name">{name}</span><span class="doctrace-tag">{html.escape(tag)}</span></div>'
            f'<div class="doctrace-path" title="{html.escape(f.uri)}">{folder}</div>{hits}</div>'
        )
    return "".join(cards)


def render_sources(hits: list[Hit]) -> str:
    lines = [
        f"{i}. `{h.chunk.path}`" + (f" ({h.chunk.location})" if h.chunk.location else "")
        for i, h in enumerate(hits, start=1)
    ]
    return "\n\n**Sources**\n\n" + "\n".join(lines)


# ------------------------------------------------------------------ open files locally
def open_local(path: str, reveal: bool) -> None:
    if sys.platform == "win32":
        if reveal:
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            os.startfile(path)  # noqa: S606 - path comes from our own index
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path] if reveal else ["open", path])
    else:
        subprocess.Popen(["xdg-open", str(Path(path).parent) if reveal else path])


# ------------------------------------------------------------------ indexing from the UI
class IndexManager:
    """Runs incremental ingests in the background and swaps in the fresh index."""

    def __init__(self, cfg: Settings, engine: SearchEngine):
        self.cfg = cfg
        self.engine = engine
        self.lock = threading.Lock()

    def update(self, rebuild: bool = False):
        """Generator yielding the growing log text while an ingest runs."""
        if not self.lock.acquire(blocking=False):
            yield "An update is already running ..."
            return
        try:
            lines: list[str] = []
            result: dict = {}

            def work():
                try:
                    result["summary"] = run_ingest(
                        self.cfg, rebuild=rebuild, embedder=self.engine.embedder,
                        log=lines.append, show_progress=False,
                    )
                    self.engine.reload()
                except (IngestError, OSError, RuntimeError) as e:
                    result["error"] = str(e)

            t = threading.Thread(target=work, daemon=True)
            t.start()
            while t.is_alive():
                t.join(0.5)
                yield "\n".join(lines[-40:])
            if "error" in result:
                yield "\n".join(lines[-40:] + ["", f"Error: {result['error']}"])
            else:
                yield "\n".join(lines[-40:] + ["", "Done: " + result["summary"].text()])
        finally:
            self.lock.release()

    def watch(self, minutes: float) -> None:
        """Background loop: pick up new / changed / deleted files every few minutes."""
        def loop():
            while True:
                time.sleep(minutes * 60)
                if not self.lock.locked():
                    for _ in self.update():
                        pass

        threading.Thread(target=loop, daemon=True).start()


# ------------------------------------------------------------------ UI
def build_ui(cfg: Settings, engine: SearchEngine, llm: Ollama | None, can_open: bool):
    import gradio as gr

    indexer = IndexManager(cfg, engine)
    if cfg.watch_minutes > 0:
        indexer.watch(cfg.watch_minutes)
    llm_msg = llm.status() if llm else "Answer generation is off (DOCTRACE_LLM=none)."
    model_missing = llm is not None and "not downloaded" in llm_msg

    def header() -> str:
        st = engine.store.stats()
        root = engine.store.get_meta("local_root") or str(cfg.data_dir)
        if not st["chunks"]:
            return (
                "## DocTrace\n**Nothing is indexed yet.** Put your files in "
                f"`{root}` (any folder structure), then click **Update index**."
            )
        last = engine.store.get_meta("last_ingest")
        when = dt.datetime.fromtimestamp(float(last)).strftime("%d %b %Y, %H:%M") if last else "unknown"
        return (
            "## DocTrace\nFind anything in your files and see exactly where it is. "
            f"**{st['files']:,} files** ({st['chunks']:,} passages) from `{root}`, "
            f"last updated {when}."
        )

    def problems() -> list[list[str]]:
        return [[p, s, e[:200]] for p, s, e in engine.store.problem_files()]

    def run(query: str, folder: str, k: float, use_llm: bool):
        no_change = gr.update()
        if not engine.ready:
            yield "", "<p>Nothing is indexed yet. Add files and click <b>Update index</b>.</p>", \
                gr.update(choices=[], value=None)
            return
        if not query or not query.strip():
            yield "", "<p>Type a question or some keywords above.</p>", gr.update(choices=[], value=None)
            return
        files, hits = engine.search(query, int(k), "" if folder == ALL else folder)
        results = render_results(files, query)
        choices = [(f"[{i}] {f.path}", f.uri) for i, f in enumerate(files, 1) if f.source == "local"]
        picker = gr.update(choices=choices, value=choices[0][1] if choices else None)
        if not files or not use_llm:
            yield "", results, picker
            return
        reason = llm.status() if llm else llm_msg
        if reason:
            yield f"*{reason}*", results, picker
            return
        ctx = context_hits(hits)
        yield f"*Generating an answer with `{llm.model}` ...*", results, picker
        answer = ""
        try:
            for token in llm.answer(query, ctx):
                answer += token
                yield answer, no_change, no_change
        except Exception as e:  # noqa: BLE001
            yield f"{answer}\n\n*LLM error: {e}*", no_change, no_change
            return
        yield answer + render_sources(ctx), no_change, no_change

    def do_update(rebuild: bool = False):
        log = ""
        for log in indexer.update(rebuild):
            yield log, gr.update(), gr.update(), gr.update()
        yield log, header(), gr.update(choices=[ALL] + engine.folders(), value=ALL), problems()

    def do_rebuild():
        yield from do_update(rebuild=True)

    def do_pull():
        if llm is None:
            yield "Answer generation is off.", gr.update(), gr.update()
            return
        if not llm.ensure_running():
            yield llm.status(), gr.update(), gr.update()
            return
        try:
            for msg in llm.pull():
                yield f"Downloading `{llm.model}`: {msg}", gr.update(), gr.update()
        except Exception as e:  # noqa: BLE001
            yield f"Download failed: {e}", gr.update(), gr.update()
            return
        yield f"`{llm.model}` is ready.", gr.update(value=True, info=f"Using {llm.model}"), \
            gr.update(visible=False)

    def do_open(uri: str | None, reveal: bool) -> str:
        if not uri:
            return "Pick a file from the results first."
        if not engine.store.is_local_file(uri) or not os.path.exists(uri):
            return "That file is not available on this computer."
        try:
            open_local(uri, reveal)
            return f"Showing `{uri}` in its folder" if reveal else f"Opened `{uri}`"
        except Exception as e:  # noqa: BLE001
            return f"Could not open it: {e}"

    blocks_kwargs = {"title": "DocTrace"}
    launch_kwargs = {}
    # Gradio 6 moved `css` from Blocks() to launch()
    if "css" in inspect.signature(gr.Blocks.launch).parameters:
        launch_kwargs["css"] = CSS
    else:
        blocks_kwargs["css"] = CSS

    with gr.Blocks(**blocks_kwargs) as demo:
        with gr.Row(equal_height=True):
            head = gr.Markdown(header())
            update_btn = gr.Button("Update index", scale=0, min_width=150)
        with gr.Accordion("Index status", open=not engine.ready) as acc:
            log_box = gr.Textbox(
                label="Log", lines=8, max_lines=16, interactive=False,
                value="" if engine.ready else
                "Add files to the data folder, then click 'Update index'. "
                "New, changed and deleted files are picked up automatically.",
            )
            issues = gr.Dataframe(
                headers=["File", "Status", "Details"], value=problems(), interactive=False,
                label="Files without searchable text (failed, empty, or scanned without OCR)",
                wrap=True,
            )
            rebuild_btn = gr.Button("Rebuild from scratch", size="sm", variant="secondary")

        with gr.Row():
            query = gr.Textbox(
                placeholder="e.g.  explain 3NF with an example   /   where are the OS scheduling notes?",
                show_label=False, scale=6, autofocus=True,
            )
            go = gr.Button("Search", variant="primary", scale=1)
        with gr.Row():
            folder = gr.Dropdown([ALL] + engine.folders(), value=ALL, label="Search in folder", scale=3)
            k = gr.Slider(1, 25, value=8, step=1, label="Files to show", scale=2)
            with gr.Column(scale=2):
                use_llm = gr.Checkbox(
                    value=llm is not None and not llm_msg, label="Generate an answer (Ollama)",
                    info=llm_msg or f"Using {llm.model}",
                )
                pull_btn = gr.Button(
                    f"Download the {llm.model if llm else ''} model", size="sm", visible=model_missing,
                )
        answer = gr.Markdown()
        results = gr.HTML()
        with gr.Row(visible=can_open):
            picker = gr.Dropdown(label="Result file", choices=[], scale=4)
            open_btn = gr.Button("Open file", scale=1)
            reveal_btn = gr.Button("Show in folder", scale=1)
        status = gr.Markdown()

        inputs = [query, folder, k, use_llm]
        outputs = [answer, results, picker]
        go.click(run, inputs, outputs)
        query.submit(run, inputs, outputs)

        update_outputs = [log_box, head, folder, issues]
        update_btn.click(lambda: gr.update(open=True), None, acc).then(do_update, None, update_outputs)
        rebuild_btn.click(do_rebuild, None, update_outputs)
        pull_btn.click(do_pull, None, [status, use_llm, pull_btn])
        open_btn.click(lambda u: do_open(u, False), picker, status)
        reveal_btn.click(lambda u: do_open(u, True), picker, status)
    return demo, launch_kwargs


def free_port(host: str, preferred: int) -> int:
    """The preferred port, or the next free one if it is taken."""
    bind_host = "127.0.0.1" if host in {"localhost", "::1"} else host
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((bind_host, port))
                return port
            except OSError:
                continue
    return preferred


# ------------------------------------------------------------------ CLI
def cli_search(engine: SearchEngine, llm: Ollama | None, query: str, k: int) -> None:
    if not engine.ready:
        sys.exit("The index is empty. Put files in the data folder and run: python ingest.py")
    files, hits = engine.search(query, k)
    if not files:
        print("No matches.")
        return
    for i, f in enumerate(files, start=1):
        print(f"\n[{i}] {f.path}\n    {f.uri}")
        for h in f.hits:
            snippet = " ".join(h.chunk.text.split())[:160]
            print(f"    - {h.chunk.location or 'match'} ({_match_label(h)}): {snippet}...")
    if llm and not llm.status():
        print("\nAnswer:\n")
        ctx = context_hits(hits)
        for token in llm.answer(query, ctx):
            print(token, end="", flush=True)
        print(render_sources(ctx).replace("**", ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--query", "-q", help="run one search in the terminal and exit")
    ap.add_argument("-k", type=int, default=5, help="files to show with --query")
    ap.add_argument("--share", action="store_true", help="create a public Gradio link")
    ap.add_argument("--no-browser", action="store_true", help="don't open a browser tab")
    args = ap.parse_args()

    try:
        cfg = load_settings()
    except ConfigError as e:
        sys.exit(f"Error: {e}")
    engine = SearchEngine(cfg)
    llm = Ollama(cfg) if cfg.llm in {"auto", "ollama"} else None

    if args.query:
        cli_search(engine, llm, args.query, args.k)
        return

    local_host = cfg.host in {"127.0.0.1", "localhost", "::1"}
    can_open = cfg.allow_open and local_host and not args.share
    demo, launch_kwargs = build_ui(cfg, engine, llm, can_open)
    port = free_port(cfg.host, cfg.port)
    if port != cfg.port:
        print(f"Port {cfg.port} is busy; using {port} instead.")
    demo.queue().launch(
        server_name=cfg.host, server_port=port, share=args.share, inbrowser=not args.no_browser,
        **launch_kwargs,
    )


if __name__ == "__main__":
    main()
