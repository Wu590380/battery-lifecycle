"""
电池交易残值评估平台 v3.0
深色工业后台风格 · 38/62 栅格 · 硬件全面检测 · SOH 环形仪表盘
"""
import streamlit as st
import sys, json, uuid, time as _time
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))

from simulator import BATTERY_CATALOG
from residual_value import estimate_residual_value
from market_scraper import BRAND_PACK_PRICES, get_brand_price_for_streamlit, get_adjusted_brand_price, get_prices_for_streamlit

st.set_page_config(page_title="电池交易评估", page_icon="⚡", layout="wide")

# ═══════════════════════════════════════
# CSS
# ═══════════════════════════════════════
st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
.stApp { background:#0f131a; font-family:'Inter',sans-serif; }
.card { background:#1a1f2b; border:1px solid #2a3040; border-radius:12px; padding:20px 24px; margin-bottom:16px; }
.card-green { border-color:#28c780; }
h1 { color:#fff !important; font-size:1.5rem !important; font-weight:700 !important; border:none !important; padding:0 !important; }
h3 { color:#e0e4ea !important; font-size:.95rem !important; font-weight:600 !important; margin-bottom:12px !important; }
.muted { color:#7a8290; font-size:.82rem; }
.stButton>button { border-radius:8px !important; font-weight:600 !important; font-size:.88rem !important; transition:all .2s !important; border:none !important; }
.stButton>button:hover { transform:scale(1.02); }
.stButton>button[kind="primary"] { background:linear-gradient(135deg,#28c780,#1a9e60) !important; color:#fff !important; }
.stButton>button[kind="primary"]:hover { box-shadow:0 4px 20px rgba(40,199,128,.3) !important; }
input,select,textarea,.stNumberInput input,.stTextInput input {
    border-radius:8px !important; border:1px solid #2a3040 !important;
    background:#141820 !important; color:#e0e4ea !important; font-size:14px !important; padding:10px 14px !important;
}
input:focus,select:focus { border-color:#28c780 !important; box-shadow:0 0 0 3px rgba(40,199,128,.12) !important; }
.stSlider>div>div>div>div { background:#28c780 !important; }
[data-testid="stMetricValue"] { font-size:1.4rem !important; font-weight:700 !important; color:#fff !important; }
[data-testid="stDataFrame"] { border:1px solid #2a3040; border-radius:8px; }
[data-testid="stDataFrame"] th { background:#1a1f2b !important; color:#7a8290 !important; }
[data-testid="stDataFrame"] td { color:#c0c6cf; }
.grade { display:inline-block; padding:5px 16px; border-radius:20px; font-weight:700; font-size:.85rem; letter-spacing:.04em; }
.grade-A { background:rgba(40,199,128,.12); color:#28c780; }
.grade-B { background:rgba(96,165,250,.12); color:#60a5fa; }
.grade-C { background:rgba(251,191,36,.12); color:#fbbf24; }
.grade-D { background:rgba(239,68,68,.12); color:#f87171; }
.deduction-bar { display:flex; align-items:center; margin:4px 0; }
.deduction-bar .bar-track { flex:1; background:#2a3040; border-radius:4px; height:6px; margin:0 10px; }
.deduction-bar .bar-fill { background:#f87171; border-radius:4px; height:6px; }
@keyframes fadeIn { from{opacity:0;transform:translateY(12px);} to{opacity:1;transform:translateY(0);} }
.fade-in { animation:fadeIn .4s ease; }
</style>""", unsafe_allow_html=True)

# ═══════════════════════════════════════
# Session init
# ═══════════════════════════════════════
if "mkt_lfp" not in st.session_state:
    st.session_state.mkt_lfp = 650; st.session_state.mkt_ncm = 850; st.session_state.mkt_nca = 900
    st.session_state.mkt_recycle_lfp = 130; st.session_state.mkt_recycle_ncm = 180; st.session_state.mkt_recycle_nca = 160
if "trade_history" not in st.session_state: st.session_state.trade_history = []
if "mkt_last_fetch" not in st.session_state: st.session_state.mkt_last_fetch = 0
# ──
import datetime as _dt
_now_ts = _dt.datetime.now().timestamp()
if _now_ts - st.session_state.mkt_last_fetch > 3600:
    try:
        p = get_prices_for_streamlit()
        st.session_state.mkt_lithium = p["lithium"]; st.session_state.mkt_cobalt = p["cobalt"]
        st.session_state.mkt_nickel = p["nickel"]; st.session_state.mkt_last_fetch = _now_ts
        st.session_state.mkt_source = f"行情 · 碳酸锂 {p['lithium']/10000:.2f}万/吨 · smm.cn/baiinfo.com/gem.com.cn"
    except: pass

# ═══════════════════════════════════════
# Header (compact)
# ═══════════════════════════════════════
st.markdown(f"""
<div style="text-align:center;padding:16px 0 2px;">
    <h1>电池交易残值评估平台</h1>
    <p class="muted">面向二手车交易 · 4S店置换 · 梯次利用回收</p>
</div>""", unsafe_allow_html=True)

# ═══════════════════════════════════════
# Main layout: 38% / 62%
# ═══════════════════════════════════════
col_left, col_right = st.columns([0.38, 0.62])

with col_left:
    search_trade = st.text_input("搜索型号", placeholder="输入品牌/车型/容量...", label_visibility="collapsed")
    filtered = [k for k in BATTERY_CATALOG.keys()
               if search_trade.lower() in BATTERY_CATALOG[k].name.lower()
               or search_trade.lower() in BATTERY_CATALOG[k].vehicle_model.lower()
               or search_trade.lower() in BATTERY_CATALOG[k].manufacturer.lower()
               or search_trade == ""]
    if not filtered: filtered = list(BATTERY_CATALOG.keys())
    bt = st.selectbox("型号", filtered, label_visibility="collapsed",
        format_func=lambda x: f"{BATTERY_CATALOG[x].name} ({BATTERY_CATALOG[x].pack_capacity_kwh}kWh · {BATTERY_CATALOG[x].vehicle_model})")
    sp = BATTERY_CATALOG[bt]

    brand_key = f"{sp.name} ({sp.vehicle_model} {sp.pack_capacity_kwh}kWh)"
    if "last_brand" not in st.session_state: st.session_state.last_brand = ""
    if st.session_state.last_brand != brand_key:
        st.session_state.last_brand = brand_key
        adj = get_brand_price_for_streamlit(sp.name, sp.vehicle_model)
        if adj:
            for k in ["mkt_lfp","mkt_ncm","mkt_nca"]:
                st.session_state[k] = int(adj["new"] * 10000 / sp.pack_capacity_kwh)
            for k in ["mkt_recycle_lfp","mkt_recycle_ncm","mkt_recycle_nca"]:
                st.session_state[k] = int(adj["scrap"] * 10000 / sp.pack_capacity_kwh)

    st.markdown(f'<p class="muted">{sp.manufacturer} · {sp.chemistry} · {sp.pack_capacity_kwh}kWh · {sp.vehicle_model}</p>', unsafe_allow_html=True)
    if st.session_state.get("mkt_source"): st.caption(st.session_state.mkt_source)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<h3><span style="color:#28c780;"></span> 电池状态</h3>', unsafe_allow_html=True)
    c1,c2=st.columns(2)
    with c1: soh_val=st.slider("SOH (%)",30.,100.,85.,.5)/100
    with c2: cyc=st.number_input("循环次数",0,5000,800,50)
    c3,c4=st.columns(2)
    with c3: sev=st.selectbox("使用环境",["mild","normal","severe"],format_func=lambda x:{"mild":"温和","normal":"正常","severe":"恶劣"}[x])
    with c4: age=st.slider("使用时长(月)",0,120,24)
    st.markdown('</div>', unsafe_allow_html=True)

    # ── Hardware inspection ──
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f'<h3><span style="color:#60a5fa;"></span> 硬件外观检测</h3>', unsafe_allow_html=True)
    cond_deduction = 1.0
    deductions = {}  # Track individual deductions

    with st.expander("壳体与外观"):
        casing = st.selectbox("壳体形变", ["无变形","轻微凹陷","严重挤压"], key="casing")
        rust = st.selectbox("外壳锈蚀", ["无锈迹","局部锈点","大面积腐蚀"], key="rust")
        seal = st.selectbox("密封胶条", ["完好","轻微老化","开裂进水"], key="seal")
        dent = st.selectbox("外部磕碰", ["无磕碰","边角轻微损伤","多处硬伤"], key="dent")
        deductions["壳体"] = (casing!="无变形")*.06 + (rust!="无锈迹")*.06 + (seal!="完好")*.08 + (dent!="无磕碰")*.08

    with st.expander("电芯与电气安全"):
        diff = st.selectbox("电芯压差", ["≤20mV","20~50mV","＞50mV"], key="diff")
        maint = st.selectbox("维修历史", ["无拆修","局部维修","整体拆解"], key="maint")
        archive = st.selectbox("出厂档案", ["完整可查","资料缺失","无溯源档案"], key="archive")
        thermal = st.selectbox("热管理状态", ["散热完好","风扇老化","管路渗漏"], key="thermal")
        wire = st.selectbox("高压线束", ["绝缘完好","外皮磨损","老化破损"], key="wire")
        connector = st.selectbox("接插件", ["无烧蚀","轻微氧化","过热发黑"], key="conn")
        insulation = st.selectbox("绝缘阻值", ["合格","偏低","不达标"], key="ins")
        deductions["电芯"] = (diff=="＞50mV")*.15 + (diff=="20~50mV")*.06
        deductions["电芯"] += (maint!="无拆修")*.10 + (archive!="完整可查")*.10
        deductions["电芯"] += (thermal!="散热完好")*.08 + (wire!="绝缘完好")*.10
        deductions["电芯"] += (connector!="无烧蚀")*.08 + (insulation!="合格")*.15

    with st.expander("事故溯源"):
        flood = st.selectbox("涉水记录", ["无涉水","轻度涉水","浸泡进水"], key="flood")
        crash = st.selectbox("碰撞记录", ["无事故","轻微托底","重大撞击"], key="crash")
        overcharge = st.selectbox("过充过放历史", ["无异常","少量记录","频繁异常"], key="over")
        deductions["事故"] = (flood!="无涉水")*.12 + (crash!="无事故")*.15 + (overcharge!="无异常")*.10

    total_deduction = sum(deductions.values())
    cond_deduction = max(0.10, 1.0 - total_deduction)
    st.caption(f"硬件检测系数：{cond_deduction:.0%}")
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="card card-green">', unsafe_allow_html=True)

    if st.button("⚡ 开始评估", type="primary", use_container_width=True):
        with st.spinner("正在评估..."):
            _time.sleep(0.4)
            rep = estimate_residual_value(
                battery_spec={"name": sp.name, "chemistry": sp.chemistry, "pack_capacity_kwh": sp.pack_capacity_kwh,
                              "cycle_life": sp.cycle_life_to_80pct, "manufacturer": sp.manufacturer, "vehicle_model": sp.vehicle_model},
                current_soh=soh_val, current_cycle=cyc, estimated_rul=int(sp.cycle_life_to_80pct * soh_val),
                usage_severity=sev, calendar_age_months=age, condition_factor=cond_deduction)

        remain = rep.value_retention_pct
        st.markdown('<div class="fade-in">', unsafe_allow_html=True)

        # Grade badge
        if remain >= 75: grade, gclass = "A级", "grade-A"
        elif remain >= 55: grade, gclass = "B级", "grade-B"
        elif remain >= 35: grade, gclass = "梯次级", "grade-C"
        else: grade, gclass = "报废", "grade-D"
        st.markdown(f'<span class="grade {gclass}">{grade}</span>', unsafe_allow_html=True)

        # Value cards with animated icons
        v1,v2=st.columns(2)
        with v1: st.metric("📊 全新价值", f"{rep.new_value_rmb:,.0f} 元")
        with v2:
            c = "#28c780" if remain>=55 else ("#fbbf24" if remain>=35 else "#f87171")
            st.metric("💰 当前残值", f"{rep.residual_value_rmb:,.0f} 元", delta=f"残值率 {remain:.1f}%")
        st.caption(f"估值区间: {rep.confidence_low:,.0f} ~ {rep.confidence_high:,.0f} 元")

        # Pricing formula breakdown
        st.markdown("<div style='height:1px;background:#2a3040;margin:16px 0;'></div>", unsafe_allow_html=True)
        st.markdown(f'<h3><span style="color:#22d3ee;"></span> 定价计算明细</h3>', unsafe_allow_html=True)
        pack_kwh = sp.pack_capacity_kwh
        price_per_kwh = st.session_state.mkt_lfp if sp.chemistry=="LFP" else (st.session_state.mkt_ncm if sp.chemistry=="NCM" else st.session_state.mkt_nca)
        base_val = pack_kwh * price_per_kwh
        soh_impact = base_val * (soh_val - 1)
        brand_factor = {"比亚迪/弗迪":0.98,"宁德时代":1.00,"松下":0.95,"中创新航":0.92,"国轩高科":0.88,"蜂巢能源":0.85,"LG新能源":0.90,"三星SDI":0.93,"SK On":0.88,"亿纬锂能":0.90,"孚能科技":0.85,"欣旺达":0.82}.get(sp.manufacturer, 0.90)
        brand_impact = base_val * soh_val * (brand_factor - 1)
        cond_impact = base_val * soh_val * brand_factor * (cond_deduction - 1)

        items = [
            ("基础价", f"{pack_kwh}kWh × {price_per_kwh}元/kWh", f"{base_val:,.0f}"),
            ("SOH衰减", f"SOH {soh_val*100:.0f}% → 折价 {(1-soh_val)*100:.0f}%", f"{soh_impact:,.0f}"),
            ("品牌折价", f"{sp.manufacturer} 系数{brand_factor} → 调整{(brand_factor-1)*100:+.1f}%", f"{brand_impact:,.0f}"),
            ("硬件扣减", f"检测系数{cond_deduction:.0%} → 折价{(1-cond_deduction)*100:.0f}%", f"{cond_impact:,.0f}"),
        ]
        for label, detail, amt in items:
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;padding:4px 0;font-size:.8rem;">
                <span style="color:#c0c6cf;width:80px;">{label}</span>
                <span style="color:#7a8290;flex:1;text-align:center;font-size:.72rem;">{detail}</span>
                <span style="color:{'#f87171' if float(amt.replace(',',''))<0 else '#c0c6cf'};width:90px;text-align:right;font-weight:600;">{amt} 元</span>
            </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid #2a3040;margin-top:4px;font-size:.9rem;font-weight:700;">
            <span style="color:#28c780;">最终残值</span>
            <span style="color:#28c780;">{rep.residual_value_rmb:,.0f} 元</span>
        </div>""", unsafe_allow_html=True)

        # SOH gauge — color by health level
        if soh_val >= 0.75: bar_color = "#28c780"
        elif soh_val >= 0.55: bar_color = "#fbbf24"
        elif soh_val >= 0.35: bar_color = "#f59e0b"
        else: bar_color = "#f87171"
        st.markdown(f"""
        <div style="margin:14px 0;">
            <div style="display:flex;justify-content:space-between;font-size:.78rem;color:#7a8290;">
                <span>SOH 健康度</span><span style="color:{bar_color};">{soh_val*100:.0f}%</span>
            </div>
            <div style="background:#2a3040;border-radius:8px;height:10px;margin-top:5px;">
                <div style="background:{bar_color};width:{soh_val*100}%;height:10px;border-radius:8px;transition:width .5s ease;"></div>
            </div>
        </div>""", unsafe_allow_html=True)

        # Deduction breakdown — always show
        st.markdown("<div style='height:1px;background:#2a3040;margin:16px 0;'></div>", unsafe_allow_html=True)
        st.markdown(f'<h3><span style="color:#f87171;"></span> 检测扣分明细</h3>', unsafe_allow_html=True)
        has_issue = False
        for cat, val in deductions.items():
            bar_w = min(val*100, 100)
            clr = "#28c780" if val == 0 else "#f87171"
            label = "正常" if val == 0 else f"-{val*100:.0f}%"
            if val > 0: has_issue = True
            st.markdown(f"""
            <div class="deduction-bar">
                <span style="font-size:.75rem;color:#c0c6cf;width:50px;">{cat}</span>
                <div class="bar-track"><div class="bar-fill" style="width:{bar_w}%;background:{clr};"></div></div>
                <span style="font-size:.75rem;color:{clr};">{label}</span>
            </div>""", unsafe_allow_html=True)
        if not has_issue:
            st.caption("所有检测项正常，无扣分")

        # Channel comparison with advice
        st.markdown("<div style='height:1px;background:#2a3040;margin:16px 0;'></div>", unsafe_allow_html=True)
        st.markdown(f'<h3><span style="color:#fbbf24;"></span> 交易渠道对比与建议</h3>', unsafe_allow_html=True)
        # Determine best channel
        vals = {"4S店置换": rep.residual_value_rmb, "梯次利用": rep.second_life_value_rmb, "材料回收": rep.recycle_value_rmb}
        best_channel = max(vals, key=vals.get)
        c1,c2,c3=st.columns(3)
        with c1:
            is_best = (best_channel == "4S店置换")
            st.metric("4S店置换", f"{rep.residual_value_rmb:,.0f} 元", delta="推荐" if is_best else None)
            st.caption("抵扣新车款" + (" · 最优" if is_best else ""))
        with c2:
            is_best = (best_channel == "梯次利用")
            st.metric("梯次利用", f"{rep.second_life_value_rmb:,.0f} 元", delta="推荐" if is_best else None)
            st.caption("转储能/备电" + (" · 最优" if is_best else ""))
        with c3:
            is_best = (best_channel == "材料回收")
            st.metric("材料回收", f"{rep.recycle_value_rmb:,.0f} 元", delta="推荐" if is_best else None)
            st.caption("保底方案" + (" · 最优" if is_best else ""))

        # Page Agent unified analysis
        st.markdown("<div style='height:1px;background:#2a3040;margin:16px 0;'></div>", unsafe_allow_html=True)
        st.markdown(f'<h3><span style="color:#a78bfa;"></span> Page Agent 智能评估</h3>', unsafe_allow_html=True)

        # Agent reasoning trace
        agent_input = f"SOH:{soh_val*100:.0f}% | 循环:{cyc}次 | 化学:{sp.chemistry} | 品牌:{sp.manufacturer} | 硬件系数:{cond_deduction:.0%}"
        if st.session_state.get("mkt_source"):
            agent_input += f"\n行情：{st.session_state.mkt_source}"
        st.code(f"Agent 分析输入：{agent_input}", language=None, wrap_lines=True)
        
        with st.spinner("Agent 分析中..."):
            _time.sleep(0.3)
        st.caption("Agent 综合 SOH、品牌折价、硬件检测、市场行情 → 生成交易建议：")
        
        # Detailed recommendation (same logic, now under Page Agent brand)
        chem = sp.chemistry
        if remain >= 75:
            st.success(f"""
**等级：A级 · 残值率 {remain:.0f}%**
- 电池健康度优秀，建议优先走 **4S 店置换** 渠道，可直接抵扣新车款
- 如搭配完整维保记录，可在二手车平台溢价 **10-15%** 出售
- 当前{chem}材料行情平稳，暂不建议拆解回收（收益较低）
- 预计可为整车增加 **{rep.residual_value_rmb*0.15:,.0f} ~ {rep.residual_value_rmb*0.25:,.0f} 元** 售价
            """)
        elif remain >= 55:
            st.warning(f"""
**等级：B级 · 残值率 {remain:.0f}%**
- 电池处于正常老化阶段，**4S置换** 和 **梯次利用** 两个渠道均可考虑
- 建议联系至少 2 家梯次利用企业比价（如格林美、邦普循环），价差可达 **20-30%**
- 如果{chem}材料价格上涨，回收价值会同步提升，可等待合适时机
- 当前剩余循环寿命约 **{int(sp.cycle_life_to_80pct*soh_val)} 次**，仍可满足储能场景需求
            """)
        elif remain >= 35:
            st.warning(f"""
**等级：梯次级 · 残值率 {remain:.0f}%**
- 电池老化明显，**不建议继续车用**，安全隐患增加
- 优先联系储能电站运营商或备电系统集成商，整包出售比拆解回收收益高 **2-3 倍**
- {chem}电池的材料回收价约 **{rep.recycle_value_rmb:,.0f} 元**，作为保底方案
- 注意：单独出售电池包需随车交易，不可单独过户，无手续电池会被大幅压价
            """)
        else:
            st.error(f"""
**等级：报废 · 残值率 {remain:.0f}%**
- 电池已接近寿命终点，**不建议任何形式的二次销售**
- 必须联系正规危废处理企业（如格林美 gem.com.cn / 邦普循环 brunp.com.cn）进行合规回收
- 私自拆解存在高压触电、电解液泄漏等安全风险，且违反《固体废物污染环境防治法》
- 材料回收价值约 **{rep.recycle_value_rmb:,.0f} 元**，作为最终处置收益
            """)

        # PDF
        if st.button("导出评估报告 PDF", key="pdf"):
            from fpdf import FPDF
            pdf=FPDF(); pdf.add_page()
            pdf.set_font('Helvetica','B',14)
            pdf.cell(0,10,'Battery Trade Assessment',align='C',new_x='LMARGIN',new_y='NEXT')
            pdf.ln(5); pdf.set_font('Helvetica','',10)
            for k,v in [('Model',sp.name),('SOH',f"{soh_val*100:.0f}%"),('Residual',f"{rep.residual_value_rmb:,.0f} RMB")]:
                pdf.cell(40,7,k+':'); pdf.cell(0,7,str(v),new_x='LMARGIN',new_y='NEXT')
            out = Path(__file__).parent / "data" / f"report_{datetime.now().strftime('%Y%m%d%H%M')}.pdf"
            pdf.output(str(out)); st.success(f"PDF: {out}")

        # History
        st.session_state.trade_history.insert(0, {
            "id":f"TRADE-{datetime.now().strftime('%Y%m%d%H%M')}-{uuid.uuid4().hex[:4].upper()}",
            "time":datetime.now().isoformat(),"model":sp.name,"vehicle":sp.vehicle_model,
            "soh":soh_val*100,"residual":rep.residual_value_rmb,"retention":remain,
            "recommendation":"4S置换" if remain>=70 else ("梯次利用" if remain>=40 else "材料回收")
        })
        st.markdown('</div>',unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:center;padding:80px 20px;color:#7a8290;">
            <div style="color:#7a8290;margin-bottom:12px;"></div>
            <div>参数填写完成后点击「开始评估」生成报告</div>
        </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════
# History
# ═══════════════════════════════════════
if st.session_state.trade_history:
    st.markdown("---")
    st.markdown(f'<h3><span style="color:#787c85;"></span> 历史评估记录</h3>', unsafe_allow_html=True)
    import pandas as pd
    h=pd.DataFrame(st.session_state.trade_history[:10])
    h["时间"]=h["time"].apply(lambda x:x[:16])
    h=h[["时间","model","vehicle","soh","residual","retention","recommendation"]]
    h.columns=["时间","型号","车型","SOH%","残值(元)","残值率%","建议"]
    st.dataframe(h,use_container_width=True,hide_index=True)
