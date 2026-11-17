import os
import json
import streamlit as st
from groq import Groq

from skills.validator import validate_architectural_plan
from skills.cad_generator import generate_cad_and_preview


# إعداد الصفحة
st.set_page_config(
    page_title="ArchiTN AI | وكيل الهندسة المعمارية بتونس",
    page_icon="📐",
    layout="wide",
)


def read_file_if_exists(filepath: str) -> str:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def load_full_system_instructions() -> str:
    """
    يجمع تعليمات الوكيل مع القوانين العمرانية والمعايير المعمارية التونسية.
    """
    prompt_candidates = [
        "agent/system_prompt.md",
        "agent/system_prompt.py",
        "system_prompt.py",
        "system_prompt.md",
    ]
    base_prompt = ""
    for path in prompt_candidates:
        content = read_file_if_exists(path)
        if content.strip():
            base_prompt = content
            break

    urban_rules = read_file_if_exists("rules/tunisia_urban_rules.md")
    arch_standards = read_file_if_exists("rules/architectural_standards.md")

    combined = base_prompt
    if urban_rules:
        combined += f"\n\n---\n# المرجع 1: قوانين التهيئة العمرانية التونسية\n{urban_rules}"
    if arch_standards:
        combined += f"\n\n---\n# المرجع 2: المعايير المعمارية المعتمدة\n{arch_standards}"

    return combined


def call_architect_agent(client: Groq, messages: list, model_name: str = "openai/gpt-oss-120b") -> dict:
    """
    يتصل بـ Groq API ويضمن استرجاع مخرجات JSON منظمة.
    """
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.15,
    )
    raw_content = response.choices[0].message.content
    return json.loads(raw_content)


# ==========================================
# واجهة المستخدم (Streamlit UI)
# ==========================================
st.title("📐 ArchiTN AI — مساعد المكتب الفني الذكي (تونس)")
st.markdown(
    "توليد مخططات معمارية أولية (**Esquisse**) مطابقة لقوانين التهيئة العمرانية التونسية، "
    "مدققة حسابياً وجاهزة للتصدير بصيغة **AutoCAD (.dxf)**."
)

# الشريط الجانبي للإعدادات
with st.sidebar:
    st.header("⚙️ إعدادات المحرك الهندسي")
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        api_key = st.text_input("مفتاح Groq API Key", type="password")

    model_choice = st.selectbox(
        "النموذج المعتمد",
        options=["openai/gpt-oss-120b", "llama-3.3-70b-versatile"],
        index=0,
    )
    max_retries = st.slider("محاولات التصحيح الهندسي الذاتي", min_value=1, max_value=4, value=3)

    st.divider()
    st.info(
        "**تنبيه مهني:** المخرجات هي مسودة أولية (Esquisse) خاضعة للمراجعة "
        "والمصادقة القانونية من طرف مهندس معماري مرسم بعمادة المهندسين المعماريين بالبلاد التونسية."
    )

# تهيئة سجل المحادثة
if "messages" not in st.session_state:
    st.session_state.messages = []

# عرض المحادثات السابقة
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# مربع إدخال طلب المهندس
user_input = st.chat_input(
    "صف قطعة الأرض والبرنامج الوظيفي (مثال: أرض 15م × 20م، بناء منفرد COS 0.4، ارتداد أمامي 4م وجانبي 3م، صالون + مطبخ + غرفتي نوم + حمام)..."
)

if user_input:
    if not api_key:
        st.error("يرجى توفير مفتاح GROQ_API_KEY في متغيرات البيئة على Render أو إدخاله في الشريط الجانبي.")
        st.stop()

    # إضافة رسالة المستخدم
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    client = Groq(api_key=api_key)
    system_instructions = load_full_system_instructions()

    api_messages = [{"role": "system", "content": system_instructions}]
    for m in st.session_state.messages:
        api_messages.append({"role": m["role"], "content": m["content"]})

    with st.chat_message("assistant"):
        with st.spinner("جاري التحليل العمراني وحساب الارتدادات وتوزيع الفضاءات..."):
            try:
                plan_data = call_architect_agent(client, api_messages, model_name=model_choice)

                # الحالة 1: نقص في البيانات (قاعدة عدم الافتراض)
                if plan_data.get("status") == "NEED_INFO":
                    msg_text = plan_data.get("message", "يرجى استكمال المعطيات الهندسية التالية:")
                    missing = plan_data.get("missing_fields", [])
                    reply = f"### ⚠️ معطيات ناقصة (قاعدة عدم الافتراض)\n{msg_text}\n\n"
                    for item in missing:
                        reply += f"- **{item}**\n"

                    st.warning(reply)
                    st.session_state.messages.append({"role": "assistant", "content": reply})

                # الحالة 2: جاهز للتدقيق الهندسي والرسم
                elif plan_data.get("status") == "READY":
                    is_valid, errors, audit_report = validate_architectural_plan(plan_data)

                    # حلقة التصحيح الذاتي إذا وجد المدقق أخطاء هندسية
                    attempt = 0
                    while not is_valid and attempt < max_retries:
                        attempt += 1
                        st.info(f"🔄 جاري التصحيح الهندسي التلقائي (المحاولة {attempt}/{max_retries}) لمعالجة {len(errors)} ملاحظة...")
                        correction_prompt = (
                            "فشل المخطط في الفحص البرمجي الهندسي (Validator) بسبب الأخطاء التالية:\n"
                            + "\n".join([f"- {err}" for err in errors])
                            + "\n\nأعد توليد كامل الـ JSON بصيغة صالحة مع تصحيح الإحداثيات والأبعاد والفتحات لتجاوز جميع هذه الأخطاء بدقة."
                        )
                        api_messages.append({"role": "assistant", "content": json.dumps(plan_data, ensure_ascii=False)})
                        api_messages.append({"role": "user", "content": correction_prompt})

                        plan_data = call_architect_agent(client, api_messages, model_name=model_choice)
                        is_valid, errors, audit_report = validate_architectural_plan(plan_data)

                    # بعد انتهاء الفحص (أو محاولات التصحيح)
                    if not is_valid:
                        st.error("❌ تعذر استيفاء جميع الشروط الهندسية تلقائياً. الملاحظات المتبقية:")
                        for err in errors:
                            st.write(f"- {err}")
                        with st.expander("عرض بيانات JSON الخام للمراجعة"):
                            st.json(plan_data)
                    else:
                        # توليد ملف AutoCAD وصورة المعاينة
                        dxf_path, png_path = generate_cad_and_preview(plan_data)

                        st.success("✅ تم اجتياز الفحص الهندسي (0 تداخل، احترام الارتدادات و COS، وتأمين التهوية والممرات).")

                        col1, col2 = st.columns([3, 2])

                        with col1:
                            st.subheader("🖼️ المخطط المعماري الأولي (Esquisse)")
                            st.image(png_path, use_container_width=True)

                            with open(dxf_path, "rb") as dxf_file:
                                st.download_button(
                                    label="📥 تحميل ملف AutoCAD (.dxf) بطبقات منظمة",
                                    data=dxf_file,
                                    file_name="ArchiTN_Esquisse.dxf",
                                    mime="application/dxf",
                                    type="primary",
                                )

                        with col2:
                            st.subheader("📊 بطاقة الفحص الفني (Audit)")
                            m1, m2 = st.columns(2)
                            m1.metric("مساحة الأرض", f"{audit_report.get('terrain_area_m2', 0)} م²")
                            m2.metric("المساحة المبنية", f"{audit_report.get('actual_built_area_m2', 0)} م²")

                            max_fp = audit_report.get("max_allowed_footprint_m2", 0)
                            if max_fp > 0:
                                st.metric("الحد الأقصى المسموح (COS)", f"{max_fp} م²")

                            st.markdown("**جدول الفضاءات والمساحات:**")
                            spaces_table = [
                                {
                                    "الفضاء": s.get("name"),
                                    "الأبعاد (م)": f"{s.get('width')} × {s.get('depth')}",
                                    "المساحة (م²)": s.get("area"),
                                }
                                for s in plan_data.get("spaces", [])
                            ]
                            st.table(spaces_table)

                            notes = plan_data.get("engineering_report", {}).get("compliance_notes", [])
                            if notes:
                                st.markdown("**ملاحظات المطابقة العمرانية:**")
                                for note in notes:
                                    st.write(f"✔️ {note}")

                        summary_msg = f"تم توليد المخطط المعماري بمساحة مبنية **{audit_report.get('actual_built_area_m2')} م²** واجتياز التدقيق الهندسي بنجاح."
                        st.session_state.messages.append({"role": "assistant", "content": summary_msg})

                else:
                    st.warning("استجابة غير متوقعة من الوكيل:")
                    st.json(plan_data)

            except Exception as e:
                st.error(f"حدث خطأ تقني أثناء المعالجة: {str(e)}")
