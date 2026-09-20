import { expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { OperatingPanel, RunningHistory } from './OperatingPanel'
import type { MetricSnapshot } from './model'

const status = {has_data:true,last_attempt_status:'success' as const,last_attempt_at:'2026-09-17T00:00:00Z',last_success_at:'2026-09-17T00:00:00Z',last_failure_at:null,data_age_seconds:0,is_stale:false,checked_at:'2026-09-17T00:00:00Z',stale_after_seconds:5}
const reading: MetricSnapshot = {status,measurement:{id:4,device_id:'motor-a',metric:'running_state',value:1,unit:'',collected_at:'2026-09-17T00:00:00Z',source_time:null,quality:'good',protocol:'modbus_tcp'}}
it('断线保留运行原记录，当前未知，不能显示停止',()=>{
  const html=renderToStaticMarkup(<OperatingPanel metric="running_state" reading={{...reading,status:{...status,last_attempt_status:'failure',last_failure_type:'communication_error',last_failure_message:'offline'}}} unverified={false}/> )
  expect(html).toContain('当前未知')
  expect(html).toContain('通信失败')
  expect(html).toContain('最后有效运行状态')
  expect(html).toContain('>运行<')
  expect(html).toContain('2026-09-17T00:00:00Z')
  expect(html).not.toContain('>停止<')
})
it('成功0是停止，非法2显示校验失败证据并保留旧运行值',()=>{
  const stopped={...reading,measurement:{...reading.measurement!,value:0}}
  expect(renderToStaticMarkup(<OperatingPanel metric="running_state" reading={stopped} unverified={false}/>)).toContain('>停止<')
  const invalid={...reading,status:{...status,last_attempt_status:'failure' as const,last_failure_type:'data_validation_error',last_failure_message:'running_state 原始值=2，只允许0/1'}}
  const html=renderToStaticMarkup(<OperatingPanel metric="running_state" reading={invalid} unverified={false}/> )
  expect(html).toContain('数据校验失败')
  expect(html).toContain('原始值=2')
  expect(html).not.toContain('通信失败')
})
it('旧API不提供与旧库无样本不同；状态历史不画连续数值轴',()=>{
  expect(renderToStaticMarkup(<OperatingPanel metric="speed" unverified={false}/>)).toContain('未提供转速')
  expect(renderToStaticMarkup(<OperatingPanel metric="running_state" reading={{...reading,measurement:null,status:{...status,has_data:false}}} unverified={false}/>)).toContain('暂无运行状态样本')
  const html=renderToStaticMarkup(<RunningHistory history={{from:status.checked_at,to:status.checked_at,limit:1000,points:[reading.measurement!,{...reading.measurement!,id:8,value:0}]}}/> )
  expect(html).toContain('运行')
  expect(html).toContain('停止')
  expect(html).toContain('原始值')
  expect(html).not.toContain('<svg')
})
it('API不可用或样本自身过期，保留数值并明确当前未知',()=>{
  expect(renderToStaticMarkup(<OperatingPanel metric="running_state" reading={reading} unverified/>)).toContain('当前未知')
  expect(renderToStaticMarkup(<OperatingPanel metric="running_state" reading={{...reading,status:{...status,is_stale:true}}} unverified={false}/>)).toContain('数据已过期')
})
