# -*- coding: utf-8 -*-
import pandas as pd
import streamlit as st

from db import get_measurements, list_subjects, upsert_measurement
from utils.balance import DEFAULT_CFG, balance_metrics
from utils.constants import DIRECTIONS, STAGES, TEST_NAMES
from utils.ui import setup, subject_picker

setup("اختبار التوازن العصبي العضلي", "⚖️")
st.caption("القوة (تماثل ونسبة) + التحمل + عتبة ألم الضغط + نشاط EMG أثناء CCFT ⟵ مؤشر توازن 0–100. "
           "الحدود مبدئية وقابلة للتعديل؛ حدّدها من مجموعة ضابطة سليمة قبل اعتمادها في الأطروحة.")

subjects = list_subjects()
if not subjects:
    st.warning("أضف لاعبين أولًا.")
    st.stop()
c1, c2 = st.columns(2)
with c1:
    subj = subject_picker(subjects)
stage = c2.selectbox("نقطة القياس", STAGES)
ex = {m["test_key"]: m["value"] for m in get_measurements(subject_id=subj["id"], stage=stage)}

FIELDS = ["str_" + d for d in DIRECTIONS] + ["end_flex", "end_ext", "ppt_trap_r", "ppt_trap_l", "ppt_scm_r", "ppt_scm_l"]
with st.form("bal_form"):
    cols = st.columns(3)
    vals = {}
    for i, k in enumerate(FIELDS):
        vals[k] = cols[i % 3].number_input(TEST_NAMES[k], min_value=0.0, value=ex.get(k), step=0.1, key=f"b_{k}_{subj['id']}_{stage}")
    st.caption("نشاط EMG (SCM والشقرافية أثناء CCFT) يُدخل من صفحة «القياسات».")
    if st.form_submit_button("💾 حفظ القياسات"):
        n = 0
        for k, v in vals.items():
            if v is not None:
                upsert_measurement(subj["id"], stage, k, float(v))
                n += 1
        st.success(f"حُفظ {n} قياسًا.")
        st.rerun()

with st.expander("⚙️ تعديل الحدود المرجعية"):
    cfg = {}
    c = st.columns(3)
    cfg["ref_strength_ratio"] = c[0].number_input("نسبة قوة المثنيات/الباسطات المرجعية", 0.1, 2.0, DEFAULT_CFG["ref_strength_ratio"], 0.01)
    cfg["ref_endurance_ratio"] = c[1].number_input("نسبة تحمل المثنيات/الباسطات المرجعية", 0.05, 2.0, DEFAULT_CFG["ref_endurance_ratio"], 0.01)
    cfg["sym_worst"] = c[2].number_input("عدم تماثل القوة الذي يعطي صفرًا (%)", 10.0, 80.0, DEFAULT_CFG["sym_worst"], 1.0)

meas = {m["test_key"]: m["value"] for m in get_measurements(subject_id=subj["id"], stage=stage)}
met, comp, idx = balance_metrics(meas, cfg)
st.subheader("النتائج")
if met:
    st.dataframe(pd.DataFrame({"المؤشر": list(met.keys()), "القيمة": [round(v, 2) for v in met.values()]}), use_container_width=True)
if comp:
    st.bar_chart(pd.Series(comp, name="الدرجة (0–100)"))
    st.metric("مؤشر التوازن العصبي العضلي", f"{idx:.0f} / 100")
    st.caption("المؤشر = متوسط المكوّنات المتوفرة فقط؛ كلما قلّت المكوّنات قلّت موثوقية المؤشر.")
    if st.button("حفظ المؤشر كمتغير (nmci_balance)"):
        upsert_measurement(subj["id"], stage, "nmci_balance", float(idx))
        st.success("حُفظ.")
else:
    st.info("أدخل القياسات لحساب المؤشر.")
