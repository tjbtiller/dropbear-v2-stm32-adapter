#!/usr/bin/env python3
"""Generate the board-outline + placement sketch PCB (NO routing) for the adapter.
Reads net maps from gen_kicad.py; placements derived from canonical shield coords.
"""
import os, sys, json, uuid, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_kicad import (T_SIGNAL, T_POWER, MEGA_GROUPS, M_NET, load_pads, fmt, U5, LINX_BT1_FP)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KICAD = os.path.join(ROOT, "kicad")

# board coords == shield coords (canonical Mega R3 shield positions)
# outline: rounded rect approx as plain rect
OUTLINE = [(-1.27, -54.61), (100.33, 1.27)]

# placements: (ref, footprint, x, y, rot)
PLACE = [
    ("J1", "TEENSY41_SOCKET", 55.0, -22.0, 0),
    # --- VBAT pickup (single-wire: J1 pad 50 -> TP1 -> wire to DCWerx VBAT pad; 2026-11-09 cleanup:
    # JP1 jumper + BT1 holder removed - the wire to the DCWerx is the disconnect point) ---
    ("VBAT", "TestPoint_THT_D2", 73.5, -42.0, 0),
]
BOTTOM_PARTS = {"VBAT"}

MOUNT_HOLES = [(13.97, -2.54), (66.04, -7.62), (15.24, -50.8),
               (96.52, -2.54), (66.04, -35.56), (90.17, -50.8)]
"""name -> <=3-char silk label (fits 2.54mm pin pitch at 0.8mm font)"""
SILK = {
    "TACHO": "TCH", "FUELPUMP": "PMP", "CS_FLASH": "FL", "ESP_TXD": "ETX", "ESP_RXD": "ERX",
    "CS_MC33810_1": "C1", "CS_MC33810_2": "C2", "SPI_MOSI": "MO", "SPI_MISO": "MI", "SPI_SCLK": "SK",
    "SPARE2_OUT": "SP2", "IDLE1": "I1", "VVT_A1": "VVT", "IDLE2_SP1": "I2",
    "STEP_EN": "EN", "STEP_STEP": "ST", "STEP_DIR": "DIR",
    "DI_VSS": "VSS", "DI_WMI": "WMI", "DI_LAUNCH": "LNC", "DI_FLEX": "FLX",
    "AI_BAT": "BAT", "AI_SP1": "P1", "AI_SP2": "P2",
    "BOOST": "BST", "CRANK": "CRK", "AI_IAT": "IAT", "AI_CLT": "CLT", "AI_O2": "O2", "AI_TPS": "TPS", "AI_BARO": "BAR", "AI_MAP": "MAP",
    "CAN_TX": "CTX", "CAN_RX": "CRX", "VBAT_RTC": "VR",
    "GND": "GND", "+5V": "5V", "+3V3": "3V3",
}
"""footprint attr string mirrored from the .kicad_mod library files (keeps lib_footprint_mismatch quiet)"""
LIBATTR = {fp: "through_hole exclude_from_pos_files exclude_from_bom"
           for fp in ["TEENSY41_SOCKET", "MEGA_DIG_A_1x10", "MEGA_DIG_B_1x8", "MEGA_DIG_C_1x8",
                      "MEGA_DIG_HI_2x18", "MEGA_AN_A_1x8", "MEGA_AN_B_1x8", "MEGA_PWR_1x7",
                      "MountingHole_3.2mm"]}
LIBATTR.update({"SOT-23_LDO": "smd", "C_0603_DNP": "smd",
                "SolderJumper-2_Bridged": "smd", "SolderJumper-2_Open": "smd"})

# net names per ref/pad
def net_of(ref, pad):
    if ref == "J1":
        p = int(pad)
        n = T_POWER.get(p) or T_SIGNAL.get(p)
        return n
    if ref in ("J2", "J3", "J4", "J5", "J6", "J7", "J8"):
        return M_NET.get(pad)
    return {
        ("JP1", "1"): "VBAT_DB", ("JP1", "2"): "VBAT_RTC",
        ("VBAT", "1"): "VBAT_RTC",
    }.get((ref, pad))

def padgeom(fpname):
    """(padname, x, y, w, h, drill, smd?, shape) local geometry per footprint"""
    if fpname == "TEENSY41_SOCKET":
        return [(p["n"], p["x"], p["y"], p["w"], p["h"], p["d"], False, p["sh"])
                for p in load_pads("teensy41_pads.json")]
    if fpname.startswith("MEGA_"):
        pads = load_pads("mega_r3_shield_pads.json")
        grp = next(g for g in MEGA_GROUPS if g[2] == fpname)
        def bare(n):
            return n[1:] if n.startswith("D") and n[1:].isdigit() else n
        sel = [p for p in pads if bare(p["n"]) in grp[3]]
        x0, y0 = min(p["x"] for p in sel), min(p["y"] for p in sel)
        return [(bare(p["n"]), p["x"] - x0, p["y"] - y0, 1.7, 1.7, 1.0, False, "oval") for p in sel]
    d = {
        "SOT-23_LDO": [("1", -1.1, -0.85, 1.0, 1.6, None, True, "rect"), ("2", 1.1, -0.85, 1.0, 1.6, None, True, "rect"), ("3", 0, 0.95, 1.0, 1.6, None, True, "rect")],
        "C_0603_DNP": [("1", -0.75, 0, 1.0, 1.0, None, True, "rect"), ("2", 0.75, 0, 1.0, 1.0, None, True, "rect")],
        "SolderJumper-2_Bridged": [("1", -0.65, 0, 1.0, 1.0, None, True, "rect"), ("2", 0.65, 0, 1.0, 1.0, None, True, "rect")],
        "SolderJumper-2_Open": [("1", -0.65, 0, 1.0, 1.0, None, True, "rect"), ("2", 0.65, 0, 1.0, 1.0, None, True, "rect")],
        "TestPoint_THT_D2": [("1", 0, 0, 2.0, 2.0, 1.0, False, "circle")],
    }
    return d[fpname]

def boxgeom(fpname):
    """silk/courtyard rects (footprint-local) matching the .kicad_mod library files exactly"""
    if fpname == "TEENSY41_SOCKET":
        # silk outline removed: J1's B-silk rect corner collided with pin-1 text and the
        # bottom near-strip labels; pads+labels are self-evident, keep courtyard only
        return [("F.CrtYd", -31, -10.4, 31, 10.4)]
    if fpname.startswith("MEGA_"):
        g = padgeom(fpname)
        m = 0.6
        w = max(p[1] for p in g); h = max(p[2] for p in g)
        return [("F.CrtYd", -m, -m, w + m, h + m)]
    sq = {"SOT-23_LDO": (2.1, 2.3), "C_0603_DNP": (1.4, 1.7),
          "SolderJumper-2_Bridged": (1.6, 1.8), "SolderJumper-2_Open": (1.6, 1.8),
          "TestPoint_THT_D2": (1.3, 1.5),
          "MountingHole_3.2mm": (1.8, 2.0)}[fpname]
    return [("F.SilkS", -sq[0], -sq[0], sq[0], sq[0]), ("F.CrtYd", -sq[1], -sq[1], sq[1], sq[1])]
def rot_xy(x, y, rot):
    r = rot % 360
    if r == 0: return x, y
    if r == 90: return y, -x
    if r == 180: return -x, -y
    if r == 270: return -y, x

def main():
    # mega group placements from canonical coords
    places = list(PLACE)
    for g in MEGA_GROUPS:
        ref, sym, value, pins = g
        pads = load_pads("mega_r3_shield_pads.json")
        m = {p["n"]: (p["x"], p["y"]) for p in pads}
        m.update({k[1:]: v for k, v in m.items() if k.startswith("D")})
        pts = [m[p] for p in pins]
        places.append((ref, value, min(x for x, _ in pts), min(y for _, y in pts), 0))

    # nets table
    nets = {}
    usertexts = {}
    def netidx(name):
        if name and name not in nets:
            nets[name] = len(nets) + 1
        return nets.get(name)

    out = []
    out.append('(kicad_pcb (version 20221018) (generator "dropbear-adapter-gen")')
    out.append('\t(general (thickness 1.6))')
    out.append('\t(paper "A4")')
    out.append('\t(layers')
    for num, (name, kind) in [(0, ("F.Cu", "signal")), (31, ("B.Cu", "signal")),
                              (34, ("B.Paste", "user")), (35, ("F.Paste", "user")),
                              (36, ("B.SilkS", "user")), (37, ("F.SilkS", "user")),
                              (38, ("B.Mask", "user")), (39, ("F.Mask", "user")),
                              (40, ("Dwgs.User", "user")), (41, ("Cmts.User", "user")),
                              (42, ("Eco1.User", "user")), (43, ("Eco2.User", "user")),
                              (44, ("Edge.Cuts", "user")), (45, ("Margin", "user"))]:
        out.append(f'\t\t({num} "{name}" {kind})')
    out.append('\t)')
    out.append('\t(setup (pad_to_mask_clearance 0))')
    out.append('\t(net 0 "")')

    # footprints
    fps = []
    for ref, fpname, x, y, rot in places:
        geom = padgeom(fpname)
        bottom = ref in BOTTOM_PARTS
        side = "B" if bottom else "F"
        slk, crt, cu, pst, msk = f"{side}.SilkS", f"{side}.CrtYd", f"{side}.Cu", f"{side}.Paste", f"{side}.Mask"
        i = next(idx for idx, (r, f, px, py, rr) in enumerate(places) if r == ref)
        reftext_y = -11.8 if ref == "J1" else -2.1
        j1_bottom = ref == "J1"
        if ref == "TP1":
            reftext_y = -2.1  # below the pad, clear of it
        elif fpname.startswith("MEGA_DIG") and fpname != "MEGA_DIG_HI_2x18":
            reftext_y = 6.4   # inboard of the label strip, x-shifted below
        elif fpname.startswith("MEGA_AN") or fpname == "MEGA_PWR_1x7":
            reftext_y = -6.4  # inboard of the label strip
        if ref == "VBAT":
            reftext_y = -2.2
            ref_lay = "B.SilkS"
            ref_mir = ' (justify mirror)'
            L_pre = [f'\t\t(fp_text user "VBAT" (at 0 {fmt(reftext_y)} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))']
        ref_lay = "B.SilkS" if ref == "J1" else slk
        ref_mir = ' (justify mirror)' if (ref == "J1" or bottom) else ''
        L_head = [f'\t(footprint "dropbear:{fpname}" (layer "{cu}") (tedit 0) (tstamp 0)',
             f'\t\t(at {fmt(x)} {fmt(y)} {rot})',
             f'\t\t(attr {LIBATTR.get(fpname, "through_hole")})',
             f'\t\t(fp_text reference "{ref}" (at {fmt(-4.6 if (fpname.startswith("MEGA_DIG") and fpname != "MEGA_DIG_HI_2x18") else (4.6 if fpname.startswith("MEGA_AN") or fpname == "MEGA_PWR_1x7" else 0))} {fmt(reftext_y)} 0) (layer "{ref_lay}") (effects (font (size 1 1) (thickness 0.15)){ref_mir}))',
             f'\t\t(fp_text value "{fpname}" (at 0 {fmt(2.1)} 0) (layer "{side}.Fab") (effects (font (size 1 1) (thickness 0.15))))']
        L_pre = [] if ref != "VBAT" else L_pre
        L = L_head + L_pre
        for (lay, bx1, by1, bx2, by2) in boxgeom(fpname):
            lay2 = ("B.SilkS" if ref == "J1" else slk) if lay.endswith("SilkS") else ("B.CrtYd" if ref == "J1" else crt)
            L.append(f'\t\t(fp_rect (start {fmt(bx1)} {fmt(by1)}) (end {fmt(bx2)} {fmt(by2)}) (stroke (width {"0.12" if lay.endswith("SilkS") else "0.05"}) (type solid)) (fill none) (layer "{lay2}"))')
        if fpname == "TEENSY41_SOCKET":
            L.append(f'\t\t(fp_text user "1" (at -30.6 7.62 0) (layer "B.SilkS") (effects (font (size 1 1) (thickness 0.15)) (justify mirror)))')
        for pn, px, py, w, h, d, smd, shape in geom:
            rx, ry = px, py  # children are footprint-local; the (at x y rot) line carries rotation
            net = net_of(ref, pn)
            netstr = f' (net {netidx(net)} "{net}")' if net else ''
            if smd:
                L.append(f'\t\t(pad "{pn}" smd rect (at {fmt(rx)} {fmt(ry)}) (size {fmt(w)} {fmt(h)}) (layers "{cu}" "{pst}" "{msk}"){netstr})')
            else:
                L.append(f'\t\t(pad "{pn}" thru_hole {shape} (at {fmt(rx)} {fmt(ry)}) (size {fmt(w)} {fmt(h)}) (drill {fmt(d)}) (layers "*.Cu" "*.Mask"){netstr})')
            # ---- per-pin silkscreen: compact names, placed to clear all pads and neighbors
            if fpname == "TEENSY41_SOCKET" and pn in ("66", "67"):
                continue  # D-/D+ sit 0.73mm from pads 1/2 - no room for labels (NC anyway)
            if fpname == "TEENSY41_SOCKET" or fpname.startswith("MEGA_"):
                lbl = SILK.get(net, net or pn if net else pn)
                w_est = 0.64 * len(lbl) + 0.05  # measured stroke-font advance at 0.8mm
                if pn in ("RST1", "IORF", "AREF"):
                    lbl = {"RST1": "RST", "IORF": "IO", "AREF": "ARF"}[pn]
                if fpname == "TEENSY41_SOCKET" and pn in ("49", "50", "51", "52", "53", "54"):
                    # true aux column pads: horizontal label to the right
                    L.append(f'\t\t(fp_text user "{lbl}" (at {fmt(rx + 3.6)} {fmt(ry)} 0) (layer "B.SilkS") (effects (font (size 0.8 0.8) (thickness 0.1)) (justify left mirror)))')
                elif fpname == "TEENSY41_SOCKET":
                    # main two rows: single outboard strip per row (labels are <=3 chars, fit 2.54 pitch)
                    ty = 9.2 if py > 0 else -9.2
                    L.append(f'\t\t(fp_text user "{lbl}" (at {fmt(rx - 1.1)} {fmt(ty)} 0) (layer "B.SilkS") (effects (font (size 0.8 0.8) (thickness 0.1)) (justify left mirror)))')
                elif fpname == "MEGA_DIG_HI_2x18":
                    # 2x18 header at 2.54 pitch has no room for per-pin silk (runs overlap);
                    # pin map lives on the schematic + RESEARCH.md — no labels here (documented)
                    pass
                else:
                    # single-row groups: one strip facing board interior (labels <=3 chars)
                    below = fpname.startswith("MEGA_DIG")
                    ty = 2.1 if below else -2.1
                    L.append(f'\t\t(fp_text user "{lbl}" (at {fmt(rx - 1.1)} {fmt(ry + ty)} 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.1)) (justify left)))')
        L.append('\t)')
        usertexts.setdefault(fpname, []).extend(
            ln.replace('\t\t', '\t') for ln in L if '(fp_text user "' in ln)
        fps.append("\n".join(L))

    # mounting holes footprints (no nets)
    # mount holes disabled 2026-11-09 — DCWerx has none; re-enable + redesign clearance around them if a future topside board needs mounting
    #     for k, (mx, my) in enumerate(MOUNT_HOLES):
    #         L = [f'\t(footprint "dropbear:MountingHole_3.2mm" (layer "F.Cu") (tedit 0) (tstamp 0)',
    #              f'\t\t(at {fmt(mx)} {fmt(my)})',
    #              '\t\t(attr through_hole exclude_from_pos_files exclude_from_bom)',
    #              f'\t\t(fp_text reference "H{k+1}" (at {0 if (mx >= 96 or abs(mx-90.17)<0.1) else (3.4 if abs(mx-15.24)>0.1 else -3.4)} {-3.4 if mx >= 96 else (3.4 if abs(mx-90.17)<0.1 else 0)} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
    #              '\t\t(fp_text value "MountingHole_3.2mm" (at 0 3 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
    #              '\t\t(fp_rect (start -1.8 -1.8) (end 1.8 1.8) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS"))',
    #              '\t\t(fp_rect (start -2 -2) (end 2 2) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))',
    #              '\t\t(pad "" np_thru_hole circle (at 0 0) (size 3.4 3.4) (drill 3.2) (layers "*.Cu" "*.Mask"))',
    #              '\t)']
    #         fps.append("\n".join(L))

    # sync per-pin silk labels into the footprint LIBRARY files (clears lib_footprint_mismatch)
    for fpname, texts in usertexts.items():
        libpath = os.path.join(KICAD, "footprints", f"{fpname}.kicad_mod")
        if not os.path.exists(libpath):
            continue
        lib = open(libpath).read()
        lib = "\n".join(ln for ln in lib.split("\n") if '(fp_text user "' not in ln)
        lib = lib.rstrip()
        assert lib.endswith(")")
        lib = lib[:-1].rstrip() + "\n" + "\n".join(texts) + "\n)\n"
        with open(libpath, "w") as f:
            f.write(lib)

    # net declarations must precede footprints in file order
    netdecls = [f'\t(net {v} "{k}")' for k, v in sorted(nets.items(), key=lambda kv: kv[1])]
    outline = []
    (x1, y1), (x2, y2) = OUTLINE
    pts = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
    for a, b in zip(pts, pts[1:] + [pts[0]]):
        outline.append(f'\t(gr_line (start {fmt(a[0])} {fmt(a[1])}) (end {fmt(b[0])} {fmt(b[1])}) (stroke (width 0.1) (type solid)) (layer "Edge.Cuts"))')
    outline.append('\t(gr_text "DropBear V2 -> STM32H7 adapter - PLACEMENT SKETCH, NO ROUTING" (at 50 -26.5 0) (layer "Cmts.User") (effects (font (size 1.5 1.5) (thickness 0.3))))')
    # --- dual-face anti-upside-down silk ---
    outline.append('\t(gr_text "STM32 / MEGA SIDE - MEGA PINS UP" (at 50.8 0.35 0) (layer "F.SilkS") (effects (font (size 1.5 1.5) (thickness 0.3)) (justify bottom)))')
    outline.append('\t(gr_text "TEENSY / DROPBEAR SIDE - TEENSY PINS UP" (at 44 -45 0) (layer "B.SilkS") (effects (font (size 1.5 1.5) (thickness 0.3)) (justify bottom mirror)))')
    # orientation cue: same-corner triangle on BOTH faces (appears at top-left viewed from each face's own side)
    for lay in ("F.SilkS", "B.SilkS"):
        outline.append(f'\t(gr_poly (pts (xy 1.5 -1.5) (xy 1.5 -5.5) (xy 5.5 -1.5)) (stroke (width 0.15) (type solid)) (fill solid) (layer "{lay}"))')
        outline.append(f'\t(gr_text "ORIENT" (at 8.5 -3.5 0) (layer "{lay}") (effects (font (size 1 1) (thickness 0.15)){" (justify mirror)" if lay == "B.SilkS" else ""}))')
    # mega pin-1 arrow (D0 = mega pin 1) on top face; teensy pin-1 already marked on B.SilkS
    outline.append('\t(gr_text "D0=1 >" (at 64.0 -53.1 0) (layer "F.SilkS") (effects (font (size 0.8 0.8) (thickness 0.1)) (justify bottom)))')
    outline.append('\t(gr_text "> pin 1" (at 25.2 -17.4 0) (layer "B.SilkS") (effects (font (size 0.8 0.8) (thickness 0.1)) (justify bottom mirror)))')

    body = "\n".join(out + netdecls + fps + outline) + "\n)\n"
    with open(os.path.join(KICAD, "dropbear-v2-stm32-adapter.kicad_pcb"), "w") as f:
        f.write(body)
    print(f"pcb sketch written: {len(places)} placements + {len(MOUNT_HOLES)} mount holes, {len(nets)} nets")

if __name__ == "__main__" and False:  # FROZEN: live .kicad_pcb is source-of-truth
    main()
