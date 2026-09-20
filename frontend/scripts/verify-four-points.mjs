// 独立临时数据库、独立端口与真实Chrome；只清理本脚本创建的进程。
import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import net from 'node:net'

const root = resolve('..'), python = resolve(root, '.venv/bin/python')
const output = resolve(root, 'docs/verification/four-points')
mkdirSync(output, { recursive: true })
const temp = mkdtempSync(resolve(tmpdir(), 'four-points-'))
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
  const api=start(python,['serve_api.py','--db',db,'--port',String(apiPort)])
  const alarm=async()=> (await fetch(`http://127.0.0.1:${apiPort}/api/devices/motor-a/alarms`)).json()
  start(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort)],resolve(root,'frontend'),{...process.env,API_PROXY_TARGET:`http://127.0.0.1:${apiPort}`})
  await Promise.all([waitPort(apiPort),waitPort(webPort)])
  browser=await chromium.launch({executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true})
  const page=await browser.newPage({viewport:{width:1440,height:1100},timezoneId:'Asia/Shanghai'})
  page.on('pageerror',e=>pageErrors.push(String(e)))
  page.on('console',m=>{if(m.type()==='error')consoleErrors.push({expected:expectedApiFailure,text:m.text()})})
  await page.goto(`http://127.0.0.1:${webPort}`)
  await waitText(page,'speed-status','暂无转速样本')
  await waitText(page,'running_state-status','暂无运行状态样本')
  assert.equal(await page.getByTestId('running_state-value').textContent(),'—')
  note('旧温度库：新指标暂无样本，既不伪造0 rpm，也不伪造停止。')
  await page.route('**/api/devices',async route=>{
    const response=await route.fetch();const data=await response.json();data.devices[0].metrics=['temperature','current'];await route.fulfill({response,json:data})
  })
  await page.reload();await waitText(page,'speed-status','未提供转速');await waitText(page,'running_state-status','未提供运行状态')
  await page.unrouteAll({behavior:'wait'});await page.reload()
  note('旧双点API能力响应：新页面正常加载，未请求不支持的speed/running_state。')
  const simArgs=['simulator.py','--port',String(modbusPort),'--raw','810','--current-raw','123','--speed-raw','1450']
  let simulator=start(python,[...simArgs,'--running-state-raw','1'])
  await waitPort(modbusPort)
  start(python,['collect_temperature.py','--port',String(modbusPort),'--db',db])
  await waitText(page,'running_state-value','运行');await waitText(page,'speed-value','1450');await waitText(page,'alarm-status','超限待确认')
  await stop(simulator)
  simulator=start(python,[...simArgs,'--running-state-raw','2']);await waitPort(modbusPort)
  await waitText(page,'running_state-status','数据校验失败')
  await waitText(page,'running_state-failure','raw=2')
  assert.equal(await page.getByTestId('running_state-value').textContent(),'运行')
  assert.equal((await alarm()).pending,null)
  const frozen=rows();const originalTime=await page.getByTestId('running_state-time').getAttribute('datetime')
  await delay(5500)
  assert.deepEqual(rows(),frozen)
  assert.equal((await alarm()).total,0)
  assert.equal(await page.getByTestId('running_state-time').getAttribute('datetime'),originalTime)
  await page.screenshot({path:resolve(output,'invalid-state.png'),fullPage:true})
  note('有效Modbus响应包含状态2：页面显示数据校验失败及raw=2，保留旧运行/原时间；四测量不新增、pending取消，等候5秒也无告警。')
  await stop(simulator)
  simulator=start(python,[...simArgs,'--running-state-raw','1']);await waitPort(modbusPort)
  await waitText(page,'running_state-status','本次数据有效')
  await waitText(page,'alarm-status','当前温度告警中')
  const rounds=JSON.parse(runPython('import sys,sqlite3,json; c=sqlite3.connect(sys.argv[1]); print(json.dumps(c.execute("select count(*) from measurements where id>1 group by collected_at").fetchall()))'))
  assert.ok(rounds.every(r=>r[0]===4))
  await page.selectOption('#history-metric','speed')
  await page.getByRole('img',{name:/转速曲线/}).waitFor()
  assert.ok(await page.locator('.chart svg').textContent().then(t=>t.includes('rpm')&&!t.includes('℃')))
  await page.screenshot({path:resolve(output,'four-points-desktop.png'),fullPage:true})
  note('恢复有效状态1，重新连续观测5秒触发；每轮四条共享UTC时间，转速曲线使用rpm。')
  await stop(simulator)
  await waitText(page,'running_state-status','通信失败')
  assert.equal(await page.getByTestId('running_state-value').textContent(),'运行')
  await waitText(page,'alarm-status','当前未知')
  note('真正断线：当前未知/通信失败，最后有效运行保留，不改成停止。')
  simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','779','--current-raw','0','--speed-raw','0','--running-state-raw','0'])
  await waitPort(modbusPort)
  await waitText(page,'speed-value','0');await waitText(page,'running_state-value','停止');await waitText(page,'running_state-status','本次数据有效')
  assert.equal(await page.getByTestId('current-value').textContent(),'0.00')
  await waitText(page,'alarm-status','当前无未解除告警')
  await page.selectOption('#history-metric','running_state')
  await page.getByRole('region',{name:'运行状态历史记录'}).waitFor()
  const historyText=await page.locator('.running-history').textContent()
  assert.ok(historyText.includes('运行')&&historyText.includes('停止')&&historyText.includes('原始值'))
  assert.equal(await page.locator('.chart svg').count(),0)
  await page.setViewportSize({width:390,height:844});await delay(300)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
  await page.screenshot({path:resolve(output,'narrow-state-history.png'),fullPage:true})
  note('有效0：显示0 rpm、0.00A、停止；77.9℃恢复告警；运行状态用真实记录表，390px无溢出。')
  expectedApiFailure=true;await stop(api)
  await waitText(page,'running_state-status','当前未知')
  assert.equal(await page.getByTestId('running_state-value').textContent(),'停止')
  assert.deepEqual(pageErrors,[]);assert.deepEqual(consoleErrors.filter(e=>!e.expected),[])
  note(`PASS Chrome ${browser.version()}，无非预期JS/console错误；本次只验收转速＋运行状态。`)
} catch(error) {note(`FAIL: ${error.stack}`);process.exitCode=1}
finally {
  if(browser)await browser.close()
  for(const item of children.reverse())await stop(item.process)
  writeFileSync(resolve(output,'report.txt'),report.join('\n')+'\n')
  writeFileSync(resolve(output,'process-logs.txt'),children.map(i=>i.command+'\n'+i.logs).join('\n\n'))
  rmSync(temp,{recursive:true,force:true})
}
