# 参考资料与实现证据索引

核对日期：2026-10-28（北京时间）。本文配套：[article.md](article.md) · [30 分钟分享大纲](presentation-outline.md)。

## 事实、解释、观点与设想分开记录

| 类别 | 本次采用的内容 | 写作约束 |
| --- | --- | --- |
| 事实 | 已读取的 Skill、AGENTS.md、工作流、处理代码及合并提交说明 | 指向具体源码；提交说明中的运行数据属于该提交自述 |
| 工程解释 | diff 有助于限定范围，独立诊断有助于失败降级，规则沉淀有助于复用经验 | 解释机制与目的，不伪装成量化运行结论 |
| 作者观点 | AI 与传统设施结合改善整体工程能力；知识可在 Skill 与确定性组件之间持续沉淀 | 明确为本文归纳，不全部归因于 Anthropic |
| 评估设想 | 复发率、越界改动、诊断采纳情况、成本与延迟 | 尚未取得统一运行数据，不报告提升比例 |

## 一、主要理论资料

### R1. Anthropic：Building effective agents

- 作者署名：Anthropic Engineering（页面 Team）。
- 发表日期：2024-12-19。
- [官方原文](https://www.anthropic.com/research/building-effective-agents)
- 已核对部分：What are agents?；When (and when not) to use agents；Agents；Combining and customizing these patterns；Summary。
- 支持论点：区分预定义代码路径的 Workflow 与模型动态控制过程的 Agent；从简单方案开始，依据效果增加复杂度；重视工具执行反馈、检查点与停止条件。
- 引用方式：正文采用中文概述，不制造直接引语。
- 边界：“人工 → AI → Skill → 确定性组件”的循环是本文工程归纳。原文页面目前包含后续更新内容，本文仅使用与其核心设计原则有关的段落，不将当前工具列表当作 2024 年原貌。

### R2. Google SRE：Eliminating Toil

- 收录：The Site Reliability Workbook，第 6 章，2018。
- 页面作者：David Challoner、Joanna Wijntjes、David Huska、Matthew Sartwell、Chris Coykendall、Chris Schrier、John Looney、Vivek Rau；另列协作作者 Betsy Beyer、Max Luebbe、Alex Perry、Murali Suriar。
- [官方章节](https://sre.google/workbook/eliminating-toil/)
- 支持论点：识别重复、可自动化、缺少持久价值的工作；优先考虑根因修复与长期收益。
- 边界：不是所有人工工作都是 toil；本文不照搬 Google 的运维时间目标。

### R3. Google SRE：The Evolution of Automation at Google

- 收录：Site Reliability Engineering，第 7 章，2016。
- 页面署名：Niall Murphy with John Looney and Michael Kacirek；编辑 Betsy Beyer。
- [官方章节](https://sre.google/sre-book/automation-at-google/)
- 支持论点：已知操作的一致性、平台化复用与反馈；自动化需要恰当设计，错误也可能被放大。
- 边界：不是 AI / Skill 专论文献，本文只借用其工程原则。

## 二、案例一：文档治理证据

以下编号是上游 GitCode/CANN CATLASS 的合并请求编号。GitHub 镜像提交信息保留了 !编号、说明与参与者，不把它们误写成 GitHub 同编号 PR。

| 上游 PR | 已核对证据 | 支持的具体事实 | 不能据此推断 |
| --- | --- | --- | --- |
| #766 | [合并提交 cca0d634](https://github.com/ascend-catlass/catlass/commit/cca0d634e9d8c70b765fe70b89d0d8d512e522f0) | 使用 Prettier 格式化 Markdown | 不能证明由 AI 生成 |
| #874 | [合并提交 5f10a480](https://github.com/ascend-catlass/catlass/commit/5f10a480a1079ca36d864367f96f90105ce2a6d8) | 使用 pre-commit 刷新格式、调整配置与检查项 | 不能据此断定覆盖所有文档问题 |
| #859 | [合并提交 0843e90a](https://github.com/ascend-catlass/catlass/commit/0843e90ab3edaeccd149e19f01213575ab615770) | 说明同时记录文档工具检查和大模型扫描文字低错 | 不能证明所有修改均由模型独立完成 |
| #1304 | [合并提交 df6e1f6a](https://github.com/ascend-catlass/catlass/commit/df6e1f6af05403837c036999f8e7bf6f67273f03) | 修复术语与拼写，AGENTS.md 新增常见易错项清单 | 不能把提交号当作严格时间顺序 |
| #1467 | [合并提交 6e5a75bd](https://github.com/ascend-catlass/catlass/commit/6e5a75bd0f513907ba506dc310c80bf740d481ec) | 修复断链，新增 scripts/check_md_links.py 和 local hook；hook 使用 --no-external | 不能证明检查脚本由 AI 编写，不能声称 hook 默认联网检查 |
| #1483 | [合并提交 37cedeca](https://github.com/ascend-catlass/catlass/commit/37cedeca455d0970f1724b0c23ab3d3fa4bdb08d) | 说明明确记录模型扫描、Agent 辅助整改 | 不能据此计算效率提升 |
| #1498 | [合并提交 3f250ec3](https://github.com/ascend-catlass/catlass/commit/3f250ec31864b821879d6e7e60d0dcfa2c8b3ce0) | 新增审查 Skill、约定文档检查流程，整理由术语到来源和量化判据的经验 | 不代表所有语义问题都被规则完全覆盖 |

当前实现入口：

- [CATLASS AGENTS.md](https://github.com/ascend-catlass/catlass/blob/master/AGENTS.md)：审查与翻译的触发入口及边界。本次取得文件 blob SHA：c227411636b4c1b05e321e4f2e1c0fb94584fe24。
- [文档审查 Skill](https://github.com/ascend-catlass/catlass/blob/master/.agents/skills/catlass-docs-review/SKILL.md)：先静态检查再语义审查、限定改动范围、保存易错项。本次 blob SHA：25d6c2222c9b628af723472d413af141b72de8d4。
- #1304 的差异是“经验进入 AGENTS.md”的直接依据；#1498 与当前文件共同支持“专门 Skill + 基础设施协同”。
- 贡献者与共同作者信息保留在各提交中。正文按社区实践表述，不将这些工作归为某一人的独立成果。

## 三、案例二：增量翻译证据

### T1. 已合入的翻译 Skill

- [源码](https://github.com/ascend-catlass/catlass/blob/master/.agents/skills/catlass-docs-translation/SKILL.md)
- 本次取得文件 blob SHA：d21a3f38692acca4fd1ba3bd5cba88d8cc8c8ff0。
- 已逐项核对：当前任务的工作区/分支 diff；source/target 配对；hunk 扩展到完整 Markdown 块；最近就绪合并提交；人工译文保留；歧义转人工；最终 diff 审查。
- 关键区别：当前任务 diff 用于发现编辑范围；从 ready commit 到 upstream/master 的源文 diff 用于就绪基线之后的增量。
- 关键约定：Translation-Ready: true 的标记合并提交具有权威性；目标文件时间或目标文件存在改动，不足以证明已同步。
- 当前状态管理：Git-only。明确不另建配置、哈希缓存、翻译状态仓库或 translation harness。
- 边界：Skill 是执行指导，不能把其要求都写成不可绕过的程序门禁；对齐和语义复核仍依赖执行者与人。
- 历史编号：前轮资料提及 #1310，本次未重新核对其对应合并提交，因此正文只采用当前已合入源码证明实现存在，不以该编号证明上线时间。

## 四、案例三：TestPR 与失败诊断证据

### C1. TestPR 工作流

- [源码](https://github.com/ascend-catlass/actions/blob/86184881b9977d5d90cf5cc5e539479414e93b4a/.github/workflows/test-atomgit-pr.yml)
- 本次取得文件 blob SHA：4d2f3bdf8a8b25d448b9f1d671e9ee0b05ff5949。
- prepare：普通 Runner 获取元数据，拉取源码与 PR head，对比 SHA，按路径分类。
- merge-and-test：Ascend 950 Runner，调用合并、容器、测试准备和运行测试组件。
- analyze-failure：prepare/merge-and-test 失败且取得 head SHA 等条件满足后执行；指定本次 run ID 与 attempt。
- report：原始准备/测试结果决定报告状态；诊断以附件形式补充，缺失时写降级说明。
- 边界：并非所有初始化失败都能自动诊断，例如尚未取得 head SHA 时不符合分析条件。

### C2. 失败分析复合 Action

- [源码](https://github.com/ascend-catlass/actions/blob/86184881b9977d5d90cf5cc5e539479414e93b4a/.github/actions/analyze-ci-failure/action.yml)
- 本次文件 blob SHA：7881e37e866c9e2606d6597168d70ce291a6836e。
- 获取指定 attempt 的失败 job，最多四个；准备提示；调用统一模型执行组件；格式化输出。
- 模型步骤 timeout-seconds 为 300；外层分析 job timeout-minutes 为 12。
- Action 接口接收读取日志的 GitHub token 与模型 PAT，但两者在对应步骤中使用；不能将调用接口画成模型直接持有发布 token。
- 分析 Action 本身不负责向社区发布评论。

### C3. 提示准备与结果处理

- [comment.cjs](https://github.com/ascend-catlass/actions/blob/86184881b9977d5d90cf5cc5e539479414e93b4a/.github/actions/analyze-ci-failure/comment.cjs)
- 本次文件 blob SHA：fd8324934793bacf015fa59bb950a44f2cf04544。
- 日志：每 job 选择首批错误行与尾部，执行脱敏；输入可能不完整。
- 响应：检查 successful manifest 与退出码，解析 cause / evidence / next_step，核对字段与长度。
- 失败处理：输出分析暂不可用说明，不改变原始测试事实。
- provenance：使用执行阶段结果中的 requested_model，不在报告代码中硬写模型归属。
- 边界：结构检查不等于诊断正确；正则脱敏不保证所有秘密都被移除。

## 五、三张演进图的证据边界

| 图 | 图的性质 | 已有依据 | 不作的历史推断 |
| --- | --- | --- | --- |
| 文档治理 | 多项社区实践的能力归纳 | PR 说明、AGENTS.md 历史 diff、当前审查 Skill | 不声称所有贡献者按统一路线推进 |
| 翻译 | 对当前能力的逐层教学拆解 | 当前翻译 Skill | 不声称每层均曾独立上线 |
| CI | 当前工作流的分层展示 | TestPR YAML、分析 Action 与处理代码 | 不声称拥有各阶段真实运行对照数据 |

## 六、当前未作为成果使用的材料

- 仓库同步：按用户要求删除，不作为文章案例。
- CATLASS #1286 的 CI 假阳性：缺少本次可核对的完整经过，不在正文叙述。
- Issue Fix → Validate → Publish：不占本次三个主案例篇幅。
- 早期 AST、Translation Memory 与独立翻译服务设计：不混入当前 Git-only 实现。
- 自动化持续稳定运行、效率百分比、AI 完成的代码比例：无统一测量证据，不作结论。
- 所有教学输入和输出示意均不得标作真实运行结果。

## 七、本次文档检查说明

- 已核对正文具体机制与上述读取的源码、提交说明是否一致。
- 已检查三份 Markdown 的代码围栏配对、行尾空白、相互链接及大纲时长。
- 这是独立中文分享材料，不改动现有 Action 接口或双语产品文档。
- 仓库 scripts/check_docs.py 的双语接口检查和完整测试需要可用的执行环境；本次不将源码阅读或文本检查冒充这些命令执行通过。PR 中以实际 GitHub 检查状态为准。
