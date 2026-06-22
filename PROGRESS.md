# Project Progress

PentaScope — AI 驱动的竞品分析 Agent 协作系统 — 项目进度日志。

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

## 2026-06-20（内部重试纠正反馈 + 前端输入一致性 warning）
- 完成：
  - **内部重试带纠正反馈**：
    - collector `_extract_profile`：ValidationError 序列化后追加到 retry prompt
    - analyzer `analyze`：同上模式
    - writer phase 3 narrative：重试时注入 `retry_error_hint` 到 system_prompt
    - 参照 writer `_call_with_validation` 成熟模式统一实施
  - **前端输入一致性 warning**：已回退，需重新评估实现方案（Streamlit rerun 模型与阻断交互冲突）
- 下一步（TODO）：
  1. **evidence 反馈闭环 v2**：按竞品分组传 URL + 打回时传 inspector 原始 reason/suggestion + 简化路由逻辑
  2. **前端输入一致性 warning**：重新评估需求和方案
- 阻塞：无

---

## 2026-06-20（反馈闭环路由改进实施）
- 完成：
  - **反馈闭环路由 9 task 全部完成**：
    1. URL 归一化函数（`src/utils/url_normalize.py`）
    2. EvidenceFeedback Pydantic 模型（`src/schemas/feedback.py`）
    3. `_route_evidence_issue` 路由函数（代码层 coverage 判断）
    4. `should_continue` 集成 evidence 优先路由
    5. `inspector_node` 写入 `_prev_evidence_coverage` 供退出判断
    6. Writer evidence 反馈注入（phase 3 prompt 含 URL 列表 + weak_fields）
    7. Collector `supplement_collect` 增量补采方法
    8. `collector_node` 增量补采模式集成
    9. 全量回归 494 passed + ruff 全通过
  - **核心改进**：evidence issues 闭环区分"有源不用"（→writer 带 URL 反馈）vs"真缺源"（→collector 定向补采），消除无效盲跑
  - **退出条件**：`_prev_evidence_coverage` 未提升时自动 end，防无限循环
- 下一步（TODO，按优先级）：
  1. **端到端验证**：跑 S1/S4 场景触发 evidence issue 验证新路由实际效果
  2. **内部重试带纠正反馈**（Q-2026-06-20）：评估 ROI
  3. **前端输入一致性 warning**（方案 C）
- 阻塞：无

---

## 2026-06-19（晚 / critic v1.2 修复 + narrative 轻重试 + max_tokens 调参 + JSON 鲁棒性）
- 完成：
  - **critic v1.2.1 三问题修复**（commit `0059db5` + `03babf7`）：
    1. scenario_payload 不再裁剪 → critic 能看到场景特有内容
    2. coherence 场景 pair 重写 → S2/S5 修字段名（实测全错导致静默跳过），S3 换 packaging vs recommendations_summary，S4 换 threats vs monitoring_actions；直接属性访问防静默失效
    3. findings/narratives/recommendations 改全量传递，消除抽样偏差
    - 9 新单测锁定 + 4 eval 反例集（S2/S5 稳定检出矛盾，S3/S4 受 MiMo 非确定性影响）
  - **phase 3 narrative 轻重试**（commit `eae4e44`）：单 section 首次失败串行重试 1 次，仍失败才占位降级。实战验证 S5 `positioning_statement_analysis` 首次 ValidationError → 重试成功 → 6/6 全通过
  - **max_tokens 基于 finish_reason 实证调参**（commit `2a06fe1` + `39bf3d2`）：
    - phase 1 outline: 4096 → 6144（实测 3983~4096 撞满 2 次）
    - phase 2 payload: 8192 → 12288（实测重试时 8192 撞满）
    - phase 3 narrative: 4096 → 8192（实测 4051/4096=99.9%）
  - **JSON 鲁棒性：三次兜底修复未转义双引号**（commit `f1bd582`）：
    - 历次 36 次 JSON 解析失败分类：Unterminated string 19 次（max_tokens 已修）/ Expecting ',' delimiter 7 次（本次修）/ 其他 10 次
    - 新增 `_fix_unescaped_quotes_in_values` 状态机：字符串值内 ASCII 双引号替换为中文引号
  - **S5 端到端验证**（trace `20260619-203923-9f5681`，Figma vs Sketch/Adobe XD/Framer）：
    - **quality_score=0.900，passed=True**（项目历史最高分 + S5 历史首次通过）
    - critic 评分 ev=3 sp=4 co=4 ac=4
    - narrative 6/6 成功（轻重试救回 1 个）
    - finish_reason=length 截断 0 次（全链路零截断）
    - 总耗时 9 分 35 秒（历史 S5 平均 25-35 分钟）
    - 一次通过无反馈闭环（历史 S5 均需 2 轮闭环）
  - **发现 Q-2026-06-19-scenario-query-低相关**：S5 query 太学术化（"品牌定位 战略差异化"）导致 Tavily 返回无关内容（MBA 百科/社科院论文），12 条搜索结果仅 5 条有效（42%）。已记入 OPEN_QUESTIONS，归入 collector 搜索优化课题
  - **字符约束全面退役**（commit `0ad443c`）：
    - 基于 27 份历史报告实测数据 + 22 次 ValidationError 失败记录评估
    - 删除所有字符串 min_length（report.py + s1-s5.py 共 70+ 处）
    - 放宽 S1/S5 vendor_profiles.strengths ≥2 → ≥1
    - 保留列表结构性约束 + URL min_length=8 + max_length 防爆
    - 质量保障完全由 critic 4 维 rubric 评分承担
  - **collector 搜索 query 策略优化**（commit `9e66079`）：
    - 每场景从 1 条学术化 query → 3 条产品实操语言 query
    - S1 功能特性/vs 竞品对比/用户评价；S2 公司融资/市场份额/行业排名；S3 定价/pricing plans/免费付费区别；S4 动态/changelog/融资新闻；S5 产品定位/vs 竞品/官网介绍
    - 3 query 并发搜索，预计有效结果从 5 条提升到 10-12 条
  - **JSON 鲁棒性追加：raw_decode 处理 Extra data**（commit `897010a`）
  - **collector Feature.description max_length 200→500**（commit `fa5bbf9`）
  - **OPEN_QUESTIONS 清理**：7 条关闭/并入 5 条，仅剩 2 条（inspector issue 丢失观察中 + query 已修待验证）
- 进行中：反馈闭环路由改进（spec v2 已落 + plan 9 task 已写，等下次 session 执行）
- 本 session 额外完成：
  - **S1-S4 端到端验证**（S1 0.800 / S2 1.000 / S3 0.833 / S4 0.633 max_retries）
  - **分层模型配置**（MODEL_FAST/MODEL_PRO 环境变量 + builder 分层注入）
  - **代码命名统一**（DOUBAO_* → LLM_* 通用配置，兼容旧 .env）
  - **collector classify 步骤删除**（专源路由已移除，省每竞品 1 次无效 LLM 调用）
  - **analyzer max_tokens 8192→16384**（S2 五竞品实测撞满）
  - **phase 3 narrative max_tokens 8192→12288**（S1 jtbd_analysis 实测撞满）
  - **前端超时 1800s→3600s**（S1 反馈闭环 32 分钟超时）
  - **TESTING_GUIDE 测试用例全部改用国产产品**
  - **README / CLAUDE.md 去 Doubao 硬编码**
  - **反馈闭环路由 spec v2**（双轮 doubt-driven：单模型 12 条 + codex 跨模型 30 条，合并 9 条 actionable）
  - **反馈闭环路由 plan**（9 task TDD，`docs/superpowers/plans/2026-06-20-feedback-loop-routing.md`）
- 下一步（TODO，按优先级）：
  1. **执行反馈闭环路由 plan 9 task**（推荐 subagent-driven 或新 session inline）
  2. **内部重试带纠正反馈**（Q-2026-06-20）：等 #1 做完后评估 ROI
  3. **前端输入一致性 warning**（方案 C）
- 阻塞：无
- 安全提醒：无新增 key

---

## 2026-06-19（LLM-as-critic spec 三轮 doubt-driven + plan 落盘 + finish_reason 可观测性）
- 完成：
  - **Brainstorming 8 个问题逐一拍板**（critic 路线 A / 4 维 evidence+specificity+coherence+actionability / 0.30/0.30/0.20/0.20 加权 / 集成顺序 C 内嵌单次调用 / coherence 限定 pair / 失败 retry 1 次后 fallback / D 阈值映射 / CoT 全维度 / 整报告级评分 / 测试三层 / v3-R17 cap 删除）
  - **Spec v1 → v4 三轮 Codex 跨模型 doubt-driven 审查**（`docs/superpowers/specs/2026-06-19-llm-as-critic-design.md`）：
    - cycle 1: 33 条（8 critical / 16 major / 9 minor）→ v2 消化 26 条 actionable（commit 2cbcde4）
    - cycle 2: 22 条（4 critical / 12 major / 6 minor）→ v3 消化 20 条 actionable（commit 725e0af）
    - cycle 3: 20 条（5 critical / 10 major / 5 minor）→ v4 消化 5 critical，10 major + 5 minor 留 plan 阶段（commit f0ff223）
    - 总共 75 条问题，消化 51 条 actionable
    - critical 数 8→4→5（未单调收敛）→ skill Step 5 触发 escalate → Cooper 选 A 修 critical 进 plan
  - **关键认知翻转**：实证 author bias —— 我自己 self-review v1 只发现 1 处问题，跨模型 codex 发现 75 条。每轮"修订引入新问题"+"v2 漏审继续在 v3 暴露"两类 bug 各占一半。今后**任何架构级 spec 必须走 doubt-driven，不能 self-review 后直接 ship**
  - **Plan 落盘**（`docs/superpowers/plans/2026-06-19-llm-as-critic.md`，2507 行 / 19 task / commit 48bde22）：自底向上 TDD（schema → quality_score → critic prompt → inspector 子函数 → 主流程 → graph 集成 → collector snippet → 测试三层 → 影响面验收脚本 → 全量回归）。每 task 含失败测试 / 实现 / 验证 / commit 五步
  - **finish_reason 可观测性增强**（commit fc94c8b）：`llm_client.py` 加 finish_reason + completion_tokens 日志 + length 时打 WARNING。为后续 max_tokens 调参决策积累硬证据（之前用 char 数反推 token 不可靠）
  - **OPEN_QUESTIONS 06-19 统一处置**：6 条 LLM 输出鲁棒性 + 字数代理副作用问题统一冻结观察"等 critic 落地后回头看可能消解一半"（Cooper 整理）
- 关键讨论结论（已落 brainstorming 8 决策 + spec v4）：
  - **Critic 不冲突 inspector**：现有 _llm_check 是"半成品 critic"（无 rubric / 输出非评分），路线 A 是升级它，不是新建 agent
  - **字数约束分阶段退役**：critic 落地是阶段 1，删字数 schema 是阶段 3-5 留后续 spec；本 PR 严禁动 schema min_length
  - **DataSource.confidence 是假动态**：Cooper 实证 `writer_orchestrator.py:1375` 写死 "medium"，confidence_avg 历史所有 trace 都是 0.6 → 删
  - **max_tokens 暂不动**：我前后矛盾论断（Cooper 反复挑战），最终结论"先加 finish_reason 日志收集硬证据，再决定要不要调"
  - **critic_failed 路由 agent="end"**（cycle3/C5）：critic 系统故障让 writer 重写无效，必须 terminal 不消耗 max_retries
  - **quality_score 是 semantic 分**（cycle3/C2）：programmatic critical 通过 passed 阻断而非降分；calculation_note 加 prog_issues 计数让追溯可见
- 进行中：plan 落盘完毕，等下次 session 实施
- 下一步（TODO，按优先级）：
  1. **执行 LLM-as-critic plan 19 task**（推荐 subagent-driven，预计 3-4 小时）—— 见 `docs/superpowers/plans/2026-06-19-llm-as-critic.md`
  2. **phase 3 narrative 轻重试**（继承 06-18 待办）：单 section 失败重跑 1 次再占位
  3. **max_tokens 调参决策**：跑 1-2 次新分析后看 finish_reason 日志数据，决定 phase 1/3/analyzer 是否调到 8192
  4. **字数约束阶段 3-5 退役**（critic 跑通后启动）：critic 校准稳定后逐字段评估"实际拦住的是什么"
- 阻塞：无
- 协作模型实证（重要）：
  - **doubt-driven 三轮没收敛**（critical 8/4/5 起伏）→ skill 文档预警的"3 cycles 后仍有 substantive issues = artifact 可能太大或有结构性问题"信号确实成立
  - **author bias 反复发作**：max_tokens 推理（机制 A vs B）+ self-review 草率（4 项检查走过场）+ "Unterminated 是机制 A 特征"拍脑袋——3 次都靠 Cooper 反问拽回来。建议未来类似讨论 Cooper 主动逼"用证据说话"
  - **Cooper 产品判断 vs Claude 工程评审**协作模型再次验证有效（feedback_pm_dev_collab_with_doubt_driven.md）：维度选 C/A/D 不要 actionability、不重跑 S5 验证、跑满 3 轮、修 critical 进 plan、A subagent-driven 等 5 处都是 Cooper 拍板我执行
- 安全提醒：本 session 全程文档 + spec + plan，无 key 引入

---

## 2026-06-18（S5 拆分端到端首次真跑 + 4 bug 修复 + OPEN_QUESTIONS 文档体系建立）
- 完成：
  - **OPEN_QUESTIONS.md 文档体系建立**：与 PROGRESS / DECISIONS 三文档边界划清，问题 ID 格式 `Q-YYYY-MM-DD-关键词`，状态 4 档（未决 / 设计中 / 实施中 / 已并入）。CLAUDE.md "上下文恢复"章节同步加入 OPEN_QUESTIONS 必读
  - **S5 拆分端到端首次真跑（trace `20260618-095358-c5ab5c`，Figma vs Sketch/Adobe XD/Framer）**：
    - **拆分路径完整跑通**：vendor=4 / factors=10 / dropped_warnings=0，phase 2a + 2b 数据完整
    - **第二次 writer phase 3 narrative 6/6 全成功**（PentaScope 历史首次，但因 phase 4 ValidationError 报告未落盘）
    - 总耗时 31 分 33 秒，最终 quality_score=0.486（仍 cap 0.5），passed=False，max_retries=2 强制结束
  - **4 个 bug Prove-It 修复（commit `6e864e1`，451 passed / 5 skipped / 2 xfailed / ruff clean）**：
    1. phase 1 outline 漏字段拖到 phase 4 才炸 → `_phase1_outline` 加 `ExecutiveSummary` 即时 Pydantic 校验 + max_retries=2 + 增强错误反馈回灌
    2. `s5_phase2b.py` prompt 没给 artifact_id 示例值 → 加 `≥3 字符必填，例如 errc-001 / bom-001` + 高频踩坑提醒
    3. `s5_phase2a.py` cluster_zones 没说条件性必填 → 加子字段 brands_in_cluster ≥2 + implication ≥20 强约束 + "不确定就返回 `[]`"
    4. `_merge_s5_payload` artifact_id 兜底漏 blue_ocean_move → 循环加 blue_ocean_move 条件兜底
  - **测试 fixture 公用化**：新增 `_make_valid_outline_dict()` fixture（含合规 executive_summary），5 处简化 mock 改用，避免 Claude 自己估字数错触发 schema 校验失败
- 关键发现（已落 OPEN_QUESTIONS）：
  - **Q-2026-06-18-json-extra-data**：JSON 解析失败的第 4 种模式 `Extra data`（LLM 在 JSON 后追加纯文本说明），与已知 `Unterminated string` / `Expecting value` / `Expecting property name` 不同类
  - **Q-2026-06-18-llm-反馈修一退一**：错误反馈回灌重试机制的天然弱点——LLM 全文重写时无"上次合规字段别动"记忆，常 attempt 0 错 A、attempt 1 修 A 但反退 B、attempt 2 修 B 但反退 C，max_retries=2 预算紧
  - **Q-2026-06-18-inspector-llm-issue-丢失**：inspector LLM 输出 issue 自身违反 `FeedbackIssue` schema 的部分被丢弃（trace 实证 2/8 条丢失），inspector 反馈信号容量被自身鲁棒性问题压低
  - **Q-2026-06-18-narrative-偶发抖动**：phase 3 narrative 单 section 失败率 ~17% 是 MiMo 在该任务的底噪，**与输入大小关系不强**（修正昨天的"输入大 → 失败概率高"假设）；同 section 重跑就过 → 强证偶发抖动可通过重试救
- 进行中：4 个 bug 已修，跳过重跑验证（Cooper 决策不必再验证浪费时间），直接进 LLM-as-critic 讨论
- 下一步（TODO）：
  1. **LLM-as-critic 评分**（最高 ROI 提质方向，正在开发中）：spec v2 已落 `docs/superpowers/specs/2026-06-19-llm-as-critic-design.md`，进 plan / 实施阶段
  2. **phase 3 narrative 轻重试**（2026-06-19 Cooper 决断）：单 section 失败重跑 1 次仍失败才占位，最坏 +3min（6 sections × 30s）。修复 `WriterOrchestrator._phase3_narrative` + 单测
- 阻塞：无

---

## 2026-06-17（S5 payload 拆分实施 + 报告质量提升方向反思）
- 完成：
  - **S5 payload 拆分（spec → plan → execute 全流程，8 task / 8 commit）**：
    - spec 修复重复段落（da915fb），plan 8 task 按 TDD 推进
    - Task 1-3：新建 `s5_phase2a.py`（数据层 prompt，4625 字符）+ `s5_phase2b.py`（战略层 prompt，3601 字符）+ `__init__.py` 导出 `S5_SPLIT_PROMPTS` dict
    - Task 4：新增 `_serialize_validation_error_enhanced` 静态方法（S5 专用人类可读错误反馈，loc 点号串联 + type 翻译为期望值，前 8 条带序号，max 2000 字符）。原 `_serialize_validation_error` S1~S4 路径不变
    - Task 5：`_call_s5_phase2a` 数据层 LLM 调用，逐模块校验（S5VendorProfile / PerceptualMap / StrategyCanvas），ValidationError 回灌增强反馈，max_retries=2
    - Task 6：`_call_s5_phase2b` 战略层 LLM 调用，注入 `phase2a_output` 的 competitive_factors + vendor_names 作为只读上下文，blue_ocean_move Optional（缺失/空 dict 都跳过）
    - Task 7：`_merge_s5_payload`（合并 + scenario_type + artifact_id 兜底 + blue_ocean_move 透传）+ `_call_s5_phase2_split`（phase2a → phase2b → merge → normalize → 实例化）+ `_call_phase2_with_validation` 入口加 scenario==S5 分支路由。S1~S4 完全不变
  - **测试**：451 passed（+5 新 S5 拆分单测）/ 5 skipped / 2 xfailed / ruff clean
  - **模型可用性验证**：Cooper 把 `.env` 里 `DOUBAO_MODEL_EP` 从 `mimo-v2.5-pro[1m]` 改为 `mimo-v2.5-pro` 后端点接受，text/json 调用都通
- 进行中：S5 拆分 Task 8 端到端真实 LLM 验证未跑（需要 Cooper 启动后端 + 前端手动跑 S5 场景验 quality_score ≥0.7）
- 关键讨论（写测试 fixture 反复触发字数 ValidationError 引出）：
  - **LLM 字数约束失败是机制问题不是能力问题**：token≠字符（中文尤其错位）、自回归生成无全局规划、训练分布缺"严格字数"任务、知行差距。换更强模型也救不了
  - **字数约束本质是质量代理而非质量本身**：能拦"懒得写"但拦不住"写很多废话"，废话是 LLM 舒适区
  - **不能在代理层叠加字符级规则**（Cooper 直接质疑过的方案 A "每段强制至少 1 个数字或专名"已撤回）：真实咨询报告大量纯洞察论断没数字（"建议优先攻防而非主动进攻"/"进入门槛主要在生态而非技术"），强制加会逼出比废话更糟的假数据幻觉
  - **提质方向应跳出代理思路**：转向 LLM-as-critic 语义评分（G-Eval / Prometheus 范式），独立 critic prompt 按 specificity/actionability/evidence/coherence rubric 打分，writer 据此重写
  - **两条记忆已落盘**：`feedback_proxy_metric_bias.md`（看到代理失效就想换代理是 Claude 的思维 bias）+ `project_length_constraint_proxy_problem.md`（项目当前字数约束的本质问题 + 提质方向）
- 下一步（TODO，按优先级）：
  1. **S5 拆分端到端真跑验证**（紧迫）：Cooper 启动后端 + 前端跑 S5 场景，验证 quality_score ≥0.7 + 总耗时 < 15 分钟 + Phase 2a/2b 各自成功（看日志）
  2. **报告质量提升 — LLM-as-critic 评分**（新增方向，最高 ROI）：独立 critic agent 按 rubric（specificity / actionability / evidence / coherence）打分，inspector 接 critic 输出做反馈闭环；字数约束渐进退役（critic 跑通后逐字段评估"实际拦住的是什么"，拦"水且违规"才保留，拦"真但不合规"或"水但合规"则删）。需走 brainstorming → doubt-driven → spec → plan 完整流程
  3. **分层模型调用**（沿用 06-16 待办）：collector/analyzer 用快模型，writer narrative 用强模型，待 Cooper 调研选型
  4. **analyzer 并行拆分**（沿用）：4 竞品拆 2×2 并发
  5. **collector 信息收集优化**（沿用）：多次搜索 + 不同关键词，需先验证 ROI
- 流水线优化方案清单（更新版）：

  | 方案 | 提速 | 提质 | 改动量 | 状态 |
  |------|------|------|--------|------|
  | S5 payload 拆分 | - | ★★★ | 中 | **已实施（待真跑验证）** |
  | LLM-as-critic 评分（新） | - | ★★★★ | 大 | **新增 / 待 brainstorming** |
  | 分层模型 | ★★★ | ★★★ | 小 | 待模型选型 |
  | analyzer 并行 | ★★★ | - | 中 | 待实施 |
  | ValidationError 反馈 | ★★ | ★★ | 小 | **S5 已含增强反馈** |
  | prompt 精简 | ★ | - | 中 | 待评估 |
  | 字数约束渐进退役 | - | ★ | 中 | 待 critic 跑通后启动 |
- 阻塞：无
- 关键发现：
  - **写 fixture 都频繁估错字数**：Claude 自己写测试数据时反复触发 ≥50/≥30/≥20 字符违规，反向证明 LLM 字符级约束不可能可靠执行——是工具误用而非 LLM 不努力
  - **拆分本身的副产品**：S5 phase 2a / 2b 各自约束少 = 合规率高，验证了 PROGRESS 06-14 假设"不是模型能力问题，是单次输出复杂度问题"

---

## 2026-06-14 ~ 06-16（模型切换 + bug 修复 + S5 复杂度问题识别 + 流水线优化规划）
- 完成：
  - **模型切换**：Doubao-Seed-2.0-lite → MiMo-v2.5-pro（1T 参数、42B 激活、1M 上下文），`.env` 更新 API key / base_url / model
  - **profile.sources bug 修复**：`_collect_single` 内部 try-except `_extract_profile`，LLM 抽取失败时保留 pipeline sources 构建占位 profile。新增测试 `test_extract_failure_preserves_pipeline_sources`
  - **截断上限**：100K→300K（适配 MiMo 1M 上下文）
  - **LLM_TIMEOUT**：120→240→360（MiMo analyzer 4 竞品实测 ~239s，卡着 240s 上限）
  - **narrative 竞品过滤约束**：prompt 硬约束"只讨论用户指定竞品"（修复 FlowUs 等额外竞品出现在报告中）
  - **venv 重建**：项目目录更名 PentaScope 后 venv 硬编码路径修复
  - **S2 真实跑通**：trace 20260616-182636，quality_score=0.821（MiMo 下最高分），analyzer 首次 240s 超时重试后成功
- 进行中：无
- 下一步（TODO，按优先级）：
  1. **S5 场景结构优化**（当前优先）：S5 payload schema 复杂度过高，单次 LLM 输出几千字 JSON 无法稳定合规。优化方案：拆分多次小 JSON + ValidationError 反馈修正
  2. **分层模型调用**：不同 Agent 用不同模型（collector/analyzer 用快模型，writer narrative 用强模型）。需 Cooper 调研模型选型后实施。架构改动小（~3 文件/30 行），不影响 Agent 内部逻辑
  3. **analyzer 并行拆分**：4 竞品拆 2×2 并发，总耗时从 ~240s 降到 ~120s
  4. **collector 信息收集优化**：多次搜索+不同关键词，需先验证 ROI
- 流水线优化方案清单（备忘）：

  | 方案 | 提速 | 提质 | 改动量 | 状态 |
  |------|------|------|--------|------|
  | 分层模型 | ★★★ | ★★★ | 小 | 待模型选型 |
  | analyzer 并行 | ★★★ | - | 中 | 待实施 |
  | ValidationError 反馈 | ★★ | ★★ | 小 | 待实施 |
  | S5 payload 拆分 | - | ★★★ | 中 | 待实施 |
  | prompt 精简 | ★ | - | 中 | 待评估 |

- 阻塞：无
- 关键发现：
  - **S5 是唯一反复失败的场景**：Doubao 1/1 PASS 靠 fix20 兜底，MiMo 0/3 PASS。S1~S4 两种模型都能过
  - **MiMo analyzer 比 Doubao 慢 2-3 倍**：Doubao 4 竞品 93s，MiMo 4 竞品 239s
  - **每次 LLM 调用完全独立**：无对话历史、无 session，Agent 间上下文通过 LangGraph state 传递。分层模型不会丢失上下文
  - **completeness 评分机制问题**：硬编码 4 项扣分，占位 profile 硬编码 0.0 而非走公式；S5 query 策略与 completeness 维度不匹配

---

## 2026-06-10（前端美化 + 报告导出，brainstorming → doubt → plan → execute 全流程 + 7 轮验收修复）
- 完成（单 session、严格 brainstorming → doubt-driven 双轮 → writing-plans → executing-plans 全流程 + 验收阶段 7 个 bug Prove-It 修复，**26 个 commit + S2 真跑 quality_score=0.650 happy path**）：
  - **brainstorming**：Cooper 7 条澄清问题 + 3 trade-off 决策（Loading 路径 / emoji 策略 / HTML 字体策略）→ spec v1 落盘
  - **doubt-driven 双轮**：单模型 code-reviewer agent 20 条 + 跨模型 codex (azure_openai/gpt-5.5) 15 条 → 合并去重 6 critical / 12 major / 7 minor
  - **跨模型独占发现 critical（C5）**：HTML 导出 narrative→html 必须 sanitize / autoescape，否则 stored XSS。这条单模型完全漏掉，再次验证「双轮 doubt-driven 不冗余」（继 06-08 v3 spec 的 source_urls 字段独占发现后又一次跨模型独占 critical）
  - **Cooper 6 条产品决策（PD-1~6）**：Loading 阶段化放弃 / markdown 字段宽松覆盖 / KPI 5 卡含 confidence_level / HTML 全内嵌 / emoji 选择性纯化 / inspector ~5-6 行软目标。**额外范围决策选 b**：仅做主题色 + 导出，舍弃场景卡重做 + Loading 阶段化（避开 C2/M3 风险）
  - **spec v2 重写**：v1 670 行减为 v2 ~500 行（范围收敛）；6 critical / 12 major 全部覆盖或显式标 v2 范围外
  - **plan 18 task**：file/function 级别拆细
  - **execute 18 task**：18 commits 干净到位（schema → inspector → 依赖 → theme.py → app.py → render.py KPI/section/action/导出按钮 → exporters 包 → markdown.py → routes export → html.py + 模板 → 各类测试）
  - **验收阶段 7 轮 Prove-It 修复**：
    1. **fix22**：theme.py `st.markdown(unsafe_allow_html=True)` 改 `st.html()`（CommonMark type 6 HTML block 遇空行截断 `<style>` 块，CSS 文本作为可见内容显示）
    2. **fix23**：导出按钮删 Material Symbols `<span>download</span>`（Streamlit iframe 字体 ligature 失效字面 download 字母透出）+ KPI 5 卡 flex 等高（`min-height:120px` + `flex-direction:column` + `justify-content:space-between` + sub `min-height:1.4em` 保 5 卡严格对齐）
    3. **fix24**：导出按钮加 `text-decoration: none !important`（Streamlit 默认 `a` 选择器优先级高过 `.btn-export`）+ 「一图看懂」改「核心要点」+ 执行摘要子标题去英文（`背景定位 Context` → `背景定位`）+ 附录加「参考资料」小节（扫全报告 source_refs 收集去重链接）
    4. **fix25**：`_collect_all_references` 改通用递归（原 5 处枚举漏 5 场景 payload 内嵌 source_refs，~20+ 个嵌套位置）—— `_walk(dict_or_list)` 遇任何节点含 `source_refs` 或 `data_sources` 就提取，无论嵌套多深都 cover
    5. **fix26**：HTML 导出 narrative markdown 标签被 Jinja2 autoescape 二次转义（`<h3>` 显示为字面 `&lt;h3&gt;`）—— `_safe_markdown` 返回值改 `markupsafe.Markup` 标记可信 HTML（nh3 已 sanitize 单层防护够用）
    6. **fix27**：KPI 第 4 张卡「数据源数」→「参考资料」（跟附录小节名对齐）
    7. **fix28**：rebase 远程 11d65cc 后顺手修 ruff F541
  - **关键技术修复（v1 doubt-driven 暴露的 6 critical）**：C1 前端 import 路径 / C5 stored XSS sanitize / C6 markdown/jinja2/nh3 加 requirements / M1-M2 导出走直链 a download / M9 markdown 5 场景常用字段覆盖（PD-2 宽松）
  - **Latent issue 识别但 v2 范围外**：03_report.json 落盘的 quality_score 永远 None（writer 节点先于 inspector 落盘）—— v2 KPI 卡通过 /analyze 实时返回的内存对象拿到分数，绕过此问题
  - **新增文件**：3 个新代码文件（theme.py / exporters/markdown.py / exporters/html.py）+ 2 个字体 woff2（PlusJakartaSans + FiraCode latin 子集）+ 1 个 Jinja2 模板（report.html.j2）+ 8 个测试文件（exporters_markdown / exporters_html / exporters_html_xss / export_path_traversal / inspector_raw_quality_score / emoji_lint / integration/export_e2e / kpi_strip_visual + render_visual_polish + frontend_theme）
  - **改动文件**：6 个（schemas/report.py 加 raw_quality_score / agents/inspector.py cap 前回填 / api/routes.py 加 export 路由 / frontend/app.py 调 inject_theme / frontend/render.py 加 KPI/卡片/导出按钮 + 4 处视觉打磨 / requirements.txt）
  - **测试增长**：387 → **445 passed**（+58 测试 / 5 skipped / 2 xfailed 不变 / ruff clean）
  - **真实跑通**：S2 trace `20260610-070926-2c23fb`，跑 4 个 AI 代码生成工具竞品（Cursor/Devin/通义灵码/GitHub Copilot），collector 平均 completeness=0.79，writer phase 3 第 2 轮 6/6 全成功（无 placeholder 降级）→ **quality_score=0.650 raw 真实分（无 cap 触发）**，coverage=1.00 满分
  - **测试**：445 passed / 5 skipped / 2 xfailed / ruff clean
- 进行中：本 session 收尾 + push
- 下一步：
  1. push origin master 同步 26 个 commit + 文档
  2. 项目介绍材料（PRD / DECISIONS / README，本次 + 06-09~10 总计 28 个 fix 是「反馈闭环 + 容错降级」实证素材）
  3. 后续迭代：profile.sources=0 旧 bug（collector 抓回来的 URL 没持久化到 profile.sources，writer 阶段 LLM 自己从语料摘 5 条入 metadata.data_sources）—— 不影响主流程，留作下个 session 修
- 阻塞：无
- 协作模型实证：
  - **doubt-driven 双轮再次验证不冗余**：跨模型 Codex 抓到单模型完全漏掉的 stored XSS critical (C5)
  - **systematic-debugging skill 实战后判定停用**（feedback_bugfix_skills.md 已记入项目记忆）：4 阶段流程对单 1 行 bug 太重，Cooper 反思后选只用 Prove-It Pattern；根因分析自己脑子里做即可，不实例化为流程
  - **Prove-It Pattern 强度**：本 session 验收阶段 7 个 bug 全部走「先红测试 → 修 → 测试绿 → 全套零回归」，58 个新测试全过、ruff clean
  - **PD 抽象**：6 条产品决策清单 + 1 条范围决策让 Cooper 1 次拍板进 spec 重写；Cooper 看实测数据（confidence_level high=80%）后修订 PD-3 选择 a 而非 b
- 安全提醒：本 session 全程纯代码 + 字体 woff2 资源 + nh3 sanitizer 依赖，无新增 key

---

## 2026-06-09 ~ 06-10（端到端测试 + 21 个 fix 大规模 bug 修复 session）
- 完成（单 session、systematic-debugging + agent-skills:test Prove-It pattern 严格模式）：
  - **5 场景端到端跑通**：S1/S2/S3/S4/S5 各跑出 03_report.json，**3 个 happy path（S2 真跑 0.800 / S3 0.836 / S5 fix20 兜底后跑通）+ 2 个 max_retries 反馈闭环正常路径（S1 / S4）**
  - **21 个 fix 全部 Prove-It 模式（先红测试 → 修 → 测试绿）**，每个 fix 平均 2-3 个新单测：
    - **fix1**：collector labeled_text 100K 字符硬截断 + 每场景 1 条 query（避免 Doubao 224K token 上限）
    - **fix2**：writer ValidationError 详情持久化到 trace_writer.save_raw → `04_writer_error.json` 含完整 errors() 列表
    - **fix3**：前端 `render_analysis_response` 对 report=None 友好提示，不再裸调 render_base_report 触发 KeyError
    - **fix4**：writer phase 2 通用 `SCHEMA_FIELD_CONSTRAINTS` 块注入到 5 套 payload prompt
    - **fix5**：writer phase 2 内部重试 max_retries 1 → 2，给 LLM 更多次修字段错位机会
    - **fix6**：前端 session_state 持久化 last_response，「加载追溯」等按钮重跑不再丢失主报告
    - **fix7**：analyzer 场景失明根治——`analyze()` 入参增 `scenario_input`，prompt 加场景上下文块（SWOT 主体按 S1-5 分支约束）
    - **fix8**：writer phase 4 `data_sources.accessed_at` 用 profile.collected_at 兜底（之前全 None）
    - **fix9**：phase 4 Appendix.glossary 预填 11 条常用术语（JTBD/SWOT/Tier1/TAM/SAM/SOM/MQ/ARR/ICP/niche/niche_focus）
    - **fix10**：S2 payload prompt 全文按 schema 重写（修 unit/value_basis/market_role/recommended_mode/impact_on_entry 5 处枚举错位）+ 末尾枚举速查清单
    - **fix11**：phase 4 Methodology.data_collection_approach 改代码合成模板（含场景标签+竞品名+URL 数+时间窗+完整度），不再依赖 LLM 写够 200 字
    - **fix12**：writer_node 入口检测 analyzer 失败 skip 兜底（避免 state.analysis 缺失触发 KeyError 污染反馈闭环）
    - **fix13**：narrative prompt 加 markdown 段落约束（段落空行 / `### 子标题` / 列表 / `**加粗**` / 英文术语中文注释）
    - **fix14**：S3 prompt 修 `expected_arr_uplift_basis` 4 个枚举错位 + `pricing_page_audit.rule_name` 8 枚举 + 末尾枚举速查 + 高频踩坑提示
    - **fix15**：S4/S5 prompt 补遗漏枚举（S4 `MonitoringOpportunity.estimated_effort/expected_impact` / S5 `WhiteSpaceZone.quadrant`）
    - **fix16**：追溯面板「报告」tab 用 `render_trace_report_tab` 渲染美化版报告 + 折叠原始 JSON
    - **fix17**：S4 prompt 给 threats/opportunities/battlecards 显式补 `artifact_id` 必填提示（否则 LLM 反复漏写）
    - **fix18**：S5 prompt `category_strategy` 从「Optional」改为「**必填**」+ 列子字段 chosen_category/why_this_category/competitors_implied
    - **fix19**：S5 prompt 末尾加「S5 枚举速查」+「S5 高频踩坑」清单（vendor_profiles 数量字数、轴标签 ≥2 字、三方 competitor_name 一致性等）
    - **fix20**：S5 normalizer 代码层兜底 3 大顽固坑（vendor_profiles.strengths < 2 复制凑齐 / 单字轴标签补字 / category_strategy 空 dict 占位填齐）—— **特别标注[LLM-CAPABILITY-WORKAROUND]，迭代时换更强 LLM 后应优先撤回**
    - **fix21**：前端 PositioningStatement 6 位模板分行 markdown 列表渲染 + AI 推断水印独立 `st.warning`
  - **测试增长**：311 → **387 passed**（新增 76 个，5 skipped / 2 xfailed 不变；ruff clean）
  - **核心方法论实证**：
    - `superpowers:systematic-debugging` 4 阶段（根因→对照→假设→修复）防止凭直觉乱改 bug；首次实战在 LLM JSON 解析问题上避免误诊（最初猜反斜杠，systematic 流程后定位真因是 OpenAI client 内部 retry × 外层 retry 嵌套放大 9× × 120s timeout = 18 分钟最坏耗时）
    - `agent-skills:test` Prove-It pattern 21 次零回归零 false-fix
    - 多个 fix 之间的因果链：fix12 兜底依赖 fix5 路由不污染、fix11 兜住的字段 fix13 prompt 又加约束、fix20 占位水印 fix21 前端分离展示
  - **5 场景战报**：

    | 场景 | trace | quality_score | passed | 备注 |
    |---|---|---|---|---|
    | S1 | 184652 | 0.65 | False (max_retries) | 反馈闭环正常路径 |
    | S2 真跑 | 203430 | **0.800** | **True** | happy path |
    | S2 错跑 | 212413 | 0.500 | False | placeholder cap |
    | S3 | 220309 | **0.836** | **True** | happy path 最高分 |
    | S4 | 222633 | 0.517 | False (max_retries) | inspector 严苛 |
    | S5 | 004549 | 0.500 | False (max_retries) | fix20 兜底 + 2 占位 |

- 进行中：本 session 收尾，commit + push
- 下一步：
  1. 项目介绍材料（PRD / DECISIONS / README，本次新增的 21 个 fix 可作为「反馈闭环 + 容错降级」实证素材）
  2. 后续迭代：换更强 LLM（Doubao-Seed-2.0-pro / GPT-4o）后**优先撤回 fix20**（见 DECISIONS.md），避免水印污染报告
  3. 可选优化：narrative section 占位率仍较高（S5 perceptual_map_analysis / errc_analysis 两次都占位）—— LLM 能力问题，prompt 改进边际收益已趋零，等换模型再观察
- 阻塞：无
- 协作模型实证：
  - **systematic-debugging + Prove-It 双流程严格执行**有效杜绝 bug 修复中"修一处错另一处"的状况
  - **doubt-driven 不复用**——本 session 没用 doubt-driven 前置审查（修 bug 而非新设计），systematic-debugging 已经覆盖根因分析需求
  - **monitor 流式事件**作为长任务可观测性的标配，本 session 21 次端到端跑都靠 monitor 抓节点切换 + WARNING/ERROR 实时定位
- 安全提醒：本 session 全程纯代码 + prompt + 测试，无新增 key

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
  3. 准备项目介绍材料（PRD / DECISIONS / README）
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
  1. 【可观测性】修日志落盘：setup_logger 写了但从未被调用，logs/app.log 不生成；agent/graph 的 INFO/WARNING 日志（[graph] → collector、采集源成败、completeness）全部丢失。需在 api 启动时初始化 logger 并配置 root level，让全链路日志可见。
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
  - 项目立项研究（产品定位 / 业界标杆调研）
  - lark-cli 安装验证、飞书认证、lark-cli skill 清理
  - PRD 撰写（产品定位、Schema 设计、4 Agent 角色定义、数据源、信息溯源、可观测性）
  - 项目文档结构整理（docs/ 分离项目内容与开发过程文档）
  - 开发计划制定（11 天极限计划，5/30-6/10）
- 进行中：PRD 待 Cooper 审阅确认
- 下一步：技术方案设计 + 项目骨架搭建（LangGraph hello world）
- 阻塞：无
