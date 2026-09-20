// 独立临时数据库、独立端口与真实Chrome；只清理本脚本创建的进程。
import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import net from 'node:net'

const root = resolve('..'), python = resolve(root, '.venv/bin/python')
const output = resolve(root, 'docs/verification/sustained-alarms')
mkdirSync(output, { recursive: true })
const temp = mkdtempSync(resolve(tmpdir(), 'sustained-temperature-'))
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
  const [modbusPort, apiPort, webPort] = await Promise.all([port(),port(),port()])
  note(`独立临时库 ${db}; 端口 ${modbusPort}/${apiPort}/${webPort}`)
  runPython('import sys; from storage import open_database,initialize; c=open_database(sys.argv[1]);initialize(c);c.close()')
  let api = start(python,['serve_api.py','--db',db,'--port',String(apiPort)])
  start(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort)],resolve(root,'frontend'),{...process.env,API_PROXY_TARGET:`http://127.0.0.1:${apiPort}`})
  await Promise.all([waitPort(apiPort),waitPort(webPort)])
  const readAlarm = async () => (await fetch(`http://127.0.0.1:${apiPort}/api/devices/motor-a/alarms`)).json()
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
  const page=await browser.newPage({viewport:{width:1440,height:1100},timezoneId:'Asia/Shanghai'})
  page.on('pageerror',e=>pageErrors.push(String(e)))
  page.on('console',m=>{if(m.type()==='error')consoleErrors.push({expected:expectedApiFailure,text:m.text()})})
  await page.goto(`http://127.0.0.1:${webPort}`)
  await waitText(page,'alarm-status','告警规则未启用')
  note('旧库在真实页面显示规则未启用；GET未创建告警表。')
  assert.equal(runPython('import sys,sqlite3; c=sqlite3.connect(sys.argv[1]); print(c.execute("select count(*) from sqlite_master where name=\'temperature_alarms\'").fetchone()[0])'),'0')
  let simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','810'])
  await waitPort(modbusPort)
  let collector=start(python,['collect_temperature.py','--port',String(modbusPort),'--db',db])
  await waitText(page,'alarm-status','超限待确认')
  await page.screenshot({path:resolve(output,'pending.png'),fullPage:true})
  const firstPending=(await readAlarm()).pending
  assert.ok(firstPending)
  collector.kill('SIGSTOP')
  await waitText(page,'alarm-status','当前未知')
  await delay(5000)
  assert.equal((await readAlarm()).total,0)
  note('首次高温显示待确认；暂停采集超过5秒后未自动报警，页面转未知。')
  collector.kill('SIGCONT')
  const deadline=Date.now()+5000
  let resumed
  while(Date.now()<deadline) {
    resumed=await readAlarm()
    if(resumed.pending && resumed.pending.first_exceeded_measurement_id!==firstPending.first_exceeded_measurement_id)break
    await delay(80)
  }
  assert.ok(resumed.pending)
  assert.notEqual(resumed.pending.first_exceeded_measurement_id,firstPending.first_exceeded_measurement_id)
  assert.ok(resumed.pending.elapsed_seconds<2)
  note('无显式失败事件的长间隙：采集恢复后首超限样本更新，累计重置。')
  await stop(collector)
  collector=start(python,['collect_temperature.py','--port',String(modbusPort),'--db',db])
  await waitText(page,'alarm-status','超限待确认')
  await waitText(page,'alarm-status','当前温度告警中')
  const triggered=await readAlarm()
  assert.equal(triggered.active.confirm_seconds,5)
  assert.ok(Date.parse(triggered.active.started_at)-Date.parse(triggered.active.first_exceeded_at)>=4900)
  assert.notEqual(triggered.active.first_exceeded_measurement_id,resumed.pending.first_exceeded_measurement_id)
  note('待确认时重启采集器重新累计；新观测满5秒正式触发，两个时间和样本证据分开。')
  await page.locator('.alarm-history summary').click()
  await delay(2500)
  assert.equal((await readAlarm()).total,1)
  await page.reload()
  await waitText(page,'alarm-status','当前温度告警中')
  await page.locator('.alarm-history summary').click()
  assert.equal((await readAlarm()).total,1)
  await page.screenshot({path:resolve(output,'active-desktop.png'),fullPage:true})
  note('81℃真实采集触发一次；连续高温和刷新页面没有重复创建。')
  await stop(collector)
  await page.route('**/api/devices/motor-a/history?*',async route=>{await delay(6000);await route.continue()})
  await page.reload()
  await page.waitForFunction(()=>document.querySelector('[data-testid="fetched-at"]')?.textContent !== '—')
  assert.equal(await page.getByTestId('alarm-status').textContent(),'当前未知')
  await page.unroute('**/api/devices/motor-a/history?*')
  note('历史接口延迟6秒：整轮完成后告警仍为未知，不将过期latest重新显示为当前已知。')
  await waitText(page,'alarm-status','当前未知')
  assert.equal((await readAlarm()).active.id,1)
  note('停止采集器超过5秒：未知，未解除告警仍为#1。')
  collector=start(python,['collect_temperature.py','--port',String(modbusPort),'--db',db])
  await waitText(page,'alarm-status','当前温度告警中')
  assert.equal((await readAlarm()).total,1)
  note('采集器同库重启，高温仍为同一条告警。')
  await stop(simulator)
  await waitText(page,'attempt','最近一次失败')
  await waitText(page,'alarm-status','当前未知')
  assert.equal((await readAlarm()).active.id,1)
  await page.screenshot({path:resolve(output,'unknown.png'),fullPage:true})
  note('通信失败：当前未知，同时显示未解除及触发81℃证据。')
  simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','780'])
  await waitPort(modbusPort)
  await waitText(page,'temperature','78.0')
  await waitText(page,'alarm-status','当前温度告警中')
  assert.equal((await readAlarm()).active.id,1)
  await stop(simulator)
  simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','779'])
  await waitPort(modbusPort)
  await waitText(page,'alarm-status','当前无未解除告警')
  const recovered=await readAlarm()
  assert.equal(recovered.active,null)
  assert.equal(recovered.history[0].recovery_value,77.9)
  await page.locator('.alarm-history summary').click()
  assert.ok(await page.getByTestId('alarm-history').textContent().then(s=>s.includes('已恢复') && s.includes('77.9')))
  await page.screenshot({path:resolve(output,'recovered.png'),fullPage:true})
  note('78℃保持；77.9℃恢复，历史显示开始/恢复时间、温度和样本编号。')
  await stop(simulator)
  simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','810'])
  await waitPort(modbusPort)
  await waitText(page,'alarm-status','当前温度告警中')
  assert.equal((await readAlarm()).total,2)
  assert.equal((await readAlarm()).active.id,2)
  await page.setViewportSize({width:390,height:844})
  await delay(300)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
  await page.screenshot({path:resolve(output,'narrow.png'),fullPage:true})
  note('恢复后81℃创建#2；390px无横向溢出。')
  expectedApiFailure=true
  await stop(api)
  await waitText(page,'alarm-status','当前未知')
  await waitText(page,'alarm-active','历史快照中有未解除告警')
  await page.screenshot({path:resolve(output,'api-unavailable.png'),fullPage:true})
  note('API停止：告警状态当前未知，旧记录标为历史快照。')
  api=start(python,['serve_api.py','--db',db,'--port',String(apiPort)])
  await waitPort(apiPort)
  await waitText(page,'alarm-status','当前温度告警中')
  assert.equal((await readAlarm()).total,2)
  assert.deepEqual(pageErrors,[])
  assert.deepEqual(consoleErrors.filter(e=>!e.expected),[])
  note(`PASS Chrome ${browser.version()}；无非预期控制台异常；API重启保留两条告警。仅验收M2持续超限这一小步。`)
} catch(error) {
  note(`FAIL: ${error.stack}`)
  process.exitCode=1
} finally {
  if(browser) await browser.close()
  for(const item of children.reverse()) await stop(item.process)
  writeFileSync(resolve(output,'report.txt'),report.join('\n')+'\n')
  writeFileSync(resolve(output,'process-logs.txt'),children.map(i=>i.command+'\n'+i.logs).join('\n\n'))
  rmSync(temp,{recursive:true,force:true})
}
