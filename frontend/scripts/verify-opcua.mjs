// 独立临时数据库、独立端口与真实Chrome；只清理本脚本创建的进程。
import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import net from 'node:net'

const root = resolve('..'), python = resolve(root, '.venv/bin/python')
const output = resolve(root, 'docs/verification/opcua-motor-b')
mkdirSync(output, { recursive: true })
const temp = mkdtempSync(resolve(tmpdir(), 'opcua-motor-b-'))
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
  start(python,['collect_opcua.py','--port',String(uaPort),'--db',db])
  const api=start(python,['serve_api.py','--db',db,'--port',String(apiPort)])
  start(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort)],resolve(root,'frontend'),{...process.env,API_PROXY_TARGET:`http://127.0.0.1:${apiPort}`})
  await Promise.all([waitPort(apiPort),waitPort(webPort)])
  const latest=async()=> (await fetch(`http://127.0.0.1:${apiPort}/api/devices/motor-b/latest`)).json()
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
  const page=await browser.newPage({viewport:{width:1440,height:1100},timezoneId:'Asia/Shanghai'})
  page.on('pageerror',e=>pageErrors.push(String(e)))
  page.on('console',m=>{if(m.type()==='error')consoleErrors.push({expected:expectedApiFailure,text:m.text()})})
  await page.goto(`http://127.0.0.1:${webPort}`)
  await waitText(page,'temperature','65.3');await waitText(page,'speed-value','1450')
  await page.selectOption('#device-selector','motor-b')
  await waitText(page,'temperature','85.0');await waitText(page,'opcua-eligibility','可以参与')
  assert.equal(await page.getByTestId('speed-value').count(),0)
  assert.deepEqual(await page.locator('#history-metric option').allTextContents(),['温度（℃）'])
  await waitText(page,'alarm-status','当前温度告警中')
  const active=(await latest()).alarm.active.id
  await page.screenshot({path:resolve(output,'good-desktop.png'),fullPage:true})
  note('A四点与B温度共库并发；B按URI解析变动的namespace index，85℃持续触发，B仅温度历史/告警。')
  async function replace(args){await stop(simulator);simulator=start(python,['opcua_simulator.py','--port',String(uaPort),...args]);await waitPort(uaPort)}
  const before=(await latest()).measurement
  await replace(['--value','70','--quality','bad'])
  await waitText(page,'opcua-quality','BadSensorFailure');await waitText(page,'opcua-communication','读取成功')
  await waitText(page,'opcua-eligibility','不可参与');await waitText(page,'alarm-status','当前未知')
  assert.equal((await latest()).measurement.id,before.id)
  assert.equal((await latest()).alarm.active.id,active)
  assert.equal(await page.getByTestId('temperature').textContent(),'85.0')
  await waitText(page,'opcua-raw','null')
  await page.screenshot({path:resolve(output,'bad-quality.png'),fullPage:true})
  note('Bad低值：通信仍成功，真实线上值null仅作诊断；85℃有效温度保留，active未解除，当前未知。')
  await replace(['--value','70','--quality','uncertain'])
  await waitText(page,'opcua-quality','UncertainSensorNotAccurate')
  assert.equal((await latest()).alarm.active.id,active)
  await replace(['--value','70','--source-mode','missing'])
  await waitText(page,'opcua-source-state','设备未提供源时间，测量新鲜度无法核实')
  const missing=await latest();assert.equal(missing.opcua.diagnostic.source_time,null);assert.ok(missing.opcua.diagnostic.received_at)
  assert.equal(missing.measurement.id,before.id);assert.equal(missing.alarm.active.id,active)
  await page.setViewportSize({width:390,height:844});await delay(300)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
  await page.screenshot({path:resolve(output,'missing-narrow.png'),fullPage:true})
  note('Uncertain及缺源均拒绝；缺源显示明确中文说明、source=null，接收时间独立；390px无横向溢出。')
  for(const [mode,text] of [['stale','源测量已过期'],['future','源时间在未来']]){
    await replace(['--value','70','--source-mode',mode]);await waitText(page,'opcua-source-state',text)
    assert.equal((await latest()).measurement.id,before.id);assert.equal((await latest()).alarm.active.id,active)
  }
  await replace(['--value','85','--source-mode','frozen'])
  await waitText(page,'opcua-source-state','重复源时间')
  assert.equal((await latest()).opcua.eligible,false)
  note('过旧、未来、冻结重复源时间均不可用；没有用新接收时间伪装新测量。')
  await replace(['--value','77.9'])
  await waitText(page,'temperature','77.9');await waitText(page,'alarm-status','当前无未解除告警')
  // 延迟B响应后切回A：被取消的旧设备轮询不得覆盖新设备快照。
  await page.selectOption('#device-selector','motor-a');await waitText(page,'temperature','65.3')
  await page.route('**/api/devices/motor-b/latest',async route=>{await delay(1200);await route.continue().catch(()=>{})})
  await page.selectOption('#device-selector','motor-b')
  assert.equal(await page.getByTestId('temperature').textContent(),'—')
  await delay(200);await page.selectOption('#device-selector','motor-a')
  await waitText(page,'temperature','65.3');await delay(1500)
  assert.equal(await page.getByTestId('temperature').textContent(),'65.3')
  await page.unrouteAll({behavior:'wait'})
  await page.selectOption('#device-selector','motor-b');await waitText(page,'temperature','77.9')
  note('有效新源77.9℃解除B告警；A保持65.3℃；延迟响应期间快速切换不串设备快照。')
  await stop(simulator);await waitText(page,'opcua-communication','通信失败')
  assert.equal(await page.getByTestId('temperature').textContent(),'77.9')
  expectedApiFailure=true;await stop(api);await waitText(page,'opcua-eligibility','当前未知')
  assert.equal(await page.getByTestId('temperature').textContent(),'77.9')
  assert.deepEqual(pageErrors,[]);assert.deepEqual(consoleErrors.filter(e=>!e.expected),[])
  note(`PASS Chrome ${browser.version()}，无非预期JS/console错误；只验收M3主动读第一步。`)
} catch(error) {note(`FAIL: ${error.stack}`);process.exitCode=1}
finally {
  if(browser)await browser.close()
  for(const item of children.reverse())await stop(item.process)
  writeFileSync(resolve(output,'report.txt'),report.join('\n')+'\n')
  writeFileSync(resolve(output,'process-logs.txt'),children.map(i=>i.command+'\n'+i.logs).join('\n\n'))
  rmSync(temp,{recursive:true,force:true})
}
