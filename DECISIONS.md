# Technical Decisions

项目关键技术决策记录。每个决策包含选择、理由和被排除的备选方案。

> 决策会直接影响后续代码实现，比进度信息更重要。

## Format

```markdown
## YYYY-MM-DD: 决策标题
- 选择：...
- 理由：...
- 备选：...（排除原因：...）
```

---

## 2026-06-19: max_tokens 基于 finish_reason 实证调参（不拍脑袋）

- 选择：**每个调用点的 max_tokens 必须基于 finish_reason 日志硬证据调整，不凭直觉猜**
- 理由：06-19 上午 session 讨论 max_tokens 时反复矛盾（Cooper 三次反问拽回），最终加 finish_reason 日志后用数据说话——实测 phase 1 撞 4096 两次 / phase 2 撞 8192 一次 / phase 3 4051/4096=99.9%。调参依据是"实测消耗 + 50% 余量"而非"觉得够用"
- 最终值：phase 1=6144 / phase 2=12288 / phase 3=8192 / analyzer+critic=8192 不变 / collector=无限制
- 备选（一律调到 16384 省事）：浪费 token 预算、增加响应时间、某些端点可能不支持过大值

## 2026-06-19: narrative 轻重试（1 次串行重试再占位）

- 选择：phase 3 gather 后对 Exception 项**逐个串行重试 1 次**，仍失败才占位降级
- 理由：06-18 实测确认 narrative 失败率 ~17% 是偶发抖动（同 section 重跑就过），占位会触发 placeholder cap 0.5 → 整轮报废。轻重试最坏增加 N_failed×30s
- 备选 a（并行重试）：可能再次打满并发压力导致更多失败
- 备选 b（增加首跑重试次数）：增加全链路 LLM 调用数，撞熔断风险
- 实战验证：S5 跑通 positioning_statement_analysis 首次失败 → 重试成功 → 6/6 全通过 → quality_score 0.900

## 2026-06-19: JSON 解析三次兜底链（反斜杠 → 未转义双引号 → 放弃重试）

- 选择：json.loads(strict=False) → 反斜杠兜底 → **未转义双引号状态机修复** → 抛错走 attempt 重试
- 理由：历次 36 次 JSON 失败中 7 次（19%）是字符串值内 ASCII 双引号未转义（LLM 用"引用"含义），状态机判断后跟非 JSON 结构字符的 " 替换为中文引号。实现简单、副作用低
- 备选（prompt 层要求不用双引号）：LLM 不可靠遵守此类格式约束，不如代码层兜底
- 边界：状态机不是万能的——如果 LLM 输出的结构性破坏更深（如整段 JSON 格式混乱），仍会走 attempt 重试

---

## 2026-06-19: 架构级 spec 必须走 cross-model doubt-driven，author self-review 不可靠

- 选择：**任何架构级 / 数据流改造级 spec（如 critic / 大重构）落盘前，必须用 codex CLI 做至少 1 轮跨模型 doubt-driven 审查**
- 理由：实证 author bias 极强——LLM-as-critic spec v1 落盘后我自己 self-review 只发现 1 处问题（max_tokens retry 笔误），cross-model codex GPT-5.5 同 spec 发现 33 条；v2 self-review 0 处遗漏，cycle 2 又发现 22 条；v3 self-review 0 处遗漏，cycle 3 又发现 20 条。**3 轮 75 条问题，自我审查只能找到不足 2%**。author bias 不是注意力问题，是结构问题——作者把"决策"当"事实"，把"想得清楚"等同"实施可行"，跨章节接口不一致 / 类型签名漂移 / 边界条件遗漏都看不见
- 备选 a（只 self-review，节省时间）：实证不靠谱——v3 之后又有 5 个 critical 是 spec 自相矛盾或代码不可执行，self-review 全漏
- 备选 b（每轮都 brainstorming + doubt-driven，包括小 spec）：成本过高——bug fix 级 / 单文件级修改 self-review 够用，三轮 doubt-driven 应该限制在"架构级"和"数据流改造级"
- 适用边界：
  - **必须走**：新增 agent / 改 graph 拓扑 / Schema 大改 / 新评分系统 / 反馈闭环改造
  - **不必走**：单文件 bug fix / 测试 fixture 修订 / prompt 文字微调 / 命名重构
- 操作指引：用 `codex exec --sandbox read-only -C <repo> - < prompt.md` 经 stdin 喂 prompt（避免 shell 转义），prompt 含 ARTIFACT + CONTRACT 但**不传 CLAIM**（避免引导审查者认同）
- 关联记忆：`feedback_proxy_metric_bias.md`（看到代理失效就想换代理是 author bias 同根问题）

## 2026-06-19: critic_failed 走 terminal 路由不消耗 max_retries

- 选择：critic 失败时强制生成 `FeedbackIssue(agent="end", severity="critical", dimension="critic_failed")`；builder.py `_should_continue` 加 `agent="end"` 特判直接 `return "end"`，不增 retry_count
- 理由：critic 系统故障（LLM timeout / JSON parse error / input builder 异常）跟 writer 内容缺陷无关——让 writer 重写不能修复 LLM API 故障，反而消耗 max_retries 预算让真正可恢复的内容问题没机会重试
- 备选 a（agent="writer" + major）：cycle 2 v3 的方案，cycle 3 codex 抓出"writer 重写解决不了系统故障"的根本问题
- 备选 b（agent="inspector" + major）：v2 方案，graph 路由会形成 inspector→inspector 循环（cycle 2 codex 抓出）
- 备选 c（不生成 issue 让 passed=True）：错——critic 失败的报告不应被当作合格通过
- 实施位置：`src/agents/inspector.py::_safe_minimal_fallback` + `src/graph/builder.py::_should_continue`

## 2026-06-19: 字数约束分阶段退役 + critic 是退役前提

- 选择：字数 schema 约束（`Field(min_length=N)`）退役按 5 阶段，critic 落地是阶段 1（前置必修），不能反过来
- 理由：直接删字数约束会让"长但空"的 LLM 输出无人管；必须先有 LLM-as-critic 接管"内容是否够具体"的判断，再逐字段评估字数约束"实际拦住的是什么"，拦"水且违规"才保留，拦"真但不合规"或"水但合规"则删
- 5 阶段：
  - 阶段 1：critic 设计 + 落地（本期 spec / plan）
  - 阶段 2：跑 2-3 次端到端校准 critic 准确度（手动 eval）
  - 阶段 3：分批退役 ≥10 / ≥20 小约束
  - 阶段 4：退役 ≥50 / ≥100 大约束（字数 ValidationError 高发区）
  - 阶段 5：保留上限约束（≤200 防 token 爆炸）+ 结构约束（必填 / 数量 / 枚举），永久不动
- 备选 a（一次删完字数约束）：风险高，没 critic 接管会让报告质量崩
- 备选 b（永远保留字数约束）：与 OPEN_QUESTIONS Q-2026-06-17-字数约束 决策矛盾——字数代理失效是已确认根因
- 范围控制：本 PR（critic 实施）严禁修改任何 schema min_length / max_length 字段（spec v4 验收 7 + Task 18 影响面脚本验证）

## 2026-06-19: quality_score 限定为 semantic 分，programmatic 通过 passed 阻断

- 选择：critic 4 维加权后的归一化分作为 `metadata.quality_score`，**不再** 把 programmatic critical/major 计入分数；programmatic issue 通过 `passed = not any(severity in {critical, major})` 阻断，并在 `quality_score_calculation_note` 加 `prog_issues=N critical / M major` 计数让追溯可见
- 理由：v3 删除 inspector_pass_rate 三项后留下漏洞——schema 外硬查失败的报告 critic 给 4 分仍能拿 1.0 quality_score（cycle 3 codex 抓出）。修法分两路：(a) 让 programmatic 也降分（恢复部分旧逻辑）；(b) 明确 quality_score 是"semantic 分"语义，programmatic 走 passed 通道。选 (b) 因为信号纯净 + 反馈闭环已经能阻断
- 备选 a（programmatic 降低 quality_score）：跟 critic 双重计算，破坏"critic_score 完全替换三项"的设计干净度
- 备选 c（新增 semantic_quality_score 字段并存）：metadata 复杂度上升，前端要展示两个分

---

## 2026-06-10（前端美化 + 报告导出 session）: 6 个产品决策 + 7 个技术决策

### 6 个产品决策（PD-1 ~ PD-6）

#### PD-1: Loading 阶段化放弃，仅 spinner + 静态文案
- 选择：保留默认 `st.spinner("正在分析中...")`，不做 4 阶段进度条
- 理由：CONTRACT 3「演示期间用户能看到运行进度」与现有 trace_writer 时序不兼容——文件 mtime 是阶段**完成**时间不是开始/进行中时间，且 graph 运行期间 meta.json::node_trace / retry_count 都不写入；要做实时进度需改后端 routes.py 拆 /analyze/start + 加心跳，与「不动 graph 拓扑」目标矛盾。中文用户 demo 场景下不会发现差异
- 备选 a（保留 + 后端拆 /analyze/start + node 心跳）：实时进度最佳，但工时 +0.5 天 + 改后端契约
- 备选 c（仅轮询 status 不拆 4 阶段）：折中方案，仍有"伪进度"嫌疑
- doubt-driven 跨模型 Codex 锁定 C2-C4 三个 critical 都源于此根因，是范围决策的关键

#### PD-2: markdown 导出宽松字段覆盖（关键字段，非全字段）
- 选择：每场景渲染常用字段 + 单测断言关键字段；放弃 CONTRACT 4「no field omission」
- 理由：5 场景 schema 嵌套深（如 S3 pricing_page_audit 8 法则、S2 competitor_recommendations 含 PESTEL）；全字段覆盖 +0.5-1 天，但 1 万字 markdown 用户不会盯每个嵌套字段
- 备选 a（严格全字段）：未来扩展不漏，但工时翻倍

#### PD-3: confidence_level 上独立 KPI 卡（5 张布局）
- 选择：KPI 由 4 张改 5 张，含 confidence_level 独立卡 + raw_quality_score 字段保留 cap 前真实分
- 理由：confidence_level 是「输出可信度」核心展示位；查近 5 trace 实测 high=80% 但仍是产品硬指标必须独立位
- 备选 b（合入场景标签卡作副信息）：节省一卡位，但失去强可见性
- raw_quality_score 配套：ReportMetadata 加新字段（5 行），inspector cap 前回填（1 行）；KPI 卡先显 raw 再附「cap 后 X.XX」副信息，让用户看到 cap 前 vs cap 后真实差

#### PD-4: HTML 全内嵌（字体 + Plotly + CSS）
- 选择：字体 woff2 base64 + Plotly include_plotlyjs=True + CSS inline 全部内嵌单 HTML，单文件 3-5MB
- 理由：演示环境断网风险（CDN 加载失败 → 字体回退 + Plotly 图表全空白）对核心卖点冲击大；3-5MB 文件大小可接受
- 备选 a（CDN，spec v1）：100KB 文件但断网失效
- 备选 b（仅 Plotly 内嵌）：折中，字体仍 CDN 失效但图表可用
- 字体子集选 latin（不含中文）：Plus Jakarta Sans + Fira Code 是英文标题/数字字体，中文走 system stack fallback；woff2 latin 子集 25KB 远小于全字符 200KB+

#### PD-5: emoji 选择性纯化（标题/导航换 Material Symbols；KPI/badge/状态点保留 emoji）
- 选择：标题 / 导航 / 剩头 emoji 全换 Material Symbols；KPI/badge/状态点 emoji 保留
- 理由：UI/UX Pro Max skill 标"no-emoji-icons"是西文 ASCII 设计语境的最佳实践，但中文用户 demo 场景下 🟢🟡🔴 状态点比扁平 Material circle 语义识别更快；视觉一致性的代价超过收益
- doubt-driven 后期 Cooper 反转：看了 git history 后发现 7 处 emoji 是 06-08 既有设计 + 1 处本 session 新增，全保留更省事
- 备选 a（全量纯化）：Material circle 颜色严格匹配主题色 #16A34A 等，但工时高 + 实测 st.button 不支持嵌套 HTML
- 备选 c（emoji 全保留）：跟现状一致

#### PD-6: inspector 改动「~5-6 行」软目标（不强压 4 行）
- 选择：CONTRACT 1 「inspector 4 行」改为「~5-6 行」软目标
- 理由：raw_quality_score 加字段需 5 行真实代码（赋值 + cap 前赋 raw + 注释），强压到 4 行（合并赋值）牺牲可读性
- 备选 a（硬约束 4 行）：可读性下降；备选 c（不限）：CONTRACT 1 「小改动」表述失效

### 7 个关键技术决策

#### C5 修复（跨模型独占发现）：HTML 导出 narrative 必须 sanitize + autoescape
- 选择：`_safe_markdown()` 走 `markdown.markdown()` → `nh3.clean()` 三步；Jinja2 模板 `autoescape=select_autoescape(["html","j2"])`；filter `safe_md` 返回值用 `markupsafe.Markup` 标记可信
- 理由：narrative 是 LLM 生成 + 含网页爬来文本，可能含 `<script>alert(1)</script>` 之类攻击向量；nh3 strip script/iframe/javascript: URI / inline event handler；autoescape 对其他字段（title 等）防 XSS。这条单模型完全漏掉，跨模型 Codex 抓到的 critical
- nh3 vs bleach：nh3 是 Rust ammonia 的 Python wrapper，预编译 wheel for win/mac/linux，零原生编译依赖
- 备选（不 sanitize 直接 raw_html）：stored XSS 漏洞，CONTRACT 2 不引入风险依赖红线

#### C6: requirements.txt 显式加 markdown / jinja2 / nh3
- 选择：requirements.txt 显式加 3 个依赖；不依赖 fastapi 传递依赖
- 理由：spec v1 假设「jinja2 已是 fastapi 传递依赖、markdown 已在 requirements」**完全错** —— 实测 markdown / nh3 都不在；jinja2 是 fastapi 间接依赖但稳健做法是显式
- 备选（不加，靠传递依赖）：将来 fastapi 升级断依赖链就崩

#### theme.py 用 st.html() 不用 st.markdown(unsafe_allow_html=True) 注入 `<style>`（验收阶段发现）
- 选择：`inject_theme()` 走 `st.html(_THEME_CSS)`
- 理由：`st.markdown(unsafe_allow_html=True)` 经 CommonMark/GFM markdown 引擎处理，type 6 HTML block (`<style>`) 遇连续空行被判定为 block 结束，剩余 CSS 文本回到 markdown 解析模式被当可见文本输出（Cooper 截图实证）
- st.html 直接走 sanitized HTML 注入路径，是 Streamlit 1.33+ 注入 `<style>` 的官方方式

#### 导出按钮 inline `<a download>` 而非 st.download_button（M1 修入）
- 选择：`st.markdown('<a href="..." download class="btn-export">导出 Markdown</a>')` 直链
- 理由：`st.download_button` 要求 data 已 materialized（不接受 lazy callable）；HTML `<a download>` 让浏览器直接调后端 GET /export 路由，零前端预拉，单点击即下载
- CSS 必须 `text-decoration: none !important`（Streamlit 默认 a 选择器优先级高过 .btn-export，普通 `text-decoration: none` 不生效，下划线仍显示）

#### 参考资料扫描通用递归（不显式枚举字段）
- 选择：`_collect_all_references` 用 `_walk(dict_or_list)` 通用递归，遇任何节点含 `source_refs` 或 `data_sources` 就提取
- 理由：原 5 处显式枚举（metadata/key_findings/analysis_sections/swot/recommendations）漏 5 场景 payload 内嵌 source_refs（~20+ 嵌套位置）；schema 全部统一 `source_refs` 命名（10 个 schema 验证），递归方式无论嵌套深度都 cover；未来 schema 加新嵌套字段自动 cover
- 备选（显式枚举）：每加一个 scenario / 嵌套字段都要改代码，遗漏风险高

#### markupsafe.Markup 包裹 _safe_markdown 返回值（Cooper 验收发现）
- 选择：`_safe_markdown` 返回 `markupsafe.Markup(cleaned_html)` 而非 `str`
- 理由：Jinja2 autoescape=True 会把 `str` 类型当不可信文本二次转义，`<h3>` → `&lt;h3&gt;`；`Markup` 标记可信，autoescape 不再二次转义；nh3 已做完整 sanitize，单层防护够用
- 备选（关 autoescape）：失去对 title / scenario 等字段的 XSS 防护，C5 防线削弱

#### KPI 卡 CSS flex 等高（Cooper 验收发现）
- 选择：`.kpi-card { display: flex; flex-direction: column; justify-content: space-between; min-height: 120px }` + `.kpi-card-sub { min-height: 1.4em }`
- 理由：sub 字段长短不一（"高 18 中 6 低 0" vs ""）导致 5 卡 div 自然高度差；flex + min-height 强制 5 卡严格等高、内部 label/main/sub 垂直均布

### 已停用的 skill：systematic-debugging（实战后判定）

- 选择：本 session 验收阶段调用了 `superpowers:systematic-debugging` skill 一次（修 CSS 文本可见 bug）后，Cooper 判定「太重」→ 后续 7 个 bug 全部仅用 `agent-skills:test` 的 Prove-It Pattern，systematic-debugging 不再调用
- 理由：流程 4 阶段（根因 → 模式 → 假设 → 实施）对单 1 行 bug 是过度工程；3 个结构性测试是「常量字符串属性测了等于没测」；流程鼓励形式主义。Prove-It 写测试是动作纪律不是流程纪律，5-10 分钟成本高收益
- 项目记忆 `feedback_bugfix_skills.md` 已记录该决策

---

## 2026-06-08（深夜 / E-G 实施）: 5 个关键技术决策

### D3 修复 3 Critical（异常路由 + S2 推荐去重 + 路径穿越校验）
- 选择（C1 异常路由）：在 writer_orchestrator.py 引入三个自定义异常类 WriterRouteToCollector / WriterRouteToWriter / WriterRouteToEnd（皆继承 RuntimeError），把 6 处 raise RuntimeError 全数换成对应子类；builder.py writer_node 用 isinstance 顺序判（End→Collector→Writer→兜底 RuntimeError），WriterRouteToEnd 设 feedback.passed=True 强制 should_continue 走 end 分支
- 理由：原实现用中文措辞子串匹配（"URL whitelist" / "scope" / "构造"）路由 LLM quota 超限和 scope 不可构造错误，code reviewer 实证"纯属侥幸命中"；自定义异常类用 isinstance 判脱离措辞依赖、可静态校验
- 6 处 RuntimeError 替换映射：profiles 0 个 URL → Collector / LLM quota 超限 → End / phase 3 半数闸门 → Collector / final_urls 空 → Writer / S2 scope 全空 → End / scope 无法构造 → End
- 选择（C2 S2 推荐合并）：移除 recommender_node 把推荐竞品名合并到 user_input.competitors 的逻辑，让 WriterOrchestrator phase 4 的 union 成为唯一合并点；collector_node 同步改为自行 union（ui.competitors + state.competitor_recommendations.recommended_competitors，按 name 去重）
- 理由：v3 spec 593 行 phase 4 union 是 S2 scope 构造的官方位置；recommender_node merge 让 phase 4 的 + rec_names 变成 dead path，spec 偏离 + 数据流双重；collector_node 自行 union 保持 ui = 用户原始输入不被改写
- 选择（C-new 路径穿越校验）：_load_prior_report_data 函数顶部加 ^[a-f0-9-]+$ 白名单 + 长度 ≤64 + 空值/None 早返；任何非法 trace_id 拒绝 + log warning
- 理由：prior_trace_id 来自前端用户输入，未做合法字符校验直接拼 RUNS_DIR / prior_trace_id，可能逃逸（如 ../../etc/passwd）。reviewer 标 Critical

### E1 quality_score 三项加权公式（复用作废 worktree A 的算法设计）
- 选择：实现 src/agents/quality_score.py 三项加权——source_coverage（BaseReport 4 类条目带 source_refs 的占比，包括 key_findings/analysis_sections/recommendations/swot.entries）+ confidence_avg（metadata.data_sources 各 confidence 数值化平均，high=1.0/medium=0.6/low=0.3）+ inspector_pass_rate（1.0 - sum(severity_penalty), clamp[0,1]，critical=0.4/major=0.2/minor=0.05）；三项各 1/3 等权，缺项时剩余项重新归一化；最终 score round 到 3 位
- 理由：v3 spec 锁定 confidence_level 由 writer phase 4 派生（数据采集面），quality_score 由 inspector 一次性回填（报告内容面）；R-22 强调二者独立。三项设计正好覆盖"溯源完整度 + 数据可信度 + 内容质量"三维。算法本身与作废 worktree A 接口假设无关，可放心复用
- 备选 a（按 issue 严重度倒推单一公式 1.0 - sum(penalty)）：master 旧实现已采用，但忽略采集质量 + 来源完整度（排除）
- 备选 c（spec 说"按 issue 总数动态算满分"）：单 critical 和 10 个 critical 落同区间不合理（排除）

### E2 inspector dispatcher 通过 globals() 间接查找
- 选择：dispatcher 不预定义 _DISPATCHER dict，而是 `globals().get(f"_check_{scenario.lower()}")` 间接查找
- 理由：测试用 monkeypatch.setattr 替换单个 _check_sX 时，预定义 dict 已绑死函数引用 monkeypatch 替换不到；间接查找让每次调用查 globals()，monkeypatch 生效
- 备选：每个测试参数化时手动重建 dict 或用 mock dict（排除：测试样板代码冗余）

### E3 quality_score cap 0.5 触发（v3-R17 锁定）
- 选择：inspector.inspect 在 calc_quality_score 之后检查 metadata.warnings 是否含 placeholder_section: / placeholder_swot / dropped_unverified_entries: 三类前缀，含则强制 cap 到 0.5
- 理由：v3-R17 spec 明确"writer 写 placeholder warnings 时 inspector 必须降分到 ≤0.5"；这是硬指标不是建议
- 实现细节：cap 仅在 score > 0.5 时触发，note 追加 "; capped to 0.5 due to placeholder warnings (v3-R17)" 便于追溯

### F1 前端拆出 src/frontend/render.py 模块
- 选择：BaseReport + scenario payload 渲染逻辑全部拆到 src/frontend/render.py（~600 行），app.py 仅调用入口 render_base_report()
- 理由：渲染代码量 ~150-600 行（F1+F2+F3 累加），全堆 app.py 会突破 600+ 行单文件可读性；render.py 独立可测、关注点分离
- 备选：所有渲染塞在 if data["status"] == "completed" 分支里（排除：单文件膨胀难维护）

### G1 E2E mock 策略（不造完整 LLM JSON fixture）
- 选择：mock 5 个 agent 类的核心方法（collect / analyze / write / inspect / recommend）为 AsyncMock，writer 直接返回预制合法 BaseReport，inspector 用真 calc_quality_score 但绕过 _programmatic_checks（避免 _check_sX 触发图重试递归到 GraphRecursionError）；不造 5 套合法 LLM JSON fixture（每场景至少 LLM 调用 12 次，写完整 fixture 工作量 1500+ 行）
- 理由：G1 E2E 真正的独特价值是"graph 拓扑装配 + scenario 路由 + state 传递契约"，agent 内部逻辑已被 unit test 覆盖；mock 到 agent 方法层够用，不必再造一遍 LLM JSON
- 实施代价：BaseReport fixture 仍要满足 schema min_length 等硬约束（_LONG 通用占位常量统一）；schema 的 min_length=20/50/100 字段防 LLM 占位敷衍是合理设计但对测试 fixture 是负担——本次接受
- 备选：mock 整个 BaseReport 为 MagicMock(spec=BaseReport)（排除：失去 quality_score 真接通验证；无法验证 scenario 字段一致性）

---

## 2026-06-08（晚 / v3 spec）: writer 4 阶段编排 v2 → v3 修订（双轮 doubt-driven 复审后 28 条）
- 选择：保持 v2 已锁定的 18 条决策（C1-C9 + Q2 + P2-P3 + M1-M10），叠加 v3 新增的 28 条 reconciled 修订（11 critical + 12 major + 5 minor）。v3 spec 长度从 v2 的 433 行扩到 1014 行，新增「Pre-flight: master 适配」章节、18 处 `[v3-RXX]` 标记的修订段、完整 v3 修订日志表
- 理由（产品决策部分，6 条）：
  - **R-02 writer raise 路径选 c**：复用既有反馈闭环语义（writer raise → builder 外层 try/except → RejectionFeedback 注入 → inspector should_continue）。备选 a (内部 try/except 返回 placeholder) 让幽灵报告过校验、备选 b (fail-fast) 与产品"反馈闭环"核心要点冲突
  - **R-05 熔断 18**：6-section × 2 重试 + phase1/2 = 16 次最坏路径，加 2 个安全荧丝防 LLMClient 内部 JSON retry。备选 b (20) 太宽容遮蔽 bug，备选 c (分 phase budget) 代码复杂度上升不值得
  - **R-14 S3/S4 source_refs min=1**：无来源则不生成该条目（prompt + normalizer 双防护）。备选 b (改 schema 降为 min=0) 破坏 A+B+C 已锁定的"防幻觉"硬约束、备选 c (允许 placeholder URL) 06-04 已被判为背信溯源设计
  - **R-19 scope.competitors S2 union**：union 全部去重 by name 用户在前。备选 b (只用 recommender) 用户填写的"重要对手"会丢、备选 c (只用用户填) 与 vendor_profiles 不对称
  - **R-21 outline 单次调用 + 全字段约束**：保持单次调用 LLM，prompt 内枚举所有 BaseReport 必填字段（19 个）+ 长度约束。备选 b (拆 1a+1b) 调用次数 +1 熔断阈值还要再调高、备选 c (长文本走 phase 3 sections) 字段语义错位
  - **R-22 confidence_level vs quality_score**：二者独立、不交叉限制，仅 spec 加语义说明（数据采集面 vs 报告内容面）。允许 high+0.3 / low+0.8 这种"采集与内容质量分离"的报告。备选 b (强制压档) 破坏 writer/inspector 职责边界
- 备选（整体方案）：
  - 备选 A：信任接手备忘 14 条标题、跳过重审直接改 v3 → 排除：原审查证据链已丢，盲改风险大；且重审实际抓到 28 条（多 14 条），证明备忘信息不全
  - 备选 B：只修 v2 复查的 1 critical（C3）、其他全推迟 → 排除：跨模型独占发现 R-01（CompetitorProfile.source_urls 不存在）即必修 critical，推迟会让 writer 第一行就 AttributeError
- 影响：
  - Task 20/21 落地拆分从 v2 的 11 个 task 扩展到 v3 的 12 个 task（多了 Task 21.0 master 适配前置组：21.0a builder 异常路由 / 21.0b state.py FinalReport 修复 / 21.0c builder 旧覆盖删除 / 21.0d config 新配置项 / 21.0e normalizer 5 套升级）
  - 测试用例从 13 → 16（v3 加 3 个：S2 recommender 强制覆盖 / S4 prior diff 前置注入 / builder writer_node 异常路由）
  - 配置项新增 2 个：`WRITER_MAX_LLM_CALLS=18` + `WRITER_NARRATIVE_CONCURRENCY=3`
  - 新依赖：`asyncio.Semaphore` + `uuid.uuid4` 在 writer_orchestrator 内
- 跨模型审查独占价值的实证：Codex 抓到 R-01（CompetitorProfile.source_urls 字段不存在），Explore agent 完整漏掉。这条贯穿 v2 phase 1/2/4 的 4-5 处使用，是必修 critical。证明二轮 doubt-driven 不是冗余

---

---

## 2026-06-07（晚）: A 大类中间态破坏的处理策略——治本清理 + 过渡 skip
- 选择：A 大类重写 `src/schemas/__init__.py` + `report.py` 时，对依赖旧类（FinalReport/CompetitorInput）但属于 D-G 大类范围的文件，采取**两层治本策略**：
  - **`__init__.py`**：直接清掉旧类暴露（不留 `FinalReport = None` 之类的占位别名）—— 和 plan "废除旧 FinalReport 一步到位"的设计一致，避免技术债积累
  - **6 个旧测试文件**（test_writer/inspector/schemas/api/graph/trace_api）：module-level `pytest.skip(allow_module_level=True)`，文件内容只留 skip + 注释（不留 dead code）；分别注明会在 D/E/F 大类哪个阶段重写
  - **analyzer 2 测试**：xfail（fixture 用旧 SwotEntry 短中文不符合新 min_length=10），E 大类 analyzer 重写时一起修
- 理由：plan 设计了"中间态破坏"是接受的（"废除旧 FinalReport 一步到位"）。如果留兼容占位，D-G session 写代码时容易误以为占位是真实可用的，造成更隐蔽的 bug。skip + 注释比 dead code 干净，git history 保留旧测试供后续重写参考
- 备选：① `FinalReport = BaseReport` 别名占位（排除：B 大类 union 接通后会语义不一致）；② 在 ruff 配置中给旧测试文件免 E402（排除：dead code 越拖越坏）；③ 直接删旧测试文件（排除：丢失重写参考）
- 影响：A 大类完成时 pytest collection 阶段会跳过 6 个文件，total 106 passed / 6 skipped / 2 xfailed / 0 failed。skip 标记必须在 D-F 大类 inspector/writer/graph 重写时一并去除并写新测试，否则将永久跳过覆盖

## 2026-06-07（晚）: scenario_payload union import 放报告文件顶部（不延后 import）
- 选择：`src/schemas/report.py` 顶部直接 `from src.schemas.scenarios.{s1..s5} import ...`，BaseReport 类放文件底部直接用
- 理由：原 plan 写"BaseReport 在 Task 11 末尾追加 union import"会在文件中部出现 module-level import，触发 ruff E402；而 scenarios 包只依赖 common（验证过无循环），可以安全提到顶部。这样 ruff 干净 + import 集中可读
- 备选：① 文件中部 import + `# noqa: E402` 抑制（排除：ruff 警告抑制是逃避，不是修复）；② BaseReport 放独立文件（排除：拆分代价大于收益，BaseReport 必须知道 5 场景才能组 union）


## 2026-06-07: 弃用 SerpAPI，仅保留 Tavily 作为唯一搜索源
- 选择：删除 SerpApiSource 类、SEARCH_API_KEY/SEARCH_PROVIDER 配置开关、collection_pipeline 的"搜索→选页→抓取"两步走机制（_llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法 + 构造器塌缩）。Tavily 一次调用直返带正文，跳过中间所有步骤
- 理由：06-06 实测证实 Tavily 在中文场景质量明显优于 SerpAPI（语雀 1.0 / 飞书 0.85 completeness）；双 provider 架构带来开关复杂度（SEARCH_PROVIDER）、conftest 防污染 fixture、builder if/else、115 行 SerpAPI 专项代码——与 Cooper 选择的"代码简化、产品故事单一 AI 搜索"目标矛盾。git 历史保留，未来若需恢复可 revert
- 反转的旧决策：06-06「双 provider 切换、保留 SerpAPI 作为可选 fallback」（一日决策反转，作为历史保留）
- 备选 1：保留 SerpAPI 但删 SEARCH_PROVIDER 开关、Tavily 作为默认（排除：仍需双 provider 代码维护、产品故事不干净）
- 备选 2：仅删 SerpAPI 类、保留 SEARCH_PROVIDER 字段（排除：废留架构假承诺）
- 实现路径：方案 B'（doubt-driven 双模型审查后修订），分 7 个细粒度 commit；commit 顺序：测试先改不依赖 → 删生产代码 → 删 SerpAPI 专项测试 → 文档同步

## 2026-06-07: 报告 schema 按使用场景拆分（5 场景全做，R2 架构）
- 选择：废除原通用单一 FinalReport schema，改为按竞品分析使用目的拆 5 个场景（S1 功能迭代 / S2 市场进入 / S3 定价策略 / S4 持续监控 / S5 战略定位），共享 BaseReport 通用骨架（discriminated union），完整 5 场景设计 + 7000-8000 字咨询级深度
- 理由：原通用 schema 的 4 段执行摘要 + 顶层 SWOT/雷达/功能矩阵字段集只对 S1 成立，对 S2（无产品调研）/S3（定价细致活）/S4（变更追踪）/S5（定位象限）都失效。调研显示业界（McKinsey/BCG/Bain/Gartner/Forrester）做竞品分析报告会按使用目的分形态——5 场景拆分既贴业界惯例又能讲"按场景分流的多 Agent 工作模板"产品故事
- R2（BaseReport 通用骨架 + payload）vs R1（5 套独立 schema）：调研显示 13 通用元素是 5/5 咨询机构共识，R2 让通用部分一处定义改一处生效，writer 编排和前端渲染都能共用大半逻辑。R1 干净分离但代码 5 倍重复
- 备选 R1（排除：5 套独立 schema 通用部分重复度高、维护成本翻倍、产品故事弱于 R2 的"共性抽象 + 场景定制"）；备选只做 S1（排除：Cooper 选 5 场景全做做出完整产品故事）

## 2026-06-07: BaseReport.scenario 改 computed_field 派生（修原 discriminator 三处不一致）
- 选择：移除独立 `scenario` 字段，改为 `@computed_field` 从 `scenario_payload.scenario_type` 派生；加 `model_validator` 强制 `metadata.scenario == scenario_payload.scenario_type`
- 理由：doubt-driven 双模型审查发现原设计有 3 处独立 scenario 字段（顶层 + metadata + payload），LLM 可能输出三处不一致（如顶层 S1 / metadata S2 / payload.scenario_type S3），Pydantic 不会报错但业务层错路由
- 备选：3 处全保留 + 全 model_validator（排除：3 处校验冗余）；只删 metadata.scenario（排除：metadata 是 trace_writer 落盘骨架，不能去掉）

## 2026-06-07: 5 场景共享 13 通用骨架元素 + ExecutiveSummary 5 段式
- 选择：基于 McKinsey/BCG/Bain/Gartner/Forrester 5/5 共识，BaseReport 含 13 通用字段（title/subtitle/at_a_glance/executive_summary/background/scope/methodology/key_findings/analysis_sections/swot/conclusions/recommendations/appendix）。ExecutiveSummary 用 5 段固定子字段（context/core_thesis/key_findings_brief/implications/path_forward）
- 理由：原 4 段（what_competitors_did_right/wrong/our_opportunities/next_steps_summary）只对 S1 成立——S2 无"我们"，S3 4 段语义不对口，S5 谈定位拥挤区不谈竞品对错。5 段 Context/Thesis/Findings/Implications/Path 是业界跨场景共识范式
- 备选：4 段保留只在 S1 用（排除：每场景用不同摘要框架，前端渲染逻辑爆炸）

## 2026-06-07: SWOT 进 BaseReport 通用骨架，5 场景全保留（决策 1）
- 选择：Swot 升到 BaseReport 通用层，5 场景每份报告都含 SWOT
- 理由：SWOT 是非技术用户一眼能懂的视觉抓手 + 业界经典框架；前端已有 4 象限渲染逻辑沉淀；5 场景产 SWOT 时各自维度不同（S1 功能维度 / S2 市场维度），用 SwotEntry.dimension 自由 str 承接
- 备选：删 SWOT（排除：失去 demo 视觉抓手）；只在 S5 保留（排除：放弃了 4 场景的 SWOT 可视化）

## 2026-06-07: 雷达图 S1 多边形 / S5 二维散点（同字段不同含义，决策 2）
- 选择：S1 用 5 维多边形雷达（feature_breadth/usability/cost_effectiveness/stability/design_quality 各 0-5）；S5 用二维散点 PerceptualMap（用户选两条 axis）
- 理由：两者是不同图表语义——S1 雷达是"产品维度评分"（多边形），S5 PerceptualMap 是"市场定位坐标"（散点）。共用一个 schema 会语义错乱
- 备选：S5 复用 S1 雷达（排除：5 维产品评分不能表达"易用性 vs 深度功能"这种二维定位）；都不做（排除：删核心可视化产物）

## 2026-06-07: BattleCard 整块从 S1 移除（决策 4）
- 选择：S1 schema 不含 BattleCard 整块（含 LandmineQuestion / Objection / proof_points / typical_deal_size 等 10 子模型）
- 理由：双模型 doubt-driven 一致认定为 YAGNI——4 个核心字段（typical_deal_size 真实成交价 / objections 客户异议库 / landmine_questions 销售引导 / proof_points 真实背书）公开网页根本拿不到（这些是 CRM/录音/销售实战数据），强制必填会让 LLM 编造，违反信息溯源（产品硬指标）。另 S1 P0+P1（vendor_profiles/feature_matrix/radar/JTBD/roadmap）已能撑起 Forrester Wave 风格完整报告
- 备选：收窄保留 4 个有源字段（排除：双模型都说性价比不划算，工作量超出收益）；全保留 + Optional 兜底（排除：LLM 仍会编 + inspector 难辨真假）

## 2026-06-07: writer 重构为 4 阶段编排（突破单次 LLM 4-5K 字上限）
- 选择：writer 从单次 LLM 调用改为 4 阶段编排：①骨架（title/exec_summary/key_findings/recommendations）②payload 结构化产物 ③逐 section 写 narrative ④代码合并 + computed_field + validator + quality_score。整体 ~8 次 LLM 调用产 7000-8000 字报告
- 理由：Doubao-Seed-2.0-lite 单次稳定输出上限 4-5K 中文字（含其他 schema 字段），无 JSON mode 越深嵌套越易局部损坏。分阶段调用每次输入小、输出小、错率低；任一节失败局部重试不阻塞其他章节；computed_field/SWOT/feature_matrix 由代码透传保 100% 结构不丢
- 已知 trade-off：单次分析 LLM 调用从 4 增到 ~10-15、整体耗时从 5-8 分钟增到 12-18 分钟。Cooper 选 demo 用成功 trace 现成报告即可，不要求现场实时跑
- 备选：单次 LLM 产整份报告（排除：稳定不到 7000 字 + JSON 损坏率高）；分章节 5+5+5 等量调用（排除：浪费 token 预算）

## 2026-06-07: 协作模型固化（Cooper 产品 / Claude 研发）
- 选择：明确两人角色——Cooper（产品 PM）决定做什么/优先级/产品故事；Claude（研发）评估技术可行性/字段命名/Pydantic 模式。冲突时分 4 类处理：完全放弃 / 部分放弃 / 换思路 / 推迟
- 理由：之前我多次擅自替 Cooper 做产品决策（如默认丢 SWOT/雷达图/选 BattleCard P2），doubt-driven 抓不到这类问题（technical 而非 product）。固化角色避免我再混淆
- 落地：未来设计阶段我必须主动列产品决策清单（abc 选项 + 标注技术约束），让 Cooper 拍板；技术问题（命名/约束/validator）我自己处理但 RECONCILE 时透明化记录在评审章节

## 2026-06-06: 移除 iTunes 专源（修正 06-01「数据源含 iTunes」）
- 选择：删除 ItunesSource 及其 category 路由机制（build_pro_sources/normalize_category）；采集只保留 SerpAPI/Tavily 搜索主线
- 理由：iTunes Search API 按关键词搜索会带回同名/相近无关 App（实测搜「飞书」带出豆包、千问，搜「语雀」带出 flomo、石墨），且代码无差别将三条结果全并入分析语料，污染结论（analyzer 可能拿豆包数据当飞书分析）。其当初引入的三类价值中，定价/描述已被 Tavily 抓官网取代（飞书抓到 7 个真实套餐 tier，远超 iTunes 的「免费」一条），仅剩 App 评分是独家——但评分一项不值得背同名污染风险。且 iTunes 仅对软件类竞品有效，硬件竞品用不上。将来确需 App 评分可从 git 历史恢复
- 备选：加同名过滤只取第 1 条（排除原因：边际价值低，不值得维护匹配逻辑）、保留骨架返回空（排除原因：留死分支，不如删干净靠 git 历史找回）

## 2026-06-06: TavilySource 鉴权用 POST + Bearer header
- 选择：Tavily 调用走 POST + JSON body，api_key 放 Authorization: Bearer header（新增 HttpClient.post_json，header 局部传参不污染共享客户端）
- 理由：Tavily 官方契约是 POST/Bearer；最初误实现为 GET + api_key query 参数导致真实调用 401（doubt-driven 时 Codex 已预警 GET 写法，实现时误判）。key 走 header 不进 URL，日志不泄漏
- 备选：GET + api_key query（排除原因：返回 401，非官方契约）

## 2026-06-04: 报告质量提升走「溯源为脉」而非「只改 writer」（方案 C）
- 选择：报告质量提升以「事实-URL 绑定链」为主线贯穿全链路——pipeline 输出带【来源】标记文本 → collector 抽取时绑定每条 fact 的 source_url → analyzer 透传维度 source_urls（代码兜底）→ writer 机械透传 SWOT/雷达/功能矩阵 + 按 dimension 下沉 source_refs → inspector 程序化硬查 + severity 分级 pass/fail
- 理由：最初设想「只改 writer 做机械下沉」，两轮 doubt-driven（单模型 + Codex gpt-5.5 跨模型，20 条命中）核对源码后证伪——溯源断链的真正根因在**采集层**：collector 抽取 prompt 只给 sample_reviews 留 source_url、正文被 merge 成无【来源】锚点的 blob，导致 analysis 各维度 source_urls 恒空。不碰采集层就修不了「每条结论可溯源」（产品核心要点 + 引用强制反幻觉）
- 关键设计原则：**能用代码保证的结构与溯源不赌 LLM**——SWOT/雷达/功能矩阵由 writer 代码透传（100% 不丢），溯源由代码机械下沉，LLM 只负责写散文深度
- 溯源粒度：维度+竞品级（不追 per-entry，per-entry 需改 analysis schema 结构，留作增强）
- severity 分级 pass/fail：从「有任何 issue 就 fail」改为「只 critical/major 阻断，minor 放行」——因 action_item 溯源等只能软查，硬查会逼成假闭环（无限重试耗尽）
- 备选：纯 prompt 工程不加代码兜底（排除：溯源/SWOT 仍可能丢，时灵时不灵）；writer 分章多次 LLM 生成（排除：调用成倍、耗时长，Cooper 选单次增强）

## 2026-06-04: 删除全链路文本截断，依赖 Doubao 256K 上下文
- 选择：删掉 analyzer(12000)/writer(8000)/inspector(15000) 的序列化文本截断，全量入参
- 理由：Doubao-Seed-2.0-lite 至少 256K context，analysis/profile 序列化通常几万字符远小于上限；截断会逐级丢信息（writer 8000 最致命，常导致没看到 SWOT/雷达就开写）。删截断是最简方案，无需结构化瘦身/分片模块（YAGNI）
- 已知 trade-off：llm_client 无 max_tokens，超长输入「迷失在中间」可能损害引用准确率——验证阶段实测观察，必要时回调
- 备选：上下文分片管理器（排除：256K 下根本触发不了，为产品话术造无用模块）

## 2026-06-04: analyzer 反馈回边为「保险」，当前效用有限
- 选择：should_continue 认 analyzer 类 issue 并加 graph 回边（inspector→analyzer），但不作为主路径
- 理由：SWOT/雷达/功能矩阵现由 writer 代码透传 + analyzer 兜底保证，正常流程不该触发 analyzer 打回；回边是保险。但 analyzer 重跑读相同 profiles，重采相同 prompt → 大概率产出相同结果，效用有限（最终 code review 指出）
- 待增强：重打 analyzer 时把 feedback.issues 附加进 prompt（「上次 SWOT 缺 X，请补全」），让回边从「随机重采」变「定向修复」——留作下一课题
- 备选：不加 analyzer 回边（排除：analyzer 类 issue 会被静默打给 writer，writer 改不了上游 → 假闭环）

## 2026-06-04: SerpAPI 鉴权从 Bearer header 反转为 api_key query 参数
- 选择：`SerpApiSource.search` 用 `&api_key=<quote(key)>` query 参数鉴权，去掉 `Authorization: Bearer` header（**反转 06-03「key 走 header 防泄漏」决策**）
- 理由：真实跑通验证发现 SerpAPI 用 Bearer header 鉴权时，**遇非 ASCII（中文）query 返回 401「Invalid API key」**——竞品名恒为中文，导致搜索主线在真实场景 100% 失效（systematic-debugging 证伪 env/激活/编码/headers 后锁定）。api_key query 是 SerpAPI 标准用法，中文 query 正常
- 防泄漏补偿：query 参数的 key 由 `HttpClient._redact_key` 在自有日志脱敏为 `api_key=***`；并把 httpx/httpcore 日志压到 WARNING（其 INFO 会绕过脱敏、明文打完整请求 URL）——见下条
- 备选：保留 Bearer + 对中文 query 做特殊处理（排除：SerpAPI 服务端行为不可控，治标不治本）

## 2026-06-04: httpx/httpcore 日志级别压到 WARNING（防 key 泄漏）
- 选择：`init_logging` 内 `logging.getLogger("httpx"/"httpcore").setLevel(WARNING)`
- 理由：httpx 的 INFO 日志会打 `HTTP Request: GET <完整URL>`，含 query 里的 api_key——这条不经过我们的 `_redact_key`，会明文落 run.log/app.log。压到 WARNING 后不打请求行，但保留真实错误（WARNING/ERROR）
- 备选：自写 httpx event hook 脱敏（排除：过度工程，压级别已足够）

## 2026-06-03: 采集层重构为分层管线（collector → pipeline → sources）
- 选择：采集逻辑从 CollectorAgent 下沉到独立的 `CollectionPipeline`（tool 层），数据源做成 `sources.py` 内可插拔插件；collector 构造器从 `(llm, http, parser)` 改为 `(llm, pipeline)`
- 理由：原 collector 内联 3 个硬编码 URL 源、职责饱满；新增「搜索→选页→正文→闸门 + 专源路由」会让它膨胀且无法独立单测。下沉后每层单一职责、可独立测试，专源可插拔
- 备选：在 collector 内线性扩展（排除：膨胀、专源无处安放）、全套配置化插件框架（排除：当前 3-5 源，过度设计）

## 2026-06-03: 两步走采集（搜索 API → LLM 选页 → 正文页）
- 选择：用专业搜索 API（默认 SerpAPI）拿候选 URL → LLM 选最相关 Top N → 抓正文页 → 质量闸门过滤
- 理由：原 Bing/搜狗抓的是搜索结果页（SERP）摘要而非内容页正文，信噪比低——这是「质量低」的首要根因。两步走直取官网/文档正文
- 备选：只加更多搜索源（排除：SERP 噪声依旧）、专源优先（排除：源零散、覆盖不全）

## 2026-06-03: 只实现 SerpAPI，不做 provider 抽象
- 选择：搜索源只实现 SerpApiSource，key 走 Authorization header（不进 query 防泄漏）；换 provider 列入未来扩展
- 理由：SerpAPI/Bing/Brave/Google CSE 响应 JSON 结构各不相同，「配置切换 provider」需各写 parser——doubt-driven 判定「config alone 可换」是假承诺。当前 YAGNI 只做一个
- 备选：provider 可配置抽象（排除：假承诺 + 过度设计）、默认 Bing（排除：微软已宣布退役）

## 2026-06-03: 按 category 路由用独立 detect_category（不复用 competitor_type）
- 选择：新增零 LLM 的 `detect_category`（规则匹配 category/name/company → saas/default），用于专源路由
- 理由：doubt-driven 捕获方向性错误——原计划用 `classify_competitor` 的 `competitor_type` 路由，但其枚举是「核心/标杆/间接竞品」（竞争关系），无 SaaS/硬件（产品形态）维度，硬件竞品会被错配到 iTunes
- 备选：复用 competitor_type（排除：维度不对口）、LLM 判类别（排除：会多一次 LLM 调用，打破集成测试 6 步序列）

## 2026-06-03: 顶层 collect 从「快速失败」改为「部分降级」
- 选择：顶层 `collect()` 用 `asyncio.gather(return_exceptions=True)`，单竞品彻底失败 → 产 completeness=0.0 占位 profile，其余竞品正常产出
- 理由：多竞品场景下一颗老鼠屎不该坏一锅汤；质检会诚实反映占位 profile 的低质量。全空也不调 extract LLM（防 LLM 编造画像）
- 备选：保留快速失败（排除：单竞品失败拖垮整个分析）；注意 parse_goal 失败仍整体中止（公共前置，合理）

## 2026-06-03: 可观测性不阻塞 + 安全脱敏（沿用既有取向）
- 选择：pipeline_trace 随 profile.metadata 落盘（不碰 graph 闭包 node_trace）；HttpClient 对 URL 和异常消息双重脱敏 key；per-domain 锁串行化限速读-睡-写
- 理由：trace 进 metadata 避免反向依赖图层、也保证可追溯随产物走；密钥可能经 run.log / /trace 接口 / report.data_sources 泄漏，必须脱敏；并发 fetch 同域名下 check-then-act 会击穿 COLLECT_INTERVAL（合规要求）
- 备选：trace 注入闭包（排除：反向依赖 + 污染 node_trace 断言）、仅 URL 脱敏（排除：异常消息也可能含 key）

## 2026-05-30: 编排框架选型
- 选择：LangGraph
- 理由：产品要求质检→采集的反馈闭环（DAG 循环），LangGraph 原生支持条件分支和环路
- 备选：CrewAI（排除原因：声明式编排，复杂闭环控制力弱，需要额外 hack）

## 2026-05-30: Agent 构建框架选型
- 选择：待定（LangChain 或纯手写）
- 理由：取决于 Doubao 模型的 SDK 适配情况
- 备选：Claude Agent SDK / OpenAI Agents SDK（排除原因：项目当前选用 Doubao 模型，需优先适配）

## 2026-05-30: LLM 选型
- 选择：Doubao-Seed-2.0-lite（EP: ep-20260514111325-xjmj7）
- 理由：项目当前可访问的模型资源
- 备选：无（项目当前使用指定资源）

## 2026-05-30: Agent 数量
- 选择：4 个（采集、分析、撰写、质检）
- 理由：职责边界清晰，覆盖竞品分析全链路；后续若行动建议质量不佳可加策略 Agent
- 备选：5 个（加策略 Agent）（排除原因：当前 4 个够用，避免过度设计）

## 2026-05-30: 竞品分析场景
- 选择：产品经理功能对标（场景 A）
- 理由：场景具体、数据源明确、可演示性强
- 备选：行业报告（场景 B）、SWOT 跟踪（场景 C）（排除原因：场景 B 太泛，场景 C 偏战略层）

## 2026-05-30: 竞品数量
- 选择：支持 N 个竞品（架构通用）
- 理由：架构上做通用，Demo 聚焦 1-2 个金融 case；演示时展示通用性
- 备选：固定 2 个竞品（排除原因：限制灵活性）

## 2026-05-30: 前端方案
- 选择：Streamlit（最简方案）
- 理由：11 天极限计划，前端不是核心重点，Streamlit 最快出活
- 备选：React/Vue（排除原因：时间不够，UI 美化不是核心要点）

## 2026-05-30: 产品定位
- 选择：面向企业产品经理的自动化竞品分析工具（内部使用）
- 理由：场景 A 锁定，目标用户明确
- 备选：通用分析平台（排除原因：太泛，无法聚焦）

## 2026-05-31: Agent 构建方式
- 选择：手写 Agent（纯 Python 函数 + LangGraph StateGraph）
- 理由：Agent 间是固定流水线，不需要 LangChain 的动态工具选择能力；Doubao 兼容性不确定；产品强调可观测性，手写逻辑更透明
- 备选：LangChain Agent 封装（排除原因：抽象层增加调试难度，Doubao function calling 兼容性未知）

## 2026-05-31: 前后端架构
- 选择：FastAPI 后端 + Streamlit 前端，前后端分离
- 理由：FastAPI 提供 API 端点，Streamlit 调用 API，职责清晰
- 备选：Streamlit 直接调用 LangGraph（排除原因：Cooper 要求前后端分离）

## 2026-05-31: 依赖管理
- 选择：venv + pip + requirements.txt
- 理由：纯 Python 项目，无重依赖（CUDA/科学计算），venv 最简单
- 备选：conda（排除原因：过重，不需要）

## 2026-05-31: 结构化输出方案
- 选择：Doubao JSON mode（response_format={"type": "json_object"}）
- 理由：Doubao 支持 JSON mode，直接约束 LLM 输出格式，比 Prompt 约束更可靠
- 备选：Prompt 约束 + 后处理解析（排除原因：JSON mode 更稳定）

## 2026-05-31: 目标设定实现方式
- 选择：采集 Agent 内部三步走（目标解析 → 竞品分类 → 差异化采集）
- 理由：目标解析是轻量 LLM 调用，不值得单独设 Agent；目标设定绑定前端 UI 会限制后续迁移为 skill
- 备选：独立目标设定 Agent / 前端 UI 下拉框（排除原因：前者过度设计，后者耦合前端形态）

## 2026-06-01: 放弃 JSON mode，改纯 prompt 约束（推翻 05-31 决策）
- 选择：去掉 `response_format={"type":"json_object"}`，靠 prompt 约束 + 代码块剥离 + 解析重试
- 理由：真实验收发现 Doubao-Seed-2.0-lite 端点不支持该参数，直接返回 400；实测纯 prompt 约束已能稳定输出合法 JSON
- 备选：保留 JSON mode（排除原因：模型不支持，是硬性失败）

## 2026-06-01: LLM 超时从 30s 调到 120s
- 选择：`LLM_TIMEOUT = 120`
- 理由：实测单次中等规模调用要 30.4s，30s 超时反复触发导致全链路失败；Doubao-Seed-2.0-lite 推理较慢
- 备选：换更快模型（排除原因：项目当前使用该模型资源）

## 2026-06-01: 数据源改为 iTunes API + Bing + 搜狗（推翻 05-30 数据源）
- 选择：iTunes Search API（结构化 JSON，含价格/评分/描述）+ Bing 搜索 + 搜狗搜索
- 理由：原数据源（App Store 页面/百度百科/百度搜索）实测全部失败（404/403/反爬）；新三源实测稳定返回真实内容，iTunes 还直接提供定价与满意度数据，强化信息溯源
- 备选：百度百科加反爬（排除原因：补全请求头后仍 403）、维基百科（排除原因：403）

## 2026-06-01: LLM 输出鲁棒性统一用「规整兜底」策略
- 选择：每个 Agent 在 Pydantic 校验前对 LLM 原始输出做 _normalize 规整（prompt 引导 + 代码兜底双保险）
- 理由：Doubao 输出不稳定，反复出现结构/枚举偏差（sample_reviews 填字符串、gap_level 填"小米领先"、priority 填"中等"、裸控制字符）。光靠 prompt 约束无法 100% 命中，必须代码兜底。枚举规整用「精确匹配→包含匹配→默认值」三级降级
- 备选：仅靠 prompt + 重试（排除原因：重试同样失败，6 品牌场景必现）、JSON Schema 强约束（排除原因：Doubao 不支持 response_format）

## 2026-06-01: 信息溯源与质量分在 graph 层回填
- 选择：`data_sources` 和 `quality_score` 由 graph 节点回填，而非依赖 writer LLM 自填
- 理由：writer 拿不到 profile 的 sources、LLM 自填的 quality_score 恒为 0 不可信；溯源应取自采集真实结果，质量分应取自质检 issue 严重度
- 备选：让 writer prompt 填这两个字段（排除原因：writer 无 source 数据、LLM 自评分不客观）

## 2026-06-10: collector 喂 LLM 前 100K 字符硬截断（fix1）
- 选择：`src/agents/collector.py::_extract_profile` 入口处对 labeled_text 做 ≤100K 字符硬截断（保头部）；同时每场景 query 数从 2 条收敛到 1 条（`_SCENARIO_QUERIES`）
- 理由：实测「飞书文档」labeled_text 拼起来 >150K 字符触发 Doubao 400 「Total tokens exceed max message tokens」（输入上限 224K token）；100K 字符 ≈ 70K token，留 50%+ 安全垫
- 备选：分批 LLM 抽取再合并（排除：4-5 倍 token 成本 + 复杂 reduce 逻辑）；不截断（排除：飞书等富文本竞品必撞 400）

## 2026-06-10: 关闭 OpenAI client 内部 retry 避免嵌套放大（fix Bug 2）
- 选择：`AsyncOpenAI(max_retries=0)`，把 retry 完全交给 `LLMClient.call_json` 外层（LLM_MAX_RETRIES + 1 = 3 次）
- 理由：默认 max_retries=2 与外层 3 次嵌套 = 9 次 HTTP × 120s timeout = 最坏 18 分钟，前端 1800s 都被打穿（trace 20260609-150301-df17ff 实证 collector 卡 10+ 分钟）
- 备选：保留默认 + 缩短 timeout（排除：解决慢但仍不可控）；只关外层（排除：OpenAI client 内部 retry 不可见，调用方无法追溯）

## 2026-06-10: writer ValidationError 完整 errors() 落 trace 文件（fix2）
- 选择：`builder.py::writer_node` 异常分支用 `_serialize_writer_exception` 提取 `e.errors()` 完整列表，通过 `trace_writer.save_raw` 落到 `04_writer_error.json`；run.log 同时打 errors_summary
- 理由：之前 `str(e)[:200]` 截断丢失关键 loc 信息，下次复发只能猜字段；ValidationError 的 errors() 含完整 loc/msg/type 三件套，是诊断 schema 失败的最重要材料
- 备选：直接打到 run.log（排除：长摘要污染日志，结构化 dict 落盘更便于解析）

## 2026-06-10: AnalyzerAgent 接口注入 ScenarioInput 解场景失明（fix7）
- 选择：`AnalyzerAgent.analyze(profiles, scenario_input=None, feedback_issues=None)`，新增可选 scenario_input 参数；ANALYZER_SYSTEM 加 SWOT 主体硬约束（S2 主体=赛道进入这件事，其余=我方产品）
- 理由：之前 analyzer 完全不知道 scenario / our_product_name / analysis_context，SWOT 主体只能脑补、feature_matrix.our_product 字段也填空"无"。trace 20260609-203430 实证：SWOT 写成 3 个竞品优劣势罗列而非围绕 Notion，inspector 标 major issue
- 备选：每场景独立 prompt（排除：5 套 prompt 维护成本高）；改 system prompt 写死场景分支（排除：通用 system prompt + user 注入更灵活）

## 2026-06-10: data_collection_approach 改代码合成模板（fix11）
- 选择：phase 4 用 `_build_data_collection_approach()` 模板（含场景标签 + 竞品名 + URL 数 + 时间窗 + 完整度）覆盖 LLM 输出；outline prompt 标注「该字段代码合成」
- 理由：LLM 反复在 phase 1 outline 写 `data_collection_approach` 不到 schema 要求的 200 字符，每次 graph 重试栽在同一处。该字段是「我们怎么采的数据」元描述，本就该模板化不该让 LLM 创作
- 备选：phase 1 加 ReportMetadata 局部校验 + 重试（排除：代价大且不能保证 LLM 听话）；强化 prompt（排除：已写过明确字数要求，LLM 仍不执行）

## 2026-06-10: writer_node 入口 skip 兜底防 analyzer 失败 KeyError（fix12）
- 选择：`builder.py::writer_node` 入口检测 `state.analysis is None` + `feedback.passed=False` 时直接 skip 透传 feedback，让 should_continue 按 `issue.agent='analyzer'` 路由回 analyzer
- 理由：analyzer 抛错（如 APITimeoutError）时返回 dict 没 analysis 字段，writer 直接 `state['analysis']` 触发 KeyError，被兜成 feedback agent=writer，**反馈闭环路由错误**——本应回 analyzer 重试，结果回 writer 重试浪费 retry quota
- 备选：让 graph 边变 conditional（排除：改 langgraph 拓扑 + 影响其它路径）；analyzer_node 失败时仍返回桩 analysis（排除：桩对象在 writer 里更难处理）

## 2026-06-10: prompt-schema 对齐成项目硬约束 + Prove-It 测试覆盖（fix4/10/14/15/17/18/19）
- 选择：5 套 payload prompt 与 schema Literal/min_length/max_length 等所有字段约束严格对齐，新增 `tests/unit/test_writer_payload_prompts.py` 用 25+ 个测试断言关键枚举值、必填字段、高频踩坑短语都在 prompt 里
- 理由：S2 trace 20260609 实证 prompt 写「value_basis 填 industry_report」但 schema 是 Literal[measured/estimated/inferred/unknown]，LLM 老老实实按 prompt 填值反复撞 schema。**永远是 prompt 跟着 schema 走，不能反过来**
- 备选：从 schema 自动生成 prompt（排除：可读性差 + 无法表达"高频踩坑"等启发式经验）

## 2026-06-10: Streamlit session_state 持久化 last_response（fix6）
- 选择：`render_analysis_response` 把整个 API response 存到 `st.session_state["last_response"]`；主入口 `if button A else if "last_response" in session_state` 双轨恢复
- 理由：Streamlit 每次按钮点击都全脚本重跑，"开始分析" if 块在追溯按钮重跑时不再 True，导致主报告区消失。这是 Streamlit 同步阻塞模型的已知特性
- 备选：迁前端到 React+FastAPI（排除：迁移成本高，本项目用 Streamlit 是 demo 优先）

## 2026-06-10: S5 normalizer 兜底是 LLM 服从性局限的临时补丁（迭代时优先撤回）
- 选择：在 `src/agents/normalizers/s5.py` 加 `[fix20]` 标记的代码层兜底——vendor_profiles.strengths < 2 时复制最后一条凑齐 / perceptual_map 单字轴标签自动补字（"低"→"低端"）/ category_strategy 空 dict 时填占位子字段
- 理由：实测 Doubao-Seed-2.0-lite 在 S5 密集约束（4 vendor × strengths 2-5 × cautions 1-4 + 多结构嵌套）下反复失误，2 次完整 S5 trace（20260609-234227 / 20260610-000505）走完反馈闭环 max_retries 仍无法产出合规报告。代码兜底让 happy path 跑通保 demo 演示
- **后续迭代提示**：本兜底是 **LLM 服从性局限**导致，不是项目正确性需求。换更强的 LLM（Doubao-Seed-2.0-pro / GPT-4o / Claude Sonnet）后这部分代码应**优先撤回**，避免水印文本（"补充条目"、"normalizer 占位 LLM 未提供"）污染报告。撤回前用新模型在 S5 端到端跑若干次确认稳定后再删
- 备选：换更强的 LLM（排除：当前 demo 时间窗内没时间换 endpoint）；让 LLM 重试更多次（排除：fix5 已 max_retries=2，再加耗时不可控）；放弃 S5 happy path 当作已知局限（排除：5 场景验证完整度对产品演示重要）

## 2026-06-02: 中间产物按 trace_id 落盘（独立 TraceWriter）
- 选择：新建 src/tools/trace_writer.py，graph 各节点产出后调 save_stage 落盘到 runs/<trace_id>/，落盘逻辑单一出口
- 理由：产品要求「每个 Agent 的决策过程与中间产物均可追溯」，是核心硬要求；独立模块容错/快照命名集中、builder.py 保持清爽、可独立单测
- 备选：节点内分散落盘（排除：重复代码、污染编排逻辑）、LangGraph 回调钩子（排除：与「手写 graph 求透明」取向冲突，见 05-31）

## 2026-06-02: trace_id 改用北京时间格式
- 选择：`YYYYMMDD-HHMMSS-` + 6 位随机 hex（东八区，datetime.now(timezone(timedelta(hours=8)))），生成后查目录碰撞则重生成
- 理由：可读、可按时间排序、防同秒碰撞（系统要考虑轻度并发）；替换原 uuid4()[:8]。已验证不破坏现有契约（测试用任意字符串 trace_id、前端只展示不解析）
- 备选：纯时间戳（排除：同秒碰撞覆盖）、保留 uuid（排除：不可读、无法排序）

## 2026-06-02: 落盘容错与并发权衡
- 选择：落盘失败仅 warning 不抛、原子写（临时文件+os.replace）、重试快照 _vN 按磁盘最大版本+1；不做跨进程文件锁
- 理由：可观测性是辅助能力，绝不能阻塞核心分析；原子写防写撕裂；_vN 取磁盘版本避免进程重启后内存计数归零覆盖历史。面向 demo 演示的轻度并发，「不同 trace 目录+原子写+碰撞规避」已足够，完整锁是过度设计
- 备选：落盘失败即请求失败（排除：鲁棒性差）、内存计数器定版本号（排除：进程重启丢历史）、跨进程锁（排除：过度设计）

## 2026-06-02: 决策过程追溯用 node_trace 轻量覆盖
- 选择：meta.json 记录 node_trace（节点执行序列 + 每次打回的 issues 摘要和目标 agent），不存 prompt/LLM 原始响应
- 理由：产品要求「决策过程可追溯」，但全存 prompt/原始响应范围爆炸；node_trace + feedback.json（质检决策）已轻量覆盖决策主体，prompt 留作未来扩展
- 备选：全量存 prompt 和 LLM 原始响应（排除：范围爆炸，收益边际递减）

## 2026-06-02: 追溯方法论 — doubt-driven 前置评审
- 选择：设计阶段用 doubt-driven（单模型 + Codex 跨模型对抗审查）在写码前审方案
- 理由：本功能跨模块、含路径穿越等安全断言，事前审查比事后调试便宜。实测捕获 8 处实质问题（原子写、model_dump mode、路径正则锚定、meta 孤儿、快照覆盖范围等），全部在写码前修正
- 备选：直接实现后 code review（排除：方向性缺陷到 review 阶段返工成本高）

## 2026-06-01: 采集数据传递方式
- 选择：Analyzer 和 Writer 使用 model_dump() 序列化完整数据传给 LLM
- 理由：原实现只传统计数字，LLM 无法生成有意义的分析/报告；完整数据传递是正确性问题
- 备选：手动拼接摘要文本（排除原因：丢失关键细节）
