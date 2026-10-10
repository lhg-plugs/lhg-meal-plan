#!/usr/bin/env python3
"""lhg-meal-plan 插件冒烟测试：全部绿才算过。

检查项：
 1. 三个 JSON 合法（plugin.json / marketplace.json / hooks.json）
 2. 4 个 SKILL.md 都有 name/description frontmatter，且 150~400 行
 3. 3 个 commands 都有 description + argument-hint frontmatter
 4. 3 个 agents 都有 name/description/tools/model frontmatter
 5. skills 平台中立：不含 Claude Code 专有工具名
 6. fixtures：坏 fixture 的埋点规则必须全部命中且脚本 exit!=0；
    好 fixture 零 blocker 且 exit==0；
    SHP-EX-001（缺采购清单）/ DSC-002（缺人群）/ SRC-002（缺 targets）
    用临时目录单独覆盖
 7. hooks 脚本：非食谱文件放行 / 食谱缺声明拦截 / 有声明放行 /
    逃生开关 / 读不到文件放行
 8. README 顶部有免责声明

用法：python3 smoke_test.py [--repo <插件根目录>]
退出码：0=全绿，1=有失败。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((PASS if cond else FAIL, name, detail))
    return cond


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def frontmatter(path):
    """解析 markdown 顶部 --- YAML 块（只取一层 key: value）。"""
    text = read(path)
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for ln in text[3:end].split("\n"):
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)


# 预期的埋点命中（坏 fixture 必须全部命中）
BAD_MUST = {
    "NUT-K-001", "NUT-K-002", "NUT-P-001", "NUT-P-002",
    "NUT-C-001", "NUT-C-002", "NUT-F-001", "NUT-F-002",
    "ALG-001",
    "TAB-PREG-001", "TAB-PREG-002", "TAB-PREG-003",
    "DIV-REP-001", "DIV-REP-002", "DIV-PRO-001", "DIV-VEG-001",
    "SHP-N-001", "SHP-DUP-001", "SHP-CAT-001", "SHP-MISS-001",
    "DSC-001", "SRC-001", "POR-001", "POR-002",
}
# 平台中立红线：skill 正文不许出现这些 Claude Code 专有表述
NEUTRAL_DENY = ["Task tool", "Bash tool", "Edit tool", "Write tool", "Read tool",
                "AskUserQuestion", "subagent_type", "PreToolUse", "PostToolUse",
                "${CLAUDE_", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    AUDIT = os.path.join(repo, "scripts", "audit")

    # 1. JSON 合法
    for rel in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                "hooks/hooks.json"]:
        p = os.path.join(repo, rel)
        try:
            d = json.loads(read(p))
            check("JSON 合法: " + rel, True)
            if rel.endswith("plugin.json"):
                check("plugin.json name==lhg-meal-plan",
                      d.get("name") == "lhg-meal-plan", str(d.get("name")))
                check("plugin.json 有 version/description/author",
                      all(d.get(k) for k in ("version", "description", "author")))
            if rel.endswith("marketplace.json"):
                ps = d.get("plugins", [])
                check("marketplace.json source==./",
                      len(ps) == 1 and ps[0].get("source") == "./" and
                      ps[0].get("name") == "lhg-meal-plan", str(ps))
            if rel.endswith("hooks.json"):
                check("hooks.json 顶层有 hooks 包装", "hooks" in d)
                evts = d["hooks"]
                check("hooks.json 有 PreToolUse", "PreToolUse" in evts, str(list(evts)))
        except Exception as e:
            check("JSON 合法: " + rel, False, str(e))

    # 2. SKILL.md frontmatter + 行数
    for skill in ["lhg-mp-profile", "lhg-mp-nutrition", "lhg-mp-menu",
                  "lhg-mp-audit"]:
        p = os.path.join(repo, "skills", skill, "SKILL.md")
        fm = frontmatter(p)
        check("skill frontmatter: " + skill,
              bool(fm.get("name")) and bool(fm.get("description")),
              "name=%s" % fm.get("name"))
        nlines = len(read(p).split("\n"))
        check("skill 行数 150~400: %s (%d 行)" % (skill, nlines),
              150 <= nlines <= 400, str(nlines))
        body = read(p)
        bad_words = [w for w in NEUTRAL_DENY if w in body]
        check("skill 平台中立: " + skill, not bad_words, "命中: %s" % bad_words)
        check("skill 有出品区: " + skill,
              "出品：刘洪光" in body and "https://github.com/lhg-skills" in body)
        check("skill 有自检与反馈: " + skill, "自检与反馈" in body)
        check("skill 有免责声明: " + skill, "非医疗建议" in body)

    # 3. commands
    for cmd in ["meal-plan", "meal-calc", "meal-audit"]:
        p = os.path.join(repo, "commands", cmd + ".md")
        fm = frontmatter(p)
        check("command description: " + cmd, bool(fm.get("description")),
              str(fm.get("description"))[:60])
        check("command argument-hint: " + cmd, bool(fm.get("argument-hint")),
              str(fm.get("argument-hint"))[:40])

    # 4. agents
    for ag in ["nutritionist", "menu-chef", "safety-reviewer"]:
        p = os.path.join(repo, "agents", ag + ".md")
        fm = frontmatter(p)
        check("agent frontmatter: " + ag,
              all(fm.get(k) for k in ("name", "description", "tools", "model")),
              str({k: fm.get(k) for k in ("name", "model")}))

    # 5. 审计脚本冒烟
    def audit_hits(target):
        r = run([sys.executable, os.path.join(AUDIT, "meal_audit.py"),
                 "--target", os.path.join(repo, target), "--format", "json"])
        try:
            d = json.loads(r.stdout)
        except Exception:
            return None, r.returncode, []
        return d["summary"], r.returncode, [f["rule_id"] for f in d["findings"]]

    s, code, ids = audit_hits("fixtures/bad")
    check("坏 fixture exit!=0", code != 0, "exit=%d" % code)
    check("坏 fixture blocker>0", s and s["blocker"] > 0, str(s))
    missing = BAD_MUST - set(ids)
    check("坏 fixture 埋点全命中 (%d/%d)" % (len(BAD_MUST - missing), len(BAD_MUST)),
          not missing, "缺失: %s" % sorted(missing))

    s, code, ids = audit_hits("fixtures/good")
    check("好 fixture 零 blocker", s and s["blocker"] == 0, str(s))
    check("好 fixture exit==0", code == 0, "exit=%d" % code)

    # SHP-EX-001 / DSC-002 / SRC-002 单独覆盖：缺采购清单、缺人群、缺 targets
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "menu-x.md"), "w") as fh:
            fh.write("## 周一\n- 早餐：白粥 | P:5g C:30g F:2g | 150kcal\n")
        with open(os.path.join(td, "meta.json"), "w") as fh:
            fh.write('{"targets": {"kcal": [1500, 1800]}}')
        s, code, ids = audit_hits(td)
        check("SHP-EX-001 命中缺采购清单", "SHP-EX-001" in ids, str(ids))
        check("DSC-002 命中缺人群", "DSC-002" in ids, str(ids))

    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "menu-x.md"), "w") as fh:
            fh.write("## 周一\n- 早餐：白粥 | P:5g C:30g F:2g | 150kcal\n")
        with open(os.path.join(td, "meta.json"), "w") as fh:
            fh.write('{"group": "减脂"}')
        s, code, ids = audit_hits(td)
        check("SRC-002 命中缺 targets", "SRC-002" in ids, str(ids))

    # 规则总数（对外口径：30+ 条）
    n = json.loads(run([sys.executable, os.path.join(AUDIT, "meal_audit.py"),
                        "--target", os.path.join(repo, "fixtures/good"),
                        "--format", "json"]).stdout)["summary"]["rules_run"]
    check("规则总数>=30 (%d)" % n, n >= 30, str(n))

    # 6. hooks 脚本
    def hook(script, payload, env=None):
        e = dict(os.environ); e.update(env or {})
        return run([sys.executable, os.path.join(repo, "hooks", script)],
                   input=payload, env=e)

    r = hook("check_disclaimer_before_save.py",
             '{"tool_input":{"file_path":"/tmp/notes/todo.md",'
             '"content":"随便写点"}}')
    check("hook: 非食谱文件放行", r.returncode == 0 and not r.stdout.strip(),
          r.stdout[:80])

    # 食谱缺声明 → 拦截（用 Write 的 content 字段，不依赖文件存在）
    r = hook("check_disclaimer_before_save.py",
             json.dumps({"tool_input": {
                 "file_path": "/tmp/meal-plans/weekly-menu.md",
                 "content": "## 周一\n- 早餐：白粥\n"}}))
    try:
        d = json.loads(r.stdout)
        denied = d["hookSpecificOutput"]["permissionDecision"] == "deny"
    except Exception:
        denied = False
    check("hook: 食谱缺声明拦截", denied, r.stdout[:120])

    # 食谱有声明 → 放行
    r = hook("check_disclaimer_before_save.py",
             json.dumps({"tool_input": {
                 "file_path": "/tmp/meal-plans/weekly-menu.md",
                 "content": "> 非医疗建议\n## 周一\n- 早餐：白粥\n"}}))
    check("hook: 食谱有声明放行", r.returncode == 0 and not r.stdout.strip(),
          r.stdout[:80])

    # 逃生开关
    r = hook("check_disclaimer_before_save.py",
             json.dumps({"tool_input": {
                 "file_path": "/tmp/meal-plans/weekly-menu.md",
                 "content": "## 周一\n"}}),
             {"LHG_MP_HOOKS_OFF": "1"})
    check("hook: 逃生开关生效", r.returncode == 0 and not r.stdout.strip())

    # 读不到文件：fail-open
    r = hook("check_disclaimer_before_save.py",
             '{"tool_input":{"file_path":"/tmp/meal-plans/不存在.md"}}')
    check("hook: 读不到文件放行", r.returncode == 0 and not r.stdout.strip())

    # 7. README 顶部免责声明
    readme = read(os.path.join(repo, "README.md"))
    check("README 顶部有免责声明",
          readme.lstrip().startswith(">") and "非医疗建议" in readme[:500],
          readme[:80])

    # 报告
    print("=" * 60)
    print("lhg-meal-plan 冒烟测试报告")
    print("=" * 60)
    fails = 0
    for st, name, detail in results:
        mark = "✓" if st == PASS else "✗"
        print("%s %s %s" % (mark, st, name))
        if detail and st == FAIL:
            print("    → %s" % detail)
        if st == FAIL:
            fails += 1
    print("=" * 60)
    print("共 %d 项，通过 %d，失败 %d" % (len(results), len(results) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
