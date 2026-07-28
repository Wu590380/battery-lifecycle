"""
动力电池数据模拟器 — Battery Data Simulator
模拟真实电池全生命周期退化数据，支持LFP/NCM/NCA多种化学体系。
基于公开文献中的电池老化模型（幂律衰减 + 日历老化 + 循环老化）。
"""
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
import json

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class BatterySpec:
    """电池规格定义 — 整车电池包级别参数"""
    name: str
    chemistry: str
    pack_capacity_kwh: float    # 电池包总能量 (kWh)
    nominal_voltage_v: float    # 电池包标称电压
    cell_chemistry: str = ""    # 单体电芯类型描述
    cycle_life_to_80pct: int = 2000
    manufacturer: str = ""
    vehicle_model: str = ""     # 搭载车型
    pack_weight_kg: int = 400   # 电池包重量


# 主流电动车电池包型号（完整Pack级别，12款）
BATTERY_CATALOG = {
    "BYD-Blade-85": BatterySpec("比亚迪刀片(汉EV 85kWh)","LFP",85.4,569.6,"磷酸铁锂刀片",3000,"比亚迪/弗迪","汉EV",pack_weight_kg=480),
    "BYD-Blade-72": BatterySpec("比亚迪刀片(海豹 72kWh)","LFP",72.0,512.0,"磷酸铁锂刀片",3000,"比亚迪/弗迪","海豹",pack_weight_kg=420),
    "BYD-Blade-47": BatterySpec("比亚迪刀片(海豚 47kWh)","LFP",47.0,384.0,"磷酸铁锂刀片",3000,"比亚迪/弗迪","海豚",pack_weight_kg=310),
    "BYD-Blade-60": BatterySpec("比亚迪刀片(元PLUS 60kWh)","LFP",60.5,448.0,"磷酸铁锂刀片",3000,"比亚迪/弗迪","元PLUS",pack_weight_kg=380),
    "BYD-Blade-27": BatterySpec("比亚迪刀片(海鸥 27kWh)","LFP",26.9,320.0,"磷酸铁锂刀片",3000,"比亚迪/弗迪","海鸥",pack_weight_kg=220),
    "BYD-Blade-108": BatterySpec("比亚迪刀片(仰望U8 108kWh)","LFP",108.0,640.0,"磷酸铁锂刀片",3000,"比亚迪/弗迪","仰望U8",pack_weight_kg=600),
    "CATL-QJ-100": BatterySpec("宁德麒麟(问界M9 100kWh)","NCM",100.0,651.0,"NCM811",1500,"宁德时代","问界M9",pack_weight_kg=520),
    "CATL-QJ-80": BatterySpec("宁德麒麟(阿维塔12 80kWh)","NCM",80.0,585.0,"NCM811",1500,"宁德时代","阿维塔12",pack_weight_kg=450),
    "CATL-QJ-140": BatterySpec("宁德麒麟(极氪009 140kWh)","NCM",140.0,780.0,"NCM811",1200,"宁德时代","极氪009",pack_weight_kg=680),
    "CATL-SL-58": BatterySpec("宁德铁锂(深蓝SL03 58kWh)","LFP",58.1,396.0,"LFP",2500,"宁德时代","深蓝SL03",pack_weight_kg=380),
    "CATL-L7-42": BatterySpec("宁德铁锂(理想L7 42kWh)","LFP",42.0,336.0,"LFP",2500,"宁德时代","理想L7",pack_weight_kg=300),
    "CATL-L9-53": BatterySpec("宁德铁锂(理想L9 53kWh)","LFP",52.3,384.0,"LFP",2500,"宁德时代","理想L9",pack_weight_kg=340),
    "CATL-M5-50": BatterySpec("宁德铁锂(问界M5 50kWh)","LFP",50.0,360.0,"LFP",2500,"宁德时代","问界M5",pack_weight_kg=330),
    "CATL-WL-39": BatterySpec("宁德铁锂(五菱缤果 39kWh)","LFP",38.5,320.0,"LFP",2500,"宁德时代","五菱缤果",pack_weight_kg=280),
    "CATL-NIO-75": BatterySpec("宁德三元(蔚来ES6 75kWh)","NCM",75.0,450.0,"NCM523",2000,"宁德时代","蔚来ES6",pack_weight_kg=450),
    "CATL-NIO-100": BatterySpec("宁德三元(蔚来ET7 100kWh)","NCM",100.0,520.0,"NCM811",1500,"宁德时代","蔚来ET7",pack_weight_kg=530),
    "CATL-XP-67": BatterySpec("宁德铁锂(小鹏G6 67kWh)","LFP",66.0,440.0,"LFP",2500,"宁德时代","小鹏G6",pack_weight_kg=400),
    "CATL-XP-88": BatterySpec("宁德三元(小鹏P7 88kWh)","NCM",88.0,480.0,"NCM811",1500,"宁德时代","小鹏P7",pack_weight_kg=480),
    "Panasonic-75": BatterySpec("松下三元(Model3 75kWh)","NCA",75.0,360.0,"NCA21700",1500,"松下","Model 3长续航",pack_weight_kg=437),
    "Panasonic-82": BatterySpec("松下三元(ModelY 82kWh)","NCA",82.0,380.0,"NCA21700",1500,"松下","Model Y长续航",pack_weight_kg=460),
    "LG-M3-60": BatterySpec("LG三元(Model3 60kWh)","NCM",60.0,352.0,"NCM软包",1200,"LG新能源","Model 3标续",pack_weight_kg=380),
    "LG-ID4-77": BatterySpec("LG三元(ID.4 77kWh)","NCM",77.0,408.0,"NCM712",1500,"LG新能源","大众ID.4",pack_weight_kg=480),
    "Samsung-I5-58": BatterySpec("三星三元(宝马i5 58kWh)","NCM",58.0,352.0,"NCM622",1800,"三星SDI","宝马i5",pack_weight_kg=380),
    "Samsung-I3-42": BatterySpec("三星三元(宝马i3 42kWh)","NCM",42.0,352.0,"NCM622",1800,"三星SDI","宝马i3",pack_weight_kg=310),
    "SK-KIA-77": BatterySpec("SK三元(起亚EV6 77kWh)","NCM",77.4,697.0,"NCM811",1500,"SK On","起亚EV6",pack_weight_kg=470),
    "CALB-S7-67": BatterySpec("中创新航(深蓝S7 67kWh)","LFP",66.8,438.0,"LFP",2500,"中创新航","深蓝S7",pack_weight_kg=420),
    "CALB-L9-53": BatterySpec("中创新航(理想L9 53kWh)","LFP",52.3,384.0,"LFP",2500,"中创新航","理想L9",pack_weight_kg=340),
    "CALB-XP-67": BatterySpec("中创新航(小鹏P5 67kWh)","LFP",66.2,440.0,"LFP",2500,"中创新航","小鹏P5",pack_weight_kg=400),
    "Gotion-A07-54": BatterySpec("国轩高科(启源A07 54kWh)","LFP",53.0,352.0,"LFP",2800,"国轩高科","长安启源A07",pack_weight_kg=350),
    "Gotion-A05-30": BatterySpec("国轩高科(启源A05 30kWh)","LFP",30.0,320.0,"LFP",2800,"国轩高科","长安启源A05",pack_weight_kg=240),
    "Gotion-MINI-14": BatterySpec("国轩高科(五菱MINI 14kWh)","LFP",13.9,96.0,"LFP",3000,"国轩高科","五菱宏光MINI EV",pack_weight_kg=120),
    "SVOLT-GW-40": BatterySpec("蜂巢能源(欧拉好猫 40kWh)","LFP",40.0,320.0,"LFP短刀",3000,"蜂巢能源","欧拉好猫",pack_weight_kg=280),
    "SVOLT-GW-29": BatterySpec("蜂巢能源(欧拉黑猫 29kWh)","LFP",28.5,320.0,"LFP短刀",3000,"蜂巢能源","欧拉黑猫",pack_weight_kg=230),
    "SVOLT-TANK-37": BatterySpec("蜂巢能源(坦克300 37kWh)","LFP",37.1,384.0,"LFP短刀",3000,"蜂巢能源","坦克300 PHEV",pack_weight_kg=290),
    "EVE-L7-42": BatterySpec("亿纬锂能(理想L7 42kWh)","LFP",42.0,336.0,"LFP",2500,"亿纬锂能","理想L7",pack_weight_kg=300),
    "EVE-GM-34": BatterySpec("亿纬锂能(宝马iX1 34kWh)","LFP",34.0,320.0,"LFP",2500,"亿纬锂能","宝马iX1",pack_weight_kg=270),
    "Farasis-GW-40": BatterySpec("孚能科技(奔驰EQA 40kWh)","NCM",40.0,352.0,"NCM软包",2000,"孚能科技","奔驰EQA",pack_weight_kg=300),
    "Sunwoda-LEAP-32": BatterySpec("欣旺达(零跑T03 32kWh)","LFP",31.9,320.0,"LFP",2500,"欣旺达","零跑T03",pack_weight_kg=250),
}


def capacity_fade_model(cycle, chemistry="NCM", temp_c=25, c_rate=1.0, dod=1.0):
    """
    容量衰减模型 — 复合多因素老化
    返回: SOH (0~1), 即 当前容量/初始容量

    模型: SOH = 1 - α·N^β - γ·t_calendar
    其中 N 为等效全循环次数，α 为衰减系数，β 为加速指数
    """
    # 化学体系相关的基准衰减参数
    if chemistry == "LFP":
        alpha = 0.00018      # 每循环衰减系数（LFP更耐久）
        beta = 0.85          # 衰减加速指数
        cal_alpha = 0.015    # 年日历老化率
    elif chemistry == "NCA":
        alpha = 0.00035
        beta = 0.88
        cal_alpha = 0.028
    else:  # NCM
        alpha = 0.00025
        beta = 0.87
        cal_alpha = 0.022

    # 温度加速因子（Arrhenius模型简化）
    temp_factor = np.exp((temp_c - 25) / 25 * 0.6)  # 每10°C约翻倍
    # C-rate 加速因子
    crate_factor = 1.0 + 0.3 * (c_rate - 1.0) ** 1.5 if c_rate > 1.0 else 1.0
    # DOD 影响（深放电加速老化）
    dod_factor = 1.0 + 0.2 * (dod - 0.8) if dod > 0.8 else 1.0

    alpha_eff = alpha * temp_factor * crate_factor * dod_factor

    # 日历老化 (假设每天等效0.0055年，即~66天等效消耗一个月的日历老化)
    cal_cycles = cycle / 365  # 粗略等效年
    cal_loss = cal_alpha * np.sqrt(cal_cycles)

    # 循环老化 + 日历老化
    soh = 1.0 - alpha_eff * (cycle ** beta) - cal_loss

    # 加入随机波动（制造差异）
    soh += np.random.normal(0, 0.003)
    return np.clip(soh, 0.30, 1.0)


def internal_resistance_model(cycle, chemistry="NCM", temp_c=25):
    """内阻增长模型（Ω）"""
    if chemistry == "LFP":
        r0, growth_rate = 0.0012, 0.00008
    elif chemistry == "NCA":
        r0, growth_rate = 0.0009, 0.00012
    else:
        r0, growth_rate = 0.0010, 0.00010

    resistance = r0 * (1 + growth_rate * (cycle ** 1.1))
    resistance *= np.exp((temp_c - 25) / 25 * 0.4)
    resistance += np.random.normal(0, resistance * 0.02)
    return resistance


def simulate_battery(spec: BatterySpec, num_cycles=2000, seed=42, c_rate_var=0.3, temp_var=5):
    """
    模拟单个电池全生命周期数据

    参数:
        spec: 电池规格
        num_cycles: 模拟循环次数
        seed: 随机种子
        c_rate_var: C-rate 随机变动幅度
        temp_var: 温度随机变动幅度 (°C)
    """
    rng = np.random.RandomState(seed)
    cycles = np.arange(1, num_cycles + 1)
    data = []

    # 模拟不同的使用工况
    base_temp = 25 + rng.normal(0, 5)  # 该电池的基准工作温度
    base_crate = 0.5 + rng.exponential(0.3)  # 基准充放电倍率

    for cycle in cycles:
        # 随机工况波动
        temp_c = base_temp + rng.normal(0, temp_var)
        c_rate = np.clip(base_crate + rng.normal(0, c_rate_var), 0.2, 3.0)
        dod = np.clip(0.9 - rng.exponential(0.15), 0.4, 1.0)

        soh = capacity_fade_model(cycle, spec.chemistry, temp_c, c_rate, dod)
        resistance = internal_resistance_model(cycle, spec.chemistry, temp_c)
        current_capacity = spec.pack_capacity_kwh * soh
        coulombic_efficiency = 0.998 - (1 - soh) * 0.003

        data.append({
            "cycle": int(cycle),
            "soh": round(soh, 6),
            "capacity_kwh": round(current_capacity, 3),
            "capacity_retention_pct": round(soh * 100, 3),
            "internal_resistance_ohm": round(resistance, 8),
            "coulombic_efficiency": round(coulombic_efficiency, 6),
            "temperature_c": round(temp_c, 1),
            "c_rate": round(c_rate, 3),
            "dod": round(dod, 3),
            "chemistry": spec.chemistry,
            "battery_model": spec.name,
            "manufacturer": spec.manufacturer,
            "vehicle_model": spec.vehicle_model,
        })

    return pd.DataFrame(data)


def simulate_fleet(battery_keys=None, num_cycles=2000, batteries_per_type=5):
    """模拟整个电池车队的数据"""
    if battery_keys is None:
        battery_keys = list(BATTERY_CATALOG.keys())

    all_data = []
    for key in battery_keys:
        spec = BATTERY_CATALOG[key]
        for i in range(batteries_per_type):
            df = simulate_battery(spec, num_cycles, seed=42 + i * 100 + len(key) * 7)
            df["battery_id"] = f"{key}-{i+1:03d}"
            all_data.append(df)

    fleet_df = pd.concat(all_data, ignore_index=True)
    return fleet_df


# ============= 主程序入口 =============
if __name__ == "__main__":
    print("=" * 60)
    print("  动力电池数据模拟器 — Battery Data Simulator")
    print("=" * 60)

    # 模拟所有电池型号的车队数据
    print("\n[1] 生成电池车队模拟数据...")
    fleet_df = simulate_fleet(batteries_per_type=3, num_cycles=2000)

    csv_path = OUTPUT_DIR / "battery_fleet_data.csv"
    fleet_df.to_csv(csv_path, index=False)
    print(f"  ✓ 车队数据已保存: {csv_path}")
    print(f"    共 {len(fleet_df)} 条记录, {fleet_df['battery_id'].nunique()} 个电池")

    # 输出统计摘要
    print("\n[2] 数据摘要:")
    for chem in ["LFP", "NCM", "NCA"]:
        chem_df = fleet_df[fleet_df["chemistry"] == chem]
        if len(chem_df) == 0:
            continue
        soh80 = chem_df[chem_df["soh"] >= 0.80]["cycle"].max()
        soh70 = chem_df[chem_df["soh"] >= 0.70]["cycle"].max()
        print(f"  {chem}: 电池数={chem_df['battery_id'].nunique()}, "
              f"到80%SOH约{soh80}循环, 到70%SOH约{soh70}循环")

    # 输出单个电池示例
    first_bid = fleet_df["battery_id"].iloc[0]
    print(f"\n[3] 单电池示例 ({first_bid}):")
    single = fleet_df[fleet_df["battery_id"] == first_bid]
    print(single[["cycle", "soh", "capacity_kwh", "internal_resistance_ohm", "temperature_c"]].head(10).to_string(index=False))

    # 输出电池规格目录
    print("\n[4] 电池包规格目录:")
    for key, spec in BATTERY_CATALOG.items():
        print(f"  {key}: {spec.chemistry} | {spec.pack_capacity_kwh}kWh | "
              f"循环寿命~{spec.cycle_life_to_80pct}次 | {spec.manufacturer} | {spec.vehicle_model}")

    # 保存电池目录
    catalog_path = OUTPUT_DIR / "battery_catalog.json"
    catalog_dict = {k: {
        "name": v.name, "chemistry": v.chemistry,
        "pack_capacity_kwh": v.pack_capacity_kwh,
        "cycle_life": v.cycle_life_to_80pct,
        "manufacturer": v.manufacturer,
        "vehicle_model": v.vehicle_model,
        "pack_weight_kg": v.pack_weight_kg,
    } for k, v in BATTERY_CATALOG.items()}
    with open(catalog_path, "w", encoding="utf-8") as f:
        json.dump(catalog_dict, f, ensure_ascii=False, indent=2)
    print(f"\n  电池目录已保存: {catalog_path}")

    print("\n" + "=" * 60)
    print(f"  模拟完成 — 数据已输出到 {OUTPUT_DIR}")
    print("=" * 60)
