"""Author the shipped prop library (studio/knowledge/prop_library.json).

Every design is a list of simple shapes on a 100 x 100 grid (see studio/engine/custom_props.py). They are written here by
hand, checked by the same cleaner the AI's designs go through, and saved as one JSON file the studio loads at startup:
these are the props a video can pick from without asking the AI to draw anything.

    python scripts/build_prop_library.py            # rewrite studio/knowledge/prop_library.json
    python scripts/build_prop_library.py --sheet    # also draw a contact sheet (data/prop_library_sheet.png)

To add a prop: write a function that returns the parts, add it to DESIGNS with its words (tags), the first year it can appear
(`frm`) and a category, run this script, look at the sheet.
"""
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# colours
WOOD, DWOOD, LWOOD = "#8B5A2B", "#5E3B1C", "#B07A44"
STEEL, DSTEEL, LSTEEL = "#9AA0A6", "#4A4F55", "#C9CED3"
GOLD, RED, BLUE, GREEN = "#E0B22E", "#C8302B", "#2B3F8C", "#3C6E47"
CREAM, BLACK, WHITE, SKIN = "#F1E6C8", "#2B2B33", "#FFFFFF", "#F2C9A0"
BRASS, COPPER, LEATHER = "#D4A83A", "#B87333", "#7A4B2A"


def R(x, y, w, h, fill, r=0, **kw):
    return dict(shape="rect", x=x, y=y, w=w, h=h, fill=fill, r=r, **kw)


def C(x, y, r, fill, **kw):
    return dict(shape="circle", x=x, y=y, r=r, fill=fill, **kw)


def E(x, y, rx, ry, fill, **kw):
    return dict(shape="ellipse", x=x, y=y, rx=rx, ry=ry, fill=fill, **kw)


def P(points, fill, **kw):
    return dict(shape="poly", points=points, fill=fill, **kw)


def L(points, color=BLACK, width=2):
    return dict(shape="line", points=points, color=color, width=width)


def ring(x, y, r, stroke, **kw):
    return dict(shape="circle", x=x, y=y, r=r, fill=None, stroke=stroke, **kw)


# ---------------------------------------------------------------- weapons and armour
def pistol():
    return [R(18, 38, 56, 9, DSTEEL), R(72, 37, 7, 11, BLACK), P([[16, 46], [34, 46], [30, 74], [12, 72]], LEATHER),
            E(32, 51, 9, 6, STEEL), P([[26, 38], [31, 28], [36, 38]], DSTEEL), L([[30, 54], [32, 62], [41, 59]], BLACK, 2)]


def bow_and_arrow():
    return [L([[38, 8], [27, 28], [23, 50], [27, 72], [38, 92]], DWOOD, 4), L([[38, 8], [38, 92]], BLACK, 1),
            L([[38, 50], [92, 50]], WOOD, 3), P([[90, 44], [100, 50], [90, 56]], STEEL),
            P([[38, 50], [47, 43], [51, 50]], RED), P([[38, 50], [47, 57], [51, 50]], RED)]


def crossbow():
    return [R(12, 46, 62, 9, LEATHER), L([[60, 16], [74, 50], [60, 84]], DWOOD, 4), L([[60, 16], [40, 50], [60, 84]], BLACK, 1.5),
            L([[28, 50], [76, 50]], WOOD, 2.5), P([[76, 45], [86, 50], [76, 55]], STEEL), P([[16, 55], [26, 55], [22, 68]], DSTEEL)]


def dagger():
    return [P([[46, 6], [54, 6], [57, 60], [50, 72], [43, 60]], LSTEEL), R(33, 60, 34, 7, GOLD), R(45, 67, 10, 20, LEATHER),
            C(50, 91, 5, GOLD), L([[50, 10], [50, 60]], STEEL, 1)]


def knight_armor():
    return [P([[32, 12], [68, 12], [72, 30], [67, 44], [33, 44], [28, 30]], LSTEEL), R(37, 24, 26, 5, BLACK),
            P([[45, 12], [50, 0], [57, 12]], RED), P([[26, 46], [74, 46], [70, 80], [30, 80]], LSTEEL), L([[50, 48], [50, 78]], DSTEEL, 2),
            C(25, 52, 8, STEEL), C(75, 52, 8, STEEL), R(34, 80, 12, 18, STEEL), R(54, 80, 12, 18, STEEL)]


def banner():
    return [R(19, 4, 4, 94, DWOOD), P([[23, 10], [86, 15], [79, 30], [86, 46], [23, 44]], RED), C(52, 28, 9, GOLD), C(21, 5, 4, GOLD),
            L([[30, 20], [78, 22]], GOLD, 1.5), L([[30, 38], [78, 38]], GOLD, 1.5)]


def tricorn_hat():
    return [P([[4, 60], [50, 80], [96, 60], [74, 48], [50, 56], [26, 48]], BLACK), P([[28, 52], [33, 26], [67, 26], [72, 52], [50, 60]], BLACK),
            L([[4, 60], [50, 80], [96, 60]], GOLD, 2.5), C(50, 62, 5, RED), L([[34, 34], [66, 34]], "#3A3A44", 2)]


def top_hat():
    return [R(30, 16, 40, 62, BLACK), E(50, 78, 36, 8, BLACK), R(30, 60, 40, 9, RED), E(50, 16, 20, 5, "#3A3A44")]


# ---------------------------------------------------------------- work, trade, craft
def printing_press():
    return [R(14, 82, 72, 13, DWOOD), R(20, 26, 8, 57, LEATHER), R(72, 26, 8, 57, LEATHER), R(16, 20, 68, 10, LEATHER),
            R(46, 30, 8, 32, DSTEEL), L([[28, 36], [72, 36]], DSTEEL, 4), R(28, 62, 44, 6, STEEL), R(32, 69, 36, 11, CREAM),
            L([[50, 36], [84, 16]], BLACK, 3), C(84, 16, 4, BLACK)]


def telegraph():
    return [R(12, 62, 76, 30, LEATHER), R(24, 54, 36, 8, DSTEEL), L([[28, 50], [64, 44]], BRASS, 4), C(64, 44, 5, BLACK),
            R(68, 32, 16, 22, COPPER), L([[76, 32], [76, 10]], BLACK, 2), L([[18, 78], [82, 78]], DWOOD, 2)]


def anvil():
    return [R(14, 24, 74, 9, "#6B7078"), P([[14, 24], [0, 31], [14, 34]], "#6B7078"), R(36, 33, 28, 36, DSTEEL), R(20, 68, 60, 22, DSTEEL),
            L([[18, 28], [82, 28]], LSTEEL, 1.5)]


def plow():
    return [L([[6, 38], [72, 62]], LEATHER, 5), L([[62, 58], [88, 18]], LEATHER, 5), L([[74, 64], [97, 30]], LEATHER, 4),
            P([[56, 66], [80, 92], [48, 94], [38, 80]], DSTEEL), C(18, 72, 13, None, stroke=DWOOD), L([[18, 72], [18, 59]], DWOOD, 2),
            L([[18, 72], [31, 72]], DWOOD, 2), L([[18, 72], [18, 85]], DWOOD, 2), L([[18, 72], [5, 72]], DWOOD, 2)]


def sickle():
    return [P([[30, 28], [56, 14], [82, 30], [92, 58], [79, 47], [62, 32], [40, 36]], LSTEEL), P([[14, 58], [24, 62], [36, 30], [26, 26]], LEATHER)]


def pitchfork():
    return [R(47, 32, 6, 66, LEATHER), R(28, 30, 44, 6, DSTEEL), R(28, 6, 5, 26, STEEL), R(47.5, 6, 5, 26, STEEL), R(67, 6, 5, 26, STEEL)]


def spinning_wheel():
    spokes = [L([[38, 56], [38 + 26 * math.cos(a), 56 + 26 * math.sin(a)]], DWOOD, 2) for a in [i * math.pi / 4 for i in range(8)]]
    return [R(56, 66, 40, 8, LEATHER), R(62, 74, 5, 22, LEATHER), R(86, 74, 5, 22, LEATHER), R(72, 42, 4, 24, "#C9A66B"),
            ring(38, 56, 28, DWOOD)] + spokes + [C(38, 56, 5, LEATHER), L([[38, 56], [74, 50]], BLACK, 1)]


def cotton_bale():
    return [R(12, 42, 76, 50, "#E8E1D0", r=6), R(28, 42, 5, 50, LEATHER), R(66, 42, 5, 50, LEATHER), R(12, 62, 76, 4, LEATHER),
            C(22, 38, 8, WHITE), C(50, 34, 10, WHITE), C(78, 38, 8, WHITE), C(36, 36, 7, WHITE), C(64, 36, 7, WHITE)]


def sack():
    return [P([[28, 30], [72, 30], [86, 62], [78, 94], [22, 94], [14, 62]], "#C9A66B"), R(38, 20, 24, 12, "#B08D57"),
            L([[34, 32], [66, 32]], LEATHER, 3), L([[30, 60], [70, 60]], "#B08D57", 1.5), L([[28, 76], [72, 76]], "#B08D57", 1.5)]


def bucket():
    return [P([[24, 34], [76, 34], [68, 94], [32, 94]], WOOD), R(27, 50, 46, 5, DSTEEL), R(30, 76, 40, 5, DSTEEL), E(50, 34, 26, 5, DWOOD),
            L([[26, 34], [38, 10], [62, 10], [74, 34]], DSTEEL, 3)]


def ladder():
    rungs = [R(30, y, 40, 4, WOOD) for y in (14, 30, 46, 62, 78)]
    return [R(28, 4, 5, 92, LEATHER), R(67, 4, 5, 92, LEATHER)] + rungs


def wheel():
    spokes = [L([[50, 50], [50 + 38 * math.cos(a), 50 + 38 * math.sin(a)]], WOOD, 3) for a in [i * math.pi / 4 for i in range(8)]]
    return [ring(50, 50, 40, DWOOD)] + spokes + [C(50, 50, 7, LEATHER)]


def corn():
    return [L([[50, 98], [50, 44]], GREEN, 4), P([[50, 90], [18, 62], [30, 58], [50, 78]], GREEN), P([[50, 84], [82, 56], [70, 52], [50, 72]], GREEN),
            E(50, 38, 11, 30, "#F2C94C"), L([[44, 18], [44, 58]], "#D9A92A", 1), L([[50, 14], [50, 62]], "#D9A92A", 1), L([[56, 18], [56, 58]], "#D9A92A", 1),
            P([[38, 40], [50, 8], [62, 40], [50, 52]], GREEN)]


def bread():
    return [E(50, 58, 38, 22, "#C98A4B"), L([[28, 48], [38, 66]], "#E8B87A", 3), L([[44, 44], [54, 66]], "#E8B87A", 3), L([[60, 46], [70, 66]], "#E8B87A", 3)]


def oil_lamp():
    return [E(50, 86, 24, 6, COPPER), E(50, 68, 22, 17, COPPER), P([[68, 62], [92, 48], [90, 58], [68, 74]], COPPER), L([[28, 60], [12, 62], [14, 78], [28, 76]], COPPER, 3),
            P([[90, 50], [95, 36], [85, 44]], "#FFB020"), C(50, 54, 6, BRASS)]


def street_lamp():
    return [R(46, 32, 8, 64, BLACK), R(38, 88, 24, 8, BLACK), P([[34, 10], [66, 10], [61, 32], [39, 32]], "#FFE9A0"), P([[30, 10], [70, 10], [50, 0]], BLACK),
            R(36, 32, 28, 4, BLACK), L([[50, 12], [50, 30]], "#FFB020", 3)]


def signpost():
    return [R(46, 12, 8, 84, LEATHER), P([[16, 16], [70, 16], [82, 28], [70, 40], [16, 40]], "#D9B77A"), P([[84, 46], [32, 46], [20, 58], [32, 70], [84, 70]], "#C8A064"),
            L([[26, 28], [60, 28]], DWOOD, 2), L([[44, 58], [76, 58]], DWOOD, 2)]


# ---------------------------------------------------------------- navigation
def ship_wheel():
    spokes, knobs = [], []
    for i in range(8):
        a = i * math.pi / 4
        spokes.append(L([[50, 50], [50 + 38 * math.cos(a), 50 + 38 * math.sin(a)]], LEATHER, 4))
        knobs.append(C(50 + 44 * math.cos(a), 50 + 44 * math.sin(a), 4, LEATHER))
    return [ring(50, 50, 30, LEATHER)] + spokes + knobs + [C(50, 50, 8, WOOD), C(50, 50, 3, GOLD)]


def sextant():
    return [P([[50, 90], [16, 30], [24, 22], [50, 16], [76, 22], [84, 30]], BRASS), L([[22, 34], [50, 22], [78, 34]], BLACK, 2),
            L([[50, 90], [66, 28]], DSTEEL, 3), R(46, 80, 8, 16, LEATHER), C(50, 90, 4, DSTEEL)]


def canoe():
    return [P([[2, 54], [98, 54], [86, 72], [50, 78], [14, 72]], "#A66A3A"), E(50, 54, 46, 5, DWOOD), L([[62, 22], [38, 70]], LEATHER, 3),
            P([[34, 66], [44, 72], [34, 86], [26, 80]], LEATHER)]


# ---------------------------------------------------------------- justice, belief, symbols
def scales():
    return [R(47, 18, 6, 72, GOLD), R(30, 88, 40, 8, GOLD), R(12, 18, 76, 5, GOLD), L([[16, 22], [8, 56]], BLACK, 1), L([[16, 22], [28, 56]], BLACK, 1),
            P([[5, 56], [31, 56], [27, 64], [9, 64]], GOLD), L([[84, 22], [72, 56]], BLACK, 1), L([[84, 22], [94, 56]], BLACK, 1), P([[69, 56], [97, 56], [91, 64], [75, 64]], GOLD)]


def gavel():
    return [R(24, 18, 46, 22, LEATHER, r=4), R(30, 18, 5, 22, GOLD), R(59, 18, 5, 22, GOLD), R(43, 38, 8, 52, WOOD), E(50, 93, 26, 5, DWOOD)]


def chains():
    links = [E(24, 50, 12, 8, LSTEEL), E(40, 50, 7, 12, STEEL), E(54, 50, 12, 8, LSTEEL), E(68, 50, 7, 12, STEEL)]
    return [C(9, 50, 9, DSTEEL), C(91, 50, 9, DSTEEL), C(9, 50, 4, WHITE), C(91, 50, 4, WHITE)] + links + [E(82, 50, 7, 11, LSTEEL)]


def skull():
    teeth = [L([[x, 70], [x, 79]], BLACK, 1.5) for x in (42, 46, 50, 54, 58)]
    return [C(50, 42, 28, "#F4F0E6"), R(36, 62, 28, 18, "#F4F0E6", r=4), C(38, 44, 7, BLACK), C(62, 44, 7, BLACK),
            P([[50, 52], [45, 62], [55, 62]], BLACK)] + teeth


def cross():
    return [R(44, 6, 12, 90, WOOD), R(22, 26, 56, 12, WOOD), L([[50, 10], [50, 92]], DWOOD, 1)]


def totem_pole():
    return [R(32, 2, 36, 96, WOOD), P([[8, 14], [32, 24], [32, 8]], RED), P([[92, 14], [68, 24], [68, 8]], RED), P([[50, 18], [60, 28], [50, 30]], GOLD),
            C(42, 14, 4, WHITE), C(58, 14, 4, WHITE), R(36, 38, 28, 22, GREEN), C(44, 45, 4, WHITE), C(56, 45, 4, WHITE), R(42, 52, 16, 5, RED),
            R(36, 66, 28, 28, BLUE), C(44, 74, 4, WHITE), C(56, 74, 4, WHITE), R(42, 84, 16, 5, GOLD)]


def wreath():
    leaves = [C(50 + 30 * math.cos(a), 50 + 30 * math.sin(a), 7, GREEN) for a in [i * math.pi / 6 for i in range(12)]]
    berries = [C(50 + 30 * math.cos(a), 50 + 30 * math.sin(a), 3, RED) for a in (0.3, 2.0, 3.6, 5.2)]
    return [ring(50, 50, 30, GREEN)] + leaves + berries + [P([[50, 84], [38, 98], [46, 100]], RED), P([[50, 84], [62, 98], [54, 100]], RED), C(50, 84, 4, RED)]


def rose():
    return [L([[50, 50], [50, 96]], GREEN, 3), P([[50, 78], [68, 66], [62, 84]], GREEN), C(50, 36, 17, RED), C(50, 36, 9, "#A82020"), C(50, 36, 3, RED)]


def handshake():
    return [P([[4, 48], [40, 40], [54, 52], [40, 64], [4, 60]], SKIN), R(0, 44, 15, 22, BLUE), P([[96, 48], [60, 40], [46, 52], [60, 64], [96, 60]], "#E7B88E"),
            R(85, 44, 15, 22, RED), E(50, 52, 11, 10, SKIN), L([[43, 48], [57, 48]], BLACK, 1), L([[43, 53], [57, 53]], BLACK, 1), L([[43, 58], [57, 58]], BLACK, 1)]


def fist():
    return [R(28, 32, 44, 40, SKIN, r=10), L([[39, 34], [39, 50]], BLACK, 1.5), L([[50, 34], [50, 50]], BLACK, 1.5), L([[61, 34], [61, 50]], BLACK, 1.5),
            E(37, 60, 14, 7, SKIN), R(34, 72, 32, 24, BLUE)]


def peace_sign():
    return [C(50, 50, 38, WHITE), L([[50, 12], [50, 88]], BLACK, 4), L([[50, 50], [24, 76]], BLACK, 4), L([[50, 50], [76, 76]], BLACK, 4)]


def coffin():
    return [P([[30, 4], [70, 4], [84, 36], [64, 96], [36, 96], [16, 36]], DWOOD), R(46, 18, 8, 28, GOLD), R(38, 28, 24, 7, GOLD)]


# ---------------------------------------------------------------- animals
def bison():
    legs = [R(x, 74, 7, 22, "#3E2810") for x in (30, 41, 62, 73)]
    return [E(54, 56, 34, 24, DWOOD), C(34, 42, 18, "#4A2E14"), E(16, 62, 14, 12, DWOOD), P([[10, 52], [4, 40], [17, 47]], CREAM),
            L([[88, 52], [95, 68]], "#3E2810", 3)] + legs + [C(13, 60, 2, WHITE)]


def deer():
    legs = [R(x, 68, 5, 28, "#8A5A2B") for x in (34, 44, 62, 72)]
    return [E(54, 58, 26, 14, LWOOD), P([[30, 54], [36, 38], [46, 40], [42, 58]], LWOOD), E(34, 30, 9, 7, LWOOD), C(78, 54, 4, WHITE)] + legs + \
           [L([[34, 25], [28, 6]], DWOOD, 2), L([[34, 25], [42, 6]], DWOOD, 2), L([[31, 14], [22, 10]], DWOOD, 2), L([[39, 14], [48, 10]], DWOOD, 2)]


def donkey():
    legs = [R(x, 66, 5, 30, "#6E6E76") for x in (32, 42, 62, 72)]
    return [E(54, 58, 28, 14, "#8C8C94"), P([[28, 54], [30, 36], [44, 38], [40, 56]], "#8C8C94"), E(24, 42, 11, 8, "#8C8C94"), P([[28, 34], [26, 18], [34, 30]], "#8C8C94"),
            P([[34, 34], [36, 18], [42, 32]], "#8C8C94"), L([[80, 52], [90, 74]], "#6E6E76", 3)] + legs


DESIGNS = {
    # name: (builder, anchor, description, tags, first year, last year, category)
    "pistol": (pistol, "center", "flintlock pistol", "pistol pistols revolver handgun sidearm duel dueling", 1550, 3000, "weapon"),
    "bow_and_arrow": (bow_and_arrow, "center", "bow and arrow", "bow bows arrow arrows archer archers archery longbow bowman", -3000, 1600, "weapon"),
    "crossbow": (crossbow, "center", "crossbow", "crossbow crossbows crossbowmen bolt", 1000, 1600, "weapon"),
    "dagger": (dagger, "bottom", "dagger", "dagger daggers knife knives blade stiletto assassin assassination stabbed", -3000, 3000, "weapon"),
    "knight_armor": (knight_armor, "bottom", "suit of armor", "armor armour knight knights chainmail plate crusader crusaders medieval", 1000, 1600, "weapon"),
    "banner": (banner, "bottom", "war banner on a pole", "banner banners standard standards pennant colors rally", -3000, 3000, "symbol"),
    "tricorn_hat": (tricorn_hat, "center", "tricorn hat", "tricorn tricorne cockade colonial revolutionary", 1680, 1830, "clothes"),
    "top_hat": (top_hat, "center", "top hat", "tophat gentleman victorian lincoln", 1790, 3000, "clothes"),
    "printing_press": (printing_press, "bottom", "printing press", "press printer printing gutenberg pamphlet pamphlets broadside typeset", 1440, 1900, "craft"),
    "telegraph": (telegraph, "bottom", "telegraph key", "telegraph telegraphs morse wire wires telegram", 1844, 1960, "tech"),
    "anvil": (anvil, "bottom", "blacksmith's anvil", "anvil forge blacksmith smith ironworks iron steel foundry", -1000, 3000, "craft"),
    "plow": (plow, "bottom", "plow", "plow plough plowing farming farmer farmers peasant peasants", -3000, 3000, "farm"),
    "sickle": (sickle, "center", "sickle", "sickle scythe harvest harvesting reap reaping", -3000, 3000, "farm"),
    "pitchfork": (pitchfork, "bottom", "pitchfork", "pitchfork pitchforks mob hay", -1000, 3000, "farm"),
    "spinning_wheel": (spinning_wheel, "bottom", "spinning wheel", "spinning loom weaving weaver textile textiles yarn thread", 1200, 1900, "craft"),
    "cotton_bale": (cotton_bale, "bottom", "bale of cotton", "cotton bale bales plantation", 1600, 1900, "trade"),
    "sack": (sack, "bottom", "sack of goods", "sack sacks grain flour sugar spice spices pepper bag", -3000, 3000, "trade"),
    "bucket": (bucket, "bottom", "wooden bucket", "bucket pail well", -3000, 3000, "tool"),
    "ladder": (ladder, "bottom", "ladder", "ladder ladders climb scaling", -3000, 3000, "tool"),
    "wheel": (wheel, "center", "wooden cart wheel", "wheel wheels cartwheel", -3500, 3000, "tool"),
    "corn": (corn, "bottom", "ear of corn", "corn maize cob", -3000, 3000, "farm"),
    "bread": (bread, "center", "loaf of bread", "bread loaf loaves bakery baker", -3000, 3000, "food"),
    "oil_lamp": (oil_lamp, "center", "oil lamp", "oillamp lamp lamps lamplight", -1000, 1900, "light"),
    "street_lamp": (street_lamp, "bottom", "street lamp", "streetlamp streetlight gaslight gaslamp", 1810, 1950, "light"),
    "signpost": (signpost, "bottom", "signpost", "signpost crossroads directions", -1000, 3000, "tool"),
    "ship_wheel": (ship_wheel, "center", "ship's wheel", "helm steering captain wheel", 1600, 3000, "sea"),
    "sextant": (sextant, "center", "sextant", "sextant astrolabe quadrant navigation navigator navigators", 1730, 1950, "sea"),
    "canoe": (canoe, "bottom", "canoe", "canoe canoes paddle paddles kayak", -3000, 3000, "sea"),
    "scales": (scales, "bottom", "scales of justice", "scales justice trial trials lawsuit fairness", -2000, 3000, "law"),
    "gavel": (gavel, "bottom", "judge's gavel", "gavel judge judges court courtroom sentence sentenced verdict jury", 1700, 3000, "law"),
    "chains": (chains, "center", "iron chains", "chains chain shackles shackled slave slaves slavery enslaved captive captives prisoner prisoners bondage", -3000, 3000, "law"),
    "skull": (skull, "center", "skull", "skull skulls bones skeleton death deadly plague poison", -3000, 3000, "symbol"),
    "christian_cross": (cross, "bottom", "wooden Christian cross", "crucifix crusade crusades crusader crusaders christian christianity missionary missionaries pope calvary", 30, 3000, "symbol"),
    "totem_pole": (totem_pole, "bottom", "totem pole", "totem totems tribe tribal", -1000, 3000, "culture"),
    "wreath": (wreath, "center", "wreath", "wreath laurel memorial honor", -1000, 3000, "symbol"),
    "rose": (rose, "bottom", "rose", "rose roses romance", -1000, 3000, "symbol"),
    "handshake": (handshake, "center", "handshake", "handshake alliance allies agreement deal negotiation negotiations diplomacy accord pact", -1000, 3000, "symbol"),
    "fist": (fist, "bottom", "raised fist", "fist resistance strike strikes union unions labor defiance", 1700, 3000, "symbol"),
    "peace_sign": (peace_sign, "center", "peace sign", "peace pacifist hippie anti-war", 1958, 3000, "symbol"),
    "coffin": (coffin, "bottom", "coffin", "coffin coffins funeral funerals burial buried", -1000, 3000, "death"),
    "bison": (bison, "bottom", "bison", "bison buffalo buffaloes plains", -3000, 3000, "animal"),
    "deer": (deer, "bottom", "deer", "deer elk stag antelope hunt hunting venison", -3000, 3000, "animal"),
    "donkey": (donkey, "bottom", "donkey", "donkey mule burro pack", -3000, 3000, "animal"),
}

# props that already exist in the engine, reached by more words (and a few with a changed look: a tea chest is a crate marked TEA)
ALIASES = {
    "tea_chest": dict(prop="crate", params={"label": "TEA"}, words="tea chest|tea chests|chests of tea|tea crates|tea crate"),
    "white_flag": dict(prop="flag", color="#FFFFFF", words="white flag|flag of truce|truce flag|surrendered flag"),
}


# words too general to point at one prop: a sentence with "well", "top" or "death" in it is not about a pistol or a coffin
VAGUE = set("""and top sign well deal court press plate pack pole standard standards strike strikes sentence sentenced hunt
climb directions thread wire wires street hat ship colors accord deadly defiance fairness resistance romance honor labor death
steel iron oil union unions captain smith bag bolt blade chain scaling steering medieval victorian colonial revolutionary tribal
tribe agreement alliance allies deal diplomacy negotiation negotiations navigation union""".split())


def build():
    from studio.engine.custom_props import clean_design
    out, problems = [], []
    for name, (fn, anchor, desc, tags, frm, to, cat) in DESIGNS.items():
        d = clean_design(dict(name=name, anchor=anchor, description=desc, parts=fn()))
        if not d:
            problems.append(name)
            continue
        d.update(tags=sorted(set(tags.split()) - VAGUE), frm=frm, to=to, cat=cat)
        out.append(d)
    return out, problems


def main():
    designs, problems = build()
    if problems:
        sys.exit("designs the cleaner rejected: " + ", ".join(problems))
    path = os.path.join(ROOT, "studio", "knowledge", "prop_library.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(note="Hand-authored vector props (scripts/build_prop_library.py). Do not edit by hand: change the script and rebuild.",
                       props=designs, aliases={k: dict(v, words=v["words"].split("|")) for k, v in ALIASES.items()}),
                  f, indent=0, ensure_ascii=False)
    print(f"wrote {len(designs)} props to {os.path.relpath(path, ROOT)}")
    if "--sheet" in sys.argv:
        from studio.engine.custom_props import kit_sheet
        out = os.path.join(ROOT, "data", "prop_library_sheet.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        kit_sheet(designs, out, cell=200)
        print("sheet:", out)


if __name__ == "__main__":
    main()
