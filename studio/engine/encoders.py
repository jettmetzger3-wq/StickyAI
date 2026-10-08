"""Video encoder choice: the CPU (libx264, the default and what every video so far was made with) or, opt-in, the graphics card.

Drawing the pictures is the bigger half of a render and always runs on the CPU; the H.264 encode that follows is about 40% of
the CPU time per frame (docs/performance.md). A hardware encoder (NVIDIA NVENC, Intel Quick Sync, AMD AMF, Apple VideoToolbox)
takes most of that off the CPU. It is OFF unless Settings > "Video encoder" says "auto" (or names one), because:

  * an encoder that is listed by ffmpeg can still fail on this PC (no card, old driver), so `detect()` runs a real half-second
    test encode and only reports the ones that work;
  * a render that fails with a hardware encoder is repeated once with the CPU encoder (`render_segment`), never left half done;
  * hardware files are a little bigger or smaller than libx264's for the same look, so the encoder is part of the render key:
    switching it re-renders the scenes (segments of two encoders are never joined into one video).

The picture itself is identical either way: only the compression differs.
"""
import subprocess

CPU = "libx264"
# name -> the ffmpeg arguments for a 30 fps 1080p flat-colour cartoon; quality chosen to match crf 20 on x264
HARDWARE = {
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "23", "-b:v", "0", "-pix_fmt", "yuv420p"],
    "h264_qsv": ["-c:v", "h264_qsv", "-preset", "veryfast", "-global_quality", "23", "-pix_fmt", "nv12"],
    "h264_amf": ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "22", "-qp_p", "24", "-pix_fmt", "yuv420p"],
    "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-q:v", "55", "-pix_fmt", "yuv420p"],
}
ORDER = ("h264_nvenc", "h264_qsv", "h264_amf", "h264_videotoolbox")
LABELS = {"cpu": "CPU (libx264): the default", "auto": "Graphics card if one works, else CPU", "h264_nvenc": "NVIDIA (NVENC)",
          "h264_qsv": "Intel (Quick Sync)", "h264_amf": "AMD (AMF)", "h264_videotoolbox": "Apple (VideoToolbox)"}

_found = {}


def _run(cmd, timeout=20):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def listed():
    """The hardware H.264 encoders this ffmpeg was built with (they may still not work on this PC)."""
    try:
        out = _run(["ffmpeg", "-hide_banner", "-encoders"]).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    return [n for n in ORDER if n in out]


def works(name):
    """True when a tiny real encode with `name` succeeds on this PC."""
    args = HARDWARE.get(name)
    if not args:
        return False
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=white:s=640x360:r=30:d=0.4",
           *args, "-f", "null", "-"]
    try:
        return _run(cmd).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def detect(refresh=False):
    """The hardware encoders that really work here, best first. Cached for the session (the test encodes take a moment)."""
    if refresh or "list" not in _found:
        _found["list"] = [n for n in listed() if works(n)]
    return list(_found["list"])


def resolve(setting):
    """The encoder to use for a Settings value ('cpu' | 'auto' | an encoder name): a name from HARDWARE or CPU. Anything that
    is not available falls back to the CPU encoder, so a wrong setting never stops a render."""
    s = str(setting or "cpu").strip().lower()
    if s in ("", "cpu", "libx264", "off"):
        return CPU
    avail = detect()
    if s == "auto":
        return avail[0] if avail else CPU
    return s if s in avail else CPU


def video_args(encoder, preset="veryfast", crf=20, threads=1):
    """The ffmpeg arguments that choose the video codec for a segment."""
    if encoder in HARDWARE:
        return list(HARDWARE[encoder])
    return ["-c:v", CPU, "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p", "-threads", str(threads)]


def key_part(encoder):
    """What the render key gets: nothing for the CPU encoder (so no existing video re-renders), the name otherwise."""
    return None if encoder == CPU else encoder
