"""Topic kits: what a video's world looks like.

A video about Napoleon should happen on Paris streets, in palaces and on battlefields with muskets and cannons; a
video about pirates in harbors, on beaches and underwater. detect() finds the themes of a video from its title,
topic and narration, and each theme brings places (backgrounds), props, hats and a few in-character lines.
The storyboard prompt gets the kit, and the no-AI scene maker uses it directly.

Also here: dialogue lines for "someone says something" beats, and the pass that stops two scenes in a row from
looking the same.
"""
import random
import re

# key: label, words (lowercase; a leading/trailing space means whole word), places, props, kinds, lines, map
THEMES = {
    "france": dict(
        label="France", words=["france", "french", "paris", "napoleon", "bonaparte", "versailles", "bastille", "louis xiv",
                               "louis xvi", "marie antoinette", "robespierre", "waterloo", "gaul", "joan of arc",
                               "normandy", "marseille", "lyon", "bordeaux", "de gaulle", "vichy", "fleur"],
        places=[{"type": "city", "skyline": "paris"}, {"type": "street", "style": "europe"}, {"type": "palace"},
                {"type": "field"}, {"type": "street", "style": "europe", "time": "night"},
                {"type": "map", "center": [2.5, 46.5], "width": 16, "style": "dark"}],
        props=["eiffel_tower", "arc_de_triomphe", "cathedral", "baguette", "cheese", "wine", "croissant", "rooster",
               "guillotine", "barricade", "musket", "cannon", "drum", "crown", "throne"],
        kinds=["france", "bicorne", "beret", "shako", "crown"],
        lines=["Vive la France!", "Vive l'Empereur!", "Allez, mes amis!", "Sacre bleu!", "For glory and France!"]),
    "britain": dict(
        label="Britain", words=["britain", "british", "england", "english", "london", "scotland", "scottish", "wales",
                                "irish", "ireland", "victoria", "churchill", "elizabeth", "tudor", "henry viii",
                                "royal navy", "redcoat", "empire on which", "parliament"],
        places=[{"type": "city", "skyline": "london"}, {"type": "street", "style": "medieval"},
                {"type": "street", "style": "europe", "time": "dusk"}, {"type": "palace"}, {"type": "hills"},
                {"type": "harbor"}],
        props=["big_ben", "cathedral", "stonehenge", "teapot", "crown", "lion", "sheep", "galleon", "ship", "musket",
               "newspaper", "throne", "castle"],
        kinds=["britain", "bearskin", "tophat", "bowler", "crown", "navy"],
        lines=["Rule, Britannia!", "Jolly good show!", "Keep calm, chaps.", "Tea first, then war.",
               "God save the King!"]),
    "usa": dict(
        label="USA", words=["america", "american", "usa", "united states", "washington", "lincoln", "new york",
                            "white house", "congress", "president", "civil war", "independence", "yankee", "texas",
                            "california", "chicago", "roosevelt", "kennedy", "wall street", "manhattan"],
        places=[{"type": "city", "skyline": "newyork"}, {"type": "city", "skyline": "washington"},
                {"type": "street", "style": "western"}, {"type": "interior"}, {"type": "field"}],
        props=["statue_of_liberty", "capitol", "white_house", "skyscraper", "eagle", "burger", "bell", "flag", "cash",
               "podium", "microphone", "newspaper", "wagon"],
        kinds=["america", "tophat", "cowboy", "army", "marine"],
        lines=["Freedom!", "God bless America!", "We the people!", "Let's make a deal.", "Yeehaw!"]),
    "russia": dict(
        label="Russia", words=["russia", "russian", "moscow", "soviet", "ussr", "stalin", "lenin", "tsar", "czar",
                               "kremlin", "siberia", "petersburg", "putin", "romanov", "bolshevik", "red army"],
        places=[{"type": "city", "skyline": "moscow"}, {"type": "snow"}, {"type": "city", "skyline": "moscow",
                                                                         "time": "night"},
                {"type": "mountains"}, {"type": "palace"}, {"type": "map", "center": [60, 58], "width": 90,
                                                            "style": "dark"}],
        props=["kremlin", "onion_domes", "bear", "matryoshka", "pine_tree", "tank", "star", "hammer", "wheat",
               "telephone", "satellite"],
        kinds=["ussr", "furhat", "crown", "army"],
        lines=["Ura!", "For the Motherland!", "Comrades, forward!", "It's cold. Very cold.", "Da!"]),
    "germany": dict(
        label="Germany", words=["germany", "german", "berlin", "prussia", "prussian", "bismarck", "kaiser", "hitler",
                                "nazi", "reich", "weimar", "bavaria", "munich", "holy roman"],
        places=[{"type": "city", "skyline": "berlin"}, {"type": "street", "style": "medieval"}, {"type": "palace"},
                {"type": "mountains"}, {"type": "field"}],
        props=["brandenburg_gate", "beer", "zeppelin", "tank", "eagle", "castle", "pine_tree", "gear", "train"],
        kinds=["germany", "army", "helmet", "crown"],
        lines=["Jawohl!", "Forward, men!", "Everything goes to plan.", "Order! Discipline!"]),
    "rome": dict(
        label="Ancient Rome", words=["rome", "roman", "caesar", "augustus", "senate", "legion", "gladiator", "nero",
                                     "colosseum", "carthage", "hannibal", "republic", "empire fell", "pompeii",
                                     "byzantine", "constantinople", "latin"],
        places=[{"type": "city", "skyline": "rome"}, {"type": "palace"}, {"type": "hills"}, {"type": "field"},
                {"type": "street", "style": "arab"}, {"type": "map", "center": [15, 40], "width": 40, "style": "dark"}],
        props=["colosseum", "temple", "aqueduct", "chariot", "eagle", "shield", "spear", "sword", "scroll", "wolf",
               "amphora", "volcano", "elephant", "catapult"],
        kinds=["roman", "laurel", "knight"],
        lines=["Ave, Caesar!", "Veni, vidi, vici!", "For Rome!", "Bread and circuses!", "The Senate will hear of this!"]),
    "greece": dict(
        label="Ancient Greece", words=["greece", "greek", "athens", "sparta", "spartan", "alexander", "macedon",
                                       "olymp", "zeus", "troy", "trojan", "persia", "persian", "philosopher",
                                       "socrates", "plato", "aristotle"],
        places=[{"type": "city", "skyline": "athens"}, {"type": "hills"}, {"type": "beach"}, {"type": "palace"},
                {"type": "map", "center": [24, 38], "width": 22, "style": "dark"}],
        props=["temple", "amphora", "shield", "spear", "galleon", "scroll", "wine", "trophy",
               "lightning", "horse"],
        kinds=["laurel", "roman", "knight"],
        lines=["This is Sparta!", "For Athens!", "Know thyself.", "Eureka!", "Molon labe!"]),
    "egypt": dict(
        label="Ancient Egypt", words=["egypt", "egyptian", "pharaoh", "pyramid", "nile", "cleopatra", "tutankhamun",
                                      "sphinx", "mummy", "cairo", "ramses", "giza", "hieroglyph"],
        places=[{"type": "desert"}, {"type": "city", "skyline": "cairo"}, {"type": "palace"},
                {"type": "desert", "time": "dusk"}, {"type": "street", "style": "arab"}],
        props=["pyramid", "sphinx", "obelisk", "camel", "cat", "scroll", "wheat", "gold_bars", "throne", "palm_tree"],
        kinds=["pharaoh", "turban", "civ"],
        lines=["Build it bigger!", "By Ra!", "Pharaoh has spoken.", "Another pyramid? Really?"]),
    "middle_east": dict(
        label="Middle East", words=["ottoman", "turk", "istanbul", "arab", "arabia", "persia", "iran", "iraq", "baghdad",
                                    "caliph", "sultan", "islam", "mecca", "jerusalem", "crusade", "saladin",
                                    "silk road", "syria", "babylon", "mesopotamia", "oil"],
        places=[{"type": "city", "skyline": "istanbul"}, {"type": "street", "style": "arab"}, {"type": "desert"},
                {"type": "palace"}, {"type": "desert", "time": "dusk"}],
        props=["mosque", "camel", "palm_tree", "derrick", "barrel", "coffee", "step_pyramid", "scroll", "sword",
               "gold_bars", "tent"],
        kinds=["turban", "crown", "knight"],
        lines=["By the Sultan's order!", "The caravan is ready.", "Trade first, talk later.", "For the faith!"]),
    "india": dict(
        label="India", words=["india", "indian", "mughal", "delhi", "bombay", "mumbai", "gandhi", "raj", "bengal",
                              "taj mahal", "maharaja", "ganges", "hindu"],
        places=[{"type": "city", "skyline": "delhi"}, {"type": "street", "style": "arab"}, {"type": "palace"},
                {"type": "jungle"}, {"type": "field"}],
        props=["taj_mahal", "elephant", "teapot", "palm_tree", "mosque", "gold_bars", "rice_bowl", "lion"],
        kinds=["turban", "crown", "britain", "civ"],
        lines=["Freedom is coming.", "The spice must flow.", "Namaste!", "We will not be moved."]),
    "japan": dict(
        label="Japan", words=["japan", "japanese", "tokyo", "samurai", "shogun", "edo", "meiji", "kyoto", "ninja",
                              "emperor hirohito", "pearl harbor", "hiroshima", "nagasaki", "tokugawa", "sushi"],
        places=[{"type": "city", "skyline": "tokyo"}, {"type": "street", "style": "asia"}, {"type": "mountains"},
                {"type": "harbor"}, {"type": "map", "center": [137, 37], "width": 22, "style": "dark"}],
        props=["torii", "pagoda", "sushi", "bamboo", "sword", "lantern", "ship", "carrier", "plane", "rice_bowl"],
        kinds=["japan", "samurai", "headband", "navy"],
        lines=["Banzai!", "Honor above all.", "For the Emperor!", "Hai!"]),
    "china": dict(
        label="China", words=["china", "chinese", "beijing", "peking", "dynasty", "ming", "qing", "han dynasty",
                              "mao", "great wall", "shanghai", "kublai", "confucius", "opium", "forbidden city"],
        places=[{"type": "city", "skyline": "beijing"}, {"type": "street", "style": "asia"}, {"type": "mountains"},
                {"type": "palace"}, {"type": "map", "center": [105, 34], "width": 50, "style": "dark"}],
        props=["great_wall", "pagoda", "dragon", "panda", "bamboo", "lantern", "rice_bowl", "teapot", "gold_bars",
               "scroll", "rocket"],
        kinds=["china", "crown", "army"],
        lines=["The Emperor commands it!", "Ten thousand years!", "Build the wall higher!", "Harmony!"]),
    "spain": dict(
        label="Spain & Portugal", words=["spain", "spanish", "madrid", "portugal", "portuguese", "lisbon",
                                         "conquistador", "columbus", "armada", "magellan", "castile", "aragon",
                                         "inquisition", "cortes", "pizarro"],
        places=[{"type": "harbor"}, {"type": "street", "style": "arab"}, {"type": "palace"}, {"type": "sea"},
                {"type": "map", "center": [-20, 25], "width": 110, "style": "dark"}],
        props=["galleon", "bull", "treasure_chest", "gold_bars", "compass", "treasure_map", "cathedral", "sword", "wine", "musket"],
        kinds=["tricorn", "crown", "knight", "pirate"],
        lines=["Land ho!", "For the Crown and gold!", "Ole!", "Set sail at dawn!"]),
    "netherlands": dict(
        label="Netherlands", words=["dutch", "netherlands", "holland", "amsterdam", "tulip", "voc", "rotterdam"],
        places=[{"type": "city", "skyline": "amsterdam"}, {"type": "street", "style": "europe"}, {"type": "field"},
                {"type": "harbor"}],
        props=["windmill", "flowers", "cheese", "galleon", "cash", "gold_bars", "keg"],
        kinds=["dutch", "tophat", "civ"],
        lines=["Tulips for sale!", "Business is business.", "Lekker!", "Buy low, sell high!"]),
    "mesoamerica": dict(
        label="Aztecs, Maya & Mexico", words=["aztec", "maya", "mayan", "inca", "mexico", "mexican", "tenochtitlan",
                                              "montezuma", "peru", "andes", "machu picchu", "olmec"],
        places=[{"type": "jungle"}, {"type": "desert"}, {"type": "mountains"}, {"type": "street", "style": "western"}],
        props=["step_pyramid", "cactus", "gold_bars", "treasure_chest", "eagle", "spear", "galleon", "volcano"],
        kinds=["headband", "crown", "knight", "cowboy"],
        lines=["For the Sun God!", "Gold? What gold?", "The gods are angry!", "Viva Mexico!"]),
    "vikings": dict(
        label="Vikings & Scandinavia", words=["viking", "norse", "scandinavia", "norway", "sweden", "denmark",
                                              "danish", "odin", "thor", "valhalla", "iceland", "longship", "raid"],
        places=[{"type": "sea", "time": "storm"}, {"type": "snow"}, {"type": "mountains"}, {"type": "beach"},
                {"type": "field", "time": "dusk"}],
        props=["viking_ship", "axe", "shield", "pine_tree", "horse", "beer", "fire",
               "treasure_chest", "sheep"],
        kinds=["viking", "furhat", "crown"],
        lines=["To Valhalla!", "Skal!", "Raid first, ask later!", "Odin is watching!"]),
    "mongols": dict(
        label="Mongols & the steppe", words=["mongol", "genghis", "khan", "steppe", "horde", "kublai", "huns",
                                             "attila", "nomad"],
        places=[{"type": "hills"}, {"type": "field"}, {"type": "desert"}, {"type": "snow"},
                {"type": "map", "center": [80, 45], "width": 110, "style": "dark"}],
        props=["horse", "tent", "camel", "sword", "catapult", "gold_bars", "eagle", "sheep"],
        kinds=["furhat", "headband", "crown"],
        lines=["Ride!", "The Khan commands it!", "Surrender or else!", "More horses!"]),
    "africa": dict(
        label="Africa", words=["africa", "african", "zulu", "mali", "mansa musa", "ethiopia", "kenya", "congo",
                               "nigeria", "south africa", "sahara", "timbuktu", "colonial", "scramble for africa"],
        places=[{"type": "desert"}, {"type": "jungle"}, {"type": "hills", "time": "dusk"}, {"type": "street",
                                                                                          "style": "arab"}],
        props=["lion", "elephant", "hut", "gold_bars", "camel", "palm_tree", "spear", "shield", "drum"],
        kinds=["headband", "crown", "turban", "civ"],
        lines=["This land is ours!", "Gold for everyone!", "We stand together!"]),
    "australia": dict(
        label="Australia", words=["australia", "australian", "sydney", "melbourne", "outback", "kangaroo",
                                  "new zealand", "emu"],
        places=[{"type": "city", "skyline": "sydney"}, {"type": "desert"}, {"type": "beach"}],
        props=["opera_house", "sheep", "rocks", "palm_tree", "galleon"],
        kinds=["cowboy", "civ", "britain"],
        lines=["G'day mate!", "No worries!", "Crikey!"]),
    # ---- subjects
    "sea": dict(
        label="the sea", words=["sea", "ocean", "navy", "naval", "ship", "fleet", "sail", "sailor", "pirate", "harbor",
                                "harbour", "port", "island", "coast", "atlantic", "pacific", "voyage", "explorer",
                                "submarine", "u-boat", "titanic", "whale", "admiral", "shipwreck", "fish"],
        places=[{"type": "sea"}, {"type": "harbor"}, {"type": "beach"}, {"type": "underwater"},
                {"type": "sea", "time": "storm"}, {"type": "sea", "time": "dusk"}],
        props=["galleon", "ship", "submarine", "anchor", "lighthouse", "wave", "whale", "shark", "fish", "octopus",
               "treasure_chest", "compass", "treasure_map", "telescope", "island", "seagull", "rowboat", "ocean_liner",
               "iceberg", "dock", "buoy", "lifebuoy"],
        kinds=["navy", "pirate", "tricorn", "marine"],
        lines=["Land ho!", "All hands on deck!", "Full speed ahead!", "Arrr!", "Abandon ship!"]),
    "space": dict(
        label="space", words=["space", "moon", "rocket", "nasa", "astronaut", "cosmonaut", "orbit", "apollo",
                              "satellite", "sputnik", "mars", "planet", "gagarin", "space race"],
        places=[{"type": "space"}, {"type": "night"}, {"type": "interior"}, {"type": "desert", "time": "night"}],
        props=["rocket", "satellite", "planet", "moon", "star", "telescope", "computer", "flag", "atom"],
        kinds=["astronaut", "ussr", "america", "glasses"],
        lines=["We have liftoff!", "Houston, we have a problem.", "One small step...", "To the stars!"]),
    "medieval": dict(
        label="the Middle Ages", words=["medieval", "middle ages", "knight", "castle", "king", "lord", "peasant",
                                        "feudal", "crusade", "plague", "black death", "monk", "siege", "kingdom",
                                        "duke", "baron"],
        places=[{"type": "street", "style": "medieval"}, {"type": "palace"}, {"type": "field"}, {"type": "hills"},
                {"type": "interior", "wall": "#B9B2A6", "floor": "#7A6A58"}, {"type": "farm"},
                {"type": "market", "style": "medieval"}, {"type": "construction", "what": "castle"}],
        props=["castle", "catapult", "shield", "sword", "horse", "crown", "throne", "cathedral", "rat", "torch",
               "scroll", "keg", "wheat", "watchtower", "bell", "hut"],
        kinds=["knight", "crown", "mitre", "civ"],
        lines=["For the King!", "Charge!", "Hold the gate!", "Long live the King!", "We need more peasants."]),
    "ww1": dict(
        label="World War I", words=["world war i", "world war one", "ww1", "wwi", "great war", "trench", "somme",
                                    "verdun", "1914", "1915", "1916", "1917", "1918", "kaiser", "western front",
                                    "archduke", "gallipoli"],
        places=[{"type": "trench"}, {"type": "battlefield", "style": "ruins"}, {"type": "field", "time": "storm"},
                {"type": "camp"},
                {"type": "map", "center": [10, 50], "width": 40, "style": "dark"}],
        props=["sandbags", "barbed_wire", "biplane", "zeppelin", "helmet", "tank", "cannon", "medal", "telephone",
               "newspaper", "musket"],
        kinds=["army", "helmet", "germany", "britain", "france"],
        lines=["Over the top!", "Home by Christmas!", "Hold the line!", "Gas! Gas!", "Not one step back!"]),
    "ww2": dict(
        label="World War II", words=["world war ii", "world war two", "ww2", "wwii", "nazi", "hitler", "churchill",
                                     "d-day", "normandy", "blitz", "stalingrad", "pearl harbor", "1939", "1940",
                                     "1941", "1942", "1943", "1944", "1945", "allies", "axis", "luftwaffe",
                                     "panzer", "midway"],
        places=[{"type": "battlefield", "style": "ruins"}, {"type": "city", "time": "night"}, {"type": "beach"},
                {"type": "factory", "style": "inside"}, {"type": "camp"},
                {"type": "map", "center": [15, 50], "width": 45, "style": "dark"}],
        props=["tank", "plane", "ship", "carrier", "submarine", "helmet", "bomb", "sandbags", "radio", "medal",
               "newspaper", "telephone", "flag"],
        kinds=["army", "helmet", "navy", "pilot", "marine", "germany", "japan", "ussr", "britain", "america"],
        lines=["We shall never surrender!", "Go, go, go!", "Incoming!", "Hold the line!", "For freedom!"]),
    "cold_war": dict(
        label="the Cold War", words=["cold war", "nuclear", "missile", "cuba", "berlin wall", "kgb", "cia", "spy",
                                     "iron curtain", "khrushchev", "reagan", "gorbachev", "arms race", "vietnam",
                                     "korea"],
        places=[{"type": "interior"}, {"type": "city", "skyline": "washington"}, {"type": "city", "skyline": "moscow"},
                {"type": "space"}, {"type": "map", "center": [20, 45], "width": 120, "style": "dark"}],
        props=["telephone", "rocket", "satellite", "briefcase", "atom", "mushroom_cloud", "chess_piece", "computer",
               "podium", "helicopter", "wall"],
        kinds=["america", "ussr", "glasses", "army", "tophat_gray"],
        lines=["Mr. Gorbachev, tear down this wall!", "Your move.", "Don't push the button!", "It's just a test..."]),
    "revolution": dict(
        label="revolution", words=["revolution", "revolt", "rebellion", "uprising", "protest", "liberty", "rights",
                                   "independence", "rebels", "mob", "storming", "republic", "overthrow"],
        places=[{"type": "street", "style": "europe"}, {"type": "palace"}, {"type": "street", "style": "europe",
                                                                            "time": "night"},
                {"type": "city", "time": "dusk"}],
        props=["barricade", "flag", "musket", "torch", "guillotine", "newspaper", "megaphone", "crown", "scroll",
               "bell", "podium"],
        kinds=["tricorn", "beret", "civ", "crown"],
        lines=["Liberty or death!", "Down with the King!", "To the barricades!", "Power to the people!"]),
    "wild_west": dict(
        label="the Wild West", words=["wild west", "cowboy", "frontier", "gold rush", "outlaw", "sheriff", "saloon",
                                      "pioneer", "oregon trail", "railroad", "texas", "native american", "buffalo"],
        places=[{"type": "street", "style": "western"}, {"type": "desert"}, {"type": "desert", "time": "dusk"},
                {"type": "mountains"}, {"type": "mine"}, {"type": "market", "style": "western"}, {"type": "farm"}],
        props=["wagon", "cactus", "horse", "pickaxe", "gold_bars", "train", "bull", "barrel", "dynamite", "cash"],
        kinds=["cowboy", "tophat", "headband", "civ"],
        lines=["Yeehaw!", "This town ain't big enough...", "Gold! Gold!", "Reach for the sky!"]),
    "polar": dict(
        label="the poles", words=["arctic", "antarctic", "south pole", "north pole", "polar", "expedition",
                                  "shackleton", "amundsen", "scott", "inuit", "greenland", "glacier", "ice age"],
        places=[{"type": "snow"}, {"type": "snow", "time": "storm"}, {"type": "mountains"}, {"type": "sea",
                                                                                            "time": "storm"}],
        props=["igloo", "iceberg", "penguin", "flag", "compass", "tent", "pine_tree", "ocean_liner"],
        kinds=["furhat", "civ", "navy"],
        lines=["So. Cold.", "We made it!", "Which way is south?", "Keep going!"]),
    "jungle": dict(
        label="jungles", words=["jungle", "rainforest", "amazon", "congo", "vietnam", "explorer", "tribe", "tropical"],
        places=[{"type": "jungle"}, {"type": "beach"}, {"type": "hills"}],
        props=["palm_tree", "bamboo", "hut", "elephant", "lion", "treasure_map", "compass", "rowboat"],
        kinds=["civ", "headband", "army"],
        lines=["Did you hear that?", "This way!", "Watch out!"]),
    "money": dict(
        label="money & economy", words=["economy", "money", "bank", "stock", "market", "trade", "inflation", "debt",
                                        "tax", "rich", "billion", "million", "price", "wall street", "crash",
                                        "depression", "gold"],
        places=[{"type": "interior"}, {"type": "city"}, {"type": "street", "style": "europe"}, {"type": "market"},
                {"type": "factory"}],
        props=["cash", "gold_bars", "moneybag", "coin", "piggy_bank", "line_chart", "bar_chart", "briefcase", "lock",
               "newspaper"],
        kinds=["tophat", "glasses", "civ", "bowler"],
        lines=["Buy! Buy! Buy!", "Sell everything!", "We're rich!", "Where did the money go?"]),
    "science": dict(
        label="science & inventions", words=["science", "scientist", "invent", "discover", "experiment", "physics",
                                             "chemistry", "einstein", "newton", "edison", "tesla", "laboratory",
                                             "atom", "electric", "engine"],
        places=[{"type": "lab"}, {"type": "interior"}, {"type": "classroom"}, {"type": "city"}],
        props=["flask", "atom", "gear", "lightbulb", "telescope", "computer", "factory", "train", "book", "apple"],
        kinds=["glasses", "graduate", "hardhat", "civ"],
        lines=["Eureka!", "It works!", "Science!", "Back to the drawing board."]),
    "industry": dict(
        label="industry & work", words=["industrial revolution", "factory", "factories", "mill", "steam engine",
                                        "railway", "railroad", "coal", "steel", "textile", "workers", "carnegie",
                                        "rockefeller", "ford", "assembly line", "manufactur", "strike", "union",
                                        "miners", "child labor", "child labour"],
        places=[{"type": "factory"}, {"type": "factory", "style": "inside"}, {"type": "construction", "what": "factory"},
                {"type": "city", "skyline": "london", "time": "dusk"},
                {"type": "street", "style": "europe", "time": "dusk"}],
        props=["factory", "train", "railway", "gear", "cash", "moneybag", "newspaper", "pickaxe", "hammer", "keg"],
        kinds=["tophat", "hardhat", "cap", "bowler", "civ"],
        lines=["Faster!", "Twelve-hour shifts?!", "Productivity!", "More coal!", "We want better pay!"]),
    "plague": dict(
        label="plague & disease", words=["plague", "black death", "disease", "pandemic", "epidemic", "virus",
                                         "smallpox", "flu", "cholera", "doctor"],
        places=[{"type": "street", "style": "medieval"}, {"type": "dark"}, {"type": "interior"}],
        props=["rat", "candle", "flask", "gravestone", "wagon", "bell"],
        kinds=["civ", "glasses", "mitre"],
        lines=["Bring out your dead!", "Wash your hands!", "Stay away!"]),
}

STOP = {"a", "the", "of", "and"}


def _hits(text, words):
    n = 0
    for w in words:
        n += len(re.findall(r"(?<![a-z])" + re.escape(w), text))
    return n


def detect(title="", topic="", beats=(), limit=3):
    """Themes of a whole video, best first."""
    head = f"{title} {topic}".lower()
    body = " ".join((b.get("text", "") if isinstance(b, dict) else str(b)) for b in beats).lower()
    scored = []
    for key, th in THEMES.items():
        s = 3 * _hits(head, th["words"]) + _hits(body, th["words"])
        if s >= 2:
            scored.append((s, key))
    scored.sort(reverse=True)
    return [k for _, k in scored[:limit]]


def beat_themes(text, video_themes=()):
    """Themes for one beat: ones it mentions, then the video's."""
    low = str(text or "").lower()
    own = [k for k, th in THEMES.items() if _hits(low, th["words"])]
    own.sort(key=lambda k: -_hits(low, THEMES[k]["words"]))
    return own + [k for k in video_themes if k not in own]


def kit_block(keys):
    """The storyboard prompt's VISUAL KIT section."""
    import json
    keys = [k for k in keys if k in THEMES]
    if not keys:
        return ""
    out = [f"VISUAL KIT FOR THIS VIDEO (it's about {', '.join(THEMES[k]['label'] for k in keys)}). Build the scenes "
           "in this world, and rotate through these places instead of reusing one background:"]
    for k in keys:
        th = THEMES[k]
        places = " | ".join(json.dumps(p, separators=(",", ":")) for p in th["places"])
        out.append(f"- {th['label']}: places {places}\n  props: {', '.join(th['props'])}\n"
                   f"  hats: {', '.join(th['kinds'])}\n  lines people might shout: {' / '.join(th['lines'])}")
    return "\n".join(out)


# ------------------------------------------------------------------ dialogue
INTENTS = [
    ("rally", ("motivat", "rallied", "rallies", "rally", "inspir", "encourag", "speech", "urged", "roused",
               "fired up", "pep talk", "led his men", "led her men", "addressed his", "addressed the")),
    ("order", ("ordered", "commanded", "orders", "demanded", "decreed", "instructed", "told his", "told them")),
    ("declare", ("declared", "announced", "proclaimed", "declares", "announces")),
    ("warn", ("warned", "threaten", "ultimatum", "or else", "warning")),
    ("promise", ("promised", "vowed", "swore", "pledged", "guaranteed")),
    ("boast", ("boasted", "bragged", "claimed he", "claimed she", "bragging", "showed off")),
    ("refuse", ("refused", "rejected", "said no", "denied", "turned down")),
    ("ask", ("asked", "begged", "pleaded", "requested", "wondered", "proposed")),
    ("complain", ("complained", "protested", "furious", "outraged", "angry")),
    ("plan", ("planned", "plotted", "schemed", "strategy", "the plan")),
    ("surrender", ("surrendered", "gave up", "capitulated")),
    ("celebrate", ("celebrated", "victory", "triumph", "won the", "cheered")),
    ("panic", ("panicked", "fled", "terrified", "shocked", "surprised", "stunned")),
    ("deal", ("agreed", "signed", "treaty", "deal", "alliance", "negotiat")),
    ("say", ("said", "says", "told", "replied", "shouted", "yelled", "famously", "quote", "wrote", "called it")),
]

LINES = {
    "rally": ["Follow me to glory!", "Today we make history!", "Courage, my friends!", "Nothing can stop us now!",
              "Victory is ours to take!", "Stand with me!"],
    "order": ["Do it. Now.", "That's an order!", "Move out!", "Bring me the plans!", "Make it happen!"],
    "declare": ["Hear ye, hear ye!", "From today, things change!", "It is official!", "Let the world know!"],
    "warn": ["Don't even think about it.", "You've been warned!", "Back off!", "Last chance!"],
    "promise": ["I promise!", "You have my word.", "Trust me!", "This time it's different!"],
    "boast": ["I'm the best!", "Too easy!", "Nobody does it better!", "Did you see that?"],
    "refuse": ["No way!", "Absolutely not.", "Nope!", "Not a chance!"],
    "ask": ["Please?", "Can we talk?", "What now?", "Any ideas?"],
    "complain": ["This is outrageous!", "Unacceptable!", "Why me?!", "Not again!"],
    "plan": ["Here's the plan...", "Phase one: begins.", "Trust the plan.", "What could go wrong?"],
    "surrender": ["We give up!", "Okay, okay, you win!", "White flag!"],
    "celebrate": ["We did it!", "Victory!", "Woohoo!", "History made!"],
    "panic": ["Uh oh.", "RUN!", "This is bad!", "Wait, what?!"],
    "deal": ["Deal!", "Sign here.", "Pleasure doing business.", "Shake on it?"],
    "say": ["Listen up!", "Here's the thing...", "Mark my words.", "You heard me!"],
}

MOOD_OK = {"somber": ("say", "ask", "promise", "surrender", "warn", "declare", "order", "refuse", "deal")}
SOMBER_LINES = {"say": ["We will remember."], "ask": ["Why?"], "promise": ["Never again."],
                "surrender": ["It's over."], "warn": ["Please, stop."], "declare": ["We must honor them."],
                "order": ["Help them."], "refuse": ["No more."], "deal": ["Peace, at last."]}


def intent(text):
    low = str(text or "").lower()
    for name, words in INTENTS:
        if any(w in low for w in words):
            return name
    return None


def line_for(text, mood="fun", themes=(), seed=0):
    """A short in-character line for a beat where someone speaks, or None."""
    it = intent(text)
    if it is None:
        return None
    r = random.Random(seed * 7919 + len(str(text)))
    if mood == "somber":
        if it not in MOOD_OK["somber"]:
            return None
        return r.choice(SOMBER_LINES[it])
    pool = list(LINES[it])
    if it in ("rally", "celebrate", "declare") and themes:
        th = THEMES.get(themes[0])
        if th:
            pool += th["lines"][:3] * 2
    return r.choice(pool)


# ------------------------------------------------------------------ variety
PAPERS = ["#FAF5E8", "#F3EAD3", "#EEF3F7", "#F6EEE6", "#EFF5E9", "#F7F0DC"]
RAYS = ["#FFECAF", "#FFD8B0", "#D8ECFF", "#E4F5D4", "#F9D5E5", "#FFE6A0"]
TIME_NEXT = {"day": "dusk", "dusk": "night", "night": "dawn", "dawn": "day", "storm": "day"}
PAINTED = ("field", "hills", "desert", "snow", "city", "battlefield", "street", "harbor", "beach", "jungle",
           "mountains", "farm", "market", "camp", "factory")


def bg_sig(bg):
    bg = bg or {}
    t = bg.get("type", "paper")
    if t == "map":
        return None          # maps are told apart by what is on them
    return (t, bg.get("time"), bg.get("color"), bg.get("ray"), bg.get("style"), bg.get("skyline"), bg.get("wall"),
            bg.get("what"), str(bg.get("progress")))


def vary(scenes, order, editable):
    """scenes: {index: scene}. When a scene looks exactly like the one before it, nudge its colors / time of day.
    Only scenes in `editable` are changed. Returns [(index, what changed)]."""
    changes = []
    prev = prev_bg = None
    for i in order:
        sc = scenes.get(i)
        if not isinstance(sc, dict):
            prev = prev_bg = None
            continue
        bg = sc.setdefault("bg", {"type": "paper"})
        if bg.get("type") == "construction" and prev_bg and prev_bg.get("type") == "construction" and \
                prev_bg.get("what") == bg.get("what") and i in editable:
            # the same building over several beats keeps going up where the last scene left it
            from ..engine.places_work import build_progress
            end = build_progress(prev_bg.get("progress"))[1]
            nxt = "done" if end >= 0.999 else [round(end, 2), round(min(1.0, end + 0.45), 2)]
            if bg.get("progress") != nxt:
                bg["progress"] = nxt
                changes.append((i, "the building keeps rising from the last scene"))
        prev_bg = bg
        sig = bg_sig(bg)
        if sig is not None and sig == prev and i in editable:
            t = bg.get("type", "paper")
            k = i % len(PAPERS)
            if t == "paper":
                bg["color"] = next(c for c in PAPERS[k:] + PAPERS if c != bg.get("color"))
                changes.append((i, "paper color"))
            elif t == "sunburst":
                bg["ray"] = next(c for c in RAYS[k:] + RAYS if c != bg.get("ray"))
                changes.append((i, "sunburst color"))
            elif t in PAINTED:
                bg["time"] = TIME_NEXT.get(bg.get("time") or ("storm" if t == "battlefield" else "day"), "dusk")
                changes.append((i, f"time of day -> {bg['time']}"))
            elif t == "interior":
                bg["wall"] = next(c for c in ["#E8DCC4", "#D9E4EA", "#E9D6D0", "#DCE6D2"][k % 4:] + ["#E8DCC4"]
                                  if c != bg.get("wall"))
                changes.append((i, "wall color"))
            elif t == "dark":
                bg["color"] = "#2E3248" if bg.get("color") != "#2E3248" else "#3A2E3E"
                changes.append((i, "dark tone"))
            sig = bg_sig(bg)
        prev = sig
    return changes


REACTIONS = {"fun": ["Wait, what?", "Interesting...", "Hold on.", "Oh no.", "Classic.", "Hmm!"],
             "tense": ["This is bad.", "Not good.", "Steady...", "Here they come!", "Get ready!"],
             "somber": []}


def speaker_for(els, text, cast=()):
    """The character who should talk: the cast member named first in the narration, else the biggest one."""
    chars = [e for e in els if isinstance(e, dict) and e.get("type") == "char" and e.get("lon") is None]
    if not chars:
        return None
    low = str(text or "").lower()
    named = []
    for c in cast or []:
        name = str(c.get("name") or "").strip().lower()
        if name and name in low:
            named.append((low.index(name), str(c.get("kind") or "").lower()))
    for _, kind in sorted(named):
        for e in chars:
            if str(e.get("kind") or "").lower() == kind:
                return e
    def size(e):
        try:
            return float(e.get("scale", 1.0))
        except (TypeError, ValueError):
            return 1.0
    return max(chars, key=size)


def ensure_dialogue(scene, text, mood="fun", cast=(), themes=(), seed=0):
    """If the narration has someone speaking and the scene has nobody talking, give the right character a line
    (and let a crowd shout back after a rallying speech). Returns True when it added something."""
    if not isinstance(scene, dict):
        return False
    els = scene.get("elements") if isinstance(scene.get("elements"), list) else []
    if any(isinstance(e, dict) and (e.get("type") == "bubble" or e.get("say")) for e in els):
        return False
    line = line_for(text, mood, themes, seed)
    sp = speaker_for(els, text, cast)
    if not line or sp is None:
        return False
    sp["say"] = [line]
    if intent(text) == "rally" and mood != "somber":
        crowd = next((e for e in els if isinstance(e, dict) and e.get("type") == "crowd"), None)
        if crowd is not None:
            th = THEMES.get(themes[0]) if themes else None
            shout = th["lines"][0] if th else "Hooray!"
            if shout != line:
                crowd["say"] = [{"text": shout, "at": 0.62}]
    return True
