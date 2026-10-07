# Transition patterns

- Same place, same speaker: **hard cut**, no effect (reads as one continuous shot). `render.pick_transition` already does this.
- New place: **slide** or **wipe** in the direction of travel; map to map: **mapzoom** or cut. `[seed]`
- Time passes: **fade** or a day -> dusk -> night background progression; never night -> day for no reason (`continuity.check`). `[seed]`
- Somber to anything and anything to somber: **fade**. `[seed]`
- Chapter change / "meanwhile": **paper** or **iris**. `[seed]`
- A transition belongs to the pattern: patterns list their default (`DOCUMENT_SIGNING`: slide/paper, `DEATH`: fade, `BATTLE_ACTION`: wipe/cut).
