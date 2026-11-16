import { test, expect } from '@playwright/test'
import { archive, file, workflow } from './fixtures'
import { readFileSync } from 'node:fs'

function fixtures(){
  const a=workflow('A','MISSING')
  a.nodes[0]!.credentials={synthetic:{id:'FAKE_REFERENCE'}}
  a.nodes[0]!.parameters={filePath:'/synthetic/local.txt'}
  const b=workflow('B','A');const c=workflow('C','MISSING');const d=workflow('D','B',true)
  return {a,b,c,d}
}
async function scan(page:import('@playwright/test').Page,zip=false){
  const f=fixtures();await page.goto('/upload')
  await page.getByTestId('file-input').setInputFiles(zip?[{name:'fabricated.zip',mimeType:'application/zip',buffer:archive({'A.json':f.a,'B.json':f.b,'C.json':f.c,'D.json':f.d})}]:[file(f.a,'A.json'),file(f.b,'B.json'),file(f.c,'C.json'),file(f.d,'D.json')])
  const response=page.waitForResponse(r=>r.url().endsWith('/api/v1/scans')&&r.request().method()==='POST')
  await page.getByRole('button',{name:'确认上传并扫描'}).click()
  const r=await response;expect(r.status()).toBe(200)
  await expect(page.getByText('扫描完成',{exact:true})).toBeVisible();return r.json()
}
test('REAL production: findings, three groupings, Chinese rules, node details and downloads',async({page})=>{
  const data=await scan(page)
  expect(data.diagnostics.statistics.unresolved_reference_count).toBe(2)
  expect(data.diagnostics.statistics.unresolved_target_count).toBe(1)
  expect(data.diagnostics.statistics.dynamic_dependency_count).toBe(1)
  await expect(page.getByRole('heading',{name:'统计口径'})).toBeVisible()
  await page.screenshot({path:'optimization-test-results/01-overview.png'})
  for(const mode of ['workflow','node','rule']){await page.getByLabel('分组方式').selectOption(mode);await expect(page.locator('[data-testid=finding]')).not.toHaveCount(0)}
  await page.getByLabel('分组方式').selectOption('workflow')
  await page.locator('.finding-group').first().screenshot({path:'optimization-test-results/02-workflow-groups.png'})
  await page.getByLabel('规则编号',{exact:true}).selectOption('WF010')
  await expect(page.getByText('凭证引用需要重新配置',{exact:true}).first()).toBeVisible()
  await page.getByRole('button',{name:'查看发现详情'}).first().click()
  const detail=page.getByRole('dialog',{name:'诊断详情'})
  await expect(detail).toContainText('FND-');await expect(detail).toContainText('n8n-nodes-base.manualTrigger')
  await detail.screenshot({path:'optimization-test-results/03-finding-detail.png'})
  await detail.getByRole('button',{name:'关闭详情'}).click()
  for(const rule of ['WF010','WF013']){
    await page.getByLabel('规则编号',{exact:true}).selectOption(rule)
    await page.getByRole('button',{name:'查看规则 '+rule}).first().click()
    const drawer=page.getByRole('dialog',{name:'规则说明'});await expect(drawer).toContainText('静态分析局限')
    await drawer.screenshot({path:'optimization-test-results/'+(rule==='WF010'?'04-WF010':'05-WF013')+'.png'})
    await drawer.getByRole('button',{name:'关闭详情'}).click()
  }
  await page.getByRole('button',{name:'查看发现详情'}).first().click()
  await page.getByRole('link',{name:'定位工作流与节点'}).click()
  await expect(page.locator('.selected-node')).toHaveCount(1)
  await page.getByRole('link',{name:'下载与预览',exact:true}).click()
  for(const format of ['text','json','markdown','html']){
    const [download]=await Promise.all([page.waitForEvent('download'),page.getByRole('button',{name:'下载 '+format.toUpperCase(),exact:true}).click()])
    const content=readFileSync((await download.path())!,'utf8');expect(content).toContain('FND-');expect(content).not.toContain('FAKE_REFERENCE')
  }
})
test('REAL ZIP production: unresolved references match graph, edge evidence, path highlighting and minimap',async({page})=>{
  await scan(page,true);await page.getByRole('link',{name:'依赖关系',exact:true}).click()
  await expect(page.locator('.vue-flow__node')).toHaveCount(5)
  await expect(page.locator('.vue-flow__edge')).toHaveCount(3)
  await expect(page.getByTestId('unresolved')).toHaveCount(2)
  await expect(page.getByLabel('图例')).toBeVisible();await expect(page.getByLabel('图形缩略图')).toBeVisible()
  await page.locator('.graph-panel').screenshot({path:'optimization-test-results/06-cross-workflow-graph.png'})
  await page.getByLabel('未解析依赖清单').scrollIntoViewIfNeeded()
  await page.getByLabel('未解析依赖清单').screenshot({path:'optimization-test-results/07-unresolved-list.png'})
  await page.getByRole('button',{name:'定位引用',exact:true}).first().click()
  await expect(page.getByRole('heading',{name:'选中项详情'})).toBeVisible()
  await expect(page.getByLabel('图选中项详情')).toContainText('关联诊断 · 2')
  await page.getByRole('button',{name:'关闭',exact:true}).click()
  await page.locator('.vue-flow__node').first().click()
  await page.getByLabel('图选中项详情').screenshot({path:'optimization-test-results/08-workflow-details.png'})
  await page.getByRole('button',{name:'查看上游依赖'}).click();await expect(page.locator('.graph-muted')).not.toHaveCount(0)
  await page.getByRole('button',{name:'查看下游依赖'}).click();await page.getByRole('button',{name:'查看完整依赖路径'}).click()
  await page.getByRole('button',{name:'清除高亮'}).click();await expect(page.locator('.graph-muted')).toHaveCount(0)
  await page.getByRole('button',{name:'关闭',exact:true}).click()
  await page.locator('.vue-flow__edge').first().click({force:true})
  await expect(page.getByLabel('图选中项详情')).toContainText('证据位置')
})
