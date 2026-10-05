"""Burned-in captions: short chunks (7 words max) split on punctuation, white bold text with a dark outline."""
from PIL import Image, ImageDraw

from .fonts import font
from .timing import WordTimer, LEAD, TAIL

MAX_WORDS = 7
CAPTION_SIZE = 52
CAPTION_BOTTOM = 70          # px from the bottom edge to the caption baseline box
CAPTION_ZONE = 180           # keep other on-screen text out of the bottom 180 px


def chunk_words(words, max_words=MAX_WORDS):
    """Return lists of word indices. Break after sentence ends, after commas once a chunk has 4+ words,
    and always at max_words. A tiny leftover (<=2 words) is merged into the previous chunk if that
    keeps it within max_words + 2."""
    chunks, cur = [], []
    for i, w in enumerate(words):
        cur.append(i)
        end = w[-1] if w else ""
        if len(cur) >= max_words or (end in ".?!" and len(cur) >= 2) or (end in ",:;" and len(cur) >= 4):
            chunks.append(cur)
            cur = []
    if cur:
        if chunks and len(cur) <= 2 and len(chunks[-1]) + len(cur) <= max_words + 1:
            chunks[-1] = chunks[-1] + cur
        else:
            chunks.append(cur)
    return chunks


def caption_timings(text, dur, lead=LEAD, tail=TAIL, word_times=None, timer=None):
    """[(start, end, chunk_text)] in scene time."""
    timer = timer or WordTimer(text, dur, lead, tail, word_times)
    words = timer.words
    out = []
    chunks = chunk_words(words)
    for k, idx in enumerate(chunks):
        t0 = timer.starts[idx[0]] if k else min(timer.starts[idx[0]], lead)
        if k + 1 < len(chunks):
            t1 = timer.starts[chunks[k + 1][0]]
        else:
            t1 = dur
        out.append((t0, max(t1, t0 + 0.2), " ".join(words[i] for i in idx)))
    return out


def render_caption(text, size=CAPTION_SIZE):
    f = font("bold", size)
    chs = text.replace(" ", "  ")  # double spaces look right with the thick outline
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    bb = tmp.textbbox((0, 0), chs, font=f, stroke_width=5)
    im = Image.new("RGBA", (bb[2] - bb[0] + 20, bb[3] - bb[1] + 20), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10 - bb[0], 10 - bb[1]), chs, font=f, fill=(255, 255, 255), stroke_width=5,
                            stroke_fill=(25, 25, 32))
    return im


def make_captions(text, dur, lead=LEAD, tail=TAIL, word_times=None, timer=None, max_width=1800):
    """[(start, end, RGBA image)] ready for Scene.render_at."""
    out = []
    for t0, t1, chunk in caption_timings(text, dur, lead, tail, word_times, timer):
        size = CAPTION_SIZE
        im = render_caption(chunk, size)
        while im.width > max_width and size > 30:
            size -= 4
            im = render_caption(chunk, size)
        out.append((t0, t1, im))
    return out
