#!/usr/bin/env python3
"""lhg-meal-plan 硬门：保存食谱文件前检查免责声明。

触发：PreToolUse / Write、Edit。脚本先判断本次写入的文件是否像
"食谱文件"（路径或文件名含 menu / meal-plan / 食谱 / weekly），
不是则 0 开销直接放行；是则检查内容是否包含"非医疗建议"免责声明，
缺失则拦截。

逃生方式（按推荐度排序）：
  1. 在食谱顶部加上免责声明（推荐，见 skill lhg-mp-audit 第 2 节模板）。
  2. 紧急情况：LHG_MP_HOOKS_OFF=1（单次豁免本次 hook）。
  3. /plugin disable lhg-meal-plan（整个插件停用，hooks 不再触发）。

设计原则：脚本内部出错（读不到文件、解析失败等）时 fail-open 直接放行，
不因插件自身故障骚扰用户；真正的门禁在 /lhg-meal-plan:meal-audit。
零第三方依赖。
"""

import json
import os
import re
import sys

MEAL_RE = re.compile(r"menu|meal-plan|食谱|weekly", re.I)
DISCLAIMER_RE = re.compile(r"非医疗建议")


def content_to_check(tool_input, file_path):
    """优先用 Write 的 content 字段（新文件 PreToolUse 时文件还不存在），
    否则读文件；Edit 则合并判断：文件已有声明或本次新增内容含声明即放行。"""
    op = (tool_input.get("new_string") or "") + "\n" + (tool_input.get("content") or "")
    if DISCLAIMER_RE.search(op):
        return ""  # 本次写入就带了声明：直接放行
    if tool_input.get("content"):
        # Write 且 content 已给：以它为准（上面没搜到即缺失）
        return tool_input["content"]
    try:
        with open(file_path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None  # 读不到：fail-open


def main() -> int:
    # 逃生开关
    if os.environ.get("LHG_MP_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # 输入解析失败：fail-open

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""

    # 非食谱文件：快速放行
    if not file_path or not MEAL_RE.search(file_path):
        return 0

    try:
        text = content_to_check(tool_input, file_path)
    except Exception:
        return 0  # 检查自身出错：fail-open

    if text is None:
        return 0  # 文件读不到（可能是新建且无 content）：fail-open
    if not text.strip():
        return 0  # 本次写入已带声明（content_to_check 返回 "" 约定）
    if DISCLAIMER_RE.search(text):
        return 0

    lines = [
        "食谱被 lhg-meal-plan 硬门拦截：未找到\"非医疗建议\"免责声明。",
        "文件：%s" % file_path,
        "",
        "请在食谱顶部加上（模板）：",
        "> 免责声明：本食谱仅供一般性膳食参考，非医疗建议。",
        "> 慢病/备孕人群请遵医嘱；如有食物过敏，请自行剔除相关食材。",
        "",
        "紧急豁免（单次）：LHG_MP_HOOKS_OFF=1",
    ]
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "\n".join(lines),
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
