#!/usr/bin/env python3
"""Generate the DropBear V2 -> STM32H7 adapter KiCad project (sch + pcb sketch + footprints).

Run from anywhere:  python3 tools/gen_kicad.py
Outputs into kicad/ under the project root. Deterministic UUIDs (uuid5) so reruns are diff-stable.
"""
import json, os, re, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KICAD = os.path.join(ROOT, "kicad")
FPDIR = os.path.join(KICAD, "footprints")
os.makedirs(FPDIR, exist_ok=True)

U5 = lambda s: str(uuid.uuid5(uuid.NAMESPACE_URL, "dropbear-adapter:" + s))

# ---------------------------------------------------------------- net maps
# Teensy socket pads (Shields:Teensy41 numbering as on DropBear V2) -> net
T_SIGNAL = {  # pad: net name (also used on the Mega side)
    2: "TACHO", 7: "FUELPUMP", 8: "CS_FLASH",
    9: "ESP_TXD", 10: "ESP_RXD",
    11: "CS_MC33810_2", 12: "CS_MC33810_1",
    13: "SPI_MOSI", 14: "SPI_MISO",
    16: "BOOST", 17: "FAN", 18: "SPARE2_OUT", 19: "IDLE1",
    20: "VVT_A1", 21: "IDLE2_SP1",
    22: "STEP_EN", 23: "STEP_STEP", 24: "STEP_DIR",
    26: "DI_VSS", 27: "DI_WMI", 28: "DI_LAUNCH", 29: "DI_FLEX",
    31: "AI_BAT", 32: "AI_SP1", 33: "AI_SP2",
    35: "SPI_SCLK",
    36: "AI_IAT", 37: "AI_CLT", 38: "AI_O2", 39: "AI_TPS",
    40: "AI_BARO", 41: "AI_MAP",
    42: "CRANK", 43: "CAM", 44: "CAN_TX", 45: "CAN_RX",
    50: "VBAT_RTC",
}
T_POWER = {15: "+3V3", 46: "+3V3", 51: "+3V3", 48: "+5V",
           1: "GND", 34: "GND", 47: "GND", 52: "GND"}
T_NC = [3, 5, 6, 25, 30, 49, 53, 54, 66, 67]
T_ALL = [str(i) for i in range(1, 55)] + ["66", "67"]

PADNAME = {
    2: "TACHO", 7: "FUELPUMP", 8: "CS_FLASH", 9: "ESP_TXD", 10: "ESP_RXD",
    11: "CS33810_2", 12: "CS33810_1", 13: "MOSI", 14: "MISO",
    16: "BOOST", 17: "FAN", 18: "SPARE2", 19: "IDLE1", 20: "VVT/STPR-A1",
    21: "IDLE2/SP1", 22: "STEP_EN", 23: "STEP_STEP", 24: "STEP_DIR",
    26: "DI_VSS", 27: "DI_WMI", 28: "DI_LAUNCH", 29: "DI_FLEX",
    31: "AI_BAT", 32: "AI_SP1", 33: "AI_SP2", 35: "SCLK",
    36: "AI_IAT", 37: "AI_CLT", 38: "AI_O2", 39: "AI_TPS",
    40: "AI_BARO", 41: "AI_MAP", 42: "CRANK", 43: "CAM", 44: "CAN_TX", 45: "CAN_RX",
    50: "VBAT_RTC", 15: "+3V3", 46: "+3V3", 51: "+3V3", 48: "+5V",
    1: "GND", 34: "GND", 47: "GND", 52: "GND",
}

# Mega socket groups: (ref, symbol name, value, [pin names]) — pin name == footprint pad name
MEGA_GROUPS = [
    ("J2", "J_MEGA_DIG_A", "MEGA_DIG_A_1x10", ["SCL", "SDA", "AREF", "GND1", "13", "12", "11", "10", "9", "8"]),
    ("J3", "J_MEGA_DIG_B", "MEGA_DIG_B_1x8", ["7", "6", "5", "4", "3", "2", "1", "0"]),
    ("J4", "J_MEGA_DIG_C", "MEGA_DIG_C_1x8", ["14", "15", "16", "17", "18", "19", "20", "21"]),
    ("J5", "J_MEGA_DIG_HI", "MEGA_DIG_HI_2x18",
     ["5V3", "5V4"] + [str(d) for d in range(22, 54)] + ["GND5", "GND6"]),
    ("J6", "J_MEGA_AN_A", "MEGA_AN_A_1x8", ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7"]),
    ("J7", "J_MEGA_AN_B", "MEGA_AN_B_1x8", ["A8", "A9", "A10", "A11", "A12", "A13", "A14", "A15"]),
    ("J8", "J_MEGA_PWR", "MEGA_PWR_1x7", ["IORF", "RST1", "3V3", "5V1", "GND2", "GND3", "VIN"]),
]
# Mega pad -> net (used pins only)
M_NET = {
    "0": "ESP_TXD", "1": "ESP_RXD", "2": "DI_FLEX",
    "14": "CAM", "15": "CRANK", "16": "DI_WMI", "17": "DI_VSS", "18": "DI_LAUNCH", "20": "VVT_A1", "21": "STEP_STEP",
    "22": "STEP_EN", "23": "STEP_DIR",
    "28": "TACHO", "29": "FAN", "30": "BOOST", "32": "IDLE1", "33": "IDLE2_SP1",
    "36": "FUELPUMP", "37": "SPARE2_OUT",
    "44": "CAN_TX", "45": "CAN_RX",
    "48": "SPI_SCLK", "49": "CS_FLASH", "50": "CS_MC33810_1",
    "51": "SPI_MISO", "52": "SPI_MOSI", "53": "CS_MC33810_2",
    "A0": "AI_IAT", "A1": "AI_CLT", "A2": "AI_O2", "A3": "AI_TPS", "A4": "AI_BAT",
    "A8": "AI_BARO", "A9": "AI_MAP", "A10": "AI_SP1", "A11": "AI_SP2",
    "5V1": "+5V", "5V3": "+5V", "5V4": "+5V",
    "GND1": "GND", "GND2": "GND", "GND3": "GND", "GND5": "GND", "GND6": "GND",
    "3V3": "+3V3",
}

# ---------------------------------------------------------------- footprints
def load_pads(rel):
    with open(os.path.join(ROOT, "research-clones", rel)) as f:
        return json.load(f)

def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return s if s else "0"

def fp_teensy():
    pads = load_pads("teensy41_pads.json")
    L = [f'(footprint "TEENSY41_SOCKET" (version 20221018) (generator gen)',
         '\t(descr "Teensy 4.1 bottom socket pattern, cloned from DropBear V2 Shields:Teensy41 (56 TH pads)")',
         '\t(attr through_hole exclude_from_pos_files exclude_from_bom)',
         '\t(fp_text reference "J1" (at -31 10.5 90) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
         '\t(fp_text value "TEENSY41_SOCKET" (at 0 12 90) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))',
         '\t(fp_rect (start -31.2 -10.6) (end 31.2 10.6) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS"))',
         '\t(fp_rect (start -31 -10.4) (end 31 10.4) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))',
         '\t(fp_text user "1" (at -30.6 7.62 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))']
    for p in pads:
        net = T_POWER.get(int(p["n"])) or T_SIGNAL.get(int(p["n"]))
        pad_type = "circle" if p["sh"] == "circle" else p["sh"]
        L.append(f'\t(pad "{p["n"]}" thru_hole {pad_type} (at {fmt(p["x"])} {fmt(p["y"])}) '
                 f'(size {fmt(p["w"])} {fmt(p["h"])}) (drill {fmt(p["d"])}) (layers "*.Cu" "*.Mask"))')
    L.append(")")
    return "\n".join(L)

MEGA_XY = {}  # pad name -> (x,y) in shield coords
def mega_groups_xy():
    pads = load_pads("mega_r3_shield_pads.json")
    for p in pads:
        MEGA_XY[p["n"]] = (p["x"], p["y"])
        if p["n"].startswith("D"):
            MEGA_XY[p["n"][1:]] = (p["x"], p["y"])  # bare-digit alias for group pin lists

def fp_mega(group):
    ref, sym, value, pins = group
    pts = [MEGA_XY[p] for p in pins]
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    # normalize so group bbox min = 0
    x0, y0 = min(xs), min(ys)
    loc = {p: (MEGA_XY[p][0] - x0, MEGA_XY[p][1] - y0) for p in pins}
    w = max(xs) - x0; h = max(ys) - y0
    L = [f'(footprint "{value}" (version 20221018) (generator gen)',
         f'\t(descr "Arduino Mega 2560 R3 socket group {value} — positions per Alarm-Siren Arduino_Mega2560_R3_Shield")',
         '\t(attr through_hole exclude_from_pos_files exclude_from_bom)',
         f'\t(fp_text reference "{ref}" (at {fmt(w/2)} {fmt(h/2)} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))',
         f'\t(fp_text value "{value}" (at {fmt(w/2)} {fmt(h/2+1.5)} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))']
    m = 0.6
    L.append(f'\t(fp_rect (start {fmt(-m)} {fmt(-m)}) (end {fmt(w+m)} {fmt(h+m)}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))')
    for p in pins:
        x, y = loc[p]
        L.append(f'\t(pad "{p}" thru_hole oval (at {fmt(x)} {fmt(y)}) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask"))')
    L.append(")")
    return "\n".join(L), (x0, y0)

def fp_simple(name, descr, pads, silk, crt):
    L = [f'(footprint "{name}" (version 20221018) (generator gen)',
         f'\t(descr "{descr}")']
    if pads[0][3] == "smd":
        L.append('\t(attr smd)')
    else:
        L.append('\t(attr through_hole)')
    L.append(f'\t(fp_text reference "REF**" (at 0 -{fmt(crt)} 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15))))')
    L.append(f'\t(fp_text value "{name}" (at 0 {fmt(crt)} 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))')
    L.append(f'\t(fp_rect (start {fmt(-silk)} {fmt(-silk)}) (end {fmt(silk)} {fmt(silk)}) (stroke (width 0.12) (type solid)) (fill none) (layer "F.SilkS"))')
    L.append(f'\t(fp_rect (start {fmt(-crt)} {fmt(-crt)}) (end {fmt(crt)} {fmt(crt)}) (stroke (width 0.05) (type solid)) (fill none) (layer "F.CrtYd"))')
    for (num, x, y, kind) in pads:
        if kind == "smd":
            L.append(f'\t(pad "{num}" smd rect (at {fmt(x)} {fmt(y)}) (size 1.0 1.6) (layers "F.Cu" "F.Paste" "F.Mask"))')
        elif kind == "npth":
            L.append(f'\t(pad "" np_thru_hole circle (at {fmt(x)} {fmt(y)}) (size 3.4 3.4) (drill 3.2) (layers "*.Cu" "*.Mask"))')
        else:
            L.append(f'\t(pad "{num}" thru_hole circle (at {fmt(x)} {fmt(y)}) (size 1.7 1.7) (drill 1.0) (layers "*.Cu" "*.Mask"))')
    L.append(")")
    return "\n".join(L)

# ---------------------------------------------------------------- schematic build
def q(s): return s.replace('\\', '\\\\').replace('"', '\\"')

def pin_def(num, name, py, electrical="passive", angle=0, x=-5.08, length=2.54, hide=False):
    h = " hide" if hide else ""
    return (f'\t\t(pin {electrical} line (at {fmt(x)} {fmt(py)} {angle}) (length {fmt(length)}){h}\n'
            f'\t\t\t(name "{q(name)}" (effects (font (size 0.9 0.9))))\n'
            f'\t\t\t(number "{q(num)}" (effects (font (size 0.9 0.9))))\n'
            f'\t\t)')

SCH = []
LIBS = []

def add_lib(sym):
    if sym not in [l.split('"')[1] for l in LIBS]:
        LIBS.append(sym)

def text_items():
    return []

LINX_BT1_FP = '''(footprint "BatteryHolder_LINX_BAT-HLD-012-SMT" (version 20221018) (generator dropbear-adapter-gen)
	(descr "SMT CR1216/1220/1225 coin cell holder, Linx BAT-HLD-012-SMT (KiCad stock Battery.pretty), ~3mm profile")
	(attr smd)
	(fp_text reference "BT1" (at 0 6 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness 0.15)) (justify mirror)))
	(fp_text value "BatteryHolder_LINX_BAT-HLD-012-SMT" (at 0 -6 0) (layer "F.Fab") (effects (font (size 1 1) (thickness 0.15))))
	(fp_line (start -6.55 -2.75) (end -4.9 -4.4) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "8a858ac8-3328-4a79-99b0-fb13f736fb1e") )
	(fp_line (start -6.55 2.85) (end -5.4 4.2) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "e15cb4ff-1a94-4e4c-b8ce-ec909302d96f") )
	(fp_line (start -4.9 -4.4) (end -3 -4.4) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "cfe7cf9c-12b1-4f21-b204-306e7d1c8c63") )
	(fp_line (start 4.9 -4.4) (end 3 -4.4) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "1edaee76-3c7e-4b63-9051-f36bb34bebca") )
	(fp_line (start 4.9 -4.4) (end 6.55 -2.75) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "029931cf-c98d-47aa-95ea-8dfc74a746f1") )
	(fp_line (start 6.55 2.85) (end 5.4 4.2) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "573c796e-bdb6-494f-b085-fd8e752db39e") )
	(fp_arc (start -2.504098 4.697607) (mid -4.031094 4.908816) (end -5.4 4.2) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "178126d5-bc89-4fdd-9f94-39230c7f76d6") )
	(fp_arc (start 5.4 4.2) (mid 4.029781 4.909041) (end 2.501694 4.696459) (stroke (width 0.12) (type solid) ) (layer "F.SilkS") (uuid "a7896674-e085-4830-8dbc-b136f8b42b5b") )
	(fp_line (start -9.35 -3.05) (end -7.25 -3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "09c46754-cb69-4b85-8fae-c289ee6fdfed") )
	(fp_line (start -9.35 3.05) (end -9.35 -3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "f18e0276-d6fd-4986-8587-e4126b53ad49") )
	(fp_line (start -9.35 3.05) (end -7.25 3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "ed9ad8ba-5753-4816-934c-7886c5a01658") )
	(fp_line (start -7.25 -3.05) (end -3.55 -6.75) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "2587f59f-08aa-46cf-aa43-e2d260dba939") )
	(fp_line (start -3.55 -6.75) (end 3.55 -6.75) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "1524842b-b6e1-4600-9a73-9fc361cfe213") )
	(fp_line (start -3.55 6.75) (end -7.25 3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "411edb8c-40f4-4d8c-a95b-5b666c87de8f") )
	(fp_line (start -3.55 6.75) (end 3.55 6.75) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "c483758e-4fe1-4456-80e5-8e598a94da03") )
	(fp_line (start 3.55 -6.75) (end 7.25 -3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "ace0046e-6bbd-4eaf-ad9b-b5aa60ce4292") )
	(fp_line (start 3.55 6.75) (end 7.25 3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "524a147a-bb9f-41df-b2ec-4ca3471f5f37") )
	(fp_line (start 7.25 -3.05) (end 9.35 -3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "a18562d7-0e03-4e70-b3f1-7a6a9c602400") )
	(fp_line (start 9.35 -3.05) (end 9.35 3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "e96d0eb8-eac1-4e0c-9814-71cb5f4e1fdf") )
	(fp_line (start 9.35 3.05) (end 7.25 3.05) (stroke (width 0.05) (type solid) ) (layer "F.CrtYd") (uuid "8855f58e-bdfc-4661-a8a7-bd50eb44a61e") )
	(pad "1" smd rect (at -7.6 0) (size 2.5 5.1) (layers "F.Cu" "F.Mask" "F.Paste") (uuid "d2313279-6c73-4c17-9049-74cf3a87dd3c") )
	(pad "1" smd rect (at 7.6 0) (size 2.5 5.1) (layers "F.Cu" "F.Mask" "F.Paste") (uuid "62584a88-748b-4949-b238-cc4e3f02c456") )
	(pad "2" smd circle (at 0 0) (size 10.2 10.2) (layers "F.Cu" "F.Mask") (uuid "fc5f2843-037d-4ed3-b475-9a273dfaa49c") )
)
'''

def main():
    mega_groups_xy()

    # ---- write footprints
    with open(os.path.join(FPDIR, "TEENSY41_SOCKET.kicad_mod"), "w") as f:
        f.write(fp_teensy())
    group_offsets = {}
    for g in MEGA_GROUPS:
        body, off = fp_mega(g)
        with open(os.path.join(FPDIR, f"{g[2]}.kicad_mod"), "w") as f:
            f.write(body)
        group_offsets[g[2]] = off

    # battery holder: Linx BAT-HLD-012 SMT (CR1216/1220/1225, ~3mm profile)
    with open(os.path.join(FPDIR, "BatteryHolder_LINX_BAT-HLD-012-SMT.kicad_mod"), "w") as f:
        f.write(LINX_BT1_FP)

    for name, descr, pads, silk, crt in [
        ("SOT-23_LDO", "SOT-23 3-pin LDO (XC6206/AP2112 class) - DNP by default",
         [("1", -1.1, -0.85, "smd"), ("2", 1.1, -0.85, "smd"), ("3", 0, 0.95, "smd")], 2.1, 2.3),
        ("SolderJumper-2_Bridged", "Solder jumper 2-pin, bridged (default CLOSED)",
         [("1", -0.65, 0, "smd"), ("2", 0.65, 0, "smd")], 1.6, 1.8),
        ("SolderJumper-2_Open", "Solder jumper 2-pin, open (default OPEN)",
         [("1", -0.65, 0, "smd"), ("2", 0.65, 0, "smd")], 1.6, 1.8),
        ("TestPoint_THT_D2", "VBAT test point (wire to DCWerx VBAT pad)",
         [("1", 0, 0, "th")], 1.3, 1.5),
        ("C_0603_DNP", "0603 capacitor placeholder (LDO in/out, DNP)",
         [("1", -0.75, 0, "smd"), ("2", 0.75, 0, "smd")], 1.4, 1.7),
        ("MountingHole_3.2mm", "M3 mounting hole (Arduino shield positions)",
         [("1", 0, 0, "npth")], 1.8, 2.0),
    ]:
        content = fp_simple(name, descr, pads, silk, crt)
        if name in ("SOT-23_LDO", "C_0603_DNP", "SolderJumper-2_Bridged", "SolderJumper-2_Open"):
            content = content.replace('(effects (font (size 1 1) (thickness 0.15))))',
                                      '(effects (font (size 1 1) (thickness 0.15)) (justify mirror)))', 1)
        if name == "MountingHole_3.2mm":
            content = content.replace("(attr through_hole)",
                                      "(attr through_hole exclude_from_pos_files exclude_from_bom)")
        if name == "C_0603_DNP":
            content = content.replace("(size 1.0 1.6)", "(size 1.0 1.0)")
        if name == "SolderJumper-2_Bridged" or name == "SolderJumper-2_Open":
            content = content.replace("(size 1.0 1.6)", "(size 1.0 1.0)")
        if name == "TestPoint_THT_D2":
            content = content.replace("(size 1.7 1.7) (drill 1.0)", "(size 2 2) (drill 1)")
        with open(os.path.join(FPDIR, f"{name}.kicad_mod"), "w") as f:
            f.write(content)

    # ---- lib symbols (embedded)
    # Teensy socket symbol
    pins = []
    ytop = 2.54 * len(T_ALL) / 2
    for i, pad in enumerate(T_ALL):
        padn = int(pad)
        py = ytop - 2.54 * i
        nm = PADNAME.get(padn, "NC")
        pins.append(pin_def(pad, f"P{pad} {nm}" if nm != "NC" else f"P{pad}", py))
    lib_t41 = (f'(symbol "dropbear:J_TEENSY41" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)\n'
               f'\t(property "Reference" "J" (at 0 {fmt(ytop+5.08)} 0) (effects (font (size 1.27 1.27))))\n'
               f'\t(property "Value" "TEENSY41_SOCKET" (at 0 {fmt(ytop+7.62)} 0) (effects (font (size 1.27 1.27))))\n'
               f'\t(property "Footprint" "dropbear:TEENSY41_SOCKET" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
               f'\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
               f'\t(symbol "J_TEENSY41_0_1"\n'
               f'\t\t(rectangle (start 2.54 {fmt(ytop+2.54)}) (end -2.54 {fmt(-ytop-2.54)}) (stroke (width 0.254) (type default)) (fill (type background)))\n'
               f'\t)\n'
               f'\t(symbol "J_TEENSY41_1_1"\n' + "\n".join(pins) + "\n\t)\n)")
    add_lib(lib_t41)

    # Mega group symbols
    for ref, sym, value, plist in MEGA_GROUPS:
        pins = []
        ytop = 2.54 * len(plist) / 2
        for i, p in enumerate(plist):
            py = ytop - 2.54 * i
            nm = M_NET.get(p, "")
            pins.append(pin_def(p, f"{p} {nm}" if nm else p, py, angle=180, x=5.08))
        lib = (f'(symbol "dropbear:{sym}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)\n'
               f'\t(property "Reference" "J" (at 0 {fmt(ytop+5.08)} 0) (effects (font (size 1.27 1.27))))\n'
               f'\t(property "Value" "{value}" (at 0 {fmt(ytop+7.62)} 0) (effects (font (size 1.27 1.27))))\n'
               f'\t(property "Footprint" "dropbear:{value}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
               f'\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
               f'\t(symbol "{sym}_0_1"\n'
               f'\t\t(rectangle (start -2.54 {fmt(ytop+2.54)}) (end 2.54 {fmt(-ytop-2.54)}) (stroke (width 0.254) (type default)) (fill (type background)))\n'
               f'\t)\n'
               f'\t(symbol "{sym}_1_1"\n' + "\n".join(pins) + "\n\t)\n)")
        add_lib(lib)

    # Small parts symbols
    def mk_sym(name, refpfx, fpref, pinlist, w=3.81):
        ytop = 2.54 * len(pinlist) / 2
        pp = [pin_def(n, nm, ytop - 2.54 * i, electrical=el) for i, (n, nm, el) in enumerate(pinlist)]
        s = (f'(symbol "dropbear:{name}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)\n'
             f'\t(property "Reference" "{refpfx}" (at 0 {fmt(ytop+5.08)} 0) (effects (font (size 1.27 1.27))))\n'
             f'\t(property "Value" "{name}" (at 0 {fmt(ytop+7.62)} 0) (effects (font (size 1.27 1.27))))\n'
             f'\t(property "Footprint" "{fpref}" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
             f'\t(property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
             f'\t(symbol "{name}_0_1"\n'
             f'\t\t(rectangle (start 2.54 {fmt(ytop+2.54)}) (end -2.54 {fmt(-ytop-2.54)}) (stroke (width 0.254) (type default)) (fill (type background)))\n'
             f'\t)\n'
             f'\t(symbol "{name}_1_1"\n' + "\n".join(pp) + "\n\t)\n)")
        add_lib(s)
    mk_sym("LDO_SOT23", "U", "dropbear:SOT-23_LDO",
           [("1", "VIN", "power_in"), ("2", "GND", "power_in"), ("3", "VOUT", "power_out")])
    mk_sym("BATTERY_CR1220", "BT", "dropbear:BatteryHolder_LINX_BAT-HLD-012-SMT",
           [("+", "+", "passive"), ("-", "-", "passive")])
    mk_sym("JUMPER_2", "JP", "dropbear:SolderJumper-2_Bridged",
           [("1", "A", "passive"), ("2", "B", "passive")])
    mk_sym("TESTPOINT", "TP", "dropbear:TestPoint_THT_D2", [("1", "1", "passive")])
    mk_sym("C_DNP", "C", "dropbear:C_0603_DNP", [("1", "1", "passive"), ("2", "2", "passive")])

    # power symbols
    for nm in ["GND", "+5V", "+3V3", "PWR_FLAG"]:
        val = nm if nm != "PWR_FLAG" else "PWR_FLAG"
        el = "power_out" if nm == "PWR_FLAG" else "power_in"
        hidepin = " hide" if nm != "PWR_FLAG" else ""
        s = (f'(symbol "dropbear:PWR_{nm}" (power) (pin_names hide) (in_bom yes) (on_board yes)\n'
             f'\t(property "Reference" "#PWR" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
             f'\t(property "Value" "{val}" (at 0 5.08 0) (effects (font (size 1.27 1.27))))\n'
             f'\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
             f'\t(symbol "PWR_{nm}_0_1"\n'
             + (f'\t\t(polyline (pts (xy -1.27 0) (xy 1.27 0)) (stroke (width 0.5) (type default)) (fill (type none)))\n'
                f'\t\t(polyline (pts (xy -0.762 0.762) (xy 0 0) (xy 0.762 0.762)) (stroke (width 0.5) (type default)) (fill (type none)))\n' if nm == "GND" else
                f'\t\t(polyline (pts (xy 0 0) (xy 0 1.27)) (stroke (width 0.5) (type default)) (fill (type none)))\n'
                f'\t\t(polyline (pts (xy -1.27 1.27) (xy 1.27 1.27)) (stroke (width 0.5) (type default)) (fill (type none)))\n' if nm == "PWR_FLAG" else
                f'\t\t(polyline (pts (xy 0 0) (xy 0 1.27)) (stroke (width 0.5) (type default)) (fill (type none)))\n'
                f'\t\t(polyline (pts (xy -1.27 1.27) (xy 0 2.54) (xy 1.27 1.27)) (stroke (width 0.5) (type default)) (fill (type none)))\n'
                f'\t\t(polyline (pts (xy -1.27 1.27) (xy 1.27 1.27)) (stroke (width 0.5) (type default)) (fill (type none)))\n')
             + f'\t)\n'
             f'\t(symbol "PWR_{nm}_1_1"\n'
             f'\t\t(pin {el} line (at 0 0 270) (length 2.54)\n'
             f'\t\t\t(name "{val}" (effects (font (size 0.9 0.9))))\n'
             f'\t\t\t(number "1" (effects (font (size 0.9 0.9))))\n'
             f'\t\t)\n\t)\n)')
        add_lib(s)

    # ---- schematic instances + wires + labels
    items = []       # (sortkey_y, text) rendered in order
    ROOTUUID = U5("root-sheet")

    def inst(lib_id, ref, val, x, y, fp=None, extra_props=()):
        uid = U5(f"inst:{ref}")
        props = [f'\t\t(property "Reference" "{ref}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27))))',
                 f'\t\t(property "Value" "{q(val)}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))']
        return (f'\t(symbol (lib_id "{lib_id}") (at {fmt(x)} {fmt(y)} 0) (unit 1)\n'
                f'\t\t(property "Reference" "{ref}" (at {fmt(x-7)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (justify right)))\n'
                f'\t\t(property "Value" "{q(val)}" (at {fmt(x-7)} {fmt(y+2.2)} 0) (effects (font (size 1.0 1.0)) (justify right)))\n'
                f'\t\t(property "Footprint" "{fp}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                f'\t\t(property "Datasheet" "" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
                f'\t\t(uuid "{uid}")\n'
                f'\t\t(in_bom yes) (on_board yes) (dnp no)\n'
                f'\t\t(instances (project "dropbear-v2-stm32-adapter" (path "/{ROOTUUID}" (reference "{ref}") (unit 1))))\n'
                f'\t)\n')

    def wire(x1, y1, x2, y2):
        return (f'\t(wire (pts (xy {fmt(x1)} {fmt(y1)}) (xy {fmt(x2)} {fmt(y2)}))\n'
                f'\t\t(stroke (width 0) (type default)) (uuid "{U5(f"w:{x1},{y1},{x2},{y2}")}")\n\t)\n')

    def label(name, x, y, just="right"):
        return (f'\t(label "{q(name)}" (at {fmt(x)} {fmt(y)} 0) (effects (font (size 0.9 0.9)) (justify {just})) (uuid "{U5(f"l:{name}:{x},{y}")}"))\n')

    def nocon(x, y):
        return f'\t(no_connect (at {fmt(x)} {fmt(y)} 0) (uuid "{U5(f"nc:{x},{y}")}"))\n'

    pwrcount = [0]
    def pwr(name, x, y):
        pwrcount[0] += 1
        ref = f"#PWR{pwrcount[0]:03d}"
        uid = U5(f"pwr:{ref}:{name}:{x},{y}")
        return (f'\t(symbol (lib_id "dropbear:PWR_{name}") (at {fmt(x)} {fmt(y)} 0) (unit 1)\n'
                f'\t\t(property "Reference" "{ref}" (at {fmt(x)} {fmt(y-2.2)} 0) (effects (font (size 1.0 1.0)) (hide yes)))\n'
                f'\t\t(property "Value" "{name}" (at {fmt(x)} {fmt(y-2.2)} 0) (effects (font (size 1.0 1.0))))\n'
                f'\t\t(uuid "{uid}")\n'
                f'\t\t(instances (project "dropbear-v2-stm32-adapter" (path "/{ROOTUUID}" (reference "{ref}") (unit 1))))\n'
                f'\t)\n')

    body = []
    # --- J1 teensy socket at left
    J1X, J1Y = 127, 111.76  # on 1.27mm lattice; pin abs conn = (J1X-5.08, J1Y - py)
    body.append(inst("dropbear:J_TEENSY41", "J1", "TEENSY41_SOCKET", J1X, J1Y, "dropbear:TEENSY41_SOCKET"))
    for i, pad in enumerate(T_ALL):
        padn = int(pad)
        py = 2.54 * len(T_ALL) / 2 - 2.54 * i
        cx, cy = J1X - 5.08, J1Y - py
        if padn in T_POWER:
            body.append(wire(cx, cy, cx - 2.54, cy))
            body.append(pwr(T_POWER[padn], cx - 2.54, cy))
        elif padn in T_SIGNAL:
            body.append(wire(cx, cy, cx - 2.54, cy))
            body.append(label(T_SIGNAL[padn], cx - 2.54, cy, "right"))
        else:
            pass  # NC flag omitted: kicad-cli 10.0.8 erc crashes on no_connect items; pin_not_connected severity ignored in .kicad_pro

    # --- Mega groups at right, pins right side
    MX = 469.9
    ys = {"J2": 58.42, "J3": 96.52, "J4": 133.35, "J5": 170.18, "J6": 273.05, "J7": 298.45, "J8": 323.85}
    for ref, sym, value, plist in MEGA_GROUPS:
        gy = ys[ref]
        body.append(inst(f"dropbear:{sym}", ref, value, MX, gy, f"dropbear:{value}"))
        for i, p in enumerate(plist):
            py = 2.54 * len(plist) / 2 - 2.54 * i
            cx, cy = MX + 5.08, gy - py
            net = M_NET.get(p)
            if net:
                if net in ("GND", "+5V", "+3V3"):
                    body.append(wire(cx, cy, cx + 2.54, cy))
                    body.append(pwr(net, cx + 2.54, cy))
                else:
                    body.append(wire(cx, cy, cx + 2.54, cy))
                    body.append(label(net, cx + 2.54, cy, "left"))
            else:
                pass  # NC flag omitted (see note at J1 loop)

    # --- power selection + VBAT + LDO + coin cell (middle column)
    def mini(ref, symname, val, x, y, fp, nets):
        """place small 2-3 pin part; nets list aligns to pins top->bottom"""
        body.append(inst(f"dropbear:{symname}", ref, val, x, y, fp))
        ytop = 2.54 * len(nets) / 2
        for i, (pinnum, net) in enumerate(nets):
            py = ytop - 2.54 * i
            cx, cy = x - 5.08, y - py
            body.append(wire(cx, cy, cx - 2.54, cy))
            if net in ("GND", "+5V", "+3V3"):
                body.append(pwr(net, cx - 2.54, cy))
            else:
                body.append(label(net, cx - 2.54, cy, "right"))

    mini("TP1", "TESTPOINT", "VBAT -> DCWerx VBAT pad", 317.5, 246.38, "dropbear:TestPoint_THT_D2",
         [("1", "VBAT_RTC")])
    body.append(f'\t(text "VBAT: DropBear coin cell (socket pad 50) -> TP1 -> one wire to the DCWerx VBAT pad (photo-verified pad near STM32, bottom-left)." (at 292.1 257.81 0) (effects (font (size 1 1)) (justify left)) (uuid "{U5("txt:note2")}"))\n')

    # PWR_FLAGs stacked coincident with existing power-symbol pin points (J1 power pads)
    def j1_pin_xy(pad):
        i = T_ALL.index(str(pad))
        py = 2.54 * len(T_ALL) / 2 - 2.54 * i
        return J1X - 5.08 - 2.54, J1Y - py
    for pad in (1, 48, 15):
        body.append(pwr("PWR_FLAG", *j1_pin_xy(pad)))

    # ---- assemble schematic file
    sch = f'''(kicad_sch (version 20231120) (generator "dropbear-adapter-gen") (generator_version "1.0")
	(uuid "{ROOTUUID}")
	(paper "A2")
	(title_block
		(title "DropBear V2 to STM32H7 (DCWerx Mega-footprint) Adapter")
		(date "2026-11-08")
		(rev "A")
		(comment 1 "Underside: Teensy-4.1 socket pattern (plugs into DropBear V2)")
		(comment 2 "Topside: Arduino Mega 2560 R3 sockets (DCWerx STM32H7 plugs in)")
		(comment 3 "Net map per RESEARCH.md section B; SPI4 crossed-label correction applied")
	)
	(lib_symbols
{os.linesep.join(LIBS)}
	)
{os.linesep.join(body)}
	(sheet_instances (path "/" (page "1")))
)
'''
    with open(os.path.join(KICAD, "dropbear-v2-stm32-adapter.kicad_sch"), "w") as f:
        f.write(sch)

    # ---- project file + lib tables + symbol lib
    with open(os.path.join(KICAD, "dropbear-v2-stm32-adapter.kicad_pro"), "w") as f:
        json.dump({"board": {"3dviewports": [], "design_settings": {}, "layer_presets": [], "viewports": []},
                   "boards": [], "cvpcb": {"equivalence_files": []},
                   "erc": {"rule_severities": {"pin_not_connected": "ignore"}, "meta": {"version": 0}},
                   "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
                   "meta": {"filename": "dropbear-v2-stm32-adapter.kicad_pro", "version": 2},
                   "net_settings": {"classes": []},
                   "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
                   "schematic": {"annotate_start_num": 0, "drawing": {}, "legacy_lib_dir": "", "legacy_lib_list": []},
                   "sheets": [[ROOTUUID, "root"]], "text_variables": {}}, f, indent=2)
    with open(os.path.join(KICAD, "sym-lib-table"), "w") as f:
        f.write('(sym_lib_table (version 7)\n'
                '\t(lib (name "dropbear")(type "KiCad")(uri "${KIPRJMOD}/dropbear.kicad_sym")(options "")(descr "Adapter-local symbols"))\n)\n')
    with open(os.path.join(KICAD, "dropbear.kicad_sym"), "w") as f:
        f.write('(kicad_symbol_lib (version 20220914) (generator "dropbear-adapter-gen")\n'
                + "\n".join(LIBS) + "\n)\n")
    with open(os.path.join(KICAD, "fp-lib-table"), "w") as f:
        f.write('(fp_lib_table (version 7)\n'
                '\t(lib (name "dropbear")(type "KiCad")(uri "${KIPRJMOD}/footprints")(options "")(descr "Adapter-local footprints"))\n)\n')

    print("schematic + footprints + pro written")
    return group_offsets

if __name__ == "__main__":
    offs = main()
    print("mega group shield-coord offsets:", offs)