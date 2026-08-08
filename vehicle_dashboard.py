"""
车载电池显示屏 v3.0 — 单辆车载终端
部署在车载屏幕/手机上，通过 URL 参数指定车辆
例：http://localhost:8503?car=CATL-QJ-100

数据来源：ESP32 → data_api.py → JSONL → 本地读取
"""
import streamlit as st
import json, time
from pathlib import Path
from glob import glob

st.set_page_config(page_title="车载电池", page_icon="⚡", layout="wide")

car_id = st.query_params.get("car", "CATL-QJ-100")

st.markdown("""
<style>
.stApp { background:#0d1117; font-family:'Inter',sans-serif; }
.alert-box { border:2px solid #f85149; border-radius:8px; padding:16px; background:rgba(248,81,73,0.1); margin:8px 0; }
.warning { border-color:#d29922; background:rgba(210,153,34,0.1); }
.normal { border-color:#3fb950; background:rgba(63,185,80,0.05); }
</style>
""", unsafe_allow_html=True)

BAT_LABELS = {
    "CATL-QJ-100": ("宁德麒麟", "问界M9", "NCM"), "BYD-Blade-85": ("比亚迪刀片", "汉EV", "LFP"),
    "CATL-QJ-80": ("宁德麒麟", "阿维塔12", "NCM"), "Panasonic-75": ("松下三元", "Model3", "NCA"),
    "BYD-Blade-72": ("比亚迪刀片", "海豹", "LFP"), "CALB-S7-67": ("中创新航", "深蓝S7", "LFP"),
    "CATL-SL-58": ("宁德铁锂", "深蓝SL03", "LFP"), "Gotion-A07-54": ("国轩高科", "启源A07", "LFP"),
    "LG-M3-60": ("LG三元", "Model3标续", "NCM"), "BYD-Blade-47": ("比亚迪刀片", "海豚", "LFP"),
    "CATL-L7-42": ("宁德铁锂", "理想L7", "LFP"), "SVOLT-GW-40": ("蜂巢能源", "欧拉好猫", "LFP"),
}

def load_latest(bid):
    """读取指定车辆的最新数据"""
    DATA_DIR = Path(__file__).parent / "data"
    files = sorted(glob(str(DATA_DIR / "telemetry_*.jsonl")))
    latest = None
    for f in reversed(files):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        r = json.loads(line)
                        if r.get("battery_id") == bid or r.get("vehicle_id") == bid:
                            latest = r
        except: pass
    return latest

data = load_latest(car_id)
if not data:
    st.warning(f"等待 {car_id} 数据...")
    st.stop()

label = BAT_LABELS.get(car_id, (car_id, "", ""))
chem = label[2]
soc = data.get("soc_pct", 0) or 0
soh = data.get("soh_pct", 92) or 92
temp = data.get("pack_temp_c", 25) or 25
diff = (data.get("cell_voltage_diff_v", 0) or 0) * 1000
ins_val = data.get("insulation_resistance_kohm", 5000) or 5000
bms_ok = (int(data.get("bms_status", 0) or 0) == 0)

alerts = []
if soc < 20: alerts.append(("电量过低", f"SOC {soc:.0f}% 请充电", "danger"))
if soh < 80: alerts.append(("健康度下降", f"SOH {soh:.1f}% 建议检测", "warning"))
if temp > 45: alerts.append(("温度过高", f"{temp:.1f}°C 超过阈值", "danger"))
if diff > 50: alerts.append(("压差过大", f"{diff:.0f}mV 一致性差", "danger"))
if diff > 30: alerts.append(("压差偏大", f"{diff:.0f}mV 注意监测", "warning"))
if ins_val < 1000: alerts.append(("绝缘异常", f"{ins_val:.0f}kΩ 安全隐患", "danger"))
if not bms_ok: alerts.append(("BMS故障", "请检查电池管理系统", "danger"))

st.markdown(f"<div style='text-align:center;padding:4px;color:#8b949e;font-size:0.7rem;'>{label[0]} · {label[1]} · {chem}</div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    sc = "#3fb950" if soc>30 else ("#d29922" if soc>15 else "#f85149")
    st.markdown(f"<div style='text-align:center;padding:20px;'><div style='font-size:5rem;font-weight:800;color:{sc};'>{soc:.0f}<span style='font-size:2rem;'>%</span></div><div style='color:#8b949e;text-transform:uppercase;letter-spacing:.1em;font-size:.9rem;'>SOC</div><div style='margin-top:12px;background:#21262d;border-radius:8px;height:14px;'><div style='background:{sc};width:{soc}%;height:14px;border-radius:8px;'></div></div></div>", unsafe_allow_html=True)
with c2:
    sc2 = "#3fb950" if soh>85 else ("#d29922" if soh>70 else "#f85149")
    st.markdown(f"<div style='text-align:center;padding:20px;'><div style='font-size:5rem;font-weight:800;color:{sc2};'>{soh:.1f}<span style='font-size:2rem;'>%</span></div><div style='color:#8b949e;text-transform:uppercase;letter-spacing:.1em;font-size:.9rem;'>SOH</div><div style='margin-top:12px;background:#21262d;border-radius:8px;height:14px;'><div style='background:{sc2};width:{soh}%;height:14px;border-radius:8px;'></div></div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div style='padding:20px;'><table style='width:100%;font-size:1.2rem;color:#c9d1d9;'><tr><td style='color:#8b949e;padding:10px 0;'>电压</td><td style='text-align:right;font-weight:600;'>{data.get('pack_voltage_v',0):.1f} V</td></tr><tr><td style='color:#8b949e;padding:10px 0;'>电流</td><td style='text-align:right;font-weight:600;'>{data.get('pack_current_a',0):.1f} A</td></tr><tr><td style='color:#8b949e;padding:10px 0;'>温度</td><td style='text-align:right;font-weight:600;color:{'#f85149' if temp>45 else '#c9d1d9'}'>{temp:.1f} °C</td></tr><tr><td style='color:#8b949e;padding:10px 0;'>压差</td><td style='text-align:right;font-weight:600;color:{'#f85149' if diff>30 else '#c9d1d9'}'>{diff:.0f} mV</td></tr><tr><td style='color:#8b949e;padding:10px 0;'>绝缘</td><td style='text-align:right;font-weight:600;'>{ins_val:.0f} kΩ</td></tr><tr><td style='color:#8b949e;padding:10px 0;'>循环</td><td style='text-align:right;font-weight:600;'>{data.get('cycle_count',0)} 次</td></tr></table></div>", unsafe_allow_html=True)

if alerts:
    st.markdown("---")
    for title, msg, lvl in alerts:
        cls = "alert-box" if lvl=="danger" else "alert-box warning"
        st.markdown(f'<div class="{cls}"><b>{title}</b><br><span style="font-size:.85rem;color:#8b949e;">{msg}</span></div>', unsafe_allow_html=True)
else:
    ts = str(data.get("timestamp",""))[:19]
    st.markdown(f'<div class="normal" style="border-radius:8px;padding:12px;margin-top:16px;text-align:center;color:#3fb950;">✅ 正常 · ESP32 · {ts}</div>', unsafe_allow_html=True)

time.sleep(3)
st.rerun()
