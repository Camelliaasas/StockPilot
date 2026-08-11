"""用 Edge CDP 打开看板并截图"""
import json, base64, time
import urllib.request
import websocket

# 1. 创建新标签页导航到看板
req = urllib.request.Request(
    'http://127.0.0.1:9222/json/new?http://127.0.0.1:5521',
    method='PUT')
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        tab = json.loads(r.read())
except Exception:
    # 备用：列出标签页找
    with urllib.request.urlopen('http://127.0.0.1:9222/json', timeout=10) as r:
        tabs = json.loads(r.read())
    tab = tabs[0]
tab_id = tab['id']
ws_url = tab['webSocketDebuggerUrl']
print('标签页:', tab.get('url', '')[:60])

# 2. 连接 WebSocket
ws = websocket.create_connection(ws_url, timeout=30)

def cmd(method, params=None):
    global msg_id
    msg_id += 1
    ws.send(json.dumps({'id': msg_id, 'method': method, 'params': params or {}}))
    while True:
        r = json.loads(ws.recv())
        if r.get('id') == msg_id:
            return r

msg_id = 0
# 3. 等待加载
time.sleep(6)
# 4. 截图
r = cmd('Page.captureScreenshot', {'format': 'png'})
data = base64.b64decode(r['result']['data'])
with open('C:/Users/23643/src_workflow/stock_predict/screenshot_dashboard.png', 'wb') as f:
    f.write(data)
print('✅ 截图保存: screenshot_dashboard.png', len(data), 'bytes')
ws.close()
