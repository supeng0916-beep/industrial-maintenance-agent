# AI4I 2020 Predictive Maintenance Dataset（本地登记副本）

- **来源**：UCI Machine Learning Repository — [AI4I 2020 Predictive Maintenance Dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
- **原作者**：Stephan Matzka, HTW Berlin（论文：*Explainable Artificial Intelligence for Predictive Maintenance Applications*）
- **许可**：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。本仓库按许可要求保留署名再分发此副本。
- **下载日期**：2026-09-20；文件：`ai4i2020.csv`（10000 行 × 14 列）
- **SHA256**：`dc6630cd9b1f0f853922fad78a1b6436570d3f1ec863f1dd5c4340ac56bc8a8e`

## 性质声明（项目诚实性合同的一部分）

该数据集是**合成数据**：由 Matzka（2020）按数控机床物理模型模拟生成，**不是现场实测记录**。本项目以"历史回放"形态使用它——回放时刻即写入时间（collected_at），行序保持原序，故障标签（Machine failure 与 TWF/HDF/PWF/OSF/RNF 列）直接来自数据集自身，本系统不做再判定。任何页面与回答不得把它表述为实时或实测数据。

## 列与项目指标映射

| 数据集列 | 项目指标（motor-c） | 单位 | 转换 |
|---|---|---|---|
| Process temperature [K] | temperature | ℃ | K−273.15 |
| Air temperature [K] | air_temperature | ℃ | K−273.15 |
| Rotational speed [rpm] | speed | rpm | 原值 |
| Torque [Nm] | torque | Nm | 原值 |
| Tool wear [min] | tool_wear | min | 原值 |
| Machine failure | running_state | — | 1=正常运转，0=数据集标注故障 |
| TWF/HDF/PWF/OSF/RNF | 故障事件（collection_events） | — | 原标注 |
