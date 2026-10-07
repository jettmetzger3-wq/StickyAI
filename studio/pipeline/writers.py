"""Which AI writes what, and how to spend less of the Claude plan for the same video.

Every AI job in a video is a "task" (writing the script, fact-checking, drawing the scenes...). By default each
task uses the video's writer; Settings > "Who does what" can hand any task to a different AI (Claude Code, Gemini,
Groq, the Anthropic API, Ollama or Basic). The backup writer still takes over if the Claude plan runs out.

The Claude plan savers work only on Claude Code calls:
  - the side jobs (watching the source video, designing props, titles and description, picking the Short) run on
    a lighter Claude model, while the script, fact-check and scenes keep your best model;
  - scenes are asked for in bigger batches, so the long scene instructions are sent fewer times;
  - the first batch goes alone, then the rest run in parallel: Claude Code caches the shared instructions from the
    first request, and later requests reuse them instead of paying for them again.
"""
import functools
import subprocess

from .. import providers as P
from ..config import load_settings
from ..providers.llm import MAIN_MODEL, MODEL_IDS, main_model, model_id   # noqa: F401  (re-exported)

TASKS = (
    ("script", "Writing the script"),
    ("factcheck", "Fact-checking the script"),
    ("watch", "Watching the source video"),
    ("props", "Designing extra props"),
    ("storyboard", "Drawing the scenes"),
    ("package", "Titles, description and thumbnail text"),
    ("short", "Picking the Short's best moment"),
)
TASK_IDS = tuple(t for t, _ in TASKS)
CLAUDE_MODELS = ("", "opus", "sonnet", "haiku")

# plan saver presets: Claude model per task, scenes per request, whether to warm the cache with one batch first,
# and how many example scenes the storyboard prompt carries
PLAN_SAVER = {
    "off": dict(models={}, batch=8, warm=False, examples=20, effort={}),
    "balanced": dict(models={"short": "haiku"},
                     batch=12, warm=True, examples=20, effort={"package": "low", "short": "low"}),
    "max": dict(models={"props": "haiku", "package": "haiku", "short": "haiku"},
                batch=16, warm=True, examples=12, effort={"package": "low", "short": "low", "props": "low"}),
}


def saver(settings=None):
    s = settings or load_settings()
    return PLAN_SAVER.get(s.get("plan_saver") or "balanced", PLAN_SAVER["balanced"])


def task_writer_id(meta, task, settings=None):
    """The AI that does `task` for this video: the task's own pick in Settings, else the video's writer."""
    s = settings or load_settings()
    pid = ((s.get("task_writers") or {}).get(task) or "") if task else ""
    if pid:
        try:
            P.get("llm", pid)
            return pid
        except KeyError:
            pass
    return (meta.get("providers") or {}).get("llm") or P.TIERS["free"]["llm"]


def claude_model(task, settings=None):
    """The Claude Code model for `task`: your pick per task, else the plan saver's, else the main model."""
    s = settings or load_settings()
    m = ((s.get("claude_task_models") or {}).get(task) or "") if task else ""
    if m and m != "auto":
        return model_id(m)
    pick = saver(s)["models"].get(task)
    return model_id(pick) if pick else main_model(s)


@functools.lru_cache(maxsize=4)
def _cli_flags(cmd):
    try:
        r = subprocess.run(list(cmd) + ["--help"], capture_output=True, text=True, timeout=30, encoding="utf-8",
                           errors="replace")
        return r.stdout + r.stderr
    except Exception:
        return ""


class ClaudeTask:
    """Claude Code doing one task: picks the task's model (and effort, when this Claude Code version has it) and
    the plan saver's batch size. Everything else is the plain Claude Code writer."""

    def __init__(self, inner, task, settings=None):
        self.inner, self.task = inner, task
        s = settings or load_settings()
        sv = saver(s)
        self.model = claude_model(task, s)
        self.effort = sv["effort"].get(task)
        self.batch_beats = max(int(getattr(inner, "batch_beats", 8) or 8), sv["batch"])
        self.examples = min(int(getattr(inner, "examples", 20) or 20), sv["examples"])
        self.warm_first = sv["warm"]

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def complete(self, system, prompt, schema=None, images=(), max_tokens=16000, model=None, label="", web=False,
                 **kw):
        model = self.model if model is None else model
        extra = []
        if self.effort and "--effort" in _cli_flags(tuple(self.inner.command())):
            extra = ["--effort", self.effort]
        return self.inner.complete(system, prompt, schema=schema, images=images, max_tokens=max_tokens, model=model,
                                   label=label, web=web, extra_args=extra, **kw)
