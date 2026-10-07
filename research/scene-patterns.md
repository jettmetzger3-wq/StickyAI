# Scene patterns

Generated from `studio/knowledge/patterns.json` by `python -m studio research build-docs`. Edit the JSON (or add your own in `data/knowledge/patterns_user.json`), then rebuild this file. Each pattern is a reusable production rule: when it applies, who is on screen, what happens in what order, what the camera does and how it is timed.

Provenance: every pattern lists the videos it was verified against. `seed` means it is a documented technique that has NOT yet been checked frame by frame.

## PERSON_INTRODUCTION: A person appears for the first time

**Use when:** a named person is introduced (born, rose to power, 'a man named', first mention of a key figure)

**Visual sequence**

1. Establish the place with a wide background and a place+year banner.
2. The person walks or pops in, big, in their signature outfit.
3. A name card appears with a role label (this is the only time the label is needed).
4. One prop that sums them up sits beside them (quill, sword, lightbulb).
5. They do one characteristic action while a short in-character line bubbles up.
6. Supporting people react or stand smaller behind.

- **Characters:** the person large (scale 1.2-1.4), 0-2 smaller supporters
- **Actions:** enter, nod/wave/point; personality action
- **Background:** the place where they were at that moment
- **Props:** one signature prop
- **Camera:** Start wide, push in slowly on the person while the name card appears.
- **Timing:** name card on the word that says the name; role label +0.4 s; line on the key verb.
- **Transitions:** slide, auto
- **Tone:** neutral, humor
- **Slots:** `who` (the person (cast name)); `role` (label under the name, max 28 chars (e.g. 'FIRST PRESIDENT')); `place` (where they are); `say` (one short in-character line); `with` (0-2 supporting people)
- **Narration cues:** events intro_person; words born, named, known as, became, rose, young, son of, daughter of, meet
- **Example narration:** "George Washington became the first president."
- **Provenance:** seed: documented technique, not yet frame-verified

## LEADER_INTRODUCTION: A head of state or commander appears

**Use when:** a king, president, emperor, general or dictator takes the stage (role words: president, king, emperor, general, tsar, chancellor)

**Visual sequence**

1. Wide establishing shot of the seat of power (palace, hall, capitol).
2. Leader steps up to the center, larger than anyone else, with the crown/hat that marks the role.
3. A flag or banner of their side unfolds behind them.
4. Name card + title.
5. Advisors or soldiers stand smaller on both sides; one reacts.

- **Characters:** leader scale 1.3, 2-4 followers scale 0.7
- **Actions:** point, salute, hands on hips
- **Background:** palace or interior or field with banners
- **Props:** flag, throne, podium
- **Camera:** Slow zoom 1.0 to 1.08 on the leader; hold.
- **Timing:** name card on the name word; flag on the country word.
- **Transitions:** slide
- **Tone:** neutral, tension
- **Slots:** `who` (the leader); `role` (their title label); `place` (palace, hall, podium or battlefield); `flag` (their country's flag color); `say` (a short boast or worry)
- **Narration cues:** events intro_person; words president, king, queen, emperor, tsar, chancellor, prime minister, dictator, general, premier
- **Example narration:** "Napoleon crowned himself emperor." / "Stalin took over the Soviet Union."
- **Provenance:** seed: documented technique, not yet frame-verified

## HISTORICAL_SPEECH: Someone gives a speech to a crowd

**Use when:** a speech, address, rally, announcement or broadcast to a crowd or to the nation

**Visual sequence**

1. Wide: speaker small at the podium, crowd below, banners.
2. Cut to a close-up of the speaker on the key phrase.
3. Quote appears as a speech bubble or big text.
4. Crowd reacts (cheer, boo, silence) on the next clause.
5. Pull back out to show the size of the crowd.

- **Characters:** speaker scale 1.1 at a podium, crowd 10-24 smaller
- **Actions:** point, raise_right, cheer (crowd)
- **Background:** field, street, palace balcony or hall
- **Props:** podium, microphone, flags, megaphone
- **Camera:** Close-up on the speaker exactly on the punchline word; whip or pull back to the crowd after.
- **Timing:** quote on the word before it is spoken; crowd reaction 0.4 s after.
- **Transitions:** auto
- **Tone:** neutral, triumph, tension
- **Slots:** `who` (the speaker); `crowd` (who listens (nation/army/people, cast name)); `quote` (the key line, max 6 words); `place` (where); `sign` (a banner text behind the speaker (optional))
- **Narration cues:** events speech; words speech, speaks, spoke, address, rally, told the crowd, promised, broadcast, announced, podium
- **Example narration:** "Hitler promised the crowd jobs and revenge." / "Lincoln gave a short speech at Gettysburg."
- **Provenance:** seed: documented technique, not yet frame-verified

## DOCUMENT_SIGNING: A document is signed

**Use when:** a treaty, law, constitution or declaration is signed or sealed

**Visual sequence**

1. Establish the room.
2. The document slides to the center and grows large enough to read, title first.
3. The signer picks up the quill; witnesses stand around and watch.
4. Close-up on the pen touching the paper on the word 'signed'.
5. A stamp or seal lands; witnesses react.
6. Cut to what the signature changed (next beat).

- **Characters:** signer scale 1.0 on the left, 1-3 witnesses smaller on the right
- **Actions:** signer: write/nod; witnesses: cheer or gasp
- **Background:** palace, parliament or interior
- **Props:** document or scroll (with title and lines), quill, table
- **Camera:** Push in on the document; close-up on the pen at the verb.
- **Timing:** document on its name; pen on 'signed'; stamp +0.8 s.
- **Transitions:** slide, paper
- **Tone:** neutral, triumph, tension
- **Slots:** `doc_title` (the document's real name, uppercase, max 22 chars); `doc_lines` (2-4 short lines actually written on it); `signer` (who signs); `witnesses` (0-3 people watching); `place` (hall, palace or interior); `stamp` (optional stamp word (SIGNED, RATIFIED, VOID))
- **Narration cues:** events signing; words signed, signs, signing, signature, ratified, pen, sealed, wrote, drafted
- **Example narration:** "The Treaty of Versailles was signed in 1919." / "Jefferson wrote the Declaration of Independence."
- **Provenance:** seed: documented technique, not yet frame-verified

## LAW_BEING_PASSED: A law is debated and passed

**Use when:** a legislature votes: congress, parliament, a senate or a convention passes a law, bill or amendment

**Visual sequence**

1. Establish the chamber (benches, flags, columns) and the place+year banner.
2. Representatives debate: one stands and speaks, others react.
3. The document appears, big, with its real title.
4. A vote counter ticks up: YES vs NO.
5. Result stamp (PASSED / REJECTED) and the room reacts.
6. Transition into the consequences.

- **Characters:** speaker at the front, 8-16 delegates in two blocks
- **Actions:** talk, cheer, shake_head
- **Background:** parliament
- **Props:** document, ballot, counter, gavel
- **Camera:** Wide first, then slow push toward the speaker; close-up on the counter at the result.
- **Timing:** document on its name; counter during the verb 'voted'; stamp on the result word.
- **Transitions:** slide
- **Tone:** neutral, tension
- **Slots:** `doc_title` (the law's name, uppercase); `doc_lines` (2-3 short lines of what it says); `yes` (votes for (number)); `no` (votes against (number)); `speaker` (who speaks (optional)); `place` (parliament)
- **Narration cues:** events law; words law, act, bill, passed, congress, parliament, senate, vote, voted, legislation
- **Example narration:** "Congress passed the Stamp Act in 1765." / "Parliament voted to end the slave trade."
- **Provenance:** seed: documented technique, not yet frame-verified

## POLITICAL_DEBATE: Two sides argue

**Use when:** two people or parties argue, disagree or split into factions

**Visual sequence**

1. Two podiums or two groups face each other, the issue symbol (document, coin, flag) between them.
2. Left side speaks: bubble.
3. Camera whips to the right side: reply bubble.
4. Third beat: crowd between them looks left and right.
5. End on one side steaming (vein, steam) and the other smug.

- **Characters:** two leaders facing each other scale 1.1, a few followers each
- **Actions:** point, angry, shrug
- **Background:** interior or parliament
- **Props:** issue prop in the middle, podiums
- **Camera:** Whip between the two sides on each line.
- **Timing:** left line on the first verb, right line 1.2 s later.
- **Transitions:** wipe
- **Tone:** tension, humor
- **Slots:** `left` (first side (cast name)); `right` (second side); `left_line` (their argument, max 5 words); `right_line` (their reply, max 5 words); `issue` (what they argue about (a prop or sign)); `place` (hall or interior)
- **Narration cues:** events debate; words debate, argued, disagreed, opposed, faction, rivals, parties, clashed over, split, federalist
- **Example narration:** "Hamilton wanted a strong bank, Jefferson hated the idea."
- **Provenance:** seed: documented technique, not yet frame-verified

## ELECTION: Voting and a result

**Use when:** an election, campaign, voting or a landslide

**Visual sequence**

1. People queue at a ballot box on a street.
2. Candidates wave on stages left and right.
3. A tally counter runs.
4. Winner is lifted; loser slumps.
5. Result banner.

- **Characters:** 2 candidates, 6-12 voters
- **Actions:** cheer, cry, wave
- **Background:** street or hall
- **Props:** ballot, counter, trophy, flags
- **Camera:** Slow pan across the queue, zoom on the counter.
- **Timing:** counter on 'votes'/'percent'; winner pose on the result verb.
- **Transitions:** slide
- **Tone:** neutral, triumph, humor
- **Slots:** `candidates` (two candidates (cast names)); `winner` (who wins); `votes` (the winning share or count); `place` (street or hall)
- **Narration cues:** events election; words election, elected, ballot, voters, landslide, campaign, polls, vote, won the presidency
- **Example narration:** "Lincoln won the 1860 election without a single Southern state."
- **Provenance:** seed: documented technique, not yet frame-verified

## WAR_DECLARATION: War is declared

**Use when:** a country declares war, issues an ultimatum, mobilizes or invades

**Visual sequence**

1. The aggressor's leader signs or reads a message at a desk or balcony.
2. The telegram/declaration appears as a document with a bold red phrase.
3. A map of the two countries; the aggressor's color flips toward the target.
4. Arrow and units start moving.
5. Crowds cheer in one place, go silent in the other.

- **Characters:** leader + messenger; crowds on both sides
- **Actions:** point, salute
- **Background:** palace then map
- **Props:** telegram/envelope, document, flags
- **Camera:** Close-up on the message, then pull out to the map.
- **Timing:** message on 'declared'; arrow on the next verb.
- **Transitions:** wipe
- **Tone:** tension
- **Slots:** `aggressor` (who declares (cast name)); `target` (who is attacked); `message` (the statement or telegram text, max 5 words); `place` (palace or map)
- **Narration cues:** events war_declaration; words declared war, ultimatum, mobilized, invaded, war on, ordered
- **Example narration:** "Germany declared war on Russia on August 1, 1914."
- **Provenance:** seed: documented technique, not yet frame-verified

## PEACE_TREATY: Peace is made

**Use when:** peace deal, armistice, surrender, ceasefire or a treaty between sides

**Visual sequence**

1. A long table; side A on the left, side B on the right, the treaty in the middle.
2. Side A slumps or gloats; side B too.
3. The treaty's terms appear as lines on the document.
4. Both sign; a dove or a flag of white shows.
5. Crowd outside reacts.

- **Characters:** two leaders facing each other, 1-2 aides each
- **Actions:** shake_head, shrug, write
- **Background:** palace
- **Props:** scroll or document, table, dove, flags
- **Camera:** Slow push toward the document; side-to-side whip on the terms.
- **Timing:** document on its name; terms read one per clause; dove at the end.
- **Transitions:** fade, slide
- **Tone:** neutral, tragedy, triumph
- **Slots:** `side_a` (first party); `side_b` (second party); `doc_title` (treaty name); `doc_lines` (2-3 terms); `place` (palace or hall); `dove` (true if peace is the point)
- **Narration cues:** events treaty; words peace, treaty, armistice, surrender, ceasefire, truce, accord, negotiated, agreement, conference
- **Example narration:** "Germany signed the armistice in a railway car in 1918."
- **Provenance:** seed: documented technique, not yet frame-verified

## BATTLE_ESTABLISHING: The scene before a battle

**Use when:** two armies meet or prepare; a named battle is introduced with its date and place

**Visual sequence**

1. Wide battlefield with both armies on opposite sides, flags planted.
2. A big label: battle name + year.
3. Army sizes appear as counters over each side.
4. A commander on each side looks across; a tense line from each.
5. Wind/dust, silence before the charge.

- **Characters:** a commander + a block of 12-20 soldiers per side
- **Actions:** point, salute
- **Background:** battlefield (river|open|ruins) at dawn or dusk
- **Props:** flags, cannon, tents, counters
- **Camera:** Slow pan across the line from one army to the other.
- **Timing:** label on the battle name; counters on the numbers.
- **Transitions:** slide
- **Tone:** tension, neutral
- **Slots:** `side_a` (first army (cast name)); `side_b` (second army); `battle` (battle name for the label); `year` (year); `place` (battlefield style river|open|ruins); `sizes` (army sizes if told)
- **Narration cues:** events battle; words battle of, armies, faced, outnumbered, camp, siege, stood ready, prepared, dawn, two armies
- **Example narration:** "At dawn on June 18, 1815 two armies faced each other near Waterloo."
- **Provenance:** verified on: OverSimplified 'The Napoleonic Wars' clip recorded by the channel owner (earlier session): the battle is a full-screen battlefield, not a small prop

## BATTLE_ACTION: The fighting itself

**Use when:** the fighting: charges, shelling, bombing, storming, the clash

**Visual sequence**

1. The two blocks run at each other (enter + run actions).
2. Explosion and smoke at the clash point on the verb.
3. Close-up on the commander on the losing side reacting.
4. Debris, flag falls.
5. Camera shakes once on the biggest word.

- **Characters:** two blocks of 10-16 soldiers, a commander each
- **Actions:** run, slash/fight, faint
- **Background:** battlefield
- **Props:** explosion, cannon, smoke, flags
- **Camera:** Shake on the verb; close-up on a commander on the punchline.
- **Timing:** clash on the attack verb; flag falls on the result verb.
- **Transitions:** wipe, cut
- **Tone:** tension, tragedy
- **Slots:** `side_a` (attacker); `side_b` (defender); `weapon` (cannon|musket|sword|bomb); `result` (who breaks (optional)); `place` (battlefield style)
- **Narration cues:** events battle; words charged, attack, attacked, fought, fighting, clash, slaughter, bombed, shelled, stormed
- **Example narration:** "The British cavalry charged straight into the French guns."
- **Provenance:** seed: documented technique, not yet frame-verified

## MAP_EXPLANATION: A map explains where things are

**Use when:** borders, empires, regions, alliances: who controls what

**Visual sequence**

1. A dark map zooms to the region.
2. The relevant countries tint in their color one by one on their names.
3. City markers pop in on their names.
4. A year counter in the corner; borders change if time passes.
5. Zoom into the one place the next beat is about.

- **Characters:** none (or a small narrator char in the corner)
- **Actions:** -
- **Background:** map (dark style)
- **Props:** city markers, labels, year counter
- **Camera:** Map view moves to fit the countries; mapzoom into the next place.
- **Timing:** each country on its name; cities on their names.
- **Transitions:** zoom, auto
- **Tone:** neutral
- **Slots:** `countries` (country names to color); `focus` (region name to zoom on); `labels` (city names to mark); `year` (the year in a big counter); `side_colors` (who is which color)
- **Narration cues:** events country; words empire, territory, border, borders, controlled, region, continent, colonies, map, alliance
- **Example narration:** "By 1810 Napoleon controlled most of Europe."
- **Provenance:** seed: documented technique, not yet frame-verified

## GEOGRAPHICAL_MOVEMENT: Something moves across the map

**Use when:** armies, ships, travelers or people move from one place to another

**Visual sequence**

1. Map zoomed on the route.
2. Start city marker; the group's color flag there.
3. An arrow draws from start to destination, little units walk along it.
4. The destination marker pops on its name with a label.
5. Camera follows the arrow to the destination.

- **Characters:** little units on the arrow
- **Actions:** -
- **Background:** map
- **Props:** arrow with units, city markers, battle marker
- **Camera:** Pan along the route, zoom to the destination at the end.
- **Timing:** arrow starts on the verb; destination marker on its name.
- **Transitions:** auto
- **Tone:** neutral, tension
- **Slots:** `from` (start place); `to` (destination); `who` (the moving group (cast name)); `units` (hat kind or prop for the little marching figures); `via` (a middle place (optional))
- **Narration cues:** events movement; words marched, sailed, crossed, advanced, retreated, fled, traveled, headed, voyage, expedition
- **Example narration:** "Napoleon marched from Paris to Moscow."
- **Provenance:** seed: documented technique, not yet frame-verified

## CITY_ESTABLISHING: Where are we? A city

**Use when:** the story arrives in a named city: first mention of a city as the setting

**Visual sequence**

1. Wide painted skyline of the city with its landmarks.
2. Place + year banner appears.
3. One small action in the foreground (people walking, a cart).
4. Push in toward the street where the story starts.

- **Characters:** 2-4 small townsfolk
- **Actions:** walk
- **Background:** city with skyline key or street
- **Props:** landmark, carts, flags
- **Camera:** Slow pan across the skyline, then zoom 1.1 on the street.
- **Timing:** banner on the city name.
- **Transitions:** slide, auto
- **Tone:** neutral
- **Slots:** `city` (city name); `year` (year); `skyline` (skyline key if known); `detail` (one prop that sums up the city)
- **Narration cues:** events city; words capital, city of, in the city, streets of, harbor, port, town
- **Example narration:** "In Paris, the crowd was running out of bread."
- **Provenance:** seed: documented technique, not yet frame-verified

## COUNTRY_ESTABLISHING: Where are we? A country

**Use when:** a country or empire is introduced as the setting, usually with a year

**Visual sequence**

1. Map zoom from the world to the country, the country glows.
2. The country's name and year appear big.
3. A flag or the leader's hat pops in beside it.
4. A fact label (population, size, ruler).
5. Move into the next beat's city.

- **Characters:** the country's representative char (cast kind) small in the corner
- **Actions:** wave
- **Background:** map
- **Props:** flag, label, year counter
- **Camera:** Zoom from wide to fit the country.
- **Timing:** country tints on its name; label +0.5 s.
- **Transitions:** zoom
- **Tone:** neutral
- **Slots:** `country` (country name); `year` (year); `flag` (flag colors); `detail` (1 sentence fact as a label (population, ruler))
- **Narration cues:** events country; words country, nation, kingdom, republic, empire, at the time, land of
- **Example narration:** "In 1750 Britain was a small island with a big navy."
- **Provenance:** seed: documented technique, not yet frame-verified

## CROWD_REACTION: A crowd reacts

**Use when:** the public reacts: cheers, boos, gasps, panic, celebration

**Visual sequence**

1. The cause (a person, a news item, an event) in the corner.
2. The crowd faces it; all react in sync on the key word.
3. One individual shouts a line.
4. Camera cuts to the loudest person for a beat.

- **Characters:** crowd of 12-30 plus 1 shouter
- **Actions:** cheer, tremble, surprise
- **Background:** street or field
- **Props:** the cause prop, flags, signs
- **Camera:** Slow zoom into the crowd; cut to a close-up on the shouter.
- **Timing:** reaction on the key verb; shouted line 0.3 s later.
- **Transitions:** auto
- **Tone:** triumph, shock, humor, tension
- **Slots:** `crowd` (which crowd (cast name)); `reaction` (cheer|boo|gasp|panic|silence); `line` (what they shout, max 4 words); `cause` (what they are reacting to (a prop or a person)); `place` (street or square)
- **Narration cues:** events celebration; words crowd, cheered, booed, gasped, reacted, everyone, citizens, audience, public, people
- **Example narration:** "The crowd went wild when the news arrived."
- **Provenance:** seed: documented technique, not yet frame-verified

## PROTEST: A protest

**Use when:** people demonstrate, strike, boycott or demand change

**Visual sequence**

1. Crowd with hand-written signs fills the street.
2. The main sign grows and shows the demand in big letters.
3. A megaphone voice; the crowd raises fists.
4. Opposite side: soldiers or officials stand stiff.
5. Standoff beat.

- **Characters:** crowd 14-26, 1 leader with megaphone, opposing line of 4-8
- **Actions:** cheer, angry, point
- **Background:** street or city
- **Props:** signs, megaphone, flags
- **Camera:** Slow zoom on the main sign; slow pan to the opposing line.
- **Timing:** sign text on the demand word; fists on the verb.
- **Transitions:** auto
- **Tone:** tension, triumph
- **Slots:** `crowd` (who protests); `demand` (the slogan on the main sign, max 4 words); `against` (who they face (soldiers, king, company)); `place` (street)
- **Narration cues:** events protest; words protest, protested, demanded, strike, boycott, petition, demonstrators, march on, rally
- **Example narration:** "Workers marched through the streets demanding an eight hour day."
- **Provenance:** seed: documented technique, not yet frame-verified

## RIOT: Things get violent

**Use when:** a riot, uprising, revolt or revolution turns violent

**Visual sequence**

1. Angry crowd with torches and pitchforks rushes in from one side.
2. The target building/prop catches fire on the verb.
3. Defenders back away or fire; smoke fills the sky.
4. A flag drops, another is raised.
5. Silence on the aftermath.

- **Characters:** crowd 16-28 angry, defenders 4-8
- **Actions:** run, angry, fight
- **Background:** street at dusk
- **Props:** fire, torches, smoke, the target building
- **Camera:** Shake on the burn/storm verb; pull back to show the flames.
- **Timing:** fire on the verb; flag change +1 s.
- **Transitions:** wipe, cut
- **Tone:** tension, tragedy
- **Slots:** `crowd` (the rioters); `target` (what they attack (building prop)); `against` (who defends); `place` (street)
- **Narration cues:** events riot; words riot, rioted, mob, uprising, revolt, rebellion, revolution, burned, looted, stormed
- **Example narration:** "The crowd stormed the Bastille."
- **Provenance:** seed: documented technique, not yet frame-verified

## STATISTIC_VISUALIZATION: A number is the story

**Use when:** a big or surprising number: money, casualties, sizes, percentages

**Visual sequence**

1. A counter spins up to the number on the word that says it.
2. Icons or a bar make its size visible (one icon = a group).
3. A comparison appears (the size of a known city, 'twice the army of X').
4. A small reaction from a character.

- **Characters:** 1 small char reacting
- **Actions:** surprise, shrug
- **Background:** paper or sunburst, or dark for tragic numbers
- **Props:** counter, chart, icons, compare
- **Camera:** Slow zoom on the counter; hold on the comparison.
- **Timing:** counter starts on the word before the number; comparison +1 s.
- **Transitions:** auto
- **Tone:** neutral, tension, tragedy
- **Slots:** `number` (the number); `unit` (what it counts); `compare` (something familiar to compare to (optional)); `style` (counter|bar|icons)
- **Narration cues:** events -; words million, billion, thousand, percent, times, doubled, tripled, half, number, total
- **Example narration:** "The war killed more than 20 million people."
- **Provenance:** seed: documented technique, not yet frame-verified

## TIMELINE: Years go by

**Use when:** several dates or a stretch of years: a sequence over time

**Visual sequence**

1. A horizontal line draws across the frame.
2. Each event pops on its date as it is spoken.
3. The active one grows; earlier ones dim.
4. A final marker at 'now' or the end year.

- **Characters:** none
- **Actions:** -
- **Background:** paper
- **Props:** timeline element
- **Camera:** Slow pan along the line following the narration.
- **Timing:** each event on its year word.
- **Transitions:** slide
- **Tone:** neutral
- **Slots:** `events` (3-5 {year, label} pairs); `start` (first year); `end` (last year)
- **Narration cues:** events -; words years later, decades, century, timeline, by 1, from 1, between, until, over the next
- **Example narration:** "From 1914 to 1918 Europe tore itself apart."
- **Provenance:** seed: documented technique, not yet frame-verified

## CAUSE_AND_EFFECT: A led to B

**Use when:** cause and consequence: because, led to, as a result, which meant

**Visual sequence**

1. Left: the cause as a picture (prop or char) with a 3-word label.
2. An arrow draws across the middle.
3. Right: the effect appears, bigger or more dramatic.
4. A small reaction on the effect.

- **Characters:** 1-2 chars
- **Actions:** surprise, facepalm
- **Background:** paper or sunburst
- **Props:** two props, arrow, labels
- **Camera:** Slow push toward the effect.
- **Timing:** cause on its word; arrow on 'so/led to'; effect on its word.
- **Transitions:** auto
- **Tone:** neutral, tension
- **Slots:** `cause` (the cause as a prop or short label); `effect` (the effect as a prop or short label); `link` (word on the arrow (so, then, BOOM))
- **Narration cues:** events cause; words because, caused, led to, as a result, which meant, therefore, consequence, triggered, sparked, resulted
- **Example narration:** "The tax made the colonists angry, so they threw the tea overboard."
- **Provenance:** seed: documented technique, not yet frame-verified

## BEFORE_AND_AFTER: Then and now

**Use when:** a change over time: how things were vs how they became

**Visual sequence**

1. The screen splits; left labeled BEFORE/year, right AFTER/year.
2. Left side shows the old state; a short pause.
3. Right side swipes in with the new state.
4. One character reacts differently on each side (happy vs sad).

- **Characters:** the same character on both sides, different state
- **Actions:** cheer / cry
- **Background:** split
- **Props:** before/after props
- **Camera:** Static, then a quick push on the right side.
- **Timing:** left on the first clause; right on the second.
- **Transitions:** wipe
- **Tone:** neutral, humor
- **Slots:** `left` (label for before (a year or word)); `right` (label for after); `left_items` (what is on the left); `right_items` (what is on the right)
- **Narration cues:** events change; words before, after, used to, no longer, changed, transformed, then, now, compared, today
- **Example narration:** "London in 1800 had one million people. Fifty years later, it had two and a half."
- **Provenance:** seed: documented technique, not yet frame-verified

## ECONOMIC_CRISIS: The economy breaks

**Use when:** a crash, depression, inflation, debt, famine or ruinous taxes

**Visual sequence**

1. A chart or sign with the key figure falls or rockets.
2. A character holds an empty bag/pocket or a huge pile of worthless money.
3. Crowd in a line (bread line, bank queue).
4. One complaint bubble.
5. Dark vignette on tragic cases.

- **Characters:** 1 main sufferer + 4-10 in a queue
- **Actions:** cry, shrug, faint
- **Background:** street or interior, dusk
- **Props:** chart, moneybag, cash, sign
- **Camera:** Zoom on the chart line at the drop.
- **Timing:** chart moves on the verb; complaint 0.5 s later.
- **Transitions:** fade
- **Tone:** tension, tragedy, humor
- **Slots:** `what` (what collapses (prices, bank, harvest)); `number` (a big number to show); `who` (who suffers); `line` (a complaint, max 4 words)
- **Narration cues:** events crisis; words crash, depression, inflation, bankrupt, debt, recession, collapsed, prices, unemployment, famine
- **Example narration:** "Prices doubled in a year and bread cost a month's pay."
- **Provenance:** seed: documented technique, not yet frame-verified

## TECHNOLOGY_EXPLANATION: How a machine works

**Use when:** how something works: a machine, engine, process, new weapon or factory

**Visual sequence**

1. The machine appears large in the center.
2. Labels with thin arrows point to 2-3 parts as they are explained.
3. Something moves (gear turns, smoke rises).
4. The output shows (a pile of goods, a number).
5. The inventor/operator reacts proudly.

- **Characters:** inventor on the side, scale 0.9
- **Actions:** point, nod, hammer
- **Background:** construction/factory or interior
- **Props:** the machine, gears, smoke, labels
- **Camera:** Slow zoom on the machine; follow the labels.
- **Timing:** each label on its part word.
- **Transitions:** auto
- **Tone:** neutral, humor
- **Slots:** `thing` (the machine/prop); `parts` (2-3 labels pointing at parts); `who` (inventor or operator); `effect` (what it produced (a number))
- **Narration cues:** events technology; words machine, engine, works by, steam, factory, telegraph, railroad, assembly line, mill, process
- **Example narration:** "The spinning jenny let one worker spin eight threads at once."
- **Provenance:** seed: documented technique, not yet frame-verified

## INVENTION: Someone invents or discovers something

**Use when:** an invention, discovery, patent or breakthrough

**Visual sequence**

1. The inventor at a workbench; a lightbulb pops above their head.
2. The invention is revealed with a pop and a label with its name and year.
3. It works (spark, movement) on the verb.
4. Onlookers gasp or cheer.

- **Characters:** inventor scale 1.1, 2-3 onlookers
- **Actions:** think, surprise, cheer
- **Background:** interior or workshop
- **Props:** lightbulb, the invention, gears, label
- **Camera:** Close-up on the lightbulb, then pull back for the reveal.
- **Timing:** lightbulb on 'idea/invented'; reveal on the thing's name.
- **Transitions:** iris, auto
- **Tone:** triumph, humor
- **Slots:** `who` (inventor/discoverer); `thing` (the invention (prop)); `year` (year); `line` (eureka line, max 4 words)
- **Narration cues:** events invention; words invented, inventor, patent, discovered, discovery, breakthrough, built the first, first ever, new device
- **Example narration:** "Edison tested thousands of materials before one glowed for 13 hours."
- **Provenance:** seed: documented technique, not yet frame-verified

## DEATH_OF_HISTORICAL_FIGURE: A key figure dies

**Use when:** a death, assassination, execution or funeral of an important person

**Visual sequence**

1. Darken the scene; the place and date appear small.
2. The person is shown (portrait-like), then falls or lies still. No gore.
3. Mourners gather; one looks up; a candle or gravestone with the years.
4. Slow fade.

- **Characters:** the person, 3-8 mourners
- **Actions:** faint, cry, look
- **Background:** dark or dusk interior/street
- **Props:** gravestone, candle, flowers
- **Camera:** Slow zoom 1.0 to 1.1; fade to black at the end.
- **Timing:** fall on the verb; gravestone +1.2 s.
- **Transitions:** fade
- **Tone:** tragedy
- **Slots:** `who` (the person); `how` (cause (shot, poison, illness, execution)); `place` (where); `mourners` (who mourns); `year` (year)
- **Narration cues:** events death; words died, death, assassinated, killed, executed, funeral, buried, passed away, murdered, poisoned
- **Example narration:** "Lincoln was shot at Ford's Theatre on April 14, 1865."
- **Provenance:** seed: documented technique, not yet frame-verified

## MIGRATION: People move

**Use when:** migration, settlers, refugees, colonists crossing to a new land

**Visual sequence**

1. Map or horizon; the group with bundles walks/sails across the frame.
2. The vehicle carries them; the number counter ticks.
3. Arrival: land appears, a flag is planted or a house goes up.
4. A child or elder looks at the new place.

- **Characters:** a group of 8-14 with bundles, 1 leader
- **Actions:** walk, look
- **Background:** map, harbor or field
- **Props:** ship, wagon, bundles, flag, route arrow
- **Camera:** Slow pan following the group.
- **Timing:** movement on the verb; counter on the number.
- **Transitions:** slide
- **Tone:** neutral, tragedy
- **Slots:** `who` (the migrants); `from` (origin); `to` (destination); `vehicle` (ship|wagon|train|foot); `number` (how many (optional))
- **Narration cues:** events migration; words migrated, immigrants, settlers, refugees, fled, emigrated, moved to, journey, exodus, colonists
- **Example narration:** "Millions of Irish families sailed to America during the famine."
- **Provenance:** seed: documented technique, not yet frame-verified

## SOCIAL_CHANGE: Society changes

**Use when:** rights, reform, abolition, civil rights, suffrage: a social shift

**Visual sequence**

1. The old rule shown as a sign or barrier with a stamp.
2. A crowd gathers with signs.
3. The barrier falls or the sign is replaced on the key verb.
4. People celebrate (or one stands alone in somber cases).
5. Date label.

- **Characters:** crowd 10-20, 1 leader
- **Actions:** cheer, raise_right, cry
- **Background:** street or hall
- **Props:** signs, barrier, flags
- **Camera:** Zoom on the sign; pull back as it changes.
- **Timing:** barrier falls on the verb.
- **Transitions:** wipe
- **Tone:** triumph, tragedy, tension
- **Slots:** `who` (who gains or loses); `slogan` (sign text, max 4 words); `old` (the old rule (sign or prop)); `new` (the new rule); `place` (street or hall)
- **Narration cues:** events social; words rights, equality, freedom, abolished, segregation, slavery, women, suffrage, reform, movement
- **Example narration:** "In 1920 women in the United States finally won the right to vote."
- **Provenance:** seed: documented technique, not yet frame-verified

## TWO_PEOPLE_TALK: Two people talk or argue

**Use when:** a conversation or meeting: someone said, told, asked, met, visited or shook hands with someone

**Visual sequence**

1. Two characters face each other, the object of the talk between them.
2. A speaks (bubble) on the verb.
3. B reacts then replies.
4. Close-up on the one who reacts worst.

- **Characters:** two characters scale 1.1
- **Actions:** point, shrug, surprise
- **Background:** interior or palace
- **Props:** the thing between them
- **Camera:** Cut between the speakers' close-ups on each line.
- **Timing:** a_line on the speech verb; b_line +1.3 s.
- **Transitions:** auto
- **Tone:** humor, tension, neutral
- **Slots:** `a` (first speaker); `b` (second speaker); `a_line` (max 6 words); `b_line` (max 6 words); `place` (interior or palace); `prop` (the thing between them)
- **Narration cues:** events dialogue; words said, told, asked, replied, whispered, shouted, argued with, offered, warned, met
- **Example narration:** "The king told his advisor he wanted more gold. The advisor said there was none."
- **Provenance:** seed: documented technique, not yet frame-verified

## SECRET_PLOT: A secret plan

**Use when:** spies, coups, conspiracies, secret deals and sabotage

**Visual sequence**

1. Dark room, a single lamp; plotters lean over the object.
2. They look around; one peeks from behind a screen.
3. The target is shown unaware in the next panel.
4. A magnifier or telegram reveals the detail.

- **Characters:** 2-3 plotters, 1 watcher/target
- **Actions:** sneak, look, whisper
- **Background:** interior at night
- **Props:** document, folding_screen, magnifier, candle
- **Camera:** Close-up on the object; slow pull back to show the watcher.
- **Timing:** reveal on the key noun.
- **Transitions:** iris, fade
- **Tone:** tension, humor
- **Slots:** `plotters` (who plots); `target` (who/what is targeted); `object` (the secret thing (document, bomb, map)); `place` (dark interior)
- **Narration cues:** events plot; words spy, spies, secret, plot, conspiracy, coup, sabotage, intelligence, whispered, assassination plan
- **Example narration:** "The conspirators met in secret the night before."
- **Provenance:** seed: documented technique, not yet frame-verified

## CELEBRATION_VICTORY: A win is celebrated

**Use when:** victory, triumph, a parade or a celebration

**Visual sequence**

1. The winner is lifted or raises a trophy/flag.
2. Crowd cheers; confetti.
3. The loser slumps in the back corner.
4. Banner with the result.

- **Characters:** winner scale 1.2, crowd 10-18, loser small
- **Actions:** cheer, celebrate, cry
- **Background:** street or field
- **Props:** trophy, flags, confetti
- **Camera:** Slow zoom on the winner; shake on the cheer.
- **Timing:** cheer on the victory word.
- **Transitions:** slide
- **Tone:** triumph
- **Slots:** `winner` (who wins); `loser` (who loses (optional)); `trophy` (prop); `place` (street or palace)
- **Narration cues:** events celebration; words won, victory, triumph, celebrated, parade, cheered, festival, conquered
- **Example narration:** "Britain celebrated the victory with a huge parade."
- **Provenance:** seed: documented technique, not yet frame-verified

## DISASTER: Something goes badly wrong

**Use when:** fires, floods, plagues, sinkings, crashes, explosions

**Visual sequence**

1. Calm before: the doomed thing appears normal.
2. The disaster hits on the verb (explosion, sinking, collapse).
3. Smoke/dark; survivors look up.
4. Number or date as a somber label.

- **Characters:** 3-8 onlookers/survivors
- **Actions:** surprise, faint, cry
- **Background:** harbor/city/field at dusk
- **Props:** explosion, fire, ship, smoke
- **Camera:** Hold wide; shake on the hit; slow zoom to the survivors.
- **Timing:** hit on the verb; label +1.5 s.
- **Transitions:** fade
- **Tone:** tragedy, tension
- **Slots:** `what` (the disaster); `where` (place); `number` (casualties or size (optional)); `survivors` (who is left)
- **Narration cues:** events disaster; words earthquake, flood, plague, epidemic, sank, crashed, exploded, fire, disaster, eruption
- **Example narration:** "The Titanic hit an iceberg a little before midnight."
- **Provenance:** seed: documented technique, not yet frame-verified

## STORY_MOMENT: An ordinary story moment

**Use when:** an ordinary story beat: someone does, says or suffers something and no specific pattern above fits

**Visual sequence**

1. Establish the setting with the place and year.
2. The main character appears with a pose that matches the feeling of the line.
3. The one prop that matters pops in on its word.
4. A short label or line lands on the key word.
5. A second character reacts.

- **Characters:** 1-2 characters
- **Actions:** one action matching the verb
- **Background:** the setting the line suggests
- **Props:** one meaningful prop
- **Camera:** Slow push-in; close-up on the punchline word.
- **Timing:** object on its name; line on the key verb.
- **Transitions:** auto
- **Tone:** neutral, humor, tension, triumph, tragedy
- **Slots:** `who` (the main character (cast name)); `with` (a second character or group); `object` (the one prop that matters (library name)); `label` (a short on-screen label, max 28 chars); `action` (what the main character does (walk|run|fight|dig|hammer|cheer|cry|think|point)); `place` (the setting); `say` (one short in-character line)
- **Narration cues:** events -; words -
- **Example narration:** "He kept losing at chess to a pigeon."
- **Provenance:** seed: documented technique, not yet frame-verified
