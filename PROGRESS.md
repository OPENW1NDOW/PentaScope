# Project Progress

AI 驱动的竞品分析 Agent 协作系统 — 项目进度日志。

> 每次结束工作前更新，下次在另一台电脑开 Claude 时先读此文件。

## Format

```markdown
## YYYY-MM-DD
- 完成：...
- 进行中：...
- 下一步：...
- 阻塞：...（可选）
```

---

## 2026-06-08（深夜 / v3 spec 实施 D-G 全部完成）
- 完成（单 session 单线推进，~10+ commit）：
  - **阶段 1（A1-A6 master 适配）**：LLMClient.call_json 加 max_tokens / config 加 WRITER_MAX_LLM_CALLS=18 + WRITER_NARRATIVE_CONCURRENCY=3 / state.py 改 BaseReport + ScenarioInput / writer.py 改桩 / inspector.py 仅修 import
  - **阶段 2（B1-B5 prompts + normalizers）**：prompts 目录搬迁（保留旧 import 兼容）/ 5 套 outline + 5 套 payload / narrative 模板 + 28 项 SECTION_CONTEXT_MAP / 5 套 normalizers v3 R-14/R-15 升级
  - **阶段 3（C1-C6 WriterOrchestrator）**：1029 行 4 阶段编排（outline / payload / narrative / assemble），含 Phase 1 Pydantic 失败重试、Phase 2 build_payload_model + S4 prior diff 注入、Phase 3 asyncio.Semaphore 并发 + 半数硬闸门、Phase 4 9 步组装 + URL 双通道收集；LLM quota 熝断 + placeholder 兜底；21 单测全绿
  - **阶段 4（D1-D4 graph 接通）**：D1 RecommenderAgent + 3 单测；D2 ai_pick_scenario + 4 单测；D3 builder.py 全面改造（recommender_node / scenario 路由 / writer_node 接 WriterOrchestrator / 异常路由 / S4 prior 读盘 + 路径穿越校验）+ 21 单测；D3 code review 后修 3 Critical（C1 自定义异常类替代字符串子串匹配 / C2 移除 recommender 重复 merge / 新 Critical 路径穿越白名单）；D4 前端 scenario_picker 接通 + AI 帮我选场景按钮
  - **阶段 5（E1-E3 inspector 重写）**：E1 quality_score.py 三项加权（source_coverage / confidence_avg / inspector_pass_rate，缺值降权重新归一化）+ 17 单测；E2 inspector.py 重写为 _check_common + _check_s1..s5 dispatcher，dispatcher 通过 globals() 间接查找便于测试 monkeypatch + 25 单测；E3 _check_warnings_prefix + quality_score cap 0.5（v3-R17 placeholder warnings 强制降分）+ 5 单测
  - **阶段 6（F1-F3 前端渲染）**：F1 BaseReport 通用部分渲染（at_a_glance / executive_summary 5 段 / methodology / key_findings / analysis_sections / swot / recommendations 按 timeline / appendix / metadata 含 quality_score 可视化）拆出 src/frontend/render.py；F2 5 场景 payload 渲染（vendor_profiles / market_sizing / packaging / battlecards / perceptual_map 等关键结构表格化）；F3 Plotly 图表（S1 5 维雷达 / S2 五力蜘蛛网 / S5 Perceptual Map + Magic Quadrant + Strategy Canvas）；新依赖 plotly>=5.20.0；42 单测全绿
  - **阶段 7（G1 E2E 集成测试）**：5 场景 E2E 跑通 graph 真编排（mock 5 agent 方法 + 真 BaseReport fixture），验证节点访问顺序 + scenario 路由 + 终态合法 + quality_score 真接通；6 单测全绿（重写旧 skip 桩 test_graph.py）
  - **测试现状**：311 passed / 5 skipped / 2 xfailed；ruff clean；新增 ~135 单测（E1 17 + E2 25 + E3 5 + F1 17 + F2 17 + F3 8 + D4 0 + G1 6 + 其他）
- 进行中：阶段 7 G2 手动验收 + 文档收尾
- 下一步：
  1. Cooper 手动验收清单（见下）
  2. 提交完整改动 + push origin master
  3. 准备答辩材料（PRD / DECISIONS / 评分项实现映射）
- 阻塞：无
- 协作模型实证：subagent-driven-development 流程在阶段 3 抓到多个隐藏 bug（C1 异常路由脆弱 / C3 phase 2 缺重试 / C-new 路径穿越）；后期 D4-G1 改用直接动手（中等任务无需 subagent 开销），D3 修复 implementer 单次 49 分钟教训记下，复杂任务拆小后再派
- 安全提醒：本次纯代码实现，无 key 引入

### 手动验收清单（Cooper 跑）
1. 启动后端 + 前端：
   - `uvicorn src.api.main:app --reload`
   - `streamlit run src/frontend/app.py`（另一终端）
2. **场景路由验收**（5 场景各试一次）：
   - S1 功能迭代：填我方产品名 + 2 个竞品名 + 分析意图 → 应直跳 collector 不经过 recommender
   - S2 市场进入：仅填行业名 → 应先经过 recommender 推荐 Top 3-5 玩家
   - S3 / S4 / S5：参考前端表单提示填字段
3. **AI 帮我选场景**：填分析意图 → 点 "AI 帮我选场景"按钮 → 验证返回的 scenario + 置信度 emoji + rationale
4. **报告渲染验收**（任一场景跑完后）：
   - 通用部分：at_a_glance / 执行摘要 5 段 / 方法论 / 关键发现 / 分析章节 / SWOT / 行动建议按 timeline 分组
   - 场景专属：S1 雷达图 + 功能矩阵 / S2 五力蜘蛛网 + TAM/SAM/SOM 三 metric / S3 GBB 套餐卡片 / S4 5 类 changes 表 + 战卡 / S5 MQ + Perceptual Map + Strategy Canvas 折线
   - 元数据面板：quality_score 显示 + warnings 列表
5. **追溯面板**：填 trace_id → 验证 4 阶段产物 + run.log 可见
6. **错误路径**：尝试 prior_trace_id 含 `..` → 应被路径穿越白名单拒绝（log warning，不崩）

---

## 2026-06-08（晚 / v3 spec）（双轮 doubt-driven 复审 v2 → v3 spec 落盘）
- 完成（单 session 单线，第二轮 doubt-driven）：
  - **重新跑 doubt-driven 复审 v2 spec**（接手备忘里 v2 复查的 14 条只有标题摘要，原审查记录已随 worktree B 丢失，按 Cooper 决策"退后一步重审"）：
    - 单模型 Explore agent 自审：18 条（8 critical + 7 major + 3 minor），现场翻 master 代码核实
    - 跨模型 Codex (azure_openai/gpt-5.5) 复审：22 条（10 critical + 10 major + 2 minor），独立审查
    - 合并去重得 **28 条 reconciled**（11 critical + 12 major + 5 minor）
  - **关键跨模型独占发现**：Codex 抓到的 `CompetitorProfile.source_urls` 字段**根本不存在**（v2 spec 全文 4-5 处用错），Explore agent 漏掉。这条贯穿 phase 1/2/4，验证了双轮 doubt-driven 价值
  - **Cooper 拍板的 6 个产品决策**（其余 22 条为技术对错由 Claude 处理）：
    - R-02 writer raise 路径：c (writer 内部 raise → builder 外层 try/except → 注入 RejectionFeedback → inspector should_continue 路由)
    - R-05 熔断阈值：a (调到 18，1 个安全荧丝)
    - R-14 S3/S4 source_refs min=1 冲突：a (无来源则不生成该条目，prompt + normalizer 双防护)
    - R-19 scope.competitors S2：a (union 全部，去重 by name，用户在前)
    - R-21 outline 字段约束：a (保持单次调用，prompt 补全所有必填字段)
    - R-22 confidence_level vs quality_score：a (不交叉限制，仅文档加语义说明)
  - **v3 spec 落盘**：`docs/superpowers/specs/2026-06-08-task20-21-writer-orchestrator-design.md` 从 v2 433 行扩到 v3 1014 行，含 83 处 `[v3-RXX]` 修订标记 + 完整 v3 修订日志表
  - **v3 新增章节**：「Pre-flight: master 适配」明确写出 5 个 master 适配前置任务（Task 21.0a-e），动 writer_orchestrator 之前必须先把这些做完否则接通不了 graph
  - **测试用例从 13 → 16**（v3 加 3 个）：phase 2 S2 recommender 强制覆盖 / phase 2 S4 prior diff 前置注入 / builder.writer_node 异常路由
- 进行中：v3 spec 已落盘，等 commit + push
- 下一步：
  1. v3 spec commit + push origin master
  2. Task 20.0 LLMClient.call_json 加 max_tokens 参数
  3. Task 20.1 prompts 目录搬迁（保留旧 WRITER_SYSTEM 兼容）
  4. Task 20.2-20.4 5 套 prompt（outline / payload / narrative）
  5. Task 21.0a-e master 适配前置（builder writer_node 异常路由 / state.py 修 import / config 加 WRITER_MAX_LLM_CALLS / normalizer 5 套升级）
  6. Task 21.1-21.6 WriterOrchestrator 主体 + 16 单测
- 阻塞：无
- 安全提醒：本次纯设计文档修订，无 key 引入

---

## 2026-06-07（晚）（A+B+C 公共层落地：BaseReport + 5 场景 payload + ScenarioInput）
- 完成（30 task plan 中 14 个 task / 4 commit / worktree-scenario-foundation 分支已合 master）：
  - **A 大类**（Task 1-5，commit 77ce4ca）：建立 BaseReport 通用骨架 + 公共 schema
    - `src/schemas/common.py` 新建 — SourceRef / DataSource / ArtifactBase / Revision / Author / Exhibit
    - `src/schemas/report.py` 重写 — ExecutiveSummary 5 段式（替代旧 4 段）/ ReportScope / Methodology（min 200 字）/ Finding / AnalysisSection（28 个 section_type Literal 枚举）/ Recommendation / Swot / SwotEntry / Appendix / ReportMetadata（含 quality_score Optional 区分"未质检"与"质检 0 分"）
    - `src/schemas/analysis.py` 删 SwotEntry/Swot/RadarScore/RadarDimensions/FeatureMatrixEntry，Swot 改从 report import 复用，feature_matrix/radar_scores 暂用 list[dict] 占位
    - `src/schemas/__init__.py` 废除 FinalReport 等旧类暴露
    - 6 个旧测试文件（test_writer/inspector/schemas/api/graph/trace_api）module-level skip，待 D-G 重写；analyzer 2 测试 xfail
  - **B 大类**（Task 6-11，commit b30cfd7，+1905 行）：5 场景 payload + BaseReport union 接通
    - `src/schemas/scenarios/s1.py` — S1 FeatureIterationPayload（vendor_profiles + feature_matrix 加权评分 computed_field + 5 维雷达 + JTBD JobStatement + roadmap），含 `_check_competitor_consistency` validator（vendor / radar / matrix 竞品名一致）
    - `src/schemas/scenarios/s2.py` — S2 MarketEntryPayload（TAM/SAM/SOM 含 value_basis 防幻觉 + Five Forces 三档枚举 + MarketPlayer 单一 source of truth + entry_strategy + recommender 产出 CompetitorRecommendations + PESTEL 默认 None）
    - `src/schemas/scenarios/s3.py` — S3 PricingStrategyPayload（GBB packaging 强制 ==1 个 is_recommended + position_uniqueness + ObservedCompetitorTier 每条 source_refs 必填防价格幻觉 + WTP proxy 强制 confidence=low + RecommendedPriceTier annual ≤ monthly×12 + PricingPageAudit 8 法则 + computed overall_score_pct）
    - `src/schemas/scenarios/s4.py` — S4 MonitoringPayload（review_period 含 prior_trace_id + FIATuple fact 必填 / impact+act Optional + 5 类 _BaseChange + ArtifactBase 多继承 + MonitoringThreat computed quadrant + 活体 Battlecard），含 `_check_monitored_competitor_consistency` 与 `_check_first_review_baseline`（首次监控全 is_baseline=True + trends 全 None）
    - `src/schemas/scenarios/s5.py` — S5 PositioningPayload（MQ 二轴评分 + computed mq_quadrant + Perceptual Map 含 confidence/score_rationale 必填 + display_watermark + Strategy Canvas factor key 完整性校验 + ERRC raise_level 改名 + Positioning Statement 含 confidence 必填 + computed full_statement_text 带 [AI 推断版本] 水印）
    - `src/schemas/report.py` 接通 BaseReport scenario_payload Annotated discriminated union（discriminator='scenario_type'）+ scenario computed_field + `_check_scenario_consistency`（强制 metadata.scenario == scenario_payload.scenario_type）
  - **C 大类**（Task 12-14，commit b412b0b）：ScenarioInput + 前端按场景切表单
    - `src/schemas/input.py` ScenarioInput 替代 CompetitorInput（按 scenario 分支校验：S2 必有 industry，其他场景必有 competitors + our_product_name）；CompetitorInput 保留为别名兼容
    - `src/api/schemas.py` AnalysisRequest 改为承载 ScenarioInput 字段，含 to_scenario_input()
    - `src/api/routes.py` 改用 request.to_scenario_input()，meta 落盘扩展输入字段（scenario / industry / our_product_name / prior_trace_id）
    - `src/frontend/app.py` 输入区按 scenario 切表单（S2 行业必填 + 选填竞品；其他场景必填竞品 + 我方产品；S4 加 prior_trace_id 选填），按场景做客户端校验
  - **plan 修订**（commit 70bd8cc）：扫 spec 发现 plan 与 spec 3 处不一致并修
    - Task 7 imports 补 PESTELFactor
    - Task 7 测试 fixture 删 MarketSizing.methodology（spec MarketSizing 无该字段）
    - Task 9 描述：S4 顶层 model_validator 数量 3→2（spec 只有竞品名一致性 + 首次 baseline，无"跨期变化"）
  - **测试**：50 个新 schema 单测全绿（common 7 + base_report 12 + s1-s5 各 6-7 + input 6）；总 145 passed / 6 skipped (旧测试过渡 skip) / 2 xfailed (analyzer fixture) / 0 failed；ruff 全过
  - **合并 master**：worktree-scenario-foundation 分支 fast-forward 到 master（fcd21eb → b412b0b，4 commit 线性历史），push origin master 完成；远程 worktree 分支已 push 留存
  - **后续 worktree rebase**：scenario-schemas-graph 与 scenario-writer-frontend 两个 worktree 已 rebase 到 master，HEAD 都在 b412b0b，可基于此跑 D-G
- 进行中：无（session1 任务结束）
- 下一步：开 D+F session 跑 D 大类 graph 改造（recommender 节点 + scenario 路由 + AnalysisState 加场景字段）+ F 大类 inspector 按 scenario 分支硬查；并行开 E+G session 跑 E 大类 writer 4 阶段编排 + G 大类前端 5 场景渲染分支
- 阻塞：无

---


## 2026-06-07（弃用 SerpAPI：搜索源单 provider 化）
- 完成（worktree-drop-serpapi 分支，9 commits 含 spec+plan）：
  - 走 brainstorming → doubt-driven 单模型 17 条 + 跨模型 Codex 20 条审查 → RECONCILE 9 actionable + 3 产品决策（PD-1 不补 soft-404 测试、PD-2 6-8 commit、PD-3 2.5-3.5h）→ writing-plans → executing-plans
  - 删除 SerpApiSource 类（28 行）+ SEARCH_API_KEY/SEARCH_PROVIDER/PICK_LLM_TIMEOUT/MAX_FETCH_CONCURRENCY/_provider_env 5 个配置 + collection_pipeline 的 _llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法（共 ~115 行生产代码）+ 构造器塌缩为单 search_source 参数
  - conftest 锁 provider 的 fixture 改名 shield_local_env（屏蔽本地 .env 的 TAVILY_API_KEY 污染）
  - 集成测试改造：fixture 加 TAVILY_API_KEY="K"、LLM mock 序列删 _llm_pick 步、mock_http 替换 get_json 为 post_json、删过时的 SEARCH_PROVIDER monkeypatch
  - 单测改造：test_sources.py 删 6 个 test_serpapi_*；test_collection_pipeline.py 删 12 个 SerpAPI 路径专项测试，重写为 5 个 Tavily 路径测试；test_config.py 删 SEARCH_API_KEY/SEARCH_PROVIDER 断言；test_http_client.py 数据 URL 通用化
  - .env.example 补 TAVILY_API_KEY；CLAUDE.md 同步 3 处架构描述
  - **125 测试通过**（从 139 减 14：删 6 SerpAPI source + 简化 12 pipeline + 删 1 SEARCH_PROVIDER + 改 reconciled 已计入）；**ruff 全清**；集成测试 11/11 全过
- 进行中：worktree-drop-serpapi 合并回 master
- 下一步：接主战场 30 task 分场景报告（worktree-A scenario-reports）
- 阻塞：无
- 安全提醒：无（本次重构仅删代码、不引入新 key）

## 2026-06-07（分场景输出报告：5 套场景 schema 设计 + 双模型 doubt-driven 审查）
- 完成（设计阶段，未写代码）：
  - **场景拆分**：从原"通用 4 Agent 报告"改为按使用目的拆 5 场景：S1 功能迭代 / S2 市场进入 / S3 定价策略 / S4 持续监控 / S5 战略定位。Cooper 选 5 场景全做（选项 A）
  - **架构决策**：R2（BaseReport 通用骨架 + scenario discriminated union），不是 R1 的 5 套独立 schema。理由：调研显示 13 通用元素是 5/5 咨询机构（McKinsey/BCG/Bain/Gartner/Forrester）共识
  - **前置研究**：4 个并行 agent 调研（S1+S5 / S2+S3 / S4 / 通用骨架），落盘 `docs/superpowers/research/2026-06-07-report-templates-research.md`（约 600 行，覆盖 Forrester Wave/Gartner MQ/McKinsey 行业报告/CB Insights/Simon-Kucher/OSCOM/IndustryLens 标杆 + 9 个业界框架）
  - **设计文档**：`docs/superpowers/specs/2026-06-07-scenario-schemas-design.md`（约 1100 行，11 Part）
  - **第 1 批 doubt-driven 双模型审查（BaseReport + S1 + S2）**：单模型 + codex(gpt-5.5) 跨模型对抗审查，合并去重 19 条问题。Cooper 拍板 12 条产品决策（含 SWOT 5 场景全保留 / 雷达 S1+S5 都保留 / S2 Top 5 / 删 BattleCard / 章节数 5-6 / timeline+priority 双字段 / JTBD 简化只留 JobStatement / Methodology 1000+ 字 / PESTEL 留结构 + Optional / competitive_alternatives 推迟 / consumer_segments Optional / 报告字数 7000-8000）
  - **第 2 批 doubt-driven 双模型审查（S3 + S4 + S5）**：合并去重 22 条问题。Cooper 拍板 5 条产品决策：
    - 13a：S4 prior_trace_id 保留 + 首次降级模式（schema_version 字段 + writer 校验 prior 报告 scenario）
    - 14a+d：S5 PerceptualMap 加 confidence + score_rationale 必填 + display_watermark
    - 15a：S3 ObservedCompetitorTier 每条 source_refs 必填（防价格幻觉）
    - 16b：S5 简化版 MQ 二轴总分（execute_score + vision_score + computed mq_quadrant），不拆 15 子项
    - 17a：S4 FIATuple fact 必填，impact + act Optional（防弱信号编造行动）
  - **关键技术修复**（doubt-driven 暴露的真实问题）：
    - discriminator 字段三处不一致 → BaseReport.scenario 改 computed_field 派生 + model_validator 校验
    - 旧 schema 废除清单缺失 → Part 0 显式列出 FinalReport/SwotEntry/RadarScore 等去向
    - S2 必填字段成幻觉发动机 → MarketValue 加 amount Optional + value_basis + currency + unit + year + geography
    - 跨场景 leader/challenger 语义碰撞 → 加场景前缀 wave_position(S1) / mq_quadrant(S5) / market_role(S2)
    - evidence_url 软强制 → score=2 必填 evidence_url、ObservedCompetitorTier 每条 source_refs 必填
    - S5 model_validator bug（map_names 重复 union 自身 + canvas_names 未用 + is_self 未约束唯一）→ 整段重写
    - S5 ERRCGrid raise_ alias 序列化坑 → 改名 raise_level
    - writer 单次 LLM 4-5K 字 vs 报告 7-8K 字目标 → Part 6 写 4 阶段编排方案（骨架→payload→narrative→合并，~8 次 LLM 调用）
    - AnalysisSection.section_type 漏列 S3/S4/S5 → 补 15 个枚举值
  - **协作模型固化**：Cooper（产品 PM）+ 我（研发负责人）。技术约束我承担，产品决策 Cooper 拍板，冲突时分 4 类处理（完全放弃/部分放弃/换思路/推迟）
- 进行中：本 session 已调 writing-plans skill 出 task list（设计阶段终止）；本 session 顺手把 worktree 方案从「项目自管 .worktrees/」迁移到「Claude Code 原生 worktree 模式」，加 .worktreeinclude 让新 worktree 自动带 .env，PROGRESS 同步更新启动指引
- 下一步（**新 session 开发阶段**，Cooper 拍板用 Claude Code 原生 worktree 并行 2 session）：

  ### 新 session 启动指引
  1. **必读**（顺序）：
     - PROGRESS.md 06-07 段（本段，了解协作模型 + 决策汇总）
     - DECISIONS.md 06-07 章节（理解 R2 架构 / computed_field 派生 / 5 场景共骨架等关键决策）
     - `docs/superpowers/specs/2026-06-07-scenario-schemas-design.md` Part 5 + Part 10 评审记录（看双模型审过的 41 条问题处理记录）
     - `docs/superpowers/plans/2026-06-07-*.md` task list（writing-plans skill 产出的实现计划）
  2. **跳读**（按需）：
     - 设计文档 Part 1（BaseReport）/ Part 2-3（S1+S2）/ Part 7-9（S3+S4+S5）—— 写哪块代码看哪块
     - `docs/superpowers/research/2026-06-07-report-templates-research.md` —— 写 prompt 时参考业界框架细节
  3. **执行（Claude Code 原生 worktree 模式）**：
     - **不要再手动 `git worktree add`**。改用 Claude Code 内置：每个 worktree 落在 `.claude/worktrees/<name>/`，分支自动叫 `worktree-<name>`，从 `origin/HEAD` 起步（干净状态）；`.claude/` 已整体进 .gitignore，无需额外忽略
     - 启动方式（两个独立终端各跑一条）：
       - 终端 1：`claude --worktree scenario-schemas-graph`
       - 终端 2：`claude --worktree scenario-writer-frontend`
     - `.worktreeinclude` 已加 `.env`，新 worktree 自动复制（无需手动 cp）
     - 按 task list 分大类并行：worktree A（Schema+Graph） / worktree B（Writer+前端）
     - 每个大类完成时跑测试 + commit（Cooper 决策 Q3=b）
     - 退出 session 时按 keep（保留下次回来）/ remove（连未提交改动一起丢）选择；Cooper 一般选 keep 直到合回 master 后再 remove

  ### 关键约束（写代码前必读）
  - **协作模型**：Cooper 是产品 PM 决定做什么，Claude 是研发评估技术可行；冲突时分 4 类处理（完全放弃/部分放弃/换思路/推迟），不擅自决策
  - **R2 架构**：BaseReport + scenario discriminated union（不是 5 套独立 schema）
  - **computed_field 派生**：weighted_scores / wave_position / mq_quadrant / quadrant / overall_score_pct / last_updated_at / full_statement_text / scenario / weight / overall_score_pct 全部 LLM 不填，代码计算
  - **场景前缀枚举**：永远不出现裸 leader/challenger（用 wave_leader/mq_leader/market_challenger）
  - **source_refs 协议**：禁止 source_urls/sources/evidence_url 命名分歧（除 FeatureScore.evidence_url 因特殊语义保留）
  - **writer 4 阶段编排**（Part 6）：单次 LLM 4-5K 字 → 拆 8 次调用产 7-8K 字。失败局部重试，结构由代码透传
  - **一步到位废除旧 schema**（无渐进过渡）：废除 FinalReport/ActionItem(s)/旧 ExecutiveSummary 4 段；前端按 metadata.schema_version 分支
- 阻塞：无
- 安全提醒：本 session 未涉及 API key

## 2026-06-06（采集能力增强：接 Tavily 搜索源 + 移除 iTunes 同名污染源）
- 完成（feat/collector-enhancement 分支，14 commits，三环境 139 测试全绿 + ruff 全清）：
  - **采集配置增强**：P1 超时 20→45s、SEARCH_TOP_N 3→5、新增 SEARCH_PROVIDER/TAVILY_API_KEY 配置
  - **http get 故障分类重试**：超时/5xx 重试 1 次、4xx 直接弃
  - **候选池递补**：抓挂才补、上限=picked 数（尊重 LLM 选页，不硬凑）+ SerpAPI num 20
  - **新增 TavilySource**：一次调用返回结果+清洗正文，吃掉搜索+选页+抓取+清洗；collect 按 returns_bodies 分叉 tavily 主线，builder 按 SEARCH_PROVIDER 注入；Tavily max_results 联动 SEARCH_TOP_N
  - **修 Tavily 401**：改用 POST + JSON body + Authorization: Bearer header（官方契约），新增 HttpClient.post_json
  - **修集成测试 .env 污染**：conftest autouse fixture 锁定 SEARCH_PROVIDER=serpapi，不受本地 .env 影响
  - **移除 iTunes 专源**：实测同名污染（搜飞书带出豆包/千问，搜语雀带出 flomo/石墨），无差别并入语料污染分析；独家价值仅剩评分、不值得背污染风险，删干净（连带 category 路由），集成测试改走 SerpAPI 主线
  - 真实端到端验收（语雀 vs 飞书，SEARCH_PROVIDER=tavily）：Tavily 生效（飞书抓 4 条官方页）、completeness 语雀 1.0/飞书 0.85、报告 5 section/quality 0.9
  - 设计 spec `docs/superpowers/specs/2026-06-06-collector-enhancement-design.md`、计划 `docs/superpowers/plans/2026-06-06-collector-enhancement.md`
- 进行中：feat/collector-enhancement 合并回 master（本 session 收尾中）
- 下一步（新 session，承接 06-04 未尽事项）：
  1. **前端输入优化**：让用户填竞品官网 URL/已知信息/指定数据源，减少盲搜依赖
  2. **溯源粒度增强**：维度+竞品级 → per-entry（需改 analysis schema 结构）
  3. 验收暴露的 analyzer/writer 质量项（独立于采集）：溯源张冠李戴（给数据配错来源链接）、雷达图缺我方产品评分、用户评价样本说明缺失
- 阻塞：无

## 2026-06-04（报告质量提升：方案C 溯源为脉，加工层全链路改造）
- 完成：
  - 走完整 brainstorming → 两轮 doubt-driven（单模型 general-purpose + Codex gpt-5.5 跨模型对抗审查，**20 条命中**证伪原方案前提）→ writing-plans → subagent-driven（每 Task 派 implementer + spec/quality 两阶段 review）
  - 设计文档 `docs/superpowers/specs/2026-06-04-report-quality-design.md`、实现计划 `docs/superpowers/plans/2026-06-04-report-quality.md`
  - **关键认知翻转**：原以为「报告溯源断链只需改 writer 做机械下沉」，doubt-driven 核对源码后证伪——根因在**采集层**（collector 抽取 prompt 只给 sample_reviews 留 source_url、正文 merge 成无【来源】锚点 blob、analyzer prompt 无 source_urls 输出槽），不碰采集层修不了「每条结论可溯源」。重排为「事实-URL 绑定链」贯穿全链路
  - 9 个 Task 全部实现（feat/report-quality 分支，136 测试全绿 + ruff 全清，16 commits）：
    - pipeline 输出带【来源:url】标记的 labeled_text；collector 抽取时绑定每条 fact 的 source_url
    - analyzer 补各维度 source_urls 输出槽 + 代码兜底回填（维度+竞品级）
    - writer 机械透传 SWOT/雷达/功能矩阵（100% 不丢，不赌 LLM）+ 按 dimension 下沉 source_refs + 过滤幻觉 URL + prompt 思考式
    - inspector 补 SWOT/雷达/矩阵/溯源程序化硬查 + severity 分级 pass/fail（只 critical/major 阻断）
    - graph 打通 focus_area 回填 + inspector 传竞品名单 + should_continue 认 analyzer 回边
    - 前端渲染 SWOT 四象限/雷达表/功能矩阵/章节溯源链接
    - 全链路删截断（collector/analyzer/writer/inspector），依赖 256K 上下文
  - 真实跑通验证（语雀 vs 飞书）：四项验收达成——质检硬伤归零、报告丰满、SWOT/雷达/矩阵结构完整、章节溯源链接可见、focus_area 填充
- **本次验证暴露的数据层瓶颈（下一课题，非本工程范围）**：
  - 采集质量是报告天花板。实证（runs/20260604-230835-8c4c1d）：飞书只抓到一个法务页（feishu.cn/legal/pricing-adjustment-subtitle）→ completeness=0.0 → 功能矩阵全「无」、雷达全低（误判，飞书实际功能全面、市占远胜语雀）；语雀有效源仅 1 个第三方页（partnershare.cn），官网页+知乎页未用上（知乎 403、LLM 选页超时退规则）
  - 真实采集缺陷：① LLM 选页频繁超时（PICK_LLM_TIMEOUT=20s 太短，飞书两轮都退规则选页）② 知乎等站点反爬 403 ③ 规则选页质量差（选到法务页）④ 只 top3、单源依赖、覆盖窄
- 进行中：feat/report-quality 合并回 master（本 session 进行中）
- 下一步（新 session，独立课题：数据层增厚 + 交互优化）：
  1. **采集能力增强**（优先）：接 AI 搜索 API（Tavily/Exa，直接返回干净正文、绕开抓取+反爬）；或修现有管线（选页超时调长、抓取重试/换UA、规则选页官网优先、top3→top5、多源融合）。注：collector 是 Doubao 纯 Python agent，不能直接挂 MCP（MCP 是给 Claude 这类 agent 的工具协议）；若要 MCP 驱动采集需架构级换成 MCP-capable agent
  2. **前端输入优化**：让用户可填竞品官网 URL/已知信息/指定数据源，减少对盲搜依赖
  3. **溯源粒度增强**：维度+竞品级 → per-entry（需改 analysis schema 结构）
  4. **analyzer 回边定向修复**：重打 analyzer 时把 feedback.issues 附加进 prompt（从随机重采变定向修复）
  5. 其他 Minor（最终 review 提）：inspector LLM issue 解析加逐条容错、前端 SWOT 补展示 evidence/source_urls
- 阻塞：无
- 安全提醒：DOUBAO_API_KEY、SEARCH_API_KEY（SerpAPI）务必轮换（历史对话/日志多处出现过），均走 .env、勿提交

## 2026-06-04（数据源拓展真实跑通验证 + SerpAPI 鉴权 bug 修复）
- 完成：
  - 走 brainstorming → doubt-driven（单模型 + Codex gpt-5.5 跨模型对抗审查，捕获 B1 import 固化/B4 主线成败混淆等盲点）定稿验证方案 `docs/superpowers/specs/2026-06-04-datasource-verification-design.md`
  - 三路径端到端真实冒烟（非补单测；逻辑分支已 117 单测覆盖，本次只验真实环境契合度），证据看落盘 01_profiles.json 的 pipeline_trace + run.log：
    - 路径 A（语雀 vs 飞书，无 key）：search_skipped/no_api_key + saas→itunes 路由 + 真实 trackViewUrl，completeness 0.9；run.log 确认无 search/pick LLM 日志
    - 路径 A'（小米 vs OPPO，无 key）：default→空专源 + completeness=0.0 占位、不调 extract LLM、零数据源 HTTP（仅 Doubao）
    - 路径 B（语雀 vs 飞书，有 key）：修复后 SerpAPI 200、pick method=llm picked=3、抓到真实官网（feishu.cn/partnershare.cn），主线全打通
  - **systematic-debugging 抓出真实 bug（修复前主线在中文场景 100% 失效）**：SerpAPI 用 `Authorization: Bearer` header 鉴权时，遇非 ASCII（中文）query 返回 401「Invalid API key」（误导性极强）。证伪 4 个假设（env 污染/key 激活延迟/二次编码/headers 干扰），用同脚本同时刻 ASCII vs 中文对比锁定根因
  - TDD 修复（119 测试全绿 + ruff 清）：
    - `sources.py`：SerpAPI 鉴权改 `api_key=` query 参数（去掉 Bearer header）；新增中文 query 编码回归测试
    - `logger.py`：httpx/httpcore 日志压到 WARNING——其 INFO 会明文打含 api_key 的完整 URL（防泄漏）；新增防泄漏测试
    - `test_config.py`：修预存测试隔离 bug（reload 时 load_dotenv 重读 .env 真实 key 致 SEARCH_API_KEY 断言失败，monkeypatch 屏蔽 load_dotenv）
  - 安全核查：.gitignore 已覆盖 .env/logs/runs/.claude，别人 clone 看不到含 key 文件；清理本地历史明文泄漏（app.log + 旧 trace），残留=0
  - **关键认知**：报告 quality_score 由 inspector 按 issue 严重度倒推回填（builder.py:602），全链路真正的质量分只有「采集 completeness_score」+「质检倒推 quality_score」两处；analyzer/writer 不自评。报告质量低与数据源好坏无关，由 writer 加工缺陷决定（课题②）
- 进行中：无
- 下一步（新 session）：
  1. 【报告质量，独立课题②】沿用待办：抓 04_feedback 完整 issues 确认是否仍是三老问题（source_refs 下沉断链 / SWOT 丢失 / focus_area 空），debug writer + collector
  2. iTunes 同名 App 污染（搜「语雀」带出 flomo/石墨；搜「飞书文档」带出腾讯文档/石墨）——top3 混入同赛道他家，profile 可能混入别家信息，可考虑结果过滤或 limit 调整
- 阻塞：无
- 安全提醒：**SEARCH_API_KEY（SerpAPI）本 session 在终端/日志多处明文出现过，务必轮换**；Doubao API Key 同样务必轮换（沿用历史提醒）。两者均走 .env、勿提交

## 2026-06-03（数据源拓展：采集管线重构）
- 完成：
  - 走完整 brainstorming → 三轮 doubt-driven（每节单模型 + Codex gpt-5.5 跨模型对抗审查）→ writing-plans → subagent-driven 流程
  - 设计文档 `docs/superpowers/specs/2026-06-03-datasource-expansion-design.md`，实现计划 `docs/superpowers/plans/2026-06-03-datasource-expansion.md`（15 Task）
  - 采集层从 collector 内 3 个硬编码 URL 源，重构为分层管线 `CollectorAgent(agent) → CollectionPipeline(tool) → sources(插件)`：
    - 主线两步走：SerpAPI 搜索 → LLM 选页（独立短超时 wait_for，失败退规则）→ 抓正文 → 质量闸门过滤
    - 结构化专源按 category 路由、可插拔（saas→iTunes；硬件电商源列入未来扩展）
    - 无 SEARCH_API_KEY 时跳过搜索主线、仅走专源（不退回 SERP 抓取）
    - 全空时产 completeness=0.0 占位 profile（不调 extract LLM，防幻觉）
    - 顶层 collect 改部分降级（单竞品失败产占位，不拖垮全局，语义从「快速失败」变更）
    - pipeline_trace 随 profile.metadata 落盘（与 graph node_trace 分离）
  - 新增 `src/tools/sources.py`（iTunes+SerpAPI+路由）、`src/agents/collection_pipeline.py`、`src/tools/quality_gate.py`；`HttpClient.get_json`（key 走 header、URL/异常双重脱敏、UA 加锁）；`ProfileMetadata.pipeline_trace`；config 加 4 个可选配置
  - 117 测试全绿（原 51 → 117）、ruff 全清；TDD + 小步提交（21 commits）
  - doubt-driven + 代码审查捕获并修复的真实问题：路由原语用错（competitor_type 误当 SaaS/硬件类别）、密钥经 query/异常消息泄漏、CollectionPipeline `_current_name` 实例属性并发数据竞争（A 报告混入 B 数据，改参数传递）、集成测试 6 步序列隐式依赖环境变量为空（显式 monkeypatch 屏蔽）、_rate_limit check-then-act 限速竞态（加 per-domain 锁）、iTunes 空壳记录污染 sources
  - **重要发现**：subagent 报「集成测试全绿」一度是占位降级路径假象（extract response 未被消费），亲自核实后在 Task15 让集成测试走真实采集路径（saas 路由 + mock get_json + call_index==6 断言锁定）
- 进行中：无
- 下一步（新 session）：
  1. feat/datasource-expansion 合并回 master（本 session 进行中）
  2. 真实跑通验证：配 `SEARCH_API_KEY`（SerpAPI）验证搜索主线；无 key 验证专源降级路径；Demo 建议用 Notion 类 SaaS（数据源契合）
  3. 【报告质量，独立课题】沿用 06-02 待办：溯源下沉断链、SWOT 丢失、focus_area 空（与本次数据源拓展无关）
- 阻塞：无
- 安全提醒：验收用的 Doubao API Key 在历史对话中明文出现过，务必轮换（沿用历史提醒）；新引入的 SEARCH_API_KEY 走 .env，勿提交

## 2026-06-02（可观测性与中间产物追溯）
- 完成：
  - 走完整 brainstorming → doubt-driven（单模型 + Codex 跨模型对抗审查）→ writing-plans → subagent-driven 流程
  - 设计文档 `docs/superpowers/specs/2026-06-02-observability-trace-persistence-design.md`，实现计划 `docs/superpowers/plans/2026-06-02-observability-trace-persistence.md`
  - SPEC.md 移入 docs/，修正过时的 JSON mode 决策（与 DECISIONS 06-01 对齐）
  - 14 个 Task 全部实现（feat/observability-trace 分支），71 测试通过、ruff 全清：
    - TraceWriter（src/tools/trace_writer.py）：trace_id 北京时间格式+碰撞规避、save_stage（json mode 序列化+原子写+重试快照 _vN）、save_meta、容错仅 warning 不抛
    - src/utils/paths.py：项目根/runs/logs 绝对路径，不依赖 CWD
    - 日志接线：init_logging 配 root logger（控制台+logs/app.log），修复 setup_logger 从未被调用的 bug；每次分析另存 runs/<trace_id>/run.log
    - graph 各节点产出落盘四阶段产物，build_graph 返回 (graph, node_trace) 记录路由决策
    - routes.py：trace_id 新格式、TraceWriter 注入、ainvoke 前后两次写 meta（running/completed/failed）
    - 追溯 API GET /trace/{trace_id}：路径穿越双重防护（fullmatch + resolve 校验）、按需取历史版本
    - 前端「执行追溯」面板：6 tab 展示中间产物+日志+快照对比
  - doubt-driven 暴露并修复的真实问题：原子写、model_dump(mode=json)、路径穿越正则未锚定、meta 两次写防孤儿、快照覆盖全 4 stage、logger 幂等判断按 baseFilename
  - 手动 UI 验证通过：真实跑通多次分析，产物落盘/meta/run.log/node_trace 全正常；反馈闭环+重试快照真实生效（ef2b68 打回 collector，01~04 的 _v1 快照全保存，验证了「快照覆盖全 4 stage」修正）；追溯面板加载成功；顺手修了前端 trace_id 输入 strip（粘贴空格导致 404）
- 进行中：无
- 下一步（新 session）：
  1. feat/observability-trace 分支合并回 master
  2. 【报告质量，独立课题】UI 验证时质检诚实暴露上游 Agent 3 类真实缺陷（与可观测性功能无关，是先前就存在、现在才被追溯照出）：
     - 溯源下沉断链：report 顶层有 12 条 data_sources，但各 section 的 source_refs、各 action_item 的 source_urls 全空（与 06-01 修过的 report.data_sources 断链同类、不同位置）
     - SWOT 丢失：analysis 里有 SWOT，但 writer 没写进最终报告的 SWOT 模块
     - focus_area 空：collector 解析目标时未填 analysis_goal.focus_area
     - 后果：质检每次发现 3+ issue、打回重试 2 次仍不通过、quality_score=0.0
     - 修复方向：debug writer（下沉 source_refs/source_urls、补 SWOT 模块）、collector（填 focus_area）
  3. 数据源场景适配（手机品牌 iTunes 不契合，Demo 建议用 Notion 类 SaaS）— 沿用 06-01 待办
  4. 【可选小优化】Windows 控制台中文乱码（GBK），run.log/app.log 文件本身 UTF-8 正常，仅终端显示乱码
- 阻塞：无
- 安全提醒：验收用的 Doubao API Key 在历史对话中明文出现过，务必轮换（沿用 06-01 提醒）

## 2026-06-01（前后端手动验收）
- 完成：
  - 环境搭建：Python 3.14 + venv，依赖全装（无 wheel 兼容问题），51 测试通过
  - 真实 Doubao API 端到端验收，跑通完整四 Agent 链路，产出高质量结构化报告
  - 验收中修复 4 个真实问题：
    - `response_format=json_object` Doubao 不支持（400）→ 改纯 prompt 约束 + 代码块剥离
    - `LLM_TIMEOUT=30s` 太短（单次调用实测 30.4s）→ 调到 120s
    - 数据源抓取全失败（百科403/AppStore404/百度反爬）→ 换 iTunes API + Bing + 搜狗，补全请求头
    - `report.data_sources` 断链（writer 拿不到 profile sources）→ graph 层 writer_node 回填
  - 顺手修两处瑕疵：前端行动建议层级标签（immediate=即时）、quality_score 由 inspector_node 按 issue 严重度回填（0-1）
  - 验证溯源恢复：报告 data_sources 含 3 个真实来源，正文用上 iTunes 真实评分（4.7/5，2万+评价）
  - CLAUDE.md 补充常用命令 + 代码架构（/init）
- 进行中：无
- 浏览器验收发现并修复：
    - 竞品上限 5→10（用户输入 6 个触发 422）
    - 前端错误处理 bug：未处理非 200 响应，直接读 data["status"] 抛 KeyError，掩盖真实校验错误 → 改为先判 status_code，解析 FastAPI detail 友好展示
    - LLM 输出结构偏差：sample_reviews 被填成字符串数组（应为 SampleReview 对象），导致采集校验失败 → ① prompt 补全元素结构示例 ② collector 加 _normalize_raw 兜底（字符串转 {content, rating:3}）
    - LLM JSON 含裸控制字符（字符串值内裸换行）→ Invalid control character → llm_client 改 json.loads(..., strict=False)
    - analyzer 枚举校验失败：feature_matrix.gap_level 被填 "小米领先" 等带主语值 → analyzer 加 _normalize（gap_level/our_product/competitors/swot.dimension 枚举规整：精确→包含匹配→默认）
    - writer 枚举校验失败：action_items.priority 被填 "中等" → writer 加 _normalize（priority 规整 + metadata 补充）
  - 最终验证成功：6 品牌（小米/VIVO/OPPO/三星/华为/苹果）完整跑通，产出高质量报告，data_sources 13 条真实 URL，quality_score 0.55，无校验错误
- 下一步（新 session 优先处理）：
  1. 【可观测性，评分项】修日志落盘：setup_logger 写了但从未被调用，logs/app.log 不生成；agent/graph 的 INFO/WARNING 日志（[graph] → collector、采集源成败、completeness）全部丢失。需在 api 启动时初始化 logger 并配置 root level，让全链路日志可见。
  2. 【数据源场景适配】手机品牌用 iTunes(App 搜索) 不契合——搜到的是同名 App 非手机硬件，导致溯源 URL 真但内容弱。Demo 建议用 Notion 类 SaaS 软件（数据源契合），手机仅作架构通用性展示；或为硬件场景换专业评测/电商源。
  3. quality_score 0.55 偏低反映数据完整度一般（质检诚实反映），与 #2 相关联。
- 已知非阻塞瑕疵：无（本轮 LLM 鲁棒性问题已全部修复）
- 阻塞：无
- 安全提醒：验收用的 Doubao API Key 在对话中明文出现过，务必轮换

## 2026-05-31 ~ 2026-06-01
- 完成：
  - PRD V3.0 重写（基于 MIT 模板 + 竞品分析 SOP，14 章节完整覆盖）
  - SPEC.md 技术规格（spec-driven development skill）
  - 18 个实现 Task 全部完成（subagent-driven development skill）
    - Task 1: 项目骨架
    - Task 2-5: 5 个 Schema（input/profile/analysis/report/feedback）
    - Task 6-9: 4 个工具（config/logger/LLM client/HTTP client/HTML parser/validators）
    - Task 10-14: 4 个 Agent + Prompts（collector/analyzer/writer/inspector）
    - Task 15-16: LangGraph State + Builder（含反馈闭环）
    - Task 17-18: FastAPI 后端 + Streamlit 前端
  - 代码审查（code-reviewer agent），发现 10 个问题
  - 10 个审查问题修复（4 批 subagent 并行修复）
  - receiving-code-review 验证：9 个修复合理，#8 为误判已回退
  - .env 配置（Doubao API Key）
  - 51 个测试全部通过
- 进行中：无
- 下一步：手动验收（启动前后端，真实 Doubao API 跑完整分析）
- 阻塞：无

## 2026-05-30
- 完成：
  - 开题材料研读与分析（CIS AI 全栈挑战赛开题材料）
  - lark-cli 安装验证、飞书认证、lark-cli skill 清理
  - PRD 撰写（产品定位、Schema 设计、4 Agent 角色定义、数据源、信息溯源、可观测性）
  - 项目文档结构整理（docs/ 分离项目内容与开发过程文档）
  - 开发计划制定（11 天极限计划，5/30-6/10）
- 进行中：PRD 待 Cooper 审阅确认
- 下一步：技术方案设计 + 项目骨架搭建（LangGraph hello world）
- 阻塞：无
