import { localTime, type OpcuaStatus } from './model'

const freshnessNames: Record<string, string> = {
  fresh: '源测量在时限内', missing: '设备未提供源时间，测量新鲜度无法核实',
  stale: '源测量已过期', future: '源时间在未来，无法核实',
  duplicate: '重复源时间，不是新测量', backward: '源时间倒退，不是新测量', unknown: '尚无源时间证据',
}
const runtimeNames: Record<string, string> = {
  reading: '主动读取中', connecting: '正在连接', subscribed: '已订阅', reconnecting: '等待重连',
  stopped: '采集已停止', failed: '采集故障停止', unknown: '当前未知',
}
export function OpcuaPanel({ evidence, unverified, sourceExpired = false, runtimeExpired = false }: { evidence?: OpcuaStatus | null; unverified: boolean; sourceExpired?: boolean; runtimeExpired?: boolean }) {
  const diagnostic = evidence?.diagnostic
  const runtime = evidence?.runtime
  const unknown = unverified || runtimeExpired
  const runtimeReady = !runtime || ['reading', 'subscribed'].includes(runtime.state)
  const eligible = !!evidence?.eligible && !unknown && !sourceExpired && runtimeReady
  return <section className="chart-panel opcua-panel" aria-label="OPC UA 数据证据">
    <div className="chart-heading"><div><h2>OPC UA 数据证据</h2><p>读取成功、质量合格和源测量足够新，分别判断。</p></div><span className={`badge ${eligible ? '' : 'warn'}`} data-testid="opcua-eligibility">{unknown ? '当前未知' : eligible ? '可以参与温度告警' : '不可参与温度告警'}</span></div>
    {runtime && <div className="subscription-evidence">
      <dl className="opcua-evidence">
        <div><dt>采集模式</dt><dd data-testid="opcua-mode">{runtime.mode === 'subscribe' ? '订阅通知' : '主动周期读取'}</dd></div>
        <div><dt>采集链状态</dt><dd data-testid="opcua-runtime">{unknown ? '当前未知' : runtimeNames[runtime.state] || '当前未知'}</dd></div>
        <div><dt>连接世代 / 重连次数</dt><dd>{runtime.generation} / {runtime.reconnect_count}</dd></div>
        <div><dt>采集器心跳</dt><dd>{localTime(runtime.updated_at)}</dd></div>
        {runtime.mode === 'subscribe' && <>
          <div><dt>最近发布响应（含保活）</dt><dd>{localTime(runtime.last_publish_at)}</dd></div>
          <div><dt>最近数据通知接收</dt><dd>{localTime(runtime.last_notification_at)}</dd></div>
          <div><dt>已忽略重复投递 / 丢弃通知</dt><dd data-testid="opcua-deliveries">{runtime.duplicate_count} / {runtime.dropped_count}</dd></div>
          <div><dt>服务端确认参数</dt><dd data-testid="opcua-revised">{runtime.revised ? `发布 ${runtime.revised.publishing_interval_ms} ms · 采样 ${runtime.revised.sampling_interval_ms} ms · 队列 ${runtime.revised.queue_size} · 保活 ${runtime.revised.keepalive_count} · 生命周期 ${runtime.revised.lifetime_count}` : '等待服务器确认'}</dd></div>
        </>}
      </dl>
      {runtime.error && <p className="error-detail" data-testid="opcua-runtime-error">采集链记录：{runtime.error}</p>}
      {runtime.mode === 'subscribe' && <p className="scope-note">保活响应只说明订阅仍有响应，不是新的温度测量。断线后创建新订阅，不补采断线期间数据；同一通知重投递不会推进或清除待确认计时。</p>}
    </div>}
    <dl className="opcua-evidence">
      <div><dt>最近通信结果</dt><dd data-testid="opcua-communication">{unknown ? '当前未知（保留上次证据）' : evidence?.communication === 'failure' ? '通信失败' : !runtimeReady ? '当前未知（保留上次证据）' : evidence?.communication === 'success' ? (runtime?.mode === 'subscribe' ? '已接收数据通知' : '读取成功') : '尚无读取结果'}</dd></div>
      <div><dt>最近 DataValue 质量{evidence?.communication === 'failure' ? '（历史）' : ''}</dt><dd data-testid="opcua-quality">{diagnostic?.status_name || '—'}{diagnostic && ` · ${evidence?.quality} · 0x${diagnostic.status_code.toString(16).padStart(8, '0')}`}</dd></div>
      <div><dt>源测量新鲜度</dt><dd data-testid="opcua-source-state">{unverified ? '当前未知' : sourceExpired && evidence?.source_freshness === 'fresh' ? '源测量已过期' : freshnessNames[evidence?.source_freshness || 'unknown']}</dd></div>
      <div><dt>原始值（诊断）</dt><dd data-testid="opcua-raw">{diagnostic?.value_json ?? '—'}{diagnostic && ` · ${diagnostic.variant_type}`}</dd></div>
      <div><dt>设备源时间</dt><dd>{localTime(diagnostic?.source_time)}</dd></div>
      <div><dt>服务端时间</dt><dd>{localTime(diagnostic?.server_time)}</dd></div>
      <div><dt>接收时间</dt><dd><time dateTime={diagnostic?.received_at}>{localTime(diagnostic?.received_at)}</time></dd></div>
      <div><dt>判定时间</dt><dd><time data-testid="opcua-decision-time" dateTime={diagnostic?.decision_at || undefined}>{diagnostic?.decision_at ? localTime(diagnostic.decision_at) : '未记录'}</time></dd></div>
      <div><dt>本次入库判定</dt><dd>{diagnostic ? diagnostic.accepted ? '已保存有效测量' : `仅保存诊断：${diagnostic.reason || evidence?.reason}` : '尚无诊断'}</dd></div>
    </dl>
    <p className="scope-note">原始值仅作诊断；被拒绝的数据不会替换上方有效温度。接收时间不代替设备源时间；排队后按判定时刻再次检查源年龄。不可用时取消待确认计时，已激活告警保留。</p>
  </section>
}
