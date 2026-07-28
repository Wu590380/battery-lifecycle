"""
车载电池实时监测采集器 v1.0
模拟 OBD/CAN 总线数据采集，可部署在车载 Linux/Android 系统
通过 HTTP API 将数据实时上传到 BMS 管理平台
"""
import json
import time
import random
import urllib.request
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════
API_URL = "http://localhost:8501/api/telemetry"  # 平台数据接收地址
VEHICLE_ID = "VIN-LS6A3E0EXA000001"
BATTERY_ID = "CATL-QJ-100-001"
UPLOAD_INTERVAL = 5  # 上传间隔（秒）

DATA_DIR = Path("E:/息壤杯")
DATA_DIR.mkdir(exist_ok=True)


def simulate_can_data():
    """
    模拟从 CAN 总线读取电池实时数据
    实际部署时替换为 python-can 库读取真实 CAN 报文
    """
    # 模拟电池参数波动
    base_soh = 0.92
    base_voltage = 651.0
    base_current = 15.0
    base_temp = 28.0

    # 累计循环次数（模拟缓慢增长）
    if not hasattr(simulate_can_data, "cycle_counter"):
        simulate_can_data.cycle_counter = 850  # 起始循环次数
    simulate_can_data.cycle_counter += 0.001  # 每次调用微增，约每天增加 17 次

    return {
        "timestamp": datetime.now().isoformat(),
        "vehicle_id": VEHICLE_ID,
        "battery_id": BATTERY_ID,
        # ── 电池状态 ──
        "pack_voltage_v": round(base_voltage + random.gauss(0, 2.0), 1),
        "pack_current_a": round(base_current + random.gauss(0, 5.0), 1),
        "soc_pct": round(random.uniform(45, 85), 1),
        "soh_pct": round(base_soh * 100 + random.gauss(0, 0.02), 2),
        "cycle_count": int(simulate_can_data.cycle_counter),
        "pack_temp_c": round(base_temp + random.gauss(0, 1.5), 1),
        # ── 单体电芯 ──
        "cell_voltage_min_v": round(3.65 + random.gauss(0, 0.01), 3),
        "cell_voltage_max_v": round(3.72 + random.gauss(0, 0.01), 3),
        "cell_voltage_diff_v": round(random.uniform(0.002, 0.015), 4),  # 压差
        "cell_temp_max_c": round(base_temp + random.gauss(0, 2.0), 1),
        # ── 绝缘与安全 ──
        "insulation_resistance_kohm": round(random.uniform(5000, 9999), 0),  # 绝缘电阻
        "bms_status": 0 if random.random() < 0.95 else random.choice([1,2]),  # 0=正常, 1=警告, 2=故障
        # ── 行驶数据 ──
        "speed_kmh": round(random.uniform(0, 80), 0),
        "odometer_km": round(28500 + random.uniform(0, 1), 1),
        "power_kw": round(base_voltage * base_current / 1000 * random.uniform(0.5, 1.5), 1),
        # ── GPS ──
        "latitude": round(29.5583 + random.uniform(-0.01, 0.01), 6),
        "longitude": round(106.5670 + random.uniform(-0.01, 0.01), 6),
    }


def upload_data(data):
    """将数据上传到管理平台"""
    try:
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False  # HTTP server not available — local storage is sufficient


def save_local(data):
    """本地备份存储"""
    local_file = DATA_DIR / f"telemetry_{datetime.now().strftime('%Y%m%d')}.jsonl"
    with open(local_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")


def run_collector():
    """主循环：持续采集并上传"""
    print(f"[车载采集器] 启动")
    print(f"  车辆: {VEHICLE_ID}")
    print(f"  电池: {BATTERY_ID}")
    print(f"  上传间隔: {UPLOAD_INTERVAL}s")
    print(f"  平台地址: {API_URL}")
    print()

    while True:
        try:
            data = simulate_can_data()
            save_local(data)

            # Try HTTP upload (optional — local file is sufficient for BMS platform)
            success = upload_data(data)
            status = "OK" if success else "SAVED"
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] {status} "
                  f"SOC:{data['soc_pct']:.1f}% SOH:{data['soh_pct']:.2f}% "
                  f"V:{data['pack_voltage_v']:.1f}V I:{data['pack_current_a']:.1f}A "
                  f"T:{data['pack_temp_c']:.1f}°C (本地已存)")

            time.sleep(UPLOAD_INTERVAL)
        except KeyboardInterrupt:
            print("\n[车载采集器] 已停止")
            break
        except Exception as e:
            print(f"  [错误] {e}")
            time.sleep(UPLOAD_INTERVAL)


if __name__ == "__main__":
    run_collector()
