# ESP32 CAN 网关 — 部署说明

## 硬件清单（总成本 < 50元）

| 部件 | 型号 | 价格 | 说明 |
|---|---|---|---|
| 主控板 | ESP32-WROOM-32 | ~18元 | 自带 WiFi + 硬件 CAN 控制器 |
| CAN 收发器 | TJA1050 / SN65HVD230 | ~5元 | **CAN 物理层收发器**（不是串口模块） |
| 杜邦线 | 母对母 × 8 | ~3元 | |
| 电解电容 | 1000μF / 16V | ~2元 | 滤波防重启（可先不加） |
| Micro USB 线 | 数据线 | ~5元 | ESP32 供电 + 烧录 |
| 12V 电源 | 12V 适配器或小电瓶 | 已有 | 给 BMS 主板供电 |

## ⚠️ 接线前必须检查

### 1. TJA1050 终端电阻

很多 TJA1050 模块板载 120Ω 终端电阻（有拨码开关或焊盘）。
**CAN 总线两端只允许一个 120Ω 电阻。** BMS 端通常已有，模块端必须断开。

操作：检查模块上是否有 `Rterm` 或 `120R` 标注的焊盘/跳线，**先断开**。如果通信不上再尝试接通。

### 2. 供电隔离（最重要！）

```
ESP32 + TJA1050  →  Micro USB 5V 供电（同一路）
BMS 主板         →  12V 小电瓶 / 电池包自身供电
```

**两套电源必须共地（GND 相连）！** 不共地 = CAN 信号乱码，收不到任何数据。

接线：将 ESP32 的 GND 和 BMS 的 GND 用一根杜邦线连通。

### 3. 绝对禁止

- ❌ 不要用电池包高压给 ESP32 供电
- ❌ 维修开关未断开时不要碰高压母线
- ❌ ESP32 只接 CAN 通信口（低压侧），不接高压回路

## 接线图

```
ESP32              TJA1050              捷威 BMS CAN口
GPIO16 (CAN_TX) → CTX                  （只接低压信号）
GPIO17 (CAN_RX) → CRX
3.3V            → VCC
GND             → GND  ────────┐
                                ├── 共地线（必须接！）
BMS GND ←──────────────────────┘
                   CANH  →  CAN_H (BMS)
                   CANL  →  CAN_L (BMS)

ESP32 供电：Micro USB 5V
BMS 供电：12V 小电瓶
```

## 固件烧录

1. 安装 Arduino IDE
2. 添加 ESP32 开发板：
   `文件 → 首选项 → 附加开发板管理器网址`
   填入：`https://espressif.github.io/arduino-esp32/package_esp32_index.json`
3. 安装库：`工具 → 管理库`
   - 搜索 `CAN` → 安装 `CAN by Sandeep Mistry`
   - 搜索 `ArduinoJson` → 安装 `ArduinoJson`
4. 修改 `esp32_can_gateway.ino` 中的：
   - WiFi 名称和密码
   - CAN 波特率（捷威常见 250kbps 或 500kbps）
   - 上传 URL（局域网 IP 或公网地址）
5. 编译上传

## 启动平台

```bash
# 终端1：API 接收服务器
python data_api.py --port 8501

# 终端2：BMS 平台
streamlit run app.py --server.port 8502

# 浏览器 → http://localhost:8502 → 实时监测
```

## CAN 协议适配

ESP32 通过**硬件 CAN 外设**直接驱动 TJA1050。TJA1050 是 CAN 物理层收发器（CAN PHY），负责差分信号 ↔ 数字电平转换，**不是串口转 CAN 模块**。

捷威 BMS 的 CAN 协议需要根据其 DBC 文件修改 `parseCANFrame()` 中的 CAN ID 和解析逻辑。常见 CAN ID 范围 0x100-0x5FF。
