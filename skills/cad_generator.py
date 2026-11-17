import ezdxf
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import io

def generate_dxf_and_preview(plan_data, land_width, land_length):
    # 1. إنشاء ملف AutoCAD DXF
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    
    # إنشاء الطبقات الهندسية (Layers)
    doc.layers.add(name='TERRAIN', color=3)   # حدود الأرض بالأخضر
    doc.layers.add(name='MURS', color=7)      # الجدران بالأبيض/الأسود
    doc.layers.add(name='TEXTE', color=2)     # أسماء الغرف بالأصفر

    # رسم حدود قطعة الأرض
    msp.add_lwpolyline([(0, 0), (land_width, 0), (land_width, land_length), (0, land_length), (0, 0)], dxfattribs={'layer': 'TERRAIN'})

    # تجهيز صورة المعاينة للويب
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.add_patch(patches.Rectangle((0, 0), land_width, land_length, fill=False, edgecolor='green', linestyle='--', linewidth=2, label='Limite Terrain'))

    # رسم الغرف في ملف AutoCAD وعلى صورة المعاينة
    for room in plan_data.get("rooms", []):
        x, y = room["x"], room["y"]
        w, h = room["width"], room["height"]
        name = room["name"]

        # رسم الجدران في DXF
        points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y)]
        msp.add_lwpolyline(points, dxfattribs={'layer': 'MURS'})
        
        # إضافة اسم الغرفة والمساحة في DXF
        area = round(w * h, 1)
        msp.add_text(f"{name} ({area}m2)", dxfattribs={'layer': 'TEXTE', 'height': 0.35}).set_placement((x + 0.3, y + h / 2))

        # رسم الغرفة في صورة المعاينة
        ax.add_patch(patches.Rectangle((x, y), w, h, facecolor='#e8f0fe', edgecolor='#1a73e8', linewidth=1.5))
        ax.text(x + w/2, y + h/2, f"{name}\n{w}x{h}m\n({area}m²)", ha='center', va='center', fontsize=9, fontweight='bold')

    ax.set_xlim(-1, land_width + 1)
    ax.set_ylim(-1, land_length + 1)
    ax.set_aspect('equal')
    ax.set_title("ArchiTN AI - Avant-Projet Sommaire (Esquisse)")
    plt.grid(True, linestyle=':', alpha=0.5)

    # حفظ ملف DXF في الذاكرة
    dxf_stream = io.StringIO()
    doc.write(dxf_stream)
    dxf_bytes = dxf_stream.getvalue().encode('utf-8')

    # حفظ الصورة في الذاكرة
    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png', bbox_inches='tight')
    plt.close(fig)
    img_stream.seek(0)

    return dxf_bytes, img_stream
