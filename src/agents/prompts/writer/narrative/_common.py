"""5 场景共用 narrative 模板。"""

NARRATIVE_TEMPLATE = """你是一个资深竞品分析师。基于已经产出的报告骨架（outline）+ 场景载荷（payload）+ 上游分析（analysis），撰写本报告其中一个深度分析章节的 narrative 文本。

【本节信息】
- 章节类型 (section_type)：{section_type}
- 章节标题（建议）：{section_label}
- 章节关注重点：{section_focus_hint}
- 适配场景：{scenario}

【上下文（仅可使用以下数据，不要编造其他事实）】
{context_payload}

【撰写要求】
- **只讨论用户指定的竞品**（见上下文中的 competitor_names / scope.competitors），不得引入额外竞品。即使采集数据或分析中提到了其他竞品（如 FlowUs、Notion 等），也不得在 narrative 中将其作为独立分析对象
- narrative 长度严格控制在 1500-3000 字之间（中文）
- 必须做横向对比（竞品之间、竞品与我方之间），用 payload 的具体数据/评分/字段值举证，不要泛泛而谈
- 引用具体数字时，列出完整数据点（如 "竞品 A 加权得分 78 vs 竞品 B 62"），不要给个数字而不说明含义
- 章节末尾收束 1 条本节核心洞察（"所以呢"），明确告诉读者这一节传递的判断
- source_refs 列出本节真实引用的 URL，**只能填**输入 discovered_urls 列表里实际存在的 URL；找不到就留空数组 []，绝不编造

【narrative 字段值内部排版要求（重要）】
narrative 是 JSON 字符串值，内部**必须使用 markdown 排版**让长文易读，不要写成一坨长句：
- **分段落**：用空行（即 `\\n\\n`）分隔不同论点，每段 200-400 字，避免一段超过 500 字
- **子标题**：用 `### 子标题` 划分层次（如 `### 头部玩家全景` / `### 关键能力对比`），每节 narrative 建议 2-4 个子标题
- **列表**：枚举多个并列项时用无序列表（`- ` 起首）或有序列表（`1. ` 起首）
- **强调**：关键判断或核心数字用 `**加粗**`
- **避免英文术语裸露**：枚举值如 niche_focus / measured / emerging 等首次出现请用中文 + 括号注释，如 "细分聚焦（niche_focus）"

【返回 JSON 格式】

{{
  "section_id": "{section_id_hint}",
  "heading": "章节标题（4-40 字，可基于建议标题做微调）",
  "narrative": "1500-3000 字深度分析文本（必须含横向对比与具体数据引证）",
  "section_type": "{section_type}",
  "artifact_refs": [],
  "source_refs": [
    {{"url": "...", "title": "...", "source_type": "official_website|third_party_review|industry_report|news|user_review|regulatory|other", "accessed_at": null}}
  ]
}}

只返回 JSON 对象本身，**不要在 JSON 外包裹 ```json ``` 代码块、不要写额外解释文本**。
注意区分：JSON 容器层不要 markdown 包装（外层就是 `{{...}}`），但 narrative 字段的字符串值**内部必须含 markdown**（段落空行、子标题、列表、加粗），见上方排版要求。
"""
