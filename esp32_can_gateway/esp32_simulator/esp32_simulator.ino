/**
 * ESP32 电池模拟采集器 v3.0 — 多电池车队模拟
 * 同时模拟 12 辆车的电池数据，轮询发送
 * 支持 WiFi + 手机热点 双网络自动切换
 *
 * 硬件：ESP32 开发板（18元）+ USB 供电
 */

#include <WiFi.h>
#include <WiFiMulti.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

WiFiMulti wifiMulti;

// ═══════════════════════════════════════
// 网络配置
// ═══════════════════════════════════════
const char* WIFI1_SSID = "HUAWEI-401";
const char* WIFI1_PASS = "18702355972";
const char* WIFI2_SSID = "OPPO Reno13 t8gb";
const char* WIFI2_PASS = "12345678";

const char* UPLOAD_URL = "http://192.168.3.9:8501/api/telemetry";

// ═══════════════════════════════════════
// 车队电池数据库 — 12个真实车型
// ═══════════════════════════════════════
struct BatteryProfile {
  const char* id;
  const char* vehicle;
  const char* chemistry;
  float capacity_kwh;
  float base_soh;
  float voltage;
  int base_cycle;
};

BatteryProfile fleet[] = {
  {"CATL-QJ-100",     "问界M9",   "NCM", 100, 0.92, 650,  850},
  {"BYD-Blade-85",    "汉EV",     "LFP",  85, 0.94, 570,  620},
  {"CATL-QJ-80",      "阿维塔12", "NCM",  80, 0.90, 580, 1040},
  {"Panasonic-75",    "Model3",   "NCA",  75, 0.88, 400, 1520},
  {"BYD-Blade-72",    "海豹",     "LFP",  72, 0.95, 520,  380},
  {"CALB-S7-67",      "深蓝S7",   "LFP",  67, 0.91, 480,  720},
  {"CATL-SL-58",      "深蓝SL03", "LFP",  58, 0.93, 410,  550},
  {"Gotion-A07-54",   "启源A07",  "LFP",  54, 0.89, 400,  910},
  {"LG-M3-60",        "Model3标续","NCM",  60, 0.86, 390, 1820},
  {"BYD-Blade-47",    "海豚",     "LFP",  47, 0.96, 340,  290},
  {"CATL-L7-42",      "理想L7",   "LFP",  42, 0.93, 350,  480},
  {"SVOLT-GW-40",     "欧拉好猫", "LFP",  40, 0.87, 320, 1100},
};
const int FLEET_SIZE = sizeof(fleet) / sizeof(fleet[0]);
int currentBattery = 0;
unsigned long lastUpload = 0;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=====================================");
  Serial.println(" ESP32 车队电池模拟器 v3.0");
  Serial.print(" 模拟 "); Serial.print(FLEET_SIZE); Serial.println(" 辆车 · 轮询发送");
  Serial.println("=====================================\n");

  wifiMulti.addAP(WIFI1_SSID, WIFI1_PASS);
  wifiMulti.addAP(WIFI2_SSID, WIFI2_PASS);

  Serial.print("连接网络");
  int dots = 0;
  while (wifiMulti.run() != WL_CONNECTED) {
    delay(500); Serial.print("."); dots++;
    if (dots >= 60) { Serial.println("\n连接失败，重启..."); ESP.restart(); }
  }
  Serial.println("\n连接成功!");
  Serial.print("SSID: "); Serial.println(WiFi.SSID());
  Serial.print("IP:   "); Serial.println(WiFi.localIP());
  Serial.print("信号: "); Serial.print(WiFi.RSSI()); Serial.println(" dBm");
  Serial.println("\n开始轮询发送...\n");
}

void loop() {
  if (wifiMulti.run() != WL_CONNECTED) { delay(1000); return; }
  if (millis() - lastUpload < 3000) return;  // 每3秒发送一辆车
  lastUpload = millis();

  BatteryProfile* b = &fleet[currentBattery];

  // 模拟行驶数据（每辆车随机行驶状态）
  bool driving = random(0, 100) < 40;  // 40%概率在行驶
  float soc = driving ? random(300, 850) / 10.0 : random(500, 950) / 10.0;  // 行驶中30-85%, 停车50-95%
  float temp = 22.0 + random(-20, 160) / 10.0;  // 20-38°C

  StaticJsonDocument<512> doc;
  doc["vehicle_id"]   = b->id;
  doc["battery_id"]   = b->id;
  doc["chemistry"]    = b->chemistry;
  doc["capacity_kwh"] = b->capacity_kwh;
  doc["pack_voltage_v"] = b->voltage + random(-30, 30) / 10.0;
  doc["pack_current_a"]  = driving ? random(-100, 200) / 10.0 : random(-20, 30) / 10.0;
  doc["soc_pct"]       = soc;
  doc["soh_pct"]       = b->base_soh * 100 + random(-2, 2) / 10.0;
  doc["cycle_count"]   = b->base_cycle + currentBattery * 10;
  doc["pack_temp_c"]   = temp;
  doc["cell_voltage_min_v"] = 3.55 + random(0, 15) / 100.0;
  doc["cell_voltage_max_v"] = 3.68 + random(0, 15) / 100.0;
  doc["cell_voltage_diff_v"] = random(2, 20) / 1000.0;
  doc["insulation_resistance_kohm"] = random(4000, 9999);
  doc["bms_status"]    = random(0, 100) < 99 ? 0 : random(1, 3);  // 99%正常，偶尔模拟故障
  doc["speed_kmh"]     = driving ? random(20, 120) : 0;
  doc["odometer_km"]   = (b->base_cycle * 250) + random(0, 2000) / 10.0;

  // 循环次数递增
  b->base_cycle += 1;

  String jsonStr;
  serializeJson(doc, jsonStr);

  // ── 发送 + 失败重传（最多3次，应对WiFi丢包） ──
  const int MAX_RETRY = 3;
  bool sent = false;
  for (int attempt = 0; attempt < MAX_RETRY; attempt++) {
    HTTPClient http;
    http.begin(UPLOAD_URL);
    http.addHeader("Content-Type", "application/json");
    int httpCode = http.POST(jsonStr);
    http.end();

    if (httpCode > 0) {
      sent = true;
      if (attempt > 0) {
        Serial.printf("RETRY OK [%s] attempt=%d\n", b->id, attempt + 1);
      }
      break;
    }
    delay(300);  // 重传间隔
  }

  if (sent) {
    Serial.printf("[%d/%d] %s %s SOC:%.1f%% SOH:%.1f%% T:%.1fC\n",
      currentBattery+1, FLEET_SIZE, b->id, b->vehicle, soc, b->base_soh*100, temp);
  } else {
    Serial.printf("FAIL [%s] after %d attempts, data dropped\n", b->id, MAX_RETRY);
  }

  // 切换到下一辆车
  currentBattery = (currentBattery + 1) % FLEET_SIZE;
}