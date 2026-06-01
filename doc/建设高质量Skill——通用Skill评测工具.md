# 建设高质量 Skill——通用 Skill 评测工具

<!-- Converted from doc/建设高质量Skill——通用Skill评测工具.pdf using pdftotext. -->

在 Agent 生态里，Skill 是连接模型能力与业务工具、流程、知识的关键说明书。它写得是否清晰、边界是否准确、路径是否稳定，会直接影响 Agent 的执行质量、业务适配性和复用效率。随着公司内部 Skill 数量快速增长，仅靠人工经验判断“好不好用”已经不够，需要建立一套统一、可量化、可复用的质量评测方法。

`skill-evaluation` 正是围绕这一目标设计的通用评测工具，本身即是一款可直接安装的原生 Skill。只需与 Agent 进行一次自然对话，即可一键发起对任意 Skill 的全自动评测，开箱即用，最后输出一份针对目标 `SKILL.md` 的完整报告。它把目标 `SKILL.md` 转换为结构化 Task，经人工 Review 确认后，在真实 OpenClaw Agent 环境中多轮执行，再由 LLM Judge 结合任务要求、评分标准和执行轨迹完成评分与问题归因，最终沉淀整体报告 `REPORT.md`、完整评价 `summary.json` 和多模型对比结果（如果配置）。

这套机制不止是给 Skill 打一个分数，更重要的是回答“下一步该优化哪里”：是 Skill 文档或外部环境存在可用性问题，是 Agent 执行过程与 Skill 适配不足，还是任务设计本身需要调整。同时，评测过程中形成的 Task 集可作为长期数字资产，支撑回归测试、模型选型、质量分级和内部 Skill 生态的规模化治理。

## 一、Skill 评测的必要性

评测的必要性主要体现在两个方面：

- 助力开发者精准迭代，提升 Skill 质量。通过系统化评测，建立可量化的标准，对 Skill 的元数据准确性、Agent 实际执行过程可能出现的问题、整体用时和资源消耗等方面进行校验，帮助 `SKILL` 开发者快速定位优化方向，推动 Skill 从“可用”向“高效好用”升级，减少迭代成本。
- 规范内部 Skill 能力管理，提升复用与协同效率。评测可实现对内部 Skill 质量的客观分级，为开发者提供明确的优化依据，同时便于各团队快速筛选适配自身业务的 Skill，提升 Skill 的复用率。此外，内部 Skill 开发规范化，以及通过评测形成的任务库，可沉淀为评测公司 Agent 内部能力的数字资产。

`skill-evaluation` 提供一个标准化的 `SKILL` 评测工具，通过评判真实的 Agent 执行轨迹，为目标 `SKILL` 生成全方位的打分，并指出存在的问题和优化方向，助力 `SKILL` 的迭代。

## 二、Skill 通用评测工具：skill-evaluation

`skill-evaluation` 是围绕 Skill 评测设计的工具，目前已上架 eSkill 平台，并完全适配 EWork。

安装后，可以直接与 Agent 交互，例如：“使用 `skill-evaluation` 评测 xxx `SKILL`”，即可执行完整的评测链路。

- Skill 名称：`skill-evaluation`
- eSkill 平台地址：<https://ework.efunds.com.cn/skill/detailPage?id=318>
- 安装方法：与 EWork 对话“使用 `eskill-finder` 技能安装 `skill-evaluation` 技能。”即可。

如需要在其他环境或 Agent 中使用，或需要基于本 `SKILL` 依赖的 Python SDK 进行开发，请参考 `skill-evaluation：评测 SKILL 的 SKILL 与 SDK 技术文档` 中的详细介绍和代码仓库。

Agent 执行完毕后，不只会输出分数，还有针对目标 `SKILL` 的完整报告，包括可用性、效果、稳定性、效率的角度的指标和不同模型的执行比较（如果配置），以及执行过程中 Agent 出现的问题总结，辅助 `SKILL` 迭代。

### 2.1 整体架构

参照整体框架图，`skill-evaluation` 的核心不是单点脚本，而是一条围绕“Task 资产化”的评测闭环：先把目标 `SKILL.md` 转换为可执行、可评分、可复用的标准 Task，再通过人工审核保证任务合理性，随后在真实 Agent 环境中多轮执行，最后由 LLM Judge 结合任务要求、评分标准与执行轨迹完成评分和归因。

从架构上看，工具可以分为五层：

- **使用入口层**：面向不同使用场景提供 EWork 对话 / Agent、CLI 和 Python SDK 三种入口。普通开发者可以通过对话完成评测；需要自动化或批量接入时，可以使用 CLI 或 SDK。
- **流程编排层**：负责串起 `generate`、`approve`、`execute`、`evaluate-tasks` 等阶段，并维护 `run_id`、review 状态、artifacts 目录和最终报告，保证评测过程可暂停、可追溯、可复跑。
- **Task 资产层**：把目标 Skill 的能力边界、预期行为和评分 Rubric 固化为结构化 Task。Task 一旦沉淀下来，就可以用于回归测试、模型横向对比和后续质量验收。
- **执行与观测层**：通过 OpenClaw 在独立 workspace 中安装目标 Skill 并执行任务，保留 transcript、耗时、token 等运行信息，尽量还原 Skill 在真实 Agent 场景中的表现。
- **评估与报告层**：由 Judge 基于 Skill、Task、Rubric 和执行轨迹进行评分，同时区分 `SKILL/Task issue` 与模型执行适配性问题，最终产出 `REPORT.md`、`summary.json` 和多模型汇总。

三种使用入口共享同一套底层能力和产物结构，因此不同团队可以从轻量对话式评测起步，后续再平滑迁移到自动化回归或 CI 评测，而不需要重做任务集和指标体系。

### 2.2 端到端流程总览

针对一个目标 Skill，完整流程可以概括为“生成 Task → 人工 Review → Agent 执行 → LLM Judge → 汇总报告 → 回归复用”。其中，生成、审核、执行、评估四个环节彼此解耦：生成阶段只负责把能力转成任务；Review 阶段守住任务合理性和安全边界；执行阶段只面向任务目标运行 Agent；Judge 阶段再根据轨迹进行评分与归因。

这种拆分的价值在于减少相互污染：生成模型不会直接决定最终分数，执行 Agent 不提前看到 Judge 结论，Judge 也不是只看最终答案，而是结合过程证据判断失败原因。这样产出的报告不仅能回答“得分是多少”，还能回答“下一步应该改 Skill、改任务、修环境，还是换更适配的执行模型”。

## 三、以案例详解 Skill 评测 Pipeline

我们以内部的 `SKILL arxiv` 为例，完整地说明一次评测 Pipeline。`arxiv` 是围绕论文检索、论文元数据获取和内容摘要展开，因此评测任务会重点覆盖“能否找到目标论文”“能否提取标题、作者、日期、DOI、链接等关键信息”“总结是否基于可验证来源”“输出是否清晰可复用”等维度。

### 3.1 Task 生成：从 Skill 到可执行的 Task

评测的第一步，是把 Skill 的能力描述转换成结构化 Task。这里的关键不是让模型随意出题，而是把 `SKILL.md` 中声明的能力边界、输入输出、工具路径和注意事项转成可执行、可评分、可复用的测试样本。工具提供了两种 Task 生成模式：

- `llm_direct` 模式：默认方式，系统读取目标 Skill 的 `SKILL.md`，由任务生成模型直接产出若干候选 Task。这个模式不运行 OpenClaw，速度较快，大部分情况够用。
- `trace_assisted` 模式：在生成阶段先临时运行一次 OpenClaw，采集目标 Skill 的真实行为 trace，再把 trace 或 profile 作为上下文喂给任务生成模型，消耗较大且提升一般。

生成阶段还会做一次 Task validation。这里的 validation 是做结构和可用性探针：检查 Task 的字段是否完整、评价标准是否合理、grader 配置是否合法。它拦截的是“格式上就有问题”的任务，而不是“执行会失败”的任务。

在 `arxiv` 示例中，生成出来的 Task 会围绕论文检索和论文信息整理展开。比如要求 Agent 找到某篇论文，输出标题、作者、发布日期、DOI 或 arXiv 链接，并给出技术内容摘要；对应 Rubric 则会把“任务结果正确性、关键信息完整性、Skill 使用合理性、输出清晰可用性”等拆成可评分维度。

Agent 通过执行如下命令生成 Task 文件：

```bash
python3 scripts/run_skill_evaluation_pipeline.py generate \
  --skills-dir /path/to/target/skills \
  --skills skillA \
  --task-count 2 \
  --task-generation-model deepseek-v4-pro \
  --task-validation-model deepseek-v4-pro \
  --task-generation-mode llm_direct \
  --task-execution-models deepseek-v4-pro \
  --runs 3 \
  --task-timeout-seconds 1800 \
  --pass-threshold 0.7 \
  --task-judge-model deepseek-v4-pro
```

执行后，系统会创建一个目录，写入生成的标准 Task 文件，并把状态置为 `awaiting_review`。

### 3.2 Task Review：人工审核

自动生成的 Task 不能直接进入执行阶段，因为 Task 本身也可能存在问题：题目超出 Skill 能力范围、依赖不可用数据、要求高风险操作，或者 Rubric 太泛导致 Judge 难以稳定评分。因此，在 Task 生成后，流水线会停在 review checkpoint。Agent 会提示用户检查生成的 Task，并重点确认以下几件事：

- 选择的模型是否符合您的要求？（目前全部默认是 `deepseek-v4-pro`）
- 这个 Task 是否落在目标 Skill 的能力内？例如 arxiv Skill 应聚焦论文检索、元数据获取和论文摘要，不应被要求完成与论文无关的外部业务动作。
- Task 依赖的数据、账号、权限和外部系统，在当前环境里是否可用？例如目标论文是否真实存在，arXiv 页面或相关检索入口是否可访问。
- 任务是否包含不可逆动作或高风险操作？比如删除数据、发起真实交易等。
- LLM Judge Rubric 是否足够具体、可评判？例如不能只写“回答得好”，而要明确是否包含标题、作者、链接、日期、摘要依据和输出结构。

在这一步用户可以与 Agent 交互修改 Task，直到用户发送批准指令，任务才会被标记为批准执行：

```bash
python3 scripts/run_skill_evaluation_pipeline.py approve \
  --run-id <run_id>
```

这个设计保留了必要的人类判断：模型负责提高任务生成效率，人负责确认业务合理性、安全边界和环境前提。以 `arxiv` 示例来说，Review 的重点就是确认任务确实能通过论文检索完成，并且评分标准能区分“找到了论文但信息不完整”和“完全没有按 Skill 路径执行”这两类情况。

### 3.3 Task 执行

Task Review 经人类批准后，执行阶段开始工作。系统会读取 run 状态，用 OpenClaw 创建独立执行 SubAgent，并只把当前任务所需的目标 Skill 安装到 Agent workspace 中。

Agent 通过执行如下 Python 脚本启动执行过程：

```bash
python3 scripts/run_skill_evaluation_pipeline.py execute \
  --run-id <run_id>
```

每个 Task 默认执行 3 轮，单次超时 1800 秒。这个超时只计算被测 Agent 执行 Task 的时间，不包含 LLM Judge。若某次执行超时，系统仍会保留已产生的 transcript，交给 Judge 基于已有行为总结原因和评分。

多轮执行是观察稳定性的必要手段。以 `arxiv` 为例，如果同一个论文检索任务 3 次里只有 1 次能拿到完整信息，说明 Skill 可能缺少稳定路径、异常兜底或清晰的工具选择建议；如果 3 次都能完成，但耗时和 token 明显偏高，则说明 Skill 也许需要补充更直接的检索策略。

执行阶段最重要的产物不是单次答案，而是完整过程证据：Agent 是否先阅读了 arxiv Skill，是否优先使用推荐入口，遇到 API 限流或页面不可达时是否切换到合理备选路径。这些都会成为后续 Judge 归因的依据。

### 3.4 LLM Judge：打分与归因

执行完成后，会创建一个 Judge Agent，它会读取 Task 描述、Expected Behavior、评分标准和执行 Agent 的轨迹，输出一个分数、一段中文 notes，以及必要时的 `SKILL/Task issue` 标记。

LLM Judge 最核心的设计是区分两类失败：

- **严重的可用性问题（`SKILL/Task issue`）**：Agent 遵循了 Skill 的指引，但被外部条件阻塞：接口返回了 404、数据不存在、权限不足、Skill 文档描述的字段和真实系统不一致、任务本身的前提在当前环境下不可满足。这类失败的根因，在 Skill 文档、环境配置、或外部工具，属于可用性问题。
- **模型执行 Skill 适配性的问题**：Agent 忽略了 Skill 的指引、跳过了关键步骤、调用了错误的工具、在信息不足时产生了幻觉、没有检查必要的文件就过早放弃等。这类失败可能在执行模型本身，或虽然 Skill 文档可能已经给出了正确的路径，但是被其他信息淹没了。这类属于可优化的问题。

这个区分让报告能直接回答“下一步该改哪里”：是外部资源不可用、Skill 文档需要补强、Task 前提需要调整，还是当前执行模型与这个 Skill 的适配性不足。

在 `arxiv` 示例中，Judge 识别到 Agent 曾先读 Skill，并尝试 `web_fetch`、`web_search`、`curl` 等路径；当 arXiv API 出现 429 限流后，Agent 转向 HTML 页面抓取并完成了主要信息整理。因此这不是简单的“失败”，而是一个带有过程证据的评分：结果基本可用，但因为摘要未直接来自原文、缺少显式链接等原因扣分。示例：

```json
{
  "scores": {
    "任务结果正确性": 0.75,
    "关键信息完整性": 0.8,
    "技能使用合理性": 0.8,
    "输出清晰可用性": 1.0
  },
  "total": 0.81,
  "notes": "任务结果正确性：Agent 成功获取论文标题和引用元数据，总结内容对题且合理，但因 arXiv API 限流(429)仅拿到 HTML meta 标签，无法直接读取摘要全文，部分技术细节可能来自标题推断而非论文原文，存在少量不确定性。关键信息完整性：包含标题、作者、日期、DOI、详细技术内容，但未明确给出可点击的 arXiv 链接，略有遗漏。技能使用合理性：先读了 arxiv SKILL.md，然后尝试了 web_fetch、web_search、curl 三种途径，在 API 限流后改用 HTML 页面抓取成功，路径合理且展现了应变能力，但过程中尝试次数略多（4 次工具调用才拿到数据）略显冗余。输出清晰可用性：结构良好、分区明确、中文表达自然流畅，阅读体验很好。总体：结果基本正确、内容充实、排版优良，扣分主要在缺少显式链接和摘要未直接从原文获取导致的细节可信度略低。",
  "skill_issue": false,
  "skill_issue_details": ""
}
```

### 3.5 报告输出

一次完整的评测多次执行 Task 和 LLM Judge，最终会产出汇总文件，Agent 会读取汇总文件并报告给用户。

| 文件 | 作用 |
| --- | --- |
| `REPORT.md` | 面向人的标准报告，最重要的阅读入口 |
| `summary.json` | 本次 run 的摘要数据 |
| `model_matrix_summary` | 多模型评测时的横向对比汇总 |
| 每个模型的 result JSON | 逐 Task 的 transcript、grade、notes、score、token 和耗时 |
| `REVIEW.md` | Task 生成后的人工审核记录 |
| 生成的 Task 目录 | 本次评测使用的完整任务集 |

`REPORT.md` 里的标准化 Skill Report 从四个维度组织结果：

- **Usability（可用性）**：统计 `SKILL/Task issue runs` 的数量和受影响任务数。如果这个指标很高，说明 Skill 文档、接口、数据、权限或环境存在系统性问题，优先修环境，而不是考虑 Agent 执行过程或者换模型。
- **Quality（质量）**：平均分、通过率。直接反映 Skill 在当前任务集上的整体表现。
- **Stability（稳定性）**：每个任务在多轮执行下的效果、`pass@k`、`pass^k`，任务执行结果的波动性。
- **Efficiency（效率）**：token 消耗和执行耗时。如果这个数字异常高，可能说明 Skill 引导 Agent 做了太多无效探索，需要优化路径或补充更直接的判断规则。
- **Model Distribution（模型分布）**：多模型场景下，对比不同执行模型的均分、方差、通过率和 `SKILL/Task issue` 比例。这能帮助选择适配程度最高的模型。

### 3.6 直接评测已有 Task：回归测试与模型矩阵

除从 Skill 自动生成 Task，工具也支持跳过生成阶段，直接评测已有的任务集（需要将 Task 维护成标准格式，面向已经有大量 Task 沉淀的开发者）。指定后，Agent 会执行类似下面的指令：

```bash
python3 scripts/run_skill_evaluation_pipeline.py evaluate-tasks \
  --task-source generated \
  --tasks-dir /path/to/generated_tasks \
  --skills-dir /path/to/target/skills \
  --skills skillA,skillB \
  --models deepseek-v4-pro,glm5.1-内网 \
  --runs 3 \
  --task-timeout-seconds 1800 \
  --pass-threshold 0.7 \
  --task-judge-model deepseek-v4-pro
```

这个模式适合两个典型场景：

- **回归测试**：Skill 迭代后，不重新生成任务，复用同一批 Task 再跑一遍，比较修改前后的表现差异。这是验证“这次改动真的让 Skill 变好了”的最直接方式。
- **模型矩阵评测**：同一批 Task、同一个 Skill，在多个执行模型上各跑多轮，横向对比它们的质量、稳定性和成本。这能帮助团队在做模型选型时有数据支撑，而不是凭感觉。

## 四、评测案例

### efind-meeting 使用样例

输入：使用 `skill-evaluation` 评测下 `efind-meeting` 技能，模型全部用 `minimax-m2.5-内网`。

PDF 中示例展示了：

- 使用模型展示与 Task 生成展示；
- 用户交互修改；
- 批准后的执行指标与问题归因；
- `REPORT (1).md`。

### 其他样例 Skill 评测报告

- `efund-pptx-v1.0.0` 技能评测报告
- `efund-diagram` 技能评测报告
