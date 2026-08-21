import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);

test("is a platform-neutral Next.js frontend", async () => {
  const [page, layout, packageJson, nextConfig] = await Promise.all([
    readFile(new URL("app/page.tsx", root), "utf8"),
    readFile(new URL("app/layout.tsx", root), "utf8"),
    readFile(new URL("package.json", root), "utf8"),
    readFile(new URL("next.config.ts", root), "utf8"),
  ]);

  assert.match(page, /<GameClient \/>/);
  assert.match(layout, /Card Duel · 卡牌对决/);
  assert.match(layout, /VERCEL_PROJECT_PRODUCTION_URL/);
  assert.match(packageJson, /"next": "16\.2\.6"/);
  assert.match(packageJson, /"build": "next build"/);
  assert.doesNotMatch(packageJson, /vinext|wrangler|cloudflare|openai\/sites/);
  assert.match(nextConfig, /NextConfig/);
  assert.match(nextConfig, /allowedDevOrigins:\s*\["127\.0\.0\.1"\]/);
  await access(new URL("public/og.png", root));
  await assert.rejects(access(new URL(".openai/hosting.json", root)));
  await assert.rejects(access(new URL("vite.config.ts", root)));
});

test("keeps the WebSocket protocol contract and safe deployment defaults", async () => {
  const gameClient = await readFile(
    new URL("app/game-client.tsx", root),
    "utf8",
  );

  assert.match(gameClient, /protocol_version !== 2/);
  assert.match(gameClient, /NEXT_PUBLIC_CARD_DUEL_WS_URL/);
  assert.match(gameClient, /match\.card_catalogs \?\? \{\}/);
  assert.match(gameClient, /match\.you\.card_costs\?\.\[index\]/);
  assert.match(gameClient, /请输入完整的 ws:\/\/ 或 wss:\/\/ 后端地址/);
  assert.doesNotMatch(gameClient, /useEffect\(\(\) => endRef/);
  assert.match(gameClient, /useEffect\(\(\) => \{\s+endRef\.current/);
  for (const action of [
    "create_room",
    "join_room",
    "select_character",
    "set_ready",
    "play_card",
    "discard_card",
    "end_turn",
    "resolve_choice",
  ]) {
    assert.match(gameClient, new RegExp(`"${action}"`));
  }
});
