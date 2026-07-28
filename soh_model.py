"""
SOH预测模型 — 基于XGBoost的电池健康状态与剩余寿命预测
使用模拟数据训练，支持特征重要性分析和SHAP可解释性
"""
import numpy as np
import pandas as pd
from pathlib import Path
import pickle
import warnings
warnings.filterwarnings("ignore")

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import xgboost as xgb

OUTPUT_DIR = Path("E:/息壤杯")
OUTPUT_DIR.mkdir(exist_ok=True)
MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(exist_ok=True)


def load_data():
    """加载电池车队数据"""
    csv_path = OUTPUT_DIR / "battery_fleet_data.csv"
    df = pd.read_csv(csv_path)
    print(f"  数据加载: {len(df)} 条记录, {df['battery_id'].nunique()} 个电池")
    return df


def engineer_features(df, window_size=10):
    """
    特征工程 — 从原始循环数据中提取健康因子

    滑动窗口特征 + 趋势特征 + 累计特征
    """
    print("  特征工程中...")
    df = df.sort_values(["battery_id", "cycle"]).copy()

    # 基础特征
    df["log_resistance"] = np.log1p(df["internal_resistance_ohm"] * 1e6)  # μΩ 对数
    df["cumulative_energy"] = df.groupby("battery_id")["capacity_kwh"].cumsum()

    features_list = []
    for bid, group in df.groupby("battery_id"):
        group = group.copy()

        # 滑动窗口统计（最近N个循环）
        if len(group) >= window_size:
            group["cap_slope"] = (
                group["capacity_kwh"].rolling(window_size, min_periods=3)
                .apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) >= 3 else 0)
            )
            group["resistance_slope"] = (
                group["internal_resistance_ohm"].rolling(window_size, min_periods=3)
                .apply(lambda x: np.polyfit(range(len(x)), x, 1)[0] if len(x) >= 3 else 0)
            )
            group["temp_ma"] = group["temperature_c"].rolling(window_size, min_periods=3).mean()
            group["crate_ma"] = group["c_rate"].rolling(window_size, min_periods=3).mean()
            group["dod_ma"] = group["dod"].rolling(window_size, min_periods=3).mean()
            group["capacity_std"] = group["capacity_kwh"].rolling(window_size, min_periods=3).std()
        else:
            group["cap_slope"] = 0
            group["resistance_slope"] = 0
            group["temp_ma"] = group["temperature_c"]
            group["crate_ma"] = group["c_rate"]
            group["dod_ma"] = group["dod"]
            group["capacity_std"] = 0

        # 累积特征（从起始到当前的统计）
        group["avg_temp_lifetime"] = group["temperature_c"].expanding().mean()
        group["avg_crate_lifetime"] = group["c_rate"].expanding().mean()
        group["capacity_fade_pct"] = 100 * (1 - group["capacity_kwh"] / group["capacity_kwh"].iloc[0])

        features_list.append(group)

    df_feat = pd.concat(features_list, ignore_index=True)

    # One-hot编码化学体系
    chem_dummies = pd.get_dummies(df_feat["chemistry"], prefix="chem")
    df_feat = pd.concat([df_feat, chem_dummies], axis=1)

    return df_feat


def prepare_training_data(df_feat):
    """准备训练/测试数据"""

    feature_cols = [
        "cycle", "log_resistance", "cumulative_energy",
        "cap_slope", "resistance_slope", "temp_ma", "crate_ma", "dod_ma",
        "capacity_std", "avg_temp_lifetime", "avg_crate_lifetime",
        "capacity_fade_pct", "temperature_c", "c_rate", "dod",
        "chem_LFP", "chem_NCA", "chem_NCM",
    ]

    # 确保所有化学列存在
    for c in ["chem_LFP", "chem_NCA", "chem_NCM"]:
        if c not in df_feat.columns:
            df_feat[c] = 0

    X = df_feat[feature_cols].fillna(0).values  # 转numpy避免Arrow兼容问题
    y_soh = df_feat["soh"].values            # 当前SOH
    y_rul = (df_feat.groupby("battery_id")["cycle"].transform("max") - df_feat["cycle"]).values  # 剩余循环数

    # 按电池分组划分，避免数据泄漏
    unique_batteries = list(df_feat["battery_id"].unique())
    train_bats, test_bats = train_test_split(unique_batteries, test_size=0.2, random_state=42)

    train_idx = df_feat["battery_id"].isin(train_bats)
    test_idx = df_feat["battery_id"].isin(test_bats)

    X_train, X_test = X[train_idx], X[test_idx]
    y_soh_train, y_soh_test = y_soh[train_idx], y_soh[test_idx]
    y_rul_train, y_rul_test = y_rul[train_idx], y_rul[test_idx]

    return X_train, X_test, y_soh_train, y_soh_test, y_rul_train, y_rul_test, feature_cols


def train_soh_model(X_train, y_train, X_test, y_test):
    """训练SOH预测模型"""
    print("\n  训练SOH预测模型 (XGBoost)...")

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"    SOH MAE:  {mae:.6f} ({mae*100:.2f}%)")
    print(f"    SOH RMSE: {rmse:.6f}")
    print(f"    SOH R²:   {r2:.4f}")

    return model


def train_rul_model(X_train, y_train, X_test, y_test):
    """训练剩余寿命(RUL)预测模型"""
    print("\n  训练剩余循环寿命预测模型 (XGBoost)...")

    model = xgb.XGBRegressor(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"    RUL MAE:  {mae:.1f} 循环 ({mae/2000*100:.1f}%)")
    print(f"    RUL RMSE: {rmse:.1f} 循环")
    print(f"    RUL R²:   {r2:.4f}")

    return model


def feature_importance_analysis(model, feature_names, title="SOH"):
    """特征重要性分析"""
    importance = model.feature_importances_
    indices = np.argsort(importance)[::-1]

    print(f"\n  [{title}] Top 10 特征重要性:")
    for i in range(min(10, len(indices))):
        idx = indices[i]
        print(f"    {i+1}. {feature_names[idx]:25s} = {importance[idx]:.4f}")

    return dict(zip([feature_names[i] for i in indices], importance[indices]))


def predict_single_battery(model_soh, model_rul, df_battery, feature_cols):
    """
    对单个电池进行全生命周期SOH预测

    df_battery: 单个电池的特征DataFrame
    """
    X = df_battery[feature_cols].fillna(0).values

    soh_pred = model_soh.predict(X)
    rul_pred = model_rul.predict(X)

    return soh_pred, rul_pred


# ============= 主程序 =============
if __name__ == "__main__":
    print("=" * 60)
    print("  SOH预测模型训练 — XGBoost Regression")
    print("=" * 60)

    # 1. 加载数据
    df = load_data()

    # 2. 特征工程
    df_feat = engineer_features(df)

    # 3. 准备数据
    X_train, X_test, y_soh_train, y_soh_test, y_rul_train, y_rul_test, feature_cols = prepare_training_data(df_feat)
    print(f"  训练集: {len(X_train)} 样本, 测试集: {len(X_test)} 样本")

    # 4. 训练模型
    model_soh = train_soh_model(X_train, y_soh_train, X_test, y_soh_test)
    model_rul = train_rul_model(X_train, y_rul_train, X_test, y_rul_test)

    # 5. 特征重要性
    importance_soh = feature_importance_analysis(model_soh, feature_cols, "SOH")
    importance_rul = feature_importance_analysis(model_rul, feature_cols, "RUL")

    # 6. 保存模型
    model_soh_path = MODEL_DIR / "soh_model.pkl"
    model_rul_path = MODEL_DIR / "rul_model.pkl"
    with open(model_soh_path, "wb") as f:
        pickle.dump({"model": model_soh, "feature_cols": feature_cols}, f)
    with open(model_rul_path, "wb") as f:
        pickle.dump({"model": model_rul, "feature_cols": feature_cols}, f)
    print(f"\n  模型已保存: {model_soh_path}")
    print(f"  模型已保存: {model_rul_path}")

    # 7. 演示预测 — 取一个电池样本
    print("\n" + "=" * 60)
    print("  预测演示 — 单电池全生命周期评估")
    print("=" * 60)

    demo_battery = df_feat[df_feat["battery_id"] == "BYD-Blade-85-001"].copy()
    X_demo = demo_battery[feature_cols].fillna(0)

    soh_pred = model_soh.predict(X_demo)
    rul_pred = model_rul.predict(X_demo)

    # 输出几个关键节点的预测
    checkpoints = [1, 100, 500, 1000, 1500, 1800, 1990]
    print(f"\n  {'循环':>6s}  {'真实SOH':>8s}  {'预测SOH':>8s}  {'偏差':>8s}  {'剩余循环':>8s}")
    print(f"  {'-'*50}")
    for cp in checkpoints:
        idx = min(cp - 1, len(demo_battery) - 1)
        row = demo_battery.iloc[idx]
        true_soh = row["soh"]
        pred_soh = soh_pred[idx]
        pred_rul = rul_pred[idx]
        error = (pred_soh - true_soh) * 100
        print(f"  {cp:6d}  {true_soh:7.4f}  {pred_soh:8.4f}  {error:+7.2f}%  {pred_rul:8.0f}")

    # 8. 生成预测报告CSV
    print("\n  生成全量预测报告...")
    all_X = df_feat[feature_cols].fillna(0)
    df_feat["soh_predicted"] = model_soh.predict(all_X)
    df_feat["rul_predicted"] = model_rul.predict(all_X)

    report_cols = ["battery_id", "cycle", "soh", "soh_predicted", "rul_predicted",
                   "capacity_kwh", "internal_resistance_ohm", "chemistry", "battery_model"]
    report_df = df_feat[report_cols].copy()
    report_path = OUTPUT_DIR / "battery_prediction_report.csv"
    report_df.to_csv(report_path, index=False)
    print(f"  预测报告已保存: {report_path}")

    print("\n" + "=" * 60)
    print("  模型训练完成！")
    print("=" * 60)
