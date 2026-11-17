import math
from typing import Dict, List, Tuple, Any

EPSILON = 0.02  # هامش تسامح هندسي 2 سم لتجنب أخطاء التقريب العشري


def check_overlap(rect1: Dict[str, float], rect2: Dict[str, float]) -> bool:
    """
    يفحص ما إذا كان هناك تداخل حقيقي بين مستطيلين (غرفتين).
    التلامس عند الجدران المشتركة مسموح به ولا يُعد تداخلاً.
    """
    r1_x1, r1_y1 = rect1["x"], rect1["y"]
    r1_x2, r1_y2 = rect1["x"] + rect1["width"], rect1["y"] + rect1["depth"]

    r2_x1, r2_y1 = rect2["x"], rect2["y"]
    r2_x2, r2_y2 = rect2["x"] + rect2["width"], rect2["y"] + rect2["depth"]

    # إذا كان أحدهما يقع بالكامل يمين أو يسار أو أعلى أو أسفل الآخر، فلا يوجد تداخل
    if (
        r1_x2 <= r2_x1 + EPSILON
        or r2_x2 <= r1_x1 + EPSILON
        or r1_y2 <= r2_y1 + EPSILON
        or r2_y2 <= r1_y1 + EPSILON
    ):
        return False
    return True


def validate_architectural_plan(plan_data: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    الدالة الرئيسية لتدقيق المخطط المعماري المولد بصيغة JSON.
    تُرجع: (هل المخطط صالح؟, قائمة الأخطاء الهندسية, ملخص الحسابات الدقيقة)
    """
    errors: List[str] = []
    report: Dict[str, Any] = {}

    if not isinstance(plan_data, dict):
        return False, ["مخرجات الوكيل ليست بصيغة JSON صالحة."], report

    status = plan_data.get("status")
    if status == "NEED_INFO":
        return True, [], {"status": "NEED_INFO"}

    if status != "READY":
        return False, [f"حالة المخطط غير معروفة: {status}"], report

    # 1. التحقق من وجود الأقسام الأساسية
    required_keys = ["terrain", "setbacks", "buildable_zone", "spaces"]
    for key in required_keys:
        if key not in plan_data or not plan_data[key]:
            errors.append(f"نقص في البيانات الأساسية للمخطط: الحقل '{key}' مفقود.")

    if errors:
        return False, errors, report

    terrain = plan_data["terrain"]
    setbacks = plan_data["setbacks"]
    b_zone = plan_data["buildable_zone"]
    spaces = plan_data["spaces"]
    eng_report = plan_data.get("engineering_report", {})

    # 2. التحقق من صحة حسابات الأرض ومنطقة البناء (Setbacks)
    t_width = float(terrain.get("width", 0))
    t_depth = float(terrain.get("depth", 0))
    if t_width <= 0 or t_depth <= 0:
        errors.append("أبعاد قطعة الأرض يجب أن تكون أكبر من الصفر.")
        return False, errors, report

    expected_x_min = float(setbacks.get("left", 0))
    expected_y_min = float(setbacks.get("front", 0))
    expected_x_max = t_width - float(setbacks.get("right", 0))
    expected_y_max = t_depth - float(setbacks.get("rear", 0))

    if expected_x_max <= expected_x_min or expected_y_max <= expected_y_min:
        errors.append("قيم الارتدادات (Setbacks) أكبر من أبعاد قطعة الأرض ولا تترك مساحة صالحة للبناء.")
        return False, errors, report

    # اعتماد القيم المحسوبة رياضياً لضمان الدقة
    x_min, y_min = expected_x_min, expected_y_min
    x_max, y_max = expected_x_max, expected_y_max

    # 3. فحص كل فضاء (غرفة / ممر) على حدة
    total_calculated_area = 0.0
    has_corridor = False
    habitable_types = {"living", "bedroom", "kitchen", "salon", "chambre", "cuisine"}

    for idx, space in enumerate(spaces):
        s_name = space.get("name", f"Space_{idx+1}")
        s_type = str(space.get("type", "")).lower()
        x = float(space.get("x", 0))
        y = float(space.get("y", 0))
        w = float(space.get("width", 0))
        d = float(space.get("depth", 0))

        if w <= 0.5 or d <= 0.5:
            errors.append(f"الفضاء '{s_name}' أبعاده غير منطقية معمارياً ({w}م × {d}م).")
            continue

        # فحص عدم الخروج عن منطقة البناء المسموحة (احترام الارتدادات)
        if (
            x < x_min - EPSILON
            or y < y_min - EPSILON
            or (x + w) > x_max + EPSILON
            or (y + d) > y_max + EPSILON
        ):
            errors.append(
                f"مخالفة ارتداد: الفضاء '{s_name}' يتجاوز حدود منطقة البناء المسموحة "
                f"[{x_min}..{x_max}, {y_min}..{y_max}]."
            )

        # حساب المساحة الفعلية وتصحيحها في البيانات
        calc_area = round(w * d, 2)
        space["area"] = calc_area
        total_calculated_area += calc_area

        # فحص الممرات وعرضها
        if s_type in {"corridor", "degagement", "dégagement", "hall"} or "dégagement" in s_name.lower() or "couloir" in s_name.lower():
            has_corridor = True
            min_dim = min(w, d)
            if min_dim < 1.0 - EPSILON:
                errors.append(
                    f"مخالفة معمارية: عرض الممر '{s_name}' هو {min_dim:.2f}م، ويجب ألا يقل عن 1.00م (يفضل 1.10م-1.20م)."
                )

        # فحص الفتحات (الأبواب والنوافذ)
        doors = space.get("doors", [])
        windows = space.get("windows", [])

        if not doors and s_type not in {"corridor", "degagement", "dégagement"}:
            errors.append(f"خطأ وظيفي: الفضاء '{s_name}' لا يحتوي على أي باب (معزول تماماً).")

        # التحقق من أن الأبواب تقع ضمن طول الجدار الفعلي
        for door in doors:
            wall = door.get("wall", "")
            offset = float(door.get("offset", 0))
            d_width = float(door.get("width", 0.9))
            wall_len = w if wall in {"north", "south"} else d
            if offset < -EPSILON or (offset + d_width) > wall_len + EPSILON:
                errors.append(
                    f"خطأ في تموضع الباب داخل '{s_name}': الباب على الجدار '{wall}' يخرج عن حدود الجدار ({wall_len}م)."
                )

        # فحص التهوية الطبيعية للغرف الرئيسية وفق القانون التونسي
        if s_type in habitable_types and len(windows) == 0:
            errors.append(
                f"مخالفة صحية/قانونية: الفضاء '{s_name}' ({s_type}) لا يحتوي على أي نافذة للتهوية والإنارة الطبيعية."
            )

        for win in windows:
            wall = win.get("wall", "")
            offset = float(win.get("offset", 0))
            w_width = float(win.get("width", 1.2))
            wall_len = w if wall in {"north", "south"} else d
            if offset < -EPSILON or (offset + w_width) > wall_len + EPSILON:
                errors.append(
                    f"خطأ في تموضع النافذة داخل '{s_name}': النافذة على الجدار '{wall}' تخرج عن حدود الجدار ({wall_len}م)."
                )

    # 4. فحص التداخل بين جميع الفضاءات (Overlap Check)
    for i in range(len(spaces)):
        for j in range(i + 1, len(spaces)):
            s1 = spaces[i]
            s2 = spaces[j]
            if check_overlap(s1, s2):
                errors.append(
                    f"تداخل هندسي مرفوض (Overlap) بين '{s1.get('name')}' و '{s2.get('name')}'."
                )

    # 5. فحص وجود ممر رابط إذا كان المخطط يحتوي على أكثر من فضاءين
    if len(spaces) > 2 and not has_corridor:
        errors.append(
            "مخالفة توزيع وظيفي: المخطط يحتوي على عدة غرف بدون ممر رابط (Dégagement / Couloir) لضمان الخصوصية والحركة."
        )

    # 6. التحقق من معامل إشغال الأرض (COS)
    terrain_area = round(t_width * t_depth, 2)
    cos_applied = float(eng_report.get("cos_applied", 0))
    max_allowed = float(eng_report.get("max_allowed_footprint_m2", 0))

    if max_allowed <= 0 and cos_applied > 0:
        max_allowed = round(terrain_area * cos_applied, 2)

    if max_allowed > 0 and total_calculated_area > max_allowed + 0.5:
        errors.append(
            f"مخالفة عمرانية (COS): المساحة المبنية الفعلية ({total_calculated_area:.2f} م²) "
            f"تتجاوز المساحة القصوى المسموحة ({max_allowed:.2f} م²)."
        )

    # إعداد تقرير التدقيق النهائي
    report = {
        "terrain_area_m2": terrain_area,
        "actual_built_area_m2": round(total_calculated_area, 2),
        "max_allowed_footprint_m2": max_allowed,
        "spaces_count": len(spaces),
        "has_corridor": has_corridor,
        "verified_buildable_zone": {
            "x_min": x_min,
            "y_min": y_min,
            "x_max": x_max,
            "y_max": y_max,
        },
    }

    is_valid = len(errors) == 0
    return is_valid, errors, report
