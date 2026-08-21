# Card Duel Web

Card Duel 的标准 Next.js 浏览器客户端。页面只发送玩家动作；房间、回合、伤害、
资源和卡牌效果均由独立的 Python WebSocket 服务权威结算。

## 本地开发

需要 Node.js 20.9+。先在项目根目录启动后端：

```bash
.venv/bin/card-duel-web
```

再启动前端：

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3000`。本地默认连接
`ws://127.0.0.1:8000/ws`，也可在入口页修改地址。

## 环境变量

```dotenv
# 可选：部署后的默认 WebSocket 后端；必须使用浏览器可访问的 ws:// 或 wss://
NEXT_PUBLIC_CARD_DUEL_WS_URL=wss://game-api.example.com/ws

# 可选：非 Vercel 平台设置此项，用于生成分享图片的绝对 URL
NEXT_PUBLIC_SITE_URL=https://game.example.com
```

HTTPS 前端必须连接 `wss://` 后端，否则浏览器会阻止混合内容。

## 检查

```bash
npm run lint
npm test
npm run build
```

生产构建输出为标准 `.next/`，首页会被静态预渲染。

## 部署前端

任何支持 Next.js 16 / Node.js 20.9+ 的平台均可部署：

- 项目根目录：`frontend`
- 安装命令：`npm install`（或按 `pnpm-lock.yaml` 使用 `pnpm install`）
- 构建命令：`npm run build`
- 启动命令（自托管平台）：`npm run start`
- 构建产物：Next.js 默认 `.next`，不要手动覆盖输出目录

在 Vercel 中导入整个 Git 仓库后，将 **Root Directory** 设置为 `frontend`，
Framework Preset 选择 **Next.js**，其余构建项保持自动检测即可。然后在项目的
Environment Variables 中设置 `NEXT_PUBLIC_CARD_DUEL_WS_URL` 并重新部署。

## 部署后端

`card-duel-web` 使用内存房间和长连接，必须部署到能长期运行 Python ASGI 进程的
服务；启动命令为：

```bash
uvicorn card_duel.web.app:app --host 0.0.0.0 --port "$PORT"
```

后端需要 TLS 终止并对外提供 `wss://<域名>/ws`。不要把当前内存房间后端当成
无状态函数拆分到多个实例，否则玩家可能连接到不同房间进程。
