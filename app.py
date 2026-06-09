import streamlit as st

st.set_page_config(
    page_title="Design Audit Agent",
    layout="wide"
)

st.title("Design Audit Agent")

st.markdown("""
Analyze UI designs or compare design iterations.
Choose a mode below.
""")

col1, col2 = st.columns(2)

with col1:
    st.subheader(" Page Design Analysis")
    st.write("""
    Analyze a single UI screenshot.

    • Visual Hierarchy
    • Contrast
    • Spacing
    • Alignment
    • Consistency
    • user impact
    """)
    
    if st.button("Open Audit Mode"):
        st.switch_page("pages/audit_page.py")

with col2:
    st.subheader("Regression Analysisn")
    st.write("""
    Compare Before vs After UI versions.

    • Improvements
    • Regressions
    • Design Changes
    • Overall Verdict
    """)

    if st.button("Open Comparison Mode"):
        st.switch_page("pages/comparison_page.py")
        
