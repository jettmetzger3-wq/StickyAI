# Visual storytelling rules: WHEN the narrator says X, the animation does Y

Tags: `[seed]` = documented technique, not yet frame-verified. `[user clip]` = seen in a clip supplied by the channel owner.
Each rule has the narration cue, the visual response, and what the studio does about it today.

## Introductions
1. **A person is named for the first time** -> establish the place, bring the person in large with their signature outfit, show a
   name card with a 2-4 word role label once, put one object that sums them up next to them. Never repeat the label.
   Studio: `PERSON_INTRODUCTION`, `LEADER_INTRODUCTION`. `[seed]`
2. **A new place is named** -> the background becomes that place (skyline, harbor, palace), with a "Place, Year" title in the top
   third. Same place next beat: no new title, same background. Studio: `CITY_ESTABLISHING`, banner + continuity tracker. `[seed]`
3. **A country or empire is named** -> a map zooms in and the country tints on the word, with its flag colour; the next scene
   zooms into the city where the story continues. Studio: `COUNTRY_ESTABLISHING`, `MAP_EXPLANATION`. `[seed]`
4. **An important object is named** -> it pops in on its word, big enough to read, and stays until the clause ends. A character
   points at it or reacts. Studio: props anchored with `at: "word:<name>"`. `[seed]`
5. **A number or statistic is named** -> a counter runs up to it on the word before the number; icons or a bar make its size
   visible; a familiar comparison follows ("the size of..."). Tragic numbers: dark background, no jokes. Studio:
   `STATISTIC_VISUALIZATION`. `[seed]`

## Things happening
6. **"X declared war"** -> the declarer at a desk or balcony, the message in big letters, a map where one country's colour reaches
   toward the other, crowds react in opposite ways. `WAR_DECLARATION`. `[seed]`
7. **"X signed / passed / ratified"** -> the document grows to readable size, its real title first; the signer leans in; the camera
   pushes to the pen exactly on the verb; a stamp or check lands; witnesses react. `DOCUMENT_SIGNING`, `LAW_BEING_PASSED`. `[seed]`
8. **"The army marched to Y"** -> map; an arrow draws from the start city to Y with little units walking along it; the destination
   marker pops on its name; the camera follows. `GEOGRAPHICAL_MOVEMENT`. `[seed]`
9. **"At the Battle of Z"** -> the place as a full battlefield background, two sides facing each other with flags, a label with the battle
   name and year, the sizes as counters; the attack beat is a separate scene with the clash, smoke and one commander reacting.
   `BATTLE_ESTABLISHING`, `BATTLE_ACTION`. `[user clip]` for "the place is a real, full-screen battlefield, not a small prop".
10. **"He built a factory / a house / a wall"** -> the construction site IS the background: walls rise during the sentence, workers
    work, a crane moves; it is finished (smoke from the chimney) when the narration says it is done. A tiny factory prop on an empty
    page is the failure case. `[user clip]` Studio: `places_work.py` construction painter.
11. **"The crowd cheered / rioted / protested"** -> a big crowd, one person in front shouting, a sign with the real slogan, the opposing
    side stiff on the other edge; a building catches fire on the verb in riots. `CROWD_REACTION`, `PROTEST`, `RIOT`. `[seed]`
12. **"He died"** -> the scene darkens, a candle or gravestone, the person falls (no gore), mourners, the years on the stone; fade out.
    `DEATH_OF_HISTORICAL_FIGURE`. `[seed]`

## Explaining
13. **"Because / so / which led to"** -> picture of the cause on the left, an arrow draws across on the connecting word, the effect
    appears bigger on the right. `CAUSE_AND_EFFECT`. `[seed]`
14. **"Before ... after / used to / now"** -> the screen splits with year labels; the same character looks different on each side.
    `BEFORE_AND_AFTER`. `[seed]`
15. **"Years later / from 1914 to 1918"** -> a timeline draws; each event pops on its year word; the active one grows. `TIMELINE`. `[seed]`
16. **"How the machine worked"** -> the machine large in the middle, labels with thin arrows to two or three parts as each is explained,
    something moves, the output appears. `TECHNOLOGY_EXPLANATION`. `[seed]`
17. **"Prices doubled / the market crashed"** -> a chart line moves on the verb, a character with an empty bag or a pile of worthless
    money, a queue, one complaint. `ECONOMIC_CRISIS`. `[seed]`

## Feeling and jokes
18. **A surprise word** ("suddenly", "shock") -> the character's face reacts on that word, the camera cuts in for a beat. Studio:
    `reactions.py`. `[seed]`
19. **The punchline** -> the camera cuts to a close-up on the punchline word exactly, then returns; the speech bubble arrives with the
    word, not before. Studio: `punch_shot`. `[seed]`
20. **An anachronistic or absurd detail** -> shown as a plain prop or sign in the same flat style, no wink: the joke is the contrast.
    Studio: custom lines via `themes.line_for`; `STORY_MOMENT` for the in-between beats. `[seed]`
21. **Somber material** -> dark or dusk backgrounds, fades instead of slides, no jokes, no parades, numbers stated plainly. Studio:
    `somber` mood switches patterns off that are comic (`patterns.score`). `[seed]`

## Rhythm
22. A new picture roughly every 3-8 seconds; longer for a map being explained; never the same picture twice in a row.
    Studio: `review.py` redundancy and pacing checks. `[seed]`
23. The first 20 seconds: surprising statement (hook), the host greeting, "so what was X" plain explanation, then the story. Studio: script
    structure + `mascot.py`. `[seed]`
24. The ending is a short like-and-subscribe card, not a recap. Studio: `outro`. `[seed]`
