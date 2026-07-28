"""
电池数字护照 — Battery Digital Passport (简化版区块链)
基于哈希链的电池全生命周期数据追溯系统
符合EU Battery Regulation 2023/1542 数字护照框架
"""
import hashlib
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional, List
import uuid

OUTPUT_DIR = Path("E:/息壤杯")
OUTPUT_DIR.mkdir(exist_ok=True)


@dataclass
class BatteryPassportEvent:
    """电池护照中的一条生命周期事件"""
    event_id: str
    event_type: str          # manufacturing / installation / maintenance / inspection / decommission
    timestamp: str
    location: str            # 发生地点
    operator: str            # 操作方
    description: str
    data: dict = field(default_factory=dict)  # 详细参数
    prev_hash: str = ""      # 前一个事件的哈希
    event_hash: str = ""     # 当前事件的哈希


@dataclass
class BatteryPassport:
    """电池数字护照主体"""
    passport_id: str
    battery_id: str
    battery_model: str
    manufacturer: str
    chemistry: str
    nominal_capacity_ah: float
    nominal_voltage_v: float
    manufacturing_date: str
    serial_number: str
    initial_soh: float = 1.0
    events: List[BatteryPassportEvent] = field(default_factory=list)

    def to_dict(self):
        """转换为字典用于JSON序列化"""
        return {
            "passport_id": self.passport_id,
            "battery_id": self.battery_id,
            "battery_model": self.battery_model,
            "manufacturer": self.manufacturer,
            "chemistry": self.chemistry,
            "nominal_capacity_ah": self.nominal_capacity_ah,
            "nominal_voltage_v": self.nominal_voltage_v,
            "manufacturing_date": self.manufacturing_date,
            "serial_number": self.serial_number,
            "initial_soh": self.initial_soh,
            "events": [asdict(e) for e in self.events],
            "event_count": len(self.events),
            "last_updated": datetime.now().isoformat(),
            "integrity_verified": False,  # will be set after verification
        }


def compute_hash(event: BatteryPassportEvent) -> str:
    """计算事件的SHA-256哈希值"""
    content = json.dumps({
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "location": event.location,
        "operator": event.operator,
        "description": event.description,
        "data": event.data,
        "prev_hash": event.prev_hash,
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def create_passport(
    battery_id: str,
    battery_model: str,
    manufacturer: str,
    chemistry: str,
    nominal_capacity_ah: float,
    nominal_voltage_v: float = 3.7,
    manufacturing_date: str = None,
    serial_number: str = None,
) -> BatteryPassport:
    """创建新的电池数字护照"""
    passport_id = f"BDP-{uuid.uuid4().hex[:12].upper()}"

    if manufacturing_date is None:
        manufacturing_date = datetime.now().strftime("%Y-%m-%d")
    if serial_number is None:
        serial_number = f"SN-{uuid.uuid4().hex[:8].upper()}"

    return BatteryPassport(
        passport_id=passport_id,
        battery_id=battery_id,
        battery_model=battery_model,
        manufacturer=manufacturer,
        chemistry=chemistry,
        nominal_capacity_ah=nominal_capacity_ah,
        nominal_voltage_v=nominal_voltage_v,
        manufacturing_date=manufacturing_date,
        serial_number=serial_number,
    )


def add_event(
    passport: BatteryPassport,
    event_type: str,
    location: str,
    operator: str,
    description: str,
    data: dict = None,
) -> BatteryPassport:
    """向护照添加一条生命周期事件（自动构建哈希链）"""
    # 获取前一个事件的哈希
    prev_hash = ""
    if passport.events:
        prev_hash = passport.events[-1].event_hash

    event = BatteryPassportEvent(
        event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
        event_type=event_type,
        timestamp=datetime.now().isoformat(),
        location=location,
        operator=operator,
        description=description,
        data=data or {},
        prev_hash=prev_hash,
    )

    # 计算当前事件哈希（包含prev_hash）
    event.event_hash = compute_hash(event)
    passport.events.append(event)

    return passport


def verify_passport(passport: BatteryPassport) -> dict:
    """
    验证护照完整性 — 重新计算哈希链验证是否被篡改

    返回: {"valid": bool, "issues": list, "verified_at": str}
    """
    issues = []

    if not passport.events:
        return {"valid": True, "issues": [], "verified_at": datetime.now().isoformat()}

    for i, event in enumerate(passport.events):
        # 检查prev_hash是否匹配
        expected_prev = "" if i == 0 else passport.events[i - 1].event_hash
        if event.prev_hash != expected_prev:
            issues.append(
                f"事件 {event.event_id} (第{i+1}条) 的prev_hash不匹配: "
                f"期望 {expected_prev[:16]}..., 实际 {event.prev_hash[:16]}..."
            )

        # 重新计算当前事件哈希
        recalculated = compute_hash(event)
        if recalculated != event.event_hash:
            issues.append(
                f"事件 {event.event_id} (第{i+1}条) 的哈希值不匹配: 数据可能被篡改!"
            )

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "verified_at": datetime.now().isoformat(),
        "total_events": len(passport.events),
    }


def tamper_passport(passport: BatteryPassport, event_index: int, new_soh: float) -> BatteryPassport:
    """
    【仅用于演示】篡改某个事件的SOH数据，展示验证机制能检测到
    """
    if 0 <= event_index < len(passport.events):
        passport.events[event_index].data["soh"] = new_soh
        # 注意：我们不重新计算哈希 — 这样验证就能检测到篡改
    return passport


def export_passport_json(passport: BatteryPassport, filepath: Path = None) -> Path:
    """导出护照为JSON文件"""
    if filepath is None:
        filepath = OUTPUT_DIR / f"passport_{passport.passport_id}.json"

    data = passport.to_dict()

    # 验证完整性
    verification = verify_passport(passport)
    data["integrity_verified"] = verification["valid"]
    data["verification"] = verification

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return filepath


def import_passport_json(filepath: Path) -> BatteryPassport:
    """从JSON文件导入护照"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    passport = BatteryPassport(
        passport_id=data["passport_id"],
        battery_id=data["battery_id"],
        battery_model=data["battery_model"],
        manufacturer=data["manufacturer"],
        chemistry=data["chemistry"],
        nominal_capacity_ah=data["nominal_capacity_ah"],
        nominal_voltage_v=data["nominal_voltage_v"],
        manufacturing_date=data["manufacturing_date"],
        serial_number=data["serial_number"],
        initial_soh=data.get("initial_soh", 1.0),
    )

    for evt_data in data["events"]:
        event = BatteryPassportEvent(**evt_data)
        passport.events.append(event)

    return passport


# ============= 主程序演示 =============
if __name__ == "__main__":
    print("=" * 60)
    print("  电池数字护照 — Battery Digital Passport (Hash-Chain)")
    print("=" * 60)

    # 1. 创建护照
    print("\n[1] 创建电池数字护照...")
    passport = create_passport(
        battery_id="CATL-NCM811-001",
        battery_model="CATL NCM811",
        manufacturer="宁德时代",
        chemistry="NCM",
        nominal_capacity_ah=180.0,
        nominal_voltage_v=3.7,
    )
    print(f"  护照ID: {passport.passport_id}")
    print(f"  电池SN: {passport.serial_number}")
    print(f"  制造商: {passport.manufacturer}")

    # 2. 添加生命周期事件
    print("\n[2] 记录生命周期事件...")

    # 事件1: 出厂
    add_event(passport, "manufacturing", "宁德时代重庆工厂",
              "CATL", "电池模组出厂检验合格",
              {"soh": 1.0, "capacity_ah": 180.0, "internal_resistance_mohm": 0.8})
    print(f"  ✓ 出厂检验 (SOH=100%) — 哈希: {passport.events[-1].event_hash[:20]}...")

    # 事件2: 装车
    add_event(passport, "installation", "赛力斯两江工厂",
              "SERES", "装入问界M9电池包",
              {"vehicle_model": "问界M9", "vin": "LM8ABCDEF12345678", "pack_id": "PACK-001"})
    print(f"  ✓ 装车 (问界M9) — 哈希: {passport.events[-1].event_hash[:20]}...")

    # 事件3: 首次维保
    add_event(passport, "maintenance", "重庆赛力斯4S店",
              "SERES Service", "1万公里例行维保，电池健康检查",
              {"soh": 0.985, "mileage_km": 10000, "capacity_ah": 177.3,
               "internal_resistance_mohm": 0.92, "cell_balance_ok": True})
    print(f"  ✓ 首次维保 (SOH=98.5%) — 哈希: {passport.events[-1].event_hash[:20]}...")

    # 事件4: 5万公里检查
    add_event(passport, "inspection", "重庆西部科学城检测中心",
              "第三方检测", "5万公里深度检测",
              {"soh": 0.935, "mileage_km": 50000, "capacity_ah": 168.3,
               "internal_resistance_mohm": 1.15, "max_temp_c": 42})
    print(f"  ✓ 5万公里检测 (SOH=93.5%) — 哈希: {passport.events[-1].event_hash[:20]}...")

    # 事件5: 10万公里维保
    add_event(passport, "maintenance", "重庆赛力斯4S店",
              "SERES Service", "10万公里维保，SOH下降至89%",
              {"soh": 0.89, "mileage_km": 100000, "capacity_ah": 160.2,
               "internal_resistance_mohm": 1.45, "recommendation": "继续使用"})
    print(f"  ✓ 10万公里维保 (SOH=89.0%) — 哈希: {passport.events[-1].event_hash[:20]}...")

    # 3. 验证护照
    print("\n[3] 验证护照完整性...")
    result = verify_passport(passport)
    status = "✅ 通过" if result["valid"] else "❌ 未通过"
    print(f"  验证状态: {status}")
    print(f"  事件总数: {result['total_events']}")
    if result["issues"]:
        for issue in result["issues"]:
            print(f"  ⚠️ {issue}")

    # 4. 导出护照
    print("\n[4] 导出护照JSON...")
    json_path = export_passport_json(passport)
    print(f"  护照已导出: {json_path}")

    # 5. 篡改演示
    print("\n[5] 安全演示 — 尝试篡改数据...")
    print("  将事件2的SOH从98.5%改为75.0%...")
    tamper_passport(passport, 2, 0.75)  # 篡改第3个事件（首次维保）

    tamper_result = verify_passport(passport)
    status = "✅ 通过" if tamper_result["valid"] else "❌ 未通过"
    print(f"  篡改后验证状态: {status}")
    for issue in tamper_result["issues"]:
        print(f"  ⚠️ {issue}")
    print("  🔐 哈希链机制成功检测到数据篡改！")

    # 6. 重新导入验证
    print("\n[6] 从JSON重新导入并验证...")
    imported = import_passport_json(json_path)
    re_verify = verify_passport(imported)
    status = "✅ 通过" if re_verify["valid"] else "❌ 未通过"
    print(f"  导入验证: {status}")
    print(f"  注意: JSON中保存的是篡改前的数据，所以验证通过")

    # 7. 打印护照概览
    print("\n" + "=" * 60)
    print("  护照生命周期概览")
    print("=" * 60)
    print(f"  {'事件':>4s}  {'类型':>14s}  {'时间':>20s}  {'哈希(前8位)':>10s}")
    print(f"  {'-'*56}")
    for i, evt in enumerate(imported.events):
        print(f"  {i+1:4d}  {evt.event_type:14s}  {evt.timestamp[:19]:20s}  {evt.event_hash[:8]:>10s}")
    print(f"\n  哈希链完整性: ", end="")
    for i, evt in enumerate(imported.events):
        if i > 0 and evt.prev_hash == imported.events[i-1].event_hash:
            print(" → ", end="")
        elif i > 0:
            print(" ✗ ", end="")
        print(f"[{evt.event_hash[:6]}]", end="")
    print()

    print("\n" + "=" * 60)
    print("  电池数字护照演示完成！")
    print("=" * 60)
