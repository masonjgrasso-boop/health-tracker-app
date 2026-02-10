import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

from database import init_db, save_entry, get_all_entries, delete_entry, update_entry, export_csv, import_csv
from analysis import (
    calc_rolling_average,
    calc_weekly_weight_change,
    estimate_maintenance_calories,
    get_trend_direction,
    calc_calorie_vs_weight_data,
    linear_regression_line,
)

st.set_page_config(page_title="Health Tracker", layout="wide")

init_db()

# --- Dark mode toggle ---
dark_mode = st.sidebar.toggle("Dark Mode", value=False)
plotly_template = "plotly_dark" if dark_mode else "plotly_white"

# ==================== SIDEBAR ====================
st.sidebar.header("Log Entry")

with st.sidebar.form("entry_form", clear_on_submit=True):
    entry_date = st.date_input("Date", value=datetime.today())
    entry_weight = st.number_input("Weight (lbs)", min_value=50.0, max_value=1000.0, value=150.0, step=0.1)
    entry_calories = st.number_input("Calories", min_value=0.0, max_value=20000.0, value=0.0, step=50.0)
    cal_blank = st.checkbox("No calorie data for this day")
    submitted = st.form_submit_button("Save Entry")
    if submitted:
        cal_value = None if cal_blank else entry_calories
        save_entry(str(entry_date), entry_weight, cal_value)
        st.success(f"Saved entry for {entry_date}")

# --- Edit / Delete ---
with st.sidebar.expander("Edit / Delete Entry"):
    df_all = get_all_entries()
    if len(df_all) > 0:
        date_options = df_all["date"].dt.strftime("%Y-%m-%d").tolist()
        selected_date = st.selectbox("Select entry by date", date_options)
        row = df_all[df_all["date"].dt.strftime("%Y-%m-%d") == selected_date].iloc[0]
        edit_weight = st.number_input("Weight", value=float(row["weight_lbs"]), step=0.1, key="edit_w")
        current_cal = float(row["calories"]) if pd.notna(row["calories"]) else 0.0
        edit_calories = st.number_input("Calories", value=current_cal, step=50.0, key="edit_c")
        edit_no_cal = st.checkbox("No calorie data", value=pd.isna(row["calories"]), key="edit_nc")

        col_upd, col_del = st.columns(2)
        with col_upd:
            if st.button("Update"):
                cal_val = None if edit_no_cal else edit_calories
                update_entry(int(row["id"]), selected_date, edit_weight, cal_val)
                st.success("Updated!")
                st.rerun()
        with col_del:
            if st.button("Delete"):
                delete_entry(int(row["id"]))
                st.warning("Deleted.")
                st.rerun()
    else:
        st.info("No entries yet.")

# --- Timeframe filter ---
st.sidebar.subheader("Timeframe")
timeframe = st.sidebar.radio("Show:", ["Last 7 days", "Last 30 days", "Last 90 days", "All time"], index=3)

# --- Rolling average ---
st.sidebar.subheader("Rolling Average")
rolling_opt = st.sidebar.radio("Window:", ["Off", "7-day", "14-day"], index=0)

# --- CSV Export / Import ---
with st.sidebar.expander("CSV Export / Import"):
    df_export = get_all_entries()
    if len(df_export) > 0:
        csv_buf = io.StringIO()
        df_export.to_csv(csv_buf, index=False)
        st.download_button("Download CSV", csv_buf.getvalue(), file_name="health_data.csv", mime="text/csv")
    uploaded = st.file_uploader("Import CSV", type=["csv"])
    if uploaded is not None:
        import tempfile, os
        tmp = os.path.join(tempfile.gettempdir(), "health_import.csv")
        with open(tmp, "wb") as f:
            f.write(uploaded.read())
        import_csv(tmp)
        st.success("Imported!")
        st.rerun()

# ==================== MAIN PANEL ====================
st.title("Health Tracker")

# Reload data after any changes
df = get_all_entries()

# Apply timeframe filter
if len(df) > 0:
    now = pd.Timestamp.today()
    if timeframe == "Last 7 days":
        df = df[df["date"] >= now - timedelta(days=7)]
    elif timeframe == "Last 30 days":
        df = df[df["date"] >= now - timedelta(days=30)]
    elif timeframe == "Last 90 days":
        df = df[df["date"] >= now - timedelta(days=90)]

if len(df) < 2:
    st.info("Add at least 2 entries to see charts and analysis.")
    if len(df) == 1:
        st.dataframe(df[["date", "weight_lbs", "calories"]])
    st.stop()

# --- Metrics ---
weekly_change = calc_weekly_weight_change(df)
maintenance = estimate_maintenance_calories(df)
direction = get_trend_direction(weekly_change)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Est. Maintenance Calories", f"{maintenance} kcal/day" if maintenance else "—")
with col2:
    st.metric("Weight Trend", direction)
with col3:
    st.metric("Weekly Change", f"{weekly_change:+.2f} lbs/week" if weekly_change is not None else "—")

# --- Weight Trend Chart ---
st.subheader("Weight Trend")
fig_weight = go.Figure()
fig_weight.add_trace(go.Scatter(
    x=df["date"], y=df["weight_lbs"],
    mode="lines+markers", name="Weight",
    line=dict(color="#636EFA"),
))

if rolling_opt != "Off":
    window = 7 if rolling_opt == "7-day" else 14
    df["rolling_avg"] = calc_rolling_average(df, window)
    fig_weight.add_trace(go.Scatter(
        x=df["date"], y=df["rolling_avg"],
        mode="lines", name=f"{window}-day Avg",
        line=dict(color="#EF553B", dash="dash"),
    ))

fig_weight.update_layout(
    template=plotly_template,
    xaxis_title="Date",
    yaxis_title="Weight (lbs)",
    hovermode="x unified",
)
st.plotly_chart(fig_weight, use_container_width=True)

# --- Calorie vs Weight Change Scatter ---
scatter_data = calc_calorie_vs_weight_data(df)
if scatter_data is not None and len(scatter_data) >= 2:
    st.subheader("Calorie Intake vs Weight Change")
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=scatter_data["calories"], y=scatter_data["weight_change"],
        mode="markers", name="Weekly Data",
        marker=dict(size=10, color="#636EFA"),
    ))

    reg = linear_regression_line(scatter_data["calories"].values, scatter_data["weight_change"].values)
    if reg:
        slope, intercept = reg
        x_range = scatter_data["calories"]
        y_line = slope * x_range + intercept
        fig_scatter.add_trace(go.Scatter(
            x=x_range, y=y_line,
            mode="lines", name="Trend",
            line=dict(color="#EF553B", dash="dash"),
        ))

    fig_scatter.update_layout(
        template=plotly_template,
        xaxis_title="Avg Weekly Calories",
        yaxis_title="Weekly Weight Change (lbs)",
        hovermode="closest",
    )
    st.plotly_chart(fig_scatter, use_container_width=True)
else:
    st.info("Need 2+ weeks of data with calorie entries for the calorie vs weight chart.")
