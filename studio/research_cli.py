"""Grow the research library from real videos, on a computer that can reach YouTube:

    python -m studio research add <youtube url>     download a small copy, find every cut, grab one frame per shot,
                                                    and write research/videos/<id>.md with the shot table to fill in
    python -m studio research list                  which videos are queued / analysed
    python -m studio research build-docs            rewrite research/scene-patterns.md from knowledge/patterns.json
    python -m studio research learn <file.json>     add patterns you distilled to data/knowledge/patterns_user.json

Nothing here asks an AI anything: the shot cuts, shot lengths and narration per shot are measured with ffmpeg and the
video's own captions. Frames are kept in data/research_frames/ (never in the repository: they are other people's
artwork); the markdown only holds the production logic you write down. Then open the video's file in Claude Code
(`claude`) and ask it to fill the "what is on screen" column from the contact sheets, or do it yourself.
"""
import json
import os
import re
import statistics
import subprocess

from . import config
from .knowledge import patterns as PT

HERE = os.path.dirname(os.path.abspath(__file__))
RESEARCH = os.path.join(os.path.dirname(HERE), "research")
FRAMES = os.path.join(config.DATA_DIR, "research_frames")


def find_cuts(video, threshold=0.28):
    """Times (seconds) where the picture cuts to a new scene, measured by ffmpeg's scene-change detector."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-filter:v", f"select='gt(scene,{threshold})',showinfo",
                        "-an", "-f", "null", "-"], capture_output=True, text=True, errors="replace")
    return [float(m.group(1)) for m in re.finditer(r"pts_time:([0-9.]+)", r.stderr)]


def shots_from_cuts(cuts, duration, min_len=0.8):
    edges = [0.0] + [c for c in cuts if 0 < c < duration] + [duration]
    shots = []
    for a, b in zip(edges, edges[1:]):
        if b - a >= min_len or not shots:
            shots.append([a, b])
        else:
            shots[-1][1] = b
    return shots


def narration_for(segments, a, b):
    return " ".join(s["text"].strip() for s in segments if a - 0.2 <= s["start"] < b).strip()


def pacing(shots):
    lens = [b - a for a, b in shots]
    if not lens:
        return {}
    return dict(shots=len(lens), avg=round(sum(lens) / len(lens), 1), median=round(statistics.median(lens), 1),
                shortest=round(min(lens), 1), longest=round(max(lens), 1), per_minute=round(len(lens) / (sum(lens) / 60), 1))


def stamp(t):
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def cmd_add(a):
    from .pipeline import source as S
    from .providers import video_id
    vid = video_id(a.url)
    if not vid:
        raise SystemExit("that doesn't look like a YouTube link")
    work = os.path.join(FRAMES, vid)
    os.makedirs(work, exist_ok=True)
    print("reading video info...")
    meta = S.fetch_meta(a.url)
    print("reading captions...")
    segs = []
    try:
        from .providers import YouTubeCaptions
        segs = YouTubeCaptions().transcript(a.url, meta, os.path.join(work, "tmp"), progress=lambda m, f: None)
    except Exception as e:
        print(f"  (no captions: {str(e)[:100]}; the narration column will be empty)")
    print("downloading a small copy...")
    video = S.download_lowres(a.url, os.path.join(work, "tmp"))
    duration = float(meta.get("duration") or 0)
    print("finding every cut...")
    shots = shots_from_cuts(find_cuts(video), duration)
    shots = shots[:a.max_shots]
    frames = []
    os.makedirs(os.path.join(work, "frames"), exist_ok=True)
    for i, (s0, s1) in enumerate(shots):
        path = os.path.join(work, "frames", f"shot_{i:03d}.jpg")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{(s0 + s1) / 2:.2f}", "-i", video, "-frames:v", "1",
                        "-vf", "scale=384:-2", "-q:v", "4", path], check=False)
        if os.path.exists(path):
            frames.append((s0, path))
    sheets = S.contact_sheets(frames, os.path.join(work, "sheets"), cols=4, rows=3)
    md = os.path.join(RESEARCH, "videos", f"{vid}.md")
    os.makedirs(os.path.dirname(md), exist_ok=True)
    rows = []
    for i, (s0, s1) in enumerate(shots):
        rows.append(f"| {i} | {stamp(s0)} | {s1 - s0:.1f} | {narration_for(segs, s0, s1)[:140]} |  |  |  |  |  |")
    pc = pacing(shots)
    with open(md, "w", encoding="utf-8") as f:
        f.write(TEMPLATE.format(title=meta.get("title", ""), channel=meta.get("channel", ""), vid=vid,
                                duration=stamp(duration), url=a.url, pacing=json.dumps(pc), sheets=os.path.join(work, "sheets"),
                                rows="\n".join(rows)))
    print(f"\nwrote {md}")
    print(f"pacing: {pc}")
    print(f"contact sheets (look at these to fill the table): {os.path.join(work, 'sheets')}")
    print("Next: open that file in Claude Code and ask it to fill the shot table from the sheets, then copy the rules that "
          "repeat into research/*-patterns.md and `python -m studio research learn`.")


TEMPLATE = """# {title}

Channel: {channel} · Video id: `{vid}` · Length: {duration} · {url}
Status: **measured shots + narration; the visual columns still need to be filled from the contact sheets**
Frames (not in the repository, other people's artwork): `{sheets}`
Measured pacing: `{pacing}`

## Shot table
| # | start | secs | narration | on screen (place, characters, doing what) | props and the text on them | camera | transition in | rule it shows |
|---|-------|------|-----------|-------------------------------------------|----------------------------|--------|---------------|---------------|
{rows}

## "WHEN the narrator says X, the animation does Y"
(write the repeating rules here, one per line, with the shot numbers that show it)

## Patterns to add
(for each: the pattern id from knowledge/patterns.json or a new one; slots; sequence; camera; timing; transitions)
"""


def cmd_list(a):
    d = os.path.join(RESEARCH, "videos")
    if not os.path.isdir(d):
        print("no videos yet")
        return
    for fn in sorted(os.listdir(d)):
        if fn.endswith(".md") and not fn.startswith("_"):
            head = open(os.path.join(d, fn), encoding="utf-8").read(900)
            status = re.search(r"Status: (.*)", head)
            print(f"{fn[:-3]:14} {status.group(1) if status else ''}")


def cmd_build_docs(a):
    os.makedirs(RESEARCH, exist_ok=True)
    out = ["# Scene patterns", "",
           "Generated from `studio/knowledge/patterns.json` by `python -m studio research build-docs`. Edit the JSON (or add "
           "your own in `data/knowledge/patterns_user.json`), then rebuild this file. Each pattern is a reusable production "
           "rule: when it applies, who is on screen, what happens in what order, what the camera does and how it is timed.",
           "", "Provenance: every pattern lists the videos it was verified against. `seed` means it is a documented technique "
           "that has NOT yet been checked frame by frame.", ""]
    for p in PT.load()["patterns"]:
        t = p["triggers"]
        out += [f"## {p['id']}: {p['label']}", "", f"**Use when:** {p['when']}", ""]
        if p.get("sequence"):
            out += ["**Visual sequence**", ""] + [f"{i}. {s}" for i, s in enumerate(p["sequence"], 1)] + [""]
        out += [f"- **Characters:** {p['characters']}", f"- **Actions:** {p['actions'] or '-'}", f"- **Background:** {p['background']}",
                f"- **Props:** {p['props']}", f"- **Camera:** {p['camera']}", f"- **Timing:** {p['timing']}",
                f"- **Transitions:** {', '.join(p['transitions'])}", f"- **Tone:** {', '.join(p['tone'])}",
                f"- **Slots:** " + "; ".join(f"`{k}` ({v})" for k, v in p["slots"].items()),
                f"- **Narration cues:** events {', '.join(t['events']) or '-'}; words {', '.join(t['words'][:10]) or '-'}",
                f"- **Example narration:** " + " / ".join(f'"{e}"' for e in p.get("examples", [])),
                f"- **Provenance:** {'verified on: ' + '; '.join(p['verified']) if p.get('verified') else p.get('source', 'seed')}", ""]
    with open(os.path.join(RESEARCH, "scene-patterns.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"wrote research/scene-patterns.md ({len(PT.load()['patterns'])} patterns)")


def cmd_learn(a):
    """Add patterns (or update verified lists) from a JSON file: {"patterns": [...]} in the same shape as patterns.json."""
    with open(a.file, encoding="utf-8") as f:
        new = json.load(f).get("patterns") or []
    path = os.path.join(config.DATA_DIR, "knowledge", "patterns_user.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cur = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            cur = {p["id"]: p for p in json.load(f).get("patterns", [])}
    for p in new:
        if p.get("id") and p.get("layout"):
            cur[p["id"].upper()] = p
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(patterns=list(cur.values())), f, indent=1)
    PT.load.cache_clear()
    PT.by_id.cache_clear()
    print(f"{len(new)} pattern(s) saved in {path}")


# ---------------------------------------------------------------- topic research and reference images (no project needed)
class _Ctx:
    def log(self, m):
        print("  " + str(m))

    warn = log


def _llm(name):
    from . import providers as P
    llm = P.get("llm", name or "claude_cli")
    ok, why = llm.available()
    if not ok:
        raise SystemExit(f"{llm.label} is not available: {why}")
    return llm


def _call_factory(llm):
    from .providers import extract_json

    def call(l, system, prompt, label, web):
        text, _ = l.complete(system, prompt, label=label, web=bool(web))
        return extract_json(text) if isinstance(text, str) else text
    return call


def cmd_topic(a):
    """Research a topic inside the budget and keep it for every later video (data/research_cache/<topic>/)."""
    from .research import budget as BD, engine as EN, store as ST
    cfg = BD.resolve_config(config.load_settings(), {"research_mode": a.mode} if a.mode else {}, "normal")
    if a.max_queries:
        cfg["max_queries"] = a.max_queries
    if a.max_sources:
        cfg["max_sources"] = a.max_sources
    llm = _llm(a.writer)
    print(f"Researching {a.topic!r} in {cfg['mode']} mode: up to {cfg['max_queries']} searches, {cfg['max_sources']} sources "
          f"(Claude Code searches the web on your plan; nothing is charged).")
    grant = None
    while True:
        try:
            r = EN.research_topic(_Ctx(), llm, _call_factory(llm), a.topic, a.minutes, cfg, focus=a.focus or (), grant=grant)
            break
        except BD.ResearchBudgetReached as e:
            i = e.info
            print(f"\nThe budget ({i['budget']['queries']} searches, {i['budget']['sources']} sources) is used up and the evidence still has gaps:")
            for g in i["gaps"]:
                print("  -", g)
            pr_ = i["proposal"]
            ans = input(f"Research {pr_['queries']} more searches / {pr_['sources']} more sources? [y/N] ").strip().lower()
            if ans != "y":
                cfg["require_approval_for_extra_research"] = False
                continue
            grant = dict(queries=pr_["queries"], sources=pr_["sources"], seconds=pr_["seconds"])
    print(f"\n{len(r.claims)} claims, {len(r.sources)} sources, {'reused from the saved research' if r.cached else 'new'}; "
          f"saved in {os.path.join(ST.root(), r.slug)}")
    if r.gaps:
        print("Known gaps:", "; ".join(r.gaps))


def cmd_cache(a):
    from .research import store as ST
    if not os.path.isdir(ST.root()):
        print("no research saved yet")
        return
    for d in sorted(os.listdir(ST.root())):
        m = ST.load(d)
        if m:
            md = m["metadata"]
            print(f"{d:40s} {md.get('claims', 0):3d} claims {md.get('sources', 0):3d} sources  mode {md.get('mode', '?'):6s} gaps: {len(md.get('gaps') or [])}")


def cmd_reference_add(a):
    """Describe a reference image's composition (one vision request, cached), rebuild it with the studio's own art."""
    from .pipeline import reference as RF
    llm = _llm(a.writer)
    comp, cached = RF.analyze(llm, a.image)
    scene, rep = RF.to_scene(comp)
    out = os.path.splitext(a.image)[0] + ".scene.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scene, f, indent=1)
    path = RF.save_pattern(os.path.dirname(RESEARCH), os.path.basename(a.image), comp, rep)
    print(("reused the saved analysis" if cached else "analysed the image (1 request)") + f"; scene -> {out}; pattern note -> {path}")
    print("reused:", rep["reused"], "| substituted:", rep["substituted"], "| missing assets:", rep["missing"])


def cmd_reference_convert(a):
    from .pipeline import reference as RF
    comp = json.load(open(a.composition, encoding="utf-8"))
    scene, rep = RF.to_scene(comp)
    out = os.path.splitext(a.composition)[0] + ".scene.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scene, f, indent=1)
    print(f"scene -> {out}\n", rep)


def register(sub):
    r = sub.add_parser("research", help="grow the research library from real videos (needs YouTube access)")
    rs = r.add_subparsers(dest="rcmd", required=True)
    ad = rs.add_parser("add")
    ad.add_argument("url")
    ad.add_argument("--max-shots", type=int, default=150)
    ad.set_defaults(fn=cmd_add)
    rs.add_parser("list").set_defaults(fn=cmd_list)
    rs.add_parser("build-docs").set_defaults(fn=cmd_build_docs)
    ln = rs.add_parser("learn")
    ln.add_argument("file")
    ln.set_defaults(fn=cmd_learn)
    tp = rs.add_parser("topic", help="research a topic inside the budget and save it for later videos")
    tp.add_argument("topic")
    tp.add_argument("--mode", choices=["fast", "normal", "deep"])
    tp.add_argument("--minutes", type=float, default=10)
    tp.add_argument("--focus", nargs="*", help="angles this video must cover")
    tp.add_argument("--max-queries", type=int)
    tp.add_argument("--max-sources", type=int)
    tp.add_argument("--writer", default="claude_cli")
    tp.set_defaults(fn=cmd_topic)
    rs.add_parser("cache", help="list the topics researched so far").set_defaults(fn=cmd_cache)
    ref = sub.add_parser("reference", help="use a reference image as a blueprint for a scene")
    rf = ref.add_subparsers(dest="rfcmd", required=True)
    ra = rf.add_parser("add")
    ra.add_argument("image")
    ra.add_argument("--writer", default="claude_cli")
    ra.set_defaults(fn=cmd_reference_add)
    rc = rf.add_parser("convert", help="composition JSON -> scene JSON (no AI)")
    rc.add_argument("composition")
    rc.set_defaults(fn=cmd_reference_convert)
