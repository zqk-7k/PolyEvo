# 通用工艺恢复入口

**2026-10-22：candidate158改进的通用实现已加入同一入口，使用 `--workflow general158 --stage prepare|publish`。完整说明见 [README_general158.md](README_general158.md)，固定规则见 [closure/protocol.md](closure/protocol.md)。下文描述的是仍保留兼容的旧cache-v2/semantic-v1路径，不能据此省略新版原文处理阶段。**

这套入口从既有 Stage0 来源及原生抽取结果继续处理工艺，不覆盖性质输出。新增原文语义阶段使用固定协议和每篇独立上下文；它是新的工作流版本，不等同于历史 candidate158 的结果拼装，也不声称复现原 terra/豆包后端。

输入清单不限定论文集合或编号。每篇包括 reference_no、native_final 和 stage0；后两者均为 path、sha256。引用或评分文件不是预测输入。

默认来源语义协议随主工程保存在`process_workflow_prompts/source_semantic_process_v1.md`，与本轮101篇实际使用的固定协议逐字节相同；不需要从历史案例或参考中拼出提示词。

1. `process_workflow_prepare_tasks.py --manifest INPUTS --output TASKS --prediction-output MODEL_OUTPUTS --protocol FIXED_PROTOCOL --authorization-record AUTHORIZATION`：校验整批输入，生成单篇来源、原生候选、固定协议和任务卡。只准备文件，不执行模型。授权凭证须对应用户实际允许的工作。
2. 在获授权的客户端中，按卡逐篇使用独立新上下文执行；保存首次图、最终图、来源清单和真实日志。不得读参考或得分，也不能用无依据内容补齐图。客户端任务执行仍需调度器，Python脚本不会自动产生模型判断。
3. `process_workflow_attach_semantic.py --input-manifest INPUTS --task-manifest TASKS/manifest.json --output-manifest PUBLICATION`：整批校验后接入来源语义结果。缺少论文或输入不一致时不发布缩小后的集合。
4. `process_workflow_runner.py --manifest PUBLICATION --output RUN --workers 4`：在冻结运行时中整理并发布活动工艺图，保留旧声明的处置、未确定项和首次图来源。支持哈希约束下的 `--resume`，不重跑成功项。

原PDF主入口也可消费同一发布清单：

```powershell
python pipeline_runner.py --input-dir PDF_DIR --process-recovery-only --process-recovery-output RUN --process-recovery-manifest PUBLICATION
```

该缓存模式不调用OCR、抽取模型或外部API。PDF目录中的所选论文必须与清单完全一致；这不是从原PDF重新抽取全部性质的命令。

结构检查、逐字锚点和哈希不代表语义正确。参考覆盖、全量输出支持、完整样品关联及语义去重，必须在预测冻结后另做独立审核。性质原文件不变可以核对字节及原评分口径，但不等同于新做了一轮完整性质语义审核。未知后端、推理设置、token和费用填null。

发布完整性检查会从实际原生对象重建候选及处置要求，拒绝大小写别名、Windows保留名和重复论文编号。续跑在跳过成功项之前仍检查全部来源、语义输入、结构报告及运行时冻结根哈希。正确性检查不支持Python优化模式，禁止用`python -O`执行这些入口。

首稿可以保留合法机械错误，但必须属于同一论文、同一来源和同一图结构。发布保留其哈希及终稿哈希；首末差异需要另存机械修订证据。文件和日志不能独立证明首次生成的历史时间或客户端上下文隔离，不能将这些事实描述为已由哈希认证。直接提供最小语义清单的低层调用不会自动获得完整来源留痕资格，正式独立评估需要标准入口的整套来源见证。
