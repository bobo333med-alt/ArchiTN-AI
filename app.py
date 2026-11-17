import os
import json
import streamlit as st
from groq import Groq

# استيراد دالة التوليد من مجلد skills
# تأكد أن اسم الدالة في ملف cad_generator.py مطابق لـ generate_cad
try:
    from skills.cad_generator import generate_cad
except ImportError:
    generate_cad = None

# 1. إعداد الصفحة والواجهة
st.set_page_config(page_title="ArchiTN AI - وكيل الهندسة المعمارية", page_icon="📐", layout="wide")
st.title("📐 ArchiTN AI — مساعد المكتب الفني الذكي (تونس)")
st.markdown("توليد المخططات المعمارية الأولية **(Esquisse)** وفق قوانين التهيئة العمرانية التونسية بصيغة **AutoCAD (.dxf)**.")

# 2. تحديد المسارات النسبية بشكل آمن لبيئة Linux / Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_text_file(relative_path):
    full_path = os.path.join(BASE_DIR, relative_path)
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# 3. تجميع التعليمات والقوانين في System Prompt واحد متكامل
@st.cache_data
def build_system_prompt():
    urban_rules = load_text_file("rules/tunisia_urban_rules.md")
    arch_standards = load_text_file("rules/architectural_standards.md")
    base_prompt = load_text_file("agent/system_prompt.md")
    
    full_prompt = f"""
{base_prompt}

=== قوانين التهيئة العمرانية التونسية (يجب احترامها بصرامة) ===
{urban_rules}

=== المعايير المعمارية والهندسية ===
{arch_standards}

=== تعليمات الإخراج الإلزامية ===
يجب أن يكون ردك دائماً بصيغة JSON صالحة (Valid JSON) فقط دون أي نص خارجها.
- إذا كانت هناك بيانات ناقصة (مثل أبعاد الأرض، المنطقة العمرانية UA/UB، عدد الغرف، الواجهات)، التزم بقاعدة "عدم الافتراض" وأرجع:
  {{"status": "missing_info", "message": "رسالة توضيحية قصيرة", "questions": ["السؤال الأول؟", "السؤال الثاني؟"]}}
- إذا اكتملت جميع البيانات، أرجع بيانات المخطط الهندسي:
  {{"status": "ready", "summary": "بطاقة الفحص الفني للمساحات ونسب COS/CUF", "plan_data": {{ ... }} }}
"""
    return full_prompt

# 4. تهيئة عميل Groq
api_key = os.environ.get("GROQ_API_KEY")
if not api_key:
    st.error("⚠️ مفتاح GROQ_API_KEY غير موجود! يرجى إضافته في إعدادات Environment Variables على منصة Render.")
    st.stop()

client = Groq(api_key=api_key)

# 5. إدارة سجل المحادثة (للحفاظ على الأسئلة والأجوبة بين الوكيل والمهندس)
if "messages" not in st.session_state:
    st.session_state.messages = []

# الشريط الجانبي (Sidebar) للتحكم وإعادة الضبط
with st.sidebar:
    st.header("⚙️ لوحة التحكم")
    if st.button("🔄 بدء مشروع جديد", use_container_width=True):
        st.session_state.messages = []
        st.rerun()
    st.info("يعتمد النظام على نموذج Llama 3.3 70B عبر Groq لضمان سرعة ودقة الحسابات الهندسية.")

# عرض سجل المحادثة السابق
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            # عرض رد الوكيل المنسق
            st.markdown(msg.get("display_text", ""))
            if "png_path" in msg and os.path.exists(msg["png_path"]):
                st.image(msg["png_path"], caption="معاينة المخطط المعماري الأولي (Esquisse)")
            if "dxf_path" in msg and os.path.exists(msg["dxf_path"]):
                with open(msg["dxf_path"], "rb") as f:
                    st.download_button(
                        label="📥 تحميل ملف AutoCAD (.dxf)",
                        data=f,
                        file_name="ArchiTN_Esquisse.dxf",
                        mime="application/dxf"
                    )

# 6. استقبال مدخلات المستخدم ومعالجتها
if user_input := st.chat_input("صف مشروعك (مثال: أرض مساحتها 300م² في منطقة UB بتونس، أريد فيلا طابق أرضي S+3)..."):
    # عرض رسالة المستخدم
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # تجهيز الرسائل لإرسالها إلى Groq
    api_messages = [{"role": "system", "content": build_system_prompt()}]
    for m in st.session_state.messages:
        api_messages.append({"role": m["role"], "content": m["raw_content"] if "raw_content" in m else m["content"]})

    # استدعاء Groq API
    with st.chat_message("assistant"):
        with st.spinner("جاري التحليل الهندسي وفحص قوانين التهيئة العمرانية..."):
            try:
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=api_messages,
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                raw_response = completion.choices[0].message.content
                data = json.loads(raw_response)

                status = data.get("status", "unknown")
                assistant_record = {"role": "assistant", "raw_content": raw_response}

                # الحالة الأولى: نقص في البيانات (تطبيق قاعدة عدم الافتراض)
                if status == "missing_info":
                    msg_text = f"**{data.get('message', 'يرجى توضيح البيانات التالية لإتمام الدراسة الهندسية:')}**\n\n"
                    for q in data.get("questions", []):
                        msg_text += f"- {q}\n"
                    st.markdown(msg_text)
                    assistant_record["display_text"] = msg_text

                # الحالة الثانية: البيانات مكتملة وجاهزة للرسم
                elif status == "ready":
                    summary = data.get("summary", "تم إعداد المخطط وفق المعايير المطلوبة.")
                    st.success("✅ اكتمل التحقق الهندسي وتم توليد المخطط!")
                    st.markdown(f"### 📋 بطاقة الفحص الفني:\n{summary}")
                    assistant_record["display_text"] = f"✅ **اكتمل التحقق الهندسي:**\n\n{summary}"

                    # استدعاء مهارة الرسم CAD Generator
                    if generate_cad:
                        plan_payload = data.get("plan_data", data)
                        # تمرير البيانات لدالة الرسم (يجب أن ترجع مسار PNG ومسار DXF)
                        result_paths = generate_cad(plan_payload)
                        
                        if isinstance(result_paths, tuple) and len(result_paths) == 2:
                            png_path, dxf_path = result_paths
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
                                        mime="application/dxf"
                                    )
                    else:
                        st.warning("⚠️ تم توليد البيانات الهندسية، ولكن دالة `generate_cad` غير مربوطة بعد في `skills/cad_generator.py`.")
                        st.json(data)

                else:
                    st.json(data)
                    assistant_record["display_text"] = f"```json\n{raw_response}\n```"

                st.session_state.messages.append(assistant_record)

            except Exception as e:
                st.error(f"حدث خطأ أثناء الاتصال أو معالجة البيانات: {str(e)}")
