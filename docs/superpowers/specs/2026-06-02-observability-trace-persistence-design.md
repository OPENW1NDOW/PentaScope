# 设计文档：可观测性与中间产物追溯

- 日期：2026-06-02
- 状态：已通过 brainstorming + doubt-driven 评审（单模型 + Codex 跨模型），待实现
- 关联评分项：多 Agent 协作可信度（35%）、技术深度与工程完整度（25%）

## 1. 背景与目标

开题材料明确要求：**「可观测：日志可查看，每个 Agent 的决策过程与中间产物均可追溯。」**

现状诊断（2026-06-02）：

- **日志不落盘**：`src/utils/logger.py::setup_logger` 定义了文件 handler，但全代码库零调用；各模块用裸 `logging.getLogger(__name__)`，root logger 未配 handler，`logs/app.log` 从不生成，全链路 INFO 日志（`[graph] → collector` 等）既不进控制台也不进文件。
- **中间产物零落盘**：`profiles`/`analysis`/`report`/`feedback` 全程只活在内存 `AnalysisState`，`graph.ainvoke` 跑完即丢，无法事后追溯。
- **信息溯源部分达成**：`report.metadata.data_sources` 已由 `builder.py` 从 profile 汇总回填（达标），但中间产物与决策过程无存档。

目标：实现「落盘 + 前端可视化追溯」，按 `trace_id` 分目录存储四阶段产物、重试快照、元信息与日志副本，并通过新增 API 供前端读取。

## 2. 范围与非目标

### 范围

1. 新增 `TraceWriter` 模块，负责中间产物落盘（容错、版本快照、原子写）。
2. graph 各节点接线，产出后即落盘。
3. 接线 `setup_logger`，全局日志写 `logs/app.log`，并为每次分析生成 `run.log` 副本。
4. 新增追溯 API 端点 `GET /api/v1/trace/{trace_id}`。
5. 前端新增「执行追溯」面板。
6. trace_id 改为北京时间格式。

### 非目标（显式权衡）

- **不做跨进程文件锁 / 完整互斥**。本系统面向答辩演示，轻度并发场景下「不同请求写不同 trace 目录 + 原子写 + 碰撞规避」已足够；完整锁是过度设计。
- **不存 prompt / LLM 原始响应**。产物 + `meta.node_trace` 已覆盖决策过程主体；全存会令范围爆炸，留作未来扩展（见 §9）。

## 3. 场景假设

- **轻度并发**：可能有多个分析请求接近同时发起（非高并发生产负载）。设计须避免 trace_id 碰撞与写撕裂，但无需重型并发控制。
- 单进程 FastAPI + LangGraph，节点串行执行。
- 跨平台：Windows（开发）+ 可能 Linux（部署）。

## 4. 目录结构与产物布局

每次分析在 `runs/<trace_id>/` 下生成：

```
runs/
└── 20260602-143052-a3f8c1/        # 北京时间 + 6 位随机短码
    ├── meta.json                  # 元信息（含 node_trace 路由决策序列）
    ├── 01_profiles.json           # 采集 Agent 产物（List[CompetitorProfile]）
    ├── 02_analysis.json           # 分析 Agent 产物（AnalysisResult）
    ├── 03_report.json             # 撰写 Agent 产物（最新版）
    ├── 04_feedback.json           # 质检 Agent 产物（最新版）
    ├── 01_profiles_v1.json        # 重试快照（若打回 collector 时产生）
    ├── 03_report_v1.json          # 重试快照（若打回 writer 时产生）
    ├── 04_feedback_v1.json        # 重试快照
    └── run.log                    # 该次分析的全链路日志副本
```

### 命名规则

- `NN_<stage>.json` 的 `NN` 数字前缀 = 流水线顺序，目录天然按执行顺序排列。
- **最新版永远不带版本号；历史版本为 `_vN`，N 从 1 起算。**
- **版本快照对全部 4 个 stage 一视同仁**：反馈闭环可打回 `collector` 或 `writer`（见 `builder.py::should_continue`）。打回 collector 时 `01_profiles`/`02_analysis` 也会重写，其旧版同样存为 `_vN`。`TraceWriter` 通用处理，不区分 stage。

### 存储路径

`runs/` 使用**基于项目根的绝对路径**（不依赖进程 CWD），避免前后端不同启动目录导致路径不一致。`runs/` 加入 `.gitignore`（运行时产物，与 `logs/` 同理）。

## 5. trace_id 格式

- 格式：`20260602-143052-a3f8c1` = 北京时间 `YYYYMMDD-HHMMSS` + `-` + **6 位随机十六进制**。
- 北京时间用 `datetime.now(timezone(timedelta(hours=8)))` 显式锁定东八区，不依赖系统时区。
- **碰撞规避**：生成后检查 `runs/<trace_id>/` 是否已存在，存在则重新生成。轻度并发下廉价规避，非重型锁。
- 替换 `routes.py:18` 现有的 `str(uuid.uuid4())[:8]`。
- 用途：目录名、`report`/`feedback`/`state` 的 `trace_id` 字段、API 响应、日志行。
- **契约兼容性已验证**：现有测试用 `"abc-123"`/`"test-001"` 等任意字符串占位，无格式/长度断言；前端仅展示不解析。换格式不破坏现有契约。

## 6. TraceWriter 模块

新建 `src/tools/trace_writer.py`，与 `llm_client`/`http_client` 平级。

```python
class TraceWriter:
    def __init__(self, trace_id: str, base_dir: str):
        # 仅记录 trace_id + 绝对目录路径 + {stage: 写入次数} 计数；不做任何 I/O

    def save_stage(self, stage: str, data: BaseModel | list) -> None:
        # stage 限定为代码内硬编码常量集合（见下），非用户输入
        # 1. mkdir(parents=True, exist_ok=True)
        # 2. 若 NN_stage.json 已存在：扫描目录现有 NN_stage_v*.json，取最大 N+1（无则 N=1），
        #    用 os.replace 把现有 NN_stage.json 改名为 NN_stage_vN.json（N 取自磁盘实际版本，
        #    非内存计数器——避免进程重启后计数归零撞已存在的 _v1）
        # 3. 序列化：isinstance(data, list) -> [m.model_dump(mode="json") for m in data]（空 list 写 []）
        #            BaseModel -> data.model_dump(mode="json")
        # 4. 原子写：先写临时文件 -> os.replace 落位到 NN_stage.json
        # 整段裹 try/except；失败仅 logger.warning，绝不抛

    def save_meta(self, meta: dict) -> None:
        # 覆盖写 meta.json（原子写），不进版本计数，try/except 仅 warning

    @staticmethod
    def new_trace_id(base_dir: str) -> str:
        # datetime.now(UTC+8) -> "YYYYMMDD-HHMMSS-xxxxxx"；查目录碰撞则重生成
```

### 契约要点

- **序列化统一用 `model_dump(mode="json")`**：避免 Pydantic v2 默认 `model_dump()` 残留 `datetime`/`HttpUrl` 对象导致 `json.dumps` 抛 `TypeError` 被 warn-only 静默吞掉。
- **原子写**：所有写操作先写同目录临时文件再 `os.replace` 落位；`os.replace` 在 Windows/Linux 均能原子覆盖，行为一致，解决改名窗口期与 Windows `FileExistsError`。
- **容错边界**：`__init__` 不做任何 I/O；所有 I/O 在 `save_*` 内部，整段 try/except 仅 warning，绝不向上抛——保证分析主流程不受落盘失败影响。
- **stage 常量集合**：`{"01_profiles", "02_analysis", "03_report", "04_feedback"}`，硬编码，杜绝动态拼接文件名。
- JSON 写 `ensure_ascii=False, indent=2`。logger 用 `logging.getLogger(__name__)`，前缀 `[trace]`。

## 7. graph 层接线与数据流

- **TraceWriter 注入 `build_graph(...)`**（与 `llm`/`http`/`parser` 同为执行依赖，**不放进 state**，避免污染数据契约）。
- **各节点落盘点**：

  | 节点 | 落盘调用 |
  |------|---------|
  | `collector_node` | `tw.save_stage("01_profiles", profiles)` |
  | `analyzer_node` | `tw.save_stage("02_analysis", analysis)` |
  | `writer_node` | `tw.save_stage("03_report", report)`（回填 sources 之后） |
  | `inspector_node` | `tw.save_stage("04_feedback", feedback)`（回填 quality_score 之后） |

- **重试快照自动生效**：writer/inspector/collector 在打回后被再次调用，第二次 `save_stage` 时 `TraceWriter` 自动把上一版改名 `_vN`，节点无感知。
- **meta 写两次**（解决中途崩溃孤儿问题）：
  1. `routes.py` 中 `graph.ainvoke` **之前**：写 `status="running"` 的 meta（trace_id、输入、开始时间）。
  2. `graph.ainvoke` **之后**（成功或异常）：覆盖为 `status="completed"`/`"failed"`，补 end 时间、retry_count、node_trace。
  - 即使进程中途崩溃，也留有 `status="running"` 的 meta 表明"有此次运行、卡在何处"。
- **meta.node_trace**（轻量覆盖"决策过程"）：记录节点执行序列，以及每次质检打回的 issues 摘要与目标 agent。`feedback.json` 本身即质检决策记录。

## 8. 追溯 API 与日志

### 追溯 API

新增 `GET /api/v1/trace/{trace_id}`：

```json
{
  "trace_id": "20260602-143052-a3f8c1",
  "meta": { ... },
  "stages": {
    "profiles": { ... }, "analysis": { ... },
    "report": { ... }, "feedback": { ... }
  },
  "snapshots": ["01_profiles_v1", "03_report_v1", "04_feedback_v1"],
  "log": "..."
}
```

- **快照按需取内容**：`snapshots` 默认只返版本名列表；新增 `GET /api/v1/trace/{trace_id}?version=03_report_v1` 取指定历史版本内容，供前端对比"打回前后怎么改"。默认响应不膨胀。
- **路径穿越双重防护**：① `re.fullmatch(r"\d{8}-\d{6}-[0-9a-f]{6}", trace_id)`（`fullmatch` 两端锚定）拒绝非法 id；② 拼路径后 `Path(base_dir / trace_id).resolve()` 校验仍在 `runs/` 目录下。
- 目录不存在返回 **404**（非 500）。
- 区分「跑出空」与「未跑」：API 据「文件存在但内容为 `[]`」与「文件缺失」区分，并以 `meta.node_trace` 佐证。
- 前后端保持分离：前端只经此 API 读产物，绝不直接读文件系统。

### 日志接线

- **全局日志**：API 启动时（`main.py`）初始化 root logger，配置 console + `logs/app.log` 两个 handler、INFO level，使全链路日志可见。
- **每次分析日志副本**：每次分析在 `runs/<trace_id>/run.log` 另存一份该次日志，便于按 trace_id 追溯单次运行。
- 轻度并发下日志副本可能有少量串扰（多请求共享 root logger）——属可接受权衡，演示场景串行为主。

## 9. 错误处理与未来扩展

### 错误处理

- 落盘失败：仅 `logger.warning`，分析继续、报告照常返回。
- meta 中途崩溃：留有 `status="running"` 记录。
- 追溯 API 非法 trace_id：404；目录缺失：404。

### 未来扩展（本期不做）

- 存储 prompt / LLM 原始响应，实现更细粒度的决策过程追溯。
- 落盘失败的结构化暴露（当前仅 warning，API 无法感知持久化失败）。
- 跨进程并发的完整锁机制（若演变为多用户生产负载）。

## 10. 测试策略

- **TraceWriter 单测**：单模型/list 序列化、空 list、重试快照 `_vN` 命名、`model_dump(mode="json")` 处理 datetime/Url、落盘失败 warn 不抛、原子写、碰撞规避。
- **追溯 API 测试**：正常读取、目录不存在 404、路径穿越（`../`、绝对路径、非法格式）被拒、`?version=` 取历史版本。
- **集成测试**：跑完整 graph，验证 `runs/<trace_id>/` 下产物齐全、meta 两次写、打回时快照生成。
- **回归**：现有 51 测试不受 trace_id 格式变更影响。
