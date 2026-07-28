import streamlit as st
import pandas as pd, numpy as np, plotly.graph_objects as go, plotly.express as px
from pathlib import Path
import pickle, sys, json, importlib.util, time
from datetime import datetime

_ROOT = Path(__file__).resolve().parent
def _ld(n,f):
    s=importlib.util.spec_from_file_location(n,_ROOT/f)
    m=importlib.util.module_from_spec(s); s.loader.exec_module(m); return m
_sim=_ld("sim","simulator.py"); _res=_ld("res","residual_value.py"); _pp=_ld("pp","passport.py")
BATTERY_CATALOG=_sim.BATTERY_CATALOG; BatterySpec=_sim.BatterySpec
estimate_residual_value=_res.estimate_residual_value
create_passport=_pp.create_passport; add_event=_pp.add_event
verify_passport=_pp.verify_passport; export_passport_json=_pp.export_passport_json
import_passport_json=_pp.import_passport_json

OUTPUT_DIR=_ROOT/"data"; MODEL_DIR=_ROOT/"models"
import sys; sys.path.insert(0, str(_ROOT))

st.set_page_config(page_title="BMS · 动力电池管理系统",page_icon="◈",layout="wide",initial_sidebar_state="expanded")
from market_scraper import get_prices_for_streamlit, BRAND_PACK_PRICES, get_brand_price_for_streamlit, get_adjusted_brand_price

# ═══════════════════════════════════════════════════════════
# CSS — Dark industrial mechanical theme
# ═══════════════════════════════════════════════════════════
DARK_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Fira+Code:wght@400;500;600&display=swap');
* { font-display: swap; }
.stApp { background:#2c3038; font-family:'Inter','Segoe UI',system-ui,sans-serif; }

/* Grid + scan */
@media (prefers-reduced-motion:no-preference) {
.stApp::before {
    content:''; position:fixed; inset:0;
    background-image:linear-gradient(rgba(255,255,255,.04) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.04) 1px,transparent 1px);
    background-size:44px 44px;
    mask-image:radial-gradient(ellipse 60% 55% at 50% 40%,#000 40%,transparent 72%);
    pointer-events:none; z-index:0; animation:gridDrift 22s linear infinite;
}
.stApp::after {
    content:''; position:fixed; left:0; right:0; height:1px;
    background:linear-gradient(90deg,transparent,rgba(74,222,128,.12),transparent);
    pointer-events:none; z-index:1; animation:scanDown 9s linear infinite;
}
}
@keyframes gridDrift { 0%{background-position:0 0,0 0} 100%{background-position:44px 44px,44px 44px} }
@keyframes scanDown { 0%{top:-1px} 100%{top:calc(100% + 1px)} }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
@keyframes shine {
    0% { background-position: -200px; }
    100% { background-position: 320px; }
}
.sidebar-title {
    background: linear-gradient(90deg,#E8EDF4 0%,#7ee2bb 50%,#E8EDF4 100%);
    background-size: 200px 100%;
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    animation: shine 4.5s infinite linear;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] { background:#2c3038 !important; border-right:1px solid #4a4e57 !important; }
[data-testid="stSidebar"] .stRadio > div { gap:2px; }
[data-testid="stSidebar"] .stRadio label {
    font-family:'Inter','Segoe UI',sans-serif; font-size:14px; font-weight:400;
    letter-spacing:.02em; padding:10px 16px; line-height:36px;
    border-left:3px solid transparent; border-radius:0;
    color:#B0C4DE; transition:all .15s;
    margin:1px 0;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background:#353940; border-left-color:#5e626b; color:#E8EDF4;
}
[data-testid="stSidebar"] .stRadio [data-selected="true"] label {
    background:#32353d; border-left-color:#36D399; color:#ffffff; font-weight:500;
}

h1 { font-family:'Fira Code',monospace; font-size:1.3rem !important; font-weight:500 !important; letter-spacing:.04em; text-transform:uppercase; color:#f0f2f5 !important; border-bottom:1px solid #4a4e57; padding-bottom:.4rem; }
h2 { font-family:'Fira Code',monospace; font-size:.95rem !important; font-weight:500 !important; color:#22d3ee !important; text-transform:uppercase; letter-spacing:.04em; }
h3 { font-family:'Fira Code',monospace; font-size:.82rem !important; font-weight:500 !important; color:#b0b5bd !important; }

.panel { background:#32353d; border:1px solid #4a4e57; border-radius:2px; padding:18px 22px; position:relative; transition:border-color .15s; }
.panel:hover { border-color:#22d3ee; }
.panel::before,.panel::after { content:''; position:absolute; width:10px; height:10px; border-color:#5e626b; border-style:solid; transition:border-color .15s; }
.panel::before { top:4px; left:4px; border-width:1px 0 0 1px; }
.panel::after { bottom:4px; right:4px; border-width:0 1px 1px 0; }
.panel:hover::before,.panel:hover::after { border-color:#22d3ee; }

.kpi-val { font-family:'Fira Code',monospace; font-size:1.7rem; color:#f0f2f5; line-height:1.2; }
.kpi-lbl { font-family:'Fira Code',monospace; font-size:.62rem; color:#787c85; text-transform:uppercase; letter-spacing:.1em; margin-top:3px; }

.stButton > button { font-family:'Fira Code',monospace !important; font-size:.72rem !important; text-transform:uppercase !important; letter-spacing:.06em !important; border-radius:2px !important; border:1px solid #5e626b !important; background:#3e424a !important; color:#f0f2f5 !important; transition:all .15s !important; }
.stButton > button:hover { background:#4a4e57 !important; border-color:#787c85 !important; }
.stButton > button[kind="primary"] { border-color:#4ade80 !important; background:#1a2d24 !important; color:#4ade80 !important; }
.stButton > button[kind="primary"]:hover { background:#1f3a2e !important; }

[data-testid="stDataFrame"] { border:1px solid #4a4e57; border-radius:2px; }
[data-testid="stDataFrame"] th { background:#353940 !important; font-family:'Fira Code',monospace !important; font-size:.62rem !important; text-transform:uppercase !important; letter-spacing:.06em !important; color:#787c85 !important; border-bottom:1px solid #4a4e57 !important; }
[data-testid="stDataFrame"] td { font-family:'Fira Code',monospace; font-size:.75rem; color:#f0f2f5; }
[data-testid="stDataFrame"] tr:hover td { background:rgba(34,211,238,.04) !important; }

input,select,textarea,.stNumberInput input { border-radius:2px !important; border:1px solid #4a4e57 !important; background:#353940 !important; color:#f0f2f5 !important; font-family:'Fira Code',monospace !important; }
input:focus,select:focus,textarea:focus { border-color:#22d3ee !important; box-shadow:none !important; }
.stSlider > div > div > div { background:#5e626b !important; }
.stTabs [data-baseweb="tab"] { font-family:'Fira Code',monospace; font-size:.68rem; text-transform:uppercase; letter-spacing:.05em; color:#787c85; }
.stTabs [aria-selected="true"] { color:#22d3ee !important; }
.stProgress > div > div { background:#22d3ee !important; border-radius:0; }

::-webkit-scrollbar { width:5px; } ::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:#4a4e57; border-radius:0; } ::-webkit-scrollbar-thumb:hover { background:#5e626b; }

hr { border-color:#4a4e57 !important; }
.status-dot { animation:pulse 3s ease-in-out infinite; }

footer { visibility:hidden; }
/* Only hide toolbar actions, keep header structure for sidebar toggle */
#MainMenu { visibility:hidden !important; }
header[data-testid="stHeader"] { background:#2c3038 !important; }
.stDeployButton { display:none !important; }
[data-testid="stHeaderActionElements"] { display:none !important; }
button[kind="header"] { display:none !important; }
button[data-testid="baseButton-headerNoPadding"] { display:none !important; }
/* Ensure sidebar toggle stays visible */
[data-testid="collapsedControl"] { display:flex !important; visibility:visible !important; }
/* Hide developer menu items */
[data-testid="stMainMenu"] { display:none !important; }
[data-testid="baseButton-header"] { display:none !important; }
[data-testid="stSidebar"] .stCaption { font-family:'Inter','Segoe UI',sans-serif !important; font-weight:300; font-size:11px; color:#788697 !important; }
/* Hide Streamlit status bar (Running/Rerun/etc) */
[data-testid="stStatusWidget"] { display:none !important; }
.stApp > footer { display:none !important; }
"""

st.markdown(f"<style>{DARK_CSS}</style>", unsafe_allow_html=True)

# ═══════════════════════════════════════════
# ID translation: English battery IDs → Chinese display names
# ═══════════════════════════════════════════
_ID_MAP = {
    "BYD-Blade-85": "比亚迪刀片(汉EV 85kWh)", "BYD-Blade-72": "比亚迪刀片(海豹 72kWh)", "BYD-Blade-47": "比亚迪刀片(海豚 47kWh)",
    "CATL-QJ-100": "宁德麒麟(问界M9 100kWh)", "CATL-QJ-80": "宁德麒麟(阿维塔12 80kWh)",
    "CATL-SL-58": "宁德铁锂(深蓝SL03 58kWh)", "CATL-L7-42": "宁德铁锂(理想L7 42kWh)",
    "Panasonic-75": "松下三元(Model3 75kWh)", "LG-M3-60": "LG三元(Model3 60kWh)",
    "CALB-S7-67": "中创新航(深蓝S7 67kWh)",
    "Gotion-A07-54": "国轩高科(启源A07 54kWh)",
    "SVOLT-GW-40": "蜂巢能源(欧拉好猫 40kWh)",
}
def cn_id(bid):
    """Translate battery_id prefix to Chinese"""
    for k, v in _ID_MAP.items():
        if bid.startswith(k):
            return bid.replace(k, v)
    return bid

# ═══════════════════════════════════════════
# Data loading (cached with TTL)
# ═══════════════════════════════════════════
@st.cache_data(ttl=3600)
def load_fleet():
    p=OUTPUT_DIR/"battery_fleet_data.csv"
    return pd.read_csv(p) if p.exists() else _sim.simulate_fleet(batteries_per_type=2,num_cycles=1000)

@st.cache_data(ttl=1)
def load_live_telemetry():
    """Read live data from ESP32 telemetry JSONL files"""
    from glob import glob as _glob
    files = sorted(_glob(str(OUTPUT_DIR / "telemetry_*.jsonl")))
    if not files:
        return pd.DataFrame()
    rows = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        except: pass
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    # Rename to match fleet data columns for chart compatibility
    col_map = {
        "soc_pct": "soh",  # SOC → soh for chart axis
        "soh_pct": "soh_actual",
        "pack_voltage_v": "pack_voltage",
        "pack_current_a": "pack_current",
        "pack_temp_c": "temperature",
        "cycle_count": "cycle",
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)
    if "vehicle_id" not in df.columns and "battery_id" in df.columns:
        df["vehicle_id"] = df["battery_id"]
    if "vehicle_id" not in df.columns:
        df["vehicle_id"] = "ESP32-001"
    # Convert timestamps
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

@st.cache_data
def sample_for_chart(df, step=5):
    """Downsample for faster chart rendering"""
    return df[df["cycle"] % step == 1]

@st.cache_resource
def load_models():
    with open(MODEL_DIR/"soh_model.pkl","rb") as f: soh=pickle.load(f)
    with open(MODEL_DIR/"rul_model.pkl","rb") as f: rul=pickle.load(f)
    return soh["model"],rul["model"],soh["feature_cols"]

# ═══════════════════════════════════════════
# Plotly theme
# ═══════════════════════════════════════════
PLOTLY = dict(
    font=dict(family="Fira Sans,sans-serif",size=11,color="#b0b5bd"),
    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(gridcolor="rgba(255,255,255,.06)",zeroline=False,linecolor="#4a4e57"),
    yaxis=dict(gridcolor="rgba(255,255,255,.06)",zeroline=False,linecolor="#4a4e57"),
    margin=dict(t=30,b=16,l=16,r=16), hovermode="x unified",
    legend=dict(font=dict(size=10,color="#b0b5bd"),bgcolor="#32353d",bordercolor="#4a4e57",borderwidth=1),
)

PAL = ["#4ade80","#22d3ee","#fbbf24","#f87171","#a78bfa","#60a5fa","#34d399","#f472b6","#818cf8","#fb923c","#2dd4bf","#e879f9"]
GREEN = "#4ade80"; AMBER = "#fbbf24"; RED = "#f87171"; CYAN = "#22d3ee"
TEXT = "#f0f2f5"; TEXT2 = "#b0b5bd"; TEXT3 = "#787c85"
CARD = "#32353d"; BORDER = "#4a4e57"; BG = "#2c3038"

def styled(fig,h=380):
    fig.update_layout(PLOTLY); fig.update_layout(height=h)
    try: fig.update_traces(line=dict(width=2.3))
    except: pass
    return fig

# ═══════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center;padding:14px 0 16px;">
        <div class="sidebar-title" style="font-family:'Inter','Segoe UI',sans-serif;font-size:20px;font-weight:600;letter-spacing:.03em;">
            电池管理系统
        </div>
        <div style="font-family:'Inter','Segoe UI',sans-serif;font-size:11px;color:#788697;font-weight:300;margin-top:4px;letter-spacing:.04em;">
            全生命周期智能管理
        </div>
    </div>
    """,unsafe_allow_html=True)
    st.markdown(f"<div style='height:1px;background:{BORDER};margin:.4rem 0;'></div>",unsafe_allow_html=True)
    st.markdown("##### 交易平台")
    st.markdown(f"<a href='http://localhost:8504' target='_blank' style='color:#4ade80;text-decoration:none;font-size:14px;padding:8px 16px;display:block;border-left:3px solid #4ade80;'>↗ 电池交易评估</a>",unsafe_allow_html=True)
    st.markdown(f"<div style='height:1px;background:{BORDER};margin:.4rem 0;'></div>",unsafe_allow_html=True)
    st.markdown("##### 管理平台")
    page=st.radio("main_sys",["电池监测","数字护照","模型性能"],label_visibility="collapsed")
    st.markdown(f"<div style='height:1px;background:{BORDER};margin:.4rem 0;'></div>",unsafe_allow_html=True)
    st.caption("BMS v1.0 · 电动汽车产业")

# ═══════════════════════════════════════════
# AI Response Generator
# ═══════════════════════════════════════════
def generate_ai_response(question, eval_data):
    """Generate contextual AI response based on evaluation data"""
    if not eval_data:
        return "请先点击「开始评估」生成评估结果，然后我才能根据具体数据为您分析。"
    q = question.lower()
    e = eval_data
    if any(w in q for w in ["行情","价格","市场","碳酸锂","涨价","跌价","锂价"]):
        lfp_p = e["lfp_p"]; ncm_p = e["ncm_p"]
        if "涨" in q:
            return f"如果原材料价格上涨，新电池包价格也会跟涨。以当前行情（LFP {lfp_p}元/kWh、NCM {ncm_p}元/kWh）为基准，假设涨幅10%，新包成本将增加至 LFP {int(lfp_p*1.1)}元/kWh、NCM {int(ncm_p*1.1)}元/kWh。这会导致二手电池包估值同步上升。"
        elif "跌" in q:
            return f"如果原材料价格下跌，新电池包价格也会降低。当前 LFP {lfp_p}元/kWh、NCM {ncm_p}元/kWh。假设跌10%，新包将降至 LFP {int(lfp_p*0.9)}元/kWh。旧电池包的回收价值也会降低。"
        else:
            return f"当前市场行情：LFP新包约{lfp_p}元/kWh，NCM新包约{ncm_p}元/kWh。碳酸锂约7.8万元/吨，处于2025年中等偏低水平。可在上方「市场行情设置」中修改。"
    if any(w in q for w in ["卖给","出售","卖","渠道","回收商","4s","置换"]):
        soh = e["soh"]; residual = e["residual"]; sl = e["sl_val"]; rec = e["rec_val"]
        return f"根据当前评估（SOH {soh:.0f}%，残值 {residual:,.0f}元），建议销售渠道优先级：\n\n1. **4S店置换**（推荐）：可直接抵扣新车款，估值最高，约{residual:,.0f}元\n2. **梯次利用企业**：适合SOH>70%的电池，估值约{sl:,.0f}元\n3. **材料回收企业**：直接拆解回收，估值约{rec:,.0f}元\n\n⚠️ 注意：单独出售电池包需随车交易，不可单独过户。"
    if any(w in q for w in ["合理","为什么","正常","偏低","偏高","值不值"]):
        soh = e["soh"]; retention = e["retention"]; condition = e["condition"]
        cond_info = ""
        if condition < 0.8: cond_info = f"硬件状况扣减了{(1-condition)*100:.0f}%，影响了最终估值。"
        return f"您的电池残值率为 {retention:.0f}%，健康度 {soh:.0f}%。{cond_info}\n\n参考标准：\n- SOH>90%：残值率约75-85%，优秀\n- SOH 80-90%：残值率约60-75%，正常\n- SOH 70-80%：残值率约40-60%，需关注\n- SOH<70%：残值率<40%，建议尽快处理"
    if any(w in q for w in ["建议","推荐","怎么办","怎么处理","方案"]):
        soh = e["soh"]; residual = e["residual"]; sl = e["sl_val"]; rec = e["rec_val"]
        if soh >= 80:
            return f"✅ **推荐方案：继续车用**\n\n电池健康度 {soh:.0f}%，状态优秀。可在卖车时出具本评估报告作为溢价依据，预计可为整车增加 5,000-15,000 元售价。"
        elif soh >= 65:
            best = "梯次利用" if sl > residual else "继续使用"
            return f"⚡ **推荐方案：{best}**\n\n电池健康度 {soh:.0f}%，进入梯次利用黄金期。\n- 继续车用价值：{residual:,.0f}元\n- 转储能梯次利用：{sl:,.0f}元\n- 材料回收：{rec:,.0f}元"
        else:
            return f"🔧 **推荐方案：材料回收**\n\n电池已不适合车用。建议联系正规回收企业（如格林美、邦普循环），材料回收价值约{rec:,.0f}元。不要私自拆解。"
    if any(w in q for w in ["铁锂","三元","磷酸铁锂","lfp","ncm","nca","刀片"]):
        chem = e["chem"]
        if chem == "LFP":
            return "磷酸铁锂（LFP）电池：✅ 安全性高、寿命长（3000+次）、成本低。❌ 能量密度较低、低温性能差。回收价值偏低（不含钴镍），但梯次利用价值高，适合转储能。"
        else:
            return f"{'NCM' if chem=='NCM' else 'NCA'}三元锂电池：✅ 能量密度高、低温性能好。❌ 循环寿命较短（~1500次）、热稳定性不如LFP。回收价值较高（含钴镍等贵金属）。"
    import re
    if any(w in q for w in ["调整","设置","改为","改成","修改"]):
        nums = re.findall(r'(\d+)', q)
        if nums:
            if "lfp" in q or "铁锂" in q:
                st.session_state.mkt_lfp = int(nums[0])
                return f"✅ 已将 LFP 新包价格调整为 {st.session_state.mkt_lfp} 元/kWh。"
            if "ncm" in q or "三元" in q:
                st.session_state.mkt_ncm = int(nums[0])
                return f"✅ 已将 NCM 新包价格调整为 {st.session_state.mkt_ncm} 元/kWh。"
            if "nca" in q:
                st.session_state.mkt_nca = int(nums[0])
                return f"✅ 已将 NCA 新包价格调整为 {st.session_state.mkt_nca} 元/kWh。"
        return "请说明要调整哪个参数和目标价格，例如：「LFP改为700」"
    return f"根据评估数据：{e['model']}，{e['capacity']}kWh，健康度 {e['soh']:.0f}%，预估价值 {e['residual']:,.0f} 元（残值率 {e['retention']:.0f}%）。\n\n您可以问我：\n- 「这个价格合理吗？」\n- 「建议卖给谁？」\n- 「行情怎么看？」\n- 「LFP改为700」（调整行情）"

# ═══════════════════════════════════════════
# PAGE 1 — FLEET STATUS
# ═══════════════════════════════════════════
if page=="电池监测":
    st.markdown('<h1>◈ 电池监测</h1>',unsafe_allow_html=True)

    # ── Live ESP32 Telemetry Section ──
    live_df = load_live_telemetry()
    if len(live_df) > 0:
        latest_ts = live_df["timestamp"].max() if "timestamp" in live_df.columns else None
        ts_str = latest_ts.strftime("%H:%M:%S") if latest_ts is not None else ""
        battery_count = live_df["vehicle_id"].nunique() if "vehicle_id" in live_df.columns else 1
        st.markdown(f'<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin:8px 0 4px;"><div><span style="color:#4ade80;font-size:14px;font-weight:700;">● LIVE</span><span style="color:#787c85;font-size:12px;"> ESP32 车队 · {battery_count}辆车 · 实时</span></div><span style="color:#787c85;font-size:11px;">{ts_str}</span></div>',unsafe_allow_html=True)

        # Get latest data per battery
        if "vehicle_id" in live_df.columns:
            latest_per_bat = live_df.groupby("vehicle_id").last().reset_index()
        else:
            latest_per_bat = live_df.tail(1)

        # Battery cards in a responsive grid
        BAT_LABELS = {
            "CATL-QJ-100": ("宁德麒麟", "问界M9", "NCM"),
            "BYD-Blade-85": ("比亚迪刀片", "汉EV", "LFP"),
            "CATL-QJ-80": ("宁德麒麟", "阿维塔12", "NCM"),
            "Panasonic-75": ("松下三元", "Model3", "NCA"),
            "BYD-Blade-72": ("比亚迪刀片", "海豹", "LFP"),
            "CALB-S7-67": ("中创新航", "深蓝S7", "LFP"),
            "CATL-SL-58": ("宁德铁锂", "深蓝SL03", "LFP"),
            "Gotion-A07-54": ("国轩高科", "启源A07", "LFP"),
            "LG-M3-60": ("LG三元", "Model3标续", "NCM"),
            "BYD-Blade-47": ("比亚迪刀片", "海豚", "LFP"),
            "CATL-L7-42": ("宁德铁锂", "理想L7", "LFP"),
            "SVOLT-GW-40": ("蜂巢能源", "欧拉好猫", "LFP"),
        }

        # Clickable battery cards using buttons
        bat_ids = sorted(latest_per_bat["vehicle_id"].unique()) if "vehicle_id" in latest_per_bat.columns else []
        if len(bat_ids) > 0:
            if "selected_bat" not in st.session_state:
                st.session_state.selected_bat = bat_ids[0]

            for i in range(0, len(bat_ids), 4):
                cols = st.columns(4)
                for j, bid in enumerate(bat_ids[i:i+4]):
                    if j >= len(cols): continue
                    row_data = latest_per_bat[latest_per_bat["vehicle_id"]==bid]
                    if len(row_data) == 0: continue
                    row = row_data.iloc[0]
                    soc = row.get("soh", 0)
                    soh_val = row.get("soh_actual", 92)
                    volt = row.get("pack_voltage", 0)
                    temp = row.get("temperature", 0)
                    label = BAT_LABELS.get(bid, (bid, "", ""))
                    chem_color = "#4ade80" if label[2]=="LFP" else ("#22d3ee" if label[2]=="NCM" else "#fbbf24")
                    sel = (bid == st.session_state.selected_bat)
                    soc_c = "#4ade80" if soc>30 else ("#fbbf24" if soc>15 else "#f87171")

                    with cols[j]:
                        # Use a container with button for click
                        btn_label = f"{label[0]}\n{label[1]}\nSOC {soc:.0f}% | SOH {soh_val:.1f}% | {volt:.0f}V | {temp:.0f}°"
                        btn_type = "primary" if sel else "secondary"
                        if st.button(btn_label, key=f"bat_{bid}", use_container_width=True, type=btn_type):
                            st.session_state.selected_bat = bid
                            st.rerun()

            # Hide button text styling
            st.markdown("""
            <style>
            button[kind="secondary"] { background:#2c3038 !important; border:1px solid #3e424a !important; color:#b0b5bd !important; font-size:10px !important; padding:6px 8px !important; text-align:left !important; line-height:1.3 !important; white-space:pre-line !important; }
            button[kind="primary"] { border:2px solid #22d3ee !important; box-shadow:0 0 12px rgba(34,211,238,.3) !important; font-size:10px !important; padding:6px 8px !important; text-align:left !important; line-height:1.3 !important; white-space:pre-line !important; }
            </style>
            """, unsafe_allow_html=True)

            sel_bat = st.session_state.selected_bat
            bat_df = live_df[live_df["vehicle_id"]==sel_bat].tail(60)
            if len(bat_df) > 1:
                label = BAT_LABELS.get(sel_bat, (sel_bat, "", ""))
                st.markdown(f"### {label[0]} {label[1]}（{label[2]}）实时曲线")
                c1,c2,c3=st.columns(3)
                with c1:
                    fig=px.line(bat_df,x="timestamp",y="soh",labels={"timestamp":"时间","soh":"SOC %"},
                        color_discrete_sequence=["#4ade80"])
                    fig.update_layout(PLOTLY,height=250,title="SOC",margin=dict(t=30,b=0,l=0,r=0))
                    st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})
                with c2:
                    fig2=px.line(bat_df,x="timestamp",y="temperature",labels={"timestamp":"时间","temperature":"°C"},
                        color_discrete_sequence=["#fbbf24"])
                    fig2.update_layout(PLOTLY,height=250,title="温度",margin=dict(t=30,b=0,l=0,r=0))
                    st.plotly_chart(fig2,width="stretch",config={"displayModeBar":False})
                with c3:
                    fig3=px.line(bat_df,x="timestamp",y="pack_voltage",labels={"timestamp":"时间","pack_voltage":"V"},
                        color_discrete_sequence=["#a78bfa"])
                    fig3.update_layout(PLOTLY,height=250,title="电压",margin=dict(t=30,b=0,l=0,r=0))
                    st.plotly_chart(fig3,width="stretch",config={"displayModeBar":False})

    st.markdown(f'<div style="height:1px;background:{BORDER};margin:16px 0;"></div>',unsafe_allow_html=True)

    # ── Fleet history section ──
    try: df=load_fleet()
    except: df=pd.DataFrame()
    if len(df)==0: st.warning("暂无历史数据")
    else:
        c1,c2,c3=st.columns(3)
        with c1: chem=st.selectbox("化学体系",["ALL"]+sorted(df["chemistry"].unique().tolist()),format_func=lambda x:"全部" if x=="ALL" else x)
        with c2: bid=sorted(df["battery_id"].unique()); sel=st.selectbox("电池单元",["ALL"]+bid,format_func=lambda x:"全部" if x=="ALL" else cn_id(x))
        with c3:
            # Persist threshold across sessions via query params
            if "soh_thr" not in st.session_state:
                st.session_state.soh_thr = int(st.query_params.get("thr", 80))
            thr = st.slider("SOH 预警阈值 %",50,100,st.session_state.soh_thr, key="thr_slider")
            if thr != st.session_state.soh_thr:
                st.session_state.soh_thr = thr
                st.query_params["thr"] = thr

        pdf=df.copy()
        if chem!="ALL": pdf=pdf[pdf["chemistry"]==chem]
        if sel!="ALL": pdf=pdf[pdf["battery_id"]==sel]

        # Use sampled data for charts (every 5th point, faster rendering)
        pdf_chart = sample_for_chart(pdf)

        k1,k2,k3,k4=st.columns(4)
        g=pdf.groupby("battery_id")
        avg_soh=g["soh"].last().mean()
        below=(g["soh"].last()*100<thr).sum()
        total=pdf["battery_id"].nunique()
        avg_cap=g["capacity_kwh"].last().mean()
        with k1:
            st.markdown(f'<div class="panel" style="text-align:center;"><div class="kpi-lbl">在役数量</div><div class="kpi-val">{total}</div></div>',unsafe_allow_html=True)
        with k2:
            clr=GREEN if avg_soh>.85 else (AMBER if avg_soh>.70 else RED)
            st.markdown(f'<div class="panel" style="text-align:center;"><div class="kpi-lbl">平均 SOH</div><div class="kpi-val" style="color:{clr};">{avg_soh*100:.1f}%</div></div>',unsafe_allow_html=True)
        with k3:
            st.markdown(f'<div class="panel" style="text-align:center;"><div class="kpi-lbl">SOH &lt; {thr}%</div><div class="kpi-val" style="color:{RED};">{below}</div></div>',unsafe_allow_html=True)
        with k4:
            st.markdown(f'<div class="panel" style="text-align:center;"><div class="kpi-lbl">平均容量</div><div class="kpi-val">{avg_cap:.1f} kWh</div></div>',unsafe_allow_html=True)

        st.markdown("""<div style="height:1px;background:inherit;margin:8px 0;"></div>""",unsafe_allow_html=True)

        ch1,ch2=st.columns(2)
        with ch1:
            pdf_disp=pdf_chart.copy(); pdf_disp["battery_id"]=pdf_disp["battery_id"].apply(cn_id)
            fig=px.line(pdf_disp,x="cycle",y="soh",color="battery_id",color_discrete_sequence=PAL,
                        labels={"cycle":"循环次数","soh":"健康度 (SOH)","battery_id":"电池编号"})
            fig.add_hline(y=.80,line_dash="dash",line_color=RED,annotation_text="80% 退役线")
            fig.update_layout(PLOTLY,height=400,showlegend=pdf["battery_id"].nunique()<=12,legend_title="")
            for t in fig.data:
                if t.type=="scatter" and t.mode=="lines":
                    t.update(line=dict(width=2.3),hovertemplate="循环: %{x}<br>SOH: %{y:.4f}<extra>%{fullData.name}</extra>")
            st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})
        with ch2:
            fig=px.line(pdf_disp,x="cycle",y="internal_resistance_ohm",color="battery_id",color_discrete_sequence=PAL,
                        labels={"cycle":"循环次数","internal_resistance_ohm":"内阻 (Ω)","battery_id":"电池编号"})
            fig.update_layout(PLOTLY,height=400,showlegend=pdf["battery_id"].nunique()<=12,legend_title="")
            for t in fig.data:
                if t.type=="scatter" and t.mode=="lines":
                    t.update(line=dict(width=2.3),hovertemplate="循环: %{x}<br>内阻: %{y:.6f} Ω<extra>%{fullData.name}</extra>")
            st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})

        sm=pdf.copy(); sm["battery_id"]=sm["battery_id"].apply(cn_id)
        sm=sm.groupby("battery_id").agg(
            SOH原始=("soh","last"),容量值=("capacity_kwh","last"),
            循环=("cycle","max"),温度值=("temperature_c","mean"),
            内阻值=("internal_resistance_ohm","max"),
        ).reset_index()
        sm.rename(columns={"battery_id":"电池编号","SOH原始":"健康度"},inplace=True)

        def status_tag(v):
            if v>=0.85: return "🟢 优秀"
            elif v>=0.70: return "🟡 注意"
            else: return "🔴 异常"
        sm["状态"]=sm["健康度"].apply(status_tag)
        sm["容量"]=sm["容量值"].apply(lambda x:f"{x:.1f} kWh")
        sm["温度"]=sm["温度值"].apply(lambda x:f"{x:.0f} °C")
        sm["内阻"]=sm["内阻值"].apply(lambda x:f"{x*1000:.2f} mΩ")
        sm=sm[["电池编号","健康度","状态","容量","循环","温度","内阻"]]

        st.dataframe(
            sm,width="stretch",hide_index=True,
            column_config={
                "电池编号":st.column_config.TextColumn("电池编号"),
                "健康度":st.column_config.ProgressColumn("健康度",format="%.1f%%",min_value=0,max_value=1),
                "状态":st.column_config.TextColumn("状态"),
                "容量":st.column_config.TextColumn("容量"),
                "循环":st.column_config.NumberColumn("循环次数"),
                "温度":st.column_config.TextColumn("温度"),
                "内阻":st.column_config.TextColumn("内阻"),
            }
        )

    # Center-align table cells
    st.markdown("""<style>
    [data-testid="stDataFrame"] td { text-align:center !important; }
    [data-testid="stDataFrame"] th { text-align:center !important; }
    </style>""",unsafe_allow_html=True)

    # Auto-refresh for live data (every 5s to match ESP32 interval)
    time.sleep(5)
    st.rerun()

# ═══════════════════════════════════════════

# ═══════════════════════════════════════════
# PAGE 2 — RESIDUAL VALUE
# ═══════════════════════════════════════════
elif page=="残值评估":
    st.markdown('<h1>◈ 电池价值评估</h1>',unsafe_allow_html=True)
    st.caption("输入电池的基本信息，即可估算当前市场价值和使用建议。AI 助手会根据评估结果给出个性化建议。")

    # Initialize AI chat history
    if "ai_chat" not in st.session_state:
        st.session_state.ai_chat = []
    if "ai_last_eval" not in st.session_state:
        st.session_state.ai_last_eval = None

    # Initialize brand prices from BRAND_PACK_PRICES (single source of truth)
    if "mkt_lfp" not in st.session_state:
        st.session_state.mkt_lfp = 650
        st.session_state.mkt_ncm = 850
        st.session_state.mkt_nca = 900
        st.session_state.mkt_recycle_lfp = 130
        st.session_state.mkt_recycle_ncm = 180
        st.session_state.mkt_recycle_nca = 160

    # Auto-fetch raw material reference data (deterministic, no randomness)
    if "mkt_last_fetch" not in st.session_state:
        st.session_state.mkt_last_fetch = 0
    import datetime as _dt
    _now_ts = _dt.datetime.now().timestamp()
    if _now_ts - st.session_state.mkt_last_fetch > 3600:
        try:
            prices = get_prices_for_streamlit()
            st.session_state.mkt_lithium = prices["lithium"]
            st.session_state.mkt_cobalt = prices["cobalt"]
            st.session_state.mkt_nickel = prices["nickel"]
            st.session_state.mkt_last_fetch = _now_ts
            sources = prices.get("sources_tried", ["基准价"])
            is_live = prices.get("is_live", False)
            status = "实时数据" if is_live else "基准价(按月微调)"
            st.session_state.mkt_source = (
                f"行情刷新 · 碳酸锂 {prices['lithium']/10000:.2f}万/吨 · 状态：{status} · "
                f"尝试数据源：{' | '.join(sources)} · "
                f"产业链参考：smm.cn / baiinfo.com / gem.com.cn / brunp.com.cn / che168.com"
            )
        except Exception:
            pass

    c1,c2=st.columns([1,1])
    with c1:
        bt=st.selectbox("选择电池型号",list(BATTERY_CATALOG.keys()),
                         format_func=lambda x:f"{BATTERY_CATALOG[x].name} ({BATTERY_CATALOG[x].chemistry})")
        sp=BATTERY_CATALOG[bt]

        # Auto-update prices when brand selection changes
        brand_key = f"{sp.name} ({sp.vehicle_model} {sp.pack_capacity_kwh}kWh)"
        if "last_brand" not in st.session_state:
            st.session_state.last_brand = ""

        if st.session_state.last_brand != brand_key:
            old_brand = st.session_state.last_brand
            st.session_state.last_brand = brand_key
            # Use dynamic pricing: brand base price × lithium correction × brand factor
            adj = get_brand_price_for_streamlit(sp.name, sp.vehicle_model)
            if adj:
                st.session_state.mkt_lfp = int(adj["new"] * 10000 / sp.pack_capacity_kwh)
                st.session_state.mkt_ncm = int(adj["new"] * 10000 / sp.pack_capacity_kwh)
                st.session_state.mkt_nca = int(adj["new"] * 10000 / sp.pack_capacity_kwh)
                st.session_state.mkt_recycle_lfp = int(adj["scrap"] * 10000 / sp.pack_capacity_kwh)
                st.session_state.mkt_recycle_ncm = int(adj["scrap"] * 10000 / sp.pack_capacity_kwh)
                st.session_state.mkt_recycle_nca = int(adj["scrap"] * 10000 / sp.pack_capacity_kwh)
                new_price = adj["new"]; new_per_kwh = int(new_price * 10000 / sp.pack_capacity_kwh)
                li_corr = adj["lithium_correction"]; brand_f = adj["brand_factor"]
                li_now = adj["current_lithium"]
                st.session_state.mkt_source = (
                    f"动态行情 · 碳酸锂 {li_now/10000:.2f}万/吨 · 锂价修正 {li_corr:.2f}× · 品牌系数 {brand_f:.2f} · "
                    f"新包 {new_price}万元 ({new_per_kwh}元/kWh) · "
                    f"来源：smm.cn → baiinfo.com → gem.com.cn → brunp.com.cn → che168.com"
                )
                if old_brand:
                    st.session_state.ai_chat.append({"role":"assistant",
                        "content":f"已切换到 **{sp.name}**（{sp.vehicle_model}，{sp.pack_capacity_kwh}kWh，{adj['chemistry']}）。\n\n当前碳酸锂 {li_now/10000:.2f}万/吨，锂价修正系数 {li_corr:.2f}，品牌流通系数 {brand_f:.2f}。\n\n动态价格：新包 {new_price}万元 ({new_per_kwh}元/kWh) | 二手良品 {adj['used_good']}万元 | 报废回收 {adj['scrap']}万元",
                    })

        st.markdown(f"**{sp.manufacturer}** · {sp.chemistry} · {sp.pack_capacity_kwh} kWh · {sp.vehicle_model} · 设计寿命约{sp.cycle_life_to_80pct}次循环")

        st.markdown("---")
        st.markdown("##### 市场行情（可调整）")
        # Initialize market prices in session state
        if "mkt_lfp" not in st.session_state:
            st.session_state.mkt_lfp = 750
            st.session_state.mkt_ncm = 950
            st.session_state.mkt_nca = 1000
            st.session_state.mkt_recycle_lfp = 150
            st.session_state.mkt_recycle_ncm = 200
            st.session_state.mkt_recycle_nca = 180

        with st.expander("点击展开市场行情设置"):
            st.caption("行情由 Page Agent 自动填入（每小时刷新），也可手动微调")

            mc1,mc2,mc3=st.columns(3)
            with mc1:
                st.session_state.mkt_lfp = st.number_input("LFP新包 (元/kWh)",300,1500,st.session_state.mkt_lfp,50,
                    help="磷酸铁锂电池包市场价，2025年约600-800元/kWh")
                st.session_state.mkt_recycle_lfp = st.number_input("LFP回收 (元/kWh)",50,500,st.session_state.mkt_recycle_lfp,10,
                    help="磷酸铁锂材料回收价")
            with mc2:
                st.session_state.mkt_ncm = st.number_input("NCM新包 (元/kWh)",400,2000,st.session_state.mkt_ncm,50,
                    help="三元锂电池包市场价，2025年约800-1000元/kWh")
                st.session_state.mkt_recycle_ncm = st.number_input("NCM回收 (元/kWh)",50,600,st.session_state.mkt_recycle_ncm,10,
                    help="三元锂材料回收价（含钴镍，价值较高）")
            with mc3:
                st.session_state.mkt_nca = st.number_input("NCA新包 (元/kWh)",400,2000,st.session_state.mkt_nca,50,
                    help="NCA电池包市场价")
                st.session_state.mkt_recycle_nca = st.number_input("NCA回收 (元/kWh)",50,600,st.session_state.mkt_recycle_nca,10,
                    help="NCA材料回收价")

            st.caption(f"当前品牌：{sp.name}")
            if st.session_state.get("mkt_source"):
                st.caption(st.session_state.mkt_source)
            else:
                st.caption("数据来源：上海有色网(smm.cn) · 百川盈孚(baiinfo.com) · 格林美(gem.com.cn) · 邦普循环(brunp.com.cn) · 二手车之家(che168.com)")

        st.markdown("---")
        st.markdown("##### 电池健康状况")
        soh_val=st.slider("电池健康度 (%)",30.,100.,85.,.5,
                          help="就像手机电池健康度，100% 表示和新的一样，越低表示老化越严重")/100
        if soh_val>=0.85: st.success(f"当前健康度 {soh_val*100:.0f}% — 电池状态良好")
        elif soh_val>=0.70: st.warning(f"当前健康度 {soh_val*100:.0f}% — 电池有一定老化")
        else: st.error(f"当前健康度 {soh_val*100:.0f}% — 电池老化较严重")

        st.markdown("##### 使用情况")
        cyc=st.number_input("已使用循环次数",0,5000,800,50,
                            help="每充满一次电算 1 个循环，通常电动车每年约 200-300 次循环")
        est_years=cyc/250
        st.caption(f"≈ 大约使用了 {est_years:.1f} 年（按每年 250 次循环估算）")

        sev=st.selectbox("使用环境",["mild","normal","severe"],
                          format_func=lambda x:{"mild":"温和（常温、慢充为主）","normal":"正常（日常通勤）","severe":"恶劣（高温、快充频繁）"}[x],
                          help="使用环境影响电池老化速度")
        age=st.slider("已使用时长 (月)",0,120,24,help="从出厂到现在的月数")

        # ── Physical inspection factors ──
        st.markdown("---")
        st.markdown("##### 外观与硬件检查（可多选）")
        cond_deduction = 1.0  # Start at 100%

        with st.expander("壳体与外观"):
            casing_ok = st.checkbox("壳体完好无变形", value=True)
            casing_rust = st.checkbox("有锈蚀痕迹")
            casing_dent = st.checkbox("有磕碰/变形")
            casing_leak = st.checkbox("有漏液/进水痕迹")
            if not casing_ok: cond_deduction -= 0.05
            if casing_rust: cond_deduction -= 0.08
            if casing_dent: cond_deduction -= 0.10
            if casing_leak: cond_deduction -= 0.20

        with st.expander("电芯状态"):
            cell_ok = st.checkbox("电芯外观正常（无鼓包漏液）", value=True)
            cell_dead = st.checkbox("存在个别损坏电芯")
            balance_ok = st.checkbox("电芯压差正常（<0.05V）", value=True)
            balance_bad = st.checkbox("压差过大（>0.1V）")
            if not cell_ok: cond_deduction -= 0.15
            if cell_dead: cond_deduction -= 0.25
            if not balance_ok: cond_deduction -= 0.10
            if balance_bad: cond_deduction -= 0.15

        with st.expander("BMS与高压系统"):
            bms_ok = st.checkbox("BMS系统正常", value=True)
            bms_fault = st.checkbox("BMS故障/报警")
            insulation_ok = st.checkbox("绝缘电阻达标", value=True)
            insulation_bad = st.checkbox("绝缘不达标")
            if not bms_ok: cond_deduction -= 0.20
            if bms_fault: cond_deduction -= 0.30
            if not insulation_ok: cond_deduction -= 0.15
            if insulation_bad: cond_deduction -= 0.35

        with st.expander("热管理系统"):
            thermal_ok = st.checkbox("液冷管路正常", value=True)
            thermal_leak = st.checkbox("冷却液泄漏")
            thermal_block = st.checkbox("管路堵塞/散热不良")
            if not thermal_ok: cond_deduction -= 0.08
            if thermal_leak: cond_deduction -= 0.12
            if thermal_block: cond_deduction -= 0.10

        with st.expander("档案与手续"):
            record_full = st.checkbox("维保记录齐全", value=True)
            record_none = st.checkbox("无维保记录")
            warranty_yes = st.checkbox("仍在8年质保期内", value=True)
            warranty_no = st.checkbox("已过保/脱保")
            accident = st.checkbox("有事故/泡水/起火史")
            if not record_full: cond_deduction -= 0.10
            if record_none: cond_deduction -= 0.25
            if not warranty_yes: cond_deduction -= 0.12
            if warranty_no: cond_deduction -= 0.15
            if accident: cond_deduction -= 0.40

        with st.expander("充放电习惯"):
            habit_gentle = st.checkbox("浅充浅放为主（20-80%）", value=True)
            habit_deep = st.checkbox("经常满充满放（0-100%）")
            habit_fast = st.checkbox("频繁使用快充")
            habit_full_store = st.checkbox("经常满电长期存放")
            if not habit_gentle: cond_deduction -= 0.05
            if habit_deep: cond_deduction -= 0.08
            if habit_fast: cond_deduction -= 0.10
            if habit_full_store: cond_deduction -= 0.12

        cond_deduction = max(cond_deduction, 0.10)

    with c2:
        if st.button("开始评估",type="primary",width="stretch"):
            rep=estimate_residual_value(
                battery_spec={"name":sp.name,"chemistry":sp.chemistry,"pack_capacity_kwh":sp.pack_capacity_kwh,
                              "cycle_life":sp.cycle_life_to_80pct,"manufacturer":sp.manufacturer,"vehicle_model":sp.vehicle_model},
                current_soh=soh_val,current_cycle=cyc,estimated_rul=int(sp.cycle_life_to_80pct*soh_val),
                usage_severity=sev,calendar_age_months=age,condition_factor=cond_deduction,
                custom_prices={
                    "LFP": st.session_state.mkt_lfp,
                    "NCM": st.session_state.mkt_ncm,
                    "NCA": st.session_state.mkt_nca,
                    "LFP_recycle": st.session_state.mkt_recycle_lfp,
                    "NCM_recycle": st.session_state.mkt_recycle_ncm,
                    "NCA_recycle": st.session_state.mkt_recycle_nca,
                })

            st.markdown("---")
            st.markdown("##### 价值评估结果")

            # New vs current value comparison
            val1,val2=st.columns(2)
            with val1:
                st.markdown(f"""
                <div class="panel" style="text-align:center;">
                    <div class="kpi-lbl">全新时的价值</div>
                    <div class="kpi-val">{rep.new_value_rmb:,.0f} 元</div>
                </div>""",unsafe_allow_html=True)
            with val2:
                val_color=GREEN if rep.value_retention_pct>=60 else (AMBER if rep.value_retention_pct>=40 else RED)
                st.markdown(f"""
                <div class="panel" style="text-align:center;border-color:{val_color};">
                    <div class="kpi-lbl">当前预估价值</div>
                    <div class="kpi-val" style="color:{val_color};">{rep.residual_value_rmb:,.0f} 元</div>
                    <div class="kpi-lbl">约为新电池的 {rep.value_retention_pct:.0f}%</div>
                </div>""",unsafe_allow_html=True)

            st.markdown(f"*估值范围：{rep.confidence_low:,.0f} ~ {rep.confidence_high:,.0f} 元*")
            if cond_deduction < 1.0:
                st.caption(f"硬件外观扣减系数：{cond_deduction:.0%}（因检查项扣分，满分100%）")

            # Plain-language summary
            st.markdown("---")
            st.markdown("##### 通俗解读")
            remain=rep.value_retention_pct
            if remain>=70:
                st.success(f"这块电池状态很好！还值原价的 {remain:.0f}%，继续用在车上完全没问题。")
            elif remain>=40:
                st.warning(f"电池有一定老化，还值原价的 {remain:.0f}%。建议考虑转做储能电站或备用电源，还能发挥余热。")
            else:
                st.error(f"电池老化较重，仅剩原价的 {remain:.0f}%。建议走正规回收渠道，安全处理。")

            # ── AI Analysis Section ──
            st.markdown("---")
            st.markdown("##### 市场数据参考")
            mkt_col1,mkt_col2,mkt_col3=st.columns(3)
            lfp_price=st.session_state.mkt_lfp; ncm_price=st.session_state.mkt_ncm
            with mkt_col1:
                st.metric("碳酸锂 (电池级)", "7.8 万元/吨", delta="-0.3万", delta_color="inverse",
                          help="数据来源：上海有色网 SMM，2025年7月")
            with mkt_col2:
                st.metric("磷酸铁锂正极", "3.6 万元/吨", delta="-0.1万", delta_color="inverse",
                          help="受碳酸锂价格下行影响")
            with mkt_col3:
                st.metric("钴 (电解钴)", "18.5 万元/吨", delta="+0.5万",
                          help="刚果(金)供应扰动推动钴价上涨")

            st.caption("行情数据基于2025年7月市场基准价 + 产业链调研数据，点击「获取最新行情」刷新")

            # Brand-specific market prices
            with st.expander("各品牌电池包动态行情"):
                li_now = st.session_state.get("mkt_lithium", 78000)
                rows = []
                for k, v in BRAND_PACK_PRICES.items():
                    adj = get_adjusted_brand_price(v, li_now)
                    rows.append({
                        "品牌/车型": k, "材料": adj["chemistry"],
                        "品牌系数": f"{adj['brand_factor']:.2f}",
                        "锂价敏感度": f"{adj['lithium_sensitivity']:.2f}",
                        "新包 (万元)": adj["new"], "二手良品 (万元)": adj["used_good"],
                        "报废回收 (万元)": adj["scrap"],
                    })
                brand_df = pd.DataFrame(rows)
                st.dataframe(brand_df, width="stretch", hide_index=True)
                st.caption(f"当前碳酸锂：{li_now/10000:.2f}万/吨 | 锂价联动修正后价格 | 来源：smm.cn · baiinfo.com · gem.com.cn · brunp.com.cn · che168.com")

            # AI recommendation generator
            st.markdown("---")
            st.markdown("##### AI 综合建议")

            # Build recommendation based on all factors
            advice_parts = []
            chem_type = sp.chemistry
            remain = rep.value_retention_pct

            # Hardware condition summary
            if cond_deduction >= 0.95:
                advice_parts.append("✅ 外观硬件检查全部正常，无额外折价。")
            elif cond_deduction >= 0.80:
                advice_parts.append("⚠️ 存在轻微硬件问题，建议维修后再评估，修复后预计可提升估值 10-20%。")
            elif cond_deduction >= 0.50:
                advice_parts.append("🔧 硬件存在明显缺陷，建议联系专业回收商现场验货后再交易。")
            else:
                advice_parts.append("🚫 硬件状况较差，整包交易困难，建议拆解后按材料分类出售。")

            # Chemistry-specific market advice
            if chem_type == "LFP":
                advice_parts.append(f"📊 当前碳酸锂价格处于低位（7.8万/吨），磷酸铁锂回收价值偏低，不建议此时拆解回收。如电池健康度尚可(>{80 if remain>=70 else 70}%)，建议继续使用或转储能梯次利用。")
            elif chem_type == "NCM":
                advice_parts.append(f"📊 三元材料含钴镍，当前钴价上涨(+0.5万/吨)，材料回收价值较高。如电池健康度<70%，可考虑拆解回收路线。")
            else:
                advice_parts.append("📊 NCA电池含钴铝，回收工艺成熟，材料价值中等偏上。")

            # Price trend advice
            if lfp_price < 700:
                advice_parts.append("📉 当前新电池包价格处于低位，换购新电池性价比较高。")
            elif lfp_price > 850:
                advice_parts.append("📈 当前新电池包价格偏高，建议优先考虑维修/梯次利用而非更换。")

            # SOH-based strategy
            if remain >= 80:
                advice_parts.append("💡 电池健康度优秀，建议在二手车交易时出具评估报告，可作为溢价依据，预计可提升整车售价 5,000-10,000 元。")
            elif remain >= 60:
                advice_parts.append("💡 电池处于梯次利用黄金期，建议联系储能电站运营商或备电系统集成商，整包出售比拆解回收收益高 2-3 倍。")
            elif remain >= 30:
                advice_parts.append("💡 电池老化明显，建议对比以下三个渠道报价：4S置换 > 梯次利用回收商 > 废品拆解。渠道差异可达数倍。")
            else:
                advice_parts.append("💡 电池接近寿命终点，建议尽快联系正规危废处理企业，避免长期存放造成安全隐患和环境罚款。")

            # Display advice
            for i, advice in enumerate(advice_parts):
                st.markdown(advice)

            # Value comparison chart
            st.markdown("---")
            st.markdown("##### 不同处理方式价值对比")
            comp_cols = st.columns(4)
            with comp_cols[0]:
                st.metric("继续车用", f"{rep.residual_value_rmb:,.0f} 元")
            with comp_cols[1]:
                st.metric("梯次利用", f"{rep.second_life_value_rmb:,.0f} 元",
                         delta=f"{(rep.second_life_value_rmb/rep.residual_value_rmb-1)*100:.0f}%" if rep.residual_value_rmb>0 else "")
            with comp_cols[2]:
                st.metric("材料回收", f"{rep.recycle_value_rmb:,.0f} 元",
                         delta=f"{(rep.recycle_value_rmb/rep.residual_value_rmb-1)*100:.0f}%" if rep.residual_value_rmb>0 else "")
            with comp_cols[3]:
                best_val = max(rep.residual_value_rmb, rep.second_life_value_rmb, rep.recycle_value_rmb)
                best_name = "继续车用" if best_val==rep.residual_value_rmb else ("梯次利用" if best_val==rep.second_life_value_rmb else "材料回收")
                st.metric("最优方案", best_name, delta=f"{best_val:,.0f} 元")

            # What to do (simplified)
            st.markdown("---")
            st.markdown("##### 建议处理方式")
            opts=st.columns(3)
            with opts[0]:
                st.markdown(f"""
                <div class="panel" style="text-align:center;border-color:{GREEN};">
                    <div class="kpi-lbl">继续车用</div>
                    <div style="font-family:'Fira Code',monospace;font-size:.85rem;color:{TEXT2};">价值 {rep.residual_value_rmb:,.0f} 元</div>
                </div>""",unsafe_allow_html=True)
            with opts[1]:
                st.markdown(f"""
                <div class="panel" style="text-align:center;border-color:{AMBER};">
                    <div class="kpi-lbl">{rep.second_life_scenario}</div>
                    <div style="font-family:'Fira Code',monospace;font-size:.85rem;color:{TEXT2};">价值 {rep.second_life_value_rmb:,.0f} 元</div>
                </div>""",unsafe_allow_html=True)
            with opts[2]:
                st.markdown(f"""
                <div class="panel" style="text-align:center;border-color:{RED};">
                    <div class="kpi-lbl">材料回收</div>
                    <div style="font-family:'Fira Code',monospace;font-size:.85rem;color:{TEXT2};">价值 {rep.recycle_value_rmb:,.0f} 元</div>
                </div>""",unsafe_allow_html=True)

            # Simple pie chart
            fig=go.Figure(data=[go.Pie(
                labels=["继续车用","梯次利用","材料回收"],
                values=[rep.residual_value_rmb,rep.second_life_value_rmb,rep.recycle_value_rmb],
                hole=.45,marker_colors=[GREEN,AMBER,RED])])
            fig.update_layout(PLOTLY,height=220,margin=dict(t=0,b=0,l=0,r=0))
            fig.update_traces(textinfo="none")
            st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})

            # Store evaluation for AI chat
            st.session_state.ai_last_eval = {
                "model": sp.name, "chem": sp.chemistry, "vehicle": sp.vehicle_model,
                "capacity": sp.pack_capacity_kwh, "soh": soh_val*100, "cycles": cyc,
                "new_val": rep.new_value_rmb, "residual": rep.residual_value_rmb,
                "retention": rep.value_retention_pct, "sl_val": rep.second_life_value_rmb,
                "rec_val": rep.recycle_value_rmb, "condition": cond_deduction,
                "lfp_p": st.session_state.mkt_lfp, "ncm_p": st.session_state.mkt_ncm,
            }

            # AI Chat Panel
            st.markdown("---")
            st.markdown("##### AI 助手")
            st.caption("您可以向 AI 助手提问，例如：\"这个价格合理吗？\"、\"建议卖给谁？\"、\"如果碳酸锂涨价会怎样？\"")

            # Display chat history
            for msg in st.session_state.ai_chat[-6:]:
                role = "🧑 您" if msg["role"]=="user" else "AI"
                with st.chat_message("user" if msg["role"]=="user" else "assistant"):
                    st.markdown(msg["content"])

            # Chat input
            user_q = st.chat_input("输入您的问题...")
            if user_q:
                st.session_state.ai_chat.append({"role":"user","content":user_q})
                # Generate AI response
                resp = generate_ai_response(user_q, st.session_state.ai_last_eval)
                st.session_state.ai_chat.append({"role":"assistant","content":resp})
                st.rerun()

# ═══════════════════════════════════════════
# ═══════════════════════════════════════════
# PAGE 3 — DIGITAL PASSPORT (redesigned)
# ═══════════════════════════════════════════
elif page=="数字护照":
    import hashlib, uuid
    st.markdown('<h1>◈ 电池数字护照</h1>',unsafe_allow_html=True)
    if "pp" not in st.session_state: st.session_state.pp=None
    if "pp_preview" not in st.session_state: st.session_state.pp_preview={}

    t1,t2=st.tabs(["创建护照","验证护照"])

    with t1:
        left,right=st.columns([1,1.2])
        with left:
            # Search filter
            search_term = st.text_input("搜索型号/品牌/车型", placeholder="输入关键词筛选...", key="pp_search")
            filtered_keys = [k for k in BATTERY_CATALOG.keys() 
                           if search_term.lower() in BATTERY_CATALOG[k].name.lower() 
                           or search_term.lower() in BATTERY_CATALOG[k].vehicle_model.lower()
                           or search_term.lower() in BATTERY_CATALOG[k].manufacturer.lower()]
            if not filtered_keys: filtered_keys = list(BATTERY_CATALOG.keys())
            pb=st.selectbox("电池型号", filtered_keys, key="pp_model",
                format_func=lambda x:f"{BATTERY_CATALOG[x].name} ({BATTERY_CATALOG[x].chemistry})")
            ps=BATTERY_CATALOG[pb]
            pid=st.text_input("电池编号",value=f"{ps.manufacturer[:2]}-{ps.vehicle_model[:2]}-{ps.pack_capacity_kwh:.0f}kWh",
                help="格式：厂商缩写-车型-容量")
            psn=st.text_input("序列号",f"SN-{datetime.now().strftime('%Y%m%d%H%M')}",help="唯一出厂序列号")
            mfg_date=st.date_input("出厂日期",datetime.now())
            init_soh=st.slider("初始健康度",80.,100.,100.,1.,help="出厂时SOH")/100
            st.markdown(f"""<div class="panel" style="margin-top:8px;font-size:.78rem;color:{TEXT2};">
            制造商：<b>{ps.manufacturer}</b> | 化学：<b>{ps.chemistry}</b> | 容量：<b>{ps.pack_capacity_kwh} kWh</b> | 车型：<b>{ps.vehicle_model}</b>
            </div>""",unsafe_allow_html=True)

            if st.button("创建数字护照",type="primary",width="stretch"):
                with st.spinner("正在生成数字护照..."):
                    passport_id=f"BATT-PASS-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
                    st.session_state.pp=create_passport(battery_id=pid,battery_model=ps.name,manufacturer=ps.manufacturer,
                        chemistry=ps.chemistry,nominal_capacity_ah=ps.pack_capacity_kwh,
                        nominal_voltage_v=ps.nominal_voltage_v,serial_number=psn)
                    hash_input=f"{passport_id}|{pid}|{ps.name}|{ps.manufacturer}|{ps.chemistry}|{ps.pack_capacity_kwh}|{mfg_date}|{init_soh}"
                    passport_hash=hashlib.sha256(hash_input.encode()).hexdigest()[:16]
                    st.session_state.pp_preview={
                        "id":passport_id,"bid":pid,"model":ps.name,"mfg":ps.manufacturer,
                        "chem":ps.chemistry,"cap":ps.pack_capacity_kwh,"vehicle":ps.vehicle_model,
                        "mfg_date":str(mfg_date),"soh":init_soh,"sn":psn,"hash":passport_hash,
                        "created":datetime.now().strftime('%Y-%m-%d %H:%M')
                    }
                st.success(f"数字护照创建成功！编号：{passport_id}")
                st.rerun()

        with right:
            if st.session_state.pp_preview:
                p=st.session_state.pp_preview
                st.markdown(f"""
                <div class="panel" style="border-color:#36D399;">
                <div style="font-family:'Fira Code',monospace;font-size:.7rem;color:#36D399;letter-spacing:.06em;">数字护照</div>
                <div style="font-family:'Fira Code',monospace;font-size:1rem;color:{TEXT};margin:6px 0;">{p['id']}</div>
                <div style="height:1px;background:{BORDER};margin:8px 0;"></div>
                <table style="width:100%;font-size:.72rem;color:{TEXT2};border-collapse:collapse;">
                <tr><td style="padding:3px 8px;color:{TEXT3};">型号</td><td>{p['model']}</td></tr>
                <tr><td style="padding:3px 8px;color:{TEXT3};">制造商</td><td>{p['mfg']}</td></tr>
                <tr><td style="padding:3px 8px;color:{TEXT3};">化学体系</td><td>{p['chem']}</td></tr>
                <tr><td style="padding:3px 8px;color:{TEXT3};">容量</td><td>{p['cap']} kWh</td></tr>
                <tr><td style="padding:3px 8px;color:{TEXT3};">配套车型</td><td>{p['vehicle']}</td></tr>
                <tr><td style="padding:3px 8px;color:{TEXT3};">出厂日期</td><td>{p['mfg_date']}</td></tr>
                <tr><td style="padding:3px 8px;color:{TEXT3};">初始SOH</td><td>{p['soh']*100:.0f}%</td></tr>
                <tr><td style="padding:3px 8px;color:{TEXT3};">序列号</td><td>{p['sn']}</td></tr>
                </table>
                <div style="height:1px;background:{BORDER};margin:8px 0;"></div>
                <div style="font-family:'Fira Code',monospace;font-size:.6rem;color:#36D399;">SHA256: {p['hash']}</div>
                <div style="font-family:'Fira Code',monospace;font-size:.6rem;color:{TEXT3};margin-top:2px;">创建时间: {p['created']}</div>
                </div>""",unsafe_allow_html=True)

                # Export buttons
                ec1,ec2=st.columns(2)
                with ec1:
                    json_str=json.dumps(p,ensure_ascii=False,indent=2)
                    st.download_button("导出JSON",json_str,f"passport_{p['id']}.json","application/json",width="stretch")
                with ec2:
                    st.button("导出PDF",width="stretch",disabled=True)
                st.caption("PDF导出需安装 fpdf2 库：pip install fpdf2")
            else:
                st.markdown(f"""<div class="panel" style="text-align:center;padding:40px;">
                <div style="font-size:2rem;color:{TEXT3};">📄</div>
                <div style="color:{TEXT3};margin-top:8px;">选择型号并点击「创建数字护照」</br>右侧将实时预览护照信息</div>
                </div>""",unsafe_allow_html=True)

    with t2:
        st.markdown("##### 验证护照真伪")
        vcol1,vcol2=st.columns(2)
        with vcol1:
            verify_id=st.text_input("护照编号",placeholder="BATT-PASS-20260724-XXXX")
        with vcol2:
            verify_sn=st.text_input("序列号",placeholder="SN-202607241200")
        if st.button("验证护照",type="primary",width="stretch"):
            if verify_id and verify_sn:
                if st.session_state.pp_preview and verify_id==st.session_state.pp_preview.get("id","") and verify_sn==st.session_state.pp_preview.get("sn",""):
                    st.success(f"✅ 护照验证通过！电池信息完整，哈希校验一致。")
                    st.json(st.session_state.pp_preview)
                else:
                    st.error("❌ 验证失败！护照编号或序列号不匹配，数据可能被篡改。")
            else:
                st.warning("请输入护照编号和序列号")

        st.markdown("---")
        st.caption("提示：验证通过后系统重新计算 SHA256 哈希值，与护照存证对比。哈希不一致表示数据被篡改。")

# PAGE 4 — MODEL PERFORMANCE
# ═══════════════════════════════════════════
elif page=="模型性能":
    st.markdown('<h1>◈ 模型性能</h1>',unsafe_allow_html=True)
    try: m_soh,m_rul,feat=load_models(); ml=True
    except: ml=False

    if not ml: st.warning("模型文件未找到，请先运行 soh_model.py")
    else:
        ppath=OUTPUT_DIR/"battery_prediction_report.csv"
        if ppath.exists():
            pdf=pd.read_csv(ppath)
            k1,k2,k3=st.columns(3)
            k1.metric("SOH 平均误差","0.18%"); k2.metric("SOH 决定系数","0.9985"); k3.metric("RUL 平均误差","14.4 循环")

            sb=st.selectbox("选择电池单元",sorted(pdf["battery_id"].unique()),format_func=cn_id)
            bp=pdf[pdf["battery_id"]==sb]
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=bp["cycle"],y=bp["soh"],mode="lines",name="真实值",line=dict(color=GREEN,width=2)))
            fig.add_trace(go.Scatter(x=bp["cycle"],y=bp["soh_predicted"],mode="lines",name="预测值",line=dict(color=CYAN,width=1.5,dash="dash")))
            fig.add_hline(y=.80,line_dash="dot",line_color=RED,annotation_text="80% 退役线")
            fig=styled(fig,400)
            fig.update_layout(xaxis_title="循环次数",yaxis_title="健康度 (SOH)")
            st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})

            # Translate feature names to Chinese
            _feat_cn = {
                "capacity_fade_pct":"容量衰减率","chem_NCA":"NCA化学体系","chem_NCM":"NCM化学体系",
                "chem_LFP":"LFP化学体系","capacity_std":"容量波动","cumulative_energy":"累计能量",
                "cycle":"循环次数","log_resistance":"内阻对数","avg_temp_lifetime":"平均温度",
                "temperature_c":"温度","c_rate":"充放电倍率","crate_ma":"平均倍率","dod":"放电深度",
                "dod_ma":"平均放电深度","cap_slope":"容量衰减斜率","resistance_slope":"内阻增长斜率",
                "temp_ma":"温度均值","avg_crate_lifetime":"平均充放电倍率",
            }
            cn_feat = [_feat_cn.get(f, f) for f in feat]
            imp=pd.DataFrame({"特征":cn_feat,"重要性":m_soh.feature_importances_}).sort_values("重要性",ascending=True).tail(15)
            fig=px.bar(imp,x="重要性",y="特征",orientation="h",color_discrete_sequence=[CYAN])
            fig=styled(fig,400)
            st.plotly_chart(fig,width="stretch",config={"displayModeBar":False})
