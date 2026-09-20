"""
ESP32 CAN 网关接收端 — 轻量 HTTP API 服务器
接收 ESP32 上传的电池数据，存入本地 JSONL 文件供 Streamlit 读取

启动方式：
  python data_api.py --port 8501

部署到 Streamlit Cloud 时，此文件作为独立 API 服务运行
"""
import json
import sys
import socket
import time
import threading
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

# 控制台编码容错：GBK 控制台下遇到 ✓ 等字符不再抛异常（曾导致响应被污染）
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors="replace")
    except Exception:
        pass

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def validate_telemetry(data):
    """
    数据完整性校验（应对传输丢包/损坏/异常值）
    返回: (是否合法, 清洗后的数据)
    """
    # 必需字段检查
    required = ["battery_id", "soc_pct", "soh_pct", "pack_voltage_v", "pack_temp_c"]
    if not all(k in data for k in required):
        return False, "缺少必需字段: " + ",".join(set(required) - set(data.keys()))

    # 数值范围检查（物理合理性）
    if not (0 <= float(data.get("soc_pct", -1)) <= 100):
        return False, f"soc_pct 越界: {data.get('soc_pct')}"
    if not (0 <= float(data.get("soh_pct", -1)) <= 100):
        return False, f"soh_pct 越界: {data.get('soh_pct')}"
    if not (100 <= float(data.get("pack_voltage_v", 0)) <= 1500):
        return False, f"pack_voltage_v 越界: {data.get('pack_voltage_v')}"
    if not (-40 <= float(data.get("pack_temp_c", 99)) <= 100):
        return False, f"pack_temp_c 越界: {data.get('pack_temp_c')}"

    # 清洗：NaN/None → 默认值
    data["soc_pct"] = round(float(data["soc_pct"]), 2)
    data["soh_pct"] = round(float(data["soh_pct"]), 3)
    data["pack_voltage_v"] = round(float(data["pack_voltage_v"]), 1)
    data["pack_temp_c"] = round(float(data["pack_temp_c"]), 1)
    return True, data


class TelemetryHandler(BaseHTTPRequestHandler):
    """接收 POST /api/telemetry 数据"""

    def do_POST(self):
        if self.path == "/api/telemetry":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body.decode("utf-8"))
                # ── 数据校验（新增） ──
                ok, result = validate_telemetry(data)
                if not ok:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "invalid", "error": result}).encode())
                    print(f"  [API] REJ 数据被拒: {result}")
                    return
                data = result
                data["timestamp"] = datetime.now().isoformat()
                data["source"] = "ESP32_CAN"

                # 写入当日 JSONL 文件
                today = datetime.now().strftime("%Y%m%d")
                filepath = DATA_DIR / f"telemetry_{today}.jsonl"
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok"}).encode())
                print(f"  [API] OK 数据已接收 SOC:{data.get('soc_pct',0):.1f}%")
            except Exception as e:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == "/api/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"not found"}')

    def log_message(self, format, *args):
        pass  # 抑制默认日志




DISCOVER_PORT = 8505  # UDP 服务发现端口


def _get_local_ip():
    """获取本机在局域网内的 IP（不依赖系统的对外出口）"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _local_ips():
    """枚举本机所有 IPv4，剔除回环/链路本地/Docker 虚拟网卡"""
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except Exception:
        pass
    ips.add(_get_local_ip())          # 默认出口 IP 兜底
    out = []
    for ip in ips:
        if ip.startswith("127.") or ip.startswith("169.254."):
            continue
        if ip.startswith("172.17."):   # Docker Desktop 默认 bridge 宿主地址
            continue
        out.append(ip)
    return sorted(out)


def _broadcast_targets():
    """为每个本机 IP 计算定向广播地址（比 255.255.255.255 可靠：
       后者的路由在装了 Docker/VPN 的机器上会指向虚拟网卡，ESP32 收不到）"""
    targets = set()
    for ip in _local_ips():
        p = ip.split(".")
        if len(p) == 4:
            targets.add(".".join(p[:3] + ["255"]))      # /24
            targets.add(p[0] + ".255.255.255")          # /8（如 26.x）
    targets.add("255.255.255.255")                      # 有限广播，保留兼容
    return sorted(targets)


def udp_broadcast(interval=2):
    """每 2 秒播报本机 IP（BMS|<ip>），供 ESP32 自动发现，免改固件
       注意：消息体必须只有一个 IP —— 固件是 strncpy 取 "BMS|" 之后的全部内容"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    ips = _local_ips()
    targets = _broadcast_targets()
    print(f"[Discover] 本机候选IP: {', '.join(ips)}")
    print(f"[Discover] 广播目标: {', '.join(targets)} | 端口{DISCOVER_PORT} 间隔{interval}s")
    while True:
        for ip in ips:
            msg = f"BMS|{ip}".encode()
            for t in targets:
                try:
                    s.sendto(msg, (t, DISCOVER_PORT))
                except Exception:
                    pass
        time.sleep(interval)


def run_api_server(port=8501):
    """启动 HTTP API 服务器"""
    server = HTTPServer(("0.0.0.0", port), TelemetryHandler)
    threading.Thread(target=udp_broadcast, daemon=True).start()
    print(f"[API Server] 启动在 http://0.0.0.0:{port}")
    print(f"[API Server] 接收地址: POST http://<IP>:{port}/api/telemetry")
    print(f"[API Server] 数据存储: {DATA_DIR}/telemetry_YYYYMMDD.jsonl")
    server.serve_forever()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    run_api_server(args.port)
