"""Synthetic image evidence for Case C (MV SEREN TALON, Santa Rilla).

1. ais_track_screenshot.png   - fleet-tracking portal screenshot with port limits and NOR positions
2. sof_signed_scan.jpg        - scanned, signed SOF with handwritten remarks and stamps
3. deck_log_16jun2026.jpg     - handwritten deck log page for the disputed rain day
"""
import csv, json, math, os, random, subprocess
import numpy as np
import pdfplumber
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon, Ellipse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

PACK = "/home/claude/laytime_sample_pack"
CASE = f"{PACK}/case_C_seren_talon"
IMG = f"{CASE}/images"
os.makedirs(IMG, exist_ok=True)
SCR = "/tmp/claude-0/-home-claude/90efa065-9f0a-5089-bf76-a80c37196572/scratchpad"

HAND = "/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyrechorus-mediumitalic.otf"
SANS = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
SANSB = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

ports = json.load(open(f"{PACK}/shared/port_information.json"))["Santa Rilla"]
L0, G0 = ports["rilla_breakwater_light"]["lat"], ports["rilla_breakwater_light"]["lon"]
COSL = math.cos(math.radians(L0))


def to_xy(lat, lon):          # nm east / north of breakwater light
    return (lon - G0) * 60 * COSL, (lat - L0) * 60


def to_ll(x, y):
    return L0 + y / 60, G0 + x / 60 / COSL


def dm(v, ns):
    h = ("N" if v >= 0 else "S") if ns else ("E" if v >= 0 else "W")
    v = abs(v); d = int(v); m = (v - d) * 60
    return f"{d:02d}°{m:04.1f}'{h}" if ns else f"{d:03d}°{m:04.1f}'{h}"


def fmt_ll(lat, lon):
    return f"{dm(lat, True)} {dm(lon, False)}"


# ============================================================ 1. AIS TRACK
def ais_track():
    rng = random.Random(7)
    nor1 = to_xy(16 + 5.2 / 60, 60 + 51.3 / 60)
    nor2 = to_xy(16 + 8.6 / 60, 61 + 2.2 / 60)
    ax_, ay_ = to_xy(ports["anchorage_alpha"]["centre_lat"], ports["anchorage_alpha"]["centre_lon"])
    bx_, by_ = to_xy(ports["anchorage_bravo"]["centre_lat"], ports["anchorage_bravo"]["centre_lon"])
    berth = (0.55, 0.35)
    # (time, x, y, status)
    pts = [("09/06 18:00", -30.5, -9.8, "Under way"), ("09/06 19:30", -26.0, -8.4, "Under way"),
           ("09/06 21:00", -20.4, -6.7, "Under way"), ("09/06 22:00", -16.3, -5.5, "Under way"),
           ("09/06 22:50", nor1[0] - 0.4, nor1[1] - 0.1, "Drifting"), ("09/06 23:05", *nor1, "Drifting")]
    x, y = nor1
    for h in ["10/06 01:00", "10/06 03:00", "10/06 05:00", "10/06 07:00", "10/06 09:00", "10/06 11:00", "10/06 13:00"]:
        x += rng.uniform(-0.45, 0.35); y += rng.uniform(-0.3, 0.4)
        pts.append((h, x, y, "Drifting"))
    pts += [("10/06 14:10", x + 0.2, y + 0.1, "Under way"), ("10/06 15:00", -8.6, -3.1, "Under way"),
            ("10/06 15:45", -5.0, -2.1, "Under way"), ("10/06 16:20", nor2[0] + 0.05, nor2[1] - 0.05, "At anchor"),
            ("10/06 16:45", *nor2, "At anchor"), ("11/06 12:00", nor2[0] + 0.06, nor2[1] + 0.04, "At anchor"),
            ("12/06 05:30", nor2[0] + 0.03, nor2[1], "Under way"), ("12/06 06:40", -1.2, -0.7, "Under way"),
            ("12/06 08:12", *berth, "Moored")]

    fig = plt.figure(figsize=(13.66, 8.0), dpi=110)
    fig.patch.set_facecolor("#1f2a36")
    # header bar
    hd = fig.add_axes([0, 0.93, 1, 0.07]); hd.axis("off"); hd.set_facecolor("#1f2a36")
    hd.text(0.012, 0.5, "OceanTrack Fleet Monitor", color="white", fontsize=15, weight="bold", va="center")
    hd.text(0.245, 0.5, "|  Voyage replay  |  SYNTHETIC SAMPLE - fictional port and vessel",
            color="#9fb3c8", fontsize=10.5, va="center")
    hd.text(0.988, 0.5, "Exported 20/06/2026 09:14 LT (UTC+4)", color="#9fb3c8", fontsize=9.5, va="center", ha="right")
    # side panel
    sp = fig.add_axes([0, 0, 0.215, 0.93]); sp.axis("off")
    sp.add_patch(plt.Rectangle((0, 0), 1, 1, color="#f3f5f8", transform=sp.transAxes))
    lines = [("VESSEL", True), ("MV SEREN TALON", False), ("IMO 9834571 · Liberia", False), ("", False),
             ("REPLAY PERIOD", True), ("09/06/2026 18:00 –", False), ("12/06/2026 08:12 LT", False), ("", False),
             ("MARKED EVENTS", True), ("① NOR No. 1 tendered", False), ("   09/06 23:05 LT", False),
             ("   " + fmt_ll(*to_ll(*nor1)), False), ("   Status: Drifting, SOG 0.4 kn", False), ("", False),
             ("② NOR No. 2 tendered", False), ("   10/06 16:45 LT", False),
             ("   " + fmt_ll(*to_ll(*nor2)), False), ("   Status: At anchor", False), ("", False),
             ("③ All fast Berth 7", False), ("   12/06 08:12 LT", False), ("", False),
             ("LAYERS", True), ("■ Port limits (5 nm radius)", False), ("■ Designated anchorages", False),
             ("■ Outer roads waiting area", False)]
    yy = 0.965
    for s, b in lines:
        sp.text(0.07, yy, s, fontsize=8.8 if not b else 8.2, weight="bold" if b else "normal",
                color="#5b6b7c" if b else "#1d2733", transform=sp.transAxes, va="top", family="DejaVu Sans")
        yy -= 0.034
    # map
    ax = fig.add_axes([0.235, 0.07, 0.75, 0.84])
    ax.set_facecolor("#cfe3f2")
    land = Polygon([(1.2, -14), (1.6, -8), (0.9, -3), (1.3, -0.4), (1.0, 0.8), (1.5, 3), (1.1, 7), (1.8, 12),
                    (8, 12), (8, -14)], closed=True, fc="#efe9dc", ec="#b9ad93", lw=1.2, zorder=2)
    ax.add_patch(land)
    ax.plot([1.0, 0.2, -0.1], [0.8, 0.75, 0.45], color="#6b6250", lw=3, zorder=3)      # breakwater
    ax.plot(0, 0, marker="*", color="#d4a017", ms=13, mec="k", zorder=6)
    ax.annotate("Rilla breakwater light\n16°10.0'N 061°05.0'E", (0, 0), (2.0, 1.6), fontsize=8.5, zorder=7,
                arrowprops=dict(arrowstyle="-", color="#444"))
    ax.add_patch(Circle((0, 0), 5, fc="#b8d8ee", ec="#c0392b", lw=2, ls="--", zorder=1, alpha=0.9))
    ax.text(-3.2, 4.55, "PORT LIMITS (5 nm)", color="#c0392b", fontsize=9, weight="bold", rotation=33, zorder=5)
    for (cx, cy, nm) in [(ax_, ay_, "Anch. ALPHA"), (bx_, by_, "Anch. BRAVO")]:
        ax.add_patch(Circle((cx, cy), 1.0, fc="none", ec="#8e44ad", lw=1.4, zorder=4))
        ax.text(cx, cy + 1.15, nm, color="#6c3483", fontsize=8.3, ha="center", zorder=5)
    ax.add_patch(Ellipse((-13.3, -4.4), 6.5, 3.8, fc="#f5d58a", ec="#b7950b", alpha=0.45, lw=1.2, zorder=1))
    ax.text(-13.3, -6.75, "OUTER ROADS - waiting / drifting area\n(outside port limits)", ha="center",
            fontsize=8.5, color="#7d6608", zorder=5)
    xs = [p[1] for p in pts]; ys = [p[2] for p in pts]
    ax.plot(xs, ys, color="#1a5276", lw=1.6, zorder=5)
    cols = {"Under way": "#1a5276", "Drifting": "#e67e22", "At anchor": "#8e44ad", "Moored": "#27ae60"}
    for tm, px, py, stt in pts:
        ax.plot(px, py, "o", ms=4.5, color=cols[stt], mec="white", mew=0.6, zorder=6)
    for tm, px, py, stt in pts:
        if tm in ("09/06 18:00", "09/06 21:00", "10/06 15:00", "12/06 06:40"):
            ax.text(px, py + 0.55, tm, fontsize=7.2, ha="center", color="#1d2733", zorder=7)
    for lab, (px, py), txt, off in [("①", nor1, "NOR No. 1  09/06 23:05 LT\n" + fmt_ll(*to_ll(*nor1)), (-6.5, 3.2)),
                                   ("②", nor2, "NOR No. 2  10/06 16:45 LT\n" + fmt_ll(*to_ll(*nor2)), (-10.5, 5.3)),
                                   ("③", berth, "All fast Berth 7\n12/06 08:12 LT", (2.2, -3.6))]:
        ax.plot(px, py, "o", ms=12, mfc="none", mec="#c0392b", mew=2, zorder=8)
        ax.annotate(f"{lab} {txt}", (px, py), (px + off[0], py + off[1]), fontsize=8.6, zorder=9,
                    bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#c0392b", lw=1),
                    arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.2))
    for stt, c in cols.items():
        ax.plot([], [], "o", color=c, label=stt)
    ax.legend(loc="lower right", fontsize=8, framealpha=0.95, title="AIS nav status", title_fontsize=8)
    ax.set_xlim(-32, 7); ax.set_ylim(-13.5, 8)
    ax.set_aspect("equal")
    xt = np.arange(-30, 7, 5); yt = np.arange(-12, 8, 4)
    ax.set_xticks(xt); ax.set_xticklabels([dm(to_ll(v, 0)[1], False) for v in xt], fontsize=8)
    ax.set_yticks(yt); ax.set_yticklabels([dm(to_ll(0, v)[0], True) for v in yt], fontsize=8)
    ax.grid(color="white", lw=0.6, alpha=0.7)
    ax.plot([-30, -25], [-12.3, -12.3], color="k", lw=2.5); ax.text(-27.5, -11.9, "5 nm", ha="center", fontsize=8)
    for s in ax.spines.values():
        s.set_color("#8a99a8")
    fig.savefig(f"{IMG}/ais_track_screenshot.png", facecolor=fig.get_facecolor())
    plt.close(fig)
    return nor1, nor2


# ============================================================ handwriting helpers
def hand(draw, xy, text, size=34, ink=(22, 42, 140), rng=None, jitter=1.6, slant=0):
    rng = rng or random.Random(len(text))
    f = ImageFont.truetype(HAND, size)
    x, y = xy
    for ch in text:
        dy = rng.uniform(-jitter, jitter)
        a = rng.randint(200, 255)
        draw.text((x, y + dy), ch, font=f, fill=ink + (a,))
        x += draw.textlength(ch, font=f) * rng.uniform(0.96, 1.04)
    return x


def scribble(draw, x, y, w, ink=(22, 42, 140), seed=1):
    r = random.Random(seed)
    pts = []
    for i in range(34):
        t = i / 33
        pts.append((x + t * w + r.uniform(-6, 6), y + math.sin(t * 13 + r.random()) * r.uniform(8, 22)))
    draw.line(pts, fill=ink + (230,), width=3, joint="curve")
    draw.line([(x - 5, y + 18), (x + w * 0.9, y + 12)], fill=ink + (220,), width=2)


def round_stamp(size, text_outer, text_inner, color, seed=3):
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c = size / 2
    d.ellipse([4, 4, size - 4, size - 4], outline=color + (220,), width=5)
    d.ellipse([28, 28, size - 28, size - 28], outline=color + (220,), width=2)
    f = ImageFont.truetype(SANSB, int(size * 0.075))
    n = len(text_outer)
    for i, ch in enumerate(text_outer):
        ang = math.radians(-90 - 150 + 300 * i / max(n - 1, 1))
        r = c - 17
        chi = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
        ImageDraw.Draw(chi).text((20, 20), ch, font=f, fill=color + (230,), anchor="mm")
        chi = chi.rotate(-math.degrees(ang) - 90, resample=Image.BICUBIC)
        im.alpha_composite(chi, (int(c + r * math.cos(ang) - 20), int(c + r * math.sin(ang) - 20)))
    fi = ImageFont.truetype(SANSB, int(size * 0.09))
    for k, line in enumerate(text_inner):
        d.text((c, c + (k - (len(text_inner) - 1) / 2) * size * 0.11), line, font=fi, fill=color + (230,), anchor="mm")
    # uneven ink
    a = np.array(im); r = np.random.default_rng(seed)
    mask = r.random(a.shape[:2]) < 0.18
    a[..., 3][mask] = (a[..., 3][mask] * 0.35).astype(np.uint8)
    return Image.fromarray(a).rotate(random.Random(seed).uniform(-14, 14), resample=Image.BICUBIC, expand=True)


def rect_stamp(lines, color, seed=5):
    f = ImageFont.truetype(SANSB, 30)
    w = max(int(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(s, font=f)) for s in lines) + 40
    h = 44 * len(lines) + 24
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([3, 3, w - 3, h - 3], outline=color + (225,), width=4)
    for i, s in enumerate(lines):
        d.text((w / 2, 34 + i * 44), s, font=f, fill=color + (225,), anchor="mm")
    a = np.array(im); r = np.random.default_rng(seed)
    mask = r.random(a.shape[:2]) < 0.2
    a[..., 3][mask] = (a[..., 3][mask] * 0.3).astype(np.uint8)
    return Image.fromarray(a).rotate(random.Random(seed).uniform(-6, 6), resample=Image.BICUBIC, expand=True)


def scan_effect(im, angle, seed):
    r = np.random.default_rng(seed)
    im = im.convert("RGB").rotate(angle, resample=Image.BICUBIC, expand=True, fillcolor=(236, 234, 226))
    a = np.array(im).astype(np.float32)
    a = a * np.array([0.985, 0.975, 0.93]) + r.normal(0, 5.5, a.shape)
    h, w = a.shape[:2]
    shade = np.linspace(1.0, 0.94, w)[None, :, None]            # uneven scanner lighting
    a = np.clip(a * shade, 0, 255).astype(np.uint8)
    return Image.fromarray(a).filter(ImageFilter.GaussianBlur(0.55))


# ============================================================ 2. SCANNED SIGNED SOF
def sof_scan():
    src = f"{CASE}/statement_of_facts.pdf"
    DPI = 150; k = DPI / 72
    subprocess.run(["pdftoppm", "-r", str(DPI), "-png", "-singlefile", src, f"{SCR}/sof_raw"], check=True)
    page = Image.open(f"{SCR}/sof_raw.png").convert("RGBA")
    with pdfplumber.open(src) as p:
        words = p.pages[0].extract_words()
    lines = {}
    for w in words:
        lines.setdefault(round(w["top"]), []).append(w)

    def find(*tokens):
        for top, ws in sorted(lines.items()):
            txt = " ".join(x["text"] for x in sorted(ws, key=lambda z: z["x0"]))
            if all(tk in txt for tk in tokens):
                return ws
        raise KeyError(tokens)

    ov = Image.new("RGBA", page.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    blue = (22, 42, 140); black = (25, 25, 30)

    # (a) date correction 14/06 -> 15/06 on the rain-stop line
    ws = find("14/06/2026", "02:00", "Rain", "stopped")
    dw = [w for w in ws if w["text"] == "14/06/2026"][0]
    x0, x1, yc = dw["x0"] * k, dw["x0"] * k + 17 * k * 0.55, (dw["top"] + dw["bottom"]) / 2 * k
    d.line([(x0 - 2, yc + 2), (x0 + 20, yc - 3)], fill=blue + (240,), width=3)
    hand(d, (x0 - 4, yc - 42), "15", size=30, ink=blue)
    last = max(ws, key=lambda z: z["x1"])
    hand(d, (last["x1"] * k + 20, yc - 20), "date corr. 15/06 - D.O. / RPA", size=27, ink=blue, rng=random.Random(4))

    # (b) agent's note on NOR No. 1 line
    ws = find("NOR", "No.", "1", "tendered")
    last = max(ws, key=lambda z: z["x1"]); yc = (last["top"] + last["bottom"]) / 2 * k
    hand(d, (last["x1"] * k + 20, yc - 22), "vsl outside port limits - NOR 1 not accepted  (RPA/MS)",
         size=26, ink=blue, rng=random.Random(9))

    # (c) master's dispute on 16/06 rain line
    ws = find("16/06/2026", "10:30", "Rain")
    first = min(ws, key=lambda z: z["x0"]); last = max(ws, key=lambda z: z["x1"])
    yc = (first["top"] + first["bottom"]) / 2 * k
    d.ellipse([first["x0"] * k - 12, yc - 22, last["x1"] * k + 12, yc + 24], outline=black + (220,), width=3)
    hand(d, (last["x1"] * k + 24, yc - 20), "NO RAIN on board - disputed  D.O.", size=28, ink=black, rng=random.Random(11))

    # (d) signatures, protest note, stamps
    ws = find("Master:", "Okonjo")
    yb = max(w["bottom"] for w in ws) * k
    mx = min(w["x0"] for w in ws) * k
    ax_ = [w for w in ws if w["text"].startswith("For")][0]["x0"] * k
    scribble(d, mx + 205, yb - 18, 120, ink=black, seed=2)
    hand(d, (mx, yb + 16), "Signed under protest - see LOP 19/06", size=28, ink=black, rng=random.Random(13))
    scribble(d, ax_ + 250, yb - 16, 110, ink=blue, seed=6)
    page = Image.alpha_composite(page, ov)
    st1 = round_stamp(260, "RILLA PORT AGENCY S.A. * SANTA RILLA *", ["SHIPPING", "AGENTS"], (40, 60, 170), seed=21)
    page.alpha_composite(st1, (int(ax_ + 220), int(yb - 40)))
    st2 = rect_stamp(["MV SEREN TALON", "MASTER", "IMO 9834571"], (150, 30, 40), seed=22)
    page.alpha_composite(st2, (int(mx + 40), int(yb + 60)))
    st3 = rect_stamp(["RECEIVED", "19 JUN 2026 17:40"], (40, 110, 60), seed=23)
    page.alpha_composite(st3, (page.width - st3.width - 110, 90))
    scan_effect(page, 0.7, 31).save(f"{IMG}/sof_signed_scan.jpg", quality=80)


# ============================================================ 3. DECK LOG PAGE
def bft(kn):
    for lim, b in [(1, 0), (3, 1), (6, 2), (10, 3), (16, 4), (21, 5), (27, 6), (33, 7)]:
        if kn <= lim:
            return b
    return 8


def deck_log():
    wx = {}
    for r in csv.DictReader(open(f"{CASE}/port_weather_log.csv")):
        if r["timestamp_local"].startswith("2026-06-16"):
            wx[int(r["timestamp_local"][11:13])] = r
    W, H = 1700, 2560
    im = Image.new("RGBA", (W, H), (247, 244, 233, 255))
    d = ImageDraw.Draw(im)
    fb = ImageFont.truetype(SANSB, 34); fs = ImageFont.truetype(SANS, 22); fsb = ImageFont.truetype(SANSB, 21)
    d.text((W / 2, 70), "DECK LOG BOOK", font=fb, fill=(30, 30, 30), anchor="mm")
    d.text((W / 2, 112), "SYNTHETIC SAMPLE - fictional vessel - for AI agent testing only", font=fs,
           fill=(120, 120, 120), anchor="mm")
    hdr = [("Ship:", 90), ("Date:", 620), ("Port / position:", 1000)]
    for s, x in hdr:
        d.text((x, 160), s, font=fsb, fill=(30, 30, 30))
    rng = random.Random(42)
    hand(d, (170, 146), "MV SEREN TALON", size=34, rng=rng)
    hand(d, (690, 146), "Tue 16 June 2026", size=34, rng=rng)
    hand(d, (1190, 146), "Santa Rilla - Berth 7", size=34, rng=rng)
    d.text((90, 205), "Ship's time: UTC+4    Weather code (Beaufort letters): b blue sky · c cloudy · o overcast · "
                      "d drizzle · r rain · p passing showers", font=fs, fill=(60, 60, 60))
    cols = [("Hr", 90), ("Wind dir", 170), ("Force (Bft)", 300), ("Sea", 420), ("Weather", 565),
            ("Visib. (nm)", 680), ("Bar. hPa", 815), ("Air °C", 945), ("Remarks", 1040)]
    top, rh = 260, 72
    d.rectangle([80, top, W - 80, top + rh * 25], outline=(60, 60, 60), width=2)
    for i, (s, x) in enumerate(cols):
        d.text((x + 6, top + 22), s, font=fsb, fill=(30, 30, 30))
        if i:
            d.line([(x, top), (x, top + rh * 25)], fill=(90, 90, 90), width=1)
    for r in range(1, 25):
        d.line([(80, top + rh * r), (W - 80, top + rh * r)], fill=(150, 150, 150), width=1)
    remarks = {0: "At berth, disch. in progress", 4: "Watch handed over - all well",
               8: "Disch. cont'd, 3 gangs", 10: "10:30 Disch. STOPPED by receivers' order",
               11: "No rain / no precipitation - fine & clear", 12: "12:00 Disch. resumed",
               16: "Moorings tended", 20: "Disch. cont'd, all well", 23: "Draft fwd 8.9 aft 9.6 m"}
    bar = 1009.4
    for hr in range(24):
        y = top + rh * (hr + 1) + 18
        w = wx[hr]; kn = int(w["wind_kn"]); bar += rng.uniform(-0.4, 0.3)
        wcode = "bc" if 9 <= hr <= 16 else ("b" if hr < 9 else "c")
        vals = [f"{hr:02d}", w["wind_dir"], str(bft(kn)), "calm" if kn < 7 else "smooth" if kn < 15 else "slight",
                wcode, "10" if hr in range(9, 17) else "8", f"{bar:.1f}", str(29 + (3 if 10 <= hr <= 15 else 0))]
        ink = (22, 42, 140) if (hr // 4) % 2 == 0 else (25, 25, 30)
        for (s, x), v in zip(cols, vals):
            hand(d, (x + 12, y - 8), v, size=30, ink=ink, rng=rng)
        if hr in remarks:
            hand(d, (1052, y - 8), remarks[hr], size=28, ink=ink, rng=rng)
    fy = top + rh * 25 + 40
    d.text((90, fy), "Officer of the watch signatures:", font=fsb, fill=(30, 30, 30))
    for i, x in enumerate([500, 760, 1020, 1280]):
        scribble(d, x, fy + 20, 150, ink=(22, 42, 140) if i % 2 == 0 else (25, 25, 30), seed=60 + i)
    hand(d, (90, fy + 80), "Master's note: rain stoppage 10:30-12:00 in agent's SOF is disputed -", size=31,
         ink=(25, 25, 30), rng=rng)
    hand(d, (90, fy + 125), "no precipitation observed or logged. Stop was on receivers' order.", size=31,
         ink=(25, 25, 30), rng=rng)
    scribble(d, 1150, fy + 170, 170, ink=(25, 25, 30), seed=77)
    hand(d, (1140, fy + 205), "D. Okonjo, Master", size=28, ink=(25, 25, 30), rng=rng)
    st = rect_stamp(["MV SEREN TALON", "MASTER", "IMO 9834571"], (150, 30, 40), seed=81)
    im.alpha_composite(st, (820, fy + 150))
    scan_effect(im, -0.9, 44).convert("RGB").save(f"{IMG}/deck_log_16jun2026.jpg", quality=82)


# ============================================================ run + answer key
nor1, nor2 = ais_track()
sof_scan()
deck_log()


def dist(p):
    return math.hypot(*p)


ax_c = to_xy(ports["anchorage_alpha"]["centre_lat"], ports["anchorage_alpha"]["centre_lon"])
evidence = [
    {"file": "images/ais_track_screenshot.png",
     "agent_should_read": f"NOR No. 1 position {fmt_ll(*to_ll(*nor1))} at 09/06 23:05 LT, status Drifting; "
                          f"NOR No. 2 position {fmt_ll(*to_ll(*nor2))} at 10/06 16:45 LT, status At anchor.",
     "deterministic_check": f"Distance from Rilla breakwater light (port_information.json): NOR 1 = {dist(nor1):.1f} nm "
                            f"(> 5 nm port limits -> OUTSIDE); NOR 2 = {dist(nor2):.1f} nm (inside), "
                            f"{math.hypot(nor2[0]-ax_c[0], nor2[1]-ax_c[1]):.2f} nm from Anchorage Alpha centre (inside 1 nm radius).",
     "conclusion": "Confirms NOR No. 1 invalid under the recap; laytime runs from NOR No. 2 + 6 h = 10/06 22:45."},
    {"file": "images/sof_signed_scan.jpg",
     "agent_should_read": "Three handwritten additions not in the typed SOF: (1) '14' struck through and corrected to '15' "
                          "on the 02:00 rain-stopped line, initialled 'D.O. / RPA'; (2) agent's note 'vsl outside port limits - "
                          "NOR 1 not accepted'; (3) Master's circled 16/06 10:30 rain line with 'NO RAIN on board - disputed'. "
                          "Also 'Signed under protest - see LOP 19/06', agent's round stamp, Master's stamp, received stamp 19 Jun 2026 17:40.",
     "deterministic_check": "Compare scanned SOF against typed statement_of_facts.pdf line by line and list differences.",
     "conclusion": "Signed SOF itself corrects the rain-stop date to 15/06 (evidence for the typo fix) and shows the port agent "
                   "did not accept NOR No. 1. Signed SOF prevails over the unsigned typed copy."},
    {"file": "images/deck_log_16jun2026.jpg",
     "agent_should_read": "16 June 2026, hours 10-11: weather code 'bc' (no rain code r/d/p), visibility 10 nm; remarks "
                          "'10:30 Disch. STOPPED by receivers' order' and 'No rain / no precipitation'; Master's note disputing "
                          "the SOF rain stoppage.",
     "deterministic_check": "Wind directions in the deck log match port_weather_log.csv for 16 June; precip 0.0 mm at 10:00 and 11:00.",
     "conclusion": "Three independent sources (deck log, weather log, Master's SOF remark) agree there was no rain -> "
                   "10:30-12:00 on 16 June counts as laytime; it is not an excepted period."},
]
kp = f"{PACK}/answer_key/answer_key.json"
ak = json.load(open(kp))
ak["C"]["image_evidence"] = evidence
json.dump(ak, open(kp, "w"), indent=2)
print(json.dumps(evidence, indent=1, ensure_ascii=False))
