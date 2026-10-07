# Character patterns

- **One look per person, everywhere.** Hat kind + hat colour + coat colour + beard/mustache, chosen once in the character registry
  (`projects/<slug>/characters/<id>.json`, seeded from `studio/knowledge/people.json`). Scene 4 and scene 15 read the same entry. `[seed]`
- **Nations and armies are a hat and a coat colour**, not a face: the French wear the blue coats, the British the red; a whole army is
  a `crowd` of that kind. A named general stands in front at 1.0-1.3 scale; the army is 0.55. `[seed]`
- **Scale is importance.** The person the sentence is about is the largest figure; supporting characters 0.7-0.85; background people 0.55.
- **A character who talks has a bubble that arrives on the key word**; one who reacts gets a face change (`react`) on the trigger word.
- **Every person on screen is doing something**: point, shrug, cheer, cry, lean toward the document. Standing still is a review failure.
- **Crowds**: 12-30 figures in 2-3 rows; one individual breaks out in front and shouts a short line (max 4 words); the opposing side is
  small, stiff, flat-mouthed. `[seed]`
- **Recurring host**: one mascot greets after the hook, signs off with the like/subscribe card, and leans in at big moments (max one
  cameo per 7 scenes). `[seed]`
- **Pose follows feeling**: triumph = arms up/grin, tragedy = arms down/sad eyes, shock = open mouth/wide eyes, tension = fists/frown,
  humour = shrug/smirk. Studio: `composer.EMOTION_FACE`.
