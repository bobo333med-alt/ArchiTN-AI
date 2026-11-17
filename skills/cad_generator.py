import os
import matplotlib
matplotlib.use('Agg')  # ضروري جداً للعمل على سيرفرات Render بدون شاشة
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import ezdxf

def generate_cad(plan_data):
    """
    تستقبل بيانات المخطط من الوكيل وتولد:
    1. صورة معاينة احترافية بصيغة PNG
    2. ملف هندسي حقيقي بصيغة AutoCAD (.dxf) بطبقات منظمة
    """
    rooms = plan_data.get("rooms", [])
    report = plan_data.get("report", {})
    
    # مسارات حفظ الملفات المؤقتة على السيرفر
    output_dir = "/tmp" if os.path.exists("/tmp") else "."
    png_path = os.path.join(output_dir, "ArchiTN_Esquisse.png")
    dxf_path = os.path.join(output_dir, "ArchiTN_Esquisse.dxf")

    # ==========================================
    # أولاً: توليد ملف AutoCAD الحقيقي (.dxf)
    # ==========================================
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # إنشاء طبقات هندسية قياسية (Layers)
    doc.layers.add(name="MURS_CLOISONS", color=7)      # أبيض/أسود للجدران
    doc.layers.add(name="TEXTES_SURFACES", color=3)    # أخضر للأسماء والمساحات
    doc.layers.add(name="COTATIONS", color=1)          # أحمر للأبعاد

    wall_thickness = 0.20  # سمك الجدار بالمتر (20 سم)

    for room in rooms:
        name = room.get("name", "Room")
        x = float(room.get("x", 0))
        y = float(room.get("y", 0))
        w = float(room.get("width", 0))
        h = float(room.get("height", 0))
        area = round(w * h, 2)

        # رسم المستطيل الخارجي والداخلي للغرفة (تمثيل الجدران)
        outer_pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        msp.add_lwpolyline(outer_pts, dxfattribs={"layer": "MURS_CLOISONS"})

        inner_pts = [
            (x + wall_thickness / 2, y + wall_thickness / 2),
            (x + w - wall_thickness / 2, y + wall_thickness / 2),
            (x + w - wall_thickness / 2, y + h - wall_thickness / 2),
            (x + wall_thickness / 2, y + h - wall_thickness / 2),
            (x + wall_thickness / 2, y + wall_thickness / 2),
        ]
        msp.add_lwpolyline(inner_pts, dxfattribs={"layer": "MURS_CLOISONS"})

        # كتابة اسم الغرفة والمساحة والأبعاد في مركز الغرفة
        cx = x + w / 2
        cy = y + h / 2
        msp.add_text(
            f"{name}",
            dxfattribs={"layer": "TEXTES_SURFACES", "height": 0.25}
        ).set_placement((cx, cy + 0.25), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

        msp.add_text(
            f"{area} m2 ({w}x{h}m)",
            dxfattribs={"layer": "COTATIONS", "height": 0.18}
        ).set_placement((cx, cy - 0.20), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)

    doc.saveas(dxf_path)

    # ==========================================
    # ثانياً: توليد صورة المعاينة (PNG)
    # ==========================================
    fig, ax = plt.subplots(figsize=(9, 9))
    
    # ألوان هندسية هادئة لتمييز الفضاءات
    colors = ["#E8F4F8", "#FDF2E9", "#EAFAF1", "#F5EEF8", "#FEF9E7", "#EBF5FB"]

    min_x, min_y = 0, 0
    max_x, max_y = 10, 10

    for idx, room in enumerate(rooms):
        name = room.get("name", "Room")
        x = float(room.get("x", 0))
        y = float(room.get("y", 0))
        w = float(room.get("width", 0))
        h = float(room.get("height", 0))
        area = round(w * h, 2)

        max_x = max(max_x, x + w)
        max_y = max(max_y, y + h)

        # رسم الغرفة مع جدار سميك
        rect = patches.Rectangle(
            (x, y), w, h,
            linewidth=3.5,
            edgecolor="#1C2833",
            facecolor=colors[idx % len(colors)]
        )
        ax.add_patch(rect)

        # إضافة النص داخل الغرفة
        ax.text(
            x + w / 2, y + h / 2,
            f"{name}\n{area} m²\n({w}m × {h}m)",
            ha="center", va="center",
            fontsize=10, fontweight="bold", color="#17202A"
        )

    ax.set_xlim(min_x - 1.5, max_x + 1.5)
    ax.set_ylim(min_y - 1.5, max_y + 1.5)
    ax.set_aspect("equal")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_xlabel("العرض (متر)")
    ax.set_ylabel("العمق (متر)")
    
    cos_val = report.get("cos_percentage", "-")
    build_area = report.get("buildable_area", "-")
    ax.set_title(f"ArchiTN AI - Esquisse Architecturale (COS: {cos_val}% | Surface: {build_area} m²)", fontsize=12, fontweight="bold", pad=15)

    plt.tight_layout()
    plt.savefig(png_path, dpi=200)
    plt.close(fig)

    return png_path, dxf_path
