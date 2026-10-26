> **⚠️ 免责声明：本插件输出仅供一般性膳食参考，非医疗建议。慢病/备孕人群请遵医嘱；如有食物过敏，请自行剔除相关食材；营养素目标区间的口径来源见 meta.json 的 source 字段。**

<!-- About 简介（推送后填写到仓库 About 栏）：
营养食谱专家：一周食谱与采购清单一键生成 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-meal-plan
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, nutrition, meal-planning -->

# lhg-meal-plan：营养食谱专家

> **一句话介绍**：一周食谱与采购清单一键生成——目标人群画像（减脂/增肌/备孕/慢病）→ 三大营养素脚本化测算 → 一周食谱编排 → 分类采购清单，31 条确定性规则 5 秒自检。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-meal-plan
> /plugin install lhg-meal-plan@lhg-plugs
> ```

**免责声明（再说一遍）**：本插件不是医疗建议。慢病/备孕人群请遵医嘱；过敏原信息由你亲口确认，插件只做"申报过敏原全周零出现"的机器检查，不承担医学判断。

## 它是什么

`lhg-meal-plan` 是一个 Claude Code 插件（plugin 为主、skill 为辅），专为"想吃得健康但不想研究营养学"的人设计：

- **3 个命令**（小白入口）：`meal-plan` 一周食谱一键生成（画像→测算→食谱→采购清单）→ `meal-calc` 营养素测算（公式与来源全展示）→ `meal-audit` 食谱自检
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：人群画像、营养素测算、一周食谱编排、食谱自检流程
- **3 个专家 agent**：营养师、食谱主厨、独立安全评审
- **1 个硬门 hook**：保存食谱文件前自动检查"非医疗建议"免责声明，缺失则拦截（可一键豁免，不骚扰）
- **31 条确定性自查规则**：营养素 vs 目标区间偏差、过敏原/人群禁忌食材、食谱多样性、采购清单与食谱对应，纯 Python、零第三方依赖，5 秒出结果

工作流：`meal-plan`（画像→测算→食谱→清单）→ `meal-audit`（查一遍），也可以单独用 `meal-calc` 只算营养素目标。

## 3 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-meal-plan:meal-plan` | 一周食谱一键生成：人群画像→营养素测算→食谱→采购清单→自检 | `/lhg-meal-plan:meal-plan "减脂，70kg，不吃香菜" --days 7` |
| `/lhg-meal-plan:meal-calc` | 营养素测算：公式全展示，输出目标区间 + 来源 | `/lhg-meal-plan:meal-calc 减脂 70kg 175cm 30岁 久坐` |
| `/lhg-meal-plan:meal-audit` | 食谱自检（脚本 + 人工评审清单） | `/lhg-meal-plan:meal-audit ./delivery/` |

## 自查说明

自查 = 确定性脚本（机器）+ 人工评审清单（人）：

1. 先跑 `scripts/audit/meal_audit.py`（31 条规则：营养素 8、过敏原 1、人群禁忌 7、多样性 4、采购清单 5、免责声明 2、来源 2、份量 2），零 AI 成本；
2. 发现分三级：**blocker**（必须修：过敏原命中、备孕/慢病禁忌、热量/蛋白低于下限、缺免责声明；保存食谱时 hook 会拦截缺声明的文件）、**warning**（修或写豁免理由）、**nit**（顺手修）；
3. 再按 `lhg-mp-audit` skill 的评审清单过一遍脚本抓不到的（食材买得到吗、做法会吗、连续吃 7 天会腻吗）。

blocker 清零才算做完；为清零改规则算作弊，不许。

## 目录结构

```
lhg-meal-plan/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 3 个命令：meal-plan / meal-calc / meal-audit
├── skills/                  # 4 个平台中立 skill（人群画像/营养素测算/食谱编排/自检流程）
├── agents/                  # 3 个专家 agent（nutritionist / menu-chef / safety-reviewer）
├── hooks/                   # 1 个硬门（食谱免责声明检查）+ 豁免说明
├── scripts/audit/           # 31 条确定性自查规则（零第三方依赖）
├── fixtures/                # 冒烟测试用例（坏/好对照）
├── smoke_test.py            # 一键冒烟测试
├── ATTRIBUTION.md           # 灵感来源与许可声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**什么时候用：**

- 你想减脂/增肌，但不知道"每天吃多少、怎么吃"时 → 用 `/lhg-meal-plan:meal-plan`，一句话出一周食谱
- 你拿到一份网红食谱，想验算它靠不靠谱时 → `meal-calc` 算出你的目标区间，再跑 `meal-audit` 验那份食谱
- 你要给家人（备孕/慢病）做饭，想避开禁忌时 → 人群画像 + 禁忌检查开箱即用（但务必先看"什么时候不用"第三条）
- 你想给健身餐工作室立一套"出餐前必须过自检"的纪律时 → 它的 hook 硬门与审计脚本开箱即用

**什么时候不用：**

- 你有确诊的慢病（糖尿病、高血压、肾病等）且医生给了具体的饮食医嘱 → **听医生的**，本插件的一般性食谱不能替代医嘱；如需使用，请拿着食谱去问医生
- 你需要的是"治疗方案"（如靠食谱降血糖、备孕调理）→ 本插件不做任何疗效承诺，请咨询医生或注册营养师
- 你是运动员备赛、术后恢复等特殊人群 → 超出本插件四类人群范围，建议咨询专业人士

**风险点诚实说明：**

- **营养素目标区间是"参考"不是"处方"**：口径来自公开膳食指南（见 meta.json source 字段），个体差异请咨询专业人士
- **过敏原靠你申报**：插件只检查"你申报的过敏原"是否出现；你没申报的，插件查不出来——申报时请认真
- **禁忌食材表是启发式**：31 条规则里的备孕/慢病禁忌表是自建常用表，会持续扩充但不可能穷尽；拿不准的食材请咨询医生
- **食谱多样性 ≠ 营养全面**：微量营养素（维生素/矿物质）本插件只做"蔬菜种类"代理检查，不做精确测算

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-video-edit](https://github.com/lhg-plugs/lhg-video-edit) | 一句话把口播素材剪成爆款短视频（+口播脚本子命令） | `/plugin install lhg-video-edit@lhg-plugs` |
| [lhg-fullstack](https://github.com/lhg-plugs/lhg-fullstack) | 小白一句话 → 高质量全栈应用 | `/plugin install lhg-fullstack@lhg-plugs` |
| [lhg-study-abroad](https://github.com/lhg-plugs/lhg-study-abroad) | 留学文书专家：PS 与推荐信的结构化写作 | `/plugin install lhg-study-abroad@lhg-plugs` |
| [lhg-meal-plan](https://github.com/lhg-plugs/lhg-meal-plan) | 营养食谱专家：一周食谱与采购清单一键生成 | `/plugin install lhg-meal-plan@lhg-plugs` |

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、31 条规则、fixtures 命中、hooks 行为）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-meal-plan/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 抖音：搜「刘老师讲AI实战」
- 微信：lhgsmsw
