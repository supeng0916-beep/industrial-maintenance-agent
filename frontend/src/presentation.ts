import type { Status } from './model'

export function noticeKind(
  status: Pick<Status, 'has_data' | 'is_stale' | 'last_attempt_status' | 'last_failure_type'> | undefined,
  error: boolean, delayed: boolean,
) {
  if (error || delayed) return 'unverified'
  if (!status) return 'loading'
  if (status.last_attempt_status === 'failure') return status.last_failure_type === 'data_validation_error' ? 'validation' : 'failure'
  if (!status.has_data) return 'empty'
  if (status.is_stale) return 'stale'
  return 'fresh'
}

export const notices = {
  validation: { title: '本轮数据校验失败', message: '协议读取已返回，但测点值不符合定义。本轮四个测量都未保存，已有数值保持原时间；温度待确认计时取消，已激活告警保留。', action: '查看下方运行状态的失败证据，核对点位表中的0＝停止、1＝运行，以及模拟器配置。', tone: 'warn' },
  unverified: { title: '当前状态未能核实', message: '页面暂时取不到新的查询结果。若下方还有温度，那是最后一次成功获取的记录，原采集时间没有改变。', action: '检查启动看板的终端是否仍在运行、后端服务是否可用；再确认采集器与后端使用同一个数据库。页面会自动重试。', tone: 'warn' },
  loading: { title: '正在读取设备数据', message: '正在获取设备、最后一次温度和最近10分钟的记录。', action: '', tone: 'neutral' },
  empty: { title: '还没有温度记录', message: '查询服务已响应，但还没有成功采集的样本。“—”表示无数据，不是0℃。', action: '检查启动终端中的模拟器和采集器是否运行，并确认采集器与后端使用同一个数据库。', tone: 'neutral' },
  failure: { title: '最近采集尝试失败', message: '这次没有取得新样本。已有温度会保留原值与原时间，不能当作当前读数。', action: '检查启动终端中的模拟器是否运行、采集端口是否一致。恢复后等待下一次成功采集。', tone: 'warn' },
  stale: { title: '显示的是较早的温度', message: '最后一次有效温度已超过新鲜度阈值。数据过期本身不能说明设备断线。', action: '先查看下方原采集时间，再检查采集器是否持续产生新记录。', tone: 'warn' },
  fresh: { title: '已获取采集记录', message: '温度来自最后一次成功采集。先看数值，再结合采集时间和数据状态判断它是否足够新。', action: '', tone: '' },
}
