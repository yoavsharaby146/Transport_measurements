import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from scipy.constants import e, h, hbar, epsilon_0
import io

# --- Configuration ---
st.set_page_config(page_title="Physics Research Calculator", layout="wide")
st.title("Interactive Research Calculator")
st.markdown("Calculations for Single/Dual Gate Systems, Hall Effect, SdH, and Mobility.")

# Initialize session state for storing plots (Comparison Feature)
if 'stored_traces' not in st.session_state:
    st.session_state['stored_traces'] = []


def clear_traces():
    st.session_state['stored_traces'] = []


# --- Sidebar: Global Settings or Instructions ---
with st.sidebar:
    st.header("Plotting Controls")
    if st.button("Clear All Stored Traces"):
        clear_traces()
    st.info("To compare parameters: Generate a plot, click 'Save Trace', then change parameters and plot again.")

# --- Tabs ---
tab1, tab2, tab3, tab4 = st.tabs([
    "Single Gate System",
    "Dual Gate System",
    "Hall Effect & SdH",
    "Mobility & Magnetic Length"
])

# ==============================================================================
# TAB 1: SINGLE GATE SYSTEM
# ==============================================================================
with tab1:
    st.header("Single Gate Calculations")

    # --- Mode Selection ---
    sg_mode = st.radio(
        "Select Sweep Variable",
        ["Gate Voltage (Vg)", "Dielectric Thickness (d)"],
        horizontal=True,
        help="Choose 'Gate Voltage' to see how density changes with voltage. Choose 'Dielectric Thickness' to see how density changes with thickness for a fixed voltage."
    )

    # --- Display Formulas ---
    with st.expander("Show Formulas", expanded=True):
        st.markdown(r"""
        **Capacitance:** $$C_{geo} = \frac{\epsilon_r \epsilon_0}{d}$$

        **Carrier Density:** $$n = \frac{C_{geo} (V_g - V_{CNP})}{e}$$
        """)

    col1, col2 = st.columns(2)

    # --- LOGIC BRANCH: SWEEP VOLTAGE (Original) ---
    if sg_mode == "Gate Voltage (Vg)":
        with col1:
            st.subheader("Parameters")
            epsilon_r = st.number_input("Dielectric Constant (ϵr)", value=3.9, help="e.g., 3.9 for SiO2, 4-7 for hBN")
            d_nm = st.number_input("Dielectric Thickness (nm)", value=300.0)
            v_cnp = st.number_input("Charge Neutrality Point (CNP) [V]", value=0.0)

        with col2:
            st.subheader("Sweep Range")
            v_start = st.number_input("Start Gate Voltage (V)", value=-40.0)
            v_end = st.number_input("End Gate Voltage (V)", value=40.0)
            n_points = st.number_input("Number of Points", value=100, min_value=10, step=10)

        # Calculations
        d_m = d_nm * 1e-9
        C_geo = (epsilon_r * epsilon_0) / d_m

        V_g = np.linspace(v_start, v_end, int(n_points))
        V_eff = V_g - v_cnp

        # Density & Field
        n_dens_m2 = (C_geo * V_eff) / e
        n_dens_cm2 = n_dens_m2 / 1e4

        E_field_V_nm = V_eff / d_nm

        # Plot Selection specific to Voltage Sweep
        st.subheader("Plotting")
        plot_type = st.selectbox("Select Plot Type", [
            "Gate Voltage vs Carrier Density",
            "Gate Voltage vs Displacement Field (E-field)",
            "Carrier Density vs Displacement Field"
        ], key="sg_plot_v")

        # Assign X and Y based on selection
        if plot_type == "Gate Voltage vs Carrier Density":
            x_data, y_data = V_g, n_dens_cm2
            x_label, y_label = "Gate Voltage (V)", "Carrier Density (cm^-2)"
        elif plot_type == "Gate Voltage vs Displacement Field (E-field)":
            x_data, y_data = V_g, E_field_V_nm
            x_label, y_label = "Gate Voltage (V)", "Displacement Field (V/nm)"
        else:
            x_data, y_data = E_field_V_nm, n_dens_cm2
            x_label, y_label = "Displacement Field (V/nm)", "Carrier Density (cm^-2)"

        trace_label = f"d={d_nm}nm, k={epsilon_r}"
        current_trace_type = "SingleGate_Voltage"

        # --- LOGIC BRANCH: SWEEP THICKNESS (New) ---
    else:
        with col1:
            st.subheader("Fixed Parameters")
            epsilon_r = st.number_input("Dielectric Constant (ϵr)", value=3.9, key="eps_d_sweep")
            v_g_fixed = st.number_input("Fixed Gate Voltage (V)", value=10.0)
            v_cnp = st.number_input("Charge Neutrality Point (CNP) [V]", value=0.0, key="cnp_d_sweep")

        with col2:
            st.subheader("Thickness Sweep Range")
            d_start = st.number_input("Start Thickness (nm)", value=10.0)
            d_end = st.number_input("End Thickness (nm)", value=300.0)
            n_points = st.number_input("Number of Points", value=100, min_value=10, key="pts_d_sweep")

        # Calculations
        d_nm_arr = np.linspace(d_start, d_end, int(n_points))
        d_m_arr = d_nm_arr * 1e-9

        # C varies with d
        C_geo_arr = (epsilon_r * epsilon_0) / d_m_arr

        # V_eff is constant across the sweep (but depends on fixed Vg)
        V_eff = v_g_fixed - v_cnp

        # n varies because C varies
        n_dens_m2 = (C_geo_arr * V_eff) / e
        n_dens_cm2 = n_dens_m2 / 1e4

        st.subheader("Plotting")
        st.caption("Plotting Thickness vs Carrier Density")

        # Only one plot type for now in this mode
        x_data, y_data = d_nm_arr, n_dens_cm2
        x_label, y_label = "Dielectric Thickness (nm)", "Carrier Density (cm^-2)"
        plot_type = "Thickness vs Density"

        trace_label = f"Vg={v_g_fixed}V, k={epsilon_r}"
        current_trace_type = "SingleGate_Thickness"

    # --- UNIFIED PLOTTING LOGIC ---

    # 1. Generate Matplotlib Figure (Hidden, for download button only)
    fig, ax = plt.subplots()
    ax.plot(x_data, y_data, label="Current", linewidth=2, color='blue')
    for trace in st.session_state['stored_traces']:
        if trace.get('trace_type') == current_trace_type and trace.get('plot') == plot_type:
            ax.plot(trace['x'], trace['y'], linestyle='--', label=trace['label'])
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)

    # Scientific notation for Matplotlib
    if "Carrier Density" in y_label:
        ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
    if "Carrier Density" in x_label:
        ax.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))

    ax.legend()
    ax.grid(True, linestyle=':', alpha=0.6)

    # 2. Generate Interactive Plotly Figure (For display)
    fig_p = go.Figure()
    # Add current trace
    fig_p.add_trace(go.Scatter(
        x=x_data, y=y_data,
        mode='lines',
        name='Current',
        line=dict(color='blue', width=2)
    ))
    # Add stored traces
    for trace in st.session_state['stored_traces']:
        if trace.get('trace_type') == current_trace_type and trace.get('plot') == plot_type:
            fig_p.add_trace(go.Scatter(
                x=trace['x'], y=trace['y'],
                mode='lines',
                name=trace['label'],
                line=dict(dash='dash')
            ))

    fig_p.update_layout(
        xaxis_title=x_label,
        yaxis_title=y_label,
        hovermode="x unified",  # Shows values for all traces at that x-position
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )

    # Scientific notation for Plotly
    if "Carrier Density" in y_label:
        fig_p.update_layout(yaxis=dict(tickformat=".2e"))
    if "Carrier Density" in x_label:
        fig_p.update_layout(xaxis=dict(tickformat=".2e"))

    st.plotly_chart(fig_p, width=True)

    # --- EXPORT SECTION ---
    c_save, c_exp_img, c_exp_csv = st.columns([1, 1, 1])

    with c_save:
        if st.button("Save Trace for Comparison", key="save_sg"):
            st.session_state['stored_traces'].append({
                'type': 'SingleGate',  # General Category
                'trace_type': current_trace_type,  # Specific Sub-category (Voltage vs Thickness)
                'plot': plot_type,
                'x': x_data,
                'y': y_data,
                'label': trace_label
            })
            st.success("Trace saved! Change parameters to compare.")

    with c_exp_img:
        img_buf = io.BytesIO()
        fig.savefig(img_buf, format='png', dpi=300, bbox_inches='tight')
        st.download_button(
            label="Download Plot (PNG)",
            data=img_buf.getvalue(),
            file_name="single_gate_plot.png",
            mime="image/png"
        )

    with c_exp_csv:
        csv_buf = io.BytesIO()
        np.savetxt(csv_buf, np.column_stack((x_data, y_data)), delimiter=",", header=f"{x_label},{y_label}",
                   comments="")
        st.download_button(
            label="Download Data (CSV)",
            data=csv_buf.getvalue(),
            file_name="single_gate_data.csv",
            mime="text/csv"
        )

# ==============================================================================
# TAB 2: DUAL GATE SYSTEM
# ==============================================================================
with tab2:
    st.header("Dual Gate Calculations")

    # --- Mode Selection ---
    dg_mode = st.radio(
        "Select Calculation Mode",
        ["Sweep Gate Voltage", "Sweep Dielectric Thickness", "Inverse (Calculate Required Voltages)"],
        horizontal=True
    )

    # === BRANCH 1: VOLTAGE SWEEP ===
    if dg_mode == "Sweep Gate Voltage":
        with st.expander("Show Formulas", expanded=True):
            st.markdown(r"""
            **Total Carrier Density:** $$n_{tot} = n_{top} + n_{bot}$$
            **Displacement Field:** $$D = (D_{top} - D_{bot}) / 2$$
            """)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top Gate")
            dt_nm = st.number_input("Top Dielectric Thickness (nm)", value=30.0)
            kt = st.number_input("Top Dielectric Constant", value=4.0)
            v_cnp_t = st.number_input("Top Gate CNP (V)", value=0.0, key="cnp_top")
            vt_range = st.text_input("Top Gate Range (start, end)", "-10, 10")

        with c2:
            st.markdown("### Bottom Gate")
            db_nm = st.number_input("Bottom Dielectric Thickness (nm)", value=300.0)
            kb = st.number_input("Bottom Dielectric Constant", value=3.9)
            v_cnp_b = st.number_input("Bottom Gate CNP (V)", value=0.0, key="cnp_bot")
            vb_range = st.text_input("Bottom Gate Range (start, end)", "-40, 40")

        num_pts = st.number_input("Number of Points (Dual)", value=100)

        # Parse ranges
        try:
            vt_start, vt_end = map(float, vt_range.split(','))
            vb_start, vb_end = map(float, vb_range.split(','))
        except:
            st.error("Invalid range format. Use 'start, end' (e.g., -10, 10)")
            vt_start, vt_end, vb_start, vb_end = -10, 10, -40, 40

        st.subheader("Sweep Configuration")
        sweep_mode = st.radio("Sweep Type", ["Sweep Top Gate (Fixed Bottom)", "Sweep Bottom Gate (Fixed Top)"])

        if sweep_mode == "Sweep Top Gate (Fixed Bottom)":
            fixed_val = st.number_input("Fixed Bottom Gate Voltage (V)", value=0.0)
            x_g = np.linspace(vt_start, vt_end, int(num_pts))
            v_tg = x_g
            v_bg = np.full_like(x_g, fixed_val)
            x_label_dg = "Top Gate Voltage (V)"
        else:
            fixed_val = st.number_input("Fixed Top Gate Voltage (V)", value=0.0)
            x_g = np.linspace(vb_start, vb_end, int(num_pts))
            v_bg = x_g
            v_tg = np.full_like(x_g, fixed_val)
            x_label_dg = "Bottom Gate Voltage (V)"

        # --- Calculations ---
        Ct = (kt * epsilon_0) / (dt_nm * 1e-9)
        Cb = (kb * epsilon_0) / (db_nm * 1e-9)

        v_tg_eff = v_tg - v_cnp_t
        v_bg_eff = v_bg - v_cnp_b

        nt = (Ct * v_tg_eff) / e
        nb = (Cb * v_bg_eff) / e
        n_tot_cm2 = (nt + nb) / 1e4

        Dt = Ct * v_tg_eff
        Db = Cb * v_bg_eff
        D_field_val = (Dt - Db) / 2
        D_field_Vnm = (D_field_val / epsilon_0) / 1e9

        dg_plot_type = st.selectbox("Select Dual Gate Plot", [
            "Gate Voltage vs Carrier Density",
            "Gate Voltage vs Displacement Field",
            "Carrier Density vs Displacement Field"
        ])

        # Assign X/Y based on plot selection
        if dg_plot_type == "Gate Voltage vs Carrier Density":
            xd, yd = x_g, n_tot_cm2
            yl = "Total Carrier Density (cm^-2)"
        elif dg_plot_type == "Gate Voltage vs Displacement Field":
            xd, yd = x_g, D_field_Vnm
            yl = "Displacement Field (V/nm)"
        else:
            xd, yd = D_field_Vnm, n_tot_cm2
            x_label_dg = "Displacement Field (V/nm)"
            yl = "Total Carrier Density (cm^-2)"

        dg_trace_type = "DualGate_Voltage"
        dg_trace_label = f"Fixed V={fixed_val}V"

        # --- Plotting Call ---
        # Note: We group the unified plotting logic for Voltage/Thickness at the end of the tab,
        # but to keep the 'Inverse' mode logic separate (since it has 2 lines instead of 1),
        # we will render plots inside the blocks for Dual Gate.

        # 1. Matplotlib
        fig2, ax2 = plt.subplots()
        ax2.plot(xd, yd, 'r-', label="Current")
        for trace in st.session_state['stored_traces']:
            if trace.get('trace_type') == dg_trace_type and trace.get('plot') == dg_plot_type:
                ax2.plot(trace['x'], trace['y'], '--', label=trace['label'])
        ax2.set_xlabel(x_label_dg)
        ax2.set_ylabel(yl)
        if "Carrier Density" in yl: ax2.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
        if "Carrier Density" in x_label_dg: ax2.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))
        ax2.legend()
        ax2.grid(True, alpha=0.5)

        # 2. Plotly
        fig_p2 = go.Figure()
        fig_p2.add_trace(go.Scatter(x=xd, y=yd, mode='lines', name='Current', line=dict(color='red', width=2)))
        for trace in st.session_state['stored_traces']:
            if trace.get('trace_type') == dg_trace_type and trace.get('plot') == dg_plot_type:
                fig_p2.add_trace(
                    go.Scatter(x=trace['x'], y=trace['y'], mode='lines', name=trace['label'], line=dict(dash='dash')))
        fig_p2.update_layout(xaxis_title=x_label_dg, yaxis_title=yl, hovermode="x unified")
        if "Carrier Density" in yl: fig_p2.update_layout(yaxis=dict(tickformat=".2e"))
        if "Carrier Density" in x_label_dg: fig_p2.update_layout(xaxis=dict(tickformat=".2e"))
        st.plotly_chart(fig_p2, width=True)

        # Export
        c_save_dg, c_exp_img_dg, c_exp_csv_dg = st.columns([1, 1, 1])
        with c_save_dg:
            if st.button("Save Trace", key="save_dg"):
                st.session_state['stored_traces'].append(
                    {'type': 'DualGate', 'trace_type': dg_trace_type, 'plot': dg_plot_type, 'x': xd, 'y': yd,
                     'label': dg_trace_label})
                st.success("Saved.")
        with c_exp_img_dg:
            img_buf_dg = io.BytesIO()
            fig2.savefig(img_buf_dg, format='png', dpi=300, bbox_inches='tight')
            st.download_button("Download Plot (PNG)", img_buf_dg.getvalue(), "dual_gate_plot.png", "image/png",
                               key="dl_img_dg")
        with c_exp_csv_dg:
            csv_buf_dg = io.BytesIO()
            np.savetxt(csv_buf_dg, np.column_stack((xd, yd)), delimiter=",", header=f"{x_label_dg},{yl}", comments="")
            st.download_button("Download Data (CSV)", csv_buf_dg.getvalue(), "dual_gate_data.csv", "text/csv",
                               key="dl_csv_dg")

    # === BRANCH 2: THICKNESS SWEEP ===
    elif dg_mode == "Sweep Dielectric Thickness":
        dg_thick_target = st.radio("Target Dielectric",
                                   ["Sweep Top Thickness (Fixed Bottom)", "Sweep Bottom Thickness (Fixed Top)"])

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top Gate")
            kt = st.number_input("Top Dielectric Constant", value=4.0, key="kt_ts")
            v_cnp_t = st.number_input("Top Gate CNP (V)", value=0.0, key="cnp_top_ts")
            if "Top Thickness" in dg_thick_target:
                dt_range = st.text_input("Top Thickness Range (nm) [start, end]", "10, 100")
                v_tg_fixed = st.number_input("Fixed Top Gate Voltage (V)", value=10.0, key="vt_ts")
            else:
                dt_nm = st.number_input("Top Thickness (nm)", value=30.0, key="dt_ts")
                v_tg_fixed = st.number_input("Fixed Top Gate Voltage (V)", value=10.0, key="vt_ts")

        with c2:
            st.markdown("### Bottom Gate")
            kb = st.number_input("Bottom Dielectric Constant", value=3.9, key="kb_ts")
            v_cnp_b = st.number_input("Bottom Gate CNP (V)", value=0.0, key="cnp_bot_ts")
            if "Bottom Thickness" in dg_thick_target:
                db_range = st.text_input("Bottom Thickness Range (nm) [start, end]", "10, 300")
                v_bg_fixed = st.number_input("Fixed Bottom Gate Voltage (V)", value=0.0, key="vb_ts")
            else:
                db_nm = st.number_input("Bottom Thickness (nm)", value=300.0, key="db_ts")
                v_bg_fixed = st.number_input("Fixed Bottom Gate Voltage (V)", value=0.0, key="vb_ts")

        num_pts = st.number_input("Number of Points", value=100, key="pts_ts")

        # --- Calculations ---
        if "Top Thickness" in dg_thick_target:
            try:
                start, end = map(float, dt_range.split(','))
            except:
                start, end = 10.0, 100.0
            dt_nm_arr = np.linspace(start, end, int(num_pts))
            dt_m_arr = dt_nm_arr * 1e-9
            db_m = db_nm * 1e-9  # Fixed
            Ct = (kt * epsilon_0) / dt_m_arr
            Cb = (kb * epsilon_0) / db_m
            xd = dt_nm_arr
            x_label_dg = "Top Dielectric Thickness (nm)"
            dg_trace_label = f"Sweep Top d, Vg_top={v_tg_fixed}V"
        else:
            try:
                start, end = map(float, db_range.split(','))
            except:
                start, end = 10.0, 300.0
            db_nm_arr = np.linspace(start, end, int(num_pts))
            db_m_arr = db_nm_arr * 1e-9
            dt_m = dt_nm * 1e-9  # Fixed
            Ct = (kt * epsilon_0) / dt_m
            Cb = (kb * epsilon_0) / db_m_arr
            xd = db_nm_arr
            x_label_dg = "Bottom Dielectric Thickness (nm)"
            dg_trace_label = f"Sweep Bot d, Vg_bot={v_bg_fixed}V"

        v_tg_eff = v_tg_fixed - v_cnp_t
        v_bg_eff = v_bg_fixed - v_cnp_b
        nt = (Ct * v_tg_eff) / e
        nb = (Cb * v_bg_eff) / e
        n_tot_cm2 = (nt + nb) / 1e4
        Dt = Ct * v_tg_eff
        Db = Cb * v_bg_eff
        D_field_val = (Dt - Db) / 2
        D_field_Vnm = (D_field_val / epsilon_0) / 1e9

        dg_plot_type = st.selectbox("Select Plot", ["Thickness vs Carrier Density", "Thickness vs Displacement Field"],
                                    key="plot_sel_ts")
        if dg_plot_type == "Thickness vs Carrier Density":
            yd = n_tot_cm2
            yl = "Total Carrier Density (cm^-2)"
        else:
            yd = D_field_Vnm
            yl = "Displacement Field (V/nm)"
        dg_trace_type = "DualGate_Thickness"

        # Plotting & Export (Same logic repeated for this block)
        fig2, ax2 = plt.subplots()
        ax2.plot(xd, yd, 'r-', label="Current")
        for trace in st.session_state['stored_traces']:
            if trace.get('trace_type') == dg_trace_type and trace.get('plot') == dg_plot_type:
                ax2.plot(trace['x'], trace['y'], '--', label=trace['label'])
        ax2.set_xlabel(x_label_dg)
        ax2.set_ylabel(yl)
        if "Carrier Density" in yl: ax2.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
        if "Carrier Density" in x_label_dg: ax2.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))
        ax2.legend()
        ax2.grid(True, alpha=0.5)

        fig_p2 = go.Figure()
        fig_p2.add_trace(go.Scatter(x=xd, y=yd, mode='lines', name='Current', line=dict(color='red', width=2)))
        for trace in st.session_state['stored_traces']:
            if trace.get('trace_type') == dg_trace_type and trace.get('plot') == dg_plot_type:
                fig_p2.add_trace(
                    go.Scatter(x=trace['x'], y=trace['y'], mode='lines', name=trace['label'], line=dict(dash='dash')))
        fig_p2.update_layout(xaxis_title=x_label_dg, yaxis_title=yl, hovermode="x unified")
        if "Carrier Density" in yl: fig_p2.update_layout(yaxis=dict(tickformat=".2e"))
        st.plotly_chart(fig_p2, width=True)

        c_save_dg, c_exp_img_dg, c_exp_csv_dg = st.columns([1, 1, 1])
        with c_save_dg:
            if st.button("Save Trace", key="save_dg"):
                st.session_state['stored_traces'].append(
                    {'type': 'DualGate', 'trace_type': dg_trace_type, 'plot': dg_plot_type, 'x': xd, 'y': yd,
                     'label': dg_trace_label})
                st.success("Saved.")
        with c_exp_img_dg:
            img_buf_dg = io.BytesIO()
            fig2.savefig(img_buf_dg, format='png', dpi=300, bbox_inches='tight')
            st.download_button("Download Plot (PNG)", img_buf_dg.getvalue(), "dual_gate_plot.png", "image/png",
                               key="dl_img_dg")
        with c_exp_csv_dg:
            csv_buf_dg = io.BytesIO()
            np.savetxt(csv_buf_dg, np.column_stack((xd, yd)), delimiter=",", header=f"{x_label_dg},{yl}", comments="")
            st.download_button("Download Data (CSV)", csv_buf_dg.getvalue(), "dual_gate_data.csv", "text/csv",
                               key="dl_csv_dg")

    # ==========================================
    #     INVERSE MODE (New Feature)
    # ==========================================
    else:  # dg_mode == "Inverse (Calculate Required Voltages)"
        st.info("Calculate required Top and Bottom Gate Voltages to achieve specific n and D.")

        # --- Device Parameters (Needed for Inverse Calc) ---
        c_dev1, c_dev2 = st.columns(2)
        with c_dev1:
            st.markdown("### Top Gate")
            dt_nm = st.number_input("Top Dielectric Thickness (nm)", value=30.0, key="dt_inv")
            kt = st.number_input("Top Dielectric Constant", value=4.0, key="kt_inv")
            v_cnp_t = st.number_input("Top Gate CNP (V)", value=0.0, key="cnp_top_inv")

        with c_dev2:
            st.markdown("### Bottom Gate")
            db_nm = st.number_input("Bottom Dielectric Thickness (nm)", value=300.0, key="db_inv")
            kb = st.number_input("Bottom Dielectric Constant", value=3.9, key="kb_inv")
            v_cnp_b = st.number_input("Bottom Gate CNP (V)", value=0.0, key="cnp_bot_inv")

        # Capacitance Calc
        Ct = (kt * epsilon_0) / (dt_nm * 1e-9)
        Cb = (kb * epsilon_0) / (db_nm * 1e-9)

        with st.expander("Show Formulas", expanded=False):
            st.markdown(r"""
            We solve the system for $V_t$ and $V_b$:
            $$V_t = V_{CNP,t} + \frac{e \cdot n_{tot} + 2 D}{2 C_t}$$
            $$V_b = V_{CNP,b} + \frac{e \cdot n_{tot} - 2 D}{2 C_b}$$
            *(Note: Input D is converted to C/m² for calculation)*
            """)

        inv_mode = st.radio("Inverse Mode Type", ["Fixed D, Sweep n", "Fixed n, Sweep D"])
        n_pts_inv = st.number_input("Number of Points", value=100, key="pts_inv")

        # --- Logic for Inverse Calculation ---
        if inv_mode == "Fixed D, Sweep n":
            c_i1, c_i2 = st.columns(2)
            with c_i1:
                fixed_D_Vnm = st.number_input("Fixed Displacement Field (V/nm)", value=0.0)
            with c_i2:
                n_range = st.text_input("Carrier Density Range (cm⁻²)", "-5e12, 5e12")

            try:
                n_start, n_end = map(float, n_range.split(','))
            except:
                n_start, n_end = -5e12, 5e12

            # Create Sweep Arrays
            n_sweep_cm2 = np.linspace(n_start, n_end, int(n_pts_inv))
            n_sweep_m2 = n_sweep_cm2 * 1e4

            # Fixed D in SI (C/m^2)
            # D_SI = D(V/nm) * 1e9 (V/m) * eps0 (F/m) = C/m^2
            D_fixed_SI = fixed_D_Vnm * 1e9 * epsilon_0

            # Apply Arrays to Formulas
            # Vt = Vcnp + (e*n + 2D) / 2Ct
            Vt_calc = v_cnp_t + (e * n_sweep_m2 + 2 * D_fixed_SI) / (2 * Ct)
            Vb_calc = v_cnp_b + (e * n_sweep_m2 - 2 * D_fixed_SI) / (2 * Cb)

            x_plot = n_sweep_cm2
            xlabel_inv = "Carrier Density (cm^-2)"
            title_inv = f"Required Gate Voltages for Fixed D = {fixed_D_Vnm} V/nm"

        else:  # Fixed n, Sweep D
            c_i1, c_i2 = st.columns(2)
            with c_i1:
                fixed_n_cm2 = st.number_input("Fixed Carrier Density (cm⁻²)", value=1e12, format="%.2e")
            with c_i2:
                d_range = st.text_input("Displacement Field Range (V/nm)", "-0.5, 0.5")

            try:
                d_start, d_end = map(float, d_range.split(','))
            except:
                d_start, d_end = -0.5, 0.5

            # Create Sweep Arrays
            D_sweep_Vnm = np.linspace(d_start, d_end, int(n_pts_inv))
            D_sweep_SI = D_sweep_Vnm * 1e9 * epsilon_0

            # Fixed n in SI
            n_fixed_m2 = fixed_n_cm2 * 1e4

            # Apply Formulas
            Vt_calc = v_cnp_t + (e * n_fixed_m2 + 2 * D_sweep_SI) / (2 * Ct)
            Vb_calc = v_cnp_b + (e * n_fixed_m2 - 2 * D_sweep_SI) / (2 * Cb)

            x_plot = D_sweep_Vnm
            xlabel_inv = "Displacement Field (V/nm)"
            title_inv = f"Required Gate Voltages for Fixed n = {fixed_n_cm2:.2e} cm^-2"

        # --- Plotting Inverse Results ---

        # 1. Matplotlib (Download)
        fig_inv, ax_inv = plt.subplots()
        ax_inv.plot(x_plot, Vt_calc, label="Top Gate (Vt)", color='red')
        ax_inv.plot(x_plot, Vb_calc, label="Bottom Gate (Vb)", color='blue')
        ax_inv.set_xlabel(xlabel_inv)
        ax_inv.set_ylabel("Gate Voltage (V)")
        ax_inv.set_title(title_inv)
        if "Carrier Density" in xlabel_inv:
            ax_inv.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))
        ax_inv.legend()
        ax_inv.grid(True, linestyle=':', alpha=0.6)

        # 2. Interactive Plotly
        fig_p_inv = go.Figure()
        fig_p_inv.add_trace(go.Scatter(x=x_plot, y=Vt_calc, mode='lines', name='Top Gate (Vt)', line=dict(color='red')))
        fig_p_inv.add_trace(
            go.Scatter(x=x_plot, y=Vb_calc, mode='lines', name='Bottom Gate (Vb)', line=dict(color='blue')))
        fig_p_inv.update_layout(
            title=title_inv,
            xaxis_title=xlabel_inv,
            yaxis_title="Gate Voltage (V)",
            hovermode="x unified"
        )
        if "Carrier Density" in xlabel_inv:
            fig_p_inv.update_layout(xaxis=dict(tickformat=".2e"))

        st.plotly_chart(fig_p_inv, width=True)

        # --- Export Inverse Results ---
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            buf_inv = io.BytesIO()
            fig_inv.savefig(buf_inv, format='png', dpi=300, bbox_inches='tight')
            st.download_button(
                "Download Plot (PNG)",
                buf_inv.getvalue(),
                "inverse_gate_plot.png",
                "image/png"
            )

        with col_dl2:
            buf_csv_inv = io.BytesIO()
            # Headers: SweepVar, Vt, Vb
            headers = f"{xlabel_inv},Top Gate V,Bottom Gate V"
            data_stack = np.column_stack((x_plot, Vt_calc, Vb_calc))
            np.savetxt(buf_csv_inv, data_stack, delimiter=",", header=headers, comments="")
            st.download_button(
                "Download Data (CSV)",
                buf_csv_inv.getvalue(),
                "inverse_gate_data.csv",
                "text/csv",
                help="Columns: Sweep Variable, Top Gate V, Bottom Gate V"
            )

# ==============================================================================
# TAB 3: HALL EFFECT & SdH
# ==============================================================================
with tab3:
    st.header("Hall Effect & SdH Oscillations")

    c_hall, c_sdh = st.columns(2)

    with c_hall:
        st.subheader("Hall Effect Carrier Density")
        st.markdown(r"Formula: $n = \frac{1}{e R_H} = \frac{1}{e (dR_{xy}/dB)}$")
        delta_r = st.number_input("Change in Hall Resistance ΔRxy (Ω)", value=1400.0)
        delta_b = st.number_input("Change in Magnetic Field ΔB (T)", value=1.0)

        if delta_r != 0:
            hall_slope = delta_r / delta_b
            n_hall = 1 / (e * hall_slope)  # m^-2
            st.metric("Carrier Density (n)", f"{n_hall / 1e4:.3e} cm⁻²")
            st.markdown(f"**Calculated Slope:** {hall_slope:.2f} Ω/T")
        else:
            st.error("ΔR cannot be zero")

    with c_sdh:
        st.subheader("SdH Oscillations")
        st.markdown(r"Formula: $n = \frac{g e}{h \Delta(1/B)} = \frac{g e}{h} B_F$")
        bf = st.number_input("SdH Frequency B_F (Tesla) [or 1/Δ(1/B)]", value=10.0)
        # Changed from selectbox to number_input (integer only)
        g_factor = st.number_input(
            "Degeneracy Factor (g)",
            value=4,
            step=1,
            min_value=1,
            format="%d",
            help="Integer value (e.g., 2 for spin degeneracy, 4 for spin+valley)"
        )

        n_sdh = (g_factor * e * bf) / h
        st.metric("SdH Carrier Density", f"{n_sdh / 1e4:.3e} cm⁻²")

# ==============================================================================
# TAB 4: MOBILITY & MAGNETIC LENGTH
# ==============================================================================
with tab4:
    st.header("Mobility & Magnetic Length")

    c_mob, c_mag = st.columns(2)

    with c_mag:
        st.subheader("Magnetic Length (lB)")
        st.markdown(r"Formula: $l_B = \sqrt{\frac{\hbar}{eB}}$")
        b_field = st.number_input("Magnetic Field B (Tesla)", value=1.0)

        if b_field > 0:
            lb = np.sqrt(hbar / (e * b_field))
            st.metric("Magnetic Length", f"{lb * 1e9:.2f} nm")
        else:
            st.write("B must be > 0")

    with c_mob:
        st.subheader("Mobility (μ)")
        st.markdown(r"Formula: $\mu = \frac{\sigma}{n e} = \frac{1}{\rho n e}$")

        calc_mode = st.radio("Input Mode", ["Conductivity (σ)", "Resistivity (ρ)", "Resistance (R) & Geom"])

        n_input = st.number_input("Carrier Density n (cm⁻²)", value=1e12, format="%.2e")
        n_m2 = n_input * 1e4

        mobility = 0
        if calc_mode == "Conductivity (σ)":
            sigma = st.number_input("Conductivity σ (S or 1/Ω)", value=0.001, format="%.2e")
            mobility = sigma / (n_m2 * e)
        elif calc_mode == "Resistivity (ρ)":
            rho = st.number_input("Resistivity ρ (Ω)", value=1000.0)
            if rho > 0: mobility = 1 / (rho * n_m2 * e)
        else:
            r_val = st.number_input("Resistance R (Ω)", value=1000.0)
            l_w = st.number_input("Aspect Ratio (L/W)", value=1.0)
            rho_calc = r_val / l_w
            if rho_calc > 0: mobility = 1 / (rho_calc * n_m2 * e)

        st.metric("Mobility", f"{mobility * 1e4:.2f} cm²/Vs")
        # Note: mobility in SI is m^2/Vs. *1e4 to get cm^2/Vs