from typing import Dict, List, Tuple, Any

def validate_plan(plan_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    يدقق في بيانات المخطط الهندسي المولدة من الوكيل قبل الرسم.
    Returns:
        (is_valid, errors, warnings)
    """
    errors: List[str] = []
    warnings: List[str] = []

    if plan_data.get("status") != "complete":
        return False, ["المخطط غير مكتمل أو ينتظر معطيات إضافية من المستخدم."], []

    urban = plan_data.get("urban_analysis", {})
    spaces = plan_data.get("spaces", [])
    openings = plan_data.get("openings", [])

    if not urban or not spaces:
        return False, ["بيانات التحليل العمراني أو الفضاءات مفقودة."], []

    t_width = float(urban.get("terrain_width", 0))
    t_depth = float(urban.get("terrain_depth", 0))
    max_footprint = float(urban.get("max_allowed_footprint", 0))
    setbacks = urban.get("setbacks", {})

    sb_left = float(setbacks.get("left", 0))
    sb_right = float(setbacks.get("right", 0))
    sb_front = float(setbacks.get("front", 0))
    sb_rear = float(setbacks.get("rear", 0))

    # حدود منطقة البناء المسموحة (Build Zone)
    min_x_allowed = sb_left
    max_x_allowed = t_width - sb_right
    min_y_allowed = sb_front
    max_y_allowed = t_depth - sb_rear

    if max_x_allowed <= min_x_allowed or max_y_allowed <= min_y_allowed:
        errors.append("الارتدادات القانونية أكبر من أبعاد قطعة الأرض، لا توجد مساحة قابلة للبناء.")
        return False, errors, warnings

    total_calculated_area = 0.0
    has_bedroom = False
    has_circulation = False
    space_map = {}

    # 1. فحص أبعاد ومواقع كل فضاء + احترام الارتدادات
    for sp in spaces:
        sp_id = sp.get("id", "Unknown")
        sp_name = sp.get("name", sp_id)
        sp_type = sp.get("type", "")
        x = float(sp.get("x", 0))
        y = float(sp.get("y", 0))
        w = float(sp.get("width", 0))
        d = float(sp.get("depth", 0))

        if w <= 0 or d <= 0:
            errors.append(f"الفضاء ({sp_name}) يحتوي على أبعاد غير صالحة (العرض={w}م، العمق={d}م).")
            continue

        space_map[sp_id] = sp
        calc_area = round(w * d, 2)
        total_calculated_area += calc_area

        if sp_type == "bedroom":
            has_bedroom = True
            if min(w, d) < 2.7:
                warnings.append(f"عرض غرفة النوم ({sp_name}) هو {min(w, d)}م، يفضل ألا يقل عن 2.80م حسب المعايير التونسية.")

        if sp_type == "circulation":
            has_circulation = True
            if min(w, d) < 1.0:
                errors.append(f"عرض الممر ({sp_name}) هو {min(w, d)}م، الحد الأدنى المسموح به هو 1.10م.")

        # التحقق من الارتدادات (مع هامش سماح عشري بسيط 0.05م)
        tol = 0.05
        if x < min_x_allowed - tol:
            errors.append(f"الفضاء ({sp_name}) يتجاوز الارتداد الأيسر (x={x}م < {min_x_allowed}م).")
        if (x + w) > max_x_allowed + tol:
            errors.append(f"الفضاء ({sp_name}) يتجاوز الارتداد الأيمن (x+w={round(x+w,2)}م > {max_x_allowed}م).")
        if y < min_y_allowed - tol:
            errors.append(f"الفضاء ({sp_name}) يتجاوز الارتداد الأمامي (y={y}م < {min_y_allowed}م).")
        if (y + d) > max_y_allowed + tol:
            errors.append(f"الفضاء ({sp_name}) يتجاوز الارتداد الخلفي (y+d={round(y+d,2)}م > {max_y_allowed}م).")

    # 2. فحص تداخل الغرف (Overlap Check)
    for i in range(len(spaces)):
        for j in range(i + 1, len(spaces)):
            s1 = spaces[i]
            s2 = spaces[j]
            x1, y1, w1, d1 = float(s1["x"]), float(s1["y"]), float(s1["width"]), float(s1["depth"])
            x2, y2, w2, d2 = float(s2["x"]), float(s2["y"]), float(s2["width"]), float(s2["depth"])

            # هامش 0.02م لتجنب أخطاء التقريب عند التلاصق
            overlap_x = (x1 + 0.02 < x2 + w2) and (x1 + w1 - 0.02 > x2)
            overlap_y = (y1 + 0.02 < y2 + d2) and (y1 + d1 - 0.02 > y2)

            if overlap_x and overlap_y:
                errors.append(f"تداخل هندسي (Overlap) بين ({s1['name']}) و ({s2['name']}).")

    # 3. فحص المساحة الإجمالية ومعامل استغلال الأرض (COS)
    if max_footprint > 0 and total_calculated_area > max_footprint + 0.5:
        errors.append(
            f"تجاوز المساحة القصوى المسموح ببنائها (COS): المساحة المحسوبة {round(total_calculated_area, 2)}م² تتجاوز المسموح {max_footprint}م²."
        )

    # 4. فحص وجود ممر توزيع (Dégagement)
    if has_bedroom and not has_circulation:
        errors.append("المخطط يحتوي على غرف نوم ولا يتضمن ممر توزيع (Dégagement / Couloir) لعزل الفضاءات الخاصة.")

    # 5. فحص الأبواب والنوافذ (Openings Check)
    spaces_with_doors = set()
    spaces_with_windows = set()

    for op in openings:
        op_type = op.get("type")
        sp_id = op.get("space_id")
        wall = op.get("wall")
        offset = float(op.get("offset", 0))
        op_w = float(op.get("width", 0))

        if sp_id not in space_map:
            warnings.append(f"فتحة ({op_type}) مرتبطة بمعرّف فضاء غير موجود ({sp_id}).")
            continue

        sp = space_map[sp_id]
        wall_len = float(sp["width"]) if wall in ["north", "south"] else float(sp["depth"])

        if offset < 0 or (offset + op_w) > wall_len + 0.05:
            errors.append(f"فتحة ({op_type}) في ({sp['name']}) تتجاوز طول الجدار ({wall}).")

        if op_type == "door":
            spaces_with_doors.add(sp_id)
        elif op_type == "window":
            spaces_with_windows.add(sp_id)
            # منع النوافذ على جدار الجار (الارتداد = 0)
            if wall == "west" and sb_left == 0 and abs(float(sp["x"]) - 0) < 0.05:
                errors.append(f"خطأ قانوني: نافذة في ({sp['name']}) على الجدار الغربي الملاصق للجار (Mitoyen).")
            if wall == "east" and sb_right == 0 and abs((float(sp["x"]) + float(sp["width"])) - t_width) < 0.05:
                errors.append(f"خطأ قانوني: نافذة في ({sp['name']}) على الجدار الشرقي الملاصق للجار (Mitoyen).")
            if wall == "north" and sb_rear == 0 and abs((float(sp["y"]) + float(sp["depth"])) - t_depth) < 0.05:
                errors.append(f"خطأ قانوني: نافذة في ({sp['name']}) على الجدار الشمالي الملاصق للجار (Mitoyen).")

    for sp_id, sp in space_map.items():
        if sp_id not in spaces_with_doors:
            warnings.append(f"الفضاء ({sp['name']}) لا يحتوي على باب محدد في البيانات.")
        if sp.get("type") in ["living", "bedroom", "kitchen"] and sp_id not in spaces_with_windows:
            errors.append(f"الفضاء ({sp['name']}) يفتقر إلى نافذة للتهوية والإنارة الطبيعية.")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings
