# 部署指南

Card Duel 由两个独立服务组成：

```text
浏览器 → Next.js 前端 → wss:// 后端/ws → FastAPI 权威对局
```

前端可以部署到任何支持 Next.js 16 或静态 Next.js 构建的平台；后端必须运行在
支持长期 Python ASGI 进程和 WebSocket 的服务上。

## 1. 部署后端

要求 Python 3.10+。平台构建命令：

```bash
python -m pip install -e .
```

平台启动命令：

```bash
uvicorn card_duel.web.app:app --host 0.0.0.0 --port "$PORT"
```

部署后确认：

```bash
curl https://game-api.example.com/health
```

应返回 `status: ok`，WebSocket 地址则为：

```text
wss://game-api.example.com/ws
```

当前房间保存在进程内存中，因此部署时请使用**单个实例/副本**。在加入共享房间
存储和断线恢复令牌之前，不要开启多实例负载均衡或无状态函数扩缩容，否则两名
玩家可能被路由到不同进程。

## 2. 部署前端

前端目录为 `frontend/`，要求 Node.js 20.9+。

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm run lint
pnpm test
pnpm run build
```

平台配置：

| 配置 | 值 |
| --- | --- |
| Root Directory | `frontend` |
| Framework | `Next.js` |
| Install Command | 自动检测，或 `pnpm install --frozen-lockfile` |
| Build Command | `pnpm run build` |
| Output Directory | 使用 Next.js 默认值，不覆盖 |
| Node.js | 20.9 或更高 |

必须配置的生产环境变量：

```dotenv
NEXT_PUBLIC_CARD_DUEL_WS_URL=wss://game-api.example.com/ws
```

非 Vercel 平台建议再配置站点地址，用于生成正确的 Open Graph 图片 URL：

```dotenv
NEXT_PUBLIC_SITE_URL=https://game.example.com
```

Vercel 会提供 `VERCEL_PROJECT_PRODUCTION_URL`，代码会自动使用它，无需额外填写
`NEXT_PUBLIC_SITE_URL`。

## 3. Vercel 面板参数

1. 将整个仓库推送到 GitHub、GitLab 或 Bitbucket。
2. 在 Vercel 中导入仓库。
3. 将 **Root Directory** 设置为 `frontend`。
4. 确认 Framework Preset 为 **Next.js**，其余构建参数保持自动检测。
5. 添加 `NEXT_PUBLIC_CARD_DUEL_WS_URL`，值为已部署后端的 `wss://.../ws`。
6. 点击部署；以后推送对应分支会自动重新构建。

Vercel 只部署前端。当前 Python 权威房间服务应部署在长期运行的 ASGI 平台，
不应与前端一起改造成短生命周期、可任意扩缩容的函数。

## 4. 上线自检

1. 打开前端，服务器地址应自动显示生产 `wss://` 地址。
2. 建立连接后创建房间，确认生成 6 位房间号。
3. 在另一浏览器加入房间，双方选角并准备。
4. 确认手牌仅本人可见，对手只显示手牌数量。
5. 完成一次出牌、弃牌、结束回合和需要选择的卡牌动作。

HTTPS 页面只能连接 `wss://`；如果填写 `ws://`，浏览器会作为混合内容阻止。
