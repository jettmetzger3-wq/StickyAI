# Prop patterns: props must say something

Rule: **if a prop matters, the viewer can read what it says.** Generic placeholders are a review failure. `[seed]`

| Prop | What it must carry | Studio |
|---|---|---|
| document / scroll | its real name as the title, 2-4 real short lines, a stamp when the beat has a result | `props_intel.doc_for`, 16 famous documents built in, deep mode adds the topic's own from the research brief |
| newspaper | the paper's name and a headline that fits the event ("WAR DECLARED") | `props_intel.headline_for` |
| sign / banner | the real slogan of the protest ("FAIR WAGES!") | `props_intel.slogan_for` |
| map | the countries and cities the narration names, tinted on their words | `composer.map_elements`, `knowledge/gazetteer.json` |
| number | a counter, never just text, with a unit label and a comparison | `L_stat` |
| money | the right object (coins, notes, gold bars, moneybag) with the amount as text | `L_economic`, `L_stat` |
| weapons and tools | match the era: sword before 1400, musket 1400-1870, cannon to 1945, tank after | `props_intel.weapon_for_year`, `review.ERA_PROPS` |
| law | the law's real name, the vote counter, a PASSED/REJECTED stamp | `LAW_BEING_PASSED` |
| gravestone | RIP and the two years | `L_death` |

Prop intelligence record (kept in the plan for important props): name, context (year/place), text, purpose, visual details, who
interacts with it, when it appears (on its word), when it leaves (end of the clause).
