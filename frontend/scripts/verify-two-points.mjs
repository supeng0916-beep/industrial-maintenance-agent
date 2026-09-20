// 独立临时数据库、独立端口与真实Chrome；只清理本脚本创建的进程。
import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import net from 'node:net'

const root = resolve('..'), python = resolve(root, '.venv/bin/python')
const output = resolve(root, 'docs/verification/two-points')
mkdirSync(output, { recursive: true })
const temp = mkdtempSync(resolve(tmpdir(), 'two-points-'))
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
  const [modbusPort,apiPort,webPort]=await Promise.all([port(),port(),port()])
  note(`临时库${db}；独立端口${modbusPort}/${apiPort}/${webPort}`)
  runPython('import sys; from storage import open_database,initialize,save_measurement; from datetime import datetime,timezone; c=open_database(sys.argv[1]); initialize(c); save_measurement(c,65.3,datetime.now(timezone.utc).isoformat(timespec="microseconds")); c.close()')
  let api=start(python,['serve_api.py','--db',db,'--port',String(apiPort)])
  start(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort)],resolve(root,'frontend'),{...process.env,API_PROXY_TARGET:`http://127.0.0.1:${apiPort}`})
  await Promise.all([waitPort(apiPort),waitPort(webPort)])
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
  const page=await browser.newPage({viewport:{width:1440,height:1100},timezoneId:'Asia/Shanghai'})
  page.on('pageerror',e=>pageErrors.push(String(e)))
  page.on('console',m=>{if(m.type()==='error')consoleErrors.push({expected:expectedApiFailure,text:m.text()})})
  await page.goto(`http://127.0.0.1:${webPort}`)
  await waitText(page,'current-status','暂无电流样本')
  assert.equal(await page.getByTestId('current-value').textContent(),'—')
  note('新API＋旧温度库：温度65.3，电流暂无样本且显示—，无伪0。')
  await page.route('**/api/devices',async route=>{
    const response=await route.fetch();const data=await response.json();data.devices[0].metrics=['temperature'];await route.fulfill({response,json:data})
  })
  await page.reload();await waitText(page,'current-status','未提供电流')
  await page.selectOption('#history-metric','current')
  assert.ok(await page.locator('.empty-chart').textContent().then(t=>t.includes('未提供电流')))
  await page.screenshot({path:resolve(output,'old-api.png'),fullPage:true})
  await page.unroute('**/api/devices');await page.reload()
  note('旧API能力响应兼容：仅temperature时仍显示温度，电流未提供，页面无异常。')
  let simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','810','--current-raw','123'])
  await waitPort(modbusPort)
  const collector=start(python,['collect_temperature.py','--port',String(modbusPort),'--db',db])
  await waitText(page,'temperature','81.0');await waitText(page,'current-value','1.23')
  await waitText(page,'alarm-status','当前温度告警中')
  const rounds=JSON.parse(runPython('import sys,sqlite3,json; c=sqlite3.connect(sys.argv[1]); print(json.dumps(c.execute("select collected_at,group_concat(metric),count(*) from measurements where id>1 and metric in (\'temperature\',\'current\') group by collected_at").fetchall()))'))
  assert.ok(rounds.length>=6)
  assert.ok(rounds.every(r=>r[1]==='temperature,current' && r[2]===2))
  note('批量采集两个metric每轮同一个UTC时间；温度观测满5秒后告警，电流1.23A仅观测。')
  await page.selectOption('#history-metric','current')
  await page.getByRole('img',{name:/电流曲线/}).waitFor()
  assert.ok(await page.locator('.chart svg').textContent().then(t=>t.includes('A')&&!t.includes('℃')))
  await page.screenshot({path:resolve(output,'current-desktop.png'),fullPage:true})
  await page.selectOption('#history-metric','temperature')
  await page.getByRole('img',{name:/温度曲线/}).waitFor()
  assert.ok(await page.locator('.chart svg').textContent().then(t=>t.includes('℃')))
  await stop(simulator)
  await waitText(page,'current-status','最近采集失败')
  await waitText(page,'attempt','最近一次失败')
  const originalTime=await page.getByTestId('current-time').getAttribute('datetime')
  const frozen=rows()
  await delay(2500)
  assert.deepEqual(rows(),frozen)
  assert.equal(await page.getByTestId('current-value').textContent(),'1.23')
  assert.equal(await page.getByTestId('current-time').getAttribute('datetime'),originalTime)
  await waitText(page,'alarm-status','当前未知')
  note('通信中断：两个指标失败、原值与原时间保留；无新测量，温度告警未解除。')
  simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','779','--current-raw','234'])
  await waitPort(modbusPort)
  await waitText(page,'temperature','77.9');await waitText(page,'current-value','2.34')
  await waitText(page,'alarm-status','当前无未解除告警')
  await page.selectOption('#history-metric','current')
  await page.setViewportSize({width:390,height:844});await delay(300)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
  await page.screenshot({path:resolve(output,'narrow.png'),fullPage:true})
  note('恢复：[779,234]→77.9℃/2.34A，温度告警恢复；电流独立A轴，390px无横向溢出。')
  expectedApiFailure=true;await stop(api)
  await waitText(page,'current-status','当前电流未能核实')
  assert.equal(await page.getByTestId('current-value').textContent(),'2.34')
  note('API停止：旧电流保留，当前未能核实。')
  assert.deepEqual(pageErrors,[]);assert.deepEqual(consoleErrors.filter(e=>!e.expected),[])
  note(`PASS Chrome ${browser.version()}：仅完成M2温度＋电流这一小步。`)
} catch(error) {
  note(`FAIL: ${error.stack}`);process.exitCode=1
} finally {
  if(browser)await browser.close()
  for(const item of children.reverse())await stop(item.process)
  writeFileSync(resolve(output,'report.txt'),report.join('\n')+'\n')
  writeFileSync(resolve(output,'process-logs.txt'),children.map(i=>i.command+'\n'+i.logs).join('\n\n'))
  rmSync(temp,{recursive:true,force:true})
}
