# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import streamlit as st

from db import get_measurements, list_subjects, upsert_measurement
from utils.balance import motor_metrics, total_index, balance_metrics
from utils.constants import STAGES
from utils.kinematics import coupled_motion_pct, peak_velocity, sparc, symmetry_index, tracking_rmse
from utils.ui import setup, subject_picker

setup("التحكم والتوازن الحركي للرقبة", "🎯")
st.caption("اختبارات: دقة التتبع بالرأس، سلاسة الحركة (SPARC)، الحركة المرافقة، وتماثل السرعة. المصدر: IMU أو الكاميرا (CSV).")

subjects = list_subjects()
if not subjects:
    st.warning("أضف لاعبين أولًا.")
    st.stop()
c1, c2 = st.columns(2)
with c1:
    subj = subject_picker(subjects)
stage = c2.selectbox("نقطة القياس", STAGES)

st.subheader("1) تحليل ملف حركة (CSV)")
st.markdown("الأعمدة: `angle` (زاوية الرأس بالدرجة) — اختياريًا `target` (مسار الهدف) و`secondary` (محور ثانوي). "
            "حدّد تردد العينة.")
up = st.file_uploader("ملف الحركة", type=["csv"])
fs = st.number_input("تردد العينة (Hz)", 10, 1000, 100)
res = {}
if up is not None:
    df = pd.read_csv(up)
    if "angle" not in df.columns:
        st.error("يلزم عمود angle.")
    else:
        a = df["angle"].to_numpy(float)
        res["peak_velocity"] = peak_velocity(a, fs)
        res["sparc"] = sparc(a, fs)
        if "target" in df.columns:
            res["rmse"] = tracking_rmse(a, df["target"])
        if "secondary" in df.columns:
            res["coupled"] = coupled_motion_pct(a, df["secondary"].to_numpy(float))
        st.line_chart(df[[c for c in ("angle", "target") if c in df.columns]])
        st.dataframe(pd.DataFrame([res]).round(2), use_container_width=True)
        st.session_state["motor_res"] = res

def _clean(v, lo, hi):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return float(min(hi, max(lo, v)))


res = st.session_state.get("motor_res", {})
st.subheader("2) تماثل السرعة يمين/يسار")
c = st.columns(2)
vr = c[0].number_input("أقصى سرعة يمين (°/ث)", 0.0, 500.0, float(_clean(res.get("peak_velocity", 0.0), 0.0, 500.0) or 0.0))
vl = c[1].number_input("أقصى سرعة يسار (°/ث)", 0.0, 500.0, 0.0)
vasym = symmetry_index(vr, vl) if vr and vl else None
if vasym is not None:
    st.write(f"عدم التماثل: **{vasym:.1f}%**")

st.subheader("3) القيم المراد حفظها")
ex = {m["test_key"]: m["value"] for m in get_measurements(subject_id=subj["id"], stage=stage)}
c = st.columns(4)
rmse = c[0].number_input("RMSE (°)", 0.0, 40.0, _clean(res.get("rmse", ex.get("mc_track_rmse")), 0.0, 40.0))
sp = c[1].number_input("SPARC", -15.0, 0.0, _clean(res.get("sparc", ex.get("mc_sparc")), -15.0, 0.0))
cp = c[2].number_input("الحركة المرافقة (%)", 0.0, 100.0, _clean(res.get("coupled", ex.get("mc_coupled")), 0.0, 100.0))
va = c[3].number_input("عدم تماثل السرعة (%)", 0.0, 100.0, _clean(vasym if vasym is not None else ex.get("mc_vel_asym"), 0.0, 100.0))
vals = {"mc_track_rmse": rmse, "mc_sparc": sp, "mc_coupled": cp, "mc_vel_asym": va}
comp, midx = motor_metrics({k: v for k, v in vals.items() if v is not None})
if comp:
    st.bar_chart(pd.Series(comp, name="الدرجة (0–100)"))
    st.metric("مؤشر التحكم الحركي", f"{midx:.0f} / 100")
if st.button("💾 حفظ القياسات والمؤشرات"):
    for k, v in vals.items():
        if v is not None:
            upsert_measurement(subj["id"], stage, k, float(v))
    if midx is not None:
        upsert_measurement(subj["id"], stage, "nmci_motor", float(midx))
        meas = {m["test_key"]: m["value"] for m in get_measurements(subject_id=subj["id"], stage=stage)}
        _, _, bidx = balance_metrics(meas)
        tot = total_index(bidx, midx)
        if tot is not None:
            upsert_measurement(subj["id"], stage, "nmci_total", float(tot))
    st.success("حُفظ. المؤشر الكلي NMCI = متوسط مؤشر التوازن ومؤشر التحكم المتوفرين.")
