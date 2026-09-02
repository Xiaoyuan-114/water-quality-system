"""
聊天智能体工具层
7 个 LangChain Tool，挂到 create_agent 上，让 LLM 用自然语言操作水质系统
  1. query_records    - 查历史检测记录（支持按结果/水源/条数过滤）
  2. query_alerts     - 查预警日志（支持只看未解决）
  3. predict_water    - 水质预测（9 项指标 → 调用 ai_api.make_prediction）
  4. query_standards  - 查水质标准 / 水源信息
  5. standards_check  - 自动把检测记录与标准逐项对照，指出超标项并给建议
  6. trend_analysis   - 水质趋势分析与未来几天简单预测（统计数据）
  7. chart_report     - 生成图表（占比/水源对比/趋势）或导出 CSV
所有 SQL 只读 + 参数化查询，工具只暴露「查什么」不暴露「怎么查」
"""
import os
import csv
import re
import time
import json
from datetime import datetime, timedelta

import pymysql
from langchain_core.tools import Tool

from chat_config import DB_CONFIG, PREDICT_COLS, INDICATOR_ALIAS


# ============================================================
# 数据库连接辅助
# ============================================================
def _get_conn():
    """每次查询开一个连接，用完即关，避免长连接状态混乱"""
    return pymysql.connect(**DB_CONFIG)


def _fetch(sql: str, params: tuple = (), limit: int = 20):
    """执行只读 SELECT，返回 list[dict]，最多 limit 条"""
    conn = _get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchmany(limit)
        return rows
    finally:
        conn.close()


# ============================================================
# 图表/导出共享基建（FastAPI 挂载 /static 后即可访问）
# ============================================================
# 图表和导出文件统一写到 WaterQualityAI/static/，由 chat_main 的 /static 路由对外提供
CHAT_STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(CHAT_STATIC_DIR, exist_ok=True)

# 检测表列名 -> 标准表 indicator_name（只有 ph/PpH 大小写不同，其余同名）
COL_TO_STANDARD = {
    "ph": "pH", "hardness": "hardness", "solids": "solids",
    "chloramines": "chloramines", "sulfate": "sulfate",
    "conductivity": "conductivity", "organic_carbon": "organic_carbon",
    "trihalomethanes": "trihalomethanes", "turbidity": "turbidity",
}

# 指标超标时的处理建议（可读性用）
INDICATOR_SUGGEST = {
    "ph": "建议调节pH值",
    "hardness": "建议软化/降低硬度",
    "solids": "建议加强沉淀/过滤",
    "chloramines": "建议优化消毒剂投加量",
    "sulfate": "建议加强源头管控",
    "conductivity": "建议关注溶解性总固体",
    "organic_carbon": "建议加强有机物去除",
    "trihalomethanes": "建议控制消毒副产物",
    "turbidity": "建议加强混凝沉淀与过滤",
}


def _static_url(name: str) -> str:
    return "/static/" + name


# 记录最近本次请求生成/导出的图，供 /chat 在流式末尾强制附上真实 URL，
# 避免模型自己编造一个不存在的图片链接导致前端破图。
_last_chart_url = None


def get_last_chart_url():
    return _last_chart_url


def clear_last_chart_url():
    global _last_chart_url
    _last_chart_url = None


def _cleanup_static(max_age_seconds: int = 7 * 86400):
    """清理超过 7 天的历史图表/导出文件。
    保留期拉长，避免历史会话里引用的旧图/旧下载链接很快失效。"""
    now = time.time()
    try:
        for f in os.listdir(CHAT_STATIC_DIR):
            p = os.path.join(CHAT_STATIC_DIR, f)
            try:
                if os.path.isfile(p) and now - os.path.getmtime(p) > max_age_seconds:
                    os.remove(p)
            except OSError:
                pass
    except OSError:
        pass


def _resolve_indicator(text: str):
    """从自然语言里识别 9 项指标之一，返回检测表列名（用于趋势分析）"""
    for alias, col in INDICATOR_ALIAS.items():
        if alias in text:
            return col
    return None


# ============================================================
# 工具 5：标准自动对照（合规检查）
# ============================================================
def _check_standards(query: str) -> str:
    """
    把最近检测记录（或指定水源的检测记录）逐项与所选水质标准限值对照，
    标出哪些指标超过上限/低于下限，并给出处理建议。
    """
    level = None
    for lv in ["饮用水", "地表水I类", "地表水II类", "污水排放"]:
        if lv in query:
            level = lv
            break
    if level is None:
        level = "饮用水"

    std_rows = _fetch(
        "SELECT indicator_name, min_value, max_value, unit "
        "FROM water_standard WHERE standard_level=%s ORDER BY id",
        (level,), limit=50,
    )
    if not std_rows:
        return f"标准库中未找到「{level}」的标准数据，暂时无法做对照。"
    std = {}
    for r in std_rows:
        std[r["indicator_name"]] = r

    m = re.search(r"最近\s*(\d+)\s*(?:条|个)", query)
    n = min(int(m.group(1)), 20) if m else 5

    # 尽量识别水源
    source_id = None
    src_name = None
    try:
        for s in _fetch("SELECT id, source_name FROM water_source_info WHERE status=1", (), limit=100):
            if s.get("source_name") and s["source_name"] in query:
                source_id = s["id"]
                src_name = s["source_name"]
                break
    except Exception:
        pass

    where = "WHERE d.source_id=%s " if source_id else ""
    params: tuple = (source_id,) if source_id else ()
    sql = (
        "SELECT d.id, d.detect_time, d.ph, d.hardness, d.solids, d.chloramines, "
        "d.sulfate, d.conductivity, d.organic_carbon, d.trihalomethanes, d.turbidity, "
        "d.prediction, ws.source_name "
        "FROM water_detection d "
        "LEFT JOIN water_source_info ws ON d.source_id=ws.id "
        + where
        + "ORDER BY d.detect_time DESC LIMIT %s"
    )
    rows = _fetch(sql, params + (n,), limit=n)
    if not rows:
        return (
            "没有找到可做标准对照的检测记录"
            + (f"（{src_name}）" if src_name else "")
            + "。"
        )

    lines = [f"《{level}》标准对照（共检查 {len(rows)} 条记录）："]
    total_violations = 0
    for rec in rows:
        rec_id = rec["id"]
        dtime = str(rec.get("detect_time", ""))[:19]
        src = rec.get("source_name") or "—"
        lines.append(f"--- 记录 #{rec_id}  {dtime}  {src}  [{rec.get('prediction')}] ---")
        for col in ["ph", "hardness", "solids", "chloramines", "sulfate",
                    "conductivity", "organic_carbon", "trihalomethanes", "turbidity"]:
            val = rec.get(col)
            if val is None:
                continue
            ind = COL_TO_STANDARD.get(col, col)
            srow = std.get(ind)
            if not srow:
                continue
            lo = srow.get("min_value")
            hi = srow.get("max_value")
            unit = srow.get("unit") or ""
            suggestion = INDICATOR_SUGGEST.get(col, "建议人工复核")
            if lo is not None and val < lo:
                total_violations += 1
                lines.append(f"  ⚠️ {ind}：{val} {unit}，低于下限 {lo}（限值 {lo}~{hi}）{suggestion}")
            elif hi is not None and val > hi:
                total_violations += 1
                lines.append(f"  ⚠️ {ind}：{val} {unit}，超过上限 {hi}（限值 {lo}~{hi}）{suggestion}")

    if total_violations == 0:
        lines.append(f"✅ 所选记录全部在《{level}》标准限值范围内。")
    else:
        lines.append(f"共发现 {total_violations} 项指标超标/偏低。")
    return "\n".join(lines)


# ============================================================
# 工具 6：水质趋势分析/预测（用历史检测数据做统计趋势）
# ============================================================
def _trend_series(col=None, source_id=None, days=30):
    """返回 [(日期, 值, 条数)]。col=None 时值=当日「Unsafe 占比(%)」。"""
    cutoff = datetime.now() - timedelta(days=days)
    where = ["d.detect_time >= %s"]
    params: list = [cutoff.strftime("%Y-%m-%d %H:%M:%S")]
    if source_id:
        where.append("d.source_id=%s")
        params.append(source_id)
    w = " AND ".join(where)

    if col:
        # 只允许白名单列名，防止 SQL 注入
        if col not in PREDICT_COLS:
            col = None
        else:
            sql = (
                f"SELECT DATE(d.detect_time) AS day, AVG(d.{col}) AS val, COUNT(*) AS cnt "
                f"FROM water_detection d WHERE {w} GROUP BY DATE(d.detect_time) ORDER BY day"
            )
            rows = _fetch(sql, tuple(params), limit=2000)
            out = []
            for r in rows:
                v = r.get("val")
                out.append((str(r["day"]), float(v) if v is not None else None, int(r.get("cnt") or 0)))
            return out

    sql = (
        "SELECT DATE(d.detect_time) AS day, COUNT(*) AS cnt, "
        "SUM(CASE WHEN d.prediction='Unsafe' THEN 1 ELSE 0 END) AS unsafe_cnt "
        f"FROM water_detection d WHERE {w} GROUP BY DATE(d.detect_time) ORDER BY day"
    )
    rows = _fetch(sql, tuple(params), limit=2000)
    out = []
    for r in rows:
        cnt = int(r.get("cnt") or 0)
        val = (int(r.get("unsafe_cnt") or 0) / cnt * 100.0) if cnt else None
        out.append((str(r["day"]), val, cnt))
    return out


def _linear_forecast(values, horizon=3):
    """用最小二乘线性拟合做未来 horizon 天简单外推。返回 (slope, forecast list) 或 None。"""
    data = [(i, v) for i, v in enumerate(values) if v is not None]
    if len(data) < 2:
        return None
    try:
        import numpy as np
    except Exception:
        return None
    x = np.array([p[0] for p in data], dtype=float)
    y = np.array([p[1] for p in data], dtype=float)
    if x.std() == 0:
        slope = 0.0
    else:
        slope = float(np.polyfit(x, y, 1)[0])
    last = data[-1][1]
    forecast = [last + slope * (i + 1) for i in range(horizon)]
    return slope, forecast


def _trend_analysis(query: str) -> str:
    """
    对某个指标（或整体安全占比）做近 N 天趋势分析，并给出未来 3 天的简单预测。
    """
    indicator = _resolve_indicator(query)
    col = indicator if indicator in PREDICT_COLS else None

    days_m = re.search(r"最近\s*(\d+)\s*天", query)
    days = min(int(days_m.group(1)), 90) if days_m else 30

    source_id = None
    src_name = None
    try:
        for s in _fetch("SELECT id, source_name FROM water_source_info WHERE status=1", (), limit=100):
            if s.get("source_name") and s["source_name"] in query:
                source_id = s["id"]
                src_name = s["source_name"]
                break
    except Exception:
        pass

    series = _trend_series(col=col, source_id=source_id, days=days)
    if not series:
        return (
            "近 " + str(days) + " 天没有检测数据"
            + (f"（{src_name}）" if src_name else "")
            + "，无法做趋势分析。"
        )

    values = [v for _, v, _ in series]
    label = "Unsafe 占比" if col is None else f"{col}"
    unit = "%" if col is None else "（原始单位）"
    valid = [(d, v) for d, v, _ in series if v is not None]
    latest = valid[-1][1] if valid else None
    avg = sum(v for _, v in valid) / len(valid) if valid else None

    fc = _linear_forecast([v for _, v in valid], horizon=3)
    lines = [
        f"水质趋势分析（{label}，近 {days} 天，"
        f"{series[0][0]} ~ {series[-1][0]}" + (f"，来源：{src_name}" if src_name else "") + "）：",
        f"- 近期平均：{avg:.2f}{unit}，最新：{latest:.2f}{unit}",
    ]
    if fc:
        slope, forecast = fc
        if slope > 0.05:
            trend = "上升（风险变大）" if col is None else "上升"
        elif slope < -0.05:
            trend = "下降（风险变小）" if col is None else "下降"
        else:
            trend = "基本平稳"
        lines.append(f"- 趋势：{trend}（斜率 {slope:.3f}/天）")
        lines.append(
            "- 未来 3 天预测：" + "、".join(f"{x:.2f}{unit}" for x in forecast)
        )
    return "\n".join(lines)


# ============================================================
# 图表/导出生成（matplotlib + CSV，写到 /static）
# ============================================================
def _mpl():
    """初始化 matplotlib，支持中文显示（Windows 常用中文字体）。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt


def _save_fig(fig, prefix):
    global _last_chart_url
    _cleanup_static()
    fn = f"{prefix}_{int(time.time())}.png"
    path = os.path.join(CHAT_STATIC_DIR, fn)
    try:
        fig.savefig(path, dpi=110, bbox_inches="tight")
    finally:
        try:
            import matplotlib.pyplot as plt
            plt.close(fig)
        except Exception:
            pass
    url = _static_url(fn)
    _last_chart_url = url
    return url


def _chart_pie():
    """安全/不合格占比饼图"""
    plt = _mpl()
    rows = _fetch("SELECT prediction, COUNT(*) AS cnt FROM water_detection GROUP BY prediction", (), limit=50)
    labels = [r["prediction"] for r in rows]
    sizes = [r["cnt"] for r in rows]
    colors = ["#22c55e" if l == "Safe" else "#ef4444" for l in labels]
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
    ax.set_title("检测结果分布（Safe vs Unsafe）")
    return _save_fig(fig, "pie"), "检测结果分布图"


def _chart_source_bar():
    """各水源检测量/不合格量柱状图"""
    plt = _mpl()
    rows = _fetch(
        "SELECT COALESCE(ws.source_name, CONCAT('水源#', d.source_id)) AS src, "
        "COUNT(*) AS cnt, SUM(CASE WHEN d.prediction='Unsafe' THEN 1 ELSE 0 END) AS unsafe_cnt "
        "FROM water_detection d "
        "LEFT JOIN water_source_info ws ON d.source_id=ws.id "
        "GROUP BY d.source_id, ws.source_name ORDER BY cnt DESC LIMIT 15",
        (), limit=50,
    )
    if not rows:
        return None, "没有可绘制的检测数据"
    names = [r["src"] for r in rows]
    total = [r["cnt"] for r in rows]
    unsafe = [r["unsafe_cnt"] or 0 for r in rows]
    x = range(len(names))
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(x, total, color="#0ea5e9", label="检测量")
    ax.bar(x, unsafe, color="#ef4444", label="不合格量")
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=8)
    ax.set_title("各水源检测量 / 不合格量")
    ax.legend()
    fig.tight_layout()
    return _save_fig(fig, "source"), "各水源对比图"


def _chart_trend(col=None, source_id=None, days=30, title=None):
    """指标/安全占比趋势折线图"""
    plt = _mpl()
    series = _trend_series(col=col, source_id=source_id, days=days)
    if not series:
        return None, "没有可绘制的趋势数据"
    valid = [(d, v) for d, v, _ in series if v is not None]
    dates = [d for d, _ in valid]
    vals = [v for _, v in valid]
    if not dates:
        return None, "没有可绘制的趋势数据"
    fig, ax = plt.subplots(figsize=(7, 3.8))
    ax.plot(range(len(dates)), vals, marker="o", color="#0ea5e9", linewidth=2)
    ax.set_xticks(range(len(dates)))
    ax.set_xticklabels(dates, rotation=30, ha="right", fontsize=7)
    label = "Unsafe 占比(%)" if col is None else f"{col}"
    ax.set_ylabel(label)
    ax.set_title(title or f"{label} 近 {days} 天趋势")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    return _save_fig(fig, "trend"), f"{label}趋势图"


def _export_records_csv(query: str) -> str:
    """把符合过滤条件的检测记录导出为 CSV（带 BOM，Excel 直接打开不乱码）。"""
    q = query.lower()
    where = ""
    params: tuple = ()
    if "不合格" in query or "不安全" in q or "unsafe" in q:
        where = "WHERE d.prediction=%s"
        params = ("Unsafe",)
    elif "合格" in query or "安全" in q or "safe" in q:
        where = "WHERE d.prediction=%s"
        params = ("Safe",)

    m = re.search(r"最近\s*(\d+)\s*(?:条|个)", query)
    n = min(int(m.group(1)), 500) if m else 200

    rows = _fetch(
        "SELECT d.id, u.username, ws.source_name, d.ph, d.hardness, d.solids, "
        "d.chloramines, d.sulfate, d.conductivity, d.organic_carbon, "
        "d.trihalomethanes, d.turbidity, d.prediction, ROUND(d.probability,3) AS probability, "
        "d.wqi_score, d.water_grade, d.standard_level, d.detect_time "
        "FROM water_detection d "
        "LEFT JOIN users u ON d.user_id=u.id "
        "LEFT JOIN water_source_info ws ON d.source_id=ws.id "
        + where + " ORDER BY d.detect_time DESC LIMIT %s",
        params + (n,), limit=n,
    )
    if not rows:
        return "没有可导出的检测记录。"

    _cleanup_static()
    fn = f"records_{int(time.time())}.csv"
    path = os.path.join(CHAT_STATIC_DIR, fn)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return f"已导出 {len(rows)} 条检测记录：\n[下载 CSV](/static/{fn})"


def _chart_report(query: str) -> str:
    """生成图表（分布/水源对比/趋势）或导出 CSV。"""
    if any(k in query.lower() for k in ["导出", "excel", "csv", "下载"]):
        return _export_records_csv(query)

    q = query.lower()
    try:
        if any(k in query for k in ["水源", "采样点", "source"]) or "对比" in query:
            url, title = _chart_source_bar()
        elif any(k in query for k in ["趋势", "变化", "走势"]):
            indicator = _resolve_indicator(query)
            col = indicator if indicator in PREDICT_COLS else None
            source_id = None
            try:
                for s in _fetch("SELECT id, source_name FROM water_source_info WHERE status=1", (), limit=100):
                    if s.get("source_name") and s["source_name"] in query:
                        source_id = s["id"]
                        break
            except Exception:
                pass
            days_m = re.search(r"最近\s*(\d+)\s*天", query)
            days = min(int(days_m.group(1)), 90) if days_m else 30
            url, title = _chart_trend(col=col, source_id=source_id, days=days)
        else:
            url, title = _chart_pie()
    except Exception as e:
        return "图表生成失败：" + type(e).__name__ + ": " + str(e).split("\n")[0]

    if not url:
        return "图表生成失败：" + (title or "无数据")
    return f"{title}：\n![{title}]({url})"


# ============================================================
# 工具 1：查询历史检测记录
# ============================================================
def _query_records(query: str) -> str:
    """
    查历史检测记录。query 是自然语言描述，这里做关键词路由：
    - 含「不合格/不安全/unsafe」→ 只查 Unsafe
    - 含「合格/安全/safe」→ 只查 Safe
    - 含「最近N条」→ 取最近 N 条
    - 否则取最近 10 条
    """
    q = query.lower()
    base = """
        SELECT d.id, u.username, ws.source_name, d.ph, d.hardness, d.solids,
               d.chloramines, d.sulfate, d.conductivity, d.organic_carbon,
               d.trihalomethanes, d.turbidity, d.prediction,
               ROUND(d.probability,3) AS probability, d.wqi_score,
               d.water_grade, d.standard_level, d.detect_time
        FROM water_detection d
        LEFT JOIN users u ON d.user_id = u.id
        LEFT JOIN water_source_info ws ON d.source_id = ws.id
    """
    where = ""
    params = ()

    if "不合格" in query or "不安全" in q or "unsafe" in q:
        where = "WHERE d.prediction = %s"
        params = ("Unsafe",)
    elif "合格" in query or "安全" in query or "safe" in q:
        where = "WHERE d.prediction = %s"
        params = ("Safe",)

    sql = f"{base} {where} ORDER BY d.detect_time DESC LIMIT %s"
    n = 10
    # 简单解析「最近N条」
    import re
    m = re.search(r"最近\s*(\d+)\s*条", query)
    if m:
        n = min(int(m.group(1)), 50)
    rows = _fetch(sql, params + (n,), limit=n)

    if not rows:
        return "没有查到符合条件的检测记录。"
    # 把 datetime 转字符串，方便序列化
    for r in rows:
        if r.get("detect_time"):
            r["detect_time"] = str(r["detect_time"])
    return f"共 {len(rows)} 条记录：\n" + json.dumps(rows, ensure_ascii=False, indent=2)


# ============================================================
# 工具 2：查询预警日志
# ============================================================
def _query_alerts(query: str) -> str:
    """查预警日志。query 含「未解决/未处理」→ 只看 is_resolved=0"""
    base = """
        SELECT w.id, w.warning_level, w.warning_message, w.is_resolved,
               w.create_time, w.handle_time, d.id AS detection_id,
               d.prediction, ROUND(d.probability,3) AS probability,
               ws.source_name
        FROM warning_log w
        JOIN water_detection d ON w.detection_id = d.id
        LEFT JOIN water_source_info ws ON d.source_id = ws.id
    """
    q = query.lower()
    if "未解决" in query or "未处理" in query or "unresolved" in q:
        sql = f"{base} WHERE w.is_resolved = 0 ORDER BY w.create_time DESC LIMIT %s"
        rows = _fetch(sql, (20,), limit=20)
    else:
        sql = f"{base} ORDER BY w.create_time DESC LIMIT %s"
        rows = _fetch(sql, (20,), limit=20)

    if not rows:
        return "当前没有预警记录。"
    for r in rows:
        if r.get("create_time"):
            r["create_time"] = str(r["create_time"])
        if r.get("handle_time"):
            r["handle_time"] = str(r["handle_time"])
    return f"共 {len(rows)} 条预警：\n" + json.dumps(rows, ensure_ascii=False, indent=2)


# ============================================================
# 工具 3：水质预测（调用现有模型）
# ============================================================
def _predict_water(query: str) -> str:
    """
    解析出 9 项指标做预测。query 是自然语言，期望含类似
    "ph=7.2, 硬度150, 浊度2.3" 的描述。
    """
    import re
    import pandas as pd
    # 延迟 import，避免 chat_tools 被 import 时就触发模型加载
    try:
        from ai_api import make_prediction
    except Exception as e:
        return (
            "预测功能暂时不可用：水质模型依赖未就绪（"
            + type(e).__name__ + ": " + str(e).split("\n")[0]
            + "）。请先在 WaterQualityAI 目录安装完整依赖"
            "（pip install -r requirements.txt）并确保 .pkl 模型文件存在。"
            "其他功能（查记录/查预警/查标准）不受影响。"
        )

    found = {}
    # 先按指标中文名/英文名在 query 里找「指标 值」或「指标=值」或「指标:值」
    text = query
    # 统一全角符号
    text = text.replace("：", ":").replace("＝", "=").replace("，", ",")
    for alias, col in INDICATOR_ALIAS.items():
        # 匹配：别名 + 可选空格/=:号 + 数字（支持小数）
        pat = rf"{re.escape(alias)}\s*[:=]?\s*([0-9]+\.?[0-9]*)"
        m = re.search(pat, text)
        if m:
            found[col] = float(m.group(1))

    # 9 项必须齐
    missing = [c for c in PREDICT_COLS if c not in found]
    if missing:
        return (
            "做水质预测需要 9 项指标，当前缺少："
            + "、".join(missing)
            + "。\n请补充完整指标，例如：ph=7.2, 硬度=150, 固体=320, "
            "氯胺=2.1, 硫酸盐=180, 电导率=450, 有机碳=1.2, "
            "三卤甲烷=25, 浊度=2.3"
        )

    # 构造模型要求的 DataFrame（列名严格匹配）
    df = pd.DataFrame([{c: found[c] for c in PREDICT_COLS}])
    result = make_prediction(df)
    return "预测结果：\n" + json.dumps(result, ensure_ascii=False, indent=2)


# ============================================================
# 工具 4：查询水质标准 / 水源信息
# ============================================================
def _query_standards(query: str) -> str:
    """
    query 含「水源/采样点」→ 查 water_source_info
    query 含「标准/限值」→ 查 water_standard（可按等级过滤）
    query 含「饮用水/地表水/污水」→ 查对应等级标准
    否则返回水源列表
    """
    q = query.lower()
    if "水源" in query or "采样点" in query or "source" in q:
        # 先看 water_source_info 表是否建了（早期版本库可能没有）
        exists = _fetch(
            "SELECT COUNT(*) AS c FROM information_schema.tables "
            "WHERE table_schema=%s AND table_name='water_source_info'",
            (DB_CONFIG["database"],), limit=1,
        )
        if not exists or not exists[0]["c"]:
            # 退化：water_detection 是否有 source_id 列
            has_sid = _fetch(
                "SELECT COUNT(*) AS c FROM information_schema.columns "
                "WHERE table_schema=%s AND table_name='water_detection' "
                "AND column_name='source_id'",
                (DB_CONFIG["database"],), limit=1,
            )
            if has_sid and has_sid[0]["c"]:
                rows = _fetch(
                    "SELECT source_id, COUNT(*) AS cnt FROM water_detection "
                    "WHERE source_id IS NOT NULL GROUP BY source_id "
                    "ORDER BY cnt DESC",
                    (), limit=20,
                )
                if rows:
                    return (
                        "本地库未建 water_source_info 水源信息表。"
                        "从检测记录看，出现过以下 source_id：\n"
                        + json.dumps(rows, ensure_ascii=False, indent=2)
                    )
            return (
                "本地库未建 water_source_info 水源信息表，"
                "且 water_detection 也没有 source_id 列（早期版本库结构），"
                "暂无法查询水源信息。可改用「最近检测记录」了解检测情况。"
            )
        rows = _fetch(
            "SELECT id, source_name, source_type, province, city, "
            "description, status FROM water_source_info WHERE status=1 "
            "ORDER BY id",
            (), limit=50,
        )
        return f"水源信息（{len(rows)} 条）：\n" + json.dumps(
            rows, ensure_ascii=False, indent=2
        )

    # 标准查询
    level = None
    for lv in ["饮用水", "地表水I类", "地表水II类", "污水排放"]:
        if lv in query:
            level = lv
            break
    if level:
        rows = _fetch(
            "SELECT indicator_name, min_value, max_value, unit, "
            "standard_level, standard_name FROM water_standard "
            "WHERE standard_level=%s ORDER BY id",
            (level,), limit=20,
        )
        return f"{level} 标准（{len(rows)} 项）：\n" + json.dumps(
            rows, ensure_ascii=False, indent=2
        )

    # 默认：返回饮用水标准（最常用）
    rows = _fetch(
        "SELECT indicator_name, min_value, max_value, unit, "
        "standard_level, standard_name FROM water_standard "
        "WHERE standard_level='饮用水' ORDER BY id",
        (), limit=20,
    )
    return f"饮用水标准（GB5749-2022，共 {len(rows)} 项）：\n" + json.dumps(
        rows, ensure_ascii=False, indent=2
    )


# ============================================================
# 会话历史持久化（chat_session / chat_message 表）
# ============================================================
def _ensure_tables():
    """确保会话历史表存在（幂等）"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "CREATE TABLE IF NOT EXISTS chat_session ("
                " id VARCHAR(64) PRIMARY KEY,"
                " client_id VARCHAR(64) NOT NULL,"
                " title VARCHAR(200) NOT NULL,"
                " created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                " updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,"
                " INDEX idx_client (client_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
            cur.execute(
                "CREATE TABLE IF NOT EXISTS chat_message ("
                " id BIGINT AUTO_INCREMENT PRIMARY KEY,"
                " session_id VARCHAR(64) NOT NULL,"
                " role VARCHAR(10) NOT NULL,"
                " content MEDIUMTEXT NOT NULL,"
                " created_at DATETIME DEFAULT CURRENT_TIMESTAMP,"
                " INDEX idx_session (session_id)"
                ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
            )
        conn.commit()
    finally:
        conn.close()


def create_chat_session(client_id: str, title: str = None) -> dict:
    """新建会话，返回 {session_id, title, created_at}"""
    import uuid
    sid = uuid.uuid4().hex
    title = (title or "新对话").strip()[:60] or "新对话"
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_session (id, client_id, title) VALUES (%s,%s,%s)",
                (sid, client_id, title),
            )
        conn.commit()
    finally:
        conn.close()
    return {"session_id": sid, "title": title}


def list_chat_sessions(client_id: str, limit: int = 30) -> list:
    """按更新时间倒序返回该 client 的会话列表"""
    conn = _get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT s.id, s.title, s.created_at, s.updated_at, "
                "(SELECT COUNT(*) FROM chat_message m WHERE m.session_id=s.id) AS msg_count, "
                "(SELECT m.content FROM chat_message m WHERE m.session_id=s.id "
                " ORDER BY m.id DESC LIMIT 1) AS last_preview "
                "FROM chat_session s WHERE s.client_id=%s "
                "ORDER BY s.updated_at DESC LIMIT %s",
                (client_id, limit),
            )
            rows = cur.fetchall()
        for r in rows:
            for k in ("created_at", "updated_at"):
                if r.get(k):
                    r[k] = str(r[k])
            if r.get("last_preview") and len(r["last_preview"]) > 80:
                r["last_preview"] = r["last_preview"][:80] + "…"
        return rows
    finally:
        conn.close()


def get_session_owner(session_id: str):
    """返回会话所属的 client_id；不存在返回 None"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT client_id FROM chat_session WHERE id=%s", (session_id,))
            row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def get_chat_messages(session_id: str, client_id: str = None) -> list:
    """返回某会话的全部消息 [{role, content, created_at}]。
    传入 client_id 时做归属校验：不是同一 client 则返回空（防越权读取）。"""
    if client_id is not None and get_session_owner(session_id) != client_id:
        return []
    conn = _get_conn()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute(
                "SELECT role, content, created_at FROM chat_message "
                "WHERE session_id=%s ORDER BY id",
                (session_id,),
            )
            rows = cur.fetchall()
        for r in rows:
            if r.get("created_at"):
                r["created_at"] = str(r["created_at"])
        return rows
    finally:
        conn.close()


def add_chat_message(session_id: str, role: str, content: str, update_title: bool = False) -> None:
    """写入一条消息；update_title=True 时若标题仍是默认值则用首条用户消息更新标题"""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_message (session_id, role, content) VALUES (%s,%s,%s)",
                (session_id, role, content),
            )
            if update_title and role == "user" and content.strip():
                title = content.strip().replace("\n", " ")[:30]
                cur.execute(
                    "UPDATE chat_session SET title=%s WHERE id=%s AND title='新对话'",
                    (title, session_id),
                )
        conn.commit()
    finally:
        conn.close()


def delete_chat_session(session_id: str, client_id: str = None) -> bool:
    """删除会话及其消息。传入 client_id 时先校验归属，非本人返回 False。"""
    if client_id is not None and get_session_owner(session_id) != client_id:
        return False
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_message WHERE session_id=%s", (session_id,))
            cur.execute("DELETE FROM chat_session WHERE id=%s", (session_id,))
        conn.commit()
        return True
    finally:
        conn.close()


# ============================================================
# 包装成 LangChain Tool 列表
# ============================================================
def get_chat_tools() -> list:
    """返回 7 个 LangChain Tool，供 create_agent 挂载"""
    return [
        Tool(
            name="query_records",
            description=(
                "查询系统中的历史水质检测记录。"
                "当用户问『最近有几条检测』『有哪些不合格的水样』"
                "『某水源的检测情况』时用这个工具。"
                "输入参数 query：用户的自然语言描述。"
            ),
            func=_query_records,
        ),
        Tool(
            name="query_alerts",
            description=(
                "查询水质预警日志。当用户问『有哪些预警』"
                "『未处理的警告』『高危记录』时用这个工具。"
                "输入参数 query：用户的自然语言描述。"
            ),
            func=_query_alerts,
        ),
        Tool(
            name="predict_water",
            description=(
                "对一组水质指标做 AI 预测，判断安全/不安全、水质等级。"
                "当用户给出 pH、硬度、浊度等数值想判断水质时用这个工具。"
                "需要 9 项指标：ph、硬度、固体、氯胺、硫酸盐、电导率、"
                "有机碳、三卤甲烷、浊度。"
                "输入参数 query：包含 9 项指标数值的自然语言，"
                "如『ph=7.2, 硬度=150, 浊度=2.3 ...』。"
            ),
            func=_predict_water,
        ),
        Tool(
            name="query_standards",
            description=(
                "查询水质标准限值或水源信息。当用户问『pH 国标范围是多少』"
                "『饮用水标准』『有哪些采样点/水源』时用这个工具。"
                "输入参数 query：用户的自然语言描述。"
            ),
            func=_query_standards,
        ),
        Tool(
            name="standards_check",
            description=(
                "把最近检测记录（或指定水源的检测记录）逐项与所选水质标准对照，"
                "指出哪些指标超过上限/低于下限，并给处理建议。"
                "当用户问『最近这批水样哪些指标超标』『对照饮用水标准检查一下』"
                "『这条记录合不合规』时用这个工具。"
                "输入参数 query：用户的自然语言描述（可含标准等级、水源名、最近N条）。"
            ),
            func=_check_standards,
        ),
        Tool(
            name="trend_analysis",
            description=(
                "对某一水质指标或整体『不安全占比』做近 N 天趋势分析，"
                "并给出未来 3 天的简单预测。"
                "当用户问『最近水质趋势怎么样』『turbidity 近30天走势』"
                "『不安全比例是在上升还是下降』时用这个工具。"
                "输入参数 query：用户的自然语言描述（可含指标名、水源名、最近N天）。"
            ),
            func=_trend_analysis,
        ),
        Tool(
            name="chart_report",
            description=(
                "生成图表或用 CSV 导出检测记录。图表类型按用户描述自动判断："
                "『分布/占比』→ Safe/Unsafe 饼图；『水源/对比』→ 各水源柱状图；"
                "『趋势/走势』→ 折线图；『导出/下载 excel/csv』→ 生成 CSV 下载链接。"
                "输出会带一个图片或下载链接，请原样保留在回答末尾。"
                "输入参数 query：用户的自然语言描述。"
            ),
            func=_chart_report,
        ),
    ]
