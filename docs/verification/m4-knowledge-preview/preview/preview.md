# 文档切块预览

仅结构与长度预览，未生成向量、未建立索引、未评测检索。

## device-points · 设备身份、Modbus点位与整轮保存

chunk_id: `device-points:703372588d06bf2d9837`

来源：device-points.md，行 12–14；字符 [290, 313)

完整输入 tokens：88；超过300软目标：False

### 元数据

```
{
  "document_id": "device-points",
  "title": "设备身份、Modbus点位与整轮保存",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a"
  ],
  "product_model": null,
  "sources": [
    "points.py",
    "docs/protocols/点位表.md",
    "storage.py"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```

# 设备身份、Modbus点位与整轮保存


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：设备身份、Modbus点位与整轮保存
文档ID：device-points
版本：0.1
章节：设备身份、Modbus点位与整轮保存
适用设备：motor-a
产品型号：未注明
仅教学：是
正文：

# 设备身份、Modbus点位与整轮保存


```

## device-points · 设备编号不是产品型号

chunk_id: `device-points:477eb716a95a39dc69bf`

来源：device-points.md，行 15–18；字符 [313, 414)

完整输入 tokens：158；超过300软目标：False

### 元数据

```
{
  "document_id": "device-points",
  "title": "设备身份、Modbus点位与整轮保存",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a"
  ],
  "product_model": null,
  "sources": [
    "points.py",
    "docs/protocols/点位表.md",
    "storage.py"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 设备编号不是产品型号

适用范围：本项目 motor-a 教学模拟设备。motor-a 是设备编号，不是厂家或产品型号；真实产品型号未录入。不能用它查找所谓“A型电机”的厂家故障码或维护周期。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：设备身份、Modbus点位与整轮保存
文档ID：device-points
版本：0.1
章节：设备编号不是产品型号
适用设备：motor-a
产品型号：未注明
仅教学：是
正文：
## 设备编号不是产品型号

适用范围：本项目 motor-a 教学模拟设备。motor-a 是设备编号，不是厂家或产品型号；真实产品型号未录入。不能用它查找所谓“A型电机”的厂家故障码或维护周期。


```

## device-points · 四个保持寄存器的含义

chunk_id: `device-points:6b47f93695b1150ecd7f`

来源：device-points.md，行 19–31；字符 [414, 790)

完整输入 tokens：322；超过300软目标：True

### 元数据

```
{
  "document_id": "device-points",
  "title": "设备身份、Modbus点位与整轮保存",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a"
  ],
  "product_model": null,
  "sources": [
    "points.py",
    "docs/protocols/点位表.md",
    "storage.py"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 四个保持寄存器的含义

本项目协议地址从0开始，保持寄存器功能码03，device ID为1。一次从地址0读取4个寄存器。

| 地址 | 指标 | 解析 | 单位或含义 |
| --- | --- | --- | --- |
| 0 | temperature | uint16 × 0.1 | ℃ |
| 1 | current | uint16 × 0.01 | A |
| 2 | speed | uint16 × 1 | rpm |
| 3 | running_state | uint16枚举 | 仅0停止、1运行 |

响应[653,123,1450,1]表示65.3℃、1.23A、1450rpm、运行。这里每点占一个寄存器；不能推广为所有设备每个测点都只占一个寄存器。列表索引0是本次读取起始地址对应项，并不总是协议地址0。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：设备身份、Modbus点位与整轮保存
文档ID：device-points
版本：0.1
章节：四个保持寄存器的含义
适用设备：motor-a
产品型号：未注明
仅教学：是
正文：
## 四个保持寄存器的含义

本项目协议地址从0开始，保持寄存器功能码03，device ID为1。一次从地址0读取4个寄存器。

| 地址 | 指标 | 解析 | 单位或含义 |
| --- | --- | --- | --- |
| 0 | temperature | uint16 × 0.1 | ℃ |
| 1 | current | uint16 × 0.01 | A |
| 2 | speed | uint16 × 1 | rpm |
| 3 | running_state | uint16枚举 | 仅0停止、1运行 |

响应[653,123,1450,1]表示65.3℃、1.23A、1450rpm、运行。这里每点占一个寄存器；不能推广为所有设备每个测点都只占一个寄存器。列表索引0是本次读取起始地址对应项，并不总是协议地址0。


```

## device-points · 有效零与无效数据

chunk_id: `device-points:929c46b2d414f88595b9`

来源：device-points.md，行 32–35；字符 [790, 888)

完整输入 tokens：160；超过300软目标：False

### 元数据

```
{
  "document_id": "device-points",
  "title": "设备身份、Modbus点位与整轮保存",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a"
  ],
  "product_model": null,
  "sources": [
    "points.py",
    "docs/protocols/点位表.md",
    "storage.py"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 有效零与无效数据

完整返回的0A、0rpm、状态0都可能有效；读到零不证明传感器物理准确。读取失败不能补零。状态2或7在本项目未定义，不能解释为故障状态：这是协议有响应但业务校验失败。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：设备身份、Modbus点位与整轮保存
文档ID：device-points
版本：0.1
章节：有效零与无效数据
适用设备：motor-a
产品型号：未注明
仅教学：是
正文：
## 有效零与无效数据

完整返回的0A、0rpm、状态0都可能有效；读到零不证明传感器物理准确。读取失败不能补零。状态2或7在本项目未定义，不能解释为故障状态：这是协议有响应但业务校验失败。


```

## device-points · 整轮保存与同步测量

chunk_id: `device-points:b23d77d60f12bbf3f0fc`

来源：device-points.md，行 36–40；字符 [888, 1111)

完整输入 tokens：281；超过300软目标：False

### 元数据

```
{
  "document_id": "device-points",
  "title": "设备身份、Modbus点位与整轮保存",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a"
  ],
  "product_model": null,
  "sources": [
    "points.py",
    "docs/protocols/点位表.md",
    "storage.py"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 整轮保存与同步测量

本项目四点必须全部读取并通过校验，才在一个事务内保存四条测量和温度告警状态。任一步写入失败整轮回滚；校验失败整轮不存有效测量，记录事件，清除温度待确认但保留已有告警。查询必须限定设备和指标，避免把电流数值展示为温度。

一次批量读取、相同collected_at或同一数据库事务，都不能证明四个传感器严格同步测量。设备可能分别更新寄存器；事务只保证相关数据库写入一起提交或撤销。同步需要设备时间或同步采样机制的证据。

```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：设备身份、Modbus点位与整轮保存
文档ID：device-points
版本：0.1
章节：整轮保存与同步测量
适用设备：motor-a
产品型号：未注明
仅教学：是
正文：
## 整轮保存与同步测量

本项目四点必须全部读取并通过校验，才在一个事务内保存四条测量和温度告警状态。任一步写入失败整轮回滚；校验失败整轮不存有效测量，记录事件，清除温度待确认但保留已有告警。查询必须限定设备和指标，避免把电流数值展示为温度。

一次批量读取、相同collected_at或同一数据库事务，都不能证明四个传感器严格同步测量。设备可能分别更新寄存器；事务只保证相关数据库写入一起提交或撤销。同步需要设备时间或同步采样机制的证据。

```

## temperature-alarms · 持续超温、恢复与证据中断

chunk_id: `temperature-alarms:70389bee3d59cc00350e`

来源：temperature-alarms.md，行 12–14；字符 [306, 323)

完整输入 tokens：93；超过300软目标：False

### 元数据

```
{
  "document_id": "temperature-alarms",
  "title": "持续超温、恢复与证据中断",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "alarms.py",
    "opcua_storage.py",
    "docs/protocols/点位表.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```

# 持续超温、恢复与证据中断


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：持续超温、恢复与证据中断
文档ID：temperature-alarms
版本：0.1
章节：持续超温、恢复与证据中断
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：

# 持续超温、恢复与证据中断


```

## temperature-alarms · 使用范围与默认规则

chunk_id: `temperature-alarms:058ff677db4a05d1db0c`

来源：temperature-alarms.md，行 15–18；字符 [323, 460)

完整输入 tokens：203；超过300软目标：False

### 元数据

```
{
  "document_id": "temperature-alarms",
  "title": "持续超温、恢复与证据中断",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "alarms.py",
    "opcua_storage.py",
    "docs/protocols/点位表.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 使用范围与默认规则

本节仅描述本项目教学模拟器，不能当作真实设备安全阈值。2026-09-18核对代码默认值：温度严格大于80℃，合格样本持续支持至少5秒，才触发新告警；默认恢复阈值为严格低于78℃。当前实际运行规则还要核对进程及状态记录，文档不是实时配置接口。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：持续超温、恢复与证据中断
文档ID：temperature-alarms
版本：0.1
章节：使用范围与默认规则
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 使用范围与默认规则

本节仅描述本项目教学模拟器，不能当作真实设备安全阈值。2026-09-18核对代码默认值：温度严格大于80℃，合格样本持续支持至少5秒，才触发新告警；默认恢复阈值为严格低于78℃。当前实际运行规则还要核对进程及状态记录，文档不是实时配置接口。


```

## temperature-alarms · 触发前的待确认

chunk_id: `temperature-alarms:4929f658630b01320fba`

来源：temperature-alarms.md，行 19–24；字符 [460, 662)

完整输入 tokens：263；超过300软目标：False

### 元数据

```
{
  "document_id": "temperature-alarms",
  "title": "持续超温、恢复与证据中断",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "alarms.py",
    "opcua_storage.py",
    "docs/protocols/点位表.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 触发前的待确认

前提：该设备尚无未解除温度告警，且温度样本通过协议对应的数据质量与新鲜度校验。温度大于80℃时开始或继续待确认；本地单调时间累计达到5秒，且新的合格样本到来后才触发。只有2秒时是“超温待确认”，不能说已正式报警，也不能说温度正常。

相邻有效证据间隔不得超过配置的1.5倍采集interval；中断后重新累计，不能仅等待墙上时钟走过5秒就触发。温度小于或等于80℃取消待确认。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：持续超温、恢复与证据中断
文档ID：temperature-alarms
版本：0.1
章节：触发前的待确认
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 触发前的待确认

前提：该设备尚无未解除温度告警，且温度样本通过协议对应的数据质量与新鲜度校验。温度大于80℃时开始或继续待确认；本地单调时间累计达到5秒，且新的合格样本到来后才触发。只有2秒时是“超温待确认”，不能说已正式报警，也不能说温度正常。

相邻有效证据间隔不得超过配置的1.5倍采集interval；中断后重新累计，不能仅等待墙上时钟走过5秒就触发。温度小于或等于80℃取消待确认。


```

## temperature-alarms · 已触发告警如何恢复

chunk_id: `temperature-alarms:71d836cea39edf51a310`

来源：temperature-alarms.md，行 25–30；字符 [662, 878)

完整输入 tokens：275；超过300软目标：False

### 元数据

```
{
  "document_id": "temperature-alarms",
  "title": "持续超温、恢复与证据中断",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "alarms.py",
    "opcua_storage.py",
    "docs/protocols/点位表.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 已触发告警如何恢复

前提：已有未解除告警，且新的温度样本有效、新鲜。程序用这条告警记录保存的recover_below判断恢复。对保存阈值78℃的告警：79℃保持、78℃保持、77.9℃恢复。不能将“低于”解释为“小于等于”。修改默认值或更新文档不意味着已有告警采用了新阈值。

未解除告警记录与当前温度状态是两个维度。重启或断线不能自动解除告警。没有新鲜有效样本时，当前情况未知；不能因为记录仍未解除就断言此刻仍超温。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：持续超温、恢复与证据中断
文档ID：temperature-alarms
版本：0.1
章节：已触发告警如何恢复
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 已触发告警如何恢复

前提：已有未解除告警，且新的温度样本有效、新鲜。程序用这条告警记录保存的recover_below判断恢复。对保存阈值78℃的告警：79℃保持、78℃保持、77.9℃恢复。不能将“低于”解释为“小于等于”。修改默认值或更新文档不意味着已有告警采用了新阈值。

未解除告警记录与当前温度状态是两个维度。重启或断线不能自动解除告警。没有新鲜有效样本时，当前情况未知；不能因为记录仍未解除就断言此刻仍超温。


```

## temperature-alarms · 证据中断与设备隔离

chunk_id: `temperature-alarms:3a9038f09a76a3e84ab0`

来源：temperature-alarms.md，行 31–35；字符 [878, 1030)

完整输入 tokens：215；超过300软目标：False

### 元数据

```
{
  "document_id": "temperature-alarms",
  "title": "持续超温、恢复与证据中断",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "alarms.py",
    "opcua_storage.py",
    "docs/protocols/点位表.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 证据中断与设备隔离

通信失败、业务校验失败或不合格OPC UA样本会清除待确认，保留已有告警。不要补零解除告警。重复投递通知的去重与新通知携带重复源时间的处理不同，见OPC UA准入文档。

状态按设备和指标隔离，B的低温或失败不能改变A的告警。待确认计时在重新启动采集时重建，已触发记录保留。

```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：持续超温、恢复与证据中断
文档ID：temperature-alarms
版本：0.1
章节：证据中断与设备隔离
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 证据中断与设备隔离

通信失败、业务校验失败或不合格OPC UA样本会清除待确认，保留已有告警。不要补零解除告警。重复投递通知的去重与新通知携带重复源时间的处理不同，见OPC UA准入文档。

状态按设备和指标隔离，B的低温或失败不能改变A的告警。待确认计时在重新启动采集时重建，已触发记录保留。

```

## opcua-evidence · OPC UA质量、源时间与订阅证据

chunk_id: `opcua-evidence:c3f68ffbbf31f02a0a71`

来源：opcua-evidence.md，行 12–14；字符 [326, 348)

完整输入 tokens：90；超过300软目标：False

### 元数据

```
{
  "document_id": "opcua-evidence",
  "title": "OPC UA质量、源时间与订阅证据",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "opcua_storage.py",
    "collect_opcua.py",
    "docs/verification/opcua-subscription/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```

# OPC UA质量、源时间与订阅证据


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：OPC UA质量、源时间与订阅证据
文档ID：opcua-evidence
版本：0.1
章节：OPC UA质量、源时间与订阅证据
适用设备：motor-b
产品型号：未注明
仅教学：是
正文：

# OPC UA质量、源时间与订阅证据


```

## opcua-evidence · 设备身份与数据准入

chunk_id: `opcua-evidence:e834f93559c716a1203a`

来源：opcua-evidence.md，行 15–20；字符 [348, 630)

完整输入 tokens：274；超过300软目标：False

### 元数据

```
{
  "document_id": "opcua-evidence",
  "title": "OPC UA质量、源时间与订阅证据",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "opcua_storage.py",
    "collect_opcua.py",
    "docs/verification/opcua-subscription/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 设备身份与数据准入

适用范围：本项目motor-b教学模拟器，真实厂家型号未录入。读取节点为NamespaceURI urn:industrial-maintenance:motor-b、String标识MotorB.Temperature，运行时解析命名空间索引，不能固定套用ns编号。标量Double表示温度，℃为教学约定。

有效测量须满足Good、有限标量Double、源时间存在且新鲜、相对最后接受的源时间严格递增。默认源年龄允许0至5秒，未来时间不接受，前提是两端UTC时钟同步。Good表示质量状态，不证明电机健康，也不自动证明数据新鲜。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：OPC UA质量、源时间与订阅证据
文档ID：opcua-evidence
版本：0.1
章节：设备身份与数据准入
适用设备：motor-b
产品型号：未注明
仅教学：是
正文：
## 设备身份与数据准入

适用范围：本项目motor-b教学模拟器，真实厂家型号未录入。读取节点为NamespaceURI urn:industrial-maintenance:motor-b、String标识MotorB.Temperature，运行时解析命名空间索引，不能固定套用ns编号。标量Double表示温度，℃为教学约定。

有效测量须满足Good、有限标量Double、源时间存在且新鲜、相对最后接受的源时间严格递增。默认源年龄允许0至5秒，未来时间不接受，前提是两端UTC时钟同步。Good表示质量状态，不证明电机健康，也不自动证明数据新鲜。


```

## opcua-evidence · 源时间和处理时间

chunk_id: `opcua-evidence:f057e10cd44697b4d20c`

来源：opcua-evidence.md，行 21–26；字符 [630, 918)

完整输入 tokens：294；超过300软目标：False

### 元数据

```
{
  "document_id": "opcua-evidence",
  "title": "OPC UA质量、源时间与订阅证据",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "opcua_storage.py",
    "collect_opcua.py",
    "docs/verification/opcua-subscription/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 源时间和处理时间

SourceTimestamp按本模拟器约定表示测量生成时间；ServerTimestamp、客户端received_at与取得数据库写锁后的decision_at分别保留。接收时间不能代替缺失源时间。判断时再次检查源年龄：接收时4.9秒、排队0.2秒后已超过5秒，不可继续用于当前告警。

Good但源时间十秒前的样本在默认配置下被拒绝。Bad、Uncertain、缺源时间或过期数据保留诊断，清待确认，保留已有告警。收到响应不能说本次服务器未响应；旧源时间也不能单独证明传感器损坏。Modbus没有源时间的协议语义不同，不能机械套用本节门槛。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：OPC UA质量、源时间与订阅证据
文档ID：opcua-evidence
版本：0.1
章节：源时间和处理时间
适用设备：motor-b
产品型号：未注明
仅教学：是
正文：
## 源时间和处理时间

SourceTimestamp按本模拟器约定表示测量生成时间；ServerTimestamp、客户端received_at与取得数据库写锁后的decision_at分别保留。接收时间不能代替缺失源时间。判断时再次检查源年龄：接收时4.9秒、排队0.2秒后已超过5秒，不可继续用于当前告警。

Good但源时间十秒前的样本在默认配置下被拒绝。Bad、Uncertain、缺源时间或过期数据保留诊断，清待确认，保留已有告警。收到响应不能说本次服务器未响应；旧源时间也不能单独证明传感器损坏。Modbus没有源时间的协议语义不同，不能机械套用本节门槛。


```

## opcua-evidence · 两种重复

chunk_id: `opcua-evidence:16022736f29b004a0d24`

来源：opcua-evidence.md，行 27–30；字符 [918, 1037)

完整输入 tokens：177；超过300软目标：False

### 元数据

```
{
  "document_id": "opcua-evidence",
  "title": "OPC UA质量、源时间与订阅证据",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "opcua_storage.py",
    "collect_opcua.py",
    "docs/verification/opcua-subscription/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 两种重复

温度相同但源时间更新，可能是新测量，不能按数值相同直接丢弃。同一通知身份重新投递会去重，不重复写入或影响待确认；新通知身份携带重复源时间按当前严格策略拒绝并清待确认。这是本项目策略，不是OPC UA所有应用统一要求。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：OPC UA质量、源时间与订阅证据
文档ID：opcua-evidence
版本：0.1
章节：两种重复
适用设备：motor-b
产品型号：未注明
仅教学：是
正文：
## 两种重复

温度相同但源时间更新，可能是新测量，不能按数值相同直接丢弃。同一通知身份重新投递会去重，不重复写入或影响待确认；新通知身份携带重复源时间按当前严格策略拒绝并清待确认。这是本项目策略，不是OPC UA所有应用统一要求。


```

## opcua-evidence · 保活、重连和缺口

chunk_id: `opcua-evidence:25dcd4a3cd9acf3ac745`

来源：opcua-evidence.md，行 31–35；字符 [1037, 1215)

完整输入 tokens：243；超过300软目标：False

### 元数据

```
{
  "document_id": "opcua-evidence",
  "title": "OPC UA质量、源时间与订阅证据",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "opcua_storage.py",
    "collect_opcua.py",
    "docs/verification/opcua-subscription/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 保活、重连和缺口

保活说明订阅有响应，不是新的温度测量，不能累计超温。断线后重建订阅不意味着补齐缺失历史。旧连接代次迟到的回调不能更新当前状态。

服务器监视项队列与采集器应用队列是不同层。应用队列积压、溢出等会破坏证据连续性；增加客户端队列找不回服务端已丢通知。没有溢出标志不能证明无丢失。本项目不保证识别所有静默丢样或提供端到端恰好一次交付。

```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：OPC UA质量、源时间与订阅证据
文档ID：opcua-evidence
版本：0.1
章节：保活、重连和缺口
适用设备：motor-b
产品型号：未注明
仅教学：是
正文：
## 保活、重连和缺口

保活说明订阅有响应，不是新的温度测量，不能累计超温。断线后重建订阅不意味着补齐缺失历史。旧连接代次迟到的回调不能更新当前状态。

服务器监视项队列与采集器应用队列是不同层。应用队列积压、溢出等会破坏证据连续性；增加客户端队列找不回服务端已丢通知。没有溢出标志不能证明无丢失。本项目不保证识别所有静默丢样或提供端到端恰好一次交付。

```

## readonly-queries · 只读工具、历史统计与错误语义

chunk_id: `readonly-queries:3a9540590f18ec2a6097`

来源：readonly-queries.md，行 12–14；字符 [370, 389)

完整输入 tokens：98；超过300软目标：False

### 元数据

```
{
  "document_id": "readonly-queries",
  "title": "只读工具、历史统计与错误语义",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "assistant/tools.py",
    "assistant/query_service.py",
    "assistant/ranges.py",
    "docs/verification/m4-readonly-tools/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```

# 只读工具、历史统计与错误语义


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：只读工具、历史统计与错误语义
文档ID：readonly-queries
版本：0.1
章节：只读工具、历史统计与错误语义
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：

# 只读工具、历史统计与错误语义


```

## readonly-queries · 三个事实查询工具

chunk_id: `readonly-queries:115b1b58700e8124f216`

来源：readonly-queries.md，行 15–20；字符 [389, 607)

完整输入 tokens：247；超过300软目标：False

### 元数据

```
{
  "document_id": "readonly-queries",
  "title": "只读工具、历史统计与错误语义",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "assistant/tools.py",
    "assistant/query_service.py",
    "assistant/ranges.py",
    "docs/verification/m4-readonly-tools/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 三个事实查询工具

get_device_status查询设备支持指标的最后有效记录、质量、时效与告警。query_metric_history查询指定时间范围的历史。list_alarms查询与范围相交的告警。只读工具不提供任意SQL、shell、写设备或解除告警的能力。

工具ok=true仅表示查询成功，设备状态usable只表示记录在时效范围内，均不等于设备健康。旧的有效数值必须保留原时间，不能伪装成当前实时测量。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：只读工具、历史统计与错误语义
文档ID：readonly-queries
版本：0.1
章节：三个事实查询工具
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 三个事实查询工具

get_device_status查询设备支持指标的最后有效记录、质量、时效与告警。query_metric_history查询指定时间范围的历史。list_alarms查询与范围相交的告警。只读工具不提供任意SQL、shell、写设备或解除告警的能力。

工具ok=true仅表示查询成功，设备状态usable只表示记录在时效范围内，均不等于设备健康。旧的有效数值必须保留原时间，不能伪装成当前实时测量。


```

## readonly-queries · 完整统计与有限明细

chunk_id: `readonly-queries:012816da6b3985d263d8`

来源：readonly-queries.md，行 21–28；字符 [607, 912)

完整输入 tokens：320；超过300软目标：True

### 元数据

```
{
  "document_id": "readonly-queries",
  "title": "只读工具、历史统计与错误语义",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "assistant/tools.py",
    "assistant/query_service.py",
    "assistant/ranges.py",
    "docs/verification/m4-readonly-tools/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 完整统计与有限明细

query_metric_history按collected_at闭区间查询quality=good记录，最大范围24小时，时间须带时区。motor-b的collected_at是接收时间，不是源时间。

count/min/max在全部匹配样本上计算。limit仅限制返回明细，最大1000；明细按时间及id升序。即使返回两条，也不是只用两条计算最高值。truncated表示明细截断，不代表统计截断。

最大值是已记录有效样本最大值，不保证等于真实物理峰值。首末时间不能证明中间无缺口，不能用订阅假设固定每秒一条计算完整率。运行状态是枚举，统计各状态次数，不计算物理最大值。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：只读工具、历史统计与错误语义
文档ID：readonly-queries
版本：0.1
章节：完整统计与有限明细
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 完整统计与有限明细

query_metric_history按collected_at闭区间查询quality=good记录，最大范围24小时，时间须带时区。motor-b的collected_at是接收时间，不是源时间。

count/min/max在全部匹配样本上计算。limit仅限制返回明细，最大1000；明细按时间及id升序。即使返回两条，也不是只用两条计算最高值。truncated表示明细截断，不代表统计截断。

最大值是已记录有效样本最大值，不保证等于真实物理峰值。首末时间不能证明中间无缺口，不能用订阅假设固定每秒一条计算完整率。运行状态是枚举，统计各状态次数，不计算物理最大值。


```

## readonly-queries · 空结果和失败

chunk_id: `readonly-queries:8feda4e6e02103c47b00`

来源：readonly-queries.md，行 29–32；字符 [912, 1021)

完整输入 tokens：159；超过300软目标：False

### 元数据

```
{
  "document_id": "readonly-queries",
  "title": "只读工具、历史统计与错误语义",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "assistant/tools.py",
    "assistant/query_service.py",
    "assistant/ranges.py",
    "docs/verification/m4-readonly-tools/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 空结果和失败

查询成功但没有有效样本：count=0，min/max=null，说明无数据、无法计算，不能返回0℃。数据库不可读、超时等返回ok=false及结构化error，不能解释成没有记录或没有告警。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：只读工具、历史统计与错误语义
文档ID：readonly-queries
版本：0.1
章节：空结果和失败
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 空结果和失败

查询成功但没有有效样本：count=0，min/max=null，说明无数据、无法计算，不能返回0℃。数据库不可读、超时等返回ok=false及结构化error，不能解释成没有记录或没有告警。


```

## readonly-queries · 告警相交与记录状态

chunk_id: `readonly-queries:e9d1a0388ed6b5e40fdf`

来源：readonly-queries.md，行 33–37；字符 [1021, 1254)

完整输入 tokens：265；超过300软目标：False

### 元数据

```
{
  "document_id": "readonly-queries",
  "title": "只读工具、历史统计与错误语义",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "assistant/tools.py",
    "assistant/query_service.py",
    "assistant/ranges.py",
    "docs/verification/m4-readonly-tools/验收说明.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 告警相交与记录状态

告警started_at不晚于查询end，且recovered_at为空或不早于start，才与闭区间相交。查询范围开始前触发但范围内仍未恢复的告警也应包含。

status筛选依据查询时记录是否恢复，不是重建过去某一刻状态。历史告警内阈值描述该次记录；当前状态返回的rule含查询进程默认值及部分数据库状态，不是所有采集进程已同步加载配置的证明。旧库history_available=false表示无告警历史表，不等于确认没有告警。

```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：只读工具、历史统计与错误语义
文档ID：readonly-queries
版本：0.1
章节：告警相交与记录状态
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 告警相交与记录状态

告警started_at不晚于查询end，且recovered_at为空或不早于start，才与闭区间相交。查询范围开始前触发但范围内仍未恢复的告警也应包含。

status筛选依据查询时记录是否恢复，不是重建过去某一刻状态。历史告警内阈值描述该次记录；当前状态返回的rule含查询进程默认值及部分数据库状态，不是所有采集进程已同步加载配置的证明。旧库history_available=false表示无告警历史表，不等于确认没有告警。

```

## evidence-boundaries · 资料适用性、引用与无法确定的情况

chunk_id: `evidence-boundaries:d45bb0029936b76b1b60`

来源：evidence-boundaries.md，行 12–14；字符 [282, 303)

完整输入 tokens：105；超过300软目标：False

### 元数据

```
{
  "document_id": "evidence-boundaries",
  "title": "资料适用性、引用与无法确定的情况",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "docs/project-plan-v0.2.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```

# 资料适用性、引用与无法确定的情况


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：资料适用性、引用与无法确定的情况
文档ID：evidence-boundaries
版本：0.1
章节：资料适用性、引用与无法确定的情况
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：

# 资料适用性、引用与无法确定的情况


```

## evidence-boundaries · 教学资料适用范围

chunk_id: `evidence-boundaries:7ccc1f91f4ac69d1f4c0`

来源：evidence-boundaries.md，行 15–18；字符 [303, 425)

完整输入 tokens：191；超过300软目标：False

### 元数据

```
{
  "document_id": "evidence-boundaries",
  "title": "资料适用性、引用与无法确定的情况",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "docs/project-plan-v0.2.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 教学资料适用范围

本知识库是项目教学说明，不是厂家手册，未提供真实产品型号、厂家故障码定义、润滑周期或维修操作规程。motor-a/motor-b是设备编号，不能推导产品型号。未注明型号不等于全部型号适用；型号、版本和工况都需核对。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：资料适用性、引用与无法确定的情况
文档ID：evidence-boundaries
版本：0.1
章节：教学资料适用范围
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 教学资料适用范围

本知识库是项目教学说明，不是厂家手册，未提供真实产品型号、厂家故障码定义、润滑周期或维修操作规程。motor-a/motor-b是设备编号，不能推导产品型号。未注明型号不等于全部型号适用；型号、版本和工况都需核对。


```

## evidence-boundaries · 事实、可能原因与现场排查

chunk_id: `evidence-boundaries:489aa895829ee1d2434a`

来源：evidence-boundaries.md，行 19–24；字符 [425, 615)

完整输入 tokens：266；超过300软目标：False

### 元数据

```
{
  "document_id": "evidence-boundaries",
  "title": "资料适用性、引用与无法确定的情况",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "docs/project-plan-v0.2.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 事实、可能原因与现场排查

设备查询工具提供当次记录事实，文档提供规则和解释依据。已记录85℃只支持超温现象，不能证明轴承或润滑系统损坏。即使外部手册列某项可能原因，也需适用性核对及现场证据才能确认；本项目不提供完整根因诊断。

缺少适用故障码表或维护周期时，说明未找到适用依据，先核对实际型号及对应手册。不能从字面相同的故障码套用另一型号资料，也不能猜测具体维修周期。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：资料适用性、引用与无法确定的情况
文档ID：evidence-boundaries
版本：0.1
章节：事实、可能原因与现场排查
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 事实、可能原因与现场排查

设备查询工具提供当次记录事实，文档提供规则和解释依据。已记录85℃只支持超温现象，不能证明轴承或润滑系统损坏。即使外部手册列某项可能原因，也需适用性核对及现场证据才能确认；本项目不提供完整根因诊断。

缺少适用故障码表或维护周期时，说明未找到适用依据，先核对实际型号及对应手册。不能从字面相同的故障码套用另一型号资料，也不能猜测具体维修周期。


```

## evidence-boundaries · 引用与版本

chunk_id: `evidence-boundaries:feca3f1ea56af749080b`

来源：evidence-boundaries.md，行 25–30；字符 [615, 791)

完整输入 tokens：240；超过300软目标：False

### 元数据

```
{
  "document_id": "evidence-boundaries",
  "title": "资料适用性、引用与无法确定的情况",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "docs/project-plan-v0.2.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 引用与版本

引用须支持实际陈述，不能引用“低于78℃”却回答“等于78℃也恢复”。引用应包含文档ID、版本、章节和真实chunk_id。文档更新时应替换或停用默认检索中的旧版片段，不能同时混用互相矛盾的版本。

文档记载、当前程序配置、某次历史告警所用规则是不同证据。出现冲突须说明并核对；查不到当前配置时，不能用最新文档冒充当前生效规则。


```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：资料适用性、引用与无法确定的情况
文档ID：evidence-boundaries
版本：0.1
章节：引用与版本
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 引用与版本

引用须支持实际陈述，不能引用“低于78℃”却回答“等于78℃也恢复”。引用应包含文档ID、版本、章节和真实chunk_id。文档更新时应替换或停用默认检索中的旧版片段，不能同时混用互相矛盾的版本。

文档记载、当前程序配置、某次历史告警所用规则是不同证据。出现冲突须说明并核对；查不到当前配置时，不能用最新文档冒充当前生效规则。


```

## evidence-boundaries · 元数据与生成概述

chunk_id: `evidence-boundaries:34190ae88f7d579d93d9`

来源：evidence-boundaries.md，行 31–33；字符 [791, 919)

完整输入 tokens：198；超过300软目标：False

### 元数据

```
{
  "document_id": "evidence-boundaries",
  "title": "资料适用性、引用与无法确定的情况",
  "version": "0.1",
  "reviewed_on": "2026-09-18",
  "teaching_only": true,
  "device_ids": [
    "motor-a",
    "motor-b"
  ],
  "product_model": null,
  "sources": [
    "docs/project-plan-v0.2.md"
  ],
  "authoring": "AI-assisted, checked against project sources"
}
```

### 原文（不含元数据前缀）

```
## 元数据与生成概述

型号、版本、出处须来自明确来源；未知保留null或未注明。AI生成上下文说明不能扩大适用范围或删掉条件，不替代原文。格式正确不证明语义正确。当前这批正文由AI依据项目文件整理并核对，未运行独立的批量AI摘要增强或向量检索流水线。

```

### embedding_text（标题、适用范围前缀＋原文）

```
文档：资料适用性、引用与无法确定的情况
文档ID：evidence-boundaries
版本：0.1
章节：元数据与生成概述
适用设备：motor-a, motor-b
产品型号：未注明
仅教学：是
正文：
## 元数据与生成概述

型号、版本、出处须来自明确来源；未知保留null或未注明。AI生成上下文说明不能扩大适用范围或删掉条件，不替代原文。格式正确不证明语义正确。当前这批正文由AI依据项目文件整理并核对，未运行独立的批量AI摘要增强或向量检索流水线。

```
