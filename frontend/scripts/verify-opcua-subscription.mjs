// 独立临时数据库、独立端口与真实Chrome；只清理本脚本创建的进程。
import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import net from 'node:net'

const root = resolve('..'), python = resolve(root, '.venv/bin/python')
const output = resolve(root, 'docs/verification/opcua-subscription')
mkdirSync(output, { recursive: true })
const temp = mkdtempSync(resolve(tmpdir(), 'opcua-subscription-'))
const db = resolve(temp, 'test.sqlite3')
const children = [], consoleErrors = [], pageErrors = [], report = []
let browser, expectedApiFailure = false
const note = (text) => { report.push(text); console.log(text) }
const delay = ms => new Promise(r => setTimeout(r, ms))
const runPython = (code) => execFileSync(python, ['-c', code, db], {cwd:root, encoding:'utf8'}).trim()
const rows = () => JSON.parse(runPython('import sqlite3,sys,json; c=sqlite3.connect(sys.argv[1]); print(json.dumps(c.execute("select id,value,collected_at from measurements order by id").fetchall())); c.close()'))
async function port() { const server = net.createServer(); await new Promise(r => server.listen(0, '127.0.0.1', r)); const p = server.address().port; await new Promise(r => server.close(r)); return p }
function start(command, args, cwd=root, env=process.env) {
  const process = spawn(command, args, {cwd, env, stdio:['ignore','pipe','pipe']})
  const item = {process, command: [command, ...args].join(' '), logs:''}
  children.push(item)
  process.stdout.on('data', b => {item.logs += b})
  process.stderr.on('data', b => {item.logs += b})
  return process
}
async function stop(process) {
  if (process.exitCode !== null || process.signalCode !== null) return
  process.kill('SIGINT')
  await Promise.race([new Promise(r => process.once('exit', r)), delay(5000)])
  if (process.exitCode === null && process.signalCode === null) {process.kill('SIGKILL'); await new Promise(r => process.once('exit', r))}
}
async function waitPort(p) {
  const deadline = Date.now()+15000
  while (Date.now()<deadline) {
    const ready = await new Promise(r => {const s=net.connect(p,'127.0.0.1'); s.on('connect',()=>{s.destroy();r(true)});s.on('error',()=>r(false))})
    if (ready) return
    await delay(80)
  }
  throw new Error(`端口${p}未就绪`)
}
async function waitText(page, testid, value) {
  await page.waitForFunction(({testid,value}) => document.querySelector(`[data-testid="${testid}"]`)?.textContent?.includes(value), {testid,value}, {timeout:15000})
}
try {
  const [modbusPort,uaPort,apiPort,webPort]=await Promise.all([port(),port(),port(),port()])
  note(`临时库${db}；独立端口${modbusPort}/${uaPort}/${apiPort}/${webPort}`)
  start(python,['simulator.py','--port',String(modbusPort),'--raw','653'])
  await waitPort(modbusPort)
  start(python,['collect_temperature.py','--port',String(modbusPort),'--db',db])
  let simulator=start(python,['opcua_simulator.py','--port',String(uaPort),'--value','85','--extra-namespace'])
  await waitPort(uaPort)
  const collector=start(python,['collect_opcua.py','--mode','subscribe','--port',String(uaPort),'--db',db])
  const api=start(python,['serve_api.py','--db',db,'--port',String(apiPort)])
  start(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort)],resolve(root,'frontend'),{...process.env,API_PROXY_TARGET:`http://127.0.0.1:${apiPort}`})
  await Promise.all([waitPort(apiPort),waitPort(webPort)])
  const latest=async(device='motor-b')=> (await fetch(`http://127.0.0.1:${apiPort}/api/devices/${device}/latest`)).json()
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
  const page=await browser.newPage({viewport:{width:1440,height:1100},timezoneId:'Asia/Shanghai'})
  page.on('pageerror',e=>pageErrors.push(String(e)))
  page.on('console',m=>{if(m.type()==='error')consoleErrors.push({expected:expectedApiFailure,text:m.text()})})
  await page.goto(`http://127.0.0.1:${webPort}`)
  await waitText(page,'temperature','65.3');await page.selectOption('#device-selector','motor-b')
  await waitText(page,'opcua-runtime','已订阅');await waitText(page,'opcua-mode','订阅通知')
  await waitText(page,'temperature','85.0');await waitText(page,'alarm-status','当前温度告警中')
  const initial=await latest(),active=initial.alarm.active.id,generation=initial.opcua.runtime.generation
  assert.ok(initial.opcua.runtime.revised.publishing_interval_ms>0)
  assert.ok(initial.opcua.runtime.revised.sampling_interval_ms>0)
  assert.ok(await page.getByTestId('opcua-decision-time').getAttribute('datetime'))
  await page.screenshot({path:resolve(output,'subscribed-desktop.png'),fullPage:true})
  note('真实常值85℃随源时间更新持续通知并触发告警；页面显示订阅模式、世代与实际revised参数。')
  const aBefore=(await latest('motor-a')).measurement.id
  await stop(simulator)
  await waitText(page,'opcua-runtime','等待重连');await waitText(page,'alarm-status','当前未知')
  const broken=await latest()
  assert.equal(broken.alarm.active.id,active);assert.equal(broken.alarm.pending,null);assert.equal(broken.opcua.eligible,false)
  await delay(1500);assert.ok((await latest('motor-a')).measurement.id>aBefore)
  await page.screenshot({path:resolve(output,'reconnecting.png'),fullPage:true})
  note('停止B：断线进入等待重连、pending取消、active保留；A继续采集，不受B影响。')
  simulator=start(python,['opcua_simulator.py','--port',String(uaPort),'--value','85'])
  await waitPort(uaPort);await waitText(page,'opcua-runtime','已订阅');await waitText(page,'opcua-eligibility','可以参与')
  const restored=await latest();assert.ok(restored.opcua.runtime.generation>generation);assert.equal(restored.alarm.active.id,active)
  await delay(1500)
  const duplicates=JSON.parse(runPython('import sqlite3,sys,json; c=sqlite3.connect(sys.argv[1]); print(json.dumps(c.execute("select source_time,count(*) from measurements where device_id=\'motor-b\' group by source_time having count(*)>1").fetchall()))'))
  assert.deepEqual(duplicates,[])
  note('B同端口重启：自动创建新世代/新订阅并恢复，无重复源测量落库、无重复active告警。')
  await stop(simulator)
  simulator=start(python,['opcua_simulator.py','--port',String(uaPort),'--value','70','--quality','bad'])
  await waitPort(uaPort);await waitText(page,'opcua-quality','BadSensorFailure');await waitText(page,'opcua-runtime','已订阅')
  await waitText(page,'opcua-communication','已接收数据通知');await waitText(page,'opcua-eligibility','不可参与')
  assert.equal((await latest()).alarm.active.id,active)
  const badGeneration=(await latest()).opcua.runtime.generation
  await delay(3200)
  const sustainedBad=await latest()
  assert.equal(sustainedBad.opcua.runtime.generation,badGeneration)
  assert.equal(sustainedBad.opcua.runtime.state,'subscribed')
  assert.equal(sustainedBad.opcua.communication,'success')
  assert.equal(await page.getByTestId('temperature').textContent(),'85.0')
  await page.setViewportSize({width:390,height:844});await delay(300)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
  await page.screenshot({path:resolve(output,'bad-narrow.png'),fullPage:true})
  note('持续Bad超过3秒：订阅世代不变、通知正常到达但温度不可用、有效85℃及active保留；390px无溢出。')
  await stop(simulator)
  simulator=start(python,['opcua_simulator.py','--port',String(uaPort),'--value','85','--source-mode','frozen'])
  await waitPort(uaPort);await waitText(page,'opcua-runtime-error','source_notification_gap')
  const silent=await latest();assert.equal(silent.opcua.runtime.state,'subscribed');assert.equal(silent.opcua.eligible,false)
  assert.equal(silent.opcua.communication,'success');assert.equal(silent.alarm.active.id,active)
  await delay(1400)
  const keepalive=await latest();assert.equal(keepalive.measurement.id,silent.measurement.id)
  assert.equal(keepalive.opcua.runtime.generation,silent.opcua.runtime.generation)
  assert.ok(keepalive.opcua.runtime.last_publish_at>silent.opcua.runtime.last_publish_at)
  note('冻结源只剩保活：发布响应继续、订阅不重建；源证据中断不可用、不新增温度或解除active。')
  await stop(simulator)
  simulator=start(python,['opcua_simulator.py','--port',String(uaPort),'--value','77.9'])
  await waitPort(uaPort);await waitText(page,'temperature','77.9');await waitText(page,'alarm-status','当前无未解除告警')
  await stop(collector);await waitText(page,'opcua-runtime','采集已停止');await waitText(page,'opcua-eligibility','不可参与')
  assert.equal(await page.getByTestId('temperature').textContent(),'77.9')
  assert.equal((await latest()).alarm.current,'unknown')
  note('新源77.9℃解除告警；停止采集器后明确显示停止/当前未知，保留有效温度，资源清理不影响A。')
  expectedApiFailure=true;await stop(api);await waitText(page,'opcua-eligibility','当前未知')
  assert.deepEqual(pageErrors,[]);assert.deepEqual(consoleErrors.filter(e=>!e.expected),[])
  note(`PASS Chrome ${browser.version()}，无非预期JS/console错误；不承诺断线补采。`)
} catch(error) {note(`FAIL: ${error.stack}`);process.exitCode=1}
finally {
  if(browser)await browser.close()
  for(const item of children.reverse())await stop(item.process)
  writeFileSync(resolve(output,'report.txt'),report.join('\n')+'\n')
  writeFileSync(resolve(output,'process-logs.txt'),children.map(i=>i.command+'\n'+i.logs).join('\n\n'))
  rmSync(temp,{recursive:true,force:true})
}
