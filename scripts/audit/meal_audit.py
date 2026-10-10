#!/usr/bin/env python3
"""lhg-meal-plan 确定性食谱审计：31 条规则，零第三方依赖。

扫描交付目录（一周食谱 menu*.md / *食谱*.md、采购清单 shopping*.md /
*采购*.md、meta.json 元数据），输出 JSON 与人类可读报告；
有 blocker 时以 exit code 2 退出（供 hooks 与 CI 使用）。

用法：
    python3 meal_audit.py --target <目录> [--format json|text] [--fail-on blocker|warning|nit]

营养素口径说明：脚本只做"实测值 vs meta.json 目标区间"的偏差检查，
不规定目标区间本身。目标区间的设定依据应在 meta.json 的 source 字段注明
（如《中国居民膳食指南（2022）》），本脚本不编造、不内置任何人群的
"标准值"。规则文案均为本项目原创（详见仓库 ATTRIBUTION.md）。

免责声明：本脚本输出不是医疗建议。慢病/备孕人群请遵医嘱。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-meal-plan/meal-audit"

SKIP_DIRS = {".git", "__pycache__", "node_modules", "dist", "build"}

DISCLAIMER_RE = re.compile(r"非医疗建议")

# ---------------------------------------------------------------- 数据模型
class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line, snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "category": self.category, "title": self.title,
            "file": self.file, "line": self.line,
            "snippet": self.snippet, "detail": self.detail,
        }


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError:
        return None
    except OSError:
        return ""


def collect(target):
    menus, shoppings, metas = [], [], []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = os.path.join(root, f)
            fl = f.lower()
            if fl.endswith(".md") and ("menu" in fl or "食谱" in f):
                menus.append(p)
            elif fl.endswith(".md") and ("shopping" in fl or "采购" in f):
                shoppings.append(p)
            elif fl == "meta.json":
                metas.append(p)
    return {"menus": sorted(menus), "shoppings": sorted(shoppings),
            "metas": sorted(metas)}


# ---------------------------------------------------------------- 规则注册表
RULES = []
_RULE_BY_ID = {}


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        r = {"id": rule_id, "severity": severity, "category": category,
             "title": title, "detail": detail}
        _RULE_BY_ID[rule_id] = r
        r["check"] = fn
        RULES.append(r)
        return fn
    return deco


def _mk(rule_id, path, line, snippet):
    r = _RULE_BY_ID[rule_id]
    return Finding(r["id"], r["severity"], r["category"], r["title"],
                   path, line, snippet[:160], r["detail"])


# ---------------------------------------------------------------- 自建表
DAY_RE = re.compile(r"^#{1,3}\s*周[一二三四五六日天]")
MEAL_RE = re.compile(r"^[\s>-]*[-*]?\s*(早餐|午餐|晚餐|加餐)[：:]")
MACRO_RE = re.compile(r"P\s*:\s*(\d+)\s*g.*?C\s*:\s*(\d+)\s*g.*?F\s*:\s*(\d+)\s*g", re.I)
KCAL_RE = re.compile(r"(\d+)\s*kcal", re.I)

# 各人群禁忌食材（启发式关键词，命中即告警；备孕/慢病为 blocker）
TABOO = {
    "备孕": {
        "TAB-PREG-001": ["生鱼片", "刺身", "生蚝", "生鸡蛋", "溏心蛋", "生肉"],
        "TAB-PREG-002": ["啤酒", "白酒", "红酒", "清酒", "酒精"],
        "TAB-PREG-003": ["金枪鱼", "剑鱼", "鲨鱼", "方头鱼"],
    },
    "慢病": {
        "TAB-CHR-001": ["咸菜", "腊肉", "咸鱼", "酱菜", "火腿", "榨菜"],
        "TAB-CHR-002": ["奶茶", "蛋糕", "含糖饮料", "可乐", "糖果", "奶油"],
    },
    "减脂": {
        "TAB-FAT-001": ["油炸", "炸鸡", "薯条", "炸串"],
        "TAB-FAT-002": ["奶茶", "可乐", "果汁饮料", "含糖饮料"],
    },
}
TABOO_TITLE = {
    "TAB-PREG-001": "备孕忌生食", "TAB-PREG-002": "备孕忌酒精",
    "TAB-PREG-003": "备孕忌高汞鱼",
    "TAB-CHR-001": "慢病忌高盐", "TAB-CHR-002": "慢病忌高糖",
    "TAB-FAT-001": "减脂忌油炸", "TAB-FAT-002": "减脂忌含糖饮料",
}

PROTEIN_SRC = ["鸡胸肉", "鸡肉", "鸡蛋", "鱼", "三文鱼", "牛肉", "猪肉",
               "虾", "豆腐", "豆浆", "牛奶", "酸奶"]
VEG_LIST = ["西兰花", "菠菜", "白菜", "生菜", "胡萝卜", "番茄", "黄瓜",
            "芹菜", "青菜", "菜心", "茄子", "冬瓜"]
KNOWN_INGREDIENTS = PROTEIN_SRC + VEG_LIST + ["燕麦", "糙米", "红薯", "玉米",
                                             "苹果", "香蕉", "橙子", "花生",
                                             "坚果", "大米", "面条", "紫薯"]


def parse_menu(text):
    """解析食谱文本 → [ {day, line_no, meal, dish, p, c, f, kcal} ]。"""
    meals = []
    cur_day = None
    for i, ln in enumerate(text.split("\n"), 1):
        if DAY_RE.match(ln.strip()):
            cur_day = ln.strip()
            continue
        m = MEAL_RE.match(ln.strip())
        if m and cur_day:
            meal = m.group(1)
            rest = ln[m.end():]
            dish = rest.split("|")[0].strip(" ：:").strip()
            mm = MACRO_RE.search(rest)
            kk = KCAL_RE.search(rest)
            meals.append({
                "day": cur_day, "line": i, "meal": meal, "dish": dish,
                "p": int(mm.group(1)) if mm else None,
                "c": int(mm.group(2)) if mm else None,
                "f": int(mm.group(3)) if mm else None,
                "kcal": int(kk.group(1)) if kk else None,
                "raw": ln.strip(),
            })
    return meals


def day_totals(meals):
    totals = {}
    for m in meals:
        d = totals.setdefault(m["day"], {"p": 0, "c": 0, "f": 0, "kcal": 0,
                                          "n_macro": 0, "n_meals": 0})
        d["n_meals"] += 1
        if m["p"] is not None:
            d["p"] += m["p"]; d["c"] += m["c"]; d["f"] += m["f"]
            d["n_macro"] += 1
        if m["kcal"] is not None:
            d["kcal"] += m["kcal"]
    return totals


def load_meta(files):
    meta = {}
    for p in files:
        try:
            with open(p, encoding="utf-8") as fh:
                meta.update(json.load(fh))
        except Exception:
            pass
    return meta


# ---------------------------------------------------------------- 规则：营养素 NUT-*
def _nut_rule(rid, sev, key, idx, cmp_op, title, detail):
    @rule(rid, sev, "营养素", title, detail)
    def _n(ctx):
        out = []
        tg = (ctx["meta"].get("targets") or {}).get(key)
        if not tg or len(tg) != 2:
            return out
        lo, hi = tg
        for day, t in ctx["totals"].items():
            if t["n_macro"] == 0:
                continue
            v = t[{"protein_g": "p", "carbs_g": "c", "fat_g": "f",
                   "kcal": "kcal"}[key]]
            bad = (v < lo) if cmp_op == "<" else (v > hi)
            if bad:
                out.append(_mk(rid, ctx["menu_path"], 1,
                                "%s 当日 %s=%d，目标区间 [%d, %d]"
                                % (day, key, v, lo, hi)))
                break
        return out
    return _n


_nut_rule("NUT-K-001", "blocker", "kcal", 0, "<",
          "当日热量低于目标下限",
          "当日总热量低于 meta.json 目标区间下限。热量缺口过大不可持续，"
          "请上调食量或目标。")
_nut_rule("NUT-K-002", "warning", "kcal", 0, ">",
          "当日热量超出目标上限",
          "当日总热量超出目标区间上限，减脂/控糖目标会落空，请下调。")
_nut_rule("NUT-P-001", "blocker", "protein_g", 0, "<",
          "当日蛋白质低于目标下限",
          "蛋白质不足会影响肌肉维持与饱腹感，请增加优质蛋白。")
_nut_rule("NUT-P-002", "warning", "protein_g", 0, ">",
          "当日蛋白质超出目标上限",
          "蛋白质超出上限，多余部分不会变成肌肉，请回调。")
_nut_rule("NUT-C-001", "warning", "carbs_g", 0, "<",
          "当日碳水低于目标下限",
          "碳水过低可能影响训练表现与情绪，请评估是否可持续。")
_nut_rule("NUT-C-002", "warning", "carbs_g", 0, ">",
          "当日碳水超出目标上限",
          "碳水超出上限，请检查主食份量。")
_nut_rule("NUT-F-001", "warning", "fat_g", 0, "<",
          "当日脂肪低于目标下限",
          "脂肪过低影响激素与脂溶性维生素吸收，请适量增加。")
_nut_rule("NUT-F-002", "warning", "fat_g", 0, ">",
          "当日脂肪超出目标上限",
          "脂肪超出上限，多为烹调用油或零食贡献，请检查。")


# ---------------------------------------------------------------- 规则：过敏原 ALG-*
@rule("ALG-001", "blocker", "过敏原", "食谱含申报的过敏原",
      "食谱中出现 meta.json allergies 申报的过敏原。过敏不是偏好，"
      "必须整周剔除。")
def _g1(ctx):
    out = []
    algs = [a for a in (ctx["meta"].get("allergies") or []) if a]
    if not algs or not ctx["menu_text"]:
        return out
    for m in ctx["meals"]:
        for a in algs:
            if a and a in m["dish"]:
                out.append(_mk("ALG-001", ctx["menu_path"], m["line"],
                                "“%s”含过敏原“%s”" % (m["dish"], a)))
                break
    return out


# ---------------------------------------------------------------- 规则：人群禁忌 TAB-*
def _taboo_rule(rid, group, title):
    sev = "blocker" if group in ("备孕", "慢病") else "warning"
    detail = ("“%s”人群出现禁忌食材（%s）。备孕/慢病禁忌为 blocker，"
              "必须整周剔除；减脂禁忌为 warning。" % (group, title))
    @rule(rid, sev, "人群禁忌", title, detail)
    def _t(ctx):
        out = []
        if ctx["meta"].get("group") != group or not ctx["menu_text"]:
            return out
        kws = TABOO[group][rid]
        for m in ctx["meals"]:
            for k in kws:
                if k in m["dish"]:
                    out.append(_mk(rid, ctx["menu_path"], m["line"],
                                    "“%s”含禁忌“%s”" % (m["dish"], k)))
                    break
        return out
    return _t


for _g, _rids in TABOO.items():
    for _rid in _rids:
        _taboo_rule(_rid, _g, TABOO_TITLE[_rid])


# ---------------------------------------------------------------- 规则：多样性 DIV-*
@rule("DIV-REP-001", "warning", "多样性", "同一菜品连续两天出现",
      "同一菜品连续两天出现。偶尔重复可以接受，但连续重复容易吃腻弃餐，"
      "建议轮换。")
def _d1(ctx):
    out = []
    days = []
    seen = {}
    for m in ctx["meals"]:
        if m["day"] not in seen:
            seen[m["day"]] = len(days)
            days.append(m["day"])
    by_day = {}
    for m in ctx["meals"]:
        by_day.setdefault(m["day"], set()).add(m["dish"])
    for i in range(1, len(days)):
        dup = by_day[days[i]] & by_day[days[i - 1]]
        dup = {d for d in dup if d}
        if dup:
            out.append(_mk("DIV-REP-001", ctx["menu_path"], 1,
                            "%s 与 %s 重复：%s"
                            % (days[i - 1], days[i], "、".join(sorted(dup)))))
            break
    return out


@rule("DIV-REP-002", "warning", "多样性", "同一菜品一周出现 4 次以上",
      "同一菜品一周出现 4 次以上。食谱多样性不足，营养来源单一，"
      "请替换。")
def _d2(ctx):
    out = []
    cnt = {}
    for m in ctx["meals"]:
        if m["dish"]:
            cnt[m["dish"]] = cnt.get(m["dish"], 0) + 1
    for dish, n in sorted(cnt.items(), key=lambda x: -x[1]):
        if n >= 4:
            out.append(_mk("DIV-REP-002", ctx["menu_path"], 1,
                            "“%s”一周出现 %d 次" % (dish, n)))
            break
    return out


@rule("DIV-PRO-001", "warning", "多样性", "蛋白质来源单一",
      "全周蛋白质来源少于 3 种。蛋白质来源多样化有助于氨基酸互补，"
      "建议轮换禽肉/鱼虾/蛋/豆制品。")
def _d3(ctx):
    out = []
    all_dish = " ".join(m["dish"] for m in ctx["meals"])
    srcs = [s for s in PROTEIN_SRC if s in all_dish]
    # 去重包含关系（如"鸡肉"含于"鸡胸肉"）
    uniq = [s for s in srcs if not any(s != o and s in o for o in srcs)]
    if ctx["meals"] and len(uniq) < 3:
        out.append(_mk("DIV-PRO-001", ctx["menu_path"], 1,
                        "蛋白质来源仅 %d 种：%s" % (len(uniq), "、".join(uniq))))
    return out


@rule("DIV-VEG-001", "warning", "多样性", "蔬菜种类不足",
      "全周蔬菜种类少于 5 种。深色蔬菜轮换有助于微量营养素覆盖，"
      "建议增加种类。")
def _d4(ctx):
    out = []
    all_dish = " ".join(m["dish"] for m in ctx["meals"])
    vegs = [v for v in VEG_LIST if v in all_dish]
    if ctx["meals"] and len(vegs) < 5:
        out.append(_mk("DIV-VEG-001", ctx["menu_path"], 1,
                        "蔬菜仅 %d 种：%s" % (len(vegs), "、".join(vegs))))
    return out


# ---------------------------------------------------------------- 规则：采购清单 SHP-*
@rule("SHP-EX-001", "blocker", "采购清单", "缺采购清单文件",
      "交付目录缺少采购清单（shopping*.md / *采购*.md）。"
      "没有清单的食谱落不了地。")
def _p0(ctx):
    if ctx["shoppings"]:
        return []
    return [_mk("SHP-EX-001", ctx["target"], 0, "未找到采购清单文件")]


@rule("SHP-N-001", "warning", "采购清单", "采购项数量过少",
      "采购项少于 天数×4。按一周 5 天计至少 20 项，过少说明清单"
      "没覆盖全周食材。")
def _p1(ctx):
    out = []
    if not ctx["shoppings"]:
        return out
    n_days = len(ctx["totals"])
    items = []
    for p in ctx["shoppings"]:
        t = ctx["shop_texts"][p]
        items += [ln for ln in t.split("\n")
                  if re.match(r"\s*[-*]\s+(\[[ x]\])?\s*\S", ln)]
    if n_days and len(items) < n_days * 4:
        out.append(_mk("SHP-N-001", ctx["shoppings"][0], 1,
                        "采购项 %d < %d 天×4" % (len(items), n_days)))
    return out


@rule("SHP-DUP-001", "nit", "采购清单", "采购清单有重复项",
      "同一食材在清单里出现多次，合并后更清爽。")
def _p2(ctx):
    out = []
    for p in ctx["shoppings"]:
        t = ctx["shop_texts"][p]
        items = [re.sub(r"\s*[-*]\s+(\[[ x]\])?\s*", "", ln).strip()
                 for ln in t.split("\n")
                 if re.match(r"\s*[-*]\s+(\[[ x]\])?\s*\S", ln)]
        seen = set()
        for it in items:
            key = re.sub(r"\d+.*$", "", it).strip()
            if key in seen and key:
                out.append(_mk("SHP-DUP-001", p, 1, "重复项：%s" % key))
                break
            seen.add(key)
    return out


@rule("SHP-CAT-001", "warning", "采购清单", "采购清单无分类",
      "清单缺少分类标题（蛋白质/蔬菜/主食等）。分类采购效率更高，"
      "也不容易漏买。")
def _p3(ctx):
    out = []
    for p in ctx["shoppings"]:
        t = ctx["shop_texts"][p]
        if not re.search(r"^#{1,3}\s*(蛋白质|蔬菜|主食|水果|调料|乳制品|豆制品)",
                         t, re.M):
            out.append(_mk("SHP-CAT-001", p, 1, "未发现分类标题"))
    return out


@rule("SHP-MISS-001", "warning", "采购清单", "食谱食材未进采购清单",
      "食谱中出现的已知食材在采购清单里找不到。漏买会导致当天"
      "做不了这顿饭。")
def _p4(ctx):
    out = []
    if not ctx["shoppings"]:
        return out
    all_dish = " ".join(m["dish"] for m in ctx["meals"])
    shop_all = " ".join(ctx["shop_texts"].values())
    used = [ing for ing in KNOWN_INGREDIENTS if ing in all_dish]
    missing = [ing for ing in used if ing not in shop_all]
    if missing:
        out.append(_mk("SHP-MISS-001", ctx["shoppings"][0], 1,
                        "未采购：%s" % "、".join(missing[:5])))
    return out


# ---------------------------------------------------------------- 规则：免责声明 DSC-*
@rule("DSC-001", "blocker", "免责声明", "食谱缺免责声明",
      "食谱文件未包含'非医疗建议'免责声明。本插件输出不是医疗建议，"
      "慢病/备孕人群请遵医嘱——这句话必须出现在每一份食谱里。")
def _c1(ctx):
    out = []
    if ctx["menu_text"] and not DISCLAIMER_RE.search(ctx["menu_text"]):
        out.append(_mk("DSC-001", ctx["menu_path"], 1, "未找到'非医疗建议'声明"))
    return out


@rule("DSC-002", "blocker", "免责声明", "meta.json 未声明目标人群",
      "meta.json 缺少 group 字段（减脂/增肌/备孕/慢病）。人群不同禁忌不同，"
      "没有人群信息，禁忌规则只能跳过——不是'通过'，是'没查'。")
def _c2(ctx):
    if ctx["meta"].get("group"):
        return []
    return [_mk("DSC-002", ctx["target"], 0, "meta.json 缺少 group 字段")]


# ---------------------------------------------------------------- 规则：来源 SRC-*
@rule("SRC-001", "warning", "来源", "未注明膳食指南来源",
      "meta.json 的 source 字段为空。营养素目标区间的口径应注明来源"
      "（如《中国居民膳食指南（2022）》），否则目标区间无从验证。")
def _r1(ctx):
    if (ctx["meta"].get("source") or "").strip():
        return []
    return [_mk("SRC-001", ctx["target"], 0, "meta.json 缺少 source 字段")]


@rule("SRC-002", "warning", "来源", "营养素目标区间缺失",
      "meta.json 缺少 targets（如 kcal/protein_g/carbs_g/fat_g 区间）。"
      "没有目标区间，NUT-* 营养素规则只能跳过——不是'通过'，是'没查'。")
def _r2(ctx):
    if (ctx["meta"].get("targets") or {}):
        return []
    return [_mk("SRC-002", ctx["target"], 0, "meta.json 缺少 targets 字段")]


# ---------------------------------------------------------------- 规则：份量 POR-*
@rule("POR-001", "warning", "份量", "某餐缺宏量标注",
      "存在未标注 P/C/F 宏量的餐。没有宏量标注就无法做营养素测算，"
      "请补上（格式如 P:20g C:45g F:12g）。")
def _o1(ctx):
    out = []
    for m in ctx["meals"]:
        if m["p"] is None:
            out.append(_mk("POR-001", ctx["menu_path"], m["line"],
                            "%s %s：%s 缺宏量标注" % (m["day"], m["meal"], m["dish"])))
            break
    return out


@rule("POR-002", "warning", "份量", "某天餐数不足三餐",
      "某天少于 3 餐。不吃正餐靠加餐凑热量，血糖波动大，"
      "请补齐三餐。")
def _o2(ctx):
    out = []
    for day, t in ctx["totals"].items():
        if t["n_meals"] < 3:
            out.append(_mk("POR-002", ctx["menu_path"], 1,
                            "%s 仅 %d 餐" % (day, t["n_meals"])))
            break
    return out


# ---------------------------------------------------------------- 主流程
def run_audit(target, fail_on="blocker"):
    files = collect(target)
    menu_text, menu_path, meals = "", "", []
    if files["menus"]:
        menu_path = files["menus"][0]
        menu_text = read_text(menu_path) or ""
        meals = parse_menu(menu_text)
    shop_texts = {p: (read_text(p) or "") for p in files["shoppings"]}
    meta = {}
    for p in files["metas"]:
        try:
            with open(p, encoding="utf-8") as fh:
                meta.update(json.load(fh))
        except Exception:
            pass
    ctx = {"target": target, "menus": files["menus"],
           "shoppings": files["shoppings"],
           "menu_path": menu_path, "menu_text": menu_text, "meals": meals,
           "totals": day_totals(meals), "shop_texts": shop_texts,
           "meta": meta}
    findings = []
    for r in RULES:
        try:
            findings.extend(r["check"](ctx) or [])
        except Exception as e:
            findings.append(Finding(r["id"], "warning", r["category"],
                                    r["title"] + "（规则执行异常）",
                                    target, 0, "",
                                    "规则内部出错：%s（fail-open 记为 warning）" % e))
    sev_rank = {"blocker": 0, "warning": 1, "nit": 2}
    findings.sort(key=lambda f: (sev_rank.get(f.severity, 3), f.rule_id))
    counts = {"blocker": 0, "warning": 0, "nit": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return {
        "tool": TOOL, "version": VERSION, "target": target,
        "summary": {"rules_run": len(RULES), "blocker": counts["blocker"],
                    "warning": counts["warning"], "nit": counts["nit"],
                    "total": len(findings),
                    "days": len(ctx["totals"]), "meals": len(meals)},
        "findings": [f.to_dict() for f in findings],
    }, fail_on


def fmt_text(rep):
    s = rep["summary"]
    lines = ["[%s v%s] 目标：%s" % (rep["tool"], rep["version"], rep["target"]),
             "规则 %d 条 → blocker %d / warning %d / nit %d"
             % (s["rules_run"], s["blocker"], s["warning"], s["nit"]),
             "覆盖 %d 天 %d 餐" % (s["days"], s["meals"]), ""]
    for f in rep["findings"]:
        lines.append("[%s][%s] %s :: %s:%s" %
                     (f["severity"], f["rule_id"], f["title"], f["file"], f["line"]))
        if f["snippet"]:
            lines.append("    " + f["snippet"])
        lines.append("    " + f["detail"])
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="lhg-meal-plan 确定性食谱审计")
    ap.add_argument("--target", required=True, help="交付目录")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    ap.add_argument("--fail-on", choices=["blocker", "warning", "nit"],
                    default="blocker")
    args = ap.parse_args(argv)
    rep, fail_on = run_audit(args.target, args.fail_on)
    if args.format == "json":
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(fmt_text(rep))
    rank = {"blocker": 0, "warning": 1, "nit": 2}
    thresh = rank[fail_on]
    bad = any(rank.get(f["severity"], 3) <= thresh for f in rep["findings"])
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
