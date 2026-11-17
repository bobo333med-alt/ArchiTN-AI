import os
import math
from typing import Dict, Any, Tuple
import ezdxf
from ezdxf.enums import TextEntityAlignment
import matplotlib.pyplot as plt
import matplotlib.patches as patches


# ألوان هادئة ومهنية للغرف في صورة المعاينة PNG
SPACE_COLORS = {
    "living": "#E8F1F5",
    "salon": "#E8F1F5",
    "bedroom": "#F3EBF5",
    "chambre": "#F3EBF5",
    "kitchen": "#FFF4E5",
    "cuisine": "#FFF4E5",
    "bathroom": "#E5F6F0",
    "sdb": "#E5F6F0",
    "wc": "#E5F6F0",
    "corridor": "#F2F3F4",
    "degagement": "#F2F3F4",
    "dégagement": "#F2F3F4",
}


def get_space_color(space_type: str, space_name: str) -> str:
    st = space_type.lower()
    sn = space_name.lower()
    for key, color in SPACE_COLORS.items():
        if key in st or key in sn:
            return color
    return "#F8F9F9"


def _compute_opening_coords(
    x: float, y: float, w: float, d: float, wall: str, offset: float, opening_w: float
) -> Tuple[Tuple[float, float], Tuple[float, float], str]:
    """
    يحسب نقطتي البداية والنهاية للفتحة (باب أو نافذة) على جدار الغرفة.
    """
    wall = wall.lower()
    if wall == "south":
        p1 = (x + offset, y)
        p2 = (x + offset + opening_w, y)
    elif wall == "north":
        p1 = (x + offset, y + d)
        p2 = (x + offset + opening_w, y + d)
    elif wall == "west":
        p1 = (x, y + offset)
        p2 = (x, y + offset + opening_w)
    elif wall == "east":
        p1 = (x + w, y + offset)
        p2 = (x + w, y + offset + opening_w)
    else:
        p1 = (x + offset, y)
        p2 = (x + offset + opening_w, y)
    return p1, p2, wall


def _get_door_swing_geometry(
    p1: Tuple[float, float], p2: Tuple[float, float], wall: str, opening_w: float
) -> Tuple[Tuple[float, float], Tuple[float, float], float, float]:
    """
    يحسب نقطة مفصلة الباب، طرف الدرفة المفتوحة، وزاويتي البداية والنهاية لقوس الفتح (90 درجة) داخل الغرفة.
    """
    x1, y1 = p1
    if wall == "south":
        hinge = (x1, y1)
        leaf_end = (x1, y1 + opening_w)
        start_angle, end_angle = 0.0, 90.0
    elif wall == "north":
        hinge = (x1, y1)
        leaf_end = (x1, y1 - opening_w)
        start_angle, end_angle = 270.0, 360.0
    elif wall == "west":
        hinge = (x1, y1)
        leaf_end = (x1 + opening_w, y1)
        start_angle, end_angle = 0.0, 90.0
    elif wall == "east":
        hinge = (x1, y1)
        leaf_end = (x1 - opening_w, y1)
        start_angle, end_angle = 90.0, 180.0
    else:
        hinge = (x1, y1)
        leaf_end = (x1, y1 + opening_w)
        start_angle, end_angle = 0.0, 90.0

    return hinge, leaf_end, start_angle, end_angle


def generate_cad_and_preview(
    plan_data: Dict[str, Any], output_dir: str = "outputs", base_filename: str = "architn_plan"
) -> Tuple[str, str]:
    """
    يولد ملف AutoCAD (.dxf) وصورة معاينة (.png) من بيانات المخطط المدققة.
    تُرجع: (مسار ملف DXF, مسار صورة PNG)
    """
    os.makedirs(output_dir, exist_ok=True)
    dxf_path = os.path.join(output_dir, f"{base_filename}.dxf")
    png_path = os.path.join(output_dir, f"{base_filename}.png")

    terrain = plan_data["terrain"]
    setbacks = plan_data["setbacks"]
    spaces = plan_data["spaces"]

    t_width = float(terrain["width"])
    t_depth = float(terrain["depth"])
    street_side = str(terrain.get("street_side", "south")).lower()

    x_min = float(setbacks.get("left", 0))
    y_min = float(setbacks.get("front", 0))
    x_max = t_width - float(setbacks.get("right", 0))
    y_max = t_depth - float(setbacks.get("rear", 0))

    # ==========================================
    # 1. إنشاء ملف AutoCAD (.dxf) بطبقات منظمة
    # ==========================================
    doc = ezdxf.new("R2010")
    doc.units = ezdxf.units.M  # الوحدة بالمتر
    msp = doc.modelspace()

    if "DASHED" not in doc.linetypes:
        doc.linetypes.new("DASHED", dxfattribs={"description": "Dashed line", "pattern": [0.5, 0.25, -0.25]})

    # تعريف الطبقات الهندسية القياسية
    doc.layers.add("TERRAIN", color=3)       # أخضر: حدود الأرض
    doc.layers.add("SETBACKS", color=1, linetype="DASHED")  # أحمر متقطع: الارتدادات
    doc.layers.add("WALLS", color=7)         # أبيض/أسود: الجدران
    doc.layers.add("DOORS", color=4)         # سماوي: الأبواب وأقواس الفتح
    doc.layers.add("WINDOWS", color=5)       # أزرق: النوافذ
    doc.layers.add("TEXT_AREAS", color=2)    # أصفر: الكتابات والمساحات

    # رسم حدود قطعة الأرض (TERRAIN)
    terrain_pts = [(0, 0), (t_width, 0), (t_width, t_depth), (0, t_depth), (0, 0)]
    msp.add_lwpolyline(terrain_pts, dxfattribs={"layer": "TERRAIN", "lineweight": 35})

    # رسم خط منطقة البناء / الارتدادات (SETBACKS)
    setback_pts = [(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max), (x_min, y_min)]
    msp.add_lwpolyline(setback_pts, dxfattribs={"layer": "SETBACKS", "lineweight": 18})

    # كتابة جهة الشارع
    msp.add_text(
        f"VOIE / RUE ({street_side.upper()})",
        dxfattribs={"layer": "TEXT_AREAS", "height": 0.35},
    ).set_placement((t_width / 2.0, -0.8), align=TextEntityAlignment.MIDDLE_CENTER)

    # ==========================================
    # 2. إعداد لوحة الرسم للمعاينة (Matplotlib PNG)
    # ==========================================
    fig, ax = plt.subplots(figsize=(10, 10 * (t_depth / max(t_width, 1.0)) + 1.5))
    ax.set_aspect("equal")
    ax.set_facecolor("#FFFFFF")

    # رسم حدود الأرض في PNG
    terrain_rect = patches.Rectangle(
        (0, 0), t_width, t_depth, linewidth=2.2, edgecolor="#1E8449", facecolor="#F9FBF9", linestyle="-", zorder=1
    )
    ax.add_patch(terrain_rect)

    # رسم خط الارتداد في PNG
    setback_rect = patches.Rectangle(
        (x_min, y_min),
        x_max - x_min,
        y_max - y_min,
        linewidth=1.3,
        edgecolor="#C0392B",
        facecolor="none",
        linestyle="--",
        zorder=2,
    )
    ax.add_patch(setback_rect)

    # ==========================================
    # 3. رسم الفضاءات، الجدران، الأبواب، والنوافذ
    # ==========================================
    for space in spaces:
        s_name = space.get("name", "Espace")
        s_type = str(space.get("type", "room"))
        x = float(space["x"])
        y = float(space["y"])
        w = float(space["width"])
        d = float(space["depth"])
        area = round(w * d, 2)

        # --- في DXF: رسم مستطيل الجدران ---
        room_pts = [(x, y), (x + w, y), (x + w, y + d), (x, y + d), (x, y)]
        msp.add_lwpolyline(room_pts, dxfattribs={"layer": "WALLS", "lineweight": 30})

        # --- في DXF: كتابة الاسم والمساحة ---
        cx, cy = x + w / 2.0, y + d / 2.0
        msp.add_text(
            s_name,
            dxfattribs={"layer": "TEXT_AREAS", "height": 0.25},
        ).set_placement((cx, cy + 0.18), align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(
            f"{area:.2f} m²",
            dxfattribs={"layer": "TEXT_AREAS", "height": 0.20},
        ).set_placement((cx, cy - 0.18), align=TextEntityAlignment.MIDDLE_CENTER)

        # --- في PNG: تعبئة الغرفة وجدرانها ---
        fill_color = get_space_color(s_type, s_name)
        room_patch = patches.Rectangle(
            (x, y), w, d, linewidth=2.0, edgecolor="#1C2833", facecolor=fill_color, zorder=3
        )
        ax.add_patch(room_patch)

        font_size = 7.5 if min(w, d) < 2.0 else 9.0
        ax.text(
            cx,
            cy,
            f"{s_name}\n({area:.1f} m²)",
            ha="center",
            va="center",
            fontsize=font_size,
            fontweight="bold",
            color="#1C2833",
            zorder=6,
        )

        # --- رسم الأبواب (DOORS) ---
        for door in space.get("doors", []):
            wall = door.get("wall", "south")
            offset = float(door.get("offset", 0.2))
            d_w = float(door.get("width", 0.9))

            p1, p2, wall_dir = _compute_opening_coords(x, y, w, d, wall, offset, d_w)
            hinge, leaf_end, start_ang, end_ang = _get_door_swing_geometry(p1, p2, wall_dir, d_w)

            # DXF: خط درفة الباب + قوس الفتح
            msp.add_line(hinge, leaf_end, dxfattribs={"layer": "DOORS", "lineweight": 15})
            msp.add_arc(
                center=hinge,
                radius=d_w,
                start_angle=start_ang,
                end_angle=end_ang,
                dxfattribs={"layer": "DOORS", "lineweight": 13},
            )

            # PNG: مسح الجدار مكان الباب + رسم الدرفة وقوس الفتح
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color=fill_color, linewidth=3.2, zorder=4)
            ax.plot([hinge[0], leaf_end[0]], [hinge[1], leaf_end[1]], color="#1F618D", linewidth=1.6, zorder=5)
            arc_patch = patches.Arc(
                hinge,
                width=2 * d_w,
                height=2 * d_w,
                angle=0,
                theta1=start_ang,
                theta2=end_ang,
                color="#1F618D",
                linewidth=1.1,
                linestyle="-",
                zorder=5,
            )
            ax.add_patch(arc_patch)

        # --- رسم النوافذ (WINDOWS) ---
        for win in space.get("windows", []):
            wall = win.get("wall", "south")
            offset = float(win.get("offset", 0.5))
            w_w = float(win.get("width", 1.2))

            p1, p2, wall_dir = _compute_opening_coords(x, y, w, d, wall, offset, w_w)

            # DXF: رمز النافذة (خط مزدوج)
            thickness = 0.14
            if wall_dir in {"south", "north"}:
                msp.add_line((p1[0], p1[1] - thickness / 2), (p2[0], p2[1] - thickness / 2), dxfattribs={"layer": "WINDOWS"})
                msp.add_line((p1[0], p1[1] + thickness / 2), (p2[0], p2[1] + thickness / 2), dxfattribs={"layer": "WINDOWS"})
                msp.add_line(p1, p2, dxfattribs={"layer": "WINDOWS"})
            else:
                msp.add_line((p1[0] - thickness / 2, p1[1]), (p2[0] - thickness / 2, p2[1]), dxfattribs={"layer": "WINDOWS"})
