"""Compose the painted-surface textures from the Pompeii/Herculaneum sources.

Usage: python3 tools/compose_paintings.py
Reads assets/paintings/raw/, writes assets/paintings/textures/<object name>.png. The object names
match the "Painted_*" objects made by blender/build_pantheon.py; the Unreal build gives each such
object its own material with the texture of the same name (falling back to the name without its
trailing _suffix). Placement and colours follow reference/paintings_plan.md (sections 2-4).

Images are cropped and framed with ffmpeg only (no image library needed).
"""

import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW = os.path.join(ROOT, "assets", "paintings", "raw")
OUT = os.path.join(ROOT, "assets", "paintings", "textures")

RED, YELLOW, BLACK, GOLD, GREEN = "0x9B2A1F", "0xC8962E", "0x1C1A17", "0xD2A64A", "0x4E6B4A"

# aedicula azimuth x10 -> (left picture, right picture); reference/paintings_plan.md 3.3
TABULAE = {
    225: ("myth_achilles_chiron_herculaneum_basilica_MANN9109", "myth_apollo_with_kithara_praedia_iulia_felix_louvre"),
    675: ("myth_hercules_telephus_herculaneum_basilica_MANN9008", "myth_hercules_omphale_pompeii_VII_ins_occ_15_MANN9000"),
    1125: ("myth_bacchus_ariadne_naxos_pompeii_VII_4_51_MANN9278", "myth_medea_house_of_jason_MANN114321"),
    1575: ("myth_io_argus_mercury_temple_of_isis_MANN9548", "myth_perseus_andromeda_pompeii_VII_ins_occ_15_MANN8997"),
    2025: ("myth_wedding_zeus_hera_house_of_tragic_poet_MANN9559", "myth_vulcan_thetis_arms_of_achilles_pompeii_IX_1_7_MANN9529"),
    2475: ("myth_sacrifice_iphigenia_house_of_tragic_poet_MANN9112", "myth_venus_in_shell_pompeii_VII_6_7_MANN"),
    2925: ("myth_achilles_skyros_house_of_dioscuri_MANN9110", "myth_medea_house_of_jason_MANN114321"),
    3375: ("myth_theseus_minotaur_herculaneum_basilica_MANN9049", "myth_venus_in_shell_pompeii_VII_6_7_MANN"),
}
# exedra azimuth -> central picture; reference/paintings_plan.md 3.2
EXEDRAE = {
    0: "myth_mars_venus_house_of_mars_and_venus_MANN9248",
    45: "myth_apollo_daphne_stabiae_villa_arianna_MANN9535",
    135: "myth_diana_actaeon_herculaneum_MANN9413",
    180: "myth_mars_venus_house_of_lucretius_fronto_tablinum",
    225: "myth_perseus_andromeda_house_of_dioscuri_MANN8998",
    315: "myth_daedalus_icarus_fall_pompeii_MANN9506",
}


def src(name):
    return os.path.join(RAW, name + ".jpg")


def run(args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error"] + args, check=True)


def fit(w, h):
    """Scale to cover w x h and centre-crop."""
    return "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h)


def framed(picture, w, h, out, gold=26, line=6):
    """Picture filling the panel inside a gilded frame with a thin black line."""
    pw, ph = w - 2 * (gold + line), h - 2 * (gold + line)
    vf = (fit(pw, ph) + ",pad=%d:%d:%d:%d:color=%s" % (pw + 2 * line, ph + 2 * line, line, line, BLACK)
          + ",pad=%d:%d:%d:%d:color=%s" % (w, h, gold, gold, GOLD))
    run(["-i", src(picture), "-vf", vf, "-frames:v", "1", out])


def on_ground(picture, out, w, h, pw, ph, crop=None, gold=22):
    """A framed picture (pw x ph) centred on a red ground with a gold frame line near the edge."""
    pre = ("crop=%s," % crop) if crop else ""
    fc = ("color=c=%s:s=%dx%d[bg];" % (RED, w, h)
          + "[0:v]" + pre + fit(pw, ph) + ",pad=%d:%d:5:5:color=%s,pad=%d:%d:%d:%d:color=%s[pic];" % (
              pw + 10, ph + 10, BLACK, pw + 10 + 2 * gold, ph + 10 + 2 * gold, gold, gold, GOLD)
          + "[bg]drawbox=x=%d:y=%d:w=%d:h=%d:color=%s:t=%d[fr];" % (
              int(w * 0.05), int(h * 0.06), int(w * 0.9), int(h * 0.88), GOLD, max(4, w // 120))
          + "[fr][pic]overlay=(W-w)/2:(H-h)/2")
    run(["-i", src(picture), "-filter_complex", fc, "-frames:v", "1", "-update", "1", out])


def exedra_field(picture, out, w=2000, h=1500):
    """Fourth Style field: red ground, black outer band, yellow and green frame lines, central picture."""
    pw, ph = 1200, 900
    fc = ("color=c=%s:s=%dx%d[bg];" % (RED, w, h)
          + "[0:v]" + fit(pw, ph) + ",pad=%d:%d:6:6:color=%s,pad=%d:%d:26:26:color=%s[pic];" % (
              pw + 12, ph + 12, BLACK, pw + 64, ph + 64, GOLD)
          + "[bg]drawbox=x=0:y=0:w=%d:h=%d:color=%s:t=60," % (w, h, BLACK)
          + "drawbox=x=90:y=90:w=%d:h=%d:color=%s:t=10," % (w - 180, h - 180, YELLOW)
          + "drawbox=x=120:y=120:w=%d:h=%d:color=%s:t=4[fr];" % (w - 240, h - 240, GREEN)
          + "[fr][pic]overlay=(W-w)/2:(H-h)/2")
    run(["-i", src(picture), "-filter_complex", fc, "-frames:v", "1", "-update", "1", out])


def strip(picture, out, w, h, crop):
    run(["-i", src(picture), "-vf", "crop=%s,%s" % (crop, fit(w, h)), "-frames:v", "1", out])


def main():
    os.makedirs(OUT, exist_ok=True)
    o = lambda n: os.path.join(OUT, n + ".png")
    # tabulae beside the aediculae: 1.24 x 1.60 m including the frame
    for az, (left, right) in TABULAE.items():
        framed(left, 775, 1000, o("Painted_Tab_%04d_L" % az))
        framed(right, 775, 1000, o("Painted_Tab_%04d_R" % az))
    # exedra wall fields, 4.0 x 3.0 m
    for az, pic in EXEDRAE.items():
        exedra_field(pic, o("Painted_Field_%03d" % az))
    # aedicula niche backs: black Third Style ground with candelabra (Boscotrecase), 2.3 x 6.15 m
    strip("deco_third_style_black_room_villa_boscotrecase_met", o("Painted_NicheBack"), 600, 1600,
          "iw*0.34:ih:iw*0.33:0")
    # aedicula friezes: garland with masks, 4.1 x 0.22 m
    strip("deco_garland_border_masks_pompeii_VI_14_43_MANN9901", o("Painted_AedFrieze"), 3000, 160,
          "iw:ih*0.35:0:ih*0.3")
    # statue pedestal dies (0.9-1.9 m wide): red ground, gold line, lararium vignette
    on_ground("deco_lararium_lares_genius_serpents_altar_pompeii_MANN8905", o("Painted_Pedestals"),
              900, 1000, 520, 600)
    # altar of Jupiter (1.6 x 0.6 m front): Jupiter crowned by Victory on red; sides with the lararium serpent
    on_ground("myth_jupiter_crowned_by_nike_house_of_dioscuri_MANN9551", o("Painted_AltarFront"),
              1600, 600, 330, 440, gold=16)
    on_ground("deco_lararium_bacchus_vesuvius_serpent_house_of_centenary_MANN112286", o("Painted_AltarSides"),
              1000, 600, 480, 400, gold=14)
    print("textures:", len(os.listdir(OUT)))


if __name__ == "__main__":
    main()
