"""Stickman Studio 2.0 demonstration: a SHORT section of the American Revolution through the whole local pipeline.

    python scripts/demo/run_american_revolution.py [--out DIR] [--no-render]

What is real and what is stood in (said plainly, so nothing here is mistaken for more than it is):
  * `american_revolution_research.json` is real web research (WebSearch, 6 searches, official sources). The pages
    themselves could not be opened in that sandbox, so every claim's evidence is marked as a search-result summary.
  * The "writer" below stands in for the Claude call: it returns the script and the director's plan in EXACTLY the
    schemas the real prompts ask for. On your PC, Claude Code writes them; everything else here is the real code path.
  * Everything after the writer (claim linking, coverage, world state, specs, muted test, QC, render, mix) is local code.

It uses a throw-away data folder, so it never touches your projects or your research cache.
"""
import argparse
import json
import os
import shutil
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
HERE = os.path.dirname(os.path.abspath(__file__))

SCRIPT = {
    "title": "How America Became a Country",
    "topic": "The American Revolution",
    "cast": [
        {"name": "George Washington", "kind": "tricorn", "hat_color": "black", "coat": "#2B3F8C"},
        {"name": "James Madison", "kind": "tricorn", "hat_color": "black", "coat": "#2A2A2A"},
        {"name": "Colonist", "kind": "tricorn", "hat_color": "#5A4632", "coat": "#6B4F3A"},
    ],
    "facts": [],
    "beats": [
        {"mood": "fun", "part": "hook",
         "text": "On a December night in 1773, colonists dumped 342 chests of tea into Boston Harbor.",
         "purpose": "start with the protest everyone remembers", "location": "Boston Harbor",
         "visual": "colonists tipping tea chests off a ship at night"},
        {"mood": "fun", "part": "intro",
         "text": "Back then, thirteen British colonies sat along the Atlantic coast, an ocean away from England.",
         "purpose": "explain who the colonists were and where", "location": "Atlantic coast of North America",
         "visual": "map of the 13 colonies with England across the ocean"},
        {"mood": "tense", "part": "story",
         "text": "Parliament's Stamp Act taxed their legal papers and newspapers, and the colonists shouted taxation without representation.",
         "purpose": "show why they were angry", "location": "the colonies",
         "visual": "a stamped paper and an angry crowd"},
        {"mood": "tense", "part": "story",
         "text": "So in 1776 the delegates in Philadelphia approved the Declaration of Independence, and Thomas Jefferson wrote most of it.",
         "purpose": "the break with Britain", "location": "Philadelphia",
         "visual": "the Declaration of Independence on a desk"},
        {"mood": "somber", "part": "story",
         "text": "Then in 1781 Cornwallis surrendered at Yorktown, and the war was finally won.",
         "purpose": "the war ends", "location": "Yorktown",
         "visual": "the British surrender at Yorktown"},
        {"mood": "fun", "part": "payoff",
         "text": "Six years later, in 1787, Madison and the delegates signed the Constitution in Philadelphia, and the new country had its rulebook.",
         "purpose": "the payoff: a country with rules", "location": "Philadelphia",
         "visual": "delegates signing the Constitution"},
    ],
}

# What the director would answer: a pattern per beat plus "needs" (what the viewer must SEE). The composer builds the scene.
PLAN = [
    {"beat": 0, "pattern": "FAMOUS_EVENT", "needs": ["Boston Harbor", "tea chests", "colonists", "ship", "342"], "slots": {}},
    {"beat": 1, "pattern": "COLONIZATION", "needs": ["13 colonies", "England", "ocean", "Atlantic coast"], "slots": {}},
    {"beat": 2, "pattern": "PROTEST", "needs": ["Stamp Act", "newspaper", "colonists", "tax"], "slots": {}},
    {"beat": 3, "pattern": "DOCUMENT_SIGNING", "needs": ["Philadelphia", "Declaration of Independence", "Thomas Jefferson", "delegates"], "slots": {}},
    {"beat": 4, "pattern": "FAMOUS_EVENT", "needs": ["Yorktown", "Cornwallis", "surrender", "1781"], "slots": {}},
    {"beat": 5, "pattern": "DOCUMENT_SIGNING", "needs": ["Philadelphia", "Constitution", "James Madison", "delegates", "1787"], "slots": {}},
]


class StandInWriter:
    """Answers like the real writer would, in the schemas the prompts demand. Counts every call so the demo can show them."""
    id, label, paid, supports_images, supports_web, short = "standin", "Stand-in writer", False, False, True, "Stand-in"
    parallel, batch_beats, examples = 2, 12, 20

    def __init__(self, research):
        self.research, self.calls = research, []

    def available(self):
        return True, ""

    def complete(self, system, prompt, schema=None, images=(), label="", **kw):
        self.calls.append(label)
        if label == "research":
            return json.dumps(self.research), {}
        if label == "script":
            return json.dumps(SCRIPT), {}
        if label.startswith("plan"):
            return json.dumps({"plan": PLAN}), {}
        if label in ("props", "facts"):
            return json.dumps({"props": [], "checks": [], "rewrites": []}), {}
        raise AssertionError("unexpected AI call: " + label)


def banner(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "demo-american-revolution"))
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)

    from studio import cache, config
    config.DATA_DIR = os.path.join(out, "data")
    config.PROJECTS_DIR = os.path.join(out, "projects")
    from studio.pipeline import project as PRJ
    PRJ.PROJECTS_DIR = config.PROJECTS_DIR
    cache.clear()
    from studio.pipeline import stages, estimate
    from studio.pipeline.project import new_project
    from studio.pipeline.runner import Ctx
    from studio.research import budget as BD, store as ST

    research = json.load(open(os.path.join(HERE, "american_revolution_research.json"), encoding="utf-8"))
    writer = StandInWriter(research)
    real_provider = stages.provider
    use = {"writer": writer}
    stages.provider = lambda meta, stage, ctx=None, task=None: (
        real_provider(meta, stage, ctx, task) if stage in ("voice", "music", "image", "shorts", "transcript") else use["writer"])
    if args.no_render:
        stages.render_previews = lambda *a, **k: None

    def make(name):
        return new_project(name, "topic", topic="The American Revolution",
                           options=dict(minutes=1, gen_mode="normal", mascot=False,
                                        research=dict(mode="normal")), providers=dict(voice="system"))

    # ---- 1. estimate BEFORE anything runs (nothing researched yet)
    banner("1. ESTIMATE BEFORE GENERATION (nothing has run yet)")
    pr = make("American Revolution demo")
    e = estimate.estimate_video(pr)
    print(json.dumps(dict(research=e["research"], usage_level=e["usage_level"], levels=e["levels"],
                          ai_calls=sum(i["calls"] for i in e["items"])), indent=1))

    # ---- 2. script stage: web research (budget) -> cache -> script -> claim linking -> fact-check
    banner("2. RESEARCH + SCRIPT")
    t0 = time.time()
    ctx = Ctx(pr, "script")
    stages.stage_script(ctx)
    rep = json.load(open(pr.p("research", "report.json")))
    print("research report:", json.dumps(rep, indent=1)[:1500])
    print("AI calls so far:", writer.calls)
    claims = json.load(open(pr.p("research", "claims.json")))
    linked = [c for c in claims if c.get("used_in_scenes")]
    print(f"claims: {len(claims)}, used by the script: {len(linked)}")
    for c in linked[:8]:
        print(f"  scenes {c['used_in_scenes']}  [{c['confidence']}/{c.get('tier')}]  {c['claim'][:90]}")
    script = pr.script()
    print("fact-check:", json.dumps(script.get("factcheck")), "| unsupported:", (script.get("evidence") or {}).get("unsupported"))
    print("narrative beats:")
    for i, b in enumerate(script["beats"]):
        print(f"  {i}. [{b.get('part') or 'host'}] {b.get('purpose', '(channel outro card)')}  @ {b.get('location')}  -> {b.get('visual')}")

    # ---- 3. storyboard: semantic requirements, coverage, world state, specs, muted test
    banner("3. STORYBOARD (visual requirements, coverage, world state, muted test)")
    stages.stage_storyboard(Ctx(pr, "storyboard"))
    rv = json.load(open(pr.p("review.json")))
    print("coverage mean %.0f%%  failed=%s blocked=%s" % (100 * rv["coverage"]["mean"], rv["coverage"]["failed"], rv["coverage"]["blocked"]))
    for i, v in sorted(rv["coverage"]["per_beat"].items(), key=lambda kv: int(kv[0])):
        print(f"  beat {i}: coverage {v:.0%}  missing={rv['coverage']['missing'].get(i, [])}")
    print("muted test: score %.2f" % rv["muted"]["score"], json.dumps(rv["muted"].get("weak") or rv["muted"].get("issues") or [])[:300])
    lay = rv.get("layout") or {}
    print("layout: mean %.0f%%, %d open, escalate=%s, per scene %s" % (100 * lay.get("mean", 1), len(lay.get("open") or []), lay.get("escalate"), lay.get("per_beat")))
    for x in [i for i in rv["issues"] if i["check"] == "layout"][:12]:
        print("   layout %s #%s: %s" % ("fixed" if x["fixed"] else x["severity"], x["beat"], x["msg"]))
    sb = json.load(open(pr.p("storyboard.json")))
    print("patterns:", [sb["scenes"][str(i)].get("pattern") for i in range(len(script["beats"]))])
    ws = json.load(open(pr.p("world_state.json")))
    print("world state per scene (place, year):")
    for i in sorted(ws["scenes"], key=int):
        s = ws["scenes"][i]
        print(f"  {i}: {s.get('location', {}).get('name') or s.get('location', {}).get('region')}, {s.get('period', {}).get('year')}")
    print("scene specs:", sorted(os.listdir(pr.p("storyboard", "specs"))), "| preview:", pr.p("storyboard", "preview.html"))
    chars = sorted(os.listdir(pr.p("characters"))) if os.path.isdir(pr.p("characters")) else []
    print("character memory (same look in every scene):", chars)
    print("AI calls after storyboard:", writer.calls)

    # ---- 4. second video on the same topic: cache hit, no research
    banner("4. A SECOND VIDEO ON THE SAME TOPIC (cache)")
    before = len(writer.calls)
    pr2 = new_project("American Revolution demo two", "topic", topic="The American Revolution",
                      options=dict(minutes=1, gen_mode="normal", mascot=False, extra="open with the Stamp Act"))
    stages.stage_script(Ctx(pr2, "script"))
    new = writer.calls[before:]
    rep2 = json.load(open(pr2.p("research", "report.json")))
    print("AI calls for the second video (different angle, same topic):", new, "-> research is NOT among them")
    print("report:", json.dumps(rep2["budget"]), "cached:", rep2["cached"])

    # ---- 5. budget guard: a thin cache + a tiny budget pauses and asks
    banner("5. BUDGET GUARD (tiny budget on a new topic asks before going on)")
    thin = dict(research, claims=research["claims"][:4], sources=research["sources"][:1])
    w3 = StandInWriter(thin)
    use["writer"] = w3
    pr3 = new_project("budget demo", "topic", topic="The Stamp Act crisis in Virginia",
                      options=dict(minutes=1, gen_mode="normal", mascot=False, research=dict(max_queries=2)))
    try:
        stages.stage_script(Ctx(pr3, "script"))
        print("NO PAUSE (unexpected)")
    except BD.ResearchBudgetReached as ex:
        print("paused for approval:", json.dumps(dict(gaps=ex.info["gaps"], proposal=ex.info["proposal"])))
    use["writer"] = writer

    # ---- 6. render
    if not args.no_render:
        banner("6. LOCAL RENDER (offline voice, no AI, no cost)")
        from studio.pipeline import runner
        t0 = time.time()
        status = runner.run(pr, start="voice", stop_after="mix")
        print("status:", status, "in %.0fs" % (time.time() - t0))
        for f in ("final/video.mp4", "final/video_nocaps.mp4"):
            p = pr.p(*f.split("/"))
            if os.path.exists(p):
                print(f, os.path.getsize(p) // 1024, "KB")

    banner("7. CLAUDE USAGE, BEFORE vs AFTER (estimate for a 10-minute video; nothing is run)")
    print(f"{'way':<28}{'AI calls':>9}{'tokens':>10}   level")
    for name, opts in (("v1: write every scene", dict(storyboard_engine="classic", research=dict(enabled=False))),
                       ("v2 normal", dict()), ("v2 fast", dict(gen_mode="fast"))):
        p10 = new_project("estimate " + name, "topic", topic="The Boer War",
                          options=dict(dict(minutes=10, mascot=False, gen_mode="normal"), **opts))
        e10 = estimate.estimate_video(p10)
        print(f"{name:<28}{sum(i['calls'] for i in e10['items']):>9}{sum(i['in_tok'] + i['out_tok'] for i in e10['items']):>10}   {e10['usage_level']}")
    print("(rendering, animation, audio and video are local in every row: no AI, no cost)")

    banner("8. SOURCES USED (written into the description)")
    for s in stages.used_sources(pr):
        print(f"  {s['organization'] or s['title']}: {s['url']}  ({len(s['claims'])} claims)")
    print("\nproject folder:", pr.dir)
    json.dump(dict(slug=pr.slug, dir=pr.dir, calls=writer.calls), open(os.path.join(out, "result.json"), "w"))


if __name__ == "__main__":
    main()
