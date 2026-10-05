from props import *
import terr

SC = []


def S(f):
    SC.append(f)
    return f


SUN = (255, 236, 175)
DARK = (44, 46, 62)
SOMBER = (205, 205, 210)

VA = View(124, 36, 52)
VJ = View(136, 36, 24)
VSE = View(113, 6, 52)
VPAC = View(163, 18, 112)
VW = View(134, 16, 100)
VM = View(124, 43, 30)
VCH = View(116, 33, 36)
VSOL = View(157, -5, 30)


def paper(sc, col=PAPER):
    with sc.background(col) as p:
        pass


def burst(sc, col=PAPER, ray=SUN):
    with sc.background(col) as p:
        p.sunburst(960, 520, col=ray)


def ground(sc, sky=(198, 228, 245), gnd=(222, 205, 160), gy=860):
    with sc.background(sky) as p:
        p.d.rectangle([0, gy * SS, W * SS, H * SS], fill=gnd)
        p.line([(0, gy), (W, gy)], 6, INK, 0.5)
        p.cloud(300, 180, 0.9)
        p.cloud(1550, 140, 0.7)
    return gy


def seascape(sc, sky=(200, 228, 246), sea=SEA, horizon=520):
    with sc.background(sky) as p:
        p.d.rectangle([0, horizon * SS, W * SS, H * SS], fill=sea)
        r = random.Random(sc.idx)
        for i in range(30):
            x, y = r.randint(0, W), r.randint(horizon + 20, H)
            p.line([(x, y), (x + 30, y - 7), (x + 60, y)], 5, SEA2, 0.5)
        p.cloud(350, 160, 0.8)
        p.cloud(1500, 210, 0.6)
    return horizon


# ------------------------------------------------------------------ 0-3 hook
@S
def s0(sc):
    burst(sc)
    with sc.layer("slide_r", 0.02, z=0) as p:
        p.factory(1500, 860, 1.0)
    sc.char(1300, 900, 1.55, "america", at=0.05, arms=CROSS, mouth="smirk", eyes="dot", flip=True)
    sc.char(560, 900, 0.85, "japan", at=0.0, arms=((20, 15), (150, 30)), mouth="open", eyes="angry", extra=("vein",))
    sc.label("JAPAN", 560, 545, 50, RED, at=0.1)
    sc.label("USA", 1020, 330, 56, NAVY, at=0.15)
    sc.label("~ 1/10 the factories", 560, 430, 46, INK, f="hand", at=sc.w("industrial"))
    sc.camera(1.0, 1.06, (900, 560))


@S
def s1(sc):
    paper(sc)
    sc.char(960, 880, 1.0, "japan", at=0.0, arms=((150, 20), (150, 20)), mouth="grin", eyes="angry", prop="sword")
    sc.char(330, 880, 0.95, "britain", at=sc.w("Britain"), arms=HIPS, mouth="frown", eyes="angry", prop="teacup", flip=False)
    sc.char(1580, 880, 0.9, "dutch", at=sc.w("Dutch"), arms=HIPS, mouth="frown", eyes="angry", flip=True)
    with sc.layer("pop", sc.w("Australia")) as p:
        p.stick(1800, 880, 0.75, "marine", arms=HIPS, mouth="frown", eyes="angry", flip=True)
    sc.char(620, 520, 0.7, "china", at=sc.w("China"), arms=((100, 10), (40, 10)), mouth="open", eyes="angry", prop="sword", idle="shake")
    sc.label("still at war with China", 620, 120, 52, INK, f="hand", at=sc.w("China"))
    sc.label("not winning", 620, 185, 46, RED, f="hand", at=sc.w("not winning"))


@S
def s2(sc):
    paper(sc, (246, 240, 226))
    sc.char(520, 900, 1.15, "japan", at=0.0, arms=((20, 15), (70, 50)), mouth="smile", eyes="happy")
    with sc.layer("pop", 0.05) as p:
        p.rect(820, 250, 620, 480, (255, 255, 250), 7, r=12)
        p.text("THE PLAN", 1130, 310, 64, RED)
        p.text("1. fight everyone", 860, 410, 52, INK, anchor="lm", f="hand")
        p.text("2. ???", 860, 490, 52, INK, anchor="lm", f="hand")
        p.text("3. win", 860, 570, 52, INK, anchor="lm", f="hand")
    with sc.layer("pop", sc.w("It was")) as p:
        p.text("terrible", 1130, 660, 70, RED, f="hand")
    with sc.layer("pop", sc.w("rewind"), idle="pulse") as p:
        p.rect(1500, 130, 300, 140, INK, 0, r=24)
        p.poly([(1560, 200), (1630, 150), (1630, 250)], WHITE, 0)
        p.poly([(1640, 200), (1710, 150), (1710, 250)], WHITE, 0)
        p.text("~1850", 1650, 320, 52, INK)


@S
def s3(sc):
    burst(sc, (250, 244, 228), (255, 226, 160))
    with sc.layer("drop", 0.02) as p:
        p.text("JAPAN", 960, 250, 170, RED, stroke=12)
    with sc.layer("drop", 0.15) as p:
        p.text("in World War II", 960, 400, 96, INK, stroke=10)
    sc.char(680, 940, 0.9, "japan", at=0.3, arms=CHEER, mouth="grin", eyes="happy")
    sc.char(1250, 940, 0.9, "america", at=0.38, arms=CROSS, mouth="smirk", flip=True)
    sc.label("let's go!", 960, 720, 70, INK, f="hand", at=sc.w("go"))
    sc.camera(1.0, 1.05)


# ------------------------------------------------------------------ 4-11 background
@S
def s4(sc):
    hz = seascape(sc)
    with sc.background((200, 228, 246)) as p:
        p.d.rectangle([0, hz * SS, W * SS, H * SS], fill=SEA)
        p.blob(1700, hz + 30, 400, 90, (150, 190, 120), 6, INK, 16, 0.2, 7)
        p.cloud(400, 160, 0.8)
    with sc.layer("slide_l", 0.02, idle="float", move=(380, 0, 0.0, 0.6)) as p:
        for i, (x, y) in enumerate(((300, 640), (60, 720), (-160, 610))):
            p.ship(x, y, 1.1, (50, 52, 60))
            p.smoke(x - 10, y - 90, 0.8, (90, 90, 100))
    sc.char(1580, 760, 0.7, "japan", at=0.15, arms=SHRUG, mouth="o", eyes="wide", look=-1)
    with sc.layer("pop", 0.15) as p:
        p.poly([(1480, 790), (1690, 790), (1660, 830), (1510, 830)], BROWN, 5)
    sc.label("1853", 960, 140, 110, INK, at=0.0)
    with sc.layer("pop", sc.w("open up")) as p:
        bubble(p, 860, 320, 560, 150, "trade with us...\nor else.", 50, tail=(-120, 90))


@S
def s5(sc):
    paper(sc)
    with sc.layer("pop", 0.05) as p:
        p.ship(450, 520, 1.4, (50, 52, 60))
        p.smoke(440, 400, 0.9, (90, 90, 100))
    with sc.layer("pop", sc.w("wooden")) as p:
        p.poly([(1350, 520), (1530, 520), (1500, 560), (1380, 560)], BROWN, 6)
        p.line([(1440, 520), (1440, 420)], 6, BROWN, 0.3)
        p.poly([(1445, 425), (1500, 500), (1445, 500)], WHITE, 5)
    sc.char(960, 880, 1.0, "japan", at=0.0, arms=THINK, mouth="flat", eyes="dot", look=-1)
    with sc.layer("pop", sc.w("decides"), idle="pulse") as p:
        p.circ(960, 340, 50, YELLOW, 6)
        p.rect(940, 385, 40, 30, GRAY, 5)
    sc.label("if you can't beat them...", 960, 140, 56, INK, f="hand", at=sc.w("if you"))
    sc.label("BECOME THEM", 960, 215, 70, RED, at=sc.w("become"))


@S
def s6(sc):
    ground(sc)
    with sc.layer("slide_r", sc.w("railways")) as p:
        p.railway(0, 1920, 840)
        p.train(1450, 760, 0.9)
    with sc.layer("pop", sc.w("factories")) as p:
        p.factory(1500, 720, 0.75)
    sc.char(330, 860, 0.8, "army", at=sc.w("army"), arms=((20, 15), (60, 40)), mouth="smile", prop=("flag", RED))
    with sc.layer("pop", sc.w("navy")) as p:
        p.ship(760, 640, 0.9, GRAY)
    sc.char(1020, 860, 0.9, "japan", at=0.0, arms=CHEER, mouth="grin", eyes="happy", legs=RUN)
    with sc.layer("pop", sc.w("Meiji"), idle="pulse") as p:
        p.text("MEIJI ERA", 960, 130, 100, RED, stroke=10)
        p.text("speedrun mode", 960, 215, 46, INK, f="hand")
    with sc.layer("pop", sc.w("fast")) as p:
        p.speed(870, 640, 4, 200)


@S
def s7(sc):
    sc.map_bg(VA, base_terr=[(terr.HOME, RED)], labels=[("CHINA", 112, 33, 50), ("RUSSIA", 121, 46.5, 50)])
    sc.terr(terr.TAIWAN, at=sc.w("Taiwan"))
    sc.label("1895", *sc.ll(117, 23), 62, RED, at=sc.w("1895"))
    sc.terr(terr.SSAKH, at=sc.w("Russia"))
    sc.label("1905", *sc.ll(146.5, 45.5), 62, RED, at=sc.w("1905"))
    sc.char(*sc.ll(105, 26), 0.55, "china", at=sc.w("China"), arms=SHRUG, mouth="frown", eyes="sad", extra=("sweat",))
    sc.char(*sc.ll(134, 44), 0.45, "ussr", at=sc.w("Russia"), arms=UP, mouth="scream", eyes="wide", extra=("!",))
    sc.char(*sc.ll(141, 34), 0.5, "japan", at=0.02, arms=CHEER, mouth="grin")
    sc.camera(1.0, 1.05, (1100, 520))


@S
def s8(sc):
    sc.map_bg(VA, base_terr=[(terr.S1905, RED)])
    sc.terr(terr.KOREA, at=sc.w("Korea"))
    sc.label("1910", *sc.ll(124, 37.5), 56, RED, at=sc.w("Korea"))
    with sc.layer("drop", sc.w("empire"), idle="float") as p:
        x, y = sc.ll(139, 39)
        p.poly([(x - 60, y - 40), (x - 60, y - 110), (x - 30, y - 70), (x, y - 120), (x + 30, y - 70), (x + 60, y - 110), (x + 60, y - 40)], YELLOW, 6)
    sc.char(*sc.ll(139, 32), 0.55, "japan", at=0.05, arms=CHEER, mouth="grin", eyes="happy")
    sc.label("EMPIRE!", 960, 130, 90, RED, at=sc.w("empire"))


@S
def s9(sc):
    paper(sc)
    sc.char(380, 880, 1.0, "japan", at=0.0, arms=SHRUG, mouth="wavy", eyes="worried", extra=("sweat",))
    for i, (word, lab, fn) in enumerate((("oil", "OIL", "barrel"), ("rubber", "RUBBER", "tire"), ("iron", "IRON", "ingot"))):
        x = 820 + i * 330
        with sc.layer("pop", sc.w(word)) as p:
            if fn == "barrel":
                p.barrel(x, 470, 1.2)
            elif fn == "tire":
                p.circ(x, 470, 80, (50, 50, 56), 8)
                p.circ(x, 470, 34, PAPER, 6)
            else:
                p.poly([(x - 90, 520), (x + 90, 520), (x + 60, 430), (x - 60, 430)], (150, 150, 165), 7)
            p.text(lab, x, 620, 50, INK)
        with sc.layer("pop", sc.w(word) + 0.05) as p:
            xmark(p, x, 470, 85)
    with sc.layer("drop", sc.w("Remember"), idle="float") as p:
        note(p, 1450, 210, "REMEMBER:\nno oil!", 50, 340, 200)


@S
def s10(sc):
    paper(sc, (238, 236, 230))
    with sc.layer("wipe_r", 0.05, edur=1.4) as p:
        chart(p, 1100, 700, 640, 420, [(0, 0.9), (0.3, 0.8), (0.55, 0.45), (0.8, 0.25), (1, 0.05)], RED)
        p.text("SILK EXPORTS", 1420, 250, 50, INK)
    sc.char(480, 880, 1.0, "civ", at=sc.w("farmers"), arms=((70, 75), (70, 75)), mouth="frown", eyes="sad", extra=("tear",))
    with sc.layer("pop", sc.w("broke")) as p:
        p.text("$0", 480, 380, 80, RED)
    sc.label("1929: Great Depression", 640, 130, 60, INK, at=0.0)


@S
def s11(sc):
    ground(sc)
    with sc.layer("pop", 0.0) as p:
        p.rect(820, 700, 260, 160, (190, 150, 100), 6)
    sc.char(950, 700, 0.9, "army", at=0.02, arms=((20, 15), (80, 10)), mouth="scream", eyes="angry", prop="megaphone")
    with sc.layer("pop", sc.w("pitch")) as p:
        bubble(p, 1460, 300, 560, 170, "WE NEED LAND!\nAND OIL!", 54, tail=(-160, 80))
    for i, x in enumerate((240, 420, 600)):
        sc.char(x, 900, 0.7, "civ", at=0.1 + i * 0.05, arms=AD, mouth="o", eyes="wide", look=1)
    sc.label("the loudest guys in the room", 520, 140, 52, INK, f="hand", at=0.05)


@S
def s12(sc):
    sc.map_bg(VM, base_terr=[(terr.S1910, RED)], labels=[("CHINA", 115, 38, 48)])
    sc.terr(terr.MANCHURIA, col=(255, 222, 120), at=0.05, outline=(170, 120, 30))
    x, y = sc.ll(125, 45.5)
    sc.label("MANCHURIA", x, y, 70, (150, 90, 20), at=0.08)
    for i, (word, lab) in enumerate((("coal", "coal"), ("iron", "iron"), ("farmland", "farmland"))):
        sc.label(lab, x - 220 + i * 230, y + 110, 48, INK, f="hand", at=sc.w(word))
    sc.char(*sc.ll(135.5, 39.6), 0.5, "army", at=0.1, arms=POINT_L, mouth="smirk", eyes="dot", look=-1)
    sc.camera(1.0, 1.06, (900, 480))


@S
def s13(sc):
    gy = ground(sc, (250, 214, 160), (205, 175, 120))
    with sc.layer("pop", 0.0, z=0) as p:
        p.railway(0, 1920, 760)
    sc.char(330, 860, 0.8, "army", at=0.05, arms=((20, 15), (100, 0)), mouth="smirk", eyes="dot", flip=False)
    with sc.layer("pop", sc.w("bomb")) as p:
        boom(p, 900, 720, 130)
    with sc.layer("pop", sc.w("bomb") + 0.04) as p:
        p.smoke(880, 650, 1.2)
    sc.char(1550, 860, 0.8, "china", at=sc.w("blame"), arms=SHRUG, mouth="o", eyes="wide", extra=("q",), flip=True)
    with sc.layer("pop", sc.w("blame")) as p:
        bubble(p, 520, 380, 420, 130, "THEY did it!", 52, tail=(-100, 90))
    sc.label("Mukden, 1931", 960, 120, 70, INK, at=0.0)


@S
def s14(sc):
    sc.map_bg(VM, base_terr=[(terr.S1910, RED)])
    sc.terr(terr.MANCHURIA, at=0.08, edur=1.4)
    sc.char(*sc.ll(127, 45), 0.5, "army", at=0.2, arms=CHEER, mouth="grin", eyes="happy")
    sc.char(*sc.ll(135.5, 39.6), 0.5, "tophat_gray", at=sc.w("Tokyo"), arms=UP, mouth="scream", eyes="wide", extra=("!",))
    sc.label("Tokyo: \"we never ordered that\"", 640, 820, 52, INK, f="hand", at=sc.w("never"))


@S
def s15(sc):
    paper(sc, (244, 238, 226))
    with sc.layer("drop", 0.15, idle="float") as p:
        puppet(p, 960, 860, 0.9)
    sc.label("Manchukuo", 960, 150, 70, RED, at=sc.w("Manchukuo"))
    sc.char(330, 880, 0.9, "army", at=0.0, arms=((150, 20), (150, 20)), mouth="smirk")
    sc.char(1600, 880, 0.9, "tophat_gray", at=sc.w("shrugs"), arms=SHRUG, mouth="flat", eyes="dot")
    sc.label("punished? nope.", 1600, 330, 52, INK, f="hand", at=sc.w("Nope"))


@S
def s16(sc):
    paper(sc, (232, 228, 218))
    with sc.layer("pop", 0.0) as p:
        p.ell(720, 640, 470, 120, (160, 120, 85), 7)
    for i, (x, k) in enumerate(((400, "britain"), (580, "france"), (760, "italy"), (940, "civ"))):
        sc.char(x, 760, 0.62, k, at=0.03 + i * 0.03, arms=((40, -60), (40, -60)), mouth="frown", eyes="angry", shadow=False)
    sc.label("League of Nations", 720, 140, 66, INK, at=0.0)
    with sc.layer("pop", 0.0) as p:
        door(p, 1600, 900, 240, 420)
    sc.char(1360, 900, 0.85, "japan", at=sc.w("walks"), arms=((60, 40), (20, 15)), legs=WALK, mouth="smirk", eyes="closed",
            move=(180, 0, sc.w("walks"), 0.95))
    sc.label("BYE", 1600, 380, 80, RED, at=sc.w("quits"))


@S
def s17(sc):
    paper(sc)
    sc.char(450, 880, 1.0, "army", at=0.0, arms=((20, 15), (60, 40)), mouth="smirk", prop="paper")
    with sc.layer("pop", 0.08) as p:
        p.rect(900, 200, 760, 360, WHITE, 7, r=14)
        p.text("lesson learned:", 1280, 260, 52, INK, f="hand")
        p.text("1. act first", 960, 350, 56, INK, anchor="lm", f="hand")
        p.text("2. politicians clean up", 960, 450, 56, INK, anchor="lm", f="hand")
    with sc.layer("pop", sc.w("act first")) as p:
        check(p, 1600, 350, 34, 12)
    with sc.layer("pop", sc.w("clean up")) as p:
        check(p, 1600, 450, 34, 12)
    sc.char(1250, 900, 0.75, "tophat_gray", at=sc.w("politicians"), arms=((50, 30), (50, 30)), mouth="wavy", eyes="worried", extra=("sweat",))
    with sc.layer("pop", sc.w("clean up")) as p:
        p.line([(1350, 760), (1440, 900)], 8, BROWN, 0.3)
        p.poly([(1410, 880), (1480, 880), (1490, 920), (1400, 920)], YELLOW, 5)


@S
def s18(sc):
    with sc.background((220, 226, 236)) as p:
        p.d.rectangle([0, 820 * SS, W * SS, H * SS], fill=(245, 248, 252))
        r = random.Random(3)
        for i in range(70):
            p.circ(r.randint(0, W), r.randint(0, 800), r.randint(4, 8), WHITE, 0)
    for i in range(5):
        sc.char(260 + i * 210, 880, 0.7, "army", at=0.02 + i * 0.04, arms=((20, 15), (60, 40)), legs=WALK, mouth="flat", eyes="angry",
                move=(80, 0, 0.0, 1.0))
    sc.label("1932 & 1936", 1450, 160, 70, INK, at=0.0)
    sc.label("coup: failed", 1450, 300, 60, RED, f="hand", at=sc.w("fails"))
    with sc.layer("wipe_u", sc.w("stronger")) as p:
        p.arrow(1450, 760, 1450, 420, (60, 170, 80), 22)
        p.text("army power", 1600, 600, 46, INK, f="hand", anchor="lm")


# ------------------------------------------------------------------ 19-24 China
@S
def s19(sc):
    with sc.background((236, 226, 205)) as p:
        p.d.rectangle([0, 780 * SS, W * SS, H * SS], fill=(150, 190, 210))
        p.rect(300, 600, 1320, 70, (190, 180, 165), 7)
        for i in range(7):
            p.d.chord([(330 + i * 185) * SS, 640 * SS, (480 + i * 185) * SS, 860 * SS], 180, 360, fill=(150, 190, 210), outline=INK, width=6 * SS)
        for i in range(12):
            p.rect(320 + i * 110, 565, 22, 40, (190, 180, 165), 4)
    sc.char(560, 600, 0.65, "army", at=0.05, arms=((20, 15), (90, 0)), mouth="open", eyes="angry", shadow=False)
    sc.char(1360, 600, 0.65, "china", at=0.08, arms=((90, 0), (20, 15)), mouth="open", eyes="angry", shadow=False, flip=True)
    with sc.layer("pop", sc.w("shootout")) as p:
        boom(p, 960, 400, 70)
        p.text("BANG", 960, 400, 40, INK)
    sc.label("Marco Polo Bridge, 1937", 960, 130, 66, INK, at=0.0)
    sc.label("FULL WAR", 960, 260, 80, RED, at=sc.w("full war"))


@S
def s20(sc):
    paper(sc)
    sc.char(450, 880, 1.0, "army", at=0.0, arms=((20, 15), (95, -5)), mouth="grin", eyes="dot")
    with sc.layer("pop", 0.05) as p:
        p.calendar(800, 260, 1.8, 3)
        p.text("3 months", 980, 720, 64, INK, f="hand")
    with sc.layer("pop", sc.w("off by")) as p:
        xmark(p, 980, 470, 170, 22)
    sc.label("actually: 8 YEARS", 1520, 470, 70, RED, at=sc.w("eight"), idle="pulse")


@S
def s21(sc):
    sc.map_bg(VCH, base_terr=[(terr.S1932, RED)])
    sc.city("Shanghai", 121.5, 31.2, at=0.05, size=44, dy=48)
    sc.city("Nanjing", 118.8, 32.06, at=sc.w("Nanjing"), size=44)
    sc.city("Beijing", 116.4, 39.9, at=0.02, size=40)
    occ = terr.CHINA_OCC.intersection(geo_box(110, 26, 123, 41))
    sc.terr(occ, at=0.1, edur=1.6)
    sc.arrow([sc.ll(121.2, 31.0), sc.ll(119.2, 31.9)], at=sc.w("marches"), curve=-20, w=12)
    sc.label("1937", 960, 120, 80, INK, at=0.0)


@S
def s22(sc):
    with sc.background((40, 42, 56)) as p:
        p.city(120, 820, 16, False, 1.0)
    with sc.layer("fade", 0.05, edur=1.2) as p:
        p.d.rectangle([0, 0, W * SS, H * SS], fill=(20, 20, 30, 120))
    for i, x in enumerate((560, 760, 960, 1160, 1360)):
        with sc.layer("fade", 0.2 + i * 0.08, edur=1.0) as p:
            p.candle(x, 900, 1.5)
    sc.label("Nanjing, December 1937", 960, 140, 62, (235, 235, 245), scol=(20, 20, 30), enter="fade", at=0.0)
    sc.camera(1.0, 1.03)


@S
def s23(sc):
    paper(sc, (40, 42, 56))
    with sc.layer("fade", 0.1, edur=1.4) as p:
        p.candle(960, 760, 3.0)
    sc.label("never forget", 960, 260, 70, (235, 235, 245), scol=(20, 20, 30), f="hand", enter="fade", at=0.25)


@S
def s24(sc):
    sc.map_bg(VCH, base_terr=[(terr.S1938, RED)], labels=[("CHINA", 106, 30, 56)])
    sc.city("Chongqing", 106.5, 29.6, at=sc.w("inland"), size=42, dy=52)
    sc.arrow([sc.ll(118.5, 31.8), sc.ll(107.5, 29.9)], col=(60, 90, 160), at=sc.w("inland"), curve=60)
    sc.char(*sc.ll(104, 33.5), 0.5, "china", at=sc.w("fighting"), arms=((20, 15), (150, 20)), mouth="open", eyes="angry", prop="sword")
    sc.char(*sc.ll(116, 36.5), 0.5, "army", at=sc.w("stuck"), arms=SHRUG, mouth="wavy", eyes="worried", extra=("sweat",))
    with sc.layer("pop", sc.w("burning")) as p:
        gauge(p, 1660, 330, 120, 0.12)
        p.text("oil", 1660, 380, 44, INK, stroke=6)
    sc.camera(1.0, 1.05)


# ------------------------------------------------------------------ 25-34 road to war
@S
def s25(sc):
    paper(sc, (236, 232, 222))
    with sc.layer("pop", 0.0) as p:
        table(p, 960, 760, 900)
        p.doc(1150, 690, 130, 70, 2)
    sc.char(560, 900, 0.85, "germany", at=0.02, arms=((60, 40), (20, 15)), mouth="smirk", eyes="dot")
    sc.char(960, 900, 0.85, "japan", at=sc.w("pact"), arms=((20, 15), (70, 20)), mouth="smile", eyes="dot")
    sc.char(1360, 900, 0.85, "italy", at=sc.w("Italy"), arms=((20, 15), (60, 40)), mouth="grin", eyes="happy", flip=True)
    sc.label("1940", 960, 130, 80, INK, at=sc.w("1940"))
    sc.label("new friends!", 700, 270, 60, (60, 150, 80), f="hand", at=sc.w("New friends"))
    sc.label("terrible friends.", 1250, 270, 60, RED, f="hand", at=sc.w("Terrible"))


@S
def s26(sc):
    sc.map_bg(VSE, base_terr=[(terr.S1938, RED)], labels=[("THAILAND", 101, 15.5, 30)])
    sc.terr(terr.FR_INDO, col=(110, 140, 220), at=sc.w("France"), outline=(40, 60, 120))
    sc.terr(terr.DUTCH_EI, col=(250, 165, 70), at=sc.w("Netherlands"), outline=(150, 90, 30))
    sc.label("French Indochina", *sc.ll(108, 18), 40, (40, 60, 120), at=sc.w("France"))
    sc.label("Dutch East Indies", 760, 830, 44, (130, 70, 20), at=sc.w("Netherlands"))
    with sc.layer("drop", sc.w("unguarded"), idle="float") as p:
        sign(p, *sc.ll(124, 2), 340, 110, "UNGUARDED", 48)
    for i, (lon, lat) in enumerate(((101.5, -1), (114.5, 0.5), (117, -2.5))):
        with sc.layer("pop", sc.w("oil-rich") + i * 0.03) as p:
            x, y = sc.ll(lon, lat)
            p.barrel(x, y, 0.45)
    sc.char(*sc.ll(117.5, 19.2), 0.45, "japan", at=0.05, arms=THINK, mouth="smirk", eyes="dot", look=1)


@S
def s27(sc):
    sc.map_bg(VSE, base_terr=[(terr.S1938, RED)])
    sc.terr(terr.INDO_N, at=sc.w("north"), edur=0.9, enter="wipe_d")
    sc.label("1940", *sc.ll(103, 23), 50, RED, at=sc.w("north"))
    sc.terr(terr.INDOCHINA.difference(terr.INDO_N), at=sc.w("south"), edur=1.0, enter="wipe_d")
    sc.label("1941", *sc.ll(110.5, 12), 50, RED, at=sc.w("south"))
    sc.camera(1.0, 1.08, (870, 420))


@S
def s28(sc):
    paper(sc)
    with sc.layer("pop", 0.0) as p:
        p.pipe(250, 330, 1650, 330)
        p.circ(960, 330, 60, RED, 7)
        p.line([(920, 330), (1000, 330)], 12, WHITE, 0.2)
        p.text("OIL", 600, 270, 48, INK)
    sc.char(960, 900, 1.0, "america", at=0.02, arms=((20, 15), (150, 20)), mouth="flat", eyes="angry")
    sc.char(620, 900, 0.75, "britain", at=sc.w("Britain"), arms=CROSS, mouth="flat", eyes="angry")
    sc.char(1300, 900, 0.75, "dutch", at=sc.w("Dutch"), arms=CROSS, mouth="flat", eyes="angry", flip=True)
    with sc.layer("pop", sc.w("freezes")) as p:
        p.rect(240, 160, 220, 140, (190, 230, 250), 6, r=14)
        p.text("$", 350, 230, 80, INK)
        p.text("frozen", 350, 340, 44, (60, 120, 180), f="hand")
    sc.label("OIL EMBARGO", 1450, 220, 80, RED, at=sc.w("cuts off"), idle="pulse")


@S
def s29(sc):
    paper(sc, (244, 238, 226))
    with sc.layer("pop", 0.02) as p:
        pie(p, 520, 480, 230, 0.8)
        p.text("80%", 470, 430, 90, WHITE, stroke=6, scol=INK)
        p.text("from USA", 520, 780, 52, INK)
    with sc.layer("pop", sc.w("navy")) as p:
        gauge(p, 1350, 560, 230, 0.12)
    sc.label("~1.5 years left", 1350, 720, 60, RED, f="hand", at=sc.w("year and a half"))
    sc.char(1700, 900, 0.6, "navy", at=sc.w("navy"), arms=SHRUG, mouth="wavy", eyes="worried", extra=("sweat",), flip=True)


@S
def s30(sc):
    paper(sc)
    with sc.layer("pop", sc.w("Option one")) as p:
        p.rect(140, 180, 760, 600, (232, 246, 236), 7, r=24)
        p.text("OPTION 1", 520, 250, 66, (50, 130, 70))
        p.text("leave China,", 520, 360, 52, INK, f="hand")
        p.text("get the oil back", 520, 425, 52, INK, f="hand")
        p.barrel(520, 600, 0.9)
    with sc.layer("pop", sc.w("Option two")) as p:
        p.rect(1020, 180, 760, 600, (250, 232, 228), 7, r=24)
        p.text("OPTION 2", 1400, 250, 66, RED)
        p.text("take the oil", 1400, 360, 52, INK, f="hand")
        p.text("by force", 1400, 425, 52, INK, f="hand")
        p.sword(1400, 660, 1.2, 25)
    sc.label("Tokyo's choice", 960, 110, 56, INK, at=0.0)


@S
def s31(sc):
    paper(sc)
    with sc.layer("pop", 0.0) as p:
        p.rect(140, 180, 760, 600, (232, 246, 236), 7, r=24)
        p.text("OPTION 1", 520, 250, 66, (50, 130, 70))
        p.text("leave China", 520, 380, 52, INK, f="hand")
        p.rect(1020, 180, 760, 600, (250, 232, 228), 7, r=24)
        p.text("OPTION 2", 1400, 250, 66, RED)
        p.text("take the oil", 1400, 380, 52, INK, f="hand")
    with sc.layer("pop", sc.w("absolutely not")) as p:
        xmark(p, 520, 480, 240, 34)
    sc.char(960, 920, 0.95, "army", at=0.05, arms=CROSS, mouth="frown", eyes="angry", extra=("vein",))
    with sc.layer("pop", sc.w("So, option two"), idle="pulse") as p:
        p.rect(1010, 170, 780, 620, None, 14, col=(60, 170, 80), r=26)
    sc.label("ABSOLUTELY NOT", 960, 110, 64, RED, at=sc.w("absolutely not"))


@S
def s32(sc):
    sc.map_bg(VW, base_terr=[(terr.S1941, RED)])
    sc.terr(terr.DUTCH_EI, col=(250, 165, 70), at=0.0, outline=(150, 90, 30), enter="fade")
    sc.terr(terr.PHIL, col=(110, 140, 220), at=sc.w("Philippines"), outline=(40, 60, 120))
    sc.arrow([sc.ll(131, 31), sc.ll(116, -1)], at=0.05, curve=-140, w=14)
    sc.label("Dutch oil", *sc.ll(112, -6), 46, (130, 70, 20), at=0.1)
    sc.label("US Philippines", *sc.ll(129, 13.5), 40, (40, 60, 120), at=sc.w("Philippines"))
    with sc.layer("pop", sc.w("Pearl")) as p:
        x, y = 1700, sc.ll(180, 23)[1]
        p.text("Pearl Harbor >", x, y, 46, NAVY, stroke=7)
        p.ship(x - 40, y + 90, 0.5, GRAY)


@S
def s33(sc):
    paper(sc)
    sc.char(380, 880, 1.0, "navy", at=0.0, arms=((20, 15), (95, -5)), mouth="flat", eyes="worried")
    sc.label("Admiral Yamamoto", 380, 360, 50, INK, at=0.02)
    with sc.layer("wipe_r", sc.w("run wild"), edur=1.2) as p:
        p.line([(700, 520), (1760, 520)], 14, INK, 0.3)
        p.rect(700, 470, 560, 100, (120, 200, 120), 6, r=20)
        p.text("winning", 980, 520, 48, INK)
    sc.label("6 months", 980, 420, 46, INK, f="hand", at=sc.w("six months"))
    sc.label("1 year", 1260, 620, 46, INK, f="hand", at=sc.w("maybe a year"))
    with sc.layer("pop", sc.w("we lose")) as p:
        p.rect(1270, 470, 490, 100, (230, 110, 100), 6, r=20)
        p.text("losing", 1515, 520, 48, WHITE)


@S
def s34(sc):
    paper(sc, (232, 240, 248))
    with sc.layer("pop", 0.1) as p:
        p.rect(760, 200, 900, 560, (60, 110, 180), 8, r=12)
        for i in range(8):
            p.line([(780, 240 + i * 66), (1640, 240 + i * 66)], 2, (110, 150, 210), 0)
        p.text("TOP SECRET PLAN", 1210, 270, 58, WHITE)
        p.carrier(1000, 500, 0.7)
        p.dotted([(1100, 480), (1300, 420), (1500, 520)], WHITE)
        p.text("X", 1540, 540, 80, YELLOW)
    sc.char(450, 900, 1.0, "navy", at=0.0, arms=((20, 15), (95, -5)), mouth="wavy", eyes="worried", extra=("sweat",))
    sc.label("a really, REALLY good one", 1210, 830, 56, RED, f="hand", at=sc.w("really, really"))


# ------------------------------------------------------------------ 35-44 Pearl Harbor & expansion
@S
def s35(sc):
    sc.map_bg(VPAC, base_terr=[(terr.S1941, RED)], labels=[("PACIFIC OCEAN", 172, 8, 54)])
    sc.city("Pearl Harbor", 202.0, 21.3, at=0.0, size=42, col=NAVY)
    start, end = sc.ll(146, 40), sc.ll(198, 26)
    with sc.layer("pop", 0.08, move=(end[0] - start[0] - 40, end[1] - start[1] + 30, 0.1, 0.85)) as p:
        for i in range(6):
            mini_carrier(p, start[0] + (i % 3) * 100 - 100, start[1] + (i // 3) * 50, 2.2)
    sc.arrow([sc.ll(146, 39), sc.ll(198, 24)], col=(250, 250, 250), w=6, at=0.1, edur=3.0, head=False, curve=-120, z=0)
    sc.label("Dec 7, 1941", 960, 120, 80, INK, at=0.0)
    sc.label("350+ planes", *sc.ll(190, 32), 50, RED, at=sc.w("three hundred"))


@S
def s36(sc):
    hz = seascape(sc, (240, 200, 160), (110, 150, 180), 600)
    for i, x in enumerate((360, 700, 1040, 1380, 1650)):
        with sc.layer("pop", 0.0, sfx=None) as p:
            p.ship(x, 700 + (i % 2) * 40, 0.8, GRAY)
        with sc.layer("fade", 0.1 + i * 0.06, edur=1.0, sfx=None) as p:
            p.smoke(x - 20, 630, 1.0, (90, 90, 100))
    for i, (x, y) in enumerate(((300, 200), (700, 140), (1150, 230), (1550, 160))):
        with sc.layer("fade", 0.02, idle="drift", sfx=None) as p:
            p.plane(x, y, 0.45, 8, (200, 205, 215))
    sc.label("Pearl Harbor", 960, 110, 66, INK, enter="fade", at=0.0)
    sc.label("2,400+ Americans killed", 960, 420, 64, (150, 30, 30), enter="fade", at=sc.w("two thousand"))


@S
def s37(sc):
    hz = seascape(sc)
    with sc.layer("pop", 0.0) as p:
        for x in (300, 520, 740):
            p.rect(x - 90, 600, 180, 22, (110, 110, 120), 5)
        p.text("empty", 520, 560, 50, INK, f="hand")
    with sc.layer("pop", sc.w("Except")) as p:
        p.magnifier(520, 380, 1.6)
    with sc.layer("slide_r", sc.w("carriers"), idle="float") as p:
        p.carrier(1350, 640, 1.0)
        p.carrier(1650, 720, 0.8)
        p.carrier(1600, 590, 0.6)
    sc.label("the carriers weren't home", 1400, 160, 56, NAVY, f="hand", at=sc.w("weren't"))
    sc.label("A huge success!", 520, 160, 60, RED, at=0.0)


@S
def s38(sc):
    ground(sc, (250, 220, 200), (222, 205, 160))
    for i in range(9):
        x = 160 + i * 200
        if 780 < x < 1140:
            continue
        sc.char(x, 860, 0.55, "civ", at=sc.w("very angry") + (i % 4) * 0.04, arms=((150, 20), (20, 15)), mouth="open", eyes="angry")
    sc.char(960, 900, 1.25, "america", at=0.0, arms=((40, -100), (40, -100)), mouth="frown", eyes="angry", extra=("vein", "steam"), idle="shake")
    sc.label("very angry", 520, 200, 64, RED, f="hand", at=sc.w("angry"))
    sc.label("very united", 1400, 200, 64, NAVY, f="hand", at=sc.w("united"))


@S
def s39(sc):
    sc.map_bg(VW, base_terr=[(terr.S1941, RED)])
    targets = [("Malaya", 102, 4, "Malaya"), ("Hong Kong", 114.2, 22.3, "Hong Kong"), ("Philippines", 121, 15, "Philippines"),
               ("Guam", 144.8, 13.4, "Guam"), ("Wake", 166.6, 19.3, "Wake")]
    origin = sc.ll(128, 26)
    for name, lon, lat, word in targets:
        sc.arrow([origin, sc.ll(lon, lat)], at=sc.w(word), edur=0.4, w=10, curve=30)
        sc.city(name, lon, lat, at=sc.w(word), size=40)
    with sc.layer("pop", sc.w("speedrun"), idle="pulse") as p:
        p.rect(1400, 80, 440, 130, INK, 0, r=20)
        p.text("SPEEDRUN", 1620, 125, 54, (120, 255, 140))
        p.text("00:00:07", 1620, 180, 40, WHITE)


@S
def s40(sc):
    with sc.background((190, 225, 200)) as p:
        p.d.rectangle([0, 760 * SS, W * SS, H * SS], fill=(210, 190, 140))
        for i in range(10):
            x = 100 + i * 200
            p.line([(x, 760), (x + 10, 560)], 10, BROWN, 0.6)
            for a in (-60, -20, 25, 65):
                p.line([(x + 10, 560), (x + 10 + math.sin(math.radians(a)) * 90, 560 + math.cos(math.radians(a)) * 30)], 10, (60, 140, 70), 0.6)
    for i in range(3):
        x = 300 + i * 420
        with sc.layer("slide_l", 0.02 + i * 0.05, idle="bob", move=(260, 0, 0.1, 1.0)) as p:
            bike(p, x, 900, 1.0)
            p.stick(x - 5, 790, 0.6, "army", arms=((70, 20), (70, 20)), legs=((40, -40), (-20, 40)), mouth="grin", eyes="dot", shadow=False)
            p.speed(x - 130, 760, 3, 140)
    sc.label("Malay Peninsula", 960, 110, 64, INK, at=0.0)
    sc.label("on bicycles!", 960, 200, 56, RED, f="hand", at=sc.w("bicycles"))


@S
def s41(sc):
    seascape(sc, (226, 238, 248), SEA, 700)
    with sc.layer("pop", 0.0) as p:
        p.fort(960, 760, 1.9)
        p.cannon(700, 560, 1.4)
        p.cannon(1240, 560, 1.4)
    sc.label("FORTRESS", 960, 300, 80, INK, at=0.02)
    with sc.layer("pop", sc.w("surrender")) as p:
        p.line([(960, 430), (960, 230)], 8, BROWN, 0.2)
        p.poly([(960, 230), (1100, 240), (1095, 300), (960, 300)], WHITE, 6)
    sc.char(330, 900, 0.9, "britain", at=sc.w("surrender"), arms=SHRUG, mouth="frown", eyes="sad", extra=("tear",), prop="teacup")
    sc.label("~80,000 surrender", 1500, 180, 56, RED, at=sc.w("eighty"))
    sc.label("\"worst disaster\"", 330, 330, 50, INK, f="hand", at=sc.w("worst"))


@S
def s42(sc):
    sc.map_bg(VW, base_terr=[(terr.S1941, RED)])
    for word, g in (("Philippines", terr.PHIL), ("Dutch", terr.DUTCH_EI), ("Burma", terr.C("Myanmar"))):
        sc.terr(g, at=sc.w(word), edur=0.6)
    rest = terr.S1942.difference(terr.S1941).difference(terr.PHIL).difference(terr.DUTCH_EI).difference(terr.C("Myanmar"))
    sc.terr(rest, at=sc.w("mid-1942"), edur=0.8)
    sc.label("1942", 960, 110, 90, RED, at=sc.w("mid-1942"))
    sc.char(*sc.ll(137, 31), 0.5, "japan", at=sc.w("gigantic"), arms=CHEER, mouth="grin", eyes="happy")
    sc.camera(1.0, 1.05)


@S
def s43(sc):
    paper(sc, (214, 210, 204))
    with sc.layer("pop", 0.0, sfx=None) as p:
        sign(p, 960, 470, 1100, 260, "Greater East Asia\nCo-Prosperity Sphere", 60)
        p.circ(1450, 260, 50, YELLOW, 6)
        p.circ(1433, 250, 6, INK, 0)
        p.circ(1467, 250, 6, INK, 0)
        p.d.arc([1420 * SS, 245 * SS, 1480 * SS, 290 * SS], 20, 160, fill=INK, width=6 * SS)
    with sc.layer("fade", sc.w("It was not"), edur=0.6, sfx=None) as p:
        for a, b in (((520, 230), (640, 380)), ((640, 380), (600, 470)), ((1300, 260), (1250, 400))):
            p.line([a, b], 8, INK, 1.5)
    for i in range(6):
        sc.char(330 + i * 260, 980, 0.5, "civ", at=sc.w("Millions") + i * 0.02, arms=((60, 60), (60, 60)), legs=WALK,
                mouth="frown", eyes="sad", enter="fade", idle=None)
    sc.label("forced labor", 960, 120, 56, INK, f="hand", enter="fade", at=sc.w("forced"))


@S
def s44(sc):
    paper(sc)
    with sc.layer("pop", 0.0) as p:
        clock(p, 960, 470, 260, 0.0)
    with sc.layer("pop", 0.0, idle="pulse") as p:
        p.text("6 MONTHS", 960, 140, 80, RED, stroke=8)
    sc.char(400, 900, 0.9, "navy", at=0.1, arms=THINK, mouth="wavy", eyes="worried", look=1, extra=("sweat",))
    sc.label("tick", 1400, 400, 60, INK, f="hand", at=sc.w("ticking"))
    sc.label("tock", 1520, 520, 60, INK, f="hand", at=sc.w("ticking") + 0.1)
    sc.sfx.append((sc.T(sc.w("ticking")), "tick"))


# ------------------------------------------------------------------ 45-52 turning point
@S
def s45(sc):
    with sc.background((255, 214, 170)) as p:
        p.city(900, 860, 9, False, 1.0)
        p.d.rectangle([0, 860 * SS, W * SS, H * SS], fill=(190, 170, 130))
    for i in range(4):
        with sc.layer("slide_l", 0.02 + i * 0.04, idle="float") as p:
            p.plane(200 + i * 180, 200 + (i % 2) * 70, 0.45, 8, (215, 218, 226))
    with sc.layer("pop", sc.w("hit")) as p:
        boom(p, 1200, 760, 50)
    sc.char(450, 900, 1.0, "japan", at=sc.w("embarrassment"), arms=((20, 15), (40, -150)), mouth="wavy", eyes="closed", extra=("blush", "sweat"))
    sc.label("damage: tiny", 1450, 160, 56, INK, f="hand", at=sc.w("tiny"))
    sc.label("embarrassment: ENORMOUS", 1150, 260, 60, RED, at=sc.w("enormous"))
    sc.label("April 1942", 450, 120, 64, INK, at=0.0)


@S
def s46(sc):
    seascape(sc, (214, 236, 250), SEA, 520)
    with sc.layer("pop", 0.05) as p:
        p.island(1300, 640, 1.4)
        p.text("MIDWAY", 1300, 760, 56, INK, stroke=6)
    with sc.layer("drop", sc.w("trap")) as p:
        mousetrap(p, 1300, 600, 1.0)
    sc.char(450, 900, 1.0, "navy", at=0.0, arms=((20, 15), (95, -5)), mouth="smirk", eyes="dot")
    sc.label("the trap", 760, 300, 60, RED, f="hand", at=sc.w("trap"))


@S
def s47(sc):
    paper(sc, (226, 232, 240))
    with sc.layer("pop", 0.0) as p:
        table(p, 860, 760, 760)
        p.rect(560, 600, 260, 160, (90, 90, 100), 6, r=12)
        for i in range(5):
            p.circ(600 + i * 45, 650, 12, (200, 200, 210), 3)
    sc.char(1150, 900, 0.95, "headphones", at=0.05, arms=((60, 40), (60, 40)), mouth="smirk", eyes="dot")
    with sc.layer("pop", sc.w("know the plan")) as p:
        p.rect(1380, 200, 420, 300, WHITE, 6)
        p.text("DECODED", 1590, 250, 44, RED)
        p.text("target: Midway", 1590, 340, 44, INK, f="hand")
        p.text("date: June 4", 1590, 410, 44, INK, f="hand")
    sc.label("codebreakers", 520, 160, 66, NAVY, at=sc.w("codebreakers"))


@S
def s48(sc):
    hz = seascape(sc, (214, 236, 250), SEA, 560)
    for i, x in enumerate((420, 960, 1500)):
        with sc.layer("pop", 0.02 + i * 0.03) as p:
            p.carrier(x, 760, 1.0)
            for k in range(3):
                p.plane(x - 90 + k * 70, 735, 0.18, 0, (200, 205, 215))
    with sc.layer("pop", sc.w("fuel")) as p:
        for x in (420, 960, 1500):
            p.barrel(x + 110, 720, 0.25)
            p.bomb(x - 120, 732, 0.6)
    for i, x in enumerate((500, 1000, 1500)):
        with sc.layer("pop", 0.15 + i * 0.05, move=(-60, 330, 0.25, 0.95)) as p:
            p.plane(x, 150, 0.6, 55, (215, 218, 226))
    sc.label("June 4, 1942", 960, 110, 70, INK, at=0.0)


@S
def s49(sc):
    seascape(sc, (226, 232, 238), SEA, 560)
    xs = (300, 760, 1220, 1660)
    for x in xs:
        with sc.layer("pop", 0.0, sfx=None) as p:
            p.carrier(x, 760, 0.95)
    for i, x in enumerate(xs[:3]):
        with sc.layer("pop", 0.08 + i * 0.07, sfx="boom") as p:
            p.flame(x - 40, 740, 1.3)
            p.smoke(x - 60, 660, 1.1)
    with sc.layer("pop", sc.w("fourth"), sfx="boom") as p:
        p.flame(xs[3] - 40, 740, 1.3)
        p.smoke(xs[3] - 60, 660, 1.1)
    with sc.layer("pop", 0.05) as p:
        clock(p, 960, 280, 120, 0.08)
        p.text("5 min", 960, 450, 50, INK, f="hand")
    sc.label("6 months after Pearl Harbor", 960, 1000 - 900, 54, RED, at=sc.w("six months"))


@S
def s50(sc):
    paper(sc)
    with sc.layer("pop", 0.0, z=0) as p:
        p.line([(960, 120), (960, 900)], 6, (180, 170, 150), 0.5)
    with sc.layer("pop", sc.w("Japan builds")) as p:
        p.rect(140, 560, 640, 30, BROWN, 5)
        p.ship(460, 520, 1.0, GRAY)
        p.text("one at a time", 460, 260, 56, INK, f="hand")
    sc.char(200, 900, 0.7, "japan", at=sc.w("Japan builds"), arms=((20, 15), (60, 40)), mouth="flat", eyes="dot", extra=("sweat",))
    with sc.layer("pop", sc.w("assembly")) as p:
        p.factory(1450, 470, 0.7)
        p.text("assembly line", 1450, 160, 56, NAVY, f="hand")
        p.rect(1000, 620, 880, 26, (90, 90, 100), 5)
    with sc.layer("pop", sc.w("assembly"), move=(-200, 0, sc.w("assembly"), 1.0), idle=None) as p:
        for i in range(6):
            p.ship(1100 + i * 170, 600, 0.35, GRAY)
    sc.char(1750, 900, 0.7, "america", at=sc.w("America builds"), arms=CHEER, mouth="grin", eyes="happy", flip=True)


@S
def s51(sc):
    paper(sc)
    sc.label("JAPAN", 300, 200, 60, RED, at=0.0)
    sc.label("USA", 1200, 200, 60, NAVY, at=sc.w("America"))
    with sc.layer("pop", sc.w("dozen")) as p:
        bars(p, 160, 520, 12, 4, mini_carrier, 95, 1.2)
        p.text("~12", 300, 640, 70, INK)
    with sc.layer("wipe_u", sc.w("over a hundred"), edur=1.2) as p:
        bars(p, 760, 900, 110, 11, mini_carrier, 92, 1.1)
    sc.label("100+", 1400, 120, 80, NAVY, at=sc.w("hundred") + 0.1, idle="pulse")
    sc.label("(counting the small ones)", 300, 820, 40, INK, f="hand", at=sc.w("counting"))


@S
def s52(sc):
    sc.map_bg(VSOL, base_terr=[(terr.S1942, RED)], labels=[("SOLOMON ISLANDS", 160, -12.5, 40), ("NEW GUINEA", 144.5, -6.5, 44)])
    sc.city("Guadalcanal", 160.0, -9.6, at=0.02, size=44)
    sc.arrow([sc.ll(166, -2), sc.ll(160.6, -8.8)], col=NAVY, at=0.05, curve=40)
    sc.arrow([sc.ll(152, -1), sc.ll(159.4, -8.8)], col=RED, at=0.1, curve=-40)
    with sc.layer("pop", sc.w("Starvation")) as p:
        p.stick(330, 760, 0.6, "army", arms=((60, 60), (20, 15)), mouth="wavy", eyes="sad", prop="bowl")
        p.text("\"Starvation Island\"", 360, 330, 50, INK, stroke=7, f="hand")
    sc.label("1942-43", 960, 110, 70, INK, at=0.0)
    with sc.layer("pop", sc.w("pulls out")) as p:
        x, y = sc.ll(160, -9.6)
        xmark(p, x, y, 50, 14)


# ------------------------------------------------------------------ 53-58 squeeze
@S
def s53(sc):
    sc.map_bg(VPAC, base_terr=[(terr.S1943, RED)])
    path = [(160.0, -9.5), (173.0, 1.4), (171.4, 7.1), (145.7, 15.2), (141.3, 24.8)]
    skipped = [(152.2, -4.2), (151.8, 7.4), (134.5, 7.5)]
    for lon, lat in skipped:
        with sc.layer("pop", sc.w("skips")) as p:
            x, y = sc.ll(lon, lat)
            p.text("skip", x, y - 40, 36, INK, stroke=6, f="hand")
            p.circ(x, y, 16, None, 5, col=INK)
    pts = [sc.ll(*q) for q in path]
    for i in range(len(pts) - 1):
        sc.arrow([pts[i], pts[i + 1]], col=NAVY, w=10, at=0.15 + i * 0.15, edur=0.5, curve=-40)
    sc.char(pts[1][0], pts[1][1], 0.4, "america", at=0.05, arms=CHEER, mouth="grin", eyes="happy")
    sc.label("ISLAND HOPPING", 960, 110, 80, NAVY, at=0.0)


@S
def s54(sc):
    seascape(sc, (214, 230, 246), (90, 140, 190), 420)
    for i, x in enumerate((350, 900, 1450)):
        with sc.layer("pop", 0.0) as p:
            p.tank_ship(x, 380, 0.9)
        with sc.layer("pop", 0.15 + i * 0.12, idle="float") as p:
            p.periscope(x - 160, 520 + i * 40, 1.0)
            p.ell(x - 260, 540 + i * 40, 120, 26, (60, 70, 80), 5)
        sc.arrow([(x - 140, 540 + i * 40), (x - 30, 440)], col=WHITE, w=6, at=0.2 + i * 0.12, edur=0.4)
        with sc.layer("pop", 0.3 + i * 0.12, sfx="boom") as p:
            boom(p, x - 10, 400, 70)
    sc.label("more than half the merchant fleet: sunk", 960, 110, 52, INK, at=sc.w("more than half"))


@S
def s55(sc):
    sc.map_bg(VW, base_terr=[(terr.S1943, RED)])
    for lon, lat in ((101.5, -1), (114.5, 0.5), (117, -2.5)):
        with sc.layer("pop", sc.w("oil fields")) as p:
            x, y = sc.ll(lon, lat)
            p.barrel(x, y, 0.5)
    t0 = sc.ll(110, 5)
    with sc.layer("pop", sc.w("tankers"), move=(150, -170, sc.w("tankers"), 0.75)) as p:
        p.tank_ship(t0[0], t0[1], 0.45)
    with sc.layer("pop", sc.w("can't get home")) as p:
        x, y = sc.ll(122, 22)
        boom(p, x, y, 60)
        p.text("BLUB", x, y + 80, 40, INK, f="hand")
    with sc.layer("drop", 0.02, idle="float") as p:
        note(p, 1560, 240, "REMEMBER:\nno oil!", 46, 320, 190)
    sc.char(*sc.ll(141, 29), 0.45, "japan", at=sc.w("never arrives"), arms=SHRUG, mouth="frown", eyes="sad", prop="can")


@S
def s56(sc):
    sc.map_bg(VW, base_terr=[(terr.S1944, RED)])
    sc.city("Saipan", 145.7, 15.2, at=0.05, size=44, col=NAVY)
    x0, y0 = sc.ll(145.7, 15.2)
    tx, ty = sc.ll(138, 36)
    r = math.hypot(tx - x0, ty - y0) + 40
    with sc.layer("grow", sc.w("close enough"), edur=0.9) as p:
        p.circ(x0, y0, r, None, 6, col=NAVY)
    sc.arrow([(x0, y0), (tx, ty)], col=NAVY, at=sc.w("B-29"), curve=40)
    with sc.layer("pop", sc.w("B-29")) as p:
        p.plane(x0 + 120, y0 - 160, 0.6, -60, (210, 214, 222))
        p.text("B-29", x0 + 230, y0 - 240, 46, NAVY, stroke=6)
    with sc.layer("pop", sc.w("resigns")) as p:
        sign(p, 1600, 760, 380, 150, "PM Tojo:\nresigned", 46)
    sc.label("June 1944", 960, 110, 70, INK, at=0.0)


@S
def s57(sc):
    seascape(sc, (226, 234, 242), (100, 150, 196), 300)
    r = random.Random(57)
    for i in range(30):
        x, y = 120 + (i % 10) * 180 + r.randint(-30, 30), 420 + (i // 10) * 170 + r.randint(-20, 20)
        with sc.layer("pop", 0.02 + (i % 10) * 0.015, sfx=None if i % 4 else "auto") as p:
            p.ship(x, y, 0.32, GRAY if i < 15 else (140, 140, 150))
    for i in range(4):
        with sc.layer("pop", sc.w("loses") + i * 0.03, sfx="boom") as p:
            p.flame(300 + i * 400, 640, 0.6)
    sc.label("Leyte Gulf, Oct 1944", 960, 110, 70, INK, at=0.0)
    sc.label("biggest naval battle ever?", 960, 210, 54, RED, f="hand", at=sc.w("biggest"))


@S
def s58(sc):
    paper(sc, (206, 204, 202))
    with sc.layer("fade", 0.0, edur=0.8) as p:
        table(p, 960, 720, 900, (130, 100, 75))
        p.rect(1180, 620, 200, 100, WHITE, 5)
        p.circ(1280, 670, 26, RED, 0)
        p.rect(600, 640, 160, 80, (250, 248, 240), 5)
    sc.char(430, 900, 0.95, "student", at=sc.w("students"), arms=AD, mouth="flat", eyes="sad", enter="fade", idle=None)
    sc.label("kamikaze", 960, 160, 70, INK, enter="fade", at=sc.w("kamikaze"))
    sc.label("many were students", 960, 260, 52, (90, 90, 100), f="hand", enter="fade", at=sc.w("students"))


# ------------------------------------------------------------------ 59-67 1945
@S
def s59(sc):
    with sc.background((32, 26, 44)) as p:
        p.d.rectangle([0, 860 * SS, W * SS, H * SS], fill=(40, 30, 30))
    with sc.layer("fade", 0.0, edur=0.8, sfx=None) as p:
        p.city(120, 880, 18, False, 0.95)
    with sc.layer("fade", sc.w("firebombs"), edur=1.5, sfx=None) as p:
        p.city(120, 880, 18, True, 0.95)
    for i in range(3):
        with sc.layer("fade", 0.05 + i * 0.05, idle="drift", sfx=None) as p:
            p.plane(300 + i * 500, 140 + (i % 2) * 70, 0.55, 4, (120, 120, 135))
    sc.label("Tokyo, March 9-10, 1945", 960, 330, 60, (255, 230, 200), scol=(30, 20, 30), enter="fade", at=0.05)
    sc.label("~100,000 dead in one night", 960, 420, 52, (255, 200, 170), scol=(30, 20, 30), f="hand", enter="fade", at=sc.w("hundred thousand"))


@S
def s60(sc):
    with sc.background((150, 150, 158)) as p:
        p.d.rectangle([0, 700 * SS, W * SS, H * SS], fill=(110, 140, 170))
        p.blob(960, 690, 820, 120, (120, 110, 100), 7, INK, 18, 0.12, 6)
        p.poly([(200, 680), (360, 520), (520, 680)], (100, 92, 84), 7)
    with sc.layer("wipe_r", sc.w("tunnels"), edur=1.4, sfx=None) as p:
        p.line([(450, 740), (800, 760), (1100, 730), (1500, 760)], 22, (60, 52, 46), 0.8)
        p.line([(800, 760), (820, 840)], 18, (60, 52, 46), 0.8)
        p.line([(1100, 730), (1150, 820)], 18, (60, 52, 46), 0.8)
    sc.label("Iwo Jima, Feb 1945", 960, 140, 66, INK, enter="fade", at=0.0)
    sc.label("~20,000 defenders. Almost none survived.", 960, 240, 50, (110, 30, 30), f="hand", enter="fade", at=sc.w("Almost all"))


@S
def s61(sc):
    v = View(127.9, 26.5, 3.0)
    sc.map_bg(v, base_terr=[], sea=(130, 160, 185), land=(180, 175, 165))
    sc.label("Okinawa, April-June 1945", 960, 130, 64, INK, enter="fade", at=0.0)
    sc.label("~100,000 civilians died", 960, 800, 58, (110, 30, 30), enter="fade", at=sc.w("civilians"))
    sc.camera(1.0, 1.04)


@S
def s62(sc):
    seascape(sc, (214, 210, 206), (120, 150, 175), 640)
    with sc.layer("pop", 0.0) as p:
        p.island(960, 720, 2.0, (150, 160, 120))
        p.ship(1550, 800, 0.6, (120, 120, 130), sunk=1)
    sc.char(960, 700, 0.8, "japan", at=0.05, arms=SHRUG, mouth="frown", eyes="sad", prop="can")
    with sc.layer("pop", sc.w("Germany")) as p:
        p.stick(330, 900, 0.7, "germany", arms=((20, 15), (150, 20)), mouth="frown", eyes="closed", prop="whiteflag")
    sc.label("surrendered", 330, 300, 46, INK, f="hand", at=sc.w("Germany"))
    sc.label("alone", 960, 200, 70, INK, f="hand", at=sc.w("alone"))
    sc.label("still won't give up", 1450, 300, 54, RED, f="hand", at=sc.w("won't"))


@S
def s63(sc):
    paper(sc, (226, 222, 214))
    with sc.layer("pop", 0.0) as p:
        table(p, 760, 700, 880)
        p.rect(520, 560, 480, 140, (190, 210, 170), 5)
        p.text("one last battle", 760, 630, 44, INK, f="hand")
    for i, x in enumerate((420, 1100)):
        sc.char(x, 900, 0.75, "army", at=0.03 + i * 0.04, arms=((95, -5), (20, 15)) if i else ((20, 15), (95, -5)), mouth="open", eyes="angry", flip=bool(i))
    with sc.layer("pop", 0.0) as p:
        door(p, 1600, 900, 240, 440)
    with sc.layer("pop", sc.w("Soviet")) as p:
        p.stick(1600, 900, 0.85, "ussr", arms=CROSS, mouth="smirk", eyes="dot", look=-1)
    sc.label("pls help?", 1350, 300, 52, INK, f="hand", at=sc.w("broker"))


@S
def s64(sc):
    paper(sc)
    with sc.layer("slide_l", 0.02) as p:
        p.rect(300, 220, 600, 520, WHITE, 7)
        p.text("Potsdam Declaration", 600, 290, 44, INK)
        p.text("surrender", 600, 420, 66, RED, f="hand")
        p.text("or else.", 600, 520, 66, RED, f="hand")
    sc.char(1350, 900, 1.0, "tophat_gray", at=0.1, arms=((20, 15), (40, -150)), mouth="o", eyes="closed")
    with sc.layer("pop", sc.w("ignores")) as p:
        p.text("~ whistling ~", 1520, 320, 50, INK, f="hand")
    sc.label("July 1945", 960, 110, 70, INK, at=0.0)


@S
def s65(sc):
    with sc.background((236, 230, 220)) as p:
        p.d.rectangle([0, 820 * SS, W * SS, H * SS], fill=(170, 160, 150))
        p.city(150, 840, 16, False, 0.9)
    with sc.layer("wipe_u", sc.w("atomic"), edur=2.2, sfx="boom") as p:
        p.mushroom(960, 840, 2.2)
    sc.label("Hiroshima, August 6, 1945", 960, 110, 64, INK, enter="fade", at=0.0)


@S
def s66(sc):
    sc.map_bg(VM, base_terr=[(terr.S1945, RED)], labels=[("USSR", 128, 48.3, 56)])
    for (a, b) in (((116, 51), (121, 45)), ((127, 52), (126, 46)), ((136, 47), (130, 44))):
        sc.arrow([sc.ll(*a), sc.ll(*b)], col=(170, 30, 30), w=18, at=sc.w("smashes"), edur=0.6)
    sc.char(*sc.ll(119.5, 47.6), 0.45, "ussr", at=sc.w("Soviet"), arms=((150, 20), (20, 15)), mouth="grin", eyes="angry")
    sc.label("August 8", 960, 110, 70, INK, at=0.0)
    sc.label("so much for that deal", 1400, 800, 54, RED, f="hand", at=sc.w("so much"))


@S
def s67(sc):
    with sc.background((226, 224, 220)) as p:
        p.d.rectangle([0, 820 * SS, W * SS, H * SS], fill=(160, 155, 150))
        p.city(160, 840, 16, False, 0.85)
    with sc.layer("wipe_u", 0.12, edur=2.0, sfx="boom") as p:
        p.mushroom(960, 840, 2.0)
    sc.label("Nagasaki, August 9, 1945", 960, 110, 64, INK, enter="fade", at=0.0)


@S
def s68(sc):
    paper(sc, (232, 228, 220))
    for i in range(6):
        x = 200 + i * 230 + (120 if i >= 3 else 0)
        k = "army" if i >= 3 else "tophat_gray"
        sc.char(x, 600, 0.55, k, at=0.03 + i * 0.03, arms=((20, 15), (95, -5)) if i >= 3 else ((95, -5), (20, 15)),
                mouth="open" if i >= 3 else "flat", eyes="angry" if i >= 3 else "dot")
    sc.label("SURRENDER", 430, 200, 54, (60, 140, 70), at=0.05)
    sc.label("FIGHT ON", 1460, 200, 54, RED, at=0.08)
    sc.label("3  vs  3", 960, 330, 70, INK, at=sc.w("three against"))
    with sc.layer("pop", sc.w("Emperor")) as p:
        screen(p, 960, 960, 480, 300)
        bubble(p, 960, 580, 480, 120, "we will surrender.", 44, tail=(0, 60), f="hand")


@S
def s69(sc):
    with sc.background((40, 44, 60)) as p:
        palace(p, 960, 860, 1.4)
        r = random.Random(9)
        for i in range(60):
            p.circ(r.randint(0, W), r.randint(0, 380), 3, (240, 240, 210), 0)
    for i in range(3):
        sc.char(300 + i * 160, 960, 0.6, "army", at=0.03 + i * 0.03, arms=((20, 15), (60, 40)), mouth="open", eyes="angry",
                legs=WALK, move=(120, 0, 0.05, 0.6))
    with sc.layer("pop", sc.w("can't find")) as p:
        p.text("???", 600, 520, 80, YELLOW, stroke=6, scol=INK)
    with sc.layer("pop", 0.1) as p:
        p.rect(1450, 640, 200, 180, (90, 90, 100), 6, r=10)
        p.circ(1550, 730, 40, (30, 30, 36), 5)
        p.circ(1550, 730, 12, RED, 0)
    sc.label("coup: FAILED", 960, 120, 70, RED, at=sc.w("fails"))


@S
def s70(sc):
    ground(sc, (250, 232, 200), (200, 180, 140))
    with sc.layer("pop", 0.0) as p:
        table(p, 960, 700, 300)
        p.radio(960, 640, 1.4)
    for i, x in enumerate((300, 480, 1440, 1620)):
        sc.char(x, 880, 0.7, "civ", at=0.05 + i * 0.03, arms=AD, mouth="o", eyes="wide", look=1 if x < 960 else -1, flip=x > 960)
    with sc.layer("pop", sc.w("court language")) as p:
        bubble(p, 960, 280, 680, 150, "...whereas... henceforth...\nthe unendurable...", 40, tail=(0, 80), f="hand")
    sc.label("???", 390, 520, 70, INK, at=sc.w("barely"))
    sc.label("???", 1530, 520, 70, INK, at=sc.w("barely"))
    sc.label("August 15, 1945", 960, 80, 56, INK, at=0.0)


@S
def s71(sc):
    with sc.background((210, 200, 190)) as p:
        p.city(140, 900, 16, False, 1.0)
        for i in range(8):
            p.smoke(200 + i * 220, 760, 0.8, (120, 115, 110))
    with sc.layer("pop", 0.05) as p:
        p.rect(310, 230, 1300, 300, WHITE, 8, r=24)
        p.text("\"...developed not necessarily", 960, 330, 64, INK, f="hand")
        p.text("to Japan's advantage\"", 960, 420, 64, INK, f="hand")
    sc.label("understatement of the century", 960, 640, 62, RED, at=sc.w("understatement"), idle="pulse")


@S
def s72(sc):
    seascape(sc, (214, 220, 228), (120, 150, 180), 560)
    with sc.layer("fade", 0.0, edur=0.8) as p:
        p.ship(960, 720, 2.6, (120, 126, 136))
    with sc.layer("fade", sc.w("signs"), edur=0.8) as p:
        table(p, 960, 560, 300)
        p.doc(900, 470, 120, 90, 3)
    sc.label("USS Missouri, September 2, 1945", 960, 120, 58, INK, enter="fade", at=0.0)
    sc.label("the war is over", 960, 230, 56, INK, f="hand", enter="fade", at=sc.w("over"))


@S
def s73(sc):
    paper(sc, (60, 62, 76))
    for i in range(40):
        with sc.layer("fade", 0.05 + (i % 10) * 0.04, edur=0.8, sfx=None) as p:
            p.candle(200 + (i % 10) * 170, 600 + (i // 10) * 100, 0.9)
    sc.label("~3 million Japanese", 960, 150, 62, (235, 235, 245), scol=(20, 20, 30), enter="fade", at=0.0)
    sc.label("many millions more across Asia", 960, 250, 56, (235, 235, 245), scol=(20, 20, 30), f="hand", enter="fade",
             at=sc.w("many millions"))


# ------------------------------------------------------------------ 74-79 payoff
@S
def s74(sc):
    paper(sc)
    with sc.layer("pop", sc.w("constitution")) as p:
        p.scroll(420, 520, 1.6)
        p.text("NEW", 420, 470, 48, RED)
        p.text("constitution", 420, 540, 40, INK, f="hand")
    with sc.layer("pop", sc.w("vote")) as p:
        ballot(p, 960, 720, 1.3)
    sc.char(1180, 900, 0.75, "civ", at=sc.w("women"), arms=CHEER, mouth="grin", eyes="happy")
    with sc.layer("pop", sc.w("symbol")) as p:
        p.circ(1550, 520, 110, (240, 200, 80), 7)
        for i in range(16):
            a = 2 * math.pi * i / 16
            p.circ(1550 + math.cos(a) * 80, 520 + math.sin(a) * 80, 28, (250, 215, 100), 4)
        p.circ(1550, 520, 40, (230, 180, 60), 5)
        p.text("just a symbol", 1550, 720, 46, INK, f="hand")
    sc.label("the occupation", 960, 120, 66, INK, at=0.0)


@S
def s75(sc):
    paper(sc, (236, 244, 236))
    with sc.layer("pop", 0.0) as p:
        table(p, 960, 680, 760)
        p.scroll(1200, 620, 1.2)
        p.text("Article 9", 1200, 600, 44, INK)
        p.text("no more war", 1200, 650, 34, INK, f="hand")
    with sc.layer("pop", sc.w("gives up")) as p:
        p.sword(760, 660, 1.2, 82)
    sc.char(420, 900, 1.0, "japan", at=0.05, arms=((60, 40), (20, 15)), mouth="smile", eyes="happy")
    with sc.layer("slide_r", sc.w("still there"), idle="float") as p:
        dove(p, 1500, 280, 1.3)
    sc.label("still there today", 960, 140, 56, (60, 140, 70), f="hand", at=sc.w("still there"))


@S
def s76(sc):
    ground(sc, (200, 230, 250), (180, 200, 160))
    with sc.layer("pop", sc.w("Cars")) as p:
        car(p, 300, 860, 1.1)
    with sc.layer("pop", sc.w("electronics")) as p:
        tv(p, 640, 860, 1.1)
    with sc.layer("slide_r", sc.w("bullet trains")) as p:
        p.train(1150, 760, 1.1)
    with sc.layer("wipe_r", sc.w("1968"), edur=1.0) as p:
        chart(p, 1350, 560, 460, 380, [(0, 0.05), (0.3, 0.2), (0.6, 0.5), (1, 0.95)], (60, 170, 80))
    sc.label("#2 economy on Earth", 1580, 120, 58, (60, 140, 70), at=sc.w("second"))
    sc.char(960, 600, 0.6, "japan", at=0.0, arms=CHEER, mouth="grin", eyes="happy")


@S
def s77(sc):
    paper(sc)
    with sc.layer("pop", 0.0) as p:
        p.rect(560, 560, 800, 60, BROWN, 6, r=8)
        p.rect(580, 620, 760, 280, (190, 150, 100), 6)
        p.text("SHOP", 960, 220, 70, INK)
    with sc.layer("pop", sc.w("oil")) as p:
        p.barrel(800, 500, 0.6)
    with sc.layer("pop", sc.w("rubber")) as p:
        p.circ(960, 510, 52, (50, 50, 56), 7)
        p.circ(960, 510, 20, PAPER, 5)
    with sc.layer("pop", sc.w("iron")) as p:
        p.poly([(1060, 550), (1180, 550), (1160, 490), (1080, 490)], (150, 150, 165), 6)
    sc.char(330, 900, 0.95, "japan", at=0.02, arms=((20, 15), (90, 10)), mouth="smile", eyes="dot")
    sc.char(1600, 900, 0.95, "america", at=0.05, arms=((90, 10), (20, 15)), mouth="grin", eyes="happy", flip=True)
    with sc.layer("pop", sc.w("buying")) as p:
        p.text("$", 520, 560, 80, (60, 140, 70), stroke=6)
    sc.label("...always an option", 960, 120 + 210, 56, RED, f="hand", at=sc.w("always"))


@S
def s78(sc):
    burst(sc)
    sc.char(560, 900, 0.85, "japan", at=0.0, arms=CHEER, mouth="grin", eyes="happy", exit_at=sc.w("then lost"))
    sc.char(560, 900, 0.85, "japan", at=sc.w("then lost"), arms=SHRUG, mouth="frown", eyes="sad", enter=None, extra=("tear",))
    sc.char(1400, 920, 1.2, "america", at=sc.w("America had"), arms=((150, 20), (150, 20)), mouth="grin", eyes="angry")
    with sc.layer("pop", sc.w("six months")) as p:
        p.rect(300, 180, 520, 110, (120, 200, 120), 6, r=20)
        p.text("6 months: winning", 560, 235, 44, INK)
    with sc.layer("pop", sc.w("then lost")) as p:
        p.rect(300, 310, 520, 110, (230, 110, 100), 6, r=20)
        p.text("then: everything lost", 560, 365, 42, WHITE)
    sc.label("plan: hope America quits", 1400, 130, 50, INK, f="hand", at=sc.w("plan needed"))
    sc.label("other ideas.", 1400, 215, 60, NAVY, at=sc.w("other ideas"))


@S
def s79(sc):
    burst(sc, (250, 244, 228), (255, 226, 160))
    with sc.layer("pop", sc.w("subscribe"), idle="pulse") as p:
        subscribe(p, 960, 300, 1.2)
    sc.char(600, 900, 0.95, "japan", at=0.0, arms=WAVE_R, mouth="grin", eyes="happy")
    sc.char(1320, 900, 1.1, "america", at=0.02, arms=((150, 25), (20, 15)), mouth="grin", eyes="happy", flip=True)
    with sc.layer("pop", sc.w("comments")) as p:
        bubble(p, 960, 560, 520, 130, "which war next?", 50, tail=(0, 70), f="hand")
    sc.label("see you next time!", 960, 130, 60, INK, f="hand", at=sc.w("See you"))


def geo_box(a, b, c, d):
    from shapely.geometry import box
    return box(a, b, c, d)
