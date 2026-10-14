const resp = await fetch('http://127.0.0.1:9222/json')
const pages = await resp.json()
const extPage = pages.find(p => p.url && p.url.includes('chrome://extensions'))

if (!extPage) {
  console.log('未找到扩展页')
  process.exit(1)
}

const ws = new WebSocket(extPage.webSocketDebuggerUrl)
await new Promise(r => ws.onopen = r)

function sendCdp(method, params = {}) {
  return new Promise((resolve) => {
    const id = Math.floor(Math.random() * 100000)
    const handler = (evt) => {
      const msg = JSON.parse(evt.data)
      if (msg.id === id) {
        ws.removeEventListener('message', handler)
        resolve(msg.result)
      }
    }
    ws.addEventListener('message', handler)
    ws.send(JSON.stringify({ id, method, params }))
  })
}

// 在扩展页面里点击我们插件的 reload 按钮
const res = await sendCdp('Runtime.evaluate', {
  expression: `(() => {
    const manager = document.querySelector('extensions-manager');
    const viewManager = manager?.shadowRoot?.querySelector('#viewManager');
    const itemList = viewManager?.querySelector('extensions-item-list');
    const items = itemList?.shadowRoot?.querySelectorAll('extensions-item') || [];
    
    let clicked = false;
    let targetName = '';
    for (const item of items) {
      const name = item.shadowRoot?.querySelector('#name')?.textContent;
      if (name && (name.includes('公考') || name.includes('排版') || name.includes('gongkao'))) {
        targetName = name;
        if (typeof item.onReloadClick_ === 'function') {
          item.onReloadClick_();
          clicked = true;
          break;
        }
        const reloadBtn = item.shadowRoot?.querySelector('#dev-reload-button');
        if (reloadBtn) {
          reloadBtn.click();
          clicked = true;
          break;
        }
      }
    }
    return { clicked, targetName, totalItems: items.length };
  })()`,
  returnByValue: true
})

console.log('扩展重载结果:', res.result.value)
ws.close()
