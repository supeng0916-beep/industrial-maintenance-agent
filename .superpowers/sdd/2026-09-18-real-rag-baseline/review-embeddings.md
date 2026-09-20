# 真实嵌入实现独立审阅

日期：2026-09-18

## 结论与范围

审阅 `assistant/rag_embeddings.py`、`tests/test_rag_embeddings.py` 与 `task-embeddings-report.md`，独立访问固定 revision 的官方模型卡并使用已缓存真实权重复跑验收。**未发现需要修复的确定性问题。** 未修改实现、语料或服务，未重新下载权重，未扩大运行全回归；不涵盖仍在调整的分块实现。

## 官方方法与代码核对

- E5：384 维，attention mask 平均池化，对所有语言使用 query/passage 英文前缀，L2 规范化。代码与固定提交的[官方 E5 模型卡](https://huggingface.co/intfloat/multilingual-e5-small/raw/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md)一致。
- BGE 中文小模型：512 维，CLS 池化与 L2 规范化；短查询加入中文检索指令，正文不加指令。代码与固定提交的[官方 BGE 模型卡](https://huggingface.co/BAAI/bge-small-zh-v1.5/blob/7999e1d3359715c523056ef9478215996d62a620/README.md)一致。
- 实现明确拒绝超过 512 token 的输入，符合本项目禁止静默截断要求；虽然官方示例启用截断，本项目这一差别是有意约束。
- `embed` 接收已格式化字符串，长度检查包含特殊 token，且在所有输入通过校验后才开始计算；推理调用同样显式 `truncation=False`。
- 签名记录固定 revision、模型名称、池化、前缀、维度、规范化、长度、特殊 token、CPU/dtype 和关键库版本；索引层完整比对签名。
- 默认 `download=False`，snapshot 与 tokenizer/model 加载均走本地路径和 `local_files_only`；只有显式下载选项开启时才访问权重下载。使用 safetensors，关闭远程代码信任及 HF telemetry。

## 独立验证

命令：`RUN_REAL_EMBEDDINGS=1 .venv/bin/python -m unittest tests.test_rag_embeddings -v`

结果：`Ran 4 tests in 1.931s — OK`，真实权重测试实际运行，没有 skip。覆盖两个模型的维度、有限值、单位范数、查询/正文前缀、官方池化公式等价性、相关文本优于无关文本、单条/批量一致性、512 token 接受与 513 token 拒绝、长中文输入拒绝、空列表及错误参数。

另独立计算已缓存权重字节数与 SHA256，与任务报告记录一致：

| 模型 | 字节数 | SHA256 |
| --- | ---: | --- |
| E5 | 470641600 | 1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477 |
| BGE | 95827648 | 354763b9b1357bc9c44f62c6be2276321081ed2567773608c0d0785b61d5a026 |

仅观察到 SentencePiece/SWIG 上游弃用提示；没有功能测试失败。本审阅确认嵌入计算契约，不把三条文本 smoke check 当真实语料检索成绩。
