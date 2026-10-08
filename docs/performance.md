# Rendering performance

How to measure, what was changed and what was tried and rejected. All numbers are from one shared 4-core cloud machine
(CPU seconds, which are steadier than wall-clock there); a real PC will be faster in absolute terms, the ratios are what matter.

## Measure

```
python scripts/bench_render.py                       # ms per frame for the 26 example scenes (30 consecutive frames each)
python scripts/bench_render.py --profile frames      # where the per-frame time goes (cProfile)
python scripts/bench_render.py --profile build       # where the once-per-scene setup time goes
python scripts/bench_render.py --save before_dir     # keep every frame as a PNG ...
python scripts/bench_render.py --check before_dir    # ... then prove a change did not alter the picture
```

`--check` reports each frame as identical, within 2 levels (rounding) or CHANGED. Use it for every speed-up: a faster renderer
that changes the look is a different feature. (The old paper grain was random per run, so two renders of one scene never
matched; the benchmark fixes the grain for both sides of a comparison.)

## What a frame costs (before, 1080p, per frame)

| step | CPU |
|---|---|
| drawing (Pillow, in Python) | ~38 ms, of which the camera crop-and-scale of the whole frame is ~60% |
| x264 `veryfast`, crf 20 (ffmpeg, in parallel) | ~30-36 ms, of which RGB to YUV is ~7 ms |
| sending the frame to ffmpeg | ~3-5 ms |

A 10-minute video is ~18,000 frames: about 23 CPU-minutes for the picture on one core, divided across the render workers.

## Changed (measured, picture unchanged)

| change | before | after |
|---|---|---|
| Layers are cut to what was drawn *before* converting and downsampling (`core.finish_layer`; a small prop no longer pays for a 3840x2160 canvas) | scene setup 1.5-1.6 s | 0.7 s (-54%) |
| One seeded paper-grain tile per process instead of fresh noise (~100 ms) per scene | | also makes renders reproducible |
| Small share copy: one capped x264 pass at 720p (`-tune animation`) instead of two passes at 1080p (setting "Share copy picture size") | 23 s per 45 s of video | 12.6 s (-45%), size never over the cap |

Scene setup is paid for every scene in the render, again for the previous scene of every transition, for every preview in the
Storyboard stage and again for a Short, so it adds up to roughly 4 CPU-minutes saved on a 10-minute video.
Frame comparison against the original renderer (same grain): 591 identical, 189 within 2 levels, 0 changed of 780.

## Tried and rejected (so nobody repeats it)

* **OpenCV `warpAffine` for the camera step**: matches Pillow to 1 level but is only ~30% faster on that step once the
  conversions in and out are paid (and ~50% slower when done naively on 3-channel images), for a 60 MB dependency. Not worth it.
  `cv2.resize` on an integer region is 7x faster but cannot do the sub-pixel camera moves that keep slow pushes smooth.
* **Pillow `transform` (AFFINE/EXTENT)**: 2x slower than `resize` with a box.
* **x264 trims** (`ref=1`, `subme=1`, `bframes=2`, `superfast`): 20-30% less encode CPU but 20-85% bigger files. The final video
  is the segments, so the size cost is real; left at `veryfast` crf 20.
* **NEAREST camera at 2x then reduce**: fast, but changes the look of slow pans; needs a human to judge motion first.

## Added since (not measured on a real graphics card)

Checked with `--save` / `--check` against the commit before the shared prop library, the prop index, the quality pass and the
encoder choice: 780 frames of the 26 example scenes, 780 identical, 0 changed (the only look change since is the two-line
title on long documents and scrolls, which none of the examples has).

* **Hardware H.264 encoders** (NVENC, QSV, AMF, VideoToolbox), opt-in (Settings > Video encoder, default CPU): `studio/engine/encoders.py`
  runs a real half-second test encode per encoder and only offers the ones that work; a scene whose hardware encode fails is
  encoded on the CPU instead; the encoder is part of the render key (so switching re-renders, and the CPU key is unchanged).
  Tested here with ffmpeg's CPU encoder and with mocked detection; **no graphics card was available**, so the quality settings
  (`-cq 23`, `global_quality 23`, `qp 22/24`, `-q:v 55`) are untuned guesses. Encode is ~40% of the CPU per frame above, so the
  best case is roughly that much faster; measure with `scripts/bench_render.py` and compare file sizes before trusting it.
* **Quick preview video** (`studio/pipeline/animatic.py`): storyboard stills + narration + the words, ~3 s for a 44 s video
  (ffmpeg only, nothing drawn). A slideshow, not a draft of the real picture; a real low-resolution draft would need the
  1920x1080 / supersampling constants (`engine/doodle.py`) to become parameters, which was not attempted.
* **Which scenes changed** (`stages.render_status`, shown in the Storyboard tab): the render key is made in one place
  (`stages.render_key`), so the check and the Render stage cannot disagree.

## Ideas not done (need a machine to test on)

* Rendering the Short's scenes together with the main video (they are drawn twice today: with and without the baked-in captions).
