import { useEffect, useState } from 'react'
import { freshness, localTime, type Metric, type Snapshot } from './model'
import { noticeKind, notices } from './presentation'
import { alarmUnverified, diagnosticExpired, runtimeExpired } from './alarmFreshness'
import { OpcuaPanel } from './OpcuaPanel'
import { AlarmPanel } from './AlarmPanel'
import { AssistantPanel } from './AssistantPanel'
import { OperatingPanel, RunningHistory } from './OperatingPanel'
import { CurrentPanel } from './CurrentPanel'
import { ReplayFaultPanel, ReplayMetricsPanel } from './ReplayPanel'
import { MotorDiagram } from './MotorDiagram'
import { TemperatureChart } from './TemperatureChart'
import { useDashboard } from './useDashboard'

const METRIC_OPTIONS: Record<Metric, string> = {
  temperature: '温度（℃）', air_temperature: '空气温度（℃）', current: '电流（A）',
  speed: '转速（rpm）', torque: '扭矩（Nm）', tool_wear: '刀具磨损（min）', running_state: '运行状态记录',
}
const DEVICE_METRICS: Record<string, Metric[]> = {
  'motor-a': ['temperature', 'current', 'speed', 'running_state'],
  'motor-b': ['temperature'],
  'motor-c': ['temperature', 'air_temperature', 'speed', 'torque', 'tool_wear', 'running_state'],
}

export default function App() {
  const [deviceId, setDeviceId] = useState('motor-a')
  const { snapshot, phase, error, fetchedAt } = useDashboard(deviceId)
  const [devices, setDevices] = useState<Snapshot['device'][]>([])
  useEffect(() => { if (snapshot?.devices) setDevices(snapshot.devices) }, [snapshot?.devices])
  const isOpcua = deviceId === 'motor-b'
  const isReplay = deviceId === 'motor-c'
  const deviceMetrics = (devices.find(item => item.id === deviceId)?.metrics as Metric[] | undefined) ?? DEVICE_METRICS[deviceId] ?? DEVICE_METRICS['motor-a']
  const [metric, setMetric] = useState<Metric>('temperature')
  const [now, setNow] = useState(Date.now())
  useEffect(() => { const timer = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(timer) }, [])
  const delayed = fetchedAt !== undefined && now - fetchedAt > 6000
  const unverified = !!error || delayed
  const sample = snapshot?.measurement
  const status = snapshot?.status
  const sourceExpired = isOpcua && diagnosticExpired(snapshot, performance.now())
  const runtimeStale = isOpcua && runtimeExpired(snapshot, performance.now())
  const fresh = freshness(status, unverified || (isOpcua && (!snapshot?.opcua?.eligible || sourceExpired || runtimeStale)))
  const firstLoad = !snapshot && !error
  const attempt = status?.last_attempt_status === 'success' ? '最近一次成功' : status?.last_attempt_status === 'failure' ? '最近一次失败' : '尚无明确结果'
  const kind = noticeKind(status, !!error, delayed)
  const notice = isOpcua && snapshot && !unverified ? {
    title: snapshot.opcua?.eligible && !sourceExpired && !runtimeStale ? '已获取有效源测量' : '本次源测量不可用于告警',
    message: '有效温度只接收质量 Good、源时间足够新且严格递增的测量。请结合下方通信、质量和源时间证据查看。',
    action: '缺源、过期、重复和倒退不会补成新样本；已激活告警保留。',
    tone: snapshot.opcua?.eligible && !sourceExpired && !runtimeStale ? '' : 'warn',
  } : isReplay && snapshot && !unverified ? {
    title: '历史数据集回放，非实时采集',
    message: '本设备逐行回放 UCI AI4I 2020 预测性维护合成数据集（CC BY 4.0）；时间为回放时刻，不是原始采集时间。',
    action: '曲线波动与故障标注来自数据集自身；回放停止后数据会如实显示“已过期”。',
    tone: '',
  } : notices[kind]
  const history = metric === 'temperature' ? snapshot?.history : snapshot?.[metric]?.history
  const chartLabel = { temperature: '温度', air_temperature: '空气温度', current: '电流', speed: '转速', torque: '扭矩', tool_wear: '刀具磨损', running_state: '运行状态' }[metric]
  const chartUnit = { temperature: '℃', air_temperature: '℃', current: 'A', speed: 'rpm', torque: 'Nm', tool_wear: 'min', running_state: '枚举' }[metric]
  return <main className="shell">
    <header className="masthead">
      <div className="workspace-title"><span className="brand-mark" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"><path d="M3 17h4l3-10 4 13 3-8h4" /></svg></span><div><h1>设备观测工作台</h1><p>多协议电机观测终端</p></div></div>
      <span className="tag">本地仿真 / 只读</span>
    </header>

    <div className="console">
      <div className="console-main">

    <div className="metric-selector device-selector"><label htmlFor="device-selector">观测设备</label><select id="device-selector" value={deviceId} onChange={event => { setDeviceId(event.target.value); setMetric('temperature') }}>
      {devices.length ? devices.map(device => <option key={device.id} value={device.id}>{device.name} · {device.protocol === 'opcua' ? 'OPC UA' : device.protocol === 'replay' ? '数据回放' : 'Modbus TCP'}</option>) : <option value="motor-a">模拟电机 A</option>}
    </select><span>{isOpcua ? `温度单测点 · ${snapshot?.opcua?.runtime?.mode === 'subscribe' ? '订阅通知' : snapshot?.opcua?.runtime?.mode === 'read' ? '主动周期读取' : '采集方式未报告'}` : isReplay ? 'AI4I 2020 合成数据集 · 历史回放 · 非实时' : '温度、电流、转速、运行状态'}</span></div>

    <details className="usage" id="usage">
      <summary><span>使用说明</span><span className="summary-hint">从哪里看起，数据不更新时怎么办</span></summary>
      <div className="usage-body">
        <ol className="usage-steps">
          <li><strong>看温度</strong><p>大数字是最后一次成功采集的温度，不是预测值。显示“—”时，尚未取得样本。</p></li>
          <li><strong>看时间与状态</strong><p>先看原采集时间。出现“过期”或“未能核实”时，把数值当作历史记录，不当作当前温度。</p></li>
          <li><strong>看曲线</strong><p>观察最近10分钟的真实记录。断开的地方没有连续样本；刚开始采集时，只有右侧少量点是正常现象。</p></li>
        </ol>
        <div className="startup-help"><strong>打开本项目</strong><p>在项目根目录的终端运行下面的命令，并保持该终端开启：</p><code>uv run --locked python run_dashboard.py</code><p>然后打开 <a href="http://127.0.0.1:5175">http://127.0.0.1:5175</a>。如果仍无数据，查看启动终端的错误提示，确认模拟器、采集器和后端正常启动，采集器与后端使用同一个数据库。</p></div>
        <p className="scope-note">这是软件仿真实验。页面只查询记录，不启动采集或控制设备；采集成功、数据未过期都不等于设备健康。</p>
      </div>
    </details>

    <section className={`notice ${notice.tone}`} role="status" aria-live="polite">
      <span className="notice-symbol" aria-hidden="true">{notice.tone === 'warn' ? '!' : 'i'}</span>
      <div><h2>{kind === 'loading' && phase === 'idle' ? '尚未加载设备数据' : error ? '接口请求失败，当前状态未能核实' : notice.title}</h2><p>{notice.message}</p>{notice.action && <p className="next-step">{notice.action}</p>}</div>
    </section>

    <section className="instrument" aria-label="最新温度与采集状态">
      <div className="instrument-heading"><div><h2>{snapshot?.device.name || (isOpcua ? '模拟电机 B' : isReplay ? 'AI4I 2020 数控机床（历史回放）' : '模拟电机 A')}</h2><span>{snapshot?.device.protocol === 'modbus_tcp' ? 'Modbus TCP' : snapshot?.device.protocol === 'replay' ? '数据回放 · AI4I 2020' : snapshot?.device.protocol || '协议信息待加载'}</span></div><span className="poll-label">{phase === 'loading' ? '正在查询新记录…' : '自动查询，约每2秒一次'}</span></div>
      <div className={`instrument-body${isReplay ? ' replay-two' : ''}`}>
        <article className="reading">
          <h3>最后有效温度</h3>
          <div className="temperature"><span className="number" data-testid="temperature">{sample ? sample.value.toFixed(1) : '—'}</span><span className="unit">{sample?.unit || '℃'}</span></div>
          <p className="value-note">{unverified ? (sample ? '保留的历史记录，当前状态未核实' : '暂未取得读数，当前状态未核实') : sample ? (isOpcua ? '来自最近一次通过质量和源时间校验的测量' : isReplay ? '数据集工艺温度列（K→℃精确换算），时间为回放时刻' : '来自最近一次成功采集') : firstLoad ? '读取完成后显示实际数值' : '等待第一次成功采集'}</p>
          <div className="sample-time"><span>{isOpcua ? '有效测量接收时间（本地）' : isReplay ? '该行回放时间（本地）' : '原采集时间（本地）'}</span><time data-testid="sample-time" dateTime={sample?.collected_at}>{localTime(sample?.collected_at)}</time></div>
        </article>
        {!isReplay && <MotorDiagram />}
        <article className="observation">
          <h3>这条数据有多新？ {unverified && snapshot && <span className="snapshot-label">历史快照</span>}</h3>
          <dl>
            <div><dt>数据状态</dt><dd><span data-testid="freshness" className={`badge ${fresh.tone}`}>{firstLoad ? '待加载' : fresh.label}</span></dd></div>
            <div><dt>{isOpcua ? '源测量年龄' : '数据年龄'} <small>查询时</small></dt><dd>{status?.data_age_seconds == null ? '—' : `${status.data_age_seconds.toFixed(1)} 秒`}</dd></div>
            <div className="attempt-row"><dt>{isOpcua ? '最近有效性判定' : '最近采集尝试'}</dt><dd data-testid="attempt">{attempt}</dd></div>
            <div><dt>尝试发生时间</dt><dd><time dateTime={status?.last_attempt_at || undefined}>{localTime(status?.last_attempt_at)}</time></dd></div>
          </dl>
        </article>
      </div>
    </section>

    {isOpcua ? <OpcuaPanel evidence={snapshot?.opcua} unverified={unverified} sourceExpired={sourceExpired} runtimeExpired={runtimeStale} /> : isReplay ? <ReplayMetricsPanel torque={snapshot?.torque} toolWear={snapshot?.tool_wear} airTemperature={snapshot?.air_temperature} unverified={unverified} /> : <CurrentPanel current={snapshot?.current} unverified={unverified} />}

    {!isOpcua && <div className="operating-grid"><OperatingPanel metric="speed" reading={snapshot?.speed} unverified={unverified} replay={isReplay} /><OperatingPanel metric="running_state" reading={snapshot?.running_state} unverified={unverified} replay={isReplay} /></div>}

    {isReplay ? <ReplayFaultPanel replay={snapshot?.replay} unverified={unverified} /> : <AlarmPanel alarm={snapshot?.alarm} unverified={alarmUnverified(snapshot, unverified || runtimeStale, performance.now())} />}

    <section className="chart-panel">
      <div className="chart-heading"><div><h2>最近10分钟{chartLabel}{metric === 'running_state' ? '记录' : '趋势'}</h2><p>{metric === 'running_state' ? '按实际采集记录展示，不推断样本之间的状态。' : `横轴是本地时间，纵轴是${chartLabel}。`}{unverified ? (history ? '当前显示最后获取的历史快照。' : '暂未取得历史查询结果。') : '只绘制实际采集的记录。'}</p></div><span className="legend">{chartLabel} / {chartUnit}</span></div>
      <div className="metric-selector"><label htmlFor="history-metric">历史指标</label><select id="history-metric" value={metric} onChange={event => setMetric(event.target.value as Metric)}>{deviceMetrics.map(item => <option key={item} value={item}>{METRIC_OPTIONS[item]}</option>)}</select><span>一次只显示一个指标，单位不混用</span></div>
      {history && history.points.length > 0 ? metric === 'running_state' ? <RunningHistory history={history} replay={isReplay} /> : <TemperatureChart history={history} metric={metric} /> : <div className="empty-chart"><strong>{firstLoad ? '正在读取历史记录' : unverified ? '暂时无法获取历史记录' : metric !== 'temperature' && !snapshot?.[metric] ? `当前接口未提供${chartLabel}` : `这个时间窗口还没有${chartLabel}样本`}</strong><p>{firstLoad ? '请稍候，记录返回后会自动显示。' : unverified ? '先检查后端查询服务；查询失败不代表数据库里没有数据。' : isReplay ? '回放器运行后曲线会自动出现；每个回放行是一条真实数据集记录。' : '检查采集器是否正在运行；第一次采集成功后，曲线会自动出现。'}</p></div>}
      <div className="chart-note"><span data-testid="sample-count">{history?.points.length ?? 0} 个真实样本</span><span>{metric === 'running_state' ? '只显示实际记录，不推断中间状态' : '采集缺口断开显示，不补零'}</span>{history && history.points.length >= history.limit && <strong className="warning">已达到1000条上限，窗口后段可能被截断</strong>}</div>
    </section>

    <details className="technical-details">
      <summary>查看采样细节与状态含义</summary>
      <div className="technical-body"><dl><div><dt>设备标识</dt><dd>{deviceId}</dd></div><div><dt>这次采样的质量</dt><dd>{sample?.quality || '无样本'}</dd></div><div><dt>后端检查时间</dt><dd>{localTime(status?.checked_at)}</dd></div><div><dt>数据过期阈值</dt><dd>大于 {status?.stale_after_seconds ?? 5} 秒</dd></div></dl>
        <p>“最近一次成功”只说明那次采集成功，不证明设备当前在线；数据过期不直接等于设备断线；质量 good 不代表电机健康。</p>
        <p>默认每秒采集时，相邻记录超过1.5秒就断开曲线。单个样本会显示为一个点；曲线不生成插值样本。</p>
        {error && <p className="error-detail">接口返回信息：{error}</p>}
      </div>
    </details>
      </div>{/* /console-main */}

      <aside className="operator-terminal" aria-label="值班终端">
        <AssistantPanel phase="idle" />
      </aside>
    </div>{/* /console */}
    <footer className="page-footer"><span>设备状态以采集记录为依据，不作健康判断</span><span>前端最后获取成功：<time data-testid="fetched-at">{localTime(fetchedAt)}</time></span></footer>
  </main>
}
