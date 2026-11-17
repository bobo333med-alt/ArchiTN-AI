import os
import math
from typing import Dict, Any, Tuple
import ezdxf
from ezdxf import enums
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def _get_opening_geometry(space: Dict[str, Any], opening: Dict[str, Any]) -> Dict[str, Any]:
    """يحسب الإحداثيات الهندسية للباب أو النافذة على الجدار المحدد."""
    x = float(space["x"])
    y = float(space["y"])
    w = float(space["width"])
    d = float(space["depth"])
    wall = opening.get("wall", "south")
    offset = float(opening.get("offset", 0.5))
    op_w = float(opening.get("width", 0.9))

    if wall == "south":
        x1, y1 = x + offset, y
        x2, y2 = x1 + op_w, y
        hinge = (x1, y1)
        start_angle, end_angle = 0, 90
    elif wall == "north":
        x1, y1 = x + offset, y + d
        x2, y2 = x1 + op_w, y + d
        hinge = (x1, y1)
        start_angle, end_angle = 270, 360
    elif wall == "west":
        x1, y1 = x, y + offset
        x2, y2 = x, y1 + op_w
        hinge = (x1, y1)
        start_angle, end_angle = 0, 90
    else:  # east
        x1, y1 = x + w, y + offset
        x2, y2 = x + w, y1 + op_w
        hinge = (x1, y1)
        start_angle, end_angle = 90, 180

    return {
        "p1": (x1, y1),
        "p2": (x2, y2),
        "hinge": hinge,
        "radius": op_w,
        "start_angle": start_angle,
        "end_angle": end_angle,
        "wall": wall,
    }


def generate_cad_and_preview(
    plan_data: Dict[str, Any],
    dxf_path: str = "output_plan.dxf",
    png_path: str = "output_preview.png",
) -> Tuple[str, str]:
    """
    يولّد ملف AutoCAD (.dxf) بطبقات منظمة وصورة معاينة (.png) للمخطط المعماري.
    """
    urban = plan_data.get("urban_analysis", {})
    spaces = plan_data.get("spaces", [])
    openings = plan_data.get("openings", [])

    t_width = float(urban.get("terrain_width", 15.0))
    t_depth = float(urban.get("terrain_depth", 20.0))
    setbacks = urban.get("setbacks", {})
    sb_left = float(setbacks.get("left", 0.0))
    sb_right = float(setbacks.get("right", 0.0))
    sb_front = float(setbacks.get("front", 0.0))
    sb_rear = float(setbacks.get("rear", 0.0))

    space_map = {sp["id"]: sp for sp in spaces if "id" in sp}

    # ==========================================
    # 1. إنشاء ملف AutoCAD (.dxf)
    # ==========================================
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # Meters
    msp = doc.modelspace()

    # إنشاء نوع خط متقطع للارتدادات
    if "DASHED" not in doc.linetypes:
        doc.linetypes.add("DASHED", pattern=[0.4, 0.2, -0.2])

    # تعريف الطبقات (Layers) بألوان AutoCAD القياسية
    layers_config = [
        ("TERRAIN", 8, "CONTINUOUS"),     # رمادي لحدود الأرض
        ("SETBACKS", 1, "DASHED"),        # أحمر متقطع للارتدادات
        ("WALLS", 7, "CONTINUOUS"),       # أبيض/أسود للجدران
        ("DOORS", 3, "CONTINUOUS"),       # أخضر للأبواب وأقواسها
        ("WINDOWS", 4, "CONTINUOUS"),     # سماوي (Cyan) للنوافذ
        ("TEXT_DIMS", 2, "CONTINUOUS"),   # أصفر للنصوص والمساحات
    ]
    for name, color, ltype in layers_config:
        if name not in doc.layers:
            doc.layers.add(name, color=color, linetype=ltype)

    # رسم حدود قطعة الأرض (Terrain)
    terrain_pts = [(0, 0), (t_width, 0), (t_width, t_depth), (0, t_depth), (0, 0)]
    msp.add_lwpolyline(terrain_pts, dxfattribs={"layer": "TERRAIN", "lineweight": 35})

    # رسم منطقة البناء المسموحة (Setbacks)
    bx1, by1 = sb_left, sb_front
    bx2, by2 = t_width - sb_right, t_depth - sb_rear
    if bx2 > bx1 and by2 > by1:
        setback_pts = [(bx1, by1), (bx2, by1), (bx2, by2), (bx1, by2), (bx1, by1)]
        msp.add_lwpolyline(setback_pts, dxfattribs={"layer": "SETBACKS"})

    # رسم الغرف والفضاءات
    for sp in spaces:
        x = float(sp["x"])
        y = float(sp["y"])
        w = float(sp["width"])
        d = float(sp["depth"])
        name = sp.get("name", "Espace")
        area = round(w * d, 2)

        room_pts = [(x, y), (x + w, y), (x + w, y + d), (x, y + d), (x, y)]
        msp.add_lwpolyline(room_pts, dxfattribs={"layer": "WALLS", "lineweight": 30})

        # إضافة اسم الغرفة والمساحة في المركز
        cx, cy = x + w / 2.0, y + d / 2.0
        label = f"{name}\\P{area} m²\\P({w}x{d}m)"
        mtext = msp.add_mtext(label, dxfattribs={"layer": "TEXT_DIMS", "char_height": 0.25})
        mtext.set_location((cx, cy), attachment_point=enums.MTextEntityAlignment.MIDDLE_CENTER)

    # رسم الأبواب والنوافذ في DXF
    for op in openings:
        sp_id = op.get("space_id")
        if sp_id not in space_map:
            continue
        geom = _get_opening_geometry(space_map[sp_id], op)
        p1, p2 = geom["p1"], geom["p2"]

        if op.get("type") == "door":
            # خط فتحة الباب + ضلفة الباب + قوس الفتح
            msp.add_line(p1, p2, dxfattribs={"layer": "DOORS"})
            hx, hy = geom["hinge"]
            r = geom["radius"]
            sa, ea = geom["start_angle"], geom["end_angle"]
            # رسم الضلفة المفتوحة
            rad_ea = math.radians(ea)
            leaf_end = (hx + r * math.cos(rad_ea), hy + r * math.sin(rad_ea))
            msp.add_line((hx, hy), leaf_end, dxfattribs={"layer": "DOORS"})
            msp.add_arc(center=(hx, hy), radius=r, start_angle=sa, end_angle=ea, dxfattribs={"layer": "DOORS"})

        elif op.get("type") == "window":
            # رسم خطين متوازيين يمثلان النافذة
            msp.add_line(p1, p2, dxfattribs={"layer": "WINDOWS", "lineweight": 25})
            if geom["wall"] in ["north", "south"]:
                msp.add_line((p1[0], p1[1] + 0.08), (p2[0], p2[1] + 0.08), dxfattribs={"layer": "WINDOWS"})
            else:
                msp.add_line((p1[0] + 0.08, p1[1]), (p2[0] + 0.08, p2[1]), dxfattribs={"layer": "WINDOWS"})

    doc.saveas(dxf_path)

    # ==========================================
    # 2. إنشاء صورة المعاينة (.png)
    # ==========================================
    fig, ax = plt.subplots(figsize=(10, 10), dpi=150)

    # رسم الأرض والارتدادات
    terrain_rect = patches.Rectangle(
        (0, 0), t_width, t_depth, linewidth=2.2, edgecolor="#333333", facecolor="#F4F6F7", label="Terrain"
    )
    ax.add_patch(terrain_rect)

    if bx2 > bx1 and by2 > by1:
        setback_rect = patches.Rectangle(
            (bx1, by1),
            bx2 - bx1,
            by2 - by1,
            linewidth=1.5,
            linestyle="--",
            edgecolor="#E74C3C",
            facecolor="none",
            label="Zone Constructible (Retraits)",
        )
        ax.add_patch(setback_rect)

    # ألوان هادئة لكل نوع فضاء
    type_colors = {
        "living": "#D6EAF8",
        "bedroom": "#FCF3CF",
        "kitchen": "#D5F5E3",
        "bathroom": "#EBDEF0",
        "circulation": "#EAEDED",
    }

    for sp in spaces:
        x = float(sp["x"])
        y = float(sp["y"])
        w = float(sp["width"])
        d = float(sp["depth"])
        sp_type = sp.get("type", "living")
        color = type_colors.get(sp_type, "#EBF5FB")

        rect = patches.Rectangle((x, y), w, d, linewidth=2.0, edgecolor="#1B2631", facecolor=color)
        ax.add_patch(rect)

        area = round(w * d, 2)
        font_size = 7 if sp_type == "circulation" else 8.5
        ax.text(
            x + w / 2.0,
            y + d / 2.0,
            f"{sp.get('name', '')}\n{area} m²\n({w}×{d}m)",
            ha="center",
            va="center",
            fontsize=font_size,
            fontweight="bold",
            color="#17202A",
        )

    # رسم الأبواب والنوافذ في صورة المعاينة
    for op in openings:
        sp_id = op.get("space_id")
        if sp_id not in space_map:
            continue
        geom = _get_opening_geometry(space_map[sp_id], op)
        p1, p2 = geom["p1"], geom["p2"]

        if op.get("type") == "door":
            # فتح الجدار بخط أبيض ثم رسم قوس الباب الأخضر
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="white", linewidth=3.2, zorder=4)
            hx, hy = geom["hinge"]
            r = geom["radius"]
            sa, ea = geom["start_angle"], geom["end_angle"]
            arc = patches.Arc(
                (hx, hy), width=2 * r, height=2 * r, angle=0, theta1=sa, theta2=ea, color="#1E8449", linewidth=1.3, zorder=5
            )
            ax.add_patch(arc)
            rad_ea = math.radians(ea)
            ax.plot([hx, hx + r * math.cos(rad_ea)], [hy, hy + r * math.sin(rad_ea)], color="#1E8449", linewidth=1.3, zorder=5)

        elif op.get("type") == "window":
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="#2980B9", linewidth=4.0, zorder=5)
            ax.plot([p1[0], p2[0]], [p1[1], p2[1]], color="white", linewidth=1.2, zorder=6)

    # ضبط الهوامش والعناوين
    margin = max(t_width, t_depth) * 0.1
    ax.set_xlim(-margin, t_width + margin)
    ax.set_ylim(-margin, t_depth + margin)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("Largeur X (m)")
    ax.set_ylabel("Profondeur Y (m)")
    ax.set_title(
        f"ArchiTN AI - Esquisse Architecturale ({t_width}m × {t_depth}m = {round(t_width * t_depth, 1)} m²)",
        fontsize=11,
        fontweight="bold",
        pad=12,
    )
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="upper right", fontsize=8)

    plt.tight_layout()
    plt.savefig(png_path, dpi=150)
    plt.close(fig)

    return dxf_path, png_path
