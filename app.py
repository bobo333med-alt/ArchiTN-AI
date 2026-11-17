import streamlit as st
import json
import os
from google import genai
from skills.cad_generator import generate_dxf_and_preview

st.set_page_config(page_title="ArchiTN AI - Assistant Architectural", layout="wide")
st.title("🏛️ ArchiTN AI - وكيل التصميم المعماري الذكي (تونس)")
st.markdown("توليد مخططات أولية **(Esquisse)** مطابقة لتراتيب التهيئة العمرانية التونسية وقابلة للتصدير بصيغة **AutoCAD (.dxf)**.")

# قراءة ملفات القواعد والبرومبت
def load_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

system_instruction = (
    load_file("agent/system_prompt.md") + "\n\n" +
    load_file("rules/tunisia_urban_rules.md") + "\n\n" +
    load_file("rules/architectural_standards.md")
)

# الشريط الجانبي لإدخال بيانات الأرض
with st.sidebar:
    st.header("📐 معطيات قطعة الأرض")
    land_width = st.number_input("عرض الأرض (الواجهة بالمتر)", min_value=8.0, max_value=100.0, value=15.0, step=0.5)
    land_length = st.number_input("عمق الأرض (الطول بالمتر)", min_value=10.0, max_value=100.0, value=20.0, step=0.5)
    typology = st.selectbox("نوع التقسيم المطلوب", ["S+1 (غرفة وصالة)", "S+2 (غرفتين وصالة)", "S+3 (ثلاث غرف وصالة)"])
    facades = st.selectbox("عدد الواجهات على الطريق", ["واجهة واحدة (1 Façade)", "واجهتين (2 Façades - زاوية)"])
    extra_notes = st.text_area("ملاحظات إضافية للمهندس", placeholder="مثال: أريد مطبخاً مفتوحاً على الصالة...")
    
    generate_btn = st.button("🚀 توليد المخطط الهندسي", type="primary", use_container_width=True)

if generate_btn:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ يرجى إضافة مفتاح GEMINI_API_KEY في إعدادات Environment Variables على Render.")
    else:
        with st.spinner("جاري دراسة الارتدادات القانونية وتصميم المخطط..."):
            client = genai.Client(api_key=api_key)
            user_prompt = f"""
            قم بتصميم مخطط طابق أرضي بالمعطيات التالية:
            - عرض الأرض: {land_width} متر
            - طول (عمق) الأرض: {land_length} متر
            - التقسيم المطلوب: {typology}
            - عدد الواجهات: {facades}
            - ملاحظات إضافية: {extra_notes}
            """
            
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=user_prompt,
                config={
                    "system_instruction": system_instruction,
                    "response_mime_type": "application/json"
                }
            )
            
            try:
                plan_data = json.loads(response.text)
                if plan_data.get("status") != "SUCCESS":
                    st.warning(f"توقف الوكيل لطلب توضيح: {plan_data}")
                else:
                    col1, col2 = st.columns([2, 1])
                    dxf_bytes, img_stream = generate_dxf_and_preview(plan_data, land_width, land_length)
                    
                    with col1:
                        st.subheader("🗺️ المخطط الهندسي الأولي")
                        st.image(img_stream, use_container_width=True)
                        st.download_button(
                            label="📥 تحميل ملف AutoCAD (.dxf)",
                            data=dxf_bytes,
                            file_name="ArchiTN_Plan.dxf",
                            mime="application/dxf",
                            type="primary"
                        )
                    
                    with col2:
                        st.subheader("📊 البطاقة الفنية (الفحص القانوني)")
                        rep = plan_data["report"]
                        st.metric("المساحة الإجمالية للأرض", f"{rep['total_land_area']} m²")
                        st.metric("المساحة المغطاة (Emprise)", f"{rep['buildable_area']} m²")
                        st.metric("نسبة البناء (COS)", f"{rep['cos_percentage']}%")
                        st.info(rep["compliance_notes"])
                        
            except Exception as e:
                st.error(f"حدث خطأ في معالجة المخطط: {e}")
