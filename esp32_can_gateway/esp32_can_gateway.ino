/**
 * 动力电池 CAN 网关固件 — ESP32 + TJA1050
 * 功能：读取 BMS CAN 数据 → WiFi HTTP POST → BMS 管理平台
 *
 * 硬件接线：
 *   ESP32 (硬件CAN外设)  TJA1050 (CAN PHY收发器)
 *   GPIO16 (CAN_TX)    →  CTX
 *   GPIO17 (CAN_RX)    →  CRX
 *   3.3V               →  VCC
 *   GND                →  GND  ← 必须与BMS共地！
 *
 *   TJA1050 CANH/CANL   →  电池BMS的CAN总线 (CAN_H/CAN_L)
 *   ⚠️ 终端电阻：检查TJA1050模块上120Ω电阻是否断开（BMS端已有）
 *   ⚠️ 供电隔离：ESP32+TJA1050用USB供电，BMS用12V独立供电，两路GND相连
 *   波特率：通常 250kbps 或 500kbps，需与BMS匹配
 *
 * 编译环境：Arduino IDE + ESP32 开发板
 * 依赖库：
 *   - CAN：https://github.com/sandeepmistry/arduino-CAN
 *   - ArduinoJson：https://arduinojson.org/
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <CAN.h>       // sandeepmistry/arduino-CAN 库

// ═══════════════════════════════════════
// 配置参数（根据实际情况修改）
// ═══════════════════════════════════════
const char* WIFI_SSID     = "YOUR_WIFI";          // WiFi 名称
const char* WIFI_PASSWORD = "YOUR_PASSWORD";      // WiFi 密码

// 上传地址：局域网演示用 localhost，公网部署用 Streamlit Cloud 地址
// 局域网：http://192.168.1.100:8501/api/telemetry
// 公网：https://your-app.streamlit.app/api/telemetry
const char* UPLOAD_URL = "http://192.168.1.100:8501/api/telemetry";

const int CAN_SPEED = 250000;    // CAN 波特率（250kbps 常见，500kbps 也很常见）
const int UPLOAD_INTERVAL = 3000; // 上传间隔（毫秒）

// ═══════════════════════════════════════
// CAN 帧 ID 映射（根据目标 BMS 协议修改）
// 此处以通用新能源 BMS 协议示例
// ═══════════════════════════════════════
#define CAN_ID_PACK_STATUS     0x100   // 电池包状态帧
#define CAN_ID_CELL_VOLTAGE    0x110   // 单体电压帧（多帧轮询）
#define CAN_ID_TEMP            0x120   // 温度帧
#define CAN_ID_SOC_SOH         0x130   // SOC/SOH 帧
#define CAN_ID_FAULT           0x140   // 故障告警帧

// 全局变量：存储解析后的电池数据
struct BatteryData {
  float packVoltage = 0;       // 总电压 V
  float packCurrent = 0;       // 电流 A (正值放电，负值充电)
  float soc = 0;               // SOC %
  float soh = 0;               // SOH %
  float packTemp = 0;          // 温度 °C
  float cellVoltMin = 0;       // 最低单体电压
  float cellVoltMax = 0;       // 最高单体电压
  float cellVoltDiff = 0;      // 压差
  int   insulation = 0;        // 绝缘电阻 kΩ
  int   cycleCount = 0;        // 循环次数
  uint8_t bmsStatus = 0;       // BMS 状态（0=正常,1=警告,2=故障）
} batteryData;

unsigned long lastUpload = 0;

// ═══════════════════════════════════════
// 初始化
// ═══════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n[ESP32] 动力电池 CAN 网关启动");

  // 连接 WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("连接 WiFi");
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 30) {
    delay(500); Serial.print("."); retry++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi 已连接");
    Serial.print("IP: "); Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi 连接失败！");
  }

  // 初始化 CAN 总线
  Serial.print("初始化 CAN 总线...");
  if (!CAN.begin(CAN_SPEED)) {
    Serial.println("失败！请检查接线");
    while (1);
  }
  Serial.println("成功");
}

// ═══════════════════════════════════════
// 主循环
// ═══════════════════════════════════════
void loop() {
  // 读取 CAN 数据
  int packetSize = CAN.parsePacket();
  if (packetSize) {
    long canId = CAN.packetId();
    uint8_t buf[8];
    int len = 0;
    while (CAN.available() && len < 8) {
      buf[len++] = CAN.read();
    }
    parseCANFrame(canId, buf, len);
  }

  // 定时上传
  unsigned long now = millis();
  if (now - lastUpload >= UPLOAD_INTERVAL && WiFi.status() == WL_CONNECTED) {
    uploadData();
    lastUpload = now;
  }
}

// ═══════════════════════════════════════
// CAN 帧解析（根据实际 BMS 协议修改）
// ═══════════════════════════════════════
void parseCANFrame(long id, uint8_t* data, int len) {
  switch (id) {
    case CAN_ID_PACK_STATUS:
      // 字节0-1: 总电压 (0.1V/bit)
      batteryData.packVoltage = ((data[0] << 8) | data[1]) * 0.1;
      // 字节2-3: 总电流 (0.1A/bit, 偏移-1000A)
      batteryData.packCurrent = (((data[2] << 8) | data[3]) - 10000) * 0.1;
      break;

    case CAN_ID_CELL_VOLTAGE:
      // 字节0-1: 最低单体电压 (mV)
      batteryData.cellVoltMin = ((data[0] << 8) | data[1]) * 0.001;
      // 字节2-3: 最高单体电压 (mV)
      batteryData.cellVoltMax = ((data[2] << 8) | data[3]) * 0.001;
      batteryData.cellVoltDiff = batteryData.cellVoltMax - batteryData.cellVoltMin;
      break;

    case CAN_ID_TEMP:
      // 字节0-1: 最高温度 (0.1°C/bit, 偏移-40°C)
      batteryData.packTemp = (((data[0] << 8) | data[1]) * 0.1) - 40;
      break;

    case CAN_ID_SOC_SOH:
      // 字节0: SOC (0.5%/bit)
      batteryData.soc = data[0] * 0.5;
      // 字节1: SOH (0.5%/bit)
      batteryData.soh = data[1] * 0.5;
      // 字节2-3: 循环次数
      batteryData.cycleCount = (data[2] << 8) | data[3];
      break;

    case CAN_ID_FAULT:
      // 字节0: 故障码 (0=正常)
      batteryData.bmsStatus = data[0];
      // 字节1-2: 绝缘电阻 (kΩ)
      batteryData.insulation = (data[1] << 8) | data[2];
      break;
  }
}

// ═══════════════════════════════════════
// HTTP POST 上传数据到 BMS 平台
// ═══════════════════════════════════════
void uploadData() {
  if (WiFi.status() != WL_CONNECTED) return;

  StaticJsonDocument<512> doc;
  doc["vehicle_id"] = "VIN-LS6A3E0EXA000001";
  doc["battery_id"] = "CATL-QJ-100-001";
  doc["pack_voltage_v"] = batteryData.packVoltage;
  doc["pack_current_a"] = batteryData.packCurrent;
  doc["soc_pct"] = batteryData.soc;
  doc["soh_pct"] = batteryData.soh;
  doc["pack_temp_c"] = batteryData.packTemp;
  doc["cell_voltage_min_v"] = batteryData.cellVoltMin;
  doc["cell_voltage_max_v"] = batteryData.cellVoltMax;
  doc["cell_voltage_diff_v"] = batteryData.cellVoltDiff;
  doc["insulation_resistance_kohm"] = batteryData.insulation;
  doc["cycle_count"] = batteryData.cycleCount;
  doc["bms_status"] = batteryData.bmsStatus;

  String jsonStr;
  serializeJson(doc, jsonStr);

  HTTPClient http;
  http.begin(UPLOAD_URL);
  http.addHeader("Content-Type", "application/json");

  int httpCode = http.POST(jsonStr);
  if (httpCode > 0) {
    Serial.print("上传成功 HTTP ");
    Serial.println(httpCode);
  } else {
    Serial.print("上传失败: ");
    Serial.println(http.errorToString(httpCode));
  }
  http.end();
}
