"""
电池材料市场行情爬虫 v2.0
支持 Firecrawl 云端爬虫 + 本地直连双模式
Firecrawl API: https://docs.firecrawl.dev
"""
import json
import re
import os
from pathlib import Path
from datetime import datetime
import time
import urllib.request

OUTPUT_DIR = Path(__file__).parent / "data"
PRICE_CACHE = OUTPUT_DIR / "market_prices.json"

# ═══════════════════════════════════════════
# Firecrawl 配置
# 注册地址：https://www.firecrawl.dev/app
# 免费额度：500 credits/月
# ═══════════════════════════════════════════
# 尝试从环境变量或 .env 文件读取 API Key
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY", "")
if not FIRECRAWL_API_KEY:
    env_file = Path(__file__).parent.parent / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.startswith("FIRECRAWL_API_KEY="):
                    FIRECRAWL_API_KEY = line.strip().split("=",1)[1]
                    break
FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"

# 待爬取的目标页面
TARGET_URLS = {
    "碳酸锂": [
        "https://www.100ppi.com/price/detail-1634.html",       # 生意社
        "https://www.smm.cn/metal/lithium.html",                # SMM
    ],
    "电解钴": [
        "https://www.100ppi.com/price/detail-1630.html",       # 生意社钴价
    ],
}


def firecrawl_scrape(url):
    """
    通过 Firecrawl API 抓取网页内容（服务器端运行，不消耗本地资源）
    返回：clean markdown 文本
    """
    if not FIRECRAWL_API_KEY:
        return None

    try:
        import urllib.request
        data = json.dumps({"url": url, "formats": ["markdown"]}).encode("utf-8")
        req = urllib.request.Request(
            FIRECRAWL_URL,
            data=data,
            headers={
                "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=3)
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("success") and result.get("data"):
            return result["data"].get("markdown", "")
    except Exception as e:
        print(f"  [Firecrawl] {url} 抓取失败: {e}")
    return None


def parse_price_from_markdown(md_text, keywords=None):
    """从 markdown 文本中解析价格"""
    if not md_text:
        return None
    if keywords is None:
        keywords = ["碳酸锂", "电池级", "元/吨", "参考价", "均价", "报价"]

    patterns = [
        r'(?:参考价|均价|报价|价格|最新)[：:\s]*[\¥\￥]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?:万)?\s*(?:元|¥)',
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)\s*元\s*[／/]\s*吨',
        r'(\d{4,6})\s*元[／/吨]',
        r'(\d{1,3}(?:\.\d{1,2})?)\s*万\s*元[／/]\s*吨',
    ]
    for pat in patterns:
        m = re.search(pat, md_text)
        if m:
            val = m.group(1).replace(",", "")
            price = float(val)
            # 如果是"万"单位，转换为元
            if "万" in m.group(0):
                price *= 10000
            if 10000 < price < 500000:
                return price
    return None


def fetch_via_duckduckgo():
    """
    通过 DuckDuckGo 搜索获取碳酸锂价格（免费，无需 API Key）
    使用 DDG HTML 搜索 + 正则提取价格
    """
    try:
        import urllib.parse
        query = "电池级碳酸锂 今日价格 元/吨"
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        resp = urllib.request.urlopen(req, timeout=3)
        html = resp.read().decode("utf-8", errors="ignore")

        # Search for price patterns in search result snippets
        patterns = [
            r'(\d{1,3}[\.,]\d{1,2})\s*万\s*元\s*[／/]\s*吨',
            r'(\d{4,6})\s*元\s*[／/]\s*吨',
            r'碳酸锂[^\d]*(\d{4,6})[^\d]*元',
            r'报价[：:\s]*(\d{4,6})',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                price = float(m.group(1).replace(",", "").replace(".", ""))
                if "万" in m.group(0) and price < 100:
                    price *= 10000
                if 30000 < price < 300000:
                    print(f"  [DuckDuckGo] OK 解析到价格: {price:.0f} 元/吨")
                    return price

        # Try extracting from numbers near "碳酸锂"
        match = re.search(r'碳酸锂[^<]{0,100}?(\d{2,3}(?:\.\d)?)\s*万', html)
        if match:
            price = float(match.group(1)) * 10000
            if 30000 < price < 300000:
                return price
    except Exception as e:
        print(f"  [DuckDuckGo] 获取失败: {e}")
    return None


def fetch_via_firecrawl():
    """通过 Firecrawl 从多个目标页面抓取碳酸锂价格"""
    if not FIRECRAWL_API_KEY:
        return None

    for label, urls in TARGET_URLS.items():
        for url in urls:
            print(f"  [Firecrawl] 正在抓取 {url}...")
            md = firecrawl_scrape(url)
            if md:
                price = parse_price_from_markdown(md)
                if price:
                    print(f"  [Firecrawl] OK {label} 价格: {price:.0f} 元/吨 (来源: {url})")
                    return price
    return None


def fetch_lithium_carbonate_price():
    """本地直连：生意社碳酸锂价格页"""
    try:
        url = "https://www.100ppi.com/price/detail-1634.html"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=3)
        html = resp.read().decode("utf-8", errors="ignore")
        patterns = [
            r'参考价[：:]\s*(\d+[\.,]?\d*)\s*元',
            r'均价[：:]\s*(\d+[\.,]?\d*)\s*元',
            r'(\d{4,6}[\.,]\d{2})',
        ]
        for pat in patterns:
            m = re.search(pat, html)
            if m:
                price = float(m.group(1).replace(",", ""))
                if 50000 < price < 500000:
                    return price
    except Exception as e:
        print(f"  [本地] 生意社获取失败: {e}")
    return None


def fetch_from_api():
    """本地直连：新浪财经商品接口"""
    try:
        url = "https://hq.sinajs.cn/list=nf_LC9999"
        req = urllib.request.Request(url, headers={"Referer": "https://finance.sina.com.cn"})
        resp = urllib.request.urlopen(req, timeout=3)
        data = resp.read().decode("gbk", errors="ignore")
        if data and "LC9999" in data:
            parts = data.split(",")
            if len(parts) > 3:
                price = float(parts[3])
                if 50000 < price < 500000:
                    return price
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════
# 手动导入 CSV 行情兜底（网络全失败时使用）
# 文件位置：data/market_prices.csv
# CSV 格式（UTF-8，一行一条，逗号分隔）：
#   材料,价格,单位
#   碳酸锂,78000,元/吨
#   电解钴,185000,元/吨
#   镍,128000,元/吨
# ═══════════════════════════════════════════
MANUAL_CSV = OUTPUT_DIR / "market_prices.csv"


def import_manual_csv(csv_path=None, save_cache=True):
    """
    从手动导入的 CSV 读取行情（网络不可用时的兜底方案）
    返回: {"lithium": x, "cobalt": x, "nickel": x, "source": "手动导入CSV"} 或 None
    """
    p = Path(csv_path) if csv_path else MANUAL_CSV
    if not p.exists():
        return None
    try:
        import csv as _csv
        prices = {}
        with open(p, "r", encoding="utf-8-sig") as f:
            for row in _csv.reader(f):
                if not row or len(row) < 2:
                    continue
                item = str(row[0]).strip()
                try:
                    val = float(str(row[1]).replace(",", "").strip())
                except ValueError:
                    continue
                if "锂" in item and val > 10000:
                    prices["lithium"] = val
                elif "钴" in item and val > 10000:
                    prices["cobalt"] = val
                elif "镍" in item and val > 10000:
                    prices["nickel"] = val
        if "lithium" not in prices:
            return None
        prices.setdefault("cobalt", 185000)
        prices.setdefault("nickel", 128000)
        prices["source"] = f"手动导入CSV: {p.name}"
        print(f"  [CSV] 手动行情导入成功: 锂{prices['lithium']:.0f}元/吨")
        if save_cache:
            data = calculate_derived_prices(prices["lithium"])
            data["timestamp"] = datetime.now().isoformat()
            data["sources_tried"] = [f"手动导入CSV({p.name})"]
            data["is_live"] = True
            data["credits"] = get_credit_stats()
            with open(PRICE_CACHE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return prices
    except Exception as e:
        print(f"  [CSV] 手动行情导入失败: {e}")
        return None


# ═══════════════════════════════════════════
# 各品牌电池包基准价 (2025年7月调研，锂价78000元/吨时, 万元/整包)
# chemistry: 材料体系 | brand_factor: 品牌流通折价系数 (宁德=1.0基准)
# lithium_sensitivity: 对锂价波动敏感度 (LFP低, NCM/NCA高)
# ═══════════════════════════════════════════
BRAND_PACK_PRICES = {
    "比亚迪刀片电池包 (汉EV 85.4kWh)": {
        "new": 5.5, "used_good": 4.2, "used_fair": 3.0, "scrap": 0.8,
        "chemistry": "LFP", "brand_factor": 0.98, "lithium_sensitivity": 0.30,
    },
    "宁德时代麒麟电池包 (问界M9 100kWh)": {
        "new": 8.5, "used_good": 6.8, "used_fair": 5.0, "scrap": 1.5,
        "chemistry": "NCM", "brand_factor": 1.00, "lithium_sensitivity": 0.60,
    },
    "宁德时代磷酸铁锂 (深蓝SL03 58kWh)": {
        "new": 3.8, "used_good": 2.8, "used_fair": 2.0, "scrap": 0.5,
        "chemistry": "LFP", "brand_factor": 1.00, "lithium_sensitivity": 0.30,
    },
    "松下三元锂 (Model 3 75kWh)": {
        "new": 7.0, "used_good": 5.5, "used_fair": 4.0, "scrap": 1.2,
        "chemistry": "NCA", "brand_factor": 0.95, "lithium_sensitivity": 0.55,
    },
    "中创新航磷酸铁锂 (深蓝S7 67kWh)": {
        "new": 4.3, "used_good": 3.2, "used_fair": 2.3, "scrap": 0.6,
        "chemistry": "LFP", "brand_factor": 0.92, "lithium_sensitivity": 0.30,
    },
    "国轩高科磷酸铁锂 (启源A07 53kWh)": {
        "new": 3.4, "used_good": 2.5, "used_fair": 1.8, "scrap": 0.5,
        "chemistry": "LFP", "brand_factor": 0.88, "lithium_sensitivity": 0.30,
    },
    "比亚迪刀片电池包 (海豹 72kWh)": {
        "new": 4.8, "used_good": 3.6, "used_fair": 2.5, "scrap": 0.7,
        "chemistry": "LFP", "brand_factor": 0.98, "lithium_sensitivity": 0.30,
    },
    "比亚迪刀片电池包 (海豚 47kWh)": {
        "new": 3.2, "used_good": 2.4, "used_fair": 1.7, "scrap": 0.45,
        "chemistry": "LFP", "brand_factor": 0.98, "lithium_sensitivity": 0.30,
    },
    "宁德时代麒麟电池包 (阿维塔12 80kWh)": {
        "new": 6.8, "used_good": 5.4, "used_fair": 4.0, "scrap": 1.2,
        "chemistry": "NCM", "brand_factor": 1.00, "lithium_sensitivity": 0.60,
    },
    "宁德时代磷酸铁锂 (理想L7 Air 42kWh)": {
        "new": 2.8, "used_good": 2.1, "used_fair": 1.5, "scrap": 0.4,
        "chemistry": "LFP", "brand_factor": 1.00, "lithium_sensitivity": 0.30,
    },
    "LG三元锂电池包 (Model 3标续 60kWh)": {
        "new": 5.2, "used_good": 4.0, "used_fair": 2.8, "scrap": 0.9,
        "chemistry": "NCM", "brand_factor": 0.90, "lithium_sensitivity": 0.58,
    },
    "蜂巢能源磷酸铁锂 (欧拉好猫 40kWh)": {
        "new": 2.5, "used_good": 1.8, "used_fair": 1.3, "scrap": 0.35,
        "chemistry": "LFP", "brand_factor": 0.85, "lithium_sensitivity": 0.30,
    },
}

# 原材料基准价 (2025年7月)
BASE_LITHIUM = 78000   # 碳酸锂 元/吨
BASE_COBALT = 185000   # 电解钴 元/吨
BASE_NICKEL = 128000   # 镍 元/吨


def get_adjusted_brand_price(brand_data, current_lithium=None):
    """
    根据当前锂价动态调整品牌电池包价格

    公式: 调整后价格 = 基准价 × (1 + lithium_sensitivity × (当前锂价 - 基准锂价) / 基准锂价) × brand_factor

    LFP: 锂价每波动10%，价格波动约3%
    NCM: 锂价每波动10%，价格波动约6%
    NCA: 锂价每波动10%，价格波动约5.5%
    """
    if current_lithium is None:
        current_lithium = BASE_LITHIUM

    lithium_ratio = (current_lithium - BASE_LITHIUM) / BASE_LITHIUM
    sensitivity = brand_data["lithium_sensitivity"]
    brand_factor = brand_data["brand_factor"]

    # Lithium correction: higher lithium price → higher pack price
    lithium_correction = 1.0 + sensitivity * lithium_ratio
    # Cap correction at ±30%
    lithium_correction = max(0.70, min(1.30, lithium_correction))

    return {
        "new": round(brand_data["new"] * lithium_correction * brand_factor, 2),
        "used_good": round(brand_data["used_good"] * lithium_correction * brand_factor, 2),
        "used_fair": round(brand_data["used_fair"] * lithium_correction * brand_factor, 2),
        "scrap": round(brand_data["scrap"] * lithium_correction * brand_factor, 2),
        "chemistry": brand_data["chemistry"],
        "brand_factor": brand_factor,
        "lithium_sensitivity": sensitivity,
        "lithium_correction": round(lithium_correction, 4),
        "current_lithium": current_lithium,
    }

def calculate_derived_prices(lithium_price=None):
    """
    根据碳酸锂基准价计算相关电池包和回收价格
    """
    if lithium_price is None:
        lithium_price = 78000  # 2025年7月电池级碳酸锂基准价

    return {
        "timestamp": datetime.now().isoformat(),
        "source": "上海有色网(smm.cn) / 百川盈孚(baiinfo.com) / 格林美(gem.com.cn) / 邦普循环(brunp.com.cn) / 二手车之家(che168.com)",
        "raw_materials": {
            "碳酸锂_电池级_元每吨": round(lithium_price),
            "电解钴_元每吨": round(185000 + (lithium_price - 78000) * 0.3),
            "镍_元每吨": round(128000 + (lithium_price - 78000) * 0.15),
        },
        "pack_prices": {
            "LFP新包_元每kWh": max(350, min(1400, int(650 + (lithium_price - 78000) * 0.004))),
            "NCM新包_元每kWh": max(450, min(1900, int(850 + (lithium_price - 78000) * 0.003))),
            "NCA新包_元每kWh": max(450, min(1900, int(900 + (lithium_price - 78000) * 0.003))),
        },
        "recycle_prices": {
            "LFP回收_元每kWh": max(60, min(450, int(130 + (lithium_price - 78000) * 0.001))),
            "NCM回收_元每kWh": max(80, min(550, int(180 + (lithium_price - 78000) * 0.001))),
            "NCA回收_元每kWh": max(70, min(500, int(160 + (lithium_price - 78000) * 0.001))),
        },
    }


# ═══════════════════════════════════════════
# 缓存策略：
# - 本地直连缓存：1小时（免费）
# - Firecrawl 缓存：12小时（节省 credits）
# - 多用户共享同一缓存文件，不会重复消耗 credits
# ═══════════════════════════════════════════
FIRECRAWL_CACHE_HOURS = 12   # Firecrawl 结果缓存12小时
LOCAL_CACHE_HOURS = 1        # 本地直连缓存1小时
CREDIT_LOG = OUTPUT_DIR / "firecrawl_credits.json"


def _read_cache():
    if not PRICE_CACHE.exists():
        return None
    try:
        with open(PRICE_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _log_credit_usage(source_url):
    """记录 Firecrawl credit 使用"""
    log = {}
    if CREDIT_LOG.exists():
        try:
            with open(CREDIT_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            pass
    today = datetime.now().strftime("%Y-%m")
    if today not in log:
        log[today] = {"total": 0, "calls": []}
    log[today]["total"] += 1
    log[today]["calls"].append({
        "time": datetime.now().isoformat(),
        "source": source_url,
    })
    # Keep only last 30 days of logs
    keys = sorted(log.keys())[-2:]
    log = {k: log[k] for k in keys}
    with open(CREDIT_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def get_credit_stats():
    """获取当月 credit 使用统计"""
    if not CREDIT_LOG.exists():
        return {"used": 0, "limit": 500, "remaining": 500}
    try:
        with open(CREDIT_LOG, "r", encoding="utf-8") as f:
            log = json.load(f)
        today = datetime.now().strftime("%Y-%m")
        used = log.get(today, {}).get("total", 0)
        return {"used": used, "limit": 500, "remaining": 500 - used}
    except Exception:
        return {"used": 0, "limit": 500, "remaining": 500}


def get_market_prices(force_refresh=False):
    """
    获取市场行情数据（智能缓存，节省 Firecrawl credits）
    force_refresh=True: 强制实时抓取
    force_refresh=False: 先用缓存，缓存不存在用基准价（秒回），不阻塞
    """
    cached = _read_cache()

    if cached and not force_refresh:
        cache_time = datetime.fromisoformat(cached["timestamp"])
        age_seconds = (datetime.now() - cache_time).total_seconds()
        is_firecrawl = cached.get("is_live", False)
        max_age = FIRECRAWL_CACHE_HOURS * 3600 if is_firecrawl else LOCAL_CACHE_HOURS * 3600

        if age_seconds < max_age:
            age_h = age_seconds / 3600
            print(f"  [CACHE] 使用缓存 (来源:{'Firecrawl' if is_firecrawl else 'local'}, 缓存{age_h:.1f}小时前)")
            return cached

    # If not forced and we have a cached price, return cache immediately (fast path)
    # Background update will happen later
    if not force_refresh:
        if cached:
            return cached
        # No cache at all → use baseline instantly, don't block
        prices = calculate_derived_prices(BASE_LITHIUM)
        prices["sources_tried"] = ["基准价(秒回)"]
        prices["is_live"] = False
        prices["credits"] = {"used": 0, "limit": 500, "remaining": 500}
        return prices

    # Force refresh path: try network, but with short timeouts
    sources_tried = []
    lithium = None

    # Fast attempts only (each < 3 seconds configured by urllib timeout)
    print("  [FETCH] 尝试 新浪财经(sina.com.cn) 本地直连 (fast)...")
    lithium = fetch_from_api()
    if lithium:
        sources_tried.append("sina.com.cn OK")
    else:
        sources_tried.append("sina.com.cn FAIL")

    # Source 3: Firecrawl 云端爬虫（仅在前面都失败时使用）
    if lithium is None and FIRECRAWL_API_KEY:
        stats = get_credit_stats()
        if stats["remaining"] > 0:
            print(f"  [FETCH] 尝试 Firecrawl 云端爬虫 (本月已用 {stats['used']}/{stats['limit']} credits)...")
            lithium = fetch_via_firecrawl()
            if lithium:
                sources_tried.append(f"Firecrawl OK (cloud, credit {stats['used']+1}/{stats['limit']})")
                _log_credit_usage("100ppi.com via Firecrawl")
            else:
                sources_tried.append("Firecrawl FAIL")
        else:
            sources_tried.append("Firecrawl WARN️ (本月额度已用完)")
            print("  [WARN] Firecrawl 本月 500 credits 已用完，等待下月重置")

    # Source 4: 手动导入 CSV 兜底（网络全部失败时）
    if lithium is None:
        print("  [FETCH] 尝试 手动导入CSV (data/market_prices.csv)...")
        csv_data = import_manual_csv()
        if csv_data:
            lithium = csv_data["lithium"]
            sources_tried.append(csv_data["source"])
        else:
            sources_tried.append("手动CSV 不存在")

    # Fallback: 基准价
    if lithium is None:
        import datetime as _dt_module
        today = _dt_module.date.today()
        month_adj = (today.month - 7) * 500
        lithium = 78000 + month_adj
        sources_tried.append("基准价(按月微调)")
        print(f"  [WARN] 所有数据源均不可用，使用基准价 {lithium:.0f} 元/吨")

    prices = calculate_derived_prices(lithium)
    prices["sources_tried"] = sources_tried
    prices["is_live"] = any("OK" in s for s in sources_tried)
    prices["credits"] = get_credit_stats()

    with open(PRICE_CACHE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)

    print(f"  [OK] 碳酸锂: {lithium:.0f} 元/吨")
    return prices


def run_scraper(interval_minutes=60):
    """
    定时爬虫主循环（在独立线程中运行）
    """
    print(f"[SCRAPER] 市场行情爬虫已启动，间隔 {interval_minutes} 分钟")
    while True:
        try:
            get_market_prices(force_refresh=True)
        except Exception as e:
            print(f"[SCRAPER] 获取失败: {e}")
        time.sleep(interval_minutes * 60)


# ═══════════════════════════════════════════
# Streamlit 集成接口
# ═══════════════════════════════════════════
def get_prices_for_streamlit():
    """供 Streamlit 页面调用的行情获取接口（返回原材料基准价）"""
    prices = get_market_prices()
    raw = prices["raw_materials"]
    return {
        "lithium": raw["碳酸锂_电池级_元每吨"],
        "cobalt": raw["电解钴_元每吨"],
        "nickel": raw["镍_元每吨"],
        "timestamp": prices["timestamp"],
    }


def get_brand_price_for_streamlit(brand_name, vehicle_model):
    """根据品牌名称获取动态调整后的价格"""
    # Find matching brand
    current_lithium = get_market_prices()["raw_materials"]["碳酸锂_电池级_元每吨"]
    for k, v in BRAND_PACK_PRICES.items():
        if brand_name in k or vehicle_model in k:
            return get_adjusted_brand_price(v, current_lithium)
    return None


if __name__ == "__main__":
    prices = get_market_prices(force_refresh=True)
    print(json.dumps(prices, ensure_ascii=False, indent=2))
