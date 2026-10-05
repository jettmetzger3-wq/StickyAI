"""Stickman Studio video engine.

Public API:
    Scene, Pen, View            low-level drawing (see core.py / pen.py)
    build_scene(scene_json, idx, dur, mood, text, timer)   JSON -> Scene
    check_scene(scene_json, mood, text) -> (fixed, fixes, errors)
    SCENE_SCHEMA                JSON Schema for one scene
    render_segment / render_still / concat_segments / share_copy / plan_timeline
    make_captions, WordTimer, prep (TTS normalization), build_mix / loudnorm (audio)
    render_thumbnail
"""
from .core import Scene, W, H, FPS
from .pen import Pen
from .geo import View, region_geom, COUNTRIES, REGIONS
from .compiler import build_scene
from .schema import SCENE_SCHEMA, check_scene, validate_scene, repair_scene
from .timing import WordTimer, LEAD, TAIL
from .captions import make_captions, caption_timings, chunk_words
from .ttsprep import prep, prep_words, year, word_times_from_alignment
from .render import render_segment, render_still, concat_segments, share_copy, plan_timeline, probe_duration
from .thumbnail import render_thumbnail

__all__ = ["Scene", "W", "H", "FPS", "Pen", "View", "region_geom", "COUNTRIES", "REGIONS", "build_scene",
           "SCENE_SCHEMA", "check_scene", "validate_scene", "repair_scene", "WordTimer", "LEAD", "TAIL",
           "make_captions", "caption_timings", "chunk_words", "prep", "prep_words", "year",
           "word_times_from_alignment", "render_segment", "render_still", "concat_segments", "share_copy",
           "plan_timeline", "probe_duration", "render_thumbnail"]
