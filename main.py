import streamlit as st

st.set_page_config(page_title="المستشار الذكي", page_icon="🎓")
st.title("🎓 النظام الخبير الذكي لإدارة التوتر والتخطيط")

name = st.text_input("ما هو اسمك الكريم؟")
if name:
    st.success(f"أهلاً بك يا {name}! النظام جاهز تماماً.")
    
    stress = st.slider("قيّم مستوى توترك من 1 إلى 10:", 1, 10, 5)
    
    if st.button("عرض التوجيهات"):
        if stress >= 8:
            st.error("مستوى التوتر مرتفع جداً! خذ استراحة وتنفس بعمق.")
        else:
            st.success("مستواك ممتاز، استمر في تنظيم وقتك!")