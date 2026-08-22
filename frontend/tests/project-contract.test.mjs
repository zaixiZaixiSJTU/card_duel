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
  assert.match(gameClient, /if \(!nextMatch\.pending_choice\)/);
  assert.match(gameClient, /aria-label="减少选择数"/);
  assert.match(gameClient, /aria-label="增加选择数"/);
  for (const action of [
    "create_room",
    "join_room",
    "leave_room",
    "select_character",
    "set_ready",
    "play_card",
    "discard_cards",
    "end_turn",
    "resolve_choice",
  ]) {
    assert.match(gameClient, new RegExp(`"${action}"`));
  }
  assert.match(gameClient, /case "room_left"/);
});

test("keeps game explanations centralized and accessible", async () => {
  const [gameClient, terms, tooltip, styles] = await Promise.all([
    readFile(new URL("app/game-client.tsx", root), "utf8"),
    readFile(new URL("app/game-terms.ts", root), "utf8"),
    readFile(new URL("app/components/game-tooltip.tsx", root), "utf8"),
    readFile(new URL("app/globals.css", root), "utf8"),
  ]);

  for (const term of ["生命", "能量", "防御", "力量", "有效手牌", "抽牌堆", "消耗"]) {
    assert.match(terms, new RegExp(`title: "${term}"`));
  }
  assert.match(gameClient, /cardCostExplanation\(cost, card\?\.cost\)/);
  assert.match(gameClient, /statusExplanation\(key\)/);
  assert.match(gameClient, /<RuleText text=\{card\?\.description/);
  assert.match(gameClient, /max_health\?: number/);
  assert.match(gameClient, /className="energy-core"/);
  assert.match(gameClient, /className="health-track" role="meter"/);
  assert.match(terms, /INLINE_RULE_TERMS/);
  assert.match(tooltip, /createPortal/);
  assert.match(tooltip, /role="tooltip"/);
  assert.match(tooltip, /aria-describedby=/);
  assert.match(tooltip, /event\.key === "Escape"/);
  assert.match(styles, /\.game-tooltip-panel/);
  assert.match(styles, /\.health-fill/);
  assert.match(styles, /\.game-tooltip-anchor\.energy-core/);
  assert.match(styles, /z-index: 1000/);
});
