import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.constants import e, h, hbar, epsilon_0, m_e
import io

# ==============================================================================
# CONFIGURATION
# ==============================================================================
st.set_page_config(page_title="Physics Research Calculator", layout="wide")
st.title("Interactive Research Calculator")
st.markdown("Calculations for Single/Dual Gate Systems, Hall Effect, SdH, and Transport Properties.")

# ==============================================================================
# CONSTANTS & PRESETS
# ==============================================================================
MATERIAL_PRESETS = {
    "Custom": {},
    "SiO₂ (Silicon Dioxide)": {"epsilon_r": 3.9, "d_nm": 285.0},
    "hBN (Hexagonal Boron Nitride)": {"epsilon_r": 4.5, "d_nm": 40.0},
    "Al₂O₃ (Alumina)": {"epsilon_r": 9.0, "d_nm": 30.0},
    "HfO₂ (Hafnium Dioxide)": {"epsilon_r": 25.0, "d_nm": 10.0},
    "PMMA": {"epsilon_r": 3.5, "d_nm": 50.0},
}

EFFECTIVE_MASS_PRESETS = {
    "Custom": {"m_star_m_e": 0.1},
    "MoS₂ (Electron)": {"m_star_m_e": 0.47},
    "MoS₂ (Hole)": {"m_star_m_e": 0.56},
    "WSe₂ (Electron)": {"m_star_m_e": 0.35},
    "WSe₂ (Hole)": {"m_star_m_e": 0.45},
    "GaAs 2DEG": {"m_star_m_e": 0.067},
    "Si (Electron)": {"m_star_m_e": 0.19},
    "Si (Hole)": {"m_star_m_e": 0.49},
    "Graphene (Dirac)": {"m_star_m_e": 0, "v_F": 1e6},
}


# ==============================================================================
# SESSION STATE
# ==============================================================================
if 'stored_traces' not in st.session_state:
    st.session_state['stored_traces'] = []


def clear_traces():
    st.session_state['stored_traces'] = []


# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================
def apply_preset(preset_key, eps_key, d_key):
    """Callback: updates session state when a material preset is selected."""
    preset_name = st.session_state[preset_key]
    if preset_name != "Custom" and preset_name in MATERIAL_PRESETS:
        preset = MATERIAL_PRESETS[preset_name]
        st.session_state[eps_key] = preset["epsilon_r"]
        st.session_state[d_key] = preset["d_nm"]


def render_plot_with_export(x_data, y_data, x_label, y_label,
                            trace_type, plot_type, trace_label,
                            save_key, img_filename="plot.png", csv_filename="data.csv",
                            line_color='blue'):
    """
    Renders a Plotly chart (interactive) + Matplotlib chart (for download),
    plus Save Trace / Download PNG / Download CSV buttons.
    """
    # --- Matplotlib figure (for PNG download) ---
    fig, ax = plt.subplots()
    ax.plot(x_data, y_data, label="Current", linewidth=2, color=line_color)
    for trace in st.session_state['stored_traces']:
        if trace.get('trace_type') == trace_type and trace.get('plot') == plot_type:
            ax.plot(trace['x'], trace['y'], linestyle='--', label=trace['label'])
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    if "Carrier Density" in y_label:
        ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
    if "Carrier Density" in x_label:
        ax.ticklabel_format(axis='x', style='sci', scilimits=(0, 0))
    ax.legend()
    ax.grid(True, linestyle=':', alpha=0.6)

    # --- Plotly figure (interactive display) ---
    fig_p = go.Figure()
    fig_p.add_trace(go.Scatter(
        x=x_data, y=y_data, mode='lines', name='Current',
        line=dict(color=line_color, width=2)
    ))
    for trace in st.session_state['stored_traces']:
        if trace.get('trace_type') == trace_type and trace.get('plot') == plot_type:
            fig_p.add_trace(go.Scatter(
                x=trace['x'], y=trace['y'], mode='lines',
                name=trace['label'], line=dict(dash='dash')
            ))
    fig_p.update_layout(
        xaxis_title=x_label, yaxis_title=y_label,
        hovermode="x unified",
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
    )
    if "Carrier Density" in y_label:
        fig_p.update_layout(yaxis=dict(tickformat=".2e"))
    if "Carrier Density" in x_label:
        fig_p.update_layout(xaxis=dict(tickformat=".2e"))

    st.plotly_chart(fig_p, width="stretch")

    # --- Export buttons ---
    c_save, c_img, c_csv = st.columns([1, 1, 1])
    with c_save:
        if st.button("💾 Save Trace", key=save_key):
            st.session_state['stored_traces'].append({
                'type': trace_type.split('_')[0],
                'trace_type': trace_type,
                'plot': plot_type,
                'x': x_data, 'y': y_data,
                'label': trace_label
            })
            st.success("Trace saved! Change parameters to compare.")
    with c_img:
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
        st.download_button("🖼️ Download PNG", buf.getvalue(),
                           img_filename, "image/png", key=f"img_{save_key}")
    with c_csv:
        buf = io.StringIO()
        buf.write(f"{x_label},{y_label}\n")
        np.savetxt(buf, np.column_stack((x_data, y_data)), delimiter=",")
        st.download_button("📄 Download CSV", buf.getvalue().encode('utf-8'),
                           csv_filename, "text/csv", key=f"csv_{save_key}")

    plt.close(fig)  # Clean up


def validate_positive(value, name):
    """Returns True if value > 0, shows error otherwise."""
    if value <= 0:
        st.error(f"⚠️ {name} must be positive (got {value}).")
        return False
    return True


# ==============================================================================
# SIDEBAR
# ==============================================================================
with st.sidebar:
    st.header("Plotting Controls")
    if st.button("Clear All Stored Traces"):
        clear_traces()
    st.info("Generate a plot → click 'Save Trace' → change parameters → plot again to compare.")

    if st.session_state['stored_traces']:
        st.markdown(f"**Stored Traces:** {len(st.session_state['stored_traces'])}")
        for i, t in enumerate(st.session_state['stored_traces']):
            c_tr, c_del = st.columns([3, 1])
            with c_tr:
                st.caption(f"{i + 1}. {t.get('label', 'Unknown')}")
            with c_del:
                if st.button("✕", key=f"del_trace_{i}", help=f"Delete trace {i+1}"):
                    st.session_state['stored_traces'].pop(i)
                    st.rerun()
    else:
        st.caption("No traces stored yet.")


# ==============================================================================
# TABS
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs([
    "Single Gate System",
    "Dual Gate System",
    "Hall Effect & SdH",
    "Transport Properties"
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
        help="Choose 'Gate Voltage' to see how density changes with voltage. "
             "Choose 'Dielectric Thickness' to see how density changes with thickness."
    )

    # --- Display Formulas ---
    with st.expander("Show Formulas", expanded=True):
        st.markdown(r"""
        **Capacitance:** $$C_{geo} = \frac{\epsilon_r \epsilon_0}{d}$$

        **Carrier Density:** $$n = \frac{C_{geo} (V_g - V_{CNP})}{e}$$
        """)

    # --- Material Preset ---
    st.markdown("##### Material Preset")
    c_preset, _ = st.columns([1, 2])
    with c_preset:
        st.selectbox(
            "Dielectric Material",
            list(MATERIAL_PRESETS.keys()),
            key="sg_preset",
            on_change=apply_preset,
            args=("sg_preset", "sg_eps", "sg_d")
        )

    col1, col2 = st.columns(2)

    if sg_mode == "Gate Voltage (Vg)":
        with col1:
            st.subheader("Parameters")
            epsilon_r = st.number_input("Dielectric Constant (ϵr)", value=3.9, min_value=0.01,
                                        key="sg_eps", help="e.g., 3.9 for SiO2, 4-7 for hBN")
            d_nm = st.number_input("Dielectric Thickness (nm)", value=300.0, min_value=0.1,
                                   key="sg_d", help="Must be > 0")
            v_cnp = st.number_input("Charge Neutrality Point (CNP) [V]", value=0.0, key="sg_cnp")

        with col2:
            st.subheader("Sweep Range")
            v_start = st.number_input("Start Gate Voltage (V)", value=-40.0, key="sg_vstart")
            v_end = st.number_input("End Gate Voltage (V)", value=40.0, key="sg_vend")
            n_points = st.number_input("Number of Points", value=100, min_value=10, step=10,
                                       key="sg_pts_v")

        if not validate_positive(d_nm, "Dielectric Thickness"):
            st.stop()

        # Calculations
        d_m = d_nm * 1e-9
        C_geo = (epsilon_r * epsilon_0) / d_m
        V_g = np.linspace(v_start, v_end, int(n_points))
        V_eff = V_g - v_cnp
        n_dens_m2 = (C_geo * V_eff) / e
        n_dens_cm2 = n_dens_m2 / 1e4
        E_field_V_nm = V_eff / d_nm

        # Plot selection
        st.subheader("Plotting")
        plot_type = st.selectbox("Select Plot Type", [
            "Gate Voltage vs Carrier Density",
            "Gate Voltage vs Displacement Field (E-field)",
            "Carrier Density vs Displacement Field"
        ], key="sg_plot_v")

        if plot_type == "Gate Voltage vs Carrier Density":
            x_data, y_data = V_g, n_dens_cm2
            x_label, y_label = "Gate Voltage (V)", "Carrier Density (cm⁻²)"
        elif plot_type == "Gate Voltage vs Displacement Field (E-field)":
            x_data, y_data = V_g, E_field_V_nm
            x_label, y_label = "Gate Voltage (V)", "Displacement Field (V/nm)"
        else:
            x_data, y_data = E_field_V_nm, n_dens_cm2
            x_label, y_label = "Displacement Field (V/nm)", "Carrier Density (cm⁻²)"

        trace_label = f"d={d_nm}nm, εr={epsilon_r}"
        current_trace_type = "SingleGate_Voltage"

    else:  # Sweep Thickness
        with col1:
            st.subheader("Fixed Parameters")
            epsilon_r = st.number_input("Dielectric Constant (ϵr)", value=3.9, min_value=0.01,
                                        key="sg_eps")
            v_g_fixed = st.number_input("Fixed Gate Voltage (V)", value=10.0, key="sg_vg_fix")
            v_cnp = st.number_input("Charge Neutrality Point (CNP) [V]", value=0.0, key="sg_cnp")

        with col2:
            st.subheader("Thickness Sweep Range")
            d_start = st.number_input("Start Thickness (nm)", value=10.0, min_value=0.1, key="sg_dstart")
            d_end = st.number_input("End Thickness (nm)", value=300.0, min_value=0.1, key="sg_dend")
            n_points = st.number_input("Number of Points", value=100, min_value=10, step=10,
                                       key="sg_pts_d")

        if d_start <= 0 or d_end <= 0:
            st.error("⚠️ Thickness values must be positive.")
            st.stop()

        d_nm_arr = np.linspace(d_start, d_end, int(n_points))
        d_m_arr = d_nm_arr * 1e-9
        C_geo_arr = (epsilon_r * epsilon_0) / d_m_arr
        V_eff = v_g_fixed - v_cnp
        n_dens_m2 = (C_geo_arr * V_eff) / e
        n_dens_cm2 = n_dens_m2 / 1e4

        x_data, y_data = d_nm_arr, n_dens_cm2
        x_label, y_label = "Dielectric Thickness (nm)", "Carrier Density (cm⁻²)"
        plot_type = "Thickness vs Density"
        trace_label = f"Vg={v_g_fixed}V, εr={epsilon_r}"
        current_trace_type = "SingleGate_Thickness"

    # --- Unified plotting & export ---
    render_plot_with_export(
        x_data, y_data, x_label, y_label,
        trace_type=current_trace_type, plot_type=plot_type, trace_label=trace_label,
        save_key="save_sg", img_filename="single_gate_plot.png",
        csv_filename="single_gate_data.csv", line_color='blue'
    )

# ==============================================================================
# TAB 2: DUAL GATE SYSTEM
# ==============================================================================
with tab2:
    st.header("Dual Gate Calculations")

    dg_mode = st.radio(
        "Select Calculation Mode",
        ["Sweep Gate Voltage", "Sweep Dielectric Thickness", "Inverse (Calculate Required Voltages)"],
        horizontal=True
    )

    # =========================================================================
    # BRANCH 1: VOLTAGE SWEEP
    # =========================================================================
    if dg_mode == "Sweep Gate Voltage":
        with st.expander("Show Formulas", expanded=True):
            st.markdown(r"""
            **Total Carrier Density:** $$n_{tot} = n_{top} + n_{bot}$$
            **Displacement Field:** $$D = (D_{top} - D_{bot}) / 2$$
            """)

        # --- Material Presets ---
        st.markdown("##### Material Presets")
        cp1, cp2 = st.columns(2)
        with cp1:
            st.selectbox("Top Dielectric", list(MATERIAL_PRESETS.keys()),
                         key="dg_v_top_preset",
                         on_change=apply_preset,
                         args=("dg_v_top_preset", "dg_v_kt", "dg_v_dt"))
        with cp2:
            st.selectbox("Bottom Dielectric", list(MATERIAL_PRESETS.keys()),
                         key="dg_v_bot_preset",
                         on_change=apply_preset,
                         args=("dg_v_bot_preset", "dg_v_kb", "dg_v_db"))

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top Gate")
            dt_nm = st.number_input("Top Dielectric Thickness (nm)", value=30.0, min_value=0.1,
                                    key="dg_v_dt")
            kt = st.number_input("Top Dielectric Constant", value=4.0, min_value=0.01,
                                 key="dg_v_kt")
            v_cnp_t = st.number_input("Top Gate CNP (V)", value=0.0, key="dg_v_cnp_t")
            vt_range = st.text_input("Top Gate Range (start, end)", "-10, 10", key="dg_v_vtr")

        with c2:
            st.markdown("### Bottom Gate")
            db_nm = st.number_input("Bottom Dielectric Thickness (nm)", value=300.0, min_value=0.1,
                                    key="dg_v_db")
            kb = st.number_input("Bottom Dielectric Constant", value=3.9, min_value=0.01,
                                 key="dg_v_kb")
            v_cnp_b = st.number_input("Bottom Gate CNP (V)", value=0.0, key="dg_v_cnp_b")
            vb_range = st.text_input("Bottom Gate Range (start, end)", "-40, 40", key="dg_v_vbr")

        num_pts = st.number_input("Number of Points", value=100, min_value=10, key="dg_v_pts")

        # Parse ranges
        try:
            vt_start, vt_end = map(float, vt_range.split(','))
            vb_start, vb_end = map(float, vb_range.split(','))
        except ValueError:
            st.error("Invalid range format. Use 'start, end' (e.g., -10, 10)")
            vt_start, vt_end, vb_start, vb_end = -10, 10, -40, 40

        st.subheader("Sweep Configuration")
        sweep_mode = st.radio("Sweep Type",
                              ["Sweep Top Gate (Fixed Bottom)", "Sweep Bottom Gate (Fixed Top)"],
                              key="dg_v_sweep")

        if sweep_mode == "Sweep Top Gate (Fixed Bottom)":
            fixed_val = st.number_input("Fixed Bottom Gate Voltage (V)", value=0.0, key="dg_v_fix_bot")
            x_g = np.linspace(vt_start, vt_end, int(num_pts))
            v_tg, v_bg = x_g, np.full_like(x_g, fixed_val)
            x_label_dg = "Top Gate Voltage (V)"
        else:
            fixed_val = st.number_input("Fixed Top Gate Voltage (V)", value=0.0, key="dg_v_fix_top")
            x_g = np.linspace(vb_start, vb_end, int(num_pts))
            v_bg, v_tg = x_g, np.full_like(x_g, fixed_val)
            x_label_dg = "Bottom Gate Voltage (V)"

        # --- Calculations ---
        Ct = (kt * epsilon_0) / (dt_nm * 1e-9)
        Cb = (kb * epsilon_0) / (db_nm * 1e-9)
        v_tg_eff = v_tg - v_cnp_t
        v_bg_eff = v_bg - v_cnp_b
        nt = (Ct * v_tg_eff) / e
        nb = (Cb * v_bg_eff) / e
        n_tot_cm2 = (nt + nb) / 1e4
        D_field_Vnm = ((Ct * v_tg_eff) - (Cb * v_bg_eff)) / (2 * epsilon_0 * 1e9)

        dg_plot_type = st.selectbox("Select Dual Gate Plot", [
            "Gate Voltage vs Carrier Density",
            "Gate Voltage vs Displacement Field",
            "Carrier Density vs Displacement Field"
        ], key="dg_v_plot")

        if dg_plot_type == "Gate Voltage vs Carrier Density":
            xd, yd = x_g, n_tot_cm2
            yl = "Total Carrier Density (cm⁻²)"
        elif dg_plot_type == "Gate Voltage vs Displacement Field":
            xd, yd = x_g, D_field_Vnm
            yl = "Displacement Field (V/nm)"
        else:
            xd, yd = D_field_Vnm, n_tot_cm2
            x_label_dg = "Displacement Field (V/nm)"
            yl = "Total Carrier Density (cm⁻²)"

        render_plot_with_export(
            xd, yd, x_label_dg, yl,
            trace_type="DualGate_Voltage", plot_type=dg_plot_type,
            trace_label=f"Fixed V={fixed_val}V",
            save_key="save_dg_v", img_filename="dual_gate_voltage_plot.png",
            csv_filename="dual_gate_voltage_data.csv", line_color='red'
        )

    # =========================================================================
    # BRANCH 2: THICKNESS SWEEP
    # =========================================================================
    elif dg_mode == "Sweep Dielectric Thickness":
        dg_thick_target = st.radio("Target Dielectric",
                                   ["Sweep Top Thickness (Fixed Bottom)",
                                    "Sweep Bottom Thickness (Fixed Top)"],
                                   key="dg_ts_target")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Top Gate")
            kt = st.number_input("Top Dielectric Constant", value=4.0, min_value=0.01, key="dg_ts_kt")
            v_cnp_t = st.number_input("Top Gate CNP (V)", value=0.0, key="dg_ts_cnp_t")
            if "Top Thickness" in dg_thick_target:
                dt_range = st.text_input("Top Thickness Range (nm) [start, end]", "10, 100",
                                         key="dg_ts_dt_range")
            else:
                dt_nm = st.number_input("Top Thickness (nm)", value=30.0, min_value=0.1, key="dg_ts_dt")
            v_tg_fixed = st.number_input("Fixed Top Gate Voltage (V)", value=10.0, key="dg_ts_vt")

        with c2:
            st.markdown("### Bottom Gate")
            kb = st.number_input("Bottom Dielectric Constant", value=3.9, min_value=0.01, key="dg_ts_kb")
            v_cnp_b = st.number_input("Bottom Gate CNP (V)", value=0.0, key="dg_ts_cnp_b")
            if "Bottom Thickness" in dg_thick_target:
                db_range = st.text_input("Bottom Thickness Range (nm) [start, end]", "10, 300",
                                         key="dg_ts_db_range")
            else:
                db_nm = st.number_input("Bottom Thickness (nm)", value=300.0, min_value=0.1, key="dg_ts_db")
            v_bg_fixed = st.number_input("Fixed Bottom Gate Voltage (V)", value=0.0, key="dg_ts_vb")

        num_pts = st.number_input("Number of Points", value=100, min_value=10, key="dg_ts_pts")

        # --- Calculations ---
        if "Top Thickness" in dg_thick_target:
            try:
                start, end = map(float, dt_range.split(','))
            except ValueError:
                start, end = 10.0, 100.0
            dt_nm_arr = np.linspace(start, end, int(num_pts))
            Ct = (kt * epsilon_0) / (dt_nm_arr * 1e-9)
            Cb = (kb * epsilon_0) / (db_nm * 1e-9)
            xd = dt_nm_arr
            x_label_dg = "Top Dielectric Thickness (nm)"
            dg_trace_label = f"Sweep Top d, Vg_t={v_tg_fixed}V"
        else:
            try:
                start, end = map(float, db_range.split(','))
            except ValueError:
                start, end = 10.0, 300.0
            db_nm_arr = np.linspace(start, end, int(num_pts))
            Ct = (kt * epsilon_0) / (dt_nm * 1e-9)
            Cb = (kb * epsilon_0) / (db_nm_arr * 1e-9)
            xd = db_nm_arr
            x_label_dg = "Bottom Dielectric Thickness (nm)"
            dg_trace_label = f"Sweep Bot d, Vg_b={v_bg_fixed}V"

        v_tg_eff = v_tg_fixed - v_cnp_t
        v_bg_eff = v_bg_fixed - v_cnp_b
        nt = (Ct * v_tg_eff) / e
        nb = (Cb * v_bg_eff) / e
        n_tot_cm2 = (nt + nb) / 1e4
        D_field_Vnm = ((Ct * v_tg_eff) - (Cb * v_bg_eff)) / (2 * epsilon_0 * 1e9)

        dg_plot_type = st.selectbox("Select Plot",
                                    ["Thickness vs Carrier Density", "Thickness vs Displacement Field"],
                                    key="dg_ts_plot")
        if dg_plot_type == "Thickness vs Carrier Density":
            yd, yl = n_tot_cm2, "Total Carrier Density (cm⁻²)"
        else:
            yd, yl = D_field_Vnm, "Displacement Field (V/nm)"

        render_plot_with_export(
            xd, yd, x_label_dg, yl,
            trace_type="DualGate_Thickness", plot_type=dg_plot_type,
            trace_label=dg_trace_label,
            save_key="save_dg_ts", img_filename="dual_gate_thickness_plot.png",
            csv_filename="dual_gate_thickness_data.csv", line_color='red'
        )

    # =========================================================================
    # BRANCH 3: INVERSE MODE
    # =========================================================================
    else:
        st.info("Calculate required Top and Bottom Gate Voltages to achieve specific n and D.")

        # --- Material Presets ---
        st.markdown("##### Material Presets")
        cp1, cp2 = st.columns(2)
        with cp1:
            st.selectbox("Top Dielectric", list(MATERIAL_PRESETS.keys()),
                         key="dg_inv_top_preset",
                         on_change=apply_preset,
                         args=("dg_inv_top_preset", "dg_inv_kt", "dg_inv_dt"))
        with cp2:
            st.selectbox("Bottom Dielectric", list(MATERIAL_PRESETS.keys()),
                         key="dg_inv_bot_preset",
                         on_change=apply_preset,
                         args=("dg_inv_bot_preset", "dg_inv_kb", "dg_inv_db"))

        c_dev1, c_dev2 = st.columns(2)
        with c_dev1:
            st.markdown("### Top Gate")
            dt_nm = st.number_input("Top Dielectric Thickness (nm)", value=30.0, min_value=0.1,
                                    key="dg_inv_dt")
            kt = st.number_input("Top Dielectric Constant", value=4.0, min_value=0.01,
                                 key="dg_inv_kt")
            v_cnp_t = st.number_input("Top Gate CNP (V)", value=0.0, key="dg_inv_cnp_t")

        with c_dev2:
            st.markdown("### Bottom Gate")
            db_nm = st.number_input("Bottom Dielectric Thickness (nm)", value=300.0, min_value=0.1,
                                    key="dg_inv_db")
            kb = st.number_input("Bottom Dielectric Constant", value=3.9, min_value=0.01,
                                 key="dg_inv_kb")
            v_cnp_b = st.number_input("Bottom Gate CNP (V)", value=0.0, key="dg_inv_cnp_b")

        Ct = (kt * epsilon_0) / (dt_nm * 1e-9)
        Cb = (kb * epsilon_0) / (db_nm * 1e-9)

        with st.expander("Show Formulas", expanded=False):
            st.markdown(r"""
            We solve the system for $V_t$ and $V_b$:
            $$V_t = V_{CNP,t} + \frac{e \cdot n_{tot} + 2 D}{2 C_t}$$
            $$V_b = V_{CNP,b} + \frac{e \cdot n_{tot} - 2 D}{2 C_b}$$
            *(Note: Input D is converted to C/m² for calculation)*
            """)

        inv_mode = st.radio("Inverse Mode Type", ["Fixed D, Sweep n", "Fixed n, Sweep D"],
                            key="dg_inv_mode")
        n_pts_inv = st.number_input("Number of Points", value=100, min_value=10, key="dg_inv_pts")

        if inv_mode == "Fixed D, Sweep n":
            c_i1, c_i2 = st.columns(2)
            with c_i1:
                fixed_D_Vnm = st.number_input("Fixed Displacement Field (V/nm)", value=0.0,
                                              key="dg_inv_fixD")
            with c_i2:
                n_range = st.text_input("Carrier Density Range (cm⁻²)", "-5e12, 5e12",
                                        key="dg_inv_n_range")

            try:
                n_start, n_end = map(float, n_range.split(','))
            except ValueError:
                n_start, n_end = -5e12, 5e12

            n_sweep_cm2 = np.linspace(n_start, n_end, int(n_pts_inv))
            n_sweep_m2 = n_sweep_cm2 * 1e4
            D_fixed_SI = fixed_D_Vnm * 1e9 * epsilon_0

            Vt_calc = v_cnp_t + (e * n_sweep_m2 + 2 * D_fixed_SI) / (2 * Ct)
            Vb_calc = v_cnp_b + (e * n_sweep_m2 - 2 * D_fixed_SI) / (2 * Cb)

            x_plot = n_sweep_cm2
            xlabel_inv = "Carrier Density (cm⁻²)"
            title_inv = f"Required Gate Voltages for Fixed D = {fixed_D_Vnm} V/nm"

        else:  # Fixed n, Sweep D
            c_i1, c_i2 = st.columns(2)
            with c_i1:
                fixed_n_cm2 = st.number_input("Fixed Carrier Density (cm⁻²)", value=1e12,
                                              format="%.2e", key="dg_inv_fix_n")
            with c_i2:
                d_range = st.text_input("Displacement Field Range (V/nm)", "-0.5, 0.5",
                                        key="dg_inv_D_range")

            try:
                d_start, d_end = map(float, d_range.split(','))
            except ValueError:
                d_start, d_end = -0.5, 0.5

            D_sweep_Vnm = np.linspace(d_start, d_end, int(n_pts_inv))
            D_sweep_SI = D_sweep_Vnm * 1e9 * epsilon_0
            n_fixed_m2 = fixed_n_cm2 * 1e4

            Vt_calc = v_cnp_t + (e * n_fixed_m2 + 2 * D_sweep_SI) / (2 * Ct)
            Vb_calc = v_cnp_b + (e * n_fixed_m2 - 2 * D_sweep_SI) / (2 * Cb)

            x_plot = D_sweep_Vnm
            xlabel_inv = "Displacement Field (V/nm)"
            title_inv = f"Required Gate Voltages for Fixed n = {fixed_n_cm2:.2e} cm⁻²"

        # --- Plotting Inverse Results (2 lines: Vt and Vb) ---
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

        fig_p_inv = go.Figure()
        fig_p_inv.add_trace(go.Scatter(x=x_plot, y=Vt_calc, mode='lines',
                                       name='Top Gate (Vt)', line=dict(color='red')))
        fig_p_inv.add_trace(go.Scatter(x=x_plot, y=Vb_calc, mode='lines',
                                       name='Bottom Gate (Vb)', line=dict(color='blue')))
        fig_p_inv.update_layout(
            title=title_inv,
            xaxis_title=xlabel_inv,
            yaxis_title="Gate Voltage (V)",
            hovermode="x unified"
        )
        if "Carrier Density" in xlabel_inv:
            fig_p_inv.update_layout(xaxis=dict(tickformat=".2e"))

        st.plotly_chart(fig_p_inv, width="stretch")

        # Export
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            buf_inv = io.BytesIO()
            fig_inv.savefig(buf_inv, format='png', dpi=300, bbox_inches='tight')
            st.download_button("🖼️ Download Plot (PNG)", buf_inv.getvalue(),
                               "inverse_gate_plot.png", "image/png", key="dl_img_inv")
        with col_dl2:
            buf_csv_inv = io.StringIO()
            buf_csv_inv.write(f"{xlabel_inv},Top Gate V,Bottom Gate V\n")
            np.savetxt(buf_csv_inv, np.column_stack((x_plot, Vt_calc, Vb_calc)), delimiter=",")
            st.download_button("📄 Download Data (CSV)", buf_csv_inv.getvalue().encode('utf-8'),
                               "inverse_gate_data.csv", "text/csv", key="dl_csv_inv",
                               help="Columns: Sweep Variable, Top Gate V, Bottom Gate V")

        plt.close(fig_inv)

# ==============================================================================
# TAB 3: HALL EFFECT & SdH
# ==============================================================================
with tab3:
    st.header("Hall Effect & SdH Oscillations")

    c_hall, c_sdh = st.columns(2)

    with c_hall:
        st.subheader("Hall Effect Carrier Density")
        st.markdown(r"Formula: $n = \frac{1}{e R_H} = \frac{1}{e (dR_{xy}/dB)}$")
        delta_r = st.number_input(r"Change in Hall Resistance $ΔR_{xy}$ (Ω)", value=1400.0,
                                  key="hall_dr")
        delta_b = st.number_input(r"Change in Magnetic Field $ΔB$ (T)", value=1.0,
                                  min_value=0.001, key="hall_db")

        if delta_b == 0:
            st.error("⚠️ ΔB cannot be zero.")
        elif delta_r == 0:
            st.error("⚠️ ΔRxy cannot be zero.")
        else:
            hall_slope = delta_r / delta_b
            n_hall = 1 / (e * hall_slope)
            st.metric("Carrier Density (n)", f"{n_hall / 1e4:.3e} cm⁻²")
            st.markdown(f"**Calculated Slope:** {hall_slope:.2f} Ω/T")

    with c_sdh:
        st.subheader("SdH Oscillations")
        st.markdown(r"Formula: $n = \frac{g e}{h \Delta(1/B)} = \frac{g e}{h} B_F$")
        bf = st.number_input(r"SdH Frequency $B_F$ (Tesla)", value=10.0, min_value=0.001,
                             key="sdh_bf")
        g_factor = st.number_input(
            "Degeneracy Factor (g)", value=4, step=1, min_value=1, format="%d",
            help="Integer value (e.g., 2 for spin degeneracy, 4 for spin+valley)",
            key="sdh_g"
        )
        n_sdh = (g_factor * e * bf) / h
        st.metric("SdH Carrier Density", f"{n_sdh / 1e4:.3e} cm⁻²")

    # =========================================================================
    # LANDAU LEVEL FAN DIAGRAM
    # =========================================================================
    st.divider()
    st.subheader("Landau Level Fan Diagram")

    with st.expander("Show Formulas", expanded=False):
        st.markdown(r"""
        **Onsager relation:** The SdH oscillation extrema occur at:

        $$\frac{1}{B_n} = \frac{2\pi e}{\hbar A_n} = \frac{n + \gamma}{B_F}$$

        where $B_F$ is the SdH frequency, $n$ is the Landau index, and $\gamma$ is the phase offset
        ($\gamma = 0$ for electrons, $\gamma = \pm 1/8$ for Dirac fermions in graphene).

        A plot of $1/B_n$ vs. $n$ should be linear, with **slope = 1/B_F**.
        """)

    c_fan1, c_fan2 = st.columns([1, 2])

    with c_fan1:
        bf_fan = st.number_input("SdH Frequency B_F (T)", value=10.0, min_value=0.001,
                                 key="fan_bf")
        gamma = st.selectbox("Phase Offset (gamma)", [0, 0.5, -0.125, 0.125],
                             format_func=lambda x: {
                                 0: "0 (Electrons, parabolic)",
                                 0.5: "1/2 (Holes, parabolic)",
                                 -0.125: "-1/8 (Graphene, electrons)",
                                 0.125: "+1/8 (Graphene, holes)"
                             }.get(x, str(x)), key="fan_gamma")
        n_start_fan = st.number_input("Start Landau Index", value=1, min_value=0, step=1,
                                      key="fan_n_start")
        n_end_fan = st.number_input("End Landau Index", value=15, min_value=1, step=1,
                                    key="fan_n_end")

        if bf_fan <= 0:
            st.error("B_F must be positive.")
        else:
            indices = np.arange(n_start_fan, n_end_fan + 1)
            inv_B = (indices + gamma) / bf_fan

            st.metric("Slope (1/B_F)", f"{1/bf_fan:.4f} T⁻¹")
            st.metric("Extracted n", f"{n_sdh / 1e4:.3e} cm⁻²")

    with c_fan2:
        if bf_fan > 0 and n_end_fan > n_start_fan:
            fig_fan = go.Figure()
            fig_fan.add_trace(go.Scatter(
                x=indices, y=inv_B, mode='markers+lines',
                name='Landau levels',
                marker=dict(size=8, color='blue'),
                line=dict(color='blue', width=1, dash='dash')
            ))

            # Linear fit for display
            slope = 1 / bf_fan
            intercept = gamma / bf_fan
            fit_line = slope * indices + intercept
            fig_fan.add_trace(go.Scatter(
                x=indices, y=fit_line, mode='lines',
                name=f'Fit: slope = 1/B_F = {slope:.4f} T⁻¹',
                line=dict(color='red', width=2)
            ))

            fig_fan.update_layout(
                title="Landau Fan Diagram",
                xaxis_title="Landau Index n",
                yaxis_title="1/B (T⁻¹)",
                hovermode="x unified",
                margin=dict(l=50, r=30, t=50, b=40),
                legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
            )
            st.plotly_chart(fig_fan, width="stretch")

            # Export
            c_fan_exp1, c_fan_exp2 = st.columns(2)
            with c_fan_exp1:
                fig_fan_mpl, ax_fan = plt.subplots()
                ax_fan.plot(indices, inv_B, 'bo-', markersize=6, label='Landau levels')
                ax_fan.plot(indices, fit_line, 'r--', label=f'Fit: 1/B_F = {slope:.4f}')
                ax_fan.set_xlabel("Landau Index n")
                ax_fan.set_ylabel("1/B (T⁻¹)")
                ax_fan.set_title("Landau Fan Diagram")
                ax_fan.legend()
                ax_fan.grid(True, alpha=0.5)
                buf_fan = io.BytesIO()
                fig_fan_mpl.savefig(buf_fan, format='png', dpi=300, bbox_inches='tight')
                st.download_button("🖼️ Download Fan Diagram (PNG)", buf_fan.getvalue(),
                                   "landau_fan.png", "image/png", key="dl_img_fan")
                plt.close(fig_fan_mpl)
            with c_fan_exp2:
                buf_fan_csv = io.StringIO()
                buf_fan_csv.write("Landau Index n,1/B (1/T)\n")
                np.savetxt(buf_fan_csv, np.column_stack((indices, inv_B)), delimiter=",")
                st.download_button("📄 Download Fan Data (CSV)",
                                   buf_fan_csv.getvalue().encode('utf-8'),
                                   "landau_fan_data.csv", "text/csv", key="dl_csv_fan")

# ==============================================================================
# TAB 4: TRANSPORT PROPERTIES
# ==============================================================================
with tab4:
    st.header("Transport Properties")

    # --- Sub-sections ---
    sec_mob, sec_mag, sec_fermi = st.columns(3)

    # =========================================================================
    # SECTION A: MOBILITY
    # =========================================================================
    with sec_mob:
        st.subheader("Mobility (μ)")
        st.markdown(r"$$\mu = \frac{\sigma}{n e} = \frac{1}{\rho n e}$$")

        calc_mode = st.radio("Input Mode", ["Conductivity (σ)", "Resistivity (ρ)",
                                            "Resistance (R) & Geom"],
                             key="mob_mode")

        n_input = st.number_input("Carrier Density n (cm⁻²)", value=1e12, format="%.2e",
                                  min_value=1e8, key="mob_n")
        n_m2 = n_input * 1e4

        mobility = 0.0
        if calc_mode == "Conductivity (σ)":
            sigma = st.number_input("Conductivity σ (S or 1/Ω)", value=0.001, format="%.2e",
                                    min_value=0.0, key="mob_sigma")
            if n_m2 > 0 and sigma > 0:
                mobility = sigma / (n_m2 * e)
        elif calc_mode == "Resistivity (ρ)":
            rho = st.number_input("Resistivity ρ (Ω)", value=1000.0, min_value=0.001,
                                  key="mob_rho")
            if n_m2 > 0:
                mobility = 1 / (rho * n_m2 * e)
        else:
            r_val = st.number_input("Resistance R (Ω)", value=1000.0, min_value=0.001,
                                    key="mob_R")
            l_w = st.number_input("Aspect Ratio (L/W)", value=1.0, min_value=0.001,
                                  key="mob_lw")
            rho_calc = r_val / l_w
            if n_m2 > 0:
                mobility = 1 / (rho_calc * n_m2 * e)

        mobility_cm2 = mobility * 1e4  # m²/Vs → cm²/Vs
        st.metric("Mobility", f"{mobility_cm2:.2f} cm²/Vs")

    # =========================================================================
    # SECTION B: MAGNETIC LENGTH
    # =========================================================================
    with sec_mag:
        st.subheader("Magnetic Length (lB)")
        st.markdown(r"$$l_B = \sqrt{\frac{\hbar}{eB}}$$")
        b_field = st.number_input("Magnetic Field B (Tesla)", value=1.0, min_value=0.001,
                                  key="mag_B")

        lb = np.sqrt(hbar / (e * b_field))
        st.metric("Magnetic Length", f"{lb * 1e9:.2f} nm")

    # =========================================================================
    # SECTION C: FERMI ENERGY & WAVELENGTH
    # =========================================================================
    with sec_fermi:
        st.subheader("Fermi Properties")
        n_fermi = st.number_input(r"Carrier Density for $E_F$ (cm⁻²)", value=1e12, format="%.2e",
                                  min_value=1e8, key="fermi_n")
        n_fermi_m2 = n_fermi * 1e4

        # Material type selector
        mat_type = st.radio("Material Type", ["Conventional 2DEG", "Graphene (Dirac)"],
                            horizontal=True, key="fermi_mat")

        if mat_type == "Conventional 2DEG":
            m_preset = st.selectbox("Effective Mass Preset", list(EFFECTIVE_MASS_PRESETS.keys()),
                                    key="fermi_m_preset")
            m_defaults = EFFECTIVE_MASS_PRESETS.get(m_preset, {"m_star_m_e": 0.1})
            m_star_m_e = st.number_input(r"Effective Mass $\frac{m^*}{m_e}$", value=m_defaults["m_star_m_e"],
                                         min_value=0.001, format="%.3f", key="fermi_mstar")
            m_star = m_star_m_e * m_e

            # E_F = πℏ²n / m*
            E_F = np.pi * hbar**2 * n_fermi_m2 / m_star
            E_F_eV = E_F / e
            st.metric("Fermi Energy", f"{E_F_eV * 1000:.2f} meV")

            # v_F = ℏk_F/m* = ℏ√(2πn)/m*
            v_F = hbar * np.sqrt(2 * np.pi * n_fermi_m2) / m_star
            st.metric("Fermi Velocity", f"{v_F:.2e} m/s")

            # τ = m*μ/e (requires mobility from above)
            tau = m_star * mobility / e
            st.metric("Scattering Time τ", f"{tau:.2e} s")

            # Mean free path = v_F × τ
            l_mfp = v_F * tau
            st.metric("Mean Free Path", f"{l_mfp * 1e9:.2f} nm")

        else:  # Graphene
            v_F_graphene = st.number_input("Fermi Velocity v_F (m/s)", value=1e6,
                                           format="%.2e", key="fermi_vF")
            # E_F = ℏv_F√(π|n|)
            E_F = hbar * v_F_graphene * np.sqrt(np.pi * abs(n_fermi_m2))
            E_F_eV = E_F / e
            st.metric("Fermi Energy", f"{E_F_eV * 1000:.2f} meV")

            # Cyclotron mass: m_cyc = E_F / v_F²
            m_cyc = E_F / (v_F_graphene**2) if v_F_graphene > 0 else 0
            st.metric("Cyclotron Mass", f"{m_cyc / m_e:.4f} m_e")

            # τ = m_cyc × μ / e
            tau = m_cyc * mobility / e if m_cyc > 0 else 0
            st.metric("Scattering Time τ", f"{tau:.2e} s")

            # Mean free path = v_F × τ
            l_mfp = v_F_graphene * tau
            st.metric("Mean Free Path", f"{l_mfp * 1e9:.2f} nm")

        # Fermi wavelength (universal for 2D)
        lambda_F = np.sqrt(2 * np.pi / n_fermi_m2)
        st.metric(r"Fermi Wavelength (λ)", f"{lambda_F * 1e9:.2f} nm")

    # =========================================================================
    # SECTION D: CYCLOTRON PROPERTIES
    # =========================================================================
    st.divider()
    st.subheader("Cyclotron Properties")

    c_cyc, c_cyc2 = st.columns(2)

    with c_cyc:
        b_cyc = st.number_input("Magnetic Field B (T)", value=1.0, min_value=0.001, key="cyc_B")
        n_cyc = st.number_input("Carrier Density n (cm⁻²)", value=1e12, format="%.2e",
                                min_value=1e8, key="cyc_n")
        n_cyc_m2 = n_cyc * 1e4
        mat_type_cyc = st.radio("Material", ["Conventional 2DEG", "Graphene (Dirac)"],
                                horizontal=True, key="cyc_mat")

        if mat_type_cyc == "Conventional 2DEG":
            m_preset_cyc = st.selectbox("Effective Mass Preset", list(EFFECTIVE_MASS_PRESETS.keys()),
                                        key="cyc_m_preset")
            m_def = EFFECTIVE_MASS_PRESETS.get(m_preset_cyc, {"m_star_m_e": 0.1})
            m_star_cyc_m_e = st.number_input("Effective Mass m*/m_e", value=m_def["m_star_m_e"],
                                             min_value=0.001, format="%.3f", key="cyc_mstar")
            m_star_cyc = m_star_cyc_m_e * m_e

            omega_c = e * b_cyc / m_star_cyc
            f_c = omega_c / (2 * np.pi)
            v_F_cyc = hbar * np.sqrt(2 * np.pi * n_cyc_m2) / m_star_cyc
            r_c = v_F_cyc / omega_c

            col_om, col_fc = st.columns(2)
            with col_om:
                st.metric("ω_c", f"{omega_c:.3e} rad/s")
            with col_fc:
                st.metric("f_c", f"{f_c:.3e} Hz")
            st.metric("Cyclotron Radius r_c", f"{r_c * 1e9:.2f} nm")

        else:  # Graphene
            v_F_g = st.number_input("Fermi Velocity v_F (m/s)", value=1e6, format="%.2e",
                                    key="cyc_vF")
            # Cyclotron mass for graphene: m_cyc = ℏ√(π|n|) / v_F
            m_cyc_g = hbar * np.sqrt(np.pi * abs(n_cyc_m2)) / v_F_g if v_F_g > 0 else 1e-31
            omega_c = e * b_cyc / m_cyc_g
            f_c = omega_c / (2 * np.pi)
            r_c = v_F_g / omega_c if omega_c > 0 else float('inf')

            col_om, col_fc = st.columns(2)
            with col_om:
                st.metric("ω_c", f"{omega_c:.3e} rad/s")
            with col_fc:
                st.metric("f_c", f"{f_c:.3e} Hz")
            st.metric("Cyclotron Radius r_c", f"{r_c * 1e9:.2f} nm")
            st.metric("Cyclotron Mass", f"{m_cyc_g / m_e:.4f} m_e")

    with c_cyc2:
        st.markdown("##### Comparison: lB vs r_c")
        st.markdown(r"""
        **Magnetic Length:** $l_B = \sqrt{\hbar / eB}$

        **Cyclotron Radius:** $r_c = v_F / \omega_c$

        When $r_c \gg l_B$, many Landau levels are occupied (semi-classical regime).
        When $r_c \sim l_B$, the system is in the quantum Hall regime.
        """)

        lb_cyc = np.sqrt(hbar / (e * b_cyc))
        ratio = r_c / lb_cyc if lb_cyc > 0 else float('inf')
        st.metric("l_B", f"{lb_cyc * 1e9:.2f} nm")
        st.metric("r_c / l_B", f"{ratio:.2f}")
        if ratio < 3:
            st.success("Quantum Hall regime (r_c ≈ l_B)")
        elif ratio < 10:
            st.info("Intermediate regime")
        else:
            st.warning("Semi-classical regime (r_c ≫ l_B)")

    # =========================================================================
    # SECTION E: DRUDE CONDUCTIVITY TENSOR SWEEP
    # =========================================================================
    st.divider()
    st.subheader("Drude Model: B-Field Sweep")

    with st.expander("Show Formulas", expanded=False):
        st.markdown(r"""
        **Drude Conductivity Tensor (single carrier type):**

        $$\sigma_{xx} = \frac{n e \mu}{1 + (\mu B)^2}$$

        $$\sigma_{xy} = \frac{n e \mu^2 B}{1 + (\mu B)^2}$$

        **Resistivity Tensor:**

        $$\rho_{xx} = \frac{1}{n e \mu} \quad \text{(constant for Drude)}$$

        $$\rho_{xy} = \frac{B}{n e} \quad \text{(linear in B)}$$
        """)

    c_drude_in, c_drude_plot = st.columns([1, 2])

    with c_drude_in:
        n_drude = st.number_input("Carrier Density n (cm⁻²)", value=1e12, format="%.2e",
                                  min_value=1e8, key="drude_n")
        mu_drude = st.number_input("Mobility μ (cm²/Vs)", value=5000.0, min_value=0.1,
                                   key="drude_mu")
        b_start_d = st.number_input("Start B (T)", value=0.0, key="drude_b_start")
        b_end_d = st.number_input("End B (T)", value=10.0, min_value=0.001, key="drude_b_end")
        n_pts_d = st.number_input("Number of Points", value=200, min_value=10, key="drude_pts")

        # Convert to SI
        n_si = n_drude * 1e4  # m⁻²
        mu_si = mu_drude * 1e-4  # m²/Vs

    with c_drude_plot:
        B_sweep = np.linspace(b_start_d, b_end_d, int(n_pts_d))

        # Drude model
        muB = mu_si * B_sweep
        sigma_xx = n_si * e * mu_si / (1 + muB**2)
        sigma_xy = n_si * e * mu_si**2 * B_sweep / (1 + muB**2)
        rho_xx = np.full_like(B_sweep, 1 / (n_si * e * mu_si)) if n_si * mu_si > 0 else np.zeros_like(B_sweep)
        rho_xy = B_sweep / (n_si * e)

        # Plotly: 2 subplots
        fig_drude = make_subplots(rows=2, cols=1,
                                  subplot_titles=("Conductivity", "Resistivity"),
                                  vertical_spacing=0.15)

        fig_drude.add_trace(go.Scatter(x=B_sweep, y=sigma_xx, mode='lines',
                                       name='σ_xx (S)', line=dict(color='blue')), row=1, col=1)
        fig_drude.add_trace(go.Scatter(x=B_sweep, y=sigma_xy, mode='lines',
                                       name='σ_xy (S)', line=dict(color='red')), row=1, col=1)
        fig_drude.add_trace(go.Scatter(x=B_sweep, y=rho_xx, mode='lines',
                                       name='ρ_xx (Ω)', line=dict(color='blue', dash='dash')),
                            row=2, col=1)
        fig_drude.add_trace(go.Scatter(x=B_sweep, y=rho_xy, mode='lines',
                                       name='ρ_xy (Ω)', line=dict(color='red', dash='dash')),
                            row=2, col=1)

        fig_drude.update_xaxes(title_text="Magnetic Field B (T)", row=2, col=1)
        fig_drude.update_yaxes(title_text="Conductivity (S)", row=1, col=1)
        fig_drude.update_yaxes(title_text="Resistivity (Ω)", row=2, col=1)
        fig_drude.update_layout(
            height=500, hovermode="x unified",
            margin=dict(l=50, r=30, t=60, b=40),
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )

        st.plotly_chart(fig_drude, width="stretch")

    # Export Drude
    c_dl_d1, c_dl_d2 = st.columns(2)
    with c_dl_d1:
        # Matplotlib for download
        fig_d_mpl, (ax_s, ax_r) = plt.subplots(2, 1, figsize=(6, 6), tight_layout=True)
        ax_s.plot(B_sweep, sigma_xx, label='σ_xx', color='blue')
        ax_s.plot(B_sweep, sigma_xy, label='σ_xy', color='red')
        ax_s.set_ylabel("Conductivity (S)")
        ax_s.legend()
        ax_s.grid(True, alpha=0.5)

        ax_r.plot(B_sweep, rho_xx, label='ρ_xx', color='blue', linestyle='--')
        ax_r.plot(B_sweep, rho_xy, label='ρ_xy', color='red', linestyle='--')
        ax_r.set_xlabel("Magnetic Field B (T)")
        ax_r.set_ylabel("Resistivity (Ω)")
        ax_r.legend()
        ax_r.grid(True, alpha=0.5)

        buf_d = io.BytesIO()
        fig_d_mpl.savefig(buf_d, format='png', dpi=300, bbox_inches='tight')
        st.download_button("🖼️ Download Drude Plot (PNG)", buf_d.getvalue(),
                           "drude_plot.png", "image/png", key="dl_img_drude")
        plt.close(fig_d_mpl)

    with c_dl_d2:
        buf_d_csv = io.StringIO()
        buf_d_csv.write("B (T),sigma_xx (S),sigma_xy (S),rho_xx (Ohm),rho_xy (Ohm)\n")
        np.savetxt(buf_d_csv, np.column_stack((B_sweep, sigma_xx, sigma_xy, rho_xx, rho_xy)), delimiter=",")
        st.download_button("📄 Download Drude Data (CSV)", buf_d_csv.getvalue().encode('utf-8'),
                           "drude_data.csv", "text/csv", key="dl_csv_drude")
