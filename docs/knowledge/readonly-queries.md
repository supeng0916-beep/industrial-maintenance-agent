---
document_id: "readonly-queries"
title: "只读工具、历史统计与错误语义"
version: "0.1"
reviewed_on: "2026-09-18"
teaching_only: true
device_ids: ["motor-a", "motor-b"]
product_model: null
sources: ["assistant/tools.py", "assistant/query_service.py", "assistant/ranges.py", "docs/verification/m4-readonly-tools/验收说明.md"]
authoring: "AI-assisted, checked against project sources"
---

# 只读工具、历史统计与错误语义

## 三个事实查询工具

get_device_status查询设备支持指标的最后有效记录、质量、时效与告警。query_metric_history查询指定时间范围的历史。list_alarms查询与范围相交的告警。只读工具不提供任意SQL、shell、写设备或解除告警的能力。

工具ok=true仅表示查询成功，设备状态usable只表示记录在时效范围内，均不等于设备健康。旧的有效数值必须保留原时间，不能伪装成当前实时测量。

## 完整统计与有限明细

query_metric_history按collected_at闭区间查询quality=good记录，最大范围24小时，时间须带时区。motor-b的collected_at是接收时间，不是源时间。

count/min/max在全部匹配样本上计算。limit仅限制返回明细，最大1000；明细按时间及id升序。即使返回两条，也不是只用两条计算最高值。truncated表示明细截断，不代表统计截断。

最大值是已记录有效样本最大值，不保证等于真实物理峰值。首末时间不能证明中间无缺口，不能用订阅假设固定每秒一条计算完整率。运行状态是枚举，统计各状态次数，不计算物理最大值。

## 空结果和失败

查询成功但没有有效样本：count=0，min/max=null，说明无数据、无法计算，不能返回0℃。数据库不可读、超时等返回ok=false及结构化error，不能解释成没有记录或没有告警。

## 告警相交与记录状态

告警started_at不晚于查询end，且recovered_at为空或不早于start，才与闭区间相交。查询范围开始前触发但范围内仍未恢复的告警也应包含。

status筛选依据查询时记录是否恢复，不是重建过去某一刻状态。历史告警内阈值描述该次记录；当前状态返回的rule含查询进程默认值及部分数据库状态，不是所有采集进程已同步加载配置的证明。旧库history_available=false表示无告警历史表，不等于确认没有告警。
