# Camera patterns

- **Slow push-in (zoom 1.0 -> 1.06)** on any static scene so nothing is ever dead still. `[seed]`
- **Close-up on the punchline word** (zoom 1.5-1.7 focused on the speaker or object), a *cut* not a glide, returning to the wide shot
  after the clause. Implemented: `punch_shot` + `auto_camera`. `[seed]`
- **Whip between two speakers** in an argument: close-up left on line one, whip to the right on the reply. `POLITICAL_DEBATE`, `TWO_PEOPLE_TALK`. `[seed]`
- **Slow pan across** wide places (a battle line, a skyline, a queue). `BATTLE_ESTABLISHING`, `CITY_ESTABLISHING`. `[seed]`
- **Map zoom**: from the wide map to the one city the next beat is about (`mapzoom` transition). `[seed]`
- **Shake once** on the biggest explosion word. `[seed]`
- **Hold wide** when the point is the size of something (a crowd, an army, a number). `[seed]`
- **Emphasise information**: an important document or number gets a push-in; the review adds one when a scene has neither a camera nor an
  emphasis. `review.check_camera`
