import os
import json
import uuid
import streamlit as st
from groq import Groq

from skills.validator import validate_plan
from skills.cad_generator import generate_cad_and_preview

st.set_page_config(page_title="ArchiTN AI - وكيل الهندسة المعمارية", page_icon="📐", layout="wide")
st.title("📐 ArchiTN AI — مساعد المكتب الفني الذكي (تونس)")
st.markdown("توليد المخططات المعمارية الأولية **(Esquisse)** وفق قوانين التهيئة العمرانية التونسية بصيغة **AutoCAD (.dxf)**.")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_text_file(relative_path: str) -> str:
    full_path = os.path.join(BASE_DIR, relative_path)
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


@st.cache_data
def build_system_prompt() -> str:
    urban_rules = load_text_file("rules/tunisia_urban_rules.md")
    arch_standards = load_text_file("rules/architectural_standards.md")
    base_prompt = load_text_file("agent/system_prompt.md")

    return f"""
{base_prompt}

=== قوانين التهيئة العمرانية التونسية (يجب احترامها بصرامة) ===
{urban_rules}

=== المعايير المعمارية والهندسية ===
{arch_standards}

=== تذكير صارم بصيغة المخرجات ===
يجب أن يكون ردك دائماً بصيغة JSON صالحة (Valid JSON) فقط دون أي نص خارجها.
- في حال نقص البيانات، أرجع `"status": "missing_info"` مع مصفوفة `"questions"`.
- في حال اكتمال البيانات، أرجع `"status": "complete"` مع الحقول: `"urban_analysis"`, `"spaces"`, `"openings"`, و `"technical_checklist"` بالضبط كما هو محدد في الهيكل أعلاه.
"""


def build_technical_report(plan_data: dict, warnings: list) -> str:
    """يبني بطاقة فحص فني احترافية لعرضها للمهندس المعماري."""
    urban = plan_data.get("urban_analysis", {})
    spaces = plan_data.get("spaces", [])
    checklist = plan_data.get("technical_checklist", {})
    setbacks = urban.get("setbacks", {})

    t_area = urban.get("terrain_area", 0)
    cos_max = urban.get("cos_max", 0)
    cuf_max = urban.get("cuf_max", 0)
    max_fp = urban.get("max_allowed_footprint", 0)
    act_fp = sum(round(float(s.get("width", 0)) * float(s.get("depth", 0)), 2) for s in spaces)

    report = f"""
#### 📊 التحليل العمراني (Données Urbanistiques)
- **مساحة قطعة الأرض:** `{t_area} م²` ({urban.get('terrain_width', 0)}م × {urban.get('terrain_depth', 0)}م)
- **المعاملات المسموحة:** `COS = {cos_max}` | `CUF = {cuf_max}`
- **المساحة القصوى المسموح ببنائها:** `{max_fp} م²`
- **المساحة المبنية الفعلية (Emprise au sol):** `{round(act_fp, 2)} م²`
- **الارتدادات (Retraits):** أمامي `{setbacks.get('front', 0)}م` | خلفي `{setbacks.get('rear', 0)}م` | يسار `{setbacks.get('left', 0)}م` | يمين `{setbacks.get('right', 0)}م`

#### 🏠 جدول الفضاءات (Tableau des Surfaces)

| المعرّف | الفضاء | النوع | الأبعاد (م) | المساحة (م²) |
| :--- | :--- | :--- | :---: | :---: |
"""
    for sp in spaces:
        w = float(sp.get("width", 0))
        d = float(sp.get("depth", 0))
        area = round(w * d, 2)
        report += f"| {sp.get('id', '-')} | {sp.get('name', '-')} | {sp.get('type', '-')} | {w} × {d} | **{area}** |\n"

    notes = checklist.get("notes", "")
    if notes:
        report += f"\n**📝 ملاحظات المكتب الفني:** {notes}\n"

    if warnings:
        report += "\n#### ⚠️ تنبيهات هندسية للمراجعة:\n"
        for w in warnings:
            report += f"- {w}\n"

    return report


api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    st.error("⚠️ مفتاح GROQ_API_KEY غير موجود! يرجى إضافته في إعدادات Environment Variables على منصة Render.")
    st.stop()

client = Groq(api_key=api_key)

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    st.info("النظام مزوّد بمدقق حسابي (Validator) لفحص التداخل، الارتدادات، والتهوية قبل الرسم.")
    if st.button("🔄 بدء مشروع جديد", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            st.markdown(msg.get("display_text", ""))
            if "png_path" in msg and os.path.exists(msg["png_path"]):
                st.image(msg["png_path"], caption="معاينة المخطط المعماري الأولي (Esquisse)")
            if "dxf_path" in msg and os.path.exists(msg["dxf_path"]):
                with open(msg["dxf_path"], "rb") as f:
                    st.download_button(
                        label="📥 تحميل ملف AutoCAD (.dxf)",
                        data=f,
                        file_name="ArchiTN_Esquisse.dxf",
                        mime="application/dxf",
                        key=f"dl_{msg.get('uid', uuid.uuid4())}",
                    )

if user_input := st.chat_input("صف مشروعك (مثال: أرض مستطيلة 15م × 20م في منطقة UB بتونس، مطلوب S+2 منفصل...)"):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    api_messages = [{"role": "system", "content": build_system_prompt()}]
    for m in st.session_state.messages:
        api_messages.append({"role": m["role"], "content": m.get("raw_content", m.get("content", ""))})

    with st.chat_message("assistant"):
        with st.spinner("جاري التحليل الهندسي وفحص قوانين التهيئة العمرانية..."):
            try:
                max_retries = 2
                attempt = 0
                data = {}
                raw_response = ""
                is_valid = False
                errors = []
                warnings = []

                while attempt <= max_retries:
                    completion = client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=api_messages,
                        temperature=0.1,
                        response_format={"type": "json_object"},
                    )
                    raw_response = completion.choices[0].message.content
                    data = json.loads(raw_response)

                    status = data.get("status", "unknown")
                    if status == "missing_info":
                        break

                    # استخراج بيانات المخطط سواء كانت مباشرة أو داخل plan_data
                    plan_payload = data.get("plan_data", data)
                    is_valid, errors, warnings = validate_plan(plan_payload)

                    if is_valid:
                        data = plan_payload
                        break

                    # حلقة التصحيح التلقائي: إرسال الأخطاء للوكيل لإصلاحها
                    attempt += 1
                    if attempt <= max_retries:
                        st.toast(f"🔄 جاري تصحيح {len(errors)} خطأ هندسي تلقائياً (محاولة {attempt}/{max_retries})...")
                        correction_prompt = (
                            "المخطط الذي ولدته يحتوي على الأخطاء الهندسية والقانونية التالية:\n"
                            + "\n".join(f"- {err}" for err in errors)
                            + "\n\nيرجى إعادة حساب الإحداثيات والأبعاد والفتحات بدقة لإصلاح جميع هذه الأخطاء وإرجاع JSON كامل وصالح."
                        )
                        api_messages.append({"role": "assistant", "content": raw_response})
                        api_messages.append({"role": "user", "content": correction_prompt})

                status = data.get("status", "unknown")
                uid = str(uuid.uuid4())[:8]
                assistant_record = {"role": "assistant", "raw_content": raw_response, "uid": uid}

                if status == "missing_info":
                    msg_text = "**يرجى توضيح البيانات التالية لإتمام الدراسة الهندسية دون افتراضات:**\n\n"
                    for q in data.get("questions", []):
                        msg_text += f"- {q}\n"
                    st.markdown(msg_text)
                    assistant_record["display_text"] = msg_text

                elif status in ["complete", "ready"]:
                    if not is_valid and errors:
                        st.warning("⚠️ تعذر حل بعض الملاحظات الهندسية تلقائياً، يرجى مراجعتها:")
                        for err in errors:
                            st.error(f"❌ {err}")

                    report_md = build_technical_report(data, warnings)
                    st.success("✅ اكتمل التحقق الهندسي وتم توليد المخطط!")
                    st.markdown(f"### 📋 بطاقة الفحص الفني:\n{report_md}")
                    assistant_record["display_text"] = f"✅ **اكتمل التحقق الهندسي:**\n\n{report_md}"

                    dxf_file = os.path.join(OUTPUT_DIR, f"ArchiTN_{uid}.dxf")
                    png_file = os.path.join(OUTPUT_DIR, f"ArchiTN_{uid}.png")

                    dxf_path, png_path = generate_cad_and_preview(data, dxf_path=dxf_file, png_path=png_file)
                    assistant_record["png_path"] = png_path
                    assistant_record["dxf_path"] = dxf_path

                    if os.path.exists(png_path):
                        st.image(png_path, caption="معاينة المخطط المعماري الأولي (Esquisse)")
                    if os.path.exists(dxf_path):
                        with open(dxf_path, "rb") as f:
                            st.download_button(
                                label="📥 تحميل ملف AutoCAD (.dxf)",
                                data=f,
                                file_name="ArchiTN_Esquisse.dxf",
                                mime="application/dxf",
                                key=f"dl_{uid}",
                            )
                else:
                    st.json(data)
                    assistant_record["display_text"] = f"```json\n{raw_response}\n```"

                st.session_state.messages.append(assistant_record)

            except Exception as e:
                st.error(f"حدث خطأ أثناء الاتصال أو معالجة البيانات: {str(e)}")
