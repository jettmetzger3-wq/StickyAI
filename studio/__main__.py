"""Command line:  python -m studio <command>

  make "The Fall of Rome" --minutes 3        topic -> finished video (free mode by default)
  make https://youtube.com/watch?v=...        remake a YouTube video as a new stickman video
  serve                                       start the dashboard (http://localhost:8765)
  list | resume <slug> | rerender <slug> <scene numbers> | estimate ... | doctor
"""
import argparse
import os
import shutil
import sys

from . import config


def _echo():
    state = {"inline": False}

    def echo(msg, end=False):
        if end:
            sys.stdout.write("\r" + msg[:150].ljust(150))
            sys.stdout.flush()
            state["inline"] = True
        else:
            if state["inline"]:
                sys.stdout.write("\n")
                state["inline"] = False
            print(msg, flush=True)
    return echo


def ask_approval(na):
    from .pipeline import costs, STAGE_LABELS
    print(f"\n$$ {STAGE_LABELS[na.stage]} uses paid services:")
    for label, c in na.lines:
        print(f"   - {label}: {costs.describe(c.to_dict())}" + (f"  ({c.note})" if c.note else ""))
    try:
        ans = input("   Spend this? [y/N] ").strip().lower()
    except EOFError:
        ans = ""
    return ans in ("y", "yes")


def is_url(s):
    return s.startswith("http://") or s.startswith("https://") or "youtu" in s


def cmd_make(a):
    from . import providers as P
    from .pipeline import new_project, run, costs
    settings = config.load_settings()
    prov = dict(P.TIERS[a.tier])
    for st in ("llm", "voice", "music", "image", "transcript"):
        v = getattr(a, st)
        if v:
            prov[st] = v
    mode = "youtube" if is_url(a.what) else "topic"
    opts = dict(minutes=a.minutes, tone=a.tone, faithfulness=a.faithfulness, watch=not a.no_watch,
                autopilot=not a.checkpoints, extra=a.extra or "", share_copy=not a.no_share,
                credit_source=True, captions=True, style_url=a.style or "")
    for stage, pid in prov.items():
        p = P.get(stage, pid)
        ok, why = p.available()
        if not ok and (stage != "transcript" or mode == "youtube"):
            print(f"! {p.label}: {why}")
    pr = new_project(a.title or (a.what if mode == "topic" else ""), mode,
                     source_url=a.what if mode == "youtube" else "", topic=a.topic or (a.what if mode == "topic" else ""),
                     options=opts, providers=prov)
    print(f"Project: {pr.dir}")
    est = costs.estimate_all(pr)
    paid = {st: e for st, e in est.items() if not e["total"]["free"]}
    if paid:
        print("Estimated costs:")
        for st, e in paid.items():
            print(f"  {st}: {costs.describe(e['total'])}")
        if a.approve_spend:
            costs.approve(pr, {st: e["total"] for st, e in paid.items()})
    else:
        print("Everything in this run is free.")
    res = run(pr, approve_cb=ask_approval, echo=_echo())
    report(pr, res)
    return 0 if res in ("done", "awaiting_review") else 1


def report(pr, res):
    print()
    if res == "done":
        yt = pr.youtube() or {}
        print("Done!")
        print("  video:     ", pr.p("final", "video.mp4"))
        if yt.get("share"):
            print("  share copy:", pr.p(yt["share"]))
        print("  thumbnail: ", pr.p("final", "thumbnail.png"))
        print("  titles:    ", " | ".join(yt.get("titles") or []))
        print("  description in", pr.p("final", "description.txt"))
    elif res == "awaiting_review":
        m = pr.meta()
        st = (m.get("pending") or {}).get("stage")
        print(f"Paused for review after '{st}'. Edit the files in {pr.dir} (or use the dashboard), then run:")
        print(f"  python -m studio resume {pr.slug}")
    elif res == "awaiting_approval":
        print(f"Paused: a paid step was not approved. Run `python -m studio resume {pr.slug}` to be asked again.")
    else:
        print(f"Stopped ({res}). Error: {pr.meta().get('error')}")
        print(f"Fix it and run: python -m studio resume {pr.slug}")


def cmd_resume(a):
    from .pipeline import Project, run, mark_reviewed
    pr = Project(a.slug)
    if not pr.exists():
        print("no such project")
        return 1
    m = pr.meta()
    pend = m.get("pending") or {}
    if pend.get("type") == "review":
        mark_reviewed(pr, pend["stage"])
    res = run(pr, start=a.from_stage, approve_cb=ask_approval, echo=_echo())
    report(pr, res)
    return 0


def cmd_rerender(a):
    from .pipeline import Project, run
    pr = Project(a.slug)
    only = [int(x) for x in a.scenes]
    res = run(pr, start="render", approve_cb=ask_approval, echo=_echo(), stage_kwargs={"render": {"only": only}})
    report(pr, res)
    return 0


def cmd_list(a):
    from .pipeline import list_projects
    for m in list_projects():
        print(f"{m['slug']:40s} {m.get('status', ''):18s} {m.get('title', '')}")
    return 0


def cmd_doctor(a):
    from . import providers as P
    print("ffmpeg:", shutil.which("ffmpeg") or "MISSING (Windows: winget install ffmpeg | Debian: sudo apt install ffmpeg)")
    print("python:", sys.version.split()[0])
    for stage, items in P.catalog().items():
        print(f"\n{P.STAGE_LABELS.get(stage, stage)}:")
        for p in items:
            print(f"  {'OK ' if p['available'] else '-- '} {p['label']}" + ("" if p["available"] else f"   ({p['reason']})"))
    return 0


def cmd_serve(a):
    import uvicorn
    port = a.port or int(config.load_settings().get("port") or 8765)
    print(f"Stickman Studio running at http://localhost:{port}")
    uvicorn.run("studio.server.app:app", host=a.host, port=port, log_level="warning")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m studio", description="Stickman Studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    mk = sub.add_parser("make", help="make a video from a topic or a YouTube link")
    mk.add_argument("what", help="a topic in quotes, or a YouTube URL to remake")
    mk.add_argument("--minutes", type=float, default=10)
    mk.add_argument("--tier", choices=["free", "pro"], default="free")
    mk.add_argument("--llm", choices=["claude_cli", "anthropic", "ollama", "offline"])
    mk.add_argument("--voice", choices=["kokoro", "elevenlabs", "system"])
    mk.add_argument("--music", choices=["synth", "upload", "elevenlabs_music"])
    mk.add_argument("--image", choices=["local", "elevenlabs_image", "higgsfield"])
    mk.add_argument("--transcript", choices=["youtube_captions", "whisper_local", "elevenlabs_scribe"])
    mk.add_argument("--tone", default="funny but respectful")
    mk.add_argument("--faithfulness", choices=["close", "balanced", "loose"], default="balanced")
    mk.add_argument("--topic", default="", help="for a YouTube remake: optional focus/angle")
    mk.add_argument("--title", default="")
    mk.add_argument("--style", default="", help="optional reference YouTube URL for style (topic mode)")
    mk.add_argument("--extra", default="", help="extra instructions for the writer")
    mk.add_argument("--no-watch", action="store_true", help="don't look at the source video's frames")
    mk.add_argument("--no-share", action="store_true", help="skip the <30 MB share copy")
    mk.add_argument("--checkpoints", action="store_true", help="pause after script, storyboard and voice")
    mk.add_argument("--approve-spend", action="store_true", help="approve the printed estimates without asking again")
    mk.set_defaults(fn=cmd_make)
    r = sub.add_parser("resume")
    r.add_argument("slug")
    r.add_argument("--from", dest="from_stage", default=None)
    r.set_defaults(fn=cmd_resume)
    rr = sub.add_parser("rerender")
    rr.add_argument("slug")
    rr.add_argument("scenes", nargs="+")
    rr.set_defaults(fn=cmd_rerender)
    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sv = sub.add_parser("serve")
    sv.add_argument("--port", type=int, default=0)
    sv.add_argument("--host", default="127.0.0.1")
    sv.set_defaults(fn=cmd_serve)
    a = ap.parse_args(argv)
    config.ensure_dirs()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
