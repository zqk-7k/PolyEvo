# candidate158 改进的通用实现

统一入口是主工程的 `process_workflow_runner.py`，版本选择 `--workflow general158`。原PDF总入口 `pipeline_runner.py` 通过 `--process-workflow general158` 调用同一实现。旧 `cache-v2` 保留兼容；它不等于完整的来源语义处理。

158是历史候选版本号，不是158个独立算法。历史中的表头/单位恢复、组成范围、制备与测试区分、操作与材料谱系、样品状态、热历史、字段级修正及数值限定，被归入12类通用规则。规则见 [closure/protocol.md](closure/protocol.md)。历史逐篇预测、参考、验收裁决、匹配结果和论文编号映射不属于运行依赖。

## 执行链路

原生性质输出 + Stage0原文 → 确定性整理 → 独立上下文原文处理 → 字段/跨度校验 → 发布工艺图及旧字段活动覆盖层。

- 确定性规则在 `core.py`、`stage_roles.py` 和 `rules/`，处理明确可恢复的表格、单位、组成及限定信息。
- 一般方法的成员适用范围、不同物理试样、支路、阶段和跨段语义，由固定原文协议指导模型处理。不会声称这些判断已全部变成正则程序。
- `general158.py` 负责准备任务、展开稀疏响应、编译工艺图和发布；`closure/` 负责完整字段库存、原文跨度、细粒度修正和来源一致性。
- 本轮不调用外部API，也没有自动执行新的模型抽取。`prepare`不是抽取完成。调用方必须把任务交给实际模型客户端，再用 `publish` 接收其真实输出。

## 输入清单

UTF-8 JSON，路径使用实际绝对路径，sha256为文件原始字节哈希，不是解析后对象哈希。

```json
{
  "papers": [{
    "reference_no": "arbitrary_safe_paper_id",
    "native_final": {"path": "./data/paper/final.json", "sha256": "实际SHA256"},
    "stage0": {"path": "./data/paper/stage0_blocks.json", "sha256": "实际SHA256"}
  }]
}
```

如有其他未审核工艺候选，可选 `prior: {path,sha256}`。其文件须为 `{graph: 完整候选对象, native_origin_index: []}`。只有能证明为原生字段逐字复制时，才能填写literal_copy来源索引；推导、相似值不得冒充逐字来源。不需要、也不应把158的逐篇验收答案交给新论文运行。

## 同一入口的两步命令

在主工程目录执行，以下路径是占位示例：

```powershell
python -B -X utf8 process_workflow_runner.py --workflow general158 --stage prepare --manifest ./experiment/inputs.json --output ./experiment/tasks --workers 4
```

每篇得到 `papers/<ID>/task.json`、完整原文/原生文件、`packet.json`、完整字段模板和 `delta_template.json`。任务卡指向固定协议。将同一篇的任务卡及其列出的文件交给一个独立新上下文。不得传参考、得分、其他论文答案或历史聊天。

实际客户端把响应保存到 `./experiment/responses/<ID>/`：

1. `attempt_001.json`：首次响应原始字节；修订另存002、003等，不覆盖首次。
2. `attempts.json`：`{"attempts":[{"path":"attempt_001.json","sha256":"实际文件哈希"}]}`，按实际尝试顺序包含失败与成功响应。
3. `run_log.json`：至少含正确 `reference_no`；如实记录模型配置、实际可获后端、时间、阅读产物、重试和用量。未知字段为null。不得伪造上下文独立性或后端证据。

模型不必输出数万个“未审核”字段。只提交实际处理过的 native_decisions/prior_decisions；编译器对其他字段自动保持 active_unknown，完整字段库存仍在不可变packet中。原文字段字符串可拆跨度，但不得遗漏未修正部分。

```powershell
python -B -X utf8 process_workflow_runner.py --workflow general158 --stage publish --manifest ./experiment/inputs.json --tasks ./experiment/tasks/prepared_tasks.json --responses ./experiment/responses --output ./experiment/published
```

主PDF入口的等效准备命令：

```powershell
python -B -X utf8 pipeline_runner.py --input-dir ./experiment/pdfs --process-recovery-only --process-recovery-manifest ./experiment/inputs.json --process-recovery-output ./experiment/tasks --process-workflow general158 --process-stage prepare
```

发布时改为 `--process-stage publish`，加 `--process-tasks`、`--process-responses`，使用新的输出目录。所选PDF与清单必须是同一完整集合；该缓存模式不重新执行PDF解析、性质抽取或OCR。缺少Stage0原文需要先由已有PDF流程生成，不能把空源当全文。

## 发布结果和保留规则

每篇 `prediction.json` 含 `active_graph_nodes`、字段活动覆盖层、不可变输入和任务包的指针/哈希、原文阅读自报、未解决来源请求及真实客户端日志指针。`general158.effective_fields(packet,prediction)` 可完整读取原字段及活动状态；未提交字段和未覆盖的字符串后缀均保持活动、未确定。不要只看新图节点就宣称统计了全部输出。

参数区分制备/处理/测试条件与工艺结果；产率、回收量单列 outcome。参数必须挂所属操作。binding有材料、操作、状态端点。顺序同时检查引用图与操作先后图，不能由数组位置产生。每条节点带七项范围及未知原因。

原始性质文件不写回；性质数值、单位、样品ID及原绑定不改写。新工艺声明的语义正确性仍需独立审核，文件未改并不证明性质上下文的语义指标已重新验收。

发布器还拒绝通过字段覆盖层撤回原性质数据或样品绑定；允许修正其工艺/测量上下文。性质评价输入始终指向 immutable_native_file，不能用只包含新工艺节点的图代替性质结果。

执行前复制并哈希冻结代码、协议和输入；准备与发布须为同一完整工作流实现。全部篇成功才生成整批freeze；任一缺篇或失败不发布“全批成功”。`--resume`仅校验已经完整冻结的同一成功运行，不重新生成成功项。对于未冻结的失败发布，修正响应并保留旧尝试，在新输出目录重新发布；不会付费重抽成功篇。

## 验收边界

代码及集成测试证明入口可运行、约束得到执行、原文件保持不变。模型填出的证据和阅读完成声明不等于语义正确的独立证明。一般协议覆盖某能力也不等于该能力已在101篇或20篇达到90%。科学指标须在预测冻结后，使用固定独立参考另评。本轮没有运行20篇，也没有更新论文。

默认旧模式保持兼容是为保护已有实验；正式使用完整版本必须显式选择general158，不能用旧模式产生的结果冒充新版本。
