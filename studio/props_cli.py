"""python -m studio props ...   the shared prop library from the command line.

  props list [--names]     what is in the library (drawn in code, shipped hand-drawn, drawn for earlier videos)
  props gaps               objects stories wanted that no prop shows yet (most wanted first)
  props seed               draw the most wanted missing props in ONE request, kept for good (asks first)
  props sheet              a picture of every library prop: data/prop_library_sheet.png
"""
import os

from . import config


def cmd_list(a):
    from .engine import prop_library as PL
    from .knowledge import propindex as PX
    st = PX.stats()
    print(f"{st['builtin']} props drawn in code, {st['shipped']} hand-drawn library props, {st['variants']} variants, "
          f"{st['drawn']} drawn for earlier videos; {st['words']} words point at them; {st['gaps']} objects still missing.")
    if PL.ERRORS:
        print("files that could not be read:", "; ".join(PL.ERRORS))
    if a.names:
        for src, label in (("shipped", "hand-drawn"), ("user", "drawn for earlier videos")):
            names = sorted(n for n, d in PL.LIBRARY.items() if d["source"] == src)
            if names:
                print(f"\n{label}:\n  " + ", ".join(names))
        if PL.VARIANTS:
            print("\nvariants:\n  " + ", ".join(sorted(PL.VARIANTS)))
    return 0


def cmd_gaps(a):
    from .knowledge import propindex as PX
    rows = PX.gaps(a.limit)
    if not rows:
        print("No missing props recorded. (Stories add to this list when the plan wants an object no prop shows.)")
        return 0
    print("Objects stories wanted that no prop shows yet:")
    for word, n, ctx in rows:
        print(f"  {n:3d}x  {word:32s} {('e.g. ' + ctx) if ctx else ''}")
    print("\nDraw them with:  python -m studio props seed")
    return 0


def cmd_sheet(a):
    from .engine import prop_library as PL
    from .engine.custom_props import kit_sheet
    kit = [dict(d) for d in PL.LIBRARY.values()]
    out = os.path.join(config.DATA_DIR, "prop_library_sheet.png")
    kit_sheet(kit, out)
    print(f"{len(kit)} library props -> {out}")
    return 0


def cmd_seed(a):
    from . import prompts as PR
    from .engine import prop_library as PL
    from .engine.custom_props import clean_kit, MAX_DESIGNS
    from .engine.registry import PROPS
    from .knowledge import propindex as PX
    from .research_cli import _call_factory, _llm
    if a.words:
        wanted = [(w.strip(), "") for w in a.words.split(",") if w.strip() and not PX.covers(w.strip())]
    else:
        wanted = [(w, ctx) for w, _, ctx in PX.gaps(a.max)]
    wanted = wanted[:min(a.max, MAX_DESIGNS)]
    if not wanted:
        print("Nothing to draw: every object on the list is already covered. (python -m studio props gaps)")
        return 0
    llm = _llm(a.writer)
    prompt = PR.prop_design_prompt("Prop library", "props for later videos", [], wanted=wanted)
    print("Props to draw (one request, all of them together):")
    for w, ctx in wanted:
        print(f"  - {w}")
    paid = bool(getattr(llm, "paid", False))
    print(f"\nEstimate: 1 request to {llm.label}, about {len(prompt) // 4:,} tokens in and 3,000-6,000 out. "
          + ("This writer is PAID (billed by the provider)." if paid else "That uses your Claude plan like any other call; nothing is charged."))
    if not a.yes:
        try:
            ans = input("Draw these now? [y/N] ").strip().lower()
        except EOFError:
            ans = ""
        if ans not in ("y", "yes"):
            print("Cancelled; nothing was asked.")
            return 0
    data = _call_factory(llm)(llm, PR.PROP_DESIGN_SYSTEM, prompt, "props", False)
    kit = clean_kit(data, PROPS)
    made = [d["name"] for d in kit if PL.add_user_design(d)]
    PX.reset()
    PX.clear_gaps([w for w, _ in wanted if PX.covers(w)])
    print(f"Kept in the library for good: {', '.join(made) or 'nothing usable came back'}")
    left = [w for w, _ in wanted if not PX.covers(w)]
    if left:
        print("Still missing:", ", ".join(left))
    return 0


def register(sub):
    p = sub.add_parser("props", help="the shared prop library: list, missing props, draw the missing ones")
    ps = p.add_subparsers(dest="pcmd", required=True)
    ls = ps.add_parser("list")
    ls.add_argument("--names", action="store_true", help="also print every name")
    ls.set_defaults(fn=cmd_list)
    g = ps.add_parser("gaps", help="objects stories wanted that no prop shows")
    g.add_argument("--limit", type=int, default=40)
    g.set_defaults(fn=cmd_gaps)
    ps.add_parser("sheet", help="draw a picture of every library prop").set_defaults(fn=cmd_sheet)
    s = ps.add_parser("seed", help="draw the most wanted missing props in one request (asks first)")
    s.add_argument("--max", type=int, default=8, help="how many to draw at most (default 8)")
    s.add_argument("--words", default="", help="comma-separated objects to draw instead of the missing list")
    s.add_argument("--writer", default="", help="which writer (default: Claude Code)")
    s.add_argument("--yes", action="store_true", help="don't ask for the go-ahead")
    s.set_defaults(fn=cmd_seed)
