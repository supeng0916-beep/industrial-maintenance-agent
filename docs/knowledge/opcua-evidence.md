---
document_id: "opcua-evidence"
title: "OPC UA质量、源时间与订阅证据"
version: "0.1"
reviewed_on: "2026-09-18"
teaching_only: true
device_ids: ["motor-b"]
product_model: null
sources: ["opcua_storage.py", "collect_opcua.py", "docs/verification/opcua-subscription/验收说明.md"]
authoring: "AI-assisted, checked against project sources"
---

# OPC UA质量、源时间与订阅证据

## 设备身份与数据准入

适用范围：本项目motor-b教学模拟器，真实厂家型号未录入。读取节点为NamespaceURI urn:industrial-maintenance:motor-b、String标识MotorB.Temperature，运行时解析命名空间索引，不能固定套用ns编号。标量Double表示温度，℃为教学约定。

有效测量须满足Good、有限标量Double、源时间存在且新鲜、相对最后接受的源时间严格递增。默认源年龄允许0至5秒，未来时间不接受，前提是两端UTC时钟同步。Good表示质量状态，不证明电机健康，也不自动证明数据新鲜。

## 源时间和处理时间

SourceTimestamp按本模拟器约定表示测量生成时间；ServerTimestamp、客户端received_at与取得数据库写锁后的decision_at分别保留。接收时间不能代替缺失源时间。判断时再次检查源年龄：接收时4.9秒、排队0.2秒后已超过5秒，不可继续用于当前告警。

Good但源时间十秒前的样本在默认配置下被拒绝。Bad、Uncertain、缺源时间或过期数据保留诊断，清待确认，保留已有告警。收到响应不能说本次服务器未响应；旧源时间也不能单独证明传感器损坏。Modbus没有源时间的协议语义不同，不能机械套用本节门槛。

## 两种重复

温度相同但源时间更新，可能是新测量，不能按数值相同直接丢弃。同一通知身份重新投递会去重，不重复写入或影响待确认；新通知身份携带重复源时间按当前严格策略拒绝并清待确认。这是本项目策略，不是OPC UA所有应用统一要求。

## 保活、重连和缺口

保活说明订阅有响应，不是新的温度测量，不能累计超温。断线后重建订阅不意味着补齐缺失历史。旧连接代次迟到的回调不能更新当前状态。

服务器监视项队列与采集器应用队列是不同层。应用队列积压、溢出等会破坏证据连续性；增加客户端队列找不回服务端已丢通知。没有溢出标志不能证明无丢失。本项目不保证识别所有静默丢样或提供端到端恰好一次交付。
