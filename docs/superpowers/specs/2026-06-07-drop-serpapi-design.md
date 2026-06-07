# 设计：弃用 SerpAPI，仅保留 Tavily 作为唯一搜索源

**日期**：2026-06-07
**状态**：设计完成，待 Cooper 审阅
**分支**：`worktree-drop-serpapi`（worktree：`.claude/worktrees/drop-serpapi/`）

---

## Part 0：背景与动机

### 动机（Cooper 拍板）

Tavily 实测明显优于 SerpAPI，双 provider 的维护成本不值。06-06 真实验收（语雀 vs 飞书）证据：
- Tavily 抓飞书 4 条官方页（feishu.cn/...），SerpAPI 还原 SERP 噪声
- Tavily 一次调用直返带正文结果，跳过「搜索→选页→抓取」三步走
- Tavily completeness 评分稳定 ≥0.85（语雀 1.0 / 飞书 0.85）

### 不在范围

- 不引入新搜索源（如 Exa/Brave/Google CSE）
- 不改 collector/analyzer/writer/inspector 的业务逻辑
- 不改 schema、不改 graph 编排、不改前端
- 不动 06-04/06-06 的"事实-URL 绑定链"和"质量闸门"

### 与 06-06 的关系

06-06 决策"接 Tavily + 保留 SerpAPI 双 provider"——**本次决策反转其后半句**，明确单 provider 收敛。06-06 决策记录作为历史保留，不修改；本次新增"06-07：弃用 SerpAPI"决策条目 append 到 DECISIONS.md（项目惯例：决策反转 append 而非改）。

---

## Part 1：删除清单（生产代码）

### A1. `src/tools/sources.py`

| 删 | 内容 |
|---|---|
| ✅ | `class SerpApiSource`（line ~24~62，~28 行）|
| ✅ | `SERPAPI_URL` 常量（line ~21）|
| ✅ | `from urllib.parse import quote`（删 SerpApiSource 后无引用，否则 ruff F401）|
| ✅ | 顶部 docstring 改为"Tavily 搜索源（唯一）"|
| 🔵 保留 | `class TavilySource` + `SourceResult` dataclass + 文件骨架 |
| 🔵 保留 | `returns_bodies = True` 类属性（保留为隐式契约文档，注明"占位标记"），见 Part 7 trade-off |

### A2. `src/utils/config.py`

| 删 | 内容 |
|---|---|
| ✅ | `SEARCH_API_KEY` 字段 |
| ✅ | `SEARCH_PROVIDER` 字段 |
| ✅ | `_provider_env` helper（仅服务 SEARCH_PROVIDER）|
| ✅ | `PICK_LLM_TIMEOUT` 配置（仅 `_llm_pick` 用，删 `_llm_pick` 后无引用）|
| ✅ | `MAX_FETCH_CONCURRENCY` 配置（仅 `_fetch_clean` 用，删后无引用）|
| 🔵 保留 | `TAVILY_API_KEY`、`SEARCH_TOP_N`、`COLLECT_INTERVAL`、`COLLECT_TIMEOUT`|

### A3. `src/graph/builder.py`

```python
# 删
from src.tools.sources import SerpApiSource, TavilySource
if settings.SEARCH_PROVIDER == "tavily":
    search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
else:
    search_source = SerpApiSource(http=http, api_key=settings.SEARCH_API_KEY)

# 改为
from src.tools.sources import TavilySource
search_source = TavilySource(http=http, api_key=settings.TAVILY_API_KEY)
```

注意：传给 `CollectionPipeline` 的参数也要改（见 A4 构造器塌缩）。

### A4. `src/agents/collection_pipeline.py`（重大化简）⚠️

**doubt-driven 跨模型审查发现**：删 `_fetch_with_backfill` 后，`_fetch_clean` 也成死代码，**进而**触发构造器大量字段塌缩——比单模型审查发现的更深。

#### A4.1 方法删除

| 删 | 方法 | 行号 | 行数 |
|---|---|---|---|
| ✅ | `_rule_pick` | line ~41~62 | ~22 |
| ✅ | `_llm_pick` | line ~63~94 | ~32 |
| ✅ | `_fetch_clean` | line ~84~93 | ~10 |
| ✅ | `_fetch_with_backfill` | line ~95~140 | ~46 |
| ✅ | `_semaphore` 方法 | line ~35~39 | ~5 |
| 🔵 保留 | `collect` 方法（流程化简见 A4.3）|

#### A4.2 构造器塌缩

```python
# 删（旧）
class CollectionPipeline:
    def __init__(self, llm, http, parser, search_source,
                 max_top_n: int = 3, pick_timeout: int = 20, max_concurrency: int = 5):
        self.llm = llm
        self.http = http
        self.parser = parser
        self.search_source = search_source
        self.max_top_n = max_top_n
        self.pick_timeout = pick_timeout
        self.max_concurrency = max_concurrency
        self._sem: asyncio.Semaphore | None = None

# 改为
class CollectionPipeline:
    def __init__(self, search_source):
        self.search_source = search_source
```

塌缩字段：`llm`、`http`、`parser`、`max_top_n`、`pick_timeout`、`max_concurrency`、`_sem` 全删。

**影响**：`builder.py` 创建 `CollectionPipeline` 时不再传这些参数；所有测试 mock 构造 pipeline 的姿势同步改。

#### A4.3 collect 方法主流程化简

删 `if/else` 分叉（line ~144~169 那段），塌平为单 Tavily 路径：

```python
# 旧（保留 Tavily 分支，删 SerpAPI 分支后 if/else 仍在）
if self.search_source.available():
    trace.append({"step": "search", "provider": self.search_source.name})
    if getattr(self.search_source, "returns_bodies", False) is True:
        # Tavily 路径
        ...
    else:
        # SerpAPI 路径（删）
        ...
else:
    trace.append({"step": "search_skipped", "reason": "no_api_key"})

# 新
if self.search_source.available():
    trace.append({"step": "search", "provider": self.search_source.name})
    tav_results = await self.search_source.search(
        f"{competitor_name} 产品 功能 定价")
    valid = 0
    for r in tav_results:
        if r.url and r.url not in seen_urls and not is_low_quality(r.text):
            _add(r.text, r.url)
            sources.append(r.url)
            seen_urls.add(r.url)
            valid += 1
    trace.append({"step": "tavily", "results": valid})
else:
    trace.append({"step": "search_skipped", "reason": "no_api_key"})
```

`returns_bodies` 检查删除（恒为 True，见 Part 7 trade-off）。

---

## Part 2：删除清单（测试）

### B1. `tests/conftest.py`：fixture 改名 + 改职责

```python
# 旧
@pytest.fixture(autouse=True)
def lock_search_provider(monkeypatch):
    """锁定 SEARCH_PROVIDER=serpapi，使集成测试不受本地 .env 影响。

    集成测试的 LLM mock 序列按 serpapi 路径（含选页调用）编排，
    若本地 .env=tavily 会改变 build_graph 注入的 source 导致调用次数错位。
    tavily 专项测试各自显式构造 TavilySource，不读此配置，不受影响。
    """
    monkeypatch.setattr(settings, "SEARCH_PROVIDER", "serpapi")

# 新
@pytest.fixture(autouse=True)
def shield_local_env(monkeypatch):
    """屏蔽本地 .env 的 TAVILY_API_KEY 污染所有测试。

    集成测试需要明确控制 TavilySource.available() 状态：
    - 走主线测试 → 自行 monkeypatch TAVILY_API_KEY="K"
    - 走占位降级测试 → 不设，本 fixture 已默认置空
    Tavily 专项测试用 MagicMock 构造 source，不读此配置，不受影响。
    """
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
```

**关键修订**：保留 fixture 而不是删除（doubt-driven 双模型一致命中：删除会让本地 .env 的 `TAVILY_API_KEY` 污染所有测试）。

### B2. `tests/unit/test_sources.py`

| 操作 | 测试 |
|---|---|
| ✅ 删 | `test_serpapi_unavailable_without_key` |
| ✅ 删 | `test_serpapi_available_with_key` |
| ✅ 删 | `test_serpapi_search_parses_candidates_and_uses_query_key` |
| ✅ 删 | `test_serpapi_search_chinese_query_encoded` |
| ✅ 删 | `test_serpapi_search_empty_on_none` |
| ✅ 删 | `test_serpapi_search_empty_when_unavailable` |
| 🔵 保留 | 4 个 `test_tavily_*` |

**净变化**：-6 测试。

### B3. `tests/unit/test_collection_pipeline.py`（doubt-driven 修订）

之前方案 B 误以为删 4 个；实际跟 `_llm_pick`/`_rule_pick`/`_fetch_clean`/`_fetch_with_backfill` 相关测试有 **7+ 个**：

| 操作 | 测试 |
|---|---|
| ✅ 删 | `test_rule_pick_prefers_official_and_pricing_paths` |
| ✅ 删 | `test_llm_pick_used_when_key_present` |
| ✅ 删 | `test_llm_pick_timeout_falls_back_to_rule` |
| ✅ 删 | `test_llm_pick_malformed_result_falls_back_to_rule` |
| ✅ 删 | `test_soft404_page_excluded_from_sources`（依赖 `_fetch_clean`，PD-1 决议不补 Tavily 等价）|
| ✅ 删 | `test_replenish_*` 系列（依赖 `_fetch_with_backfill` 候选池递补）|
| ✅ 删 | `test_backfill_does_not_pad`（同上）|
| 🔵 保留 | Tavily 相关、占位降级相关、构造器塌缩后能存活的测试 |

执行时按 pytest 实际报错确认全数（doubt-driven 估算"7+"非精确数）。**净变化**：估 -7~-9 测试。

### B4. `tests/unit/test_config.py`

| 操作 | 测试 |
|---|---|
| ✅ 删 | `test_invalid_search_provider_falls_back_to_serpapi`（`_provider_env` 已删）|
| ⚙️ 改 | `test_settings_load_from_env`：删 `SEARCH_API_KEY` / `SEARCH_PROVIDER` 断言，保留 `TAVILY_API_KEY` |
| 🔵 保留 | `_int_env` 相关测试（与 SerpAPI 无关）、`SEARCH_TOP_N` 测试 |

### B5. `tests/unit/test_http_client.py`

数据 URL 改名（`https://serpapi.com/search` → `https://api.tavily.com/search` 或通用 URL），**不删 `get_json`/`_redact_key` 单测**——这俩是通用 HTTP 工具，删 SerpAPI 不影响。

### B6. `tests/unit/test_profile_schema.py`

**不动**——里面 `"provider": "serpapi"` 是 `pipeline_trace` 的字面量数据，跟 `SEARCH_PROVIDER` 配置无关（doubt-driven N-1 噪声归类）。

### B7. `tests/integration/test_graph.py` + `test_api.py` + `test_trace_api.py`（doubt-driven 重大修订）⚠️

**这是单/双模型审查命中最深的硬伤区**——三个文件**都要改**，不止 fixture 改名：

#### B7.1 fixture：加 `TAVILY_API_KEY="K"` monkeypatch

```python
# 三个测试文件中，每个测试的 fixture 都要加：
monkeypatch.setattr(settings, "TAVILY_API_KEY", "K", raising=False)
# （或用 monkeypatch.setattr 一次性给 fixture 加 + raising=False 防字段不存在时报错）
```

#### B7.2 LLM mock 序列：删 `_llm_pick` 步、call_index 改值

当前 7 步 mock 序列（典型）：
```python
mock_llm.call_json.side_effect = [
    {"goal_type": ...},                 # 1. parse_goal
    {"competitor_type": ...},           # 2. classify
    {"urls": ["https://..."]},          # 3. _llm_pick ← 删
    {basic_info ...},                   # 4. extract_profile（变成 step 3）
    {analysis ...},                     # 5. analyze
    {report ...},                       # 6. write
    {issues ...},                       # 7. inspect
]
# 断言 call_index[0] == 7 → 改为 == 6
```

每个集成测试单独检查序列长度，包括反馈闭环重试路径（重试时 collector/analyzer/writer 会重跑，对应 mock 序列也长，重试路径序列同步重排）。

#### B7.3 mock_http 加 `post_json`

当前 mock 只配 `mock_http.get_json`（SerpAPI 用），Tavily 走 `post_json`，**未配则 await MagicMock 直接挂**：

```python
# 加（每个集成测试）
mock_http.post_json = AsyncMock(return_value={
    "results": [
        {"url": "https://alipay.com/pricing", "raw_content": "支付宝定价介绍" * 30},
        {"url": "https://alipay.com/features", "raw_content": "支付宝功能列表" * 30},
        {"url": "https://alipay.com/help", "raw_content": "支付宝帮助文档" * 30},
    ]
})
# get_json 可保留或删（看是否仍有别的地方调）
```

### B8. 各测试文件改完后，预期最终测试数

```
原 139 → 删 6（B2）+ 删 7~9（B3）+ 删 1（B4）= 删 14~16
最终 ≈ 123~125
```

不再说"115-120"——doubt-driven 指出这个数字不严谨（Codex #18）。**实际数字以执行时 pytest 报告为准**。

---

## Part 3：配置 / 文档（C 类）

### C1. `.env.example`

```diff
DOUBAO_API_KEY=your_api_key_here
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_EP=ep-20260514111325-xjmj7
+TAVILY_API_KEY=your_tavily_api_key_here
```

注：`SEARCH_API_KEY` / `SEARCH_PROVIDER` **本来就不在 `.env.example` 里**（这是个历史 bug，本次顺手修）。

### C2. `CLAUDE.md`

**doubt-driven 修订**：不止 line 98。整段重写两处：

#### C2.1 line 95~100「环境变量」段

```diff
 运行需在项目根目录配置 `.env`：
 - `DOUBAO_API_KEY` 必填
-- 搜索主线按 `SEARCH_PROVIDER` 切换：`serpapi`（需 `SEARCH_API_KEY`）或 `tavily`（需 `TAVILY_API_KEY`）；缺 key 则跳过搜索主线、仅走专源/占位降级
+- `TAVILY_API_KEY` 选填——搜索主线 Tavily 的鉴权 key；缺 key 则跳过搜索主线、走占位降级（completeness=0.0）
 - 其余配置见 `src/utils/config.py` 默认值
```

#### C2.2 line ~114「采集层」段

```diff
- ……搜索源插件在 `src/tools/sources.py`（SerpAPI / Tavily 双 provider，按 `SEARCH_PROVIDER` 切换；iTunes 已于 06-06 因同名污染移除）。analyzer/writer/inspector 仍为 `(llm)` 依赖。
+ ……搜索源插件在 `src/tools/sources.py`（仅 Tavily，06-07 弃用 SerpAPI；iTunes 已于 06-06 因同名污染移除）。Tavily 一次调用直返带正文 SourceResult，跳过传统的"搜索→选页→抓取"三步走（_llm_pick/_rule_pick/_fetch_with_backfill 已于 06-07 删除）。analyzer/writer/inspector 仍为 `(llm)` 依赖。
```

### C3. `PROGRESS.md` / `DECISIONS.md`

**doubt-driven 修订**：历史条目作为历史不动；只 append 06-07 决策条目（与项目惯例一致，DECISIONS.md 06-04 的"SerpAPI 鉴权反转"也是 append）。

#### C3.1 PROGRESS.md append

```markdown
## 2026-06-07（弃用 SerpAPI：搜索源单 provider 化）
- 完成（feat/drop-serpapi 分支，N commits）：
  - 删除 SerpApiSource 类、SEARCH_API_KEY/SEARCH_PROVIDER 配置、collection_pipeline 的 _llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法（共 ~115 行生产代码）
  - 删除 conftest 锁 provider 的 fixture，改为 shield_local_env（屏蔽本地 .env 的 TAVILY_API_KEY 污染）
  - 三个集成测试 fixture 加 TAVILY_API_KEY="K"、LLM mock 序列删 _llm_pick 步、mock_http 替换 get_json 为 post_json
  - .env.example 补 TAVILY_API_KEY；CLAUDE.md 同步两处描述
  - 最终测试 N 通过、ruff 全清
  - 走 brainstorming → doubt-driven 单模型 17 条 + 跨模型 Codex 20 条审查 → RECONCILE 9 条 actionable + 3 条产品决策 → writing-plans → execute
- 进行中：feat/drop-serpapi 合并回 master
- 下一步：接主战场 30 task 分场景报告（worktree-A scenario-reports）
- 阻塞：无
- 安全提醒：无（本次重构仅删代码、不引入新 key）
```

#### C3.2 DECISIONS.md append

```markdown
## 2026-06-07: 弃用 SerpAPI，仅保留 Tavily 作为唯一搜索源
- 选择：删除 SerpApiSource 类、SEARCH_API_KEY/SEARCH_PROVIDER 配置开关、collection_pipeline 的"搜索→选页→抓取"两步走机制（_llm_pick/_rule_pick/_fetch_clean/_fetch_with_backfill 四方法 + 构造器塌缩）。Tavily 一次调用直返带正文，跳过中间所有步骤
- 理由：06-06 实测证实 Tavily 在中文场景质量明显优于 SerpAPI（语雀 1.0 / 飞书 0.85 completeness）；双 provider 架构带来开关复杂度（SEARCH_PROVIDER）、conftest 防污染 fixture、builder if/else、115 行 SerpAPI 专项代码——与 Cooper 选择的"代码简化、答辩故事单一 AI 搜索"目标矛盾。git 历史保留，未来若需恢复可 revert
- 反转的旧决策：06-06「双 provider 切换、保留 SerpAPI 作为可选 fallback」（半年前的决策反转，作为历史保留）
- 备选 1：保留 SerpAPI 但删 SEARCH_PROVIDER 开关、Tavily 作为默认（排除：仍需双 provider 代码维护、答辩故事不干净）
- 备选 2：仅删 SerpAPI 类、保留 SEARCH_PROVIDER 字段（排除：废留架构假承诺）
- 实现路径：方案 B'（doubt-driven 双模型审查后修订），分 6-8 个细粒度 commit；commit 顺序：测试先改不依赖 → 删生产代码 → 删 SerpAPI 专项测试 → 文档同步
```

---

## Part 4：执行约束

| 维度 | 决策 | 来源 |
|---|---|---|
| 时间盒 | **2.5-3.5 小时**（PD-3） | doubt-driven 双模型审查后修订（原 1.5-2 低估）|
| commit 颗粒 | **6-8 个细粒度 commit**（PD-2） | 与你历史习惯一致（06-06 14 commits / 06-04 16 commits）|
| commit 顺序 | 测试先改 → 删生产 → 删测试 → 文档同步 | doubt-driven A-9：避免中间 commit 出现 import 失败 |
| 验证标准 | pytest 全过 + ruff 全清 | 你 brainstorm 阶段拍板 |
| soft-404 等价测试 | **不补**（PD-1） | 前提：`is_low_quality` 自身有单测 ✅（`tests/unit/test_quality_gate.py`）|
| doubt-driven | **走完，单+跨模型 Codex 二审** | 你拍板 |
| 跨模型工具 | Codex CLI（azure_openai/gpt-5.5） | 第 1 次 502 失败、重试通过 |

---

## Part 5：commit 拓扑（6-8 个细粒度）

```
1. test: integration tests 加 TAVILY_API_KEY=K monkeypatch + mock_http.post_json
   （让 3 个集成测试在生产代码改之前先适应 Tavily 路径，pytest 仍通过）

2. test: integration tests 删 LLM mock 序列里的 _llm_pick 步、call_index 同步
   （让 mock 序列按 Tavily 路径调用次数编排，pytest 仍通过）

3. refactor: collection_pipeline 删 _rule_pick / _llm_pick / _fetch_clean / _fetch_with_backfill 四方法 + 构造器塌缩
   （删生产代码，所有依赖已在 1+2 解除）

4. refactor: builder + sources 删 SerpApiSource，单 TavilySource 注入
   （删 sources.py 类、改 builder if/else 为单 TavilySource）

5. refactor: config 删 SEARCH_API_KEY / SEARCH_PROVIDER / _provider_env / PICK_LLM_TIMEOUT / MAX_FETCH_CONCURRENCY
   （删配置字段）

6. test: 删 test_sources.py / test_collection_pipeline.py / test_config.py 中 SerpAPI 专项测试 + conftest fixture 改名 shield_local_env
   （删测试和 fixture 改名）

7. docs: CLAUDE.md 整段重写 + .env.example 补 TAVILY_API_KEY
   （文档同步）

8. docs: PROGRESS.md / DECISIONS.md append 06-07 决策条目
   （决策记录）
```

每个 commit 后跑 `pytest -q` 确认全过、`ruff check src tests` 全清后才 commit 下一个。

---

## Part 6：评审记录（doubt-driven 完整循环）

### 单模型对抗审查（fresh-context subagent，code-reviewer with 对抗 prompt 覆盖）

17 条 finding，去重后核心 5 条命中：
1. 集成测试 LLM mock 序列依赖 SerpAPI 主线（最致命）
2. test_api.py 不在 B5 列表中
3. `_provider_env` 删除评估错误
4. `_fetch_clean` 死代码评估错误（其实未死，但删 `_fetch_with_backfill` 后会变死）
5. 时间预算严重低估

### 跨模型对抗审查（Codex CLI，azure_openai/gpt-5.5，read-only 沙箱）

20 条 finding，与单模型重叠的 ~9 条，新增独立命中 ~5 条：
1. （重复）集成测试 TAVILY_API_KEY 没设
2. （重复）mock_http 没配 post_json
3. （重复）LLM mock 序列要重排
4. **新增**：conftest fixture 双重职责（屏蔽 .env 是更深一层）
5. **新增**：构造器塌缩——`http`/`parser`/`max_concurrency` 等多字段也成悬空
6. （重复）插件契约硬编码隐式从鸭子类型变 SourceResult 必返
7. （重复）CLAUDE.md 不止改 line 98

### RECONCILE（4 类分类）

| 类别 | 数量 | 处理 |
|---|---|---|
| Contract 误解 | 1（R-1：HTTP/config 副作用边界）| 修 contract、明确"通用工具保留" |
| Valid + Actionable | 9（A-1 ~ A-9）| 全部纳入修订方案 B' |
| Valid Trade-off | 2（T-1 `_fetch_clean`、T-2 插件契约）| 已纳入 spec 处理 |
| Noise | 3（test_profile_schema 字面量、test_count、双方 finding 重叠）| 不动 |

### 产品决策（按 memory feedback_pm_dev_collab_with_doubt_driven 强制流程）

| 编号 | 决策点 | Cooper 拍板 |
|---|---|---|
| PD-1 | soft-404 Tavily 等价测试 | 不补，靠 is_low_quality 自身单测 |
| PD-2 | commit 颗粒度 | C：6-8 commit 细粒度（与历史习惯一致）|
| PD-3 | 时间盒 | B：2.5-3.5 小时 |

### STOP 条件

- ✅ 满足"actionable findings 显著但 contract 修订后基本归零"
- ✅ 不触发"doubt theater"红旗（第 1 轮就 9 条 actionable）
- ❌ 不走第 2 轮 doubt cycle——你拍板"停在这里"

---

## Part 7：已知 trade-off

### T-1：`returns_bodies` 类属性保留为占位标记

**问题**：删 SerpAPI 后 `returns_bodies` 检查恒真，删除会让 `sources.py` 的隐式契约从"鸭子类型"变"必须返回 `SourceResult`"。未来加新 provider 若返回 dict 候选会 `AttributeError`。

**决策**：`TavilySource.returns_bodies = True` 类属性保留，加注释 `# 占位标记：当前仅 Tavily 走带正文路径，未来若有不带正文 provider 需引入条件分支`。`collection_pipeline` 内的检查删除（恒真无意义）。

**未来扩展**：若引入新 provider，回到"按 returns_bodies 分叉"的双路径架构（git 历史可参考 06-03/06-06）。

### T-2：测试覆盖窄化

**问题**：删 SerpAPI 后失去：
- soft-404 集成测试（PD-1 决议不补 Tavily 等价）
- LLM 选页超时降级测试（这条业务逻辑随 `_llm_pick` 删除消失，无需替代）
- 候选池递补、降级计数等 SerpAPI 专属场景

**决策**：接受。理由：① Tavily 主线无中间步骤、容错路径少；② 6/10 答辩前主战场是 30 task 分场景报告，测试覆盖只需"不降低核心 contract 覆盖度"，不需要扩展。

### T-3：CollectionPipeline 构造器塌缩破坏向前兼容

**问题**：构造器签名从 `(llm, http, parser, search_source, max_top_n, pick_timeout, max_concurrency)` 减为 `(search_source)`，**任何外部代码调用 CollectionPipeline 都会失败**。

**核查**：grep 显示生产代码中 `CollectionPipeline(...)` 仅在 `builder.py` 调用一处；测试中均用 `CollectionPipeline(MagicMock(), ...)` 等 mock 形式构造，会随 commit 6（删测试）一起改。**无外部依赖（项目尚未发布、没有外部 importer）**。

**决策**：接受。

---

## Part 8：风险与回滚

### 风险

1. **集成测试改不干净导致 pytest 卡住** —— 用 commit 1+2 先改测试再删生产，每步 pytest 必须全过；若卡住单独排查、不强行向下推
2. **`is_low_quality` 单测覆盖不足导致 PD-1 假设破灭** —— 已先验证 `tests/unit/test_quality_gate.py` 存在；执行时如发现覆盖薄，回到 PD-1 重审
3. **本地 .env 包含 TAVILY_API_KEY 导致集成测试假性走真路径** —— 已通过 conftest 改名为 shield_local_env 屏蔽

### 回滚

`git revert` 本批 commit 即可恢复 SerpAPI。git 历史完整保留 SerpApiSource 类与所有相关代码。

---

## Part 9：Spec 自审

按 brainstorming 技能要求：

| 项 | 检查 | 结果 |
|---|---|---|
| Placeholder | "TBD"/"TODO"/不完整字段 | 无 |
| Internal consistency | 各节描述是否冲突 | Part 0 不在范围 / Part 1 删除清单 / Part 7 trade-off 一致 |
| Scope | 是否单一可执行 | 是，单一 refactor 任务 |
| Ambiguity | 是否多解释 | "重新排列 LLM mock 序列"（Part 2 B7.2）由 commit 拓扑（Part 5）+ 实际报错驱动，无歧义 |

**自审通过，待 Cooper 审阅。**
