> **⚠️ 免责声明：本插件输出仅供一般性膳食参考，非医疗建议。慢病/备孕人群请遵医嘱；如有食物过敏，请自行剔除相关食材；营养素目标区间的口径来源见 meta.json 的 source 字段。**

<!-- About 简介（推送后填写到仓库 About 栏）：
营养食谱专家：一周食谱与采购清单一键生成——目标人群画像、三大营养素脚本化测算、一周食谱编排、采购清单；免责声明：非医疗建议，慢病/备孕人群请遵医嘱。 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-meal-plan
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, nutrition, meal-planning, diet, grocery-list, macros -->

<p align="center">
  <img src="./assets/readme/hero.svg" width="100%" alt="lhg-meal-plan — 营养食谱专家">
</p>

> **一句话介绍**：营养食谱专家：一周食谱与采购清单一键生成——目标人群画像、三大营养素脚本化测算、一周食谱编排、采购清单；免责声明：非医疗建议，慢病/备孕人群请遵医嘱。

**一键安装**：在 Claude Code 里运行

```bash
/plugin marketplace add lhg-plugs/lhg-meal-plan
/plugin install lhg-meal-plan@lhg-plugs
```

## 它能帮你做出什么

每条产出先过确定性脚本自查，再交人工复核清单——数字全部数自仓库里的审计脚本，不靠模型"自觉"。

| 自查脚本 | 规则数 | blocker | warning | nit | 覆盖 |
|---|---|---|---|---|---|
| `scripts/audit/meal_audit.py` | 16 | 4 | 11 | 1 | 过敏原、多样性、采购清单、免责声明、来源、份量 |
| **合计** | **16** | **4** | **11** | **1** | |

- **零 LLM 成本**：规则是纯 Python 脚本，零第三方依赖，本地运行。
- **坏 / 好对照可验**：`fixtures/` 里备有坏/好用例，冒烟测试断言命中情况。
- **冒烟全绿**：`python3 smoke_test.py` 56 项全部通过（JSON 合法、frontmatter 完整、命令/skill/agent 齐全）。

## 它是什么

`lhg-meal-plan` 是一个 Claude Code 插件（plugin 为主、skill 为辅）：

- **3 个命令**（小白入口）：`meal-audit` 食谱自检、`meal-calc` 营养素测算、`meal-plan` 营养食谱一键生成
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：lhg-mp-audit, lhg-mp-menu, lhg-mp-nutrition, lhg-mp-profile
- **3 个专家 agent**：menu-chef, nutritionist, safety-reviewer
- **2 个 hooks**（`hooks/`：check_disclaimer_before_save.py），关键操作前自动把关
- **16 条确定性自查规则**：纯 Python 脚本，见上表

## 为什么是它

不是一个 prompt，而是一套互相兜底的机制：

1. **确定性脚本（机器）+ 人工复核清单（人）**：先跑 `scripts/` 下的审计脚本（共 16 条规则），发现分三级：**blocker**（必须修）、**warning**（修或写豁免理由）、**nit**（顺手修）；再按对应 skill 的复核清单过一遍脚本抓不到的（内容真实性、越权、口径一致）。blocker 清零才算做完；为清零改规则算作弊，不许。
2. **硬门，不是提醒**：hooks 在关键操作前自动拦截或警告（见 `hooks/`），而不是只在文档里写一句"请注意"。
3. **方法论沉淀在 skill 里**：流程、检查清单、口径都写在 `skills/` 的方法论里，命令只是入口；换个 agent 平台也能复用同一套做法。
4. **可验，不是可信**：`fixtures/` 备有坏/好对照用例，`smoke_test.py` 一键验证，规则有没有生效、自己跑一遍就知道。

## 快速上手

```bash
# 1. 安装（Claude Code 里运行）
/plugin marketplace add lhg-plugs/lhg-meal-plan
/plugin install lhg-meal-plan@lhg-plugs

# 2. 营养食谱一键生成：目标人群画像→营养素测算→一周食谱→采购清单，全程带"非医疗建
/lhg-meal-plan:meal-plan "减脂，70kg，不吃香菜" --days 7
```

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-meal-plan:meal-audit` | 食谱自检：先跑 31 条确定性审计脚本（营养素偏差/过敏原/禁忌/多样性/采购清单对应），再按人工清单评审… | `/lhg-meal-plan:meal-audit ./delivery/` |
| `/lhg-meal-plan:meal-calc` | 营养素测算：按人群与身体数据算出每日热量/蛋白质/碳水/脂肪目标区间，口径注明膳食指南来源。 | `/lhg-meal-plan:meal-calc 减脂 70kg 175cm 30岁 久坐` |
| `/lhg-meal-plan:meal-plan` | 营养食谱一键生成：目标人群画像→营养素测算→一周食谱→采购清单，全程带"非医疗建议"免责声明。 | `/lhg-meal-plan:meal-plan "减脂，70kg，不吃香菜" --days 7` |

## 什么时候用 / 什么时候不用（FAQ）

**什么时候用：**

- 你需要食谱自检时 → 用 `/lhg-meal-plan:meal-audit`
- 你需要营养素测算时 → 用 `/lhg-meal-plan:meal-calc`
- 你需要营养食谱一键生成时 → 用 `/lhg-meal-plan:meal-plan`

**什么时候不用：**

- 你只需要其中一个零散能力时 → 本插件是成套流程，单点需求用更轻量的 skill 更合适
- 你希望 AI 完全自由发挥、不接受任何自查与硬门时 → 它的规则审计与 hooks 会介入（可关，但那就别装它）
- 你的场景不在上面命令表覆盖范围内时 → 先看命令表，没有对应命令就别硬套

## 目录结构

```
lhg-meal-plan/
├── smoke_test.py          # 一键冒烟测试
├── ATTRIBUTION.md         # 灵感来源与许可声明
├── LICENSE                # MIT
├── README.md              # 本文件
├── .claude-plugin/
├── agents/
├── assets/
├── commands/
├── fixtures/
├── hooks/
├── scripts/
├── skills/
```

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（本次实测 56 项全部通过）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-meal-plan/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

同门插件见 [lhg-plugs](https://github.com/lhg-plugs)，86 个插件的完整矩阵在 [marketplace](https://github.com/lhg-plugs/marketplace) 维护。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 抖音：搜「刘老师讲AI实战」
- 微信：lhgsmsw
