"""Measure how much AI a video uses, the old way vs the new way, with a stand-in writer (no network, no cost).

    python scripts/measure_usage.py

The pipeline code is the real code: the prompts are the real prompts, so the INPUT sizes are real. The stand-in's answers
are realistic in size (scene answers reuse the size of the studio's own example scenes), so the OUTPUT sizes are close but
not measured from a real model. Tokens are characters / 3.6. Claude Code's own per-call overhead is not included.
"""
import json
import os
import sys
import tempfile
import time

_tmp = tempfile.mkdtemp(prefix="studio_measure_")
os.environ["STUDIO_DATA_DIR"] = os.path.join(_tmp, "data")
os.environ["STUDIO_PROJECTS_DIR"] = os.path.join(_tmp, "projects")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from studio import cache, usage, config                      # noqa: E402
from studio.pipeline import stages, modes                    # noqa: E402
from studio.pipeline.project import new_project              # noqa: E402
from studio.pipeline.runner import Ctx                       # noqa: E402
from studio import prompts as PR                             # noqa: E402

COLD_WAR = [  # (part, mood, text)
    ("hook", "fun", "The two most powerful countries on Earth spent 45 years trying not to fight, and almost blew up the planet anyway."),
    ("intro", "fun", "So what was the Cold War? A long standoff between the United States and the Soviet Union that never became a direct war."),
    ("intro", "fun", "Instead they fought with spies, space rockets, nuclear weapons and proxy wars in other people's countries."),
    ("intro", "fun", "First we'll see how it started in 1945, then the scariest moments, and finally how it ended in 1991."),
    ("story", "fun", "In 1945 the Allies had just beaten Germany, and Roosevelt, Churchill and Stalin met in Yalta to carve up Europe."),
    ("story", "tense", "Stalin promised free elections in Eastern Europe, and then, famously, did not hold any."),
    ("story", "tense", "Churchill said an iron curtain had come down across Europe, which is a dramatic way to say nobody could visit."),
    ("story", "fun", "President Truman answered with the Truman Doctrine in 1947: America would help any country resisting communism."),
    ("story", "fun", "Then came the Marshall Plan, which poured 13 billion dollars into rebuilding Western Europe."),
    ("story", "tense", "In 1948 Stalin blockaded West Berlin, so America flew in food and coal for almost a year."),
    ("story", "fun", "Pilots dropped candy on parachutes for the Berlin kids, which is the nicest thing anyone did in this entire war."),
    ("story", "tense", "In 1949 the Soviets tested their own atomic bomb, and suddenly both sides could end the world."),
    ("story", "tense", "The same year, Mao Zedong won the civil war in China, and the communist side got a lot bigger."),
    ("story", "tense", "In 1950 North Korea invaded South Korea, and the Cold War turned hot, with armies marching across a map."),
    ("story", "somber", "About 3 million people died in Korea before a ceasefire in 1953 left the border exactly where it started."),
    ("story", "fun", "Back home, Senator McCarthy accused half of America of being a secret communist, with almost no evidence."),
    ("story", "fun", "Stalin died in 1953, and Nikita Khrushchev took over, banging his shoe on a desk at the United Nations."),
    ("story", "tense", "In 1957 the Soviets launched Sputnik, a beeping metal ball that made Americans panic about the sky."),
    ("story", "fun", "America answered with NASA, and the space race began, with both sides racing to put a man on the moon."),
    ("story", "tense", "In 1961 East Germany built the Berlin Wall overnight, splitting a city and thousands of families in two."),
    ("story", "tense", "Then in 1962 a spy plane photographed Soviet missiles in Cuba, only 90 miles from Florida."),
    ("story", "tense", "President Kennedy ordered a naval blockade, and for 13 days the world held its breath."),
    ("story", "fun", "Finally Khrushchev blinked, the missiles left Cuba, and America quietly removed its own missiles from Turkey."),
    ("story", "fun", "Both leaders then installed a hotline so they could call each other instead of ending civilisation."),
    ("story", "tense", "In the 1960s America sent troops to Vietnam, and the Cold War turned into a long and bloody jungle war."),
    ("story", "somber", "More than 58,000 Americans and perhaps 2 million Vietnamese died before the United States pulled out in 1973."),
    ("story", "fun", "In 1969 Neil Armstrong walked on the moon, which the Americans considered a pretty decisive win in the space race."),
    ("story", "fun", "Nixon visited Mao in China in 1972, shocking everyone by shaking hands with the enemy of his enemy."),
    ("story", "fun", "That era was called detente, which is French for both sides being tired of nearly dying."),
    ("story", "tense", "In 1979 the Soviets invaded Afghanistan, and it became their Vietnam, a war they could not win."),
    ("story", "tense", "Ronald Reagan won in 1980, called the Soviet Union an evil empire and spent huge sums on weapons."),
    ("story", "fun", "The Soviet economy, already creaking, could not keep up, and the shelves in Moscow's shops stayed empty."),
    ("story", "fun", "In 1985 Mikhail Gorbachev took power and tried to reform things with two Russian words: glasnost and perestroika."),
    ("story", "tense", "Reforms turned out to be like pulling one brick out of a wall: everything started to fall."),
    ("story", "fun", "On November 9, 1989, East Germany opened the border, and crowds in Berlin tore the Wall down with hammers."),
    ("story", "fun", "One by one, the communist governments of Eastern Europe collapsed, mostly without a single shot."),
    ("story", "somber", "On December 25, 1991, Gorbachev resigned, the red flag came down over the Kremlin, and the Soviet Union ceased to exist."),
    ("payoff", "fun", "The two superpowers never fought directly, and the world's biggest standoff ended not with a bang but with a resignation speech."),
    ("payoff", "fun", "Which just goes to show that sometimes the best way to win a war is to outlast the other guy's budget."),
]
SCRIPT_CAST = [dict(name="Truman", kind="tophat_gray", hat_color="gray", coat="#3A3A4A", look="", role="US president"),
               dict(name="Stalin", kind="army", hat_color="khaki", coat="#6B6B3A", look="mustache", role="Soviet dictator"),
               dict(name="Khrushchev", kind="civ", hat_color="", coat="#555555", look="", role="Soviet leader"),
               dict(name="Kennedy", kind="civ", hat_color="", coat="#2B3F8C", look="", role="US president"),
               dict(name="Americans", kind="america", hat_color="", coat="", look=""),
               dict(name="Soviets", kind="ussr", hat_color="", coat="#C8302B", look="")]


class StandIn:
    """Answers every request with valid JSON of a realistic size, and remembers what it was asked."""
    id, label, paid, supports_images, supports_web, short = "claude_cli", "Stand-in writer", False, False, True, "Claude"
    parallel, batch_beats, examples = 3, 12, 20

    def __init__(self, variant=False):
        self.ex = PR.load_examples()
        self.k = 0
        self.variant = variant              # a second video on the same topic: different words, so nothing but research/props matches

    def available(self):
        return True, ""

    def complete(self, system, prompt, schema=None, images=(), label="", **kw):
        if label == "script":
            pre = "Here's another angle: " if self.variant else ""
            return json.dumps(dict(title="The Cold War", topic="the Cold War", facts=[], cast=SCRIPT_CAST,
                                   beats=[dict(mood=m, text=(pre + t if (self.variant and k == 4) else t).replace("Truman", "Truman" if not self.variant else "Harry Truman") if self.variant else t, part=p)
                                          for k, (p, m, t) in enumerate(COLD_WAR)])), {}
        if label == "facts":
            return json.dumps(dict(checks=[], rewrites=[])), {}
        if label == "flow":
            return json.dumps(dict(rewrites=[])), {}
        if label == "research":
            return json.dumps(dict(summary="x", people=[dict(name="Truman", role="US president", years="1884-1972", look="gray hat", trait="plain")],
                                   places=[], documents=[dict(name="Truman Doctrine", lines=["The US will help", "nations resisting", "communism."])],
                                   numbers=[], timeline=[dict(year=1947, event="Truman Doctrine")], visuals=[])), {}
        if label == "props":
            return json.dumps(dict(props=[])), {}
        if label == "package":
            return json.dumps(dict(titles=["The Cold War"], hook="h", chapters=[dict(beat=0, title="Start")], question="q", tags=["t"],
                                   hashtags=["#history"], thumbnail=dict(line1="COLD WAR", line2="WHY?", small_kind="civ", big_kind="ussr", image_prompt="x"))), {}
        if label.startswith("plan"):
            import re
            idx = [int(x) for x in label.split()[1].split("-")]
            from studio.knowledge import patterns as PT
            out = []
            for i in range(idx[0], idx[1] + 1):
                m = re.search(rf"\[{i}\] \(\w+\) .*?\n(?:\s+->\s*(.*))?", prompt)
                cand = re.search(r"candidates: ([A-Z_, ]+)", m.group(1) or "") if m else None
                pid = (cand.group(1).split(",")[0].strip() if cand else "STORY_MOMENT")
                if i % 9 == 4:
                    pid = "CUSTOM"                      # the AI asks for the full scene writer on about one beat in nine
                out.append(dict(beat=i, pattern=pid, slots={}, say=[dict(who="", text="Wait, what?")]))
            return json.dumps(dict(plan=out)), {}
        if label.startswith("storyboard") or label.startswith("fix"):
            idx = [int(x) for x in label.split()[-1].split("-")]
            scenes = []
            for i in range(idx[0], idx[1] + 1):
                self.k += 1
                scenes.append(dict(beat=i, scene=self.ex[self.k % len(self.ex)]["scene"]))   # as big as the studio's own example scenes
            return json.dumps(dict(scenes=scenes)), {}
        raise AssertionError("unexpected request: " + label)


def run_video(title, opts, standin):
    pr = new_project(title, "topic", topic="the Cold War", options=dict(minutes=5, mascot=False, **opts))
    stages.provider = lambda meta, stage, ctx=None, task=None: standin
    stages.render_previews = lambda *a, **k: None
    ctx = Ctx(pr, "script")
    stages.stage_script(ctx)
    stages.stage_storyboard(Ctx(pr, "storyboard"))
    stages.stage_package(type("C", (Ctx,), {})(pr, "package")) if False else None
    return pr


def package_cost(standin, pr, mode_name):
    """The package call is one small request either way; count it the same way for both."""
    prof = modes.MODES[mode_name]
    return prof["package_ai"]


def row(label, pr):
    s = usage.summary(pr)["total"]
    return label, s["calls"], s["cached"], s["in_tok"], s["out_tok"], s["tokens"]


def main():
    config.ensure_dirs()
    rows = []
    cache.clear()
    cache_enabled = cache.enabled
    # 1. BEFORE: the old way (classic storyboard, no flow check, nothing remembered)
    cache.enabled = lambda: False
    st = StandIn()
    pr = run_video("before", dict(storyboard_engine="classic", gen_mode="normal", smooth_flow=False), st)
    rows.append(row("BEFORE (old way: classic storyboard, no memory)", pr))
    cache.enabled = cache_enabled
    cache.clear()
    # 2. AFTER: the three modes, cold
    for m in ("fast", "normal", "deep"):
        cache.clear()
        st = StandIn()
        pr = run_video(f"after-{m}", dict(storyboard_engine="director", gen_mode=m), st)
        rows.append(row(f"AFTER {m.upper()} (first time)", pr))
        if m == "normal":
            normal_pr, normal_st = pr, st
    # 3. same video again (a crash/resume, or re-running the stage): everything remembered
    cache.clear()
    run_video("again-1", dict(storyboard_engine="director", gen_mode="normal"), StandIn())
    pr = run_video("again-2", dict(storyboard_engine="director", gen_mode="normal"), StandIn())
    rows.append(row("AFTER NORMAL, same video re-run (all remembered)", pr))
    # 4. a second video on the same topic in deep mode: the research brief and props come from memory
    cache.clear()
    run_video("deep-1", dict(storyboard_engine="director", gen_mode="deep"), StandIn())
    pr = run_video("deep-2", dict(storyboard_engine="director", gen_mode="deep", tone="more serious"), StandIn(variant=True))
    rows.append(row("AFTER DEEP, 2nd video on the same topic (new words)", pr))
    # package + short are one small request each in both ways; report them separately
    print(f"\nVideo: 'The Cold War', {len(COLD_WAR)} beats (about 5 minutes). Script + fact-check + storyboard + props (package and Short pick are 1 small request each, same in every row).\n")
    print(f"{'':58} {'AI calls':>8} {'saved':>6} {'input tok':>10} {'output tok':>10} {'total tok':>10}")
    base = rows[0][5]
    for label, calls, cached, tin, tout, tot in rows:
        print(f"{label:58} {calls:>8} {cached:>6} {tin:>10,} {tout:>10,} {tot:>10,}   (saves {100 * (1 - tot / base):.0f}% vs before)" if label != rows[0][0] else
              f"{label:58} {calls:>8} {cached:>6} {tin:>10,} {tout:>10,} {tot:>10,}")
    print("\nWhat each step did in the NORMAL run:")
    for t, v in usage.summary(normal_pr)["by_task"].items():
        print(f"  {t:12} calls={v['calls']} tokens={v['tokens']:,}")
    sb = json.load(open(normal_pr.p("storyboard.json")))
    srcs = {}
    for i, v in sb["scenes"].items():
        k = "composed from a pattern" if str(v.get("source", "")).startswith("pattern:") else "drawn by the full scene writer" if v.get("source") == "claude_cli" else v.get("source")
        srcs[k] = srcs.get(k, 0) + 1
    print("  scenes:", srcs)
    rev = json.load(open(normal_pr.p("review.json")))
    print(f"  review: {rev['fixed']} problems fixed automatically, {rev['open']} left; scores {rev['scores']}")
    return rows


if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\n(measured in {time.time() - t0:.0f} s, nothing was sent anywhere)")
