import { expect, it, vi, afterEach } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { CurrentPanel } from './CurrentPanel'
import { loadSnapshot } from './useDashboard'
import type { Status } from './model'

const status: Status = { has_data: false, last_attempt_status:'unknown', last_attempt_at:null,last_success_at:null,last_failure_at:null,data_age_seconds:null,is_stale:null,checked_at:'2026-09-17T00:00:00Z',stale_after_seconds:5 }
afterEach(()=>vi.unstubAllGlobals())
it('旧API不提供电流时不发电流请求，温度仍能加载',async()=>{
  const fetcher=vi.fn(async (path:string)=>({ok:true,json:async()=>path==='/api/devices'?{devices:[{id:'motor-a',name:'电机',protocol:'modbus_tcp',metrics:['temperature']}]}:path.includes('latest')?{measurement:null,status}: {points:[],from:status.checked_at,to:status.checked_at,limit:1000}}))
  vi.stubGlobal('fetch',fetcher)
  const result=await loadSnapshot(new AbortController().signal)
  expect(result.current).toBeUndefined()
  expect(fetcher.mock.calls.every(([path])=>!path.includes('metric=current'))).toBe(true)
  expect(renderToStaticMarkup(<CurrentPanel current={result.current} unverified={false}/>)).toContain('未提供电流')
})
it('空电流和真实0A不同，使用电流自身采集时间及失败状态',()=>{
  expect(renderToStaticMarkup(<CurrentPanel current={{measurement:null,status}} unverified={false}/>)).toContain('暂无电流样本')
  const reading={measurement:{id:2,device_id:'motor-a',metric:'current',value:0,unit:'A',collected_at:'2026-09-17T00:00:00Z',source_time:null,quality:'good',protocol:'modbus_tcp'},status:{...status,has_data:true,last_attempt_status:'failure' as const}}
  const html=renderToStaticMarkup(<CurrentPanel current={reading} unverified={false}/>)
  expect(html).toContain('0.00')
  expect(html).toContain('最近采集失败')
  expect(html).toContain('2026-09-17T00:00:00Z')
  expect(renderToStaticMarkup(<CurrentPanel current={reading} unverified/>)).toContain('当前电流未能核实')
})

it('电流时间冲突状态未知不能显示未过期的确认结论',()=>{
  const reading={measurement:{id:2,device_id:'motor-a',metric:'current',value:1.23,unit:'A',collected_at:'2026-09-17T00:00:00Z',source_time:null,quality:'good',protocol:'modbus_tcp'},status:{...status,has_data:true,last_attempt_status:'unknown' as const}}
  expect(renderToStaticMarkup(<CurrentPanel current={reading} unverified={false}/>)).toContain('当前电流未能核实')
})

it('四点按自己的检查时间查询历史，旧双点API不请求新指标',async()=>{
  let metrics=['temperature','current','speed','running_state']
  const times:Record<string,string>={temperature:'2026-09-17T00:00:00Z',current:'2026-09-17T00:00:01Z',speed:'2026-09-17T00:00:02Z',running_state:'2026-09-17T00:00:03Z'}
  const paths:string[]=[]
  vi.stubGlobal('fetch',async(path:string)=>{
    paths.push(path)
    const metric=new URL(path,'http://test').searchParams.get('metric')??'temperature'
    return {ok:true,json:async()=>path==='/api/devices'?{devices:[{id:'motor-a',name:'电机',protocol:'modbus_tcp',metrics}]}:path.includes('latest')?{metric,measurement:null,status:{...status,checked_at:times[metric]}}:{points:[],from:times[metric],to:times[metric],limit:1000}}
  })
  const result=await loadSnapshot(new AbortController().signal)
  expect(result.speed?.status.checked_at).toBe(times.speed)
  expect(result.running_state?.history?.to).toBe(times.running_state)
  for(const metric of metrics){
    const history=paths.find(p=>p.includes('history')&&new URL(p,'http://test').searchParams.get('metric')===metric)!
    expect(new URL(history,'http://test').searchParams.get('to')).toBe(times[metric])
  }
  metrics=['temperature','current'];paths.length=0
  const old=await loadSnapshot(new AbortController().signal)
  expect(old.speed).toBeUndefined();expect(old.running_state).toBeUndefined()
  expect(paths.some(p=>p.includes('metric=speed')||p.includes('metric=running_state'))).toBe(false)
})

it('B按设备能力仅查询自己的温度，A数据不进入B快照', async () => {
  const paths: string[] = []
  vi.stubGlobal('fetch', async (path: string) => {
    paths.push(path)
    return { ok: true, json: async () => path === '/api/devices' ? { devices: [
      { id: 'motor-a', name: 'A', protocol: 'modbus_tcp', metrics: ['temperature', 'current', 'speed', 'running_state'] },
      { id: 'motor-b', name: 'B', protocol: 'opcua', metrics: ['temperature'] },
    ] } : path.includes('latest') ? { measurement: null, status, opcua: { communication: 'success', quality: 'bad', eligible: false } } : { points: [], from: status.checked_at, to: status.checked_at, limit: 1000 } }
  })
  const result = await loadSnapshot(new AbortController().signal, 'motor-b')
  expect(result.device.id).toBe('motor-b')
  expect(result.opcua?.quality).toBe('bad')
  expect(result.current).toBeUndefined()
  expect(result.speed).toBeUndefined()
  expect(result.devices).toHaveLength(2)
  expect(paths.filter(p => p !== '/api/devices')).toHaveLength(2)
  expect(paths.filter(p => p !== '/api/devices').every(p => p.includes('/motor-b/'))).toBe(true)
})
