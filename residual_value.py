"""
电池残值评估引擎 — Battery Residual Value Estimator
多维度加权评分模型，结合SOH预测、市场行情和梯次利用潜力
参考2024-2025年中国动力电池市场实际行情
"""
import numpy as np
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
import json
import pickle
from datetime import datetime, timedelta

OUTPUT_DIR = Path(__file__).parent / "data"
OUTPUT_DIR.mkdir(exist_ok=True)
MODEL_DIR = Path(__file__).parent / "models"

# ============ 市场行情数据 (2025年基准，整车Pack级别) ============
MARKET_PRICE = {
    "LFP": {"new_pack_rmb_per_kwh": 750, "recycle_rmb_per_kwh": 150},
    "NCM": {"new_pack_rmb_per_kwh": 950, "recycle_rmb_per_kwh": 200},
    "NCA": {"new_pack_rmb_per_kwh": 1000, "recycle_rmb_per_kwh": 180},
}

# 梯次利用场景及对应价值系数
SECOND_LIFE_SCENARIOS = {
    "automotive": {"name": "车用动力电池", "soh_min": 0.80, "soh_max": 1.00, "value_factor": 0.85},
    "grid_storage": {"name": "电网储能", "soh_min": 0.60, "soh_max": 0.80, "value_factor": 0.45},
    "backup_power": {"name": "备电系统", "soh_min": 0.50, "soh_max": 0.70, "value_factor": 0.35},
    "low_speed_vehicle": {"name": "低速车/两轮车", "soh_min": 0.40, "soh_max": 0.60, "value_factor": 0.25},
    "recycling": {"name": "材料回收", "soh_min": 0.00, "soh_max": 0.40, "value_factor": 0.12},
}


@dataclass
class ResidualValueReport:
    """残值评估报告"""
    battery_id: str
    battery_model: str
    chemistry: str
    manufacturer: str
    pack_capacity_kwh: float
    vehicle_model: str

    # 当前状态
    current_soh: float
    current_cycle: int
    estimated_remaining_cycles: int
    usage_severity: str  # mild / normal / severe

    # 估值
    new_value_rmb: float          # 新电池价值
    residual_value_rmb: float     # 预估残值
    value_retention_pct: float    # 残值率
    confidence_low: float
    confidence_high: float

    # 梯次利用
    second_life_scenario: str
    second_life_value_rmb: float
    recycle_value_rmb: float

    # 建议
    recommendation: str
    assessment_date: str


def load_models():
    """加载训练好的模型"""
    with open(MODEL_DIR / "soh_model.pkl", "rb") as f:
        soh_pkg = pickle.load(f)
    with open(MODEL_DIR / "rul_model.pkl", "rb") as f:
        rul_pkg = pickle.load(f)
    return soh_pkg["model"], rul_pkg["model"], soh_pkg["feature_cols"]


def estimate_residual_value(
    battery_spec: dict,     # 电池规格
    current_soh: float,     # 当前SOH (0~1)
    current_cycle: int,     # 当前循环数
    estimated_rul: int,     # 预测剩余循环数
    usage_severity: str = "normal",  # 使用强度
    calendar_age_months: int = 24,   # 日历老化（月）
    condition_factor: float = 1.0,   # 外观/硬件检查系数（0-1）
    custom_prices: dict = None,      # 自定义市场行情价格
) -> ResidualValueReport:
    """
    核心残值评估算法

    评估维度权重：
    - 健康度 (SOH + RUL): 40%
    - 市场行情: 25%
    - 品牌/型号溢价: 20%
    - 梯次利用潜力: 15%
    """
    chem = battery_spec["chemistry"]
    pack_kwh = battery_spec.get("pack_capacity_kwh", battery_spec.get("nominal_capacity_ah", 50))

    # 新电池市场价值（按整车Pack价格，支持自定义行情）
    if custom_prices and chem in custom_prices:
        new_price_per_kwh = custom_prices[chem]
    else:
        new_price_per_kwh = MARKET_PRICE[chem]["new_pack_rmb_per_kwh"]
    new_value = pack_kwh * new_price_per_kwh

    # ============ 维度1: 健康度评分 (40%) ============
    # SOH权重70% + RUL权重30%
    soh_score = current_soh * 100  # 0-100

    # RUL评分: 剩余循环 / 标称循环寿命
    cycle_life = battery_spec.get("cycle_life", 2000)
    rul_score = min(estimated_rul / cycle_life * 100, 100)
    health_score = soh_score * 0.70 + rul_score * 0.30

    # ============ 维度2: 市场行情 (25%) ============
    # LFP在2024-2025年价格快速下行，NCM相对稳定
    if chem == "LFP":
        market_trend = 0.88  # LFP价格下行约12%
    elif chem == "NCA":
        market_trend = 0.92
    else:
        market_trend = 0.90
    market_score = market_trend * 100

    # ============ 维度3: 品牌/型号溢价 (20%) ============
    # Brand score: base 90, premium brands get bonus up to 100
    brand_premium = {
        "比亚迪/弗迪": 98,
        "宁德时代": 100,
        "松下": 95,
        "中创新航": 88,
        "国轩高科": 85,
    }
    brand_score = brand_premium.get(battery_spec.get("manufacturer", ""), 85)

    # ============ 维度4: 梯次利用潜力 (15%) ============
    # 根据SOH判断最适合的梯次利用场景
    second_life_scenario = None
    sl_value_factor = 0
    for key, scenario in SECOND_LIFE_SCENARIOS.items():
        if scenario["soh_min"] <= current_soh <= scenario["soh_max"]:
            second_life_scenario = scenario
            sl_value_factor = scenario["value_factor"]
            break

    if second_life_scenario is None:
        second_life_scenario = SECOND_LIFE_SCENARIOS["recycling"]
        sl_value_factor = second_life_scenario["value_factor"]

    second_life_score = sl_value_factor * 100  # 0-100 scale

    # ============ 使用强度修正系数 ============
    severity_factor = {"mild": 1.00, "normal": 0.95, "severe": 0.85}[usage_severity]

    # 日历老化修正（每月约0.5%贬值）
    calendar_factor = max(0.60, 1.0 - calendar_age_months * 0.005)

    # ============ 综合加权 ============
    weights = {"health": 0.40, "market": 0.25, "brand": 0.20, "second_life": 0.15}

    composite_score = (
        health_score * weights["health"]
        + market_score * weights["market"]
        + brand_score * weights["brand"]
        + second_life_score * weights["second_life"]
    )

    # 残值 = 新电池价值 × 综合得分率 × 修正系数 × 外观硬件系数（上限100%）
    value_retention = min(composite_score / 100 * severity_factor * calendar_factor * condition_factor, 1.0)
    residual_value = new_value * value_retention

    # 置信区间 (±10%)
    conf_range = residual_value * 0.10

    # 梯次利用价值
    sl_value = new_value * sl_value_factor * calendar_factor
    # Recycle value with custom prices
    recycle_key = f"{chem}_recycle"
    if custom_prices and recycle_key in custom_prices:
        recycle_price = custom_prices[recycle_key]
    else:
        recycle_price = MARKET_PRICE[chem]["recycle_rmb_per_kwh"]
    recycle_value = pack_kwh * recycle_price

    # 生成建议
    if current_soh >= 0.80:
        recommendation = "建议继续作为车用动力电池使用，SOH良好"
    elif current_soh >= 0.60:
        recommendation = f"建议转入{second_life_scenario['name']}梯次利用，预估收益{sl_value:.0f}元"
    elif current_soh >= 0.40:
        recommendation = f"建议用于{second_life_scenario['name']}，或考虑材料回收({recycle_value:.0f}元)"
    else:
        recommendation = f"建议直接进入材料回收流程，预估回收价值{recycle_value:.0f}元"

    return ResidualValueReport(
        battery_id="",
        battery_model=battery_spec.get("name", ""),
        chemistry=chem,
        manufacturer=battery_spec.get("manufacturer", ""),
        pack_capacity_kwh=round(pack_kwh, 1),
        vehicle_model=battery_spec.get("vehicle_model", ""),
        current_soh=round(current_soh, 4),
        current_cycle=current_cycle,
        estimated_remaining_cycles=estimated_rul,
        usage_severity=usage_severity,
        new_value_rmb=round(new_value, 0),
        residual_value_rmb=round(residual_value, 0),
        value_retention_pct=round(value_retention * 100, 1),
        confidence_low=round(residual_value - conf_range, 0),
        confidence_high=round(residual_value + conf_range, 0),
        second_life_scenario=second_life_scenario["name"],
        second_life_value_rmb=round(sl_value, 0),
        recycle_value_rmb=round(recycle_value, 0),
        recommendation=recommendation,
        assessment_date=datetime.now().strftime("%Y-%m-%d"),
    )


def batch_assessment(fleet_df, battery_catalog):
    """
    对车队数据进行批量残值评估
    基于预测的SOH和RUL对每个电池的关键节点进行评估
    """
    results = []

    for battery_id, group in fleet_df.groupby("battery_id"):
        spec_key = "-".join(battery_id.split("-")[:-1])  # 去掉序号
        spec = battery_catalog.get(spec_key, list(battery_catalog.values())[0])

        # 最后一条记录作为"当前状态"
        last = group.iloc[-1]
        mid = group.iloc[len(group) // 2]  # 中期评估

        for label, row in [("当前", last), ("中期", mid)]:
            temp = row.get("temperature_c", 25) if "temperature_c" in row.index else 25
            usage = "severe" if temp > 35 else ("mild" if temp < 20 else "normal")

            report = estimate_residual_value(
                battery_spec={
                    "name": spec.name,
                    "chemistry": spec.chemistry,
                    "pack_capacity_kwh": spec.pack_capacity_kwh,
                    "cycle_life": spec.cycle_life_to_80pct,
                    "manufacturer": spec.manufacturer,
                },
                current_soh=row.get("soh_predicted", row["soh"]),
                current_cycle=int(row["cycle"]),
                estimated_rul=int(row.get("rul_predicted", 100)),
                usage_severity=usage,
                calendar_age_months=int(row["cycle"] / 365 * 12),
            )
            report.battery_id = battery_id

            results.append({
                "battery_id": report.battery_id,
                "assessment_point": label,
                "battery_model": report.battery_model,
                "chemistry": report.chemistry,
                "manufacturer": report.manufacturer,
                "pack_capacity_kwh": report.pack_capacity_kwh,
                "current_soh": report.current_soh,
                "current_cycle": report.current_cycle,
                "new_value_rmb": report.new_value_rmb,
                "residual_value_rmb": report.residual_value_rmb,
                "value_retention_pct": report.value_retention_pct,
                "second_life_scenario": report.second_life_scenario,
                "second_life_value_rmb": report.second_life_value_rmb,
                "recycle_value_rmb": report.recycle_value_rmb,
                "recommendation": report.recommendation,
            })

    return pd.DataFrame(results)


# ============= 主程序 =============
if __name__ == "__main__":
    print("=" * 60)
    print("  电池残值评估引擎 — Residual Value Estimator")
    print("=" * 60)

    # 加载预测数据
    pred_path = OUTPUT_DIR / "battery_prediction_report.csv"
    fleet_df = pd.read_csv(pred_path)

    # 导入电池规格
    from simulator import BATTERY_CATALOG

    # 批量评估
    print("\n[1] 执行批量残值评估...")
    assessment_df = batch_assessment(fleet_df, BATTERY_CATALOG)
    assessment_path = OUTPUT_DIR / "battery_residual_value_assessment.csv"
    assessment_df.to_csv(assessment_path, index=False)
    print(f"  评估报告已保存: {assessment_path}")
    print(f"  共评估 {len(assessment_df)} 条记录")

    # 统计摘要
    print("\n[2] 评估摘要:")
    for chem in ["LFP", "NCM", "NCA"]:
        chem_df = assessment_df[assessment_df["chemistry"] == chem]
        if len(chem_df) == 0:
            continue
        cur = chem_df[chem_df["assessment_point"] == "当前"]
        print(f"  {chem}: 平均新电池价值={cur['new_value_rmb'].mean():.0f}元, "
              f"平均残值={cur['residual_value_rmb'].mean():.0f}元, "
              f"平均残值率={cur['value_retention_pct'].mean():.1f}%")

    # 单个详细报告示例
    print("\n[3] 单个电池详细评估报告:")
    print("-" * 60)

    # 选择一个NCM电池和LFP电池做对比演示
    for demo_bid in ["CATL-QJ-100-001", "BYD-Blade-85-001"]:
        spec_key = "-".join(demo_bid.split("-")[:-1])
        spec = BATTERY_CATALOG[spec_key]
        battery_data = fleet_df[fleet_df["battery_id"] == demo_bid]

        if len(battery_data) == 0:
            continue

        # 取500循环时的数据作为评估点
        row = battery_data.iloc[min(500, len(battery_data) - 1)]

        report = estimate_residual_value(
            battery_spec={
                "name": spec.name,
                "chemistry": spec.chemistry,
                "pack_capacity_kwh": spec.pack_capacity_kwh,
                "cycle_life": spec.cycle_life_to_80pct,
                "manufacturer": spec.manufacturer,
            },
            current_soh=row.get("soh_predicted", row["soh"]),
            current_cycle=int(row["cycle"]),
            estimated_rul=int(row.get("rul_predicted", 1500)),
            usage_severity="normal",
            calendar_age_months=18,
        )
        report.battery_id = demo_bid

        print(f"\n  🔋 {report.battery_model} ({report.chemistry})")
        print(f"     制造商: {report.manufacturer}")
        print(f"     电池包容量: {report.pack_capacity_kwh} kWh")
        print(f"     当前循环: {report.current_cycle} 次")
        print(f"     当前SOH: {report.current_soh*100:.1f}%")
        print(f"     预估剩余循环: {report.estimated_remaining_cycles} 次")
        print(f"     ─────────────────────────────")
        print(f"     新电池价值: {report.new_value_rmb:,.0f} 元")
        print(f"     预估残值:   {report.residual_value_rmb:,.0f} 元")
        print(f"     残值率:     {report.value_retention_pct:.1f}%")
        print(f"     置信区间:   [{report.confidence_low:,.0f} - {report.confidence_high:,.0f}] 元")
        print(f"     梯次利用场景: {report.second_life_scenario} (价值 {report.second_life_value_rmb:,.0f} 元)")
        print(f"     回收价值:     {report.recycle_value_rmb:,.0f} 元")
        print(f"     💡 建议: {report.recommendation}")

    print("\n" + "=" * 60)
    print("  残值评估完成！")
    print("=" * 60)
