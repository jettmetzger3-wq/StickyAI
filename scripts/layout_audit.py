"""Audit (and optionally repair) the layout of every scene of a project. Nothing is rendered, no AI is used.

    python scripts/layout_audit.py <project-slug>            # report only
    python scripts/layout_audit.py <project-slug> --fix      # repair the scenes and save them

Prints, per scene, the layout score and what is wrong (high / medium / low), then the video-wide consistency findings.
See docs/layout.md for the rules.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--fix", action="store_true", help="repair what can be repaired by moving things and save the scenes")
    args = ap.parse_args()
    from studio.engine import layout as LY
    from studio.pipeline.project import Project, read_json, write_json
    pr = Project(args.slug)
    beats = (pr.script() or {}).get("beats") or []
    scenes = {}
    for i, b in enumerate(beats):
        if b.get("host") or not os.path.exists(pr.scene_path(i)):
            continue
        scenes[i] = read_json(pr.scene_path(i))
    changed = set()
    for i, sc in scenes.items():
        ctx = dict(text=beats[i].get("text", ""))
        if args.fix:
            _, fixes, _ = LY.fix_scene(sc, ctx)
            if fixes:
                changed.add(i)
        left = LY.audit(sc, ctx)
        print(f"scene {i + 1:>3}  layout {LY.score(left):.0%}" + ("  (repaired)" if i in changed else ""))
        for x in sorted(left, key=lambda z: LY.SEV_ORDER[z["sev"]]):
            print(f"           {x['sev']:6} {x['msg']}" + (f"  -> {x['fix']}" if x.get("fix") else ""))
    rows = LY.consistency(scenes, fix=args.fix)
    for r in rows:
        if r["fixed"]:
            changed.add(r["beat"])
        print(f"video-wide, scene {r['beat'] + 1}: {r['msg']}" + (" (fixed)" if r["fixed"] else ""))
    if args.fix:
        for i in changed:
            write_json(pr.scene_path(i), scenes[i])
        print(f"saved {len(changed)} repaired scene(s)")


if __name__ == "__main__":
    main()
