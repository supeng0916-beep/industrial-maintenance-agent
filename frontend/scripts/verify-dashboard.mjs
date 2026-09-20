// 独立临时数据库、独立端口与真实Chrome；只清理本脚本创建的进程。
import { chromium } from '@playwright/test'
import assert from 'node:assert/strict'
import { spawn, execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'
import net from 'node:net'

const root = resolve('..'), python = resolve(root, '.venv/bin/python')
const output = resolve(root, 'docs/verification/dashboard')
mkdirSync(output, { recursive: true })
const temp = mkdtempSync(resolve(tmpdir(), 'temperature-dashboard-'))
const db = resolve(temp, 'test.sqlite3')
const children = [], consoleErrors = [], pageErrors = [], report = []
let browser, expectedApiFailure = false
const note = (text) => { report.push(text); console.log(text) }
const delay = ms => new Promise(r => setTimeout(r, ms))
const runPython = (code) => execFileSync(python, ['-c', code, db], {cwd:root, encoding:'utf8'}).trim()
const rows = () => JSON.parse(runPython('import sqlite3,sys,json; c=sqlite3.connect(sys.argv[1]); print(json.dumps(c.execute("select id,value,collected_at from measurements where metric=\'temperature\' order by id").fetchall())); c.close()'))
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
  note(`环境 Node ${process.version}; Chrome /Applications/Google Chrome.app; ports ${modbusPort}/${apiPort}/${webPort}; 临时库 ${db}`)
  runPython('import sys; from contextlib import closing; from storage import open_database,initialize; c=open_database(sys.argv[1]);initialize(c);c.close()')
  let api = start(python, ['serve_api.py','--db',db,'--port',String(apiPort)])
  start(process.execPath, ['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(webPort)], resolve(root,'frontend'), {...process.env, API_PROXY_TARGET:`http://127.0.0.1:${apiPort}`})
  await Promise.all([waitPort(apiPort),waitPort(webPort)])
  browser = await chromium.launch({executablePath:process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless:true})
  note(`浏览器版本 ${browser.version()}`)
  const context = await browser.newContext({viewport:{width:1440,height:1050}, timezoneId:'Asia/Shanghai'})
  function observe(page) {
    page.on('pageerror', e=>pageErrors.push(String(e)))
    page.on('console', m=> {if(m.type()==='error') consoleErrors.push({expected:expectedApiFailure,text:m.text()})})
  }
  const page = await context.newPage(); observe(page)
  await page.goto(`http://127.0.0.1:${webPort}`)
  await waitText(page,'freshness','暂无温度样本')
  assert.equal(await page.getByTestId('temperature').textContent(),'—')
  await page.screenshot({path:resolve(output,'empty.png'),fullPage:true})
  note('真实浏览器：空库显示无样本和—，没有伪造0。')
  let simulator = start(python,['simulator.py','--port',String(modbusPort)])
  await waitPort(modbusPort)
  start(python,['collect_temperature.py','--port',String(modbusPort),'--db',db])
  await waitText(page,'temperature','65.3')
  await page.locator('.chart svg').waitFor()
  await page.screenshot({path:resolve(output,'desktop.png'),fullPage:true})
  note('653 → 页面65.3℃，原时间、本地时间、曲线SVG均已加载。')
  const baselineStart=rows().length
  await delay(4200)
  const baselineDelta=rows().length-baselineStart
  const second=await context.newPage();observe(second)
  await second.goto(`http://127.0.0.1:${webPort}`)
  await waitText(second,'temperature','65.3')
  const doubleStart=rows().length
  await second.reload();await waitText(second,'temperature','65.3')
  await delay(4200)
  const doubleDelta=rows().length-doubleStart
  assert.ok(baselineDelta>=3 && baselineDelta<=6,baselineDelta)
  assert.ok(doubleDelta>=3 && doubleDelta<=6,doubleDelta)
  const recent=rows().slice(-5).map(r=>Date.parse(r[2]))
  assert.ok(recent.slice(1).every((t,i)=>t-recent[i]>850))
  note(`单页4.2秒新增${baselineDelta}条；第二页面+刷新后的约4.2秒新增${doubleDelta}条；相邻采样仍约1秒，未翻倍。`)
  await second.close()
  await stop(simulator)
  await waitText(page,'attempt','最近一次失败')
  await waitText(page,'freshness','数据已过期')
  const frozen=await page.getByTestId('sample-time').getAttribute('datetime')
  const frozenRows=rows()
  await delay(2300)
  assert.equal(await page.getByTestId('sample-time').getAttribute('datetime'),frozen)
  assert.deepEqual(rows(),frozenRows)
  assert.equal(await page.getByTestId('temperature').textContent(),'65.3')
  await page.screenshot({path:resolve(output,'stale.png'),fullPage:true})
  note(`停模拟器：失败+过期明显；温度65.3和原时间${frozen}保留，测量数${frozenRows.length}不变。`)
  const changedAt=performance.now()
  simulator=start(python,['simulator.py','--port',String(modbusPort),'--raw','728'])
  await waitPort(modbusPort)
  await waitText(page,'temperature','72.8')
  const latency=performance.now()-changedAt
  note(`从启动728模拟器（含启动耗时）到页面72.8：${latency.toFixed(0)}ms。`)
  assert.ok(rows().some(r=>r[1]===72.8))
  await page.screenshot({path:resolve(output,'recovered.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844})
  await delay(300)
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth))
  await page.screenshot({path:resolve(output,'narrow.png'),fullPage:true})
  note('390px窄屏无横向溢出，卡片与图表正常显示。')
  expectedApiFailure=true
  await stop(api)
  await waitText(page,'freshness','当前状态未能核实')
  const saved=await page.getByTestId('sample-time').getAttribute('datetime')
  assert.equal(await page.getByTestId('temperature').textContent(),'72.8')
  assert.ok((await page.getByTestId('freshness').getAttribute('class')).includes('neutral'))
  assert.notEqual(await page.getByTestId('fetched-at').textContent(),'—')
  await delay(2300)
  assert.equal(await page.getByTestId('sample-time').getAttribute('datetime'),saved)
  await page.screenshot({path:resolve(output,'api-unavailable.png'),fullPage:true})
  note('后端停止：保留72.8及原时间，状态变未核实；前端最后获取成功时间可见。')
  const preserved=rows()
  api=start(python,['serve_api.py','--db',db,'--port',String(apiPort)])
  await waitPort(apiPort)
  await waitText(page,'freshness','数据未过期')
  assert.deepEqual(rows().slice(0,preserved.length),preserved)
  expectedApiFailure=false
  note(`后端同库重启：页面自动恢复，原${preserved.length}条历史逐字段保留。`)
  assert.deepEqual(pageErrors,[])
  const unexpected=consoleErrors.filter(e=>!e.expected)
  assert.deepEqual(unexpected,[])
  note(`控制台：未捕获JS异常0，非故障注入期间console.error为0；主动停后端期间网络错误${consoleErrors.length}条（预期）。`)
  note('PASS：M1功能链路验收完成；学习者亲自理解/修改验收未代为完成。')
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
