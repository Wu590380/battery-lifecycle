"""
连续学习引擎 — 从ESP32实时数据中持续优化SOH预测模型
每次积累够新数据就自动重训练并更新模型文件

原理：
  1. 从JSONL读取新到达的真实(模拟)数据
  2. 提取特征向量(与训练数据相同的16维)
  3. 合并原始模拟数据 + 新数据 → 全量重训练
  4. 覆盖 models/ 下的模型文件
  5. 下次预测自动使用更新后的模型

触发：定时任务 / 数据积累够1000条 / 手动执行
"""
import json
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime
from glob import glob
import warnings
warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, r2_score

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

# 模拟训练数据的参考列(必须和训练时一致)
FEATURE_COLS = [
    "cycle", "log_resistance", "cumulative_energy",
    "cap_slope", "resistance_slope", "temp_ma", "crate_ma", "dod_ma",
    "capacity_std", "avg_temp_lifetime", "avg_crate_lifetime",
    "capacity_fade_pct", "temperature_c", "c_rate", "dod",
    "chem_LFP", "chem_NCA", "chem_NCM",
]

def load_original_training_data():
    """加载原始模拟训练数据并做特征工程"""
    csv_path = DATA_DIR / "battery_fleet_data.csv"
    if not csv_path.exists():
        print("[连续学习] 原始训练数据不存在，请先运行 simulator.py")
        return None
    df = pd.read_csv(csv_path)
    print(f"[连续学习] 原始训练数据: {len(df)} 条, {df['battery_id'].nunique()} 个电池")

    # 特征工程(与soh_model.py一致)
    df = df.sort_values(["battery_id", "cycle"]).copy()
    df["log_resistance"] = np.log1p(df["internal_resistance_ohm"] * 1e6)
    df["cumulative_energy"] = df.groupby("battery_id")["capacity_kwh"].cumsum()
    window_size = 10
    features_list = []
    for bid, group in df.groupby("battery_id"):
        group = group.copy()
        if len(group) >= window_size:
            group["cap_slope"] = group["capacity_kwh"].rolling(window_size, min_periods=3).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x)>=3 else 0)
            group["resistance_slope"] = group["internal_resistance_ohm"].rolling(window_size, min_periods=3).apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x)>=3 else 0)
            group["temp_ma"] = group["temperature_c"].rolling(window_size, min_periods=3).mean()
            group["crate_ma"] = group["c_rate"].rolling(window_size, min_periods=3).mean()
            group["dod_ma"] = group["dod"].rolling(window_size, min_periods=3).mean()
            group["capacity_std"] = group["capacity_kwh"].rolling(window_size, min_periods=3).std()
        else:
            group["cap_slope"] = 0; group["resistance_slope"] = 0; group["temp_ma"] = group["temperature_c"]
            group["crate_ma"] = group["c_rate"]; group["dod_ma"] = group["dod"]; group["capacity_std"] = 0
        group["avg_temp_lifetime"] = group["temperature_c"].expanding().mean()
        group["avg_crate_lifetime"] = group["c_rate"].expanding().mean()
        group["capacity_fade_pct"] = 100*(1 - group["capacity_kwh"]/group["capacity_kwh"].iloc[0])
        features_list.append(group)
    df = pd.concat(features_list, ignore_index=True)
    chem_dummies = pd.get_dummies(df["chemistry"], prefix="chem")
    df = pd.concat([df, chem_dummies], axis=1)
    for c in ["chem_LFP","chem_NCA","chem_NCM"]:
        if c not in df.columns: df[c] = 0
    return df


def load_telemetry_data():
    """读取ESP32实时数据并转换为训练特征"""
    files = sorted(glob(str(DATA_DIR / "telemetry_*.jsonl")))
    if not files:
        print("[连续学习] 暂无遥测数据")
        return None

    rows = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
        except Exception:
            pass

    if not rows:
        return None

    df = pd.DataFrame(rows)
    print(f"[连续学习] 遥测数据: {len(df)} 条, {len(files)} 个文件")

    # 字段映射：telemetry → training format
    # 训练数据列: battery_id, cycle, soh, capacity_kwh, internal_resistance_ohm, chemistry, temperature_c, c_rate, dod, ...
    if "battery_id" not in df.columns and "vehicle_id" in df.columns:
        df["battery_id"] = df["vehicle_id"]

    if "soc_pct" in df.columns:
        df["soh"] = df["soc_pct"] / 100.0  # SOC作为当前健康度的代理

    if "capacity_kwh" not in df.columns:
        df["capacity_kwh"] = 60.0  # 默认值

    if "internal_resistance_ohm" not in df.columns:
        df["internal_resistance_ohm"] = 0.001

    if "chemistry" not in df.columns:
        df["chemistry"] = "LFP"

    if "temperature_c" not in df.columns and "pack_temp_c" in df.columns:
        df["temperature_c"] = df["pack_temp_c"]

    if "c_rate" not in df.columns:
        df["c_rate"] = 1.0

    if "dod" not in df.columns:
        df["dod"] = 0.8

    if "cycle_count" in df.columns:
        df["cycle"] = df["cycle_count"]
    elif "cycle" not in df.columns:
        df["cycle"] = df.groupby("battery_id").cumcount()

    # 模拟训练数据中的特征工程(简化版)
    df["log_resistance"] = np.log1p(df["internal_resistance_ohm"] * 1e6)
    df["cumulative_energy"] = df.groupby("battery_id")["capacity_kwh"].cumsum()
    df["cap_slope"] = 0.0
    df["resistance_slope"] = 0.0
    df["temp_ma"] = df["temperature_c"]
    df["crate_ma"] = df["c_rate"]
    df["dod_ma"] = df["dod"]
    df["capacity_std"] = 0.0
    df["avg_temp_lifetime"] = df["temperature_c"]
    df["avg_crate_lifetime"] = df["c_rate"]
    df["capacity_fade_pct"] = 0.0

    # One-hot chemistry
    for chem in ["LFP", "NCA", "NCM"]:
        col = f"chem_{chem}"
        df[col] = (df["chemistry"] == chem).astype(int)

    return df


def retrain_models():
    """
    合并原始数据 + 新数据 → 全量重训练 → 覆盖模型文件
    """
    print("\n" + "=" * 60)
    print(f"  [连续学习] 开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 1. 加载原始训练数据
    orig = load_original_training_data()
    if orig is None:
        return

    # 2. 加载新数据
    new_data = load_telemetry_data()

    # 3. 合并数据 — 只保留 orig 和 new 都有的列
    if new_data is not None and len(new_data) > 0:
        common = [c for c in FEATURE_COLS if c in orig.columns and c in new_data.columns]
        if "soh" in orig.columns and "soh" in new_data.columns:
            common.append("soh")
        if len(common) > 5:
            combined = pd.concat([orig[common], new_data[common]], ignore_index=True)
            print(f"[连续学习] 合并后数据: {len(combined)} 条 (新数据贡献 {len(new_data)} 条)")
        else:
            combined = orig
            print("[连续学习] 新数据列不匹配，仅使用原始数据")
    else:
        combined = orig

    # 4. 准备特征
    X = combined[FEATURE_COLS].fillna(0).values
    y_soh = combined["soh"].values

    # 5. 划分训练/测试集
    X_train, X_test, y_train, y_test = train_test_split(X, y_soh, test_size=0.2, random_state=42)

    # 6. 重训练
    model = xgb.XGBRegressor(
        n_estimators=200, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, random_state=42, n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    print(f"[连续学习] 新模型: MAE={mae:.6f} R²={r2:.4f}")

    # 7. 备份旧模型 → 覆盖新模型
    import shutil
    soh_path = MODEL_DIR / "soh_model.pkl"
    if soh_path.exists():
        backup = MODEL_DIR / f"soh_model_backup_{datetime.now().strftime('%Y%m%d%H%M')}.pkl"
        shutil.copy(soh_path, backup)
        print(f"[连续学习] 旧模型已备份: {backup.name}")

    with open(soh_path, "wb") as f:
        pickle.dump({"model": model, "feature_cols": FEATURE_COLS}, f)
    print(f"[连续学习] 新模型已保存: {soh_path}")
    print(f"[连续学习] 训练样本: {len(X_train)}, 评估 MAE: {mae:.6f}")

    return model


def run_continuous_loop(interval_minutes=60):
    """后台持续学习循环"""
    import time
    print(f"[连续学习] 启动定时重训练, 间隔 {interval_minutes} 分钟")
    while True:
        try:
            retrain_models()
        except Exception as e:
            print(f"[连续学习] 错误: {e}")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    retrain_models()
