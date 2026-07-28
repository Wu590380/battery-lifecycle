# ESP32 纯软件模拟方案

## 物料清单

| 物料 | 数量 | 价格 |
|---|---|---|
| ESP32-WROOM-32 开发板 | 1 | 18元 |
| Micro USB 数据线 | 1 | 已有 |
| **合计** | | **18元** |

不需要：TJA1050、电池、传感器、杜邦线

## 步骤

### 1. 安装 Arduino IDE
下载：https://www.arduino.cc/en/software

### 2. 添加 ESP32 支持
文件 → 首选项 → 附加开发板管理器网址，填入：
```
https://espressif.github.io/arduino-esp32/package_esp32_index.json
```
工具 → 开发板 → 开发板管理器 → 搜索 ESP32 → 安装

### 3. 安装库
工具 → 管理库：
- 搜索 `ArduinoJson` → 安装

### 4. 修改代码
打开 `esp32_simulator.ino`，修改三处：
- WIFI_SSID → 你的 WiFi 名称
- WIFI_PASSWORD → 你的 WiFi 密码
- UPLOAD_URL → 你的电脑 IP 地址（如 http://192.168.1.100:8501）

### 5. 烧录
USB 连接 ESP32 → 选择端口 → 上传

### 6. 启动平台接收端
```bash
python data_api.py --port 8501
```

### 7. 浏览器查看
http://localhost:8502 → 电池监测 → 实时监测
http://localhost:8503 → 车载显示屏

## 演示效果
ESP32 每 5 秒发送一次模拟数据（SOC 45-85%，SOH 92%，电压 650V，温度 26°C），网页实时刷新曲线和数据。和接真电池的效果一样。
