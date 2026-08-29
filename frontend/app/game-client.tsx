"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";
import Image from "next/image";

import { GameTooltip } from "./components/game-tooltip";
import {
  GAME_TERMS,
  INLINE_RULE_TERMS,
  cardCostExplanation,
  cardTypeExplanation,
  phaseExplanation,
  statusExplanation,
} from "./game-terms";
import type { GameExplanation } from "./game-terms";
import { toggleLimitedIndex } from "./selection";

type ConnectionStatus = "idle" | "connecting" | "connected" | "closed";

type CharacterOption = { character_id: number; name: string };
type RoomPlayer = {
  player_id: number;
  character_id: number | null;
  ready: boolean;
  team_id?: number | null;
  display_name?: string;
  deck_counts?: Record<string, Record<string, number>>;
};
// 多人扩展：seats 覆盖所有座位（含空座位），方便渲染选座位 UI。
type RoomSeat =
  | { seat_id: number; occupied: false }
  | {
      seat_id: number;
      occupied: true;
      player_id: number;
      display_name: string;
      is_host?: boolean;
      character_id: number | null;
      ready: boolean;
      team_id?: number | null;
      deck_counts?: Record<string, Record<string, number>>;
    };
type RoomView = {
  room_code: string;
  status: string;
  seat_capacity?: number;
  host_seat?: number | null;
  seats?: RoomSeat[];
  settings: {
    first_player: string;
    first_seat?: number | null;
    random_seat_order?: boolean;
    seed: number | null;
    round1_no_damage: boolean;
  };
  players: RoomPlayer[];
  characters: CharacterOption[];
  catalogs?: Record<string, CardDefinition[]>;
  default_deck_counts?: Record<string, Record<string, number>>;
};

type CardDefinition = {
  card_id: number;
  name: string;
  card_type: string;
  cost: number | null;
  description: string;
  exhausted: boolean;
  unlock_condition?: string | null;
};

type Creature = {
  card_id: number;
  health: number;
  owner_id: number;
  shell?: boolean;
  held_item?: number;
};

type PublicPlayer = {
  health: number;
  max_health?: number;
  energy: number;
  strength: number;
  poison: number;
  defence: number;
  is_alive?: boolean;
  team_id?: number | null;
  display_name?: string;
  seat_id?: number;
  statuses: {
    hand_creatures: Creature[];
    creature_threats: Creature[];
    [key: string]: unknown;
  };
  character_data: Record<string, unknown> | null;
};

// 多人扩展：others 列表用于 3+ 人渲染除自己外所有玩家牌区计数。
type OtherPlayer = {
  player_id: number;
  hand_count: number;
  draw_count: number;
  discard_count: number;
};

type MatchView = {
  room_code: string;
  revision: number;
  player_id: number;
  character_ids: Record<string, number>;
  player_teams?: Record<string, number | null>;
  turn_order?: number[];
  players: Record<string, PublicPlayer>;
  card_catalogs?: Record<string, CardDefinition[]>;
  random_seed: number;
  first_player_id: number;
  round1_no_damage: boolean;
  round_number: number;
  active_player_id: number;
  current_phase: string | null;
  game_over: boolean;
  hand_limit: number;
  pending_choice: boolean;
  you: {
    hand_cards: number[];
    draw_pile?: number[];
    discard_pile?: number[];
    card_costs?: Array<number | null>;
    card_discardable?: boolean[];
    effective_hand_size?: number;
    draw_count: number;
    discard_count: number;
    forced_discards?: number;
  };
  // 兼容字段：2 人时即对手；3+ 人时仅返回轮转中下一个对手。
  opponent: { hand_count: number; draw_count: number; discard_count: number };
  // 多人扩展：除自己外所有玩家牌区计数。
  others?: OtherPlayer[];
};

// 多人扩展：阵营颜色映射，team_id -> CSS 类名 + 显示名。
// null 表示 FFA（自由阵营，互为敌方）。所有玩家共用同一份映射。
const TEAM_COLORS: Array<{ id: number; label: string; className: string }> = [
  { id: 0, label: "红", className: "team-red" },
  { id: 1, label: "蓝", className: "team-blue" },
  { id: 2, label: "绿", className: "team-green" },
  { id: 3, label: "黄", className: "team-yellow" },
  { id: 4, label: "紫", className: "team-purple" },
  { id: 5, label: "橙", className: "team-orange" },
];

// 多人扩展：根据 team_id 取 CSS 类名（局内信息栏边框、座位高亮用）。
function teamClassFor(teamId: number | null | undefined): string {
  if (teamId === null || teamId === undefined) return "team-ffa";
  return TEAM_COLORS.find((item) => item.id === teamId)?.className ?? "team-ffa";
}

type ChoicePrompt = {
  kind: "integer" | "option" | "card_indexes";
  title: string;
  prompt: string;
  default: number | string | null;
  options?: string[];
  minimum?: number;
  maximum?: number;
  hand?: number[];
  count?: number;
  excluded_card_id?: number;
};

type PendingChoice = { choice_id: string; choice: ChoicePrompt };
type LogEntry = { id: number; tone: string; text: string };
type PlayTarget = { source: "hand" | "creature"; index: number; token: number };
type DeckViewerMode = "draw" | "discard";
type LayoutRegion = "opponentStatus" | "ownStatus" | "piles" | "hand" | "lastPlayed" | "actionPanel" | "logPanel";
type DiscardPress = { index: number; token: number };
type LayoutSettings = {
  cardHeight: number;
  cardWidth: number;
  chatFontSize: number;
  chatHeight: number;
  sideColumnWidth: number;
};
type InteractionSettings = {
  clickMode: "single" | "double";
  playGapMs: number;
};
const DEFAULT_LAYOUT_SETTINGS: LayoutSettings = {
  cardHeight: 240,
  cardWidth: 145,
  chatFontSize: 13,
  chatHeight: 285,
  sideColumnWidth: 350,
};

const DEFAULT_REGION_OFFSETS: Record<LayoutRegion, { x: number; y: number }> = {
  opponentStatus: { x: 0, y: 0 },
  ownStatus: { x: 0, y: 0 },
  piles: { x: 0, y: 0 },
  hand: { x: 0, y: 0 },
  lastPlayed: { x: 0, y: 0 },
  actionPanel: { x: 0, y: 0 },
  logPanel: { x: 0, y: 0 },
};
const DEFAULT_INTERACTION_SETTINGS: InteractionSettings = {
  clickMode: "double",
  playGapMs: 700,
};

const phaseIndex: Record<string, number> = {
  "回合开始时": 0,
  "抽牌阶段": 1,
  "出牌阶段": 2,
  "弃牌阶段": 3,
  "回合结束时": 4,
};

const phases = ["回合开始", "抽牌", "出牌", "弃牌", "回合结束"];
const inlineRulePattern = new RegExp(`(${INLINE_RULE_TERMS.map(({ term }) => term).join("|")})`, "g");

function logTone(message: string) {
  if (/伤害|扣血|实际扣血|失去生命|流血/.test(message)) return "damage";
  if (/获得|增加|恢复|抽牌|饱食度\+|敏捷\+|动能\+|力量\+/.test(message)) return "gain";
  if (/不能|不足|无法|失败|警告|超时/.test(message)) return "warn";
  if (/回合|轮到|阶段/.test(message)) return "turn";
  return "normal";
}

function defaultEndpoint() {
  const configuredEndpoint = process.env.NEXT_PUBLIC_CARD_DUEL_WS_URL;
  if (configuredEndpoint) return configuredEndpoint;
  if (typeof window === "undefined") return "ws://127.0.0.1:8000/ws";
  if (["localhost", "127.0.0.1"].includes(window.location.hostname)) {
    return "ws://127.0.0.1:8000/ws";
  }
  return "";
}

export function GameClient() {
  const socketRef = useRef<WebSocket | null>(null);
  const logCounter = useRef(0);
  // 玩家名称解析用 ref：socket.onmessage 只在 connect 时绑定一次，后续 render
  // 产生的新闭包不会重新接线，因此必须用 ref 读取最新的 match/room 名称映射。
  const matchRef = useRef<MatchView | null>(null);
  const roomRef = useRef<RoomView | null>(null);
  const [endpoint, setEndpoint] = useState(defaultEndpoint);
  const [connection, setConnection] = useState<ConnectionStatus>("idle");
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [room, setRoom] = useState<RoomView | null>(null);
  const [match, setMatch] = useState<MatchView | null>(null);
  const [joinCode, setJoinCode] = useState("");
  // 玩家名称：进房间前在入口编辑，localStorage 持久，create_room/join_room 带上。
  const [playerName, setPlayerName] = useState("");
  const [chatText, setChatText] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastPlayed, setLastPlayed] = useState<{ character_id: number; card_id: number } | null>(null);
  const [choice, setChoice] = useState<PendingChoice | null>(null);
  const [choiceValue, setChoiceValue] = useState<number | string | null>(null);
  const [selectedIndexes, setSelectedIndexes] = useState<number[]>([]);
  const [firstPlayer, setFirstPlayer] = useState("random");
  // 多人扩展：随机座位顺序开关（替代旧 host/guest/random 三选一）。
  const [randomSeatOrder, setRandomSeatOrder] = useState(false);
  const [seed, setSeed] = useState("");
  const [roundOneSafe, setRoundOneSafe] = useState(true);
  const [layout, setLayout] = useState(DEFAULT_LAYOUT_SETTINGS);
  const [interaction, setInteraction] = useState(DEFAULT_INTERACTION_SETTINGS);

  useEffect(() => {
    matchRef.current = match;
  }, [match]);
  useEffect(() => {
    roomRef.current = room;
  }, [room]);

  // 玩家名称解析：把"玩家{数字}"替换为该玩家的展示名（display_name）。
  // 这样无需改动后端上百条 announce 字符串，前端一处即可全局显示玩家名称。
  const playerNameOf = (id: number | string): string => {
    const key = String(id);
    const inMatch = matchRef.current?.players?.[key]?.display_name;
    if (inMatch) return inMatch;
    const inRoom = roomRef.current?.players?.find(
      (p) => String(p.player_id) === key,
    )?.display_name;
    if (inRoom) return inRoom;
    return `玩家${key}`;
  };
  const resolvePlayerNames = (text: string): string =>
    text.replace(/玩家(\d+)/g, (m, id) => {
      const name = playerNameOf(id);
      return name === `玩家${id}` ? m : name;
    });

  useEffect(() => {
    try {
      const savedLayout = localStorage.getItem("cardDuel.layout");
      let nextLayout = null as LayoutSettings | null;
      if (savedLayout) {
        const parsed = JSON.parse(savedLayout) as Partial<LayoutSettings> & { uiScale?: number };
        nextLayout = { ...DEFAULT_LAYOUT_SETTINGS, ...parsed };
        if (typeof parsed.cardHeight !== "number" && typeof parsed.uiScale === "number") {
          // 旧版"整体缩放"按百分比迁移为手牌高度（240px 基准）。
          nextLayout.cardHeight = Math.round(240 * parsed.uiScale / 100);
        }
      }
      const savedInteraction = localStorage.getItem("cardDuel.interaction");
        const nextInteraction = savedInteraction ? { ...DEFAULT_INTERACTION_SETTINGS, ...JSON.parse(savedInteraction) } : null;
        if (nextLayout || nextInteraction) {
          window.setTimeout(() => {
            if (nextLayout) setLayout(nextLayout);
            if (nextInteraction) setInteraction(nextInteraction);
          }, 0);
        }
        const savedName = localStorage.getItem("cardDuel.playerName");
        if (savedName) {
          window.setTimeout(() => setPlayerName(savedName), 0);
        }
    } catch {
      localStorage.removeItem("cardDuel.layout");
      localStorage.removeItem("cardDuel.interaction");
      localStorage.removeItem("cardDuel.regions");
    }
  }, []);

  const addLog = (text: string, tone = "normal") => {
    setLogs((current) => [
      ...current.slice(-119),
      { id: ++logCounter.current, tone, text },
    ]);
  };

  // 玩家名称持久化：入口编辑后写入 localStorage，下次进入自动恢复。
  useEffect(() => {
    if (playerName) {
      localStorage.setItem("cardDuel.playerName", playerName);
    }
  }, [playerName]);

  const send = (action: string, data: Record<string, unknown> = {}) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setNotice("尚未连接到服务器");
      return;
    }
    socket.send(JSON.stringify({ action, data }));
  };

  const resetSession = () => {
    setRoom(null);
    setMatch(null);
    setPlayerId(null);
    setChoice(null);
    setLastPlayed(null);
  };

  const handleServerEvent = (payload: { type: string; protocol_version: number; data: Record<string, unknown> }) => {
    const { type, data } = payload;
    if (payload.protocol_version !== 2) {
      setNotice(`协议版本不匹配：服务器为 ${payload.protocol_version}，页面需要 2`);
      return;
    }
    switch (type) {
      case "connected":
        setConnection("connected");
        addLog("已连接权威对局服务器", "system");
        break;
      case "room_created":
      case "room_joined":
        setPlayerId(Number(data.player_id));
        addLog(type === "room_created" ? `房间 ${data.room_code} 已创建` : `已加入房间 ${data.room_code}`, "system");
        break;
      case "room_state": {
        const nextRoom = data.room as RoomView;
        setRoom(nextRoom);
        // 同步 ref（与下面 match 同理）：onmessage 只绑定一次，setRoom 触发的
        // useEffect 要等渲染后才回写 ref，期间若紧接着来 announcement/chat，
        // resolvePlayerNames 会读到旧名。这里在收到消息当下立即写 ref，避免空窗。
        roomRef.current = nextRoom;
        // 同步本地 playerId：房主/玩家换座后后端会推送新的 your_player_id，
        // 前端必须跟随更新，否则 isHost/isMine 判断会脱节。
        if (data.your_player_id !== undefined && data.your_player_id !== null) {
          setPlayerId(Number(data.your_player_id));
        }
        setMatch(null);
        matchRef.current = null;
        setFirstPlayer(nextRoom.settings.first_player);
        setRandomSeatOrder(Boolean(nextRoom.settings.random_seat_order));
        setSeed(nextRoom.settings.seed === null ? "" : String(nextRoom.settings.seed));
        setRoundOneSafe(nextRoom.settings.round1_no_damage);
        break;
      }
      case "match_started":
        setMatch(data.state as MatchView);
        matchRef.current = data.state as MatchView;
        setRoom(null);
        roomRef.current = null;
        setChoice(null);
        if (!(data.state as MatchView).card_catalogs) {
          setNotice("后端进程尚未提供卡牌目录；请重启 card-duel-web 以显示完整卡面");
        }
        addLog("对局开始", "turn");
        break;
      case "state": {
        const nextMatch = data.state as MatchView;
        setMatch(nextMatch);
        matchRef.current = nextMatch;
        if (!nextMatch.pending_choice) {
          setChoice(null);
          setSelectedIndexes([]);
        }
        break;
      }
      case "chat":
        addLog(`${playerNameOf(String(data.player_id))}：${data.message}`, "chat");
        break;
      case "announcement": {
        // logTone 仍按原文判断语气（关键词不受"玩家{数字}"替换影响），
        // 显示文本经 resolvePlayerNames 把"玩家{n}"替换为展示名。
        const rawAnnounce = String(data.message);
        addLog(resolvePlayerNames(rawAnnounce), logTone(rawAnnounce));
        break;
      }
      case "private_announcement":
        addLog(resolvePlayerNames(String(data.message)), "private");
        break;
      case "card_played":
        setLastPlayed({ character_id: Number(data.character_id), card_id: Number(data.card_id) });
        break;
      case "choice_required": {
        const pending = data as unknown as PendingChoice;
        setChoice(pending);
        setChoiceValue(pending.choice.default ?? null);
        setSelectedIndexes([]);
        break;
      }
      case "choice_cancelled":
        setChoice(null);
        addLog("已取消本次选择", "system");
        break;
      case "room_closed":
        addLog("房间已关闭", "warn");
        resetSession();
        break;
      case "room_left":
        addLog("已离开房间", "system");
        resetSession();
        break;
      case "error":
        setNotice(String(data.message));
        addLog(String(data.message), "warn");
        break;
    }
  };

  const connect = () => {
    socketRef.current?.close();
    resetSession();
    setConnection("connecting");
    setNotice(null);
    const address = endpoint.trim();
    if (!/^wss?:\/\/[^\s]+$/i.test(address)) {
      setConnection("closed");
      setNotice("请输入完整的 ws:// 或 wss:// 后端地址");
      return;
    }
    try {
      const socket = new WebSocket(address);
      socketRef.current = socket;
      socket.onmessage = (message) => {
        try {
          handleServerEvent(JSON.parse(message.data));
        } catch {
          setNotice("收到无法解析的服务器消息");
        }
      };
      socket.onerror = () => setNotice("无法连接服务器，请确认后端已启动");
      socket.onclose = () => {
        setConnection("closed");
        setChoice(null);
      };
    } catch {
      setConnection("closed");
      setNotice("服务器地址格式不正确");
    }
  };

  useEffect(() => {
    return () => {
      socketRef.current?.close();
    };
  }, []);

  const submitChat = (event: FormEvent) => {
    event.preventDefault();
    if (!chatText.trim()) return;
    send("chat", { message: chatText.trim() });
    setChatText("");
  };

  const configureRoom = () => {
    const numericSeed = seed.trim() === "" ? null : Number(seed);
    if (numericSeed !== null && !Number.isInteger(numericSeed)) {
      setNotice("随机种子必须是整数");
      return;
    }
    // 多人扩展：发送 first_seat=null + random_seat_order 替代旧 host/guest/random。
    // first_player 仍传 "random" 以兼容旧后端，但前端不再用其值。
    send("configure_room", {
      first_player: "random",
      first_seat: null,
      random_seat_order: randomSeatOrder,
      seed: numericSeed,
      round1_no_damage: roundOneSafe,
    });
  };

  // 多人扩展：房主加座位（最多 8 个）。
  const addSeat = () => send("add_seat");
  // 多人扩展：房主移除一个空座位。
  const removeSeat = (seatId: number) => send("remove_seat", { seat: seatId });
  // 多人扩展：房主随机重排座位。
  const shuffleSeats = () => send("shuffle_seats");
  // 多人扩展：玩家选择一个空座位坐下，或在已入房后换座。
  const pickSeat = (seatId: number) => send("pick_seat", { seat: seatId });
  // 多人扩展：玩家选择自己的阵营颜色（红/蓝/绿/黄/紫/橙），null=FFA。
  const setTeam = (teamId: number | null) =>
    send("set_team", { team_id: teamId });
  // 多人扩展：玩家设置自己的展示名称，方便在座位上辨识。
  const setName = (name: string) => send("set_name", { display_name: name });
  // 多人扩展：房主强制交换两个已占用座位的玩家。
  const swapSeats = (seatA: number, seatB: number) =>
    send("swap_seats", { seat_a: seatA, seat_b: seatB });
  // 多人扩展：房主把某玩家强制迁移到空座位。
  const movePlayer = (fromSeat: number, toSeat: number) =>
    send("move_player", { from_seat: fromSeat, to_seat: toSeat });

  const resolveChoice = (value: unknown) => {
    if (!choice) return;
    send("resolve_choice", { choice_id: choice.choice_id, value });
  };

  if (match) {
    return (
      <MatchScreen
        match={match}
        logs={logs}
        chatText={chatText}
        setChatText={setChatText}
        submitChat={submitChat}
        send={send}
        lastPlayed={lastPlayed}
        connection={connection}
        layout={layout}
        interaction={interaction}
        onLayoutChange={setLayout}
        onInteractionChange={setInteraction}
      >
        {choice && (
          <ChoiceDialog
            pending={choice}
            value={choiceValue}
            setValue={setChoiceValue}
            selected={selectedIndexes}
            setSelected={setSelectedIndexes}
            match={match}
            resolve={resolveChoice}
            cancel={() => send("cancel_choice", { choice_id: choice.choice_id })}
          />
        )}
        <AnimatePresence>{notice && <Notice message={notice} close={() => setNotice(null)} />}</AnimatePresence>
      </MatchScreen>
    );
  }

  if (room && playerId !== null) {
    return (
      <LobbyScreen
        room={room}
        playerId={playerId}
        logs={logs}
        chatText={chatText}
        setChatText={setChatText}
        submitChat={submitChat}
        send={send}
        firstPlayer={firstPlayer}
        setFirstPlayer={setFirstPlayer}
        randomSeatOrder={randomSeatOrder}
        setRandomSeatOrder={setRandomSeatOrder}
        seed={seed}
        setSeed={setSeed}
        roundOneSafe={roundOneSafe}
        setRoundOneSafe={setRoundOneSafe}
        configureRoom={configureRoom}
        addSeat={addSeat}
        removeSeat={removeSeat}
        shuffleSeats={shuffleSeats}
        pickSeat={pickSeat}
        setTeam={setTeam}
        setName={setName}
        swapSeats={swapSeats}
        movePlayer={movePlayer}
      >
        <AnimatePresence>{notice && <Notice message={notice} close={() => setNotice(null)} />}</AnimatePresence>
      </LobbyScreen>
    );
  }

  return (
    <main className="entry-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <Brand connection={connection} />
      <section className="entry-grid">
        <article className="hero-panel">
          <div className="hero-copy">
            <p className="kicker">双人 · 回合制 · 实时同步</p>
            <h2>进入牌桌，<br />让每一次选择生效。</h2>
            <p className="lead">五阶段权威结算。你的手牌只属于你，所有伤害与状态由服务器裁决。</p>
          </div>
          <DemoCards />
        </article>

        <aside className="connect-panel">
          <div className="panel-heading"><span>连接牌桌</span><b>01</b></div>
          <label htmlFor="player-name-input">你的名称</label>
          <div className="endpoint-field name-field">
            <span>ID</span>
            <input
              id="player-name-input"
              value={playerName}
              maxLength={20}
              placeholder="进入房间前先设个名字"
              onChange={(event) => setPlayerName(event.target.value)}
            />
          </div>
          <label htmlFor="server-url">服务器地址</label>
          <div className="endpoint-field">
            <span>WS</span>
            <input id="server-url" value={endpoint} placeholder="wss://game-api.example.com/ws" onChange={(event) => setEndpoint(event.target.value)} disabled={connection === "connecting" || connection === "connected"} />
          </div>
          {connection !== "connected" ? (
            <button className="primary-action" type="button" onClick={connect} disabled={connection === "connecting"}>
              {connection === "connecting" ? "正在连接…" : "建立连接"}<span>→</span>
            </button>
          ) : (
            <>
              <div className="connected-strip"><i /> 已连接，选择进入方式</div>
              <div className="mode-row">
                <button type="button" className="mode-card" onClick={() => send("create_room", { display_name: playerName.trim() })}>
                  <small>HOST</small><strong>创建房间</strong><span>生成 6 位房间号</span>
                </button>
                <div className="mode-card join-card">
                  <small>JOIN</small><strong>加入对局</strong>
                  <div><input aria-label="房间号" maxLength={6} placeholder="000000" value={joinCode} onChange={(event) => setJoinCode(event.target.value.replace(/\D/g, ""))} />
                  <button type="button" onClick={() => send("join_room", { room_code: joinCode, display_name: playerName.trim() })}>→</button></div>
                </div>
              </div>
            </>
          )}
          <p className="connection-note"><i /> 后端服务需在本机或可访问服务器运行</p>
        </aside>
      </section>
      <PhaseFooter />
      <AnimatePresence>{notice && <Notice message={notice} close={() => setNotice(null)} />}</AnimatePresence>
    </main>
  );
}

function Brand({ connection, compact = false }: { connection: ConnectionStatus; compact?: boolean }) {
  return (
    <header className={`brand-bar ${compact ? "compact" : ""}`}>
      <div className="brand-mark">CD</div>
      <div><p className="eyebrow">AUTHORITATIVE DUEL SYSTEM</p><h1>卡牌对决</h1></div>
      <span className={`server-pill status-${connection}`}><i /> {connection === "connected" ? "已连接 · 协议 2" : "协议 2"}</span>
    </header>
  );
}

function DemoCards() {
  return <div className="card-orbit" aria-hidden="true"><div className="demo-card demo-card-back"><span>守</span></div><div className="demo-card demo-card-main"><div className="demo-cost">1</div><span className="demo-type">攻击</span><strong>一根钢筋</strong><p>造成 2 点伤害<br />穿透时插入目标</p><small>RAIN WORLD · 001</small></div></div>;
}

function PhaseFooter() {
  return <footer className="entry-footer">{phases.map((phase, index) => <GameTooltip key={phase} explanation={phaseExplanation(phase)}>{index > 0 && <i />}{phase}</GameTooltip>)}</footer>;
}

function LobbyScreen(props: {
  room: RoomView; playerId: number; logs: LogEntry[]; chatText: string;
  setChatText: (value: string) => void; submitChat: (event: FormEvent) => void;
  send: (action: string, data?: Record<string, unknown>) => void;
  firstPlayer: string; setFirstPlayer: (value: string) => void;
  randomSeatOrder: boolean; setRandomSeatOrder: (value: boolean) => void;
  seed: string; setSeed: (value: string) => void; roundOneSafe: boolean;
  setRoundOneSafe: (value: boolean) => void; configureRoom: () => void;
  addSeat: () => void; removeSeat: (seatId: number) => void;
  shuffleSeats: () => void; pickSeat: (seatId: number) => void;
  setTeam: (teamId: number | null) => void;
  setName: (name: string) => void;
  swapSeats: (seatA: number, seatB: number) => void;
  movePlayer: (fromSeat: number, toSeat: number) => void;
  children: ReactNode;
}) {
  const { room, playerId, send } = props;
  const local = room.players.find((player) => player.player_id === playerId);
  // 房主身份跟随 client_id（后端 host_seat 是房主当前所在座位号）。
  // 房主换座位后 host_seat 更新，权限不丢。
  const isHost = playerId === (room.host_seat ?? 1);
  // 房主座位调整模式：null=未激活，"swap"=选第二个交换座位，"move"=选目标空座位。
  // 激活后记住第一个座位，点击下一个座位完成操作。
  const [seatOpMode, setSeatOpMode] = useState<null | "swap" | "move">(null);
  const [seatOpSource, setSeatOpSource] = useState<number | null>(null);
  // 名称输入：本地草稿缓冲，回车或失焦时发送 set_name。
  const [nameDraft, setNameDraft] = useState(local?.display_name ?? "");
  useEffect(() => {
    setNameDraft(local?.display_name ?? "");
  }, [local?.display_name]);
  const submitName = () => {
    const trimmed = nameDraft.trim();
    if (trimmed && trimmed !== local?.display_name) {
      props.setName(trimmed);
    } else if (!trimmed) {
      setNameDraft(local?.display_name ?? "");
    }
  };
  const [deckEditorOpen, setDeckEditorOpen] = useState(false);
  const [deckEditorCharacter, setDeckEditorCharacter] = useState<number | null>(null);
  const [deckCounts, setDeckCounts] = useState<Record<number, Record<number, number>>>({});
  const [previewedCard, setPreviewedCard] = useState<CardDefinition | null>(null);
  const savedDeckKey = `cardDuel.deck.${playerId}`;
  const deckSyncRef = useRef(false);
  const [viewportHeight, setViewportHeight] = useState(() =>
    typeof window === "undefined" ? 800 : window.innerHeight,
  );
  useEffect(() => {
    const measure = () => setViewportHeight(window.innerHeight);
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);
  const enlargeScale = Math.min(
    1.25,
    Math.max(0.7, (viewportHeight - 130) / 240),
  );
  useEffect(() => {
    if (deckSyncRef.current) return;
    deckSyncRef.current = true;
    let saved: Record<string, Record<string, number>> | null = null;
    try {
      const raw = localStorage.getItem(savedDeckKey);
      saved = raw ? JSON.parse(raw) : null;
    } catch {
      saved = null;
    }
    if (!saved) return;
    for (const [charKey, counts] of Object.entries(saved)) {
      if (!local?.deck_counts?.[charKey]) {
        send("configure_character_deck", {
          character_id: Number(charKey),
          deck_counts: counts,
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const selectedCharacterId = deckEditorCharacter ?? local?.character_id ?? null;
  const defaultDeckCounts = room.default_deck_counts ?? {};
  const serverDeckFor = (characterId: number) =>
    local?.deck_counts?.[String(characterId)] ?? null;
  const editorCatalog =
    selectedCharacterId === null
      ? []
      : (room.catalogs?.[String(selectedCharacterId)] ?? []).filter(
          (card) =>
            selectedCharacterId !== 4 ||
            (card.card_type !== "物品" && card.card_type !== "生物"),
        );
  const editorDefaults =
    selectedCharacterId === null ? {} : defaultDeckCounts[String(selectedCharacterId)] ?? {};
  const currentDeck =
    selectedCharacterId === null
      ? {}
      : deckCounts[selectedCharacterId] ??
        serverDeckFor(selectedCharacterId) ??
        { ...editorDefaults };
  const groupedEditorCards = Object.entries(editorCatalog.reduce<Record<string, CardDefinition[]>>((groups, card) => {
    (groups[card.card_type] ??= []).push(card);
    return groups;
  }, {}));
  const setDeckCount = (cardId: number, count: number) => {
    if (selectedCharacterId === null) return;
    const base =
      deckCounts[selectedCharacterId] ??
      serverDeckFor(selectedCharacterId) ??
      { ...editorDefaults };
    const next = { ...base, [cardId]: Math.max(0, Math.min(99, count)) };
    setDeckCounts((current) => ({
      ...current,
      [selectedCharacterId]: next,
    }));
    try {
      const existing = JSON.parse(localStorage.getItem(savedDeckKey) ?? "{}") ?? {};
      existing[String(selectedCharacterId)] = next;
      localStorage.setItem(savedDeckKey, JSON.stringify(existing));
    } catch {
      /* 本地保存失败不影响对局 */
    }
    send("configure_character_deck", {
      character_id: selectedCharacterId,
      deck_counts: next,
    });
  };
  const restoreDefaultDeck = () => {
    if (selectedCharacterId === null) return;
    const defaults = { ...editorDefaults };
    setDeckCounts((current) => ({ ...current, [selectedCharacterId]: defaults }));
    try {
      const existing = JSON.parse(localStorage.getItem(savedDeckKey) ?? "{}") ?? {};
      existing[String(selectedCharacterId)] = defaults;
      localStorage.setItem(savedDeckKey, JSON.stringify(existing));
    } catch {
      /* 本地保存失败不影响对局 */
    }
    send("configure_character_deck", {
      character_id: selectedCharacterId,
      deck_counts: defaults,
    });
  };
  return (
    <main className="lobby-shell" style={{ "--enlarge-scale": String(enlargeScale) } as React.CSSProperties}>
      <Brand connection="connected" compact />
      <section className="lobby-header">
        <div><p className="eyebrow">ROOM CODE</p><button className="room-code" type="button" onClick={() => navigator.clipboard?.writeText(room.room_code)}>{room.room_code}<span>复制</span></button></div>
        <div className="lobby-title"><p>等待双方就绪</p><h2>选择你的角色</h2></div>
        <button className="ghost-action" type="button" onClick={() => send("leave_room")}>离开房间</button>
      </section>

      <section className="lobby-content">
        <div className="character-section">
          <div className="character-grid">
            {room.characters.map((character) => {
              const selected = local?.character_id === character.character_id;
              const implemented = [1, 4].includes(character.character_id);
              return <button key={character.character_id} type="button" disabled={!implemented || !!local?.ready} title={local?.ready ? "已准备，请先取消准备" : undefined} className={`character-card char-${character.character_id} ${selected ? "selected" : ""}`} onClick={() => send("select_character", { character_id: character.character_id })}>
                <span className="character-number">0{character.character_id}</span><div className="character-glyph">{character.character_id === 1 ? "战" : character.character_id === 4 ? "猫" : "?"}</div><small>{implemented ? "PLAYABLE" : "IN DEVELOPMENT"}</small><strong>{character.name}</strong><p><RuleText text={character.character_id === 1 ? "防御 · 力量 · 献祭" : character.character_id === 4 ? "敏捷 · 业力 · 生物" : "角色机制开发中"} /></p>{selected && <b>已选择</b>}
              </button>;
            })}
          </div>

          <div className="player-slots">
            {/* 多人扩展：渲染所有座位（含空座位），玩家可点选空座位坐下，
                已入房后可点击其他空座位换座；房主可移除空座位、强制交换两座位、
                强制迁移玩家到空座位。每个已就座玩家可点击色块切换阵营颜色。 */}
            {seatOpMode && seatOpSource !== null && (
              <div className="seat-op-hint" role="status">
                {seatOpMode === "swap"
                  ? `交换模式：点击另一个已占用座位完成交换（源：座位 ${seatOpSource}）`
                  : `迁移模式：点击一个空座位作为目标（源：座位 ${seatOpSource}）`}
                <button type="button" className="ghost-action" onClick={() => { setSeatOpMode(null); setSeatOpSource(null); }}>取消</button>
              </div>
            )}
            {(room.seats ?? Array.from({ length: room.seat_capacity ?? 2 }, (_, index) => ({ seat_id: index + 1, occupied: false }))).map((seat) => {
              const isMine = seat.occupied && seat.player_id === playerId;
              const seatIsHost = seat.occupied && seat.is_host;
              const seatCharacterId = seat.occupied ? seat.character_id : null;
              const character = room.characters.find((item) => item.character_id === seatCharacterId);
              const seatTeamClass = seat.occupied ? teamClassFor(seat.team_id) : "";
              // 房主座位调整模式激活时，点击座位卡片完成操作。
              const handleSeatCardClick = () => {
                if (!isHost || seatOpMode === null || seatOpSource === null) return;
                if (seatOpMode === "swap") {
                  if (seat.occupied && seat.seat_id !== seatOpSource) {
                    props.swapSeats(seatOpSource, seat.seat_id);
                  }
                } else if (seatOpMode === "move") {
                  if (!seat.occupied) {
                    props.movePlayer(seatOpSource, seat.seat_id);
                  }
                }
                setSeatOpMode(null);
                setSeatOpSource(null);
              };
              const interactiveMode = isHost && seatOpMode !== null && seatOpSource !== null;
              if (!seat.occupied) {
                return (
                  <div
                    className={`player-slot seat-empty ${interactiveMode && seatOpMode === "move" ? "seat-target" : ""} ${interactiveMode ? "seat-interactive" : ""}`}
                    key={seat.seat_id}
                    onClick={handleSeatCardClick}
                    role={interactiveMode ? "button" : undefined}
                  >
                    <span>座位 {seat.seat_id} · 空位</span>
                    {!interactiveMode && (
                      <button type="button" className="seat-pick" onClick={(event) => { event.stopPropagation(); props.pickSeat(seat.seat_id); }}>选此座位</button>
                    )}
                    {isHost && !interactiveMode && (room.seat_capacity ?? 2) > 2 && (
                      <button type="button" className="seat-remove" onClick={(event) => { event.stopPropagation(); props.removeSeat(seat.seat_id); }}>移除座位</button>
                    )}
                    <i>{interactiveMode && seatOpMode === "move" ? "点此迁移" : "EMPTY"}</i>
                  </div>
                );
              }
              return (
                <div
                  className={`player-slot ${seatTeamClass} ${seat.ready ? "ready" : ""} ${isMine ? "mine" : ""} ${seatIsHost ? "host-seat" : ""} ${interactiveMode && seatOpMode === "swap" && seat.seat_id !== seatOpSource ? "seat-target" : ""} ${interactiveMode ? "seat-interactive" : ""}`}
                  key={seat.seat_id}
                  onClick={handleSeatCardClick}
                  role={interactiveMode ? "button" : undefined}
                >
                  {seatIsHost && <i className="host-badge">房主</i>}
                  <span>座位 {seat.seat_id}{isMine ? " · 你" : ""}</span>
                  <strong className="seat-display-name">{seat.display_name || `玩家${seat.seat_id}`}</strong>
                  <small className="seat-character-name">{character?.name ?? "未选择角色"}</small>
                  {isMine && !local?.ready && (
                    <div className="team-picker" role="group" aria-label="选择阵营颜色">
                      {TEAM_COLORS.map((color) => (
                        <button
                          key={color.id}
                          type="button"
                          aria-label={`选择${color.label}阵营`}
                          className={`team-swatch ${color.className} ${seat.team_id === color.id ? "active" : ""}`}
                          onClick={(event) => { event.stopPropagation(); props.setTeam(color.id); }}
                        />
                      ))}
                      <button
                        type="button"
                        aria-label="自由阵营 FFA"
                        className={`team-swatch team-ffa ${seat.team_id === null || seat.team_id === undefined ? "active" : ""}`}
                        onClick={(event) => { event.stopPropagation(); props.setTeam(null); }}
                      />
                    </div>
                  )}
                  {/* 房主对其他已占用座位（非自己）的操作按钮 */}
                  {isHost && !isMine && !interactiveMode && (
                    <div className="seat-host-actions">
                      <button type="button" className="seat-op-btn" title="与另一个座位交换" onClick={(event) => { event.stopPropagation(); setSeatOpMode("swap"); setSeatOpSource(seat.seat_id); }}>交换</button>
                      <button type="button" className="seat-op-btn" title="迁移到空座位" onClick={(event) => { event.stopPropagation(); setSeatOpMode("move"); setSeatOpSource(seat.seat_id); }}>迁移</button>
                    </div>
                  )}
                  <i>{seat.ready ? "READY" : "NOT READY"}</i>
                </div>
              );
            })}
            {isHost && (room.seat_capacity ?? 2) < 8 && (
              <button type="button" className="player-slot seat-add" onClick={props.addSeat}>+ 加座位</button>
            )}
          </div>
        </div>

        <aside className="lobby-sidebar">
          <div className="rules-panel">
            <div className="panel-heading"><span>房间规则</span><b>02</b></div>
            {/* 多人扩展：原"先手方 host/guest/random"三选一改为"开局时随机
                座位顺序"开关；房主可立即"随机重排"当前座位号。 */}
            <div className="toggle-row">
              <label htmlFor="random-seat-order">
                <strong>开局时随机座位顺序</strong>
                <small>开启后，开局时按种子打乱座位号再确定先手</small>
              </label>
              <input
                id="random-seat-order"
                aria-label="开局时随机座位顺序"
                type="checkbox"
                disabled={!isHost}
                checked={props.randomSeatOrder}
                onChange={(event) => props.setRandomSeatOrder(event.target.checked)}
              />
            </div>
            {isHost && (
              <button type="button" className="secondary-action" onClick={props.shuffleSeats}>立即随机重排座位</button>
            )}
            <label htmlFor="match-seed">随机种子</label>
            <input id="match-seed" className="rule-input" disabled={!isHost} placeholder="留空则随机" value={props.seed} onChange={(event) => props.setSeed(event.target.value)} />
            <div className="toggle-row"><label htmlFor="round-one-safe"><strong>首回合无伤</strong><small>先手第一回合无法扣除对方生命</small></label><input id="round-one-safe" aria-label="首回合无伤" type="checkbox" disabled={!isHost} checked={props.roundOneSafe} onChange={(event) => props.setRoundOneSafe(event.target.checked)} /></div>
            {isHost && <button className="secondary-action" type="button" onClick={props.configureRoom}>应用房间规则</button>}
          </div>
          <LogPanel logs={props.logs} chatText={props.chatText} setChatText={props.setChatText} submitChat={props.submitChat} compact />
        </aside>
      </section>
      <div className="lobby-ready-bar">
        <div className="lobby-ready-left">
          <label className="name-input-row" htmlFor="player-name">
            <span className="name-label">名称</span>
            <input
              id="player-name"
              className="name-input"
              type="text"
              maxLength={20}
              placeholder={`玩家${playerId}`}
              value={nameDraft}
              disabled={!!local?.ready}
              title={local?.ready ? "已准备，请先取消准备再改名" : "设置你在座位上显示的名字"}
              onChange={(event) => setNameDraft(event.target.value)}
              onBlur={submitName}
              onKeyDown={(event) => { if (event.key === "Enter") { (event.target as HTMLInputElement).blur(); } }}
            />
          </label>
          <p>{local?.character_id ? `已选择 ${room.characters.find((item) => item.character_id === local.character_id)?.name}` : "请先选择角色"}</p>
          <button type="button" className="deck-builder-toggle" disabled={!!local?.ready} title={local?.ready ? "已准备，请先取消准备" : undefined} onClick={() => { setDeckEditorCharacter(local?.character_id ?? 1); setDeckEditorOpen(true); }}>构建牌组</button>
        </div>
        <button type="button" disabled={!local?.character_id} className={local?.ready ? "ready-active" : ""} onClick={() => send("set_ready", { ready: !local?.ready })}>{local?.ready ? "取消准备" : "准备对局"}<span>→</span></button>
      </div>
      {deckEditorOpen && (
        <div className="modal-backdrop" onClick={() => setDeckEditorOpen(false)} role="presentation">
          <section className="choice-dialog deck-viewer deck-editor" role="dialog" aria-modal="true" aria-labelledby="deck-editor-title" onClick={(event) => event.stopPropagation()}>
            <p className="eyebrow">DECK BUILDER</p>
            <h2 id="deck-editor-title">构建牌组</h2>
            <p>点卡面放大查看；右下角 当前/默认：左键 +1、右键 -1（最少 0）。{selectedCharacterId === 4 ? "物品与生物由默认配置/区域机制决定，不可修改。" : ""}</p>
            <div className="deck-editor-tabs">
              {room.characters.filter((item) => [1, 4].includes(item.character_id)).map((item) => (
                <button key={item.character_id} type="button" className={selectedCharacterId === item.character_id ? "active" : ""} onClick={() => setDeckEditorCharacter(item.character_id)}>{item.name}</button>
              ))}
              <button type="button" className="deck-restore" onClick={restoreDefaultDeck}>恢复默认牌组</button>
            </div>
            {groupedEditorCards.length === 0 ? (
              <p className="muted">该角色暂无卡牌。</p>
            ) : (
              groupedEditorCards.map(([type, cards]) => (
                <section key={type} className="deck-group">
                  <h3>{type} · {cards.length}</h3>
                  <div className="deck-grid">
                    {cards.map((card) => {
                      const current = currentDeck[card.card_id] ?? 0;
                      const defaultValue = editorDefaults[card.card_id] ?? 0;
                      return (
                        <div key={card.card_id} className="deck-edit-card">
                          <button
                            type="button"
                            className="deck-card-button"
                            title="点击放大查看"
                            onClick={() => setPreviewedCard(card)}
                            onContextMenu={(event) => { event.preventDefault(); setPreviewedCard(card); }}
                          >
                            <GameCard card={card} characterId={selectedCharacterId ?? 1} cardId={card.card_id} cost={card.cost} index={card.card_id - 1} discardState="none" />
                          </button>
                          <button
                            type="button"
                            className="deck-count-badge"
                            title="左键 +1，右键 -1"
                            onClick={() => setDeckCount(card.card_id, current + 1)}
                            onContextMenu={(event) => { event.preventDefault(); setDeckCount(card.card_id, current - 1); }}
                          >
                            {current}<i>/{defaultValue}</i>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </section>
              ))
            )}
          </section>
        </div>
      )}
      {previewedCard && (
        <div className="modal-backdrop card-preview-backdrop" onClick={() => setPreviewedCard(null)} role="presentation">
          <div className="card-preview" onClick={(event) => event.stopPropagation()}>
            <div className="card-preview-card">
              <GameCard card={previewedCard} characterId={selectedCharacterId ?? 1} cardId={previewedCard.card_id} cost={previewedCard.cost} index={previewedCard.card_id - 1} discardState="none" />
            </div>
            <button type="button" className="card-preview-close" onClick={() => setPreviewedCard(null)}>关闭</button>
          </div>
        </div>
      )}
      {props.children}
    </main>
  );
}

function MatchScreen(props: {
  match: MatchView; logs: LogEntry[]; chatText: string; setChatText: (value: string) => void;
  submitChat: (event: FormEvent) => void; send: (action: string, data?: Record<string, unknown>) => void;
  lastPlayed: { character_id: number; card_id: number } | null; connection: ConnectionStatus;
  layout: LayoutSettings; interaction: InteractionSettings;
  onLayoutChange: (settings: LayoutSettings) => void;
  onInteractionChange: (settings: InteractionSettings) => void;
  children: ReactNode;
}) {
  const [localNotice, setLocalNotice] = useState<string | null>(null);
  const { match } = props;
  const [discardDraft, setDiscardDraft] = useState({
    revision: match.revision,
    activePlayerId: match.active_player_id,
    mode: false,
    indexes: [] as number[],
  });
  const discardDraftRef = useRef(discardDraft);
  const discardRevisionRef = useRef(`${match.revision}:${match.active_player_id}`);
  useEffect(() => {
    discardDraftRef.current = discardDraft;
  }, [discardDraft]);
  useEffect(() => {
    const revisionKey = `${match.revision}:${match.active_player_id}`;
    if (discardRevisionRef.current === revisionKey) return;
    discardRevisionRef.current = revisionKey;
    window.setTimeout(() => {
      setDiscardDraft((current) => ({
        revision: match.revision,
        activePlayerId: match.active_player_id,
        mode: current.mode,
        indexes: [],
      }));
    }, 0);
  }, [match.revision, match.active_player_id]);
  const me = match.players[String(match.player_id)];
  const opponentId =
    match.turn_order?.find((id) => id !== match.player_id) ??
    (match.player_id === 1 ? 2 : 1);
  const opponent = match.players[String(opponentId)];
  const myCharacter = match.character_ids[String(match.player_id)];
  const opponentCharacter = match.character_ids[String(opponentId)];
  const myTurn = match.active_player_id === match.player_id;
  const inPlay = match.current_phase === "出牌阶段";
  const inDiscard = match.current_phase === "弃牌阶段";
  const draftIsCurrent = discardDraft.revision === match.revision && discardDraft.activePlayerId === match.active_player_id;
  const manualDiscardMode = draftIsCurrent && discardDraft.mode;
  // 强制选择弃牌（混沌胃袋/手牌超限）：后端 forced_discards>0 时自动进入
  // 红框弃牌，与手动"进入弃牌"按钮表现一致，无需玩家手动切换。
  const forcedDiscard = myTurn && (match.you.forced_discards ?? 0) > 0;
  const discardMode = manualDiscardMode || forcedDiscard;
  const discardSelection = draftIsCurrent ? discardDraft.indexes : [];
  const selectingDiscard = discardMode;
  const effectiveHandSize = match.you.effective_hand_size ?? match.you.hand_cards.length;
  const excessCards = Math.max(0, effectiveHandSize - match.hand_limit);
  const currentPhase = phaseIndex[match.current_phase ?? ""] ?? -1;
  const catalogs = match.card_catalogs ?? {};
  const getCard = (characterId: number, cardId: number) => catalogs[String(characterId)]?.find((card) => card.card_id === cardId);
  const lastCard = props.lastPlayed ? getCard(props.lastPlayed.character_id, props.lastPlayed.card_id) : null;
  const creatures = me.statuses.hand_creatures.filter((creature) => creature.card_id !== 26);
  const playTimerRef = useRef<number | null>(null);
  const playTokenRef = useRef(0);
  const relayoutTimerRef = useRef<number | null>(null);
  const playLockUntilRef = useRef(0);
  const [playLocked, setPlayLocked] = useState(false);
  const [handRelayouting, setHandRelayouting] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [deckViewer, setDeckViewer] = useState<DeckViewerMode | null>(null);
  const [previewedCard, setPreviewedCard] = useState<{ card: CardDefinition; count: number } | null>(null);
  const [codexOpen, setCodexOpen] = useState(false);
  const [handView, setHandView] = useState<"cards" | "creatures">("cards");
  const [viewportHeight, setViewportHeight] = useState(() =>
    typeof window === "undefined" ? 800 : window.innerHeight,
  );
  const pendingPlayRef = useRef<PlayTarget | null>(null);
  const [activePlayTarget, setActivePlayTarget] = useState<PlayTarget | null>(null);
  const [activeDiscardTarget, setActiveDiscardTarget] = useState<DiscardPress | null>(null);
  const canPlay = myTurn && inPlay && !match.pending_choice && !playLocked && !handRelayouting;
  const cardEnlargeScale = Math.min(
    1.25,
    Math.max(
      0.7,
      (viewportHeight - 130) / props.layout.cardHeight,
    ),
  );
  const styleVariables = {
    "--ui-scale": String(props.layout.cardHeight / 240),
    "--card-height": `${props.layout.cardHeight}px`,
    "--card-width": `${props.layout.cardWidth}px`,
    "--chat-font-size": `${props.layout.chatFontSize}px`,
    "--chat-height": `${props.layout.chatHeight}px`,
    "--side-column": `${props.layout.sideColumnWidth}px`,
    "--enlarge-scale": String(cardEnlargeScale),
  } as React.CSSProperties;

  useEffect(() => {
    const measure = () => setViewportHeight(window.innerHeight);
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, []);

  useEffect(() => () => {
    if (playTimerRef.current !== null) window.clearTimeout(playTimerRef.current);
    if (relayoutTimerRef.current !== null) window.clearTimeout(relayoutTimerRef.current);
  }, []);

  const cancelScheduledPlay = () => {
    if (playTimerRef.current !== null) {
      window.clearTimeout(playTimerRef.current);
      playTimerRef.current = null;
      setLocalNotice(null);
    }
  };

  const startHandRelayout = () => {
    setHandRelayouting(true);
    if (relayoutTimerRef.current !== null) window.clearTimeout(relayoutTimerRef.current);
    relayoutTimerRef.current = window.setTimeout(() => {
      relayoutTimerRef.current = null;
      setHandRelayouting(false);
    }, 260);
  };

  const lockPlayForGap = () => {
    playLockUntilRef.current = 1;
    setPlayLocked(true);
    window.setTimeout(() => {
      playLockUntilRef.current = 0;
      setPlayLocked(false);
    }, Math.max(260, props.interaction.playGapMs));
  };

  const playTarget = (target: PlayTarget) => {
    setActivePlayTarget(null);
    props.send("play_card", { source: target.source, index: target.index });
    startHandRelayout();
    setLocalNotice(null);
    lockPlayForGap();
  };

  const beginPress = (source: "hand" | "creature", index: number) => {
    if (playLockUntilRef.current) return;
    const token = ++playTokenRef.current;
    const target = { source, index, token };
    if (props.interaction.clickMode === "double") {
      if (
        pendingPlayRef.current &&
        pendingPlayRef.current.source === source &&
        pendingPlayRef.current.index === index &&
        playTimerRef.current !== null
      ) {
        window.clearTimeout(playTimerRef.current);
        playTimerRef.current = null;
        pendingPlayRef.current = null;
        setActivePlayTarget(null);
        playTarget(target);
        return;
      }
      cancelScheduledPlay();
      setActivePlayTarget(target);
      pendingPlayRef.current = target;
      playTimerRef.current = window.setTimeout(() => {
        playTimerRef.current = null;
        pendingPlayRef.current = null;
        setLocalNotice("请再次点击确认出牌");
      }, 500);
      return;
    }

    cancelScheduledPlay();
    setActivePlayTarget(target);
    pendingPlayRef.current = target;
  };

  const confirmPress = (source: "hand" | "creature", index: number) => {
    if (props.interaction.clickMode !== "single") return;
    const pending = pendingPlayRef.current;
    if (playLockUntilRef.current || !pending) return;
    if (pending.source === source && pending.index === index) {
      playTimerRef.current = null;
      pendingPlayRef.current = null;
      setActivePlayTarget(null);
      playTarget(pending);
    }
  };

  const cancelPress = (source: "hand" | "creature", index: number) => {
    const pending = pendingPlayRef.current;
    if (pending && pending.source === source && pending.index === index) {
      cancelScheduledPlay();
      pendingPlayRef.current = null;
      setActivePlayTarget(null);
    }
  };

  const updateMatchLayout = (patch: Partial<LayoutSettings>) => {
    const next = { ...props.layout, ...patch };
    localStorage.setItem("cardDuel.layout", JSON.stringify(next));
    props.onLayoutChange(next);
  };

  const [regionOffsets, setRegionOffsets] = useState(DEFAULT_REGION_OFFSETS);
  useEffect(() => {
    try {
      const savedRegions = localStorage.getItem("cardDuel.regions");
      const nextRegions = savedRegions ? { ...DEFAULT_REGION_OFFSETS, ...JSON.parse(savedRegions) } : null;
      if (nextRegions) window.setTimeout(() => setRegionOffsets(nextRegions), 0);
    } catch {
      localStorage.removeItem("cardDuel.regions");
    }
  }, []);

  const updateRegionOffset = (region: LayoutRegion, patch: { x?: number; y?: number }) => {
    setRegionOffsets((current) => {
      const next = { ...current, [region]: { ...current[region], ...patch } };
      localStorage.setItem("cardDuel.regions", JSON.stringify(next));
      return next;
    });
  };

  const resetRegionOffsets = () => {
    localStorage.setItem("cardDuel.regions", JSON.stringify(DEFAULT_REGION_OFFSETS));
    setRegionOffsets(DEFAULT_REGION_OFFSETS);
  };

  const startRegionDrag = (event: React.PointerEvent<HTMLElement>, region: LayoutRegion) => {
    const target = event.target as HTMLElement;
    if (target.closest("button, input, form")) return;
    if ((event.target as HTMLElement).closest("[data-region]")?.getAttribute("data-region") !== region) return;
    event.preventDefault();
    const startX = event.clientX;
    const startY = event.clientY;
    const origin = regionOffsets[region];
    const move = (moveEvent: PointerEvent) => {
      updateRegionOffset(region, { x: Math.round(origin.x + moveEvent.clientX - startX), y: Math.round(origin.y + moveEvent.clientY - startY) });
    };
    const stop = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  };

  const updateMatchInteraction = (patch: Partial<InteractionSettings>) => {
    const next = { ...props.interaction, ...patch };
    localStorage.setItem("cardDuel.interaction", JSON.stringify(next));
    props.onInteractionChange(next);
  };

  const beginDiscardPress = (index: number) => {
    const discardable = match.you.card_discardable?.[index] ?? ![49, 50].includes(match.you.hand_cards[index]);
    if (!discardable) return;
    const token = ++playTokenRef.current;
    if (props.interaction.clickMode === "double") {
      const pending = activeDiscardTarget;
      if (pending && pending.index === index && playTimerRef.current !== null) {
        window.clearTimeout(playTimerRef.current);
        playTimerRef.current = null;
        setActiveDiscardTarget(null);
        setDiscardDraft({ revision: match.revision, activePlayerId: match.active_player_id, mode: manualDiscardMode, indexes: [] });
        props.send("discard_card", { index });
        return;
      }
      cancelScheduledPlay();
      setActiveDiscardTarget({ index, token });
      playTimerRef.current = window.setTimeout(() => {
        playTimerRef.current = null;
        setActiveDiscardTarget(null);
        setLocalNotice("请再次点击确认弃牌");
      }, 500);
      return;
    }

    cancelScheduledPlay();
    setActiveDiscardTarget({ index, token });
  };

  const confirmDiscardPress = (index: number) => {
    if (props.interaction.clickMode !== "single") return;
    const pending = activeDiscardTarget;
    if (pending && pending.index === index) {
      playTimerRef.current = null;
      setActiveDiscardTarget(null);
      setDiscardDraft({ revision: match.revision, activePlayerId: match.active_player_id, mode: manualDiscardMode, indexes: [] });
      props.send("discard_card", { index });
    }
  };

  const cancelDiscardPress = (index: number) => {
    const pending = activeDiscardTarget;
    if (pending && pending.index === index) {
      cancelScheduledPlay();
      setActiveDiscardTarget(null);
    }
  };


  const visibleHandCards = handView === "cards" ? match.you.hand_cards : [];
  const visibleCreatures = handView === "creatures" ? creatures : [];

  const deckViewerCards = deckViewer === "draw"
    ? match.you.draw_pile ?? []
    : match.you.discard_pile ?? [];
  const unlockedCreatures = me.statuses.unlocked_creature_counts ?? {};
  const safeUnlockedCreatures = unlockedCreatures && typeof unlockedCreatures === "object" ? unlockedCreatures : {};
  const groupedViewerCards = Object.entries(
    [
      ...deckViewerCards,
      ...(deckViewer === "draw" ? Object.entries(safeUnlockedCreatures).flatMap(([cardId, count]) => Array.from({ length: Number(count) }, () => Number(cardId))) : []),
    ].reduce<Record<string, Array<{ card: CardDefinition; count: number }>>>((groups, cardId) => {
      const card = getCard(myCharacter, cardId);
      if (!card) return groups;
      groups[card.card_type] ??= [];
      const existing = groups[card.card_type].find((item) => item.card.card_id === card.card_id);
      if (existing) existing.count += 1;
      else groups[card.card_type].push({ card, count: 1 });
      return groups;
    }, {}),
  );
  const codexGroups = Object.entries(
    (catalogs[String(myCharacter)] ?? []).reduce<Record<string, CardDefinition[]>>((groups, card) => {
      if (card.card_id === 0) return groups;
      (groups[card.card_type] ??= []).push(card);
      return groups;
    }, {}),
  );

  return (
    <main className="match-shell" style={styleVariables}>
      {match.game_over && (() => {
        // 严谨结算：按 is_alive 统计存活阵营。只剩一个阵营 → 该阵营胜；
        // FFA（team_id 为 null）时每个玩家独立成阵营，只剩一人即胜。
        const aliveEntries = Object.entries(match.players).filter(
          ([, p]) => p.is_alive !== false && p.health > 0,
        );
        const aliveTeams = new Set(
          aliveEntries.map(([, p]) => (p.team_id === undefined ? null : p.team_id)),
        );
        let resultText: string;
        if (aliveTeams.size === 1) {
          const teamId = [...aliveTeams][0];
          if (teamId === null) {
            const ffaWinner = aliveEntries[0]?.[1];
            resultText = `${ffaWinner?.display_name || `玩家 ${aliveEntries[0]?.[0] ?? ""}`} 胜利`;
          } else {
            const color = TEAM_COLORS.find((c) => c.id === teamId);
            resultText = `${color?.label ?? `阵营 ${teamId}`} 阵营胜利`;
          }
        } else {
          resultText = "对局结束";
        }
        return (
          <div className="game-over-overlay">
            <div className="game-over-card">
              <h2>对局结束</h2>
              <p>{resultText}</p>
              <button type="button" className="return-room-button" onClick={() => props.send("return_to_room", {})}>回到房间</button>
            </div>
          </div>
        );
      })()}
      <header className="match-topbar"><Brand connection={props.connection} compact /><div className="turn-track">{phases.map((phase, index) => <div key={phase} className={`${index === currentPhase ? "active" : ""} ${index < currentPhase ? "done" : ""}`}><span>{index + 1}</span><GameTooltip className="phase-name" explanation={phaseExplanation(phase)}><b>{phase}</b></GameTooltip></div>)}</div><GameTooltip className="round-tooltip" explanation={{ title: "轮次", description: "双方各完成一个回合后，轮次增加。新轮次会重新分配双方能量。" }}><span className="round-chip"><small>ROUND</small><strong>{String(match.round_number).padStart(2, "0")}</strong></span></GameTooltip></header>

      <section className="opponent-zone layout-region" data-region="opponentStatus" style={{ transform: `translate(${regionOffsets.opponentStatus.x}px, ${regionOffsets.opponentStatus.y}px)` }} onPointerDown={(event) => startRegionDrag(event, "opponentStatus")}>
        <PlayerStatus label={opponent?.display_name || `玩家 ${opponentId}`} character={opponentCharacter} player={opponent} active={match.active_player_id === opponentId} teamClass={teamClassFor(opponent?.team_id)} />
      </section>

      <section className="battlefield">
        <div className="creature-lane opponent-creatures">{opponent.statuses.hand_creatures.map((creature, index) => <CreatureChip key={`${creature.card_id}-${index}`} creature={creature} card={getCard(opponentCharacter, creature.card_id)} />)}</div>
        <div className="layout-region last-played-frame" data-region="lastPlayed" style={{ transform: `translate(${regionOffsets.lastPlayed.x}px, ${regionOffsets.lastPlayed.y}px)` }} onPointerDown={(event) => startRegionDrag(event, "lastPlayed")}>
          {lastCard && props.lastPlayed ? <GameCard card={lastCard} characterId={props.lastPlayed.character_id} cardId={lastCard.card_id} cost={lastCard.cost} index={lastCard.card_id - 1} discardState="none" /> : <div className="empty-played"><span>LAST PLAYED</span><b>等待出牌</b></div>}
        </div>
        <AnimatePresence mode="wait">
          <motion.div 
            className="turn-banner"
            key={String(match.current_phase) + String(myTurn)}
            initial={{ opacity: 0, scale: 0.8, filter: "blur(10px)", backgroundColor: "rgba(0,0,0,0)" }}
            animate={{ 
              opacity: [0, 1, 1, 0], 
              scale: [0.8, 1, 1, 1.1], 
              filter: ["blur(10px)", "blur(0px)", "blur(0px)", "blur(10px)"],
              backgroundColor: ["rgba(0,0,0,0)", "rgba(0,0,0,0.7)", "rgba(0,0,0,0.7)", "rgba(0,0,0,0)"]
            }}
            transition={{ duration: 2, times: [0, 0.15, 0.85, 1], ease: "easeInOut" }}
          >
            <div className="turn-banner-content">
              <i /><span>{myTurn ? "你的回合" : `${opponent?.display_name || `玩家 ${opponentId}`} 行动中`}</span><i />
            </div>
            <small>{match.current_phase}</small>
          </motion.div>
        </AnimatePresence>
      </section>

      <section className="player-zone">
        <div className="layout-region own-status-region" data-region="ownStatus" style={{ transform: `translate(${regionOffsets.ownStatus.x}px, ${regionOffsets.ownStatus.y}px)` }} onPointerDown={(event) => startRegionDrag(event, "ownStatus")}>
          <PlayerStatus label={`${me?.display_name || `玩家 ${match.player_id}`} · 你`} character={myCharacter} player={me} active={myTurn} teamClass={teamClassFor(me?.team_id)} />
          <div className="layout-region status-piles" data-region="piles" style={{ transform: `translate(${regionOffsets.piles.x}px, ${regionOffsets.piles.y}px)` }} onPointerDown={(event) => startRegionDrag(event, "piles")}>
            <button type="button" className="pile-button" onClick={() => setDeckViewer("draw")}><Pile label="抽牌" count={match.you.draw_count} /></button>
            <button type="button" className="pile-button" onClick={() => setDeckViewer("discard")}><Pile label="弃牌" count={match.you.discard_count} /></button>
          </div>
        </div>
        <div className="hand-stage">
          <div className="hand-toolbar">
            <GameTooltip className="hand-limit-tooltip" explanation={GAME_TERMS.handLimit}><span>{effectiveHandSize} / {match.hand_limit} 有效手牌{excessCards > 0 && <em>还需弃 {excessCards} 张</em>}</span></GameTooltip>
          </div>
          <div className={`hand-cards ${handView === "creatures" ? "creature-view" : ""} ${selectingDiscard ? "selecting-discard" : ""}`}>
            <AnimatePresence>
              {[...visibleHandCards.map((cardId) => ({ kind: "card" as const, cardId })), ...visibleCreatures.map((creature) => ({ kind: "creature" as const, creature }))].map((item, rawIndex) => {
                if (item.kind === "creature") {
                  const creatureIndex = creatures.indexOf(item.creature);
                  const activeTarget = activePlayTarget?.source === "creature" && activePlayTarget.index === creatureIndex;
                  const totalCards = visibleCreatures.length;
                  const middleIndex = (totalCards - 1) / 2;
                  const dist = rawIndex - middleIndex;
                  const spread = Math.min(130, 900 / Math.max(1, totalCards));
                  const index = rawIndex;
                  const translateX = dist * spread;
                  const translateY = Math.abs(dist) * Math.abs(dist) * (spread < 100 ? 2.5 : 1.5);
                  const rotate = dist * (spread < 100 ? 5 : 3.5);
                  return (
                    <motion.button layout="position" key={`creature-${item.creature.card_id}-${creatureIndex}`} initial={{ opacity: 0, y: 150, x: translateX - 50, scale: 0.5, rotate: -30 }} animate={{ opacity: 1, y: activeTarget ? translateY - 55 : translateY, x: translateX, scale: activeTarget ? 1.2 : 1, rotate: activeTarget ? 0 : rotate, zIndex: activeTarget ? 60 : index }} exit={{ opacity: 0, y: -200, scale: 1.2, transition: { duration: .15 } }} transition={{ type: "tween", ease: "circOut", duration: .2 }} whileHover={{ y: translateY - 80, scale: 1.35, rotate: 0, zIndex: 100 }} aria-pressed={activeTarget} className={`hand-card-button creature-hand-button ${activeTarget ? "press-selected" : ""}`} type="button" disabled={!canPlay} onMouseDown={() => beginPress("creature", creatureIndex)} onMouseUp={() => confirmPress("creature", creatureIndex)} onMouseLeave={() => cancelPress("creature", creatureIndex)}>
                      <GameCard card={getCard(myCharacter, item.creature.card_id)} characterId={myCharacter} cardId={item.creature.card_id} cost={null} index={rawIndex} discardState="none" creatureHealth={item.creature.health} creatureShell={item.creature.shell} />
                    </motion.button>
                  );
                }
                const index = rawIndex;
                const cardId = item.cardId;
                const card = getCard(myCharacter, cardId);
                const cost = match.you.card_costs?.[index] ?? card?.cost ?? null;
                const discardable = match.you.card_discardable?.[index] ?? ![49, 50].includes(cardId);
                const selected = discardSelection.includes(index);
                const activeTarget = !selectingDiscard && activePlayTarget?.source === "hand" && activePlayTarget.index === index;
                const discardTarget = selectingDiscard && activeDiscardTarget?.index === index;
                
                const totalCards = handView === "cards" ? visibleHandCards.length : visibleCreatures.length;

                // Calculate arc geometry explicitly with dynamic spread
                const middleIndex = (totalCards - 1) / 2;
                const dist = index - middleIndex;
                
                // Dynamically adjust spacing based on hand size to prevent overlapping too much
                // Max safe width is ~900px. If hand is small, spread them comfortably by 130px.
                const spread = Math.min(130, 900 / Math.max(1, totalCards)); 
                const translateX = dist * spread;
                
                // Adjust arc height multiplier based on how packed the cards are
                const translateY = Math.abs(dist) * Math.abs(dist) * (spread < 100 ? 2.5 : 1.5);
                const rotate = dist * (spread < 100 ? 5 : 3.5);

                return (
                  <motion.button
                    layout="position"
                    initial={{ opacity: 0, y: 150, x: translateX - 50, scale: 0.5, rotate: -30 }}
                    animate={{ 
                      opacity: 1, 
                      y: activeTarget ? translateY - 55 : selected ? translateY - 40 : translateY,
                      x: translateX, 
                      scale: activeTarget ? 1.2 : selected ? 1.1 : 1,
                      rotate: activeTarget || selected ? 0 : rotate,
                      zIndex: activeTarget ? 60 : selected ? 50 : index,
                    }}
                    exit={{ opacity: 0, y: -200, scale: 1.2, transition: { duration: 0.15 } }}
                    transition={{ type: "tween", ease: "circOut", duration: 0.2 }}
                    whileHover={{ 
                      y: translateY - 80, 
                      scale: 1.35, 
                      rotate: 0, 
                      zIndex: 100, 
                      transition: { type: "tween", ease: "easeOut", duration: 0.1 } 
                    }}
                    aria-pressed={activeTarget || discardTarget}
                    className={`hand-card-button ${activeTarget || discardTarget ? "press-selected" : ""} ${!selectingDiscard && handRelayouting ? "relayout" : ""}`}
                    key={`${cardId}-${index}`}
                    type="button"
                    disabled={selectingDiscard ? !myTurn || match.pending_choice || !discardable : !canPlay}
                    onMouseDown={() => { if (selectingDiscard) beginDiscardPress(index); else beginPress("hand", index); }}
                    onMouseUp={() => { if (selectingDiscard) confirmDiscardPress(index); else confirmPress("hand", index); }}
                    onMouseLeave={() => { if (selectingDiscard) cancelDiscardPress(index); else cancelPress("hand", index); }}
                    onTouchStart={(event) => { event.preventDefault(); if (selectingDiscard) beginDiscardPress(index); else beginPress("hand", index); }}
                    onTouchEnd={(event) => { event.preventDefault(); if (selectingDiscard) confirmDiscardPress(index); else confirmPress("hand", index); }}
                    onTouchCancel={() => { if (selectingDiscard) cancelDiscardPress(index); else cancelPress("hand", index); }}
                    onKeyDown={(event) => {
                      if (event.key !== "Enter" && event.key !== " ") return;
                      event.preventDefault();
                      if (selectingDiscard) {
                        beginDiscardPress(index);
                        confirmDiscardPress(index);
                      } else {
                        beginPress("hand", index);
                        confirmPress("hand", index);
                      }
                    }}
                  >
                    <GameCard card={card} characterId={myCharacter} cardId={cardId} cost={cost} index={index} discardState="none" />
                  </motion.button>
                );
              })}
            </AnimatePresence>
          </div>
        </div>
        <div className="log-actions layout-region" data-region="actionPanel" style={{ transform: `translate(calc(-50% + ${regionOffsets.actionPanel.x}px), calc(0px + ${regionOffsets.actionPanel.y}px))` }} onPointerDown={(event) => startRegionDrag(event, "actionPanel")}>
          <button type="button" className={`discard-toggle ${discardMode ? "active" : ""}`} disabled={!myTurn || match.pending_choice || forcedDiscard || !inPlay} onClick={() => { setActiveDiscardTarget(null); setDiscardDraft({ revision: match.revision, activePlayerId: match.active_player_id, mode: !manualDiscardMode, indexes: [] }); }}>{discardMode ? "退出弃牌" : "进入弃牌"}</button>
          <button type="button" className={`hand-view-toggle ${handView === "creatures" ? "active" : ""}`} aria-label={handView === "cards" ? "切换到手中生物" : "切换到手牌"} onClick={() => setHandView(handView === "cards" ? "creatures" : "cards")}>{handView === "cards" ? `生 ${creatures.length}` : `牌 ${match.you.hand_cards.length}`}</button>
          <button type="button" className="turn-end" disabled={!myTurn || match.pending_choice || forcedDiscard || (!inPlay && !inDiscard && excessCards === 0)} onClick={() => { setDiscardDraft({ revision: match.revision, activePlayerId: match.active_player_id, mode: false, indexes: [] }); props.send("end_turn"); }}>{forcedDiscard ? "弃牌中…" : excessCards > 0 ? `还需弃 ${excessCards} 张` : "结束回合"} <b>→</b></button>
        </div>
        <div className="interface-actions">
          <button type="button" className="icon-button" aria-label="打开牌图鉴" title="牌图鉴" onClick={() => setCodexOpen(true)}>📖</button>
          <button type="button" className="icon-button layout-reset" aria-label="复位界面布局" title="复位界面布局" onClick={resetRegionOffsets}>⟲</button>
          <button type="button" className="icon-button settings-toggle" aria-label="打开界面设置" title="界面设置" onClick={() => setSettingsOpen(true)}>⚙</button>
        </div>
        <div className="layout-region log-region" data-region="logPanel" style={{ position: "fixed", right: 40, bottom: 40, transform: `translate(${regionOffsets.logPanel.x}px, ${regionOffsets.logPanel.y}px)` }} onPointerDown={(event) => startRegionDrag(event, "logPanel")}>
          <LogPanel logs={props.logs} chatText={props.chatText} setChatText={props.setChatText} submitChat={props.submitChat} />
        </div>
      </section>
      {props.children}
      {localNotice && <Notice message={localNotice} close={() => setLocalNotice(null)} />}
      {settingsOpen && (
      <SettingsDialog
          layout={props.layout}
          interaction={props.interaction}
          onChangeLayout={updateMatchLayout}
          onChangeInteraction={updateMatchInteraction}
          close={() => setSettingsOpen(false)}
        />
      )}
      {deckViewer && (
        <div className="modal-backdrop" onClick={() => setDeckViewer(null)} role="presentation">
          <section className="choice-dialog deck-viewer" role="dialog" aria-modal="true" aria-labelledby="deck-viewer-title" onClick={(event) => event.stopPropagation()}>
            <p className="eyebrow">DECK VIEW</p>
            <h2 id="deck-viewer-title">{deckViewer === "draw" ? "抽牌堆" : "弃牌堆"}</h2>
            <p>{deckViewer === "draw" ? "按卡牌类型分组显示当前抽牌堆。" : "按卡牌类型分组显示当前弃牌堆。"} 共 {groupedViewerCards.reduce((total, [, cards]) => total + cards.reduce((sum, item) => sum + item.count, 0), 0)} 张 · {groupedViewerCards.length} 类。</p>
            {groupedViewerCards.length === 0 ? (
              <p className="muted">当前牌堆为空。</p>
            ) : (
              groupedViewerCards.map(([type, cards]) => (
                <section key={type} className="deck-group">
                  <h3>{type} · {cards.reduce((total, item) => total + item.count, 0)}</h3>
                  <div className="deck-grid">
                    {cards.map(({ card, count }) => {
                      const cardId = card.card_id;
                      return (
                        <button
                          key={cardId}
                          type="button"
                          className="deck-card-button"
                          title="右键查看放大卡面"
                          onContextMenu={(event) => { event.preventDefault(); setPreviewedCard({ card, count }); }}
                        >
                          <GameCard card={card} characterId={myCharacter} cardId={cardId} cost={card.cost} index={count - 1} discardState="none" stackCount={count > 1 ? count : undefined} />
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))
            )}
          </section>
        </div>
      )}
      {previewedCard && (
        <div className="modal-backdrop card-preview-backdrop" onClick={() => setPreviewedCard(null)} role="presentation">
          <div className="card-preview" onClick={(event) => event.stopPropagation()} onKeyDown={(event) => event.stopPropagation()} role="presentation">
            <div className="card-preview-card">
              <GameCard card={previewedCard.card} characterId={myCharacter} cardId={previewedCard.card.card_id} cost={previewedCard.card.cost} index={previewedCard.card.card_id - 1} discardState="none" />
            </div>
            <button type="button" className="card-preview-close" onClick={() => setPreviewedCard(null)}>关闭预览</button>
          </div>
        </div>
      )}
      {codexOpen && (
        <div className="modal-backdrop" onClick={() => setCodexOpen(false)} role="presentation">
          <section className="choice-dialog deck-viewer codex-viewer" role="dialog" aria-modal="true" aria-labelledby="codex-title" onClick={(event) => event.stopPropagation()}>
            <p className="eyebrow">CARD CODEX</p>
            <h2 id="codex-title">牌图鉴</h2>
            <p>按分类查看当前角色的全部卡牌与能力解锁条件。</p>
            {codexGroups.map(([type, cards]) => (
              <section key={type} className="deck-group">
                <h3>{type} · {cards.length}</h3>
                <div className="deck-grid">
                  {cards.map((card) => (
                    <button
                      key={card.card_id}
                      type="button"
                      className="deck-card-button"
                      title="右键查看放大卡面"
                      onContextMenu={(event) => { event.preventDefault(); setPreviewedCard({ card, count: 1 }); }}
                    >
                      <GameCard card={card} characterId={myCharacter} cardId={card.card_id} cost={card.cost} index={card.card_id - 1} discardState="none" />
                    </button>
                  ))}
                </div>
              </section>
            ))}
          </section>
        </div>
      )}
    </main>
  );
}

function PlayerStatus({ label, character, player, active, teamClass }: { label: string; character: number; player: PublicPlayer; active: boolean; teamClass?: string }) {
  const name = character === 1 ? "战士" : character === 4 ? "蛞蝓猫" : `角色 ${character}`;
  const data = player.character_data ?? {};
  const maxHealth = Math.max(1, player.max_health ?? (character === 4 ? 5 : 30));
  const healthPercent = Math.max(0, Math.min(100, player.health / maxHealth * 100));
  const healthTone = healthPercent <= 25 ? "critical" : healthPercent <= 50 ? "wounded" : "healthy";
  const detail = Object.entries(data)
    .filter(([key, value]) => typeof value === "number" && statusExplanation(key))
    .map(([key, value]) => ({
      key,
      value:
        key === "karma" && typeof data.karma_max === "number"
          ? `${value}/${data.karma_max}`
          : key === "satiety" && typeof data.satiety_max === "number"
            ? `${value}/${data.satiety_max}`
            : String(value),
    }));
  if (typeof data.form === "string") detail.unshift({ key: "form", value: data.form });
  return (
    <div className={`player-status ${active ? "active" : ""} ${teamClass ?? ""}`}>
      <div className="player-identity">
        <div className={`avatar char-${character}`}>{character === 1 ? "战" : "猫"}</div>
        <div className="identity"><small>{label}</small><strong>{name}</strong></div>
      </div>
      <GameTooltip className="energy-core" explanation={{ ...GAME_TERMS.energy, description: `当前拥有 ${player.energy} 点能量。${GAME_TERMS.energy.description}` }}>
        <span className="energy-glyph">◆</span><span className="energy-copy"><small>能量</small><strong>{player.energy}</strong></span>
      </GameTooltip>
      <div className="secondary-stats">
        {character !== 4 && (
          <>
            <Stat icon="⬟" label="防御" value={player.defence} tone="defence" explanation={GAME_TERMS.defence} />
            <Stat icon="↑" label="力量" value={player.strength} tone="strength" explanation={GAME_TERMS.strength} />
          </>
        )}
        {player.poison > 0 && <Stat icon="●" label="中毒" value={player.poison} tone="poison" explanation={GAME_TERMS.poison} />}
      </div>
      <GameTooltip className={`health-vital ${healthTone}`} explanation={{ ...GAME_TERMS.health, description: `当前生命为 ${player.health}/${maxHealth}。${GAME_TERMS.health.description}` }}>
        <span className="health-heading"><span><b>♥</b> 生命</span><strong>{player.health}<i>/{maxHealth}</i></strong></span>
        <span className="health-track" role="meter" aria-label={`${name}生命`} aria-valuemin={0} aria-valuemax={maxHealth} aria-valuenow={Math.max(0, Math.min(maxHealth, player.health))}>
          <span className="health-fill" style={{ width: `${healthPercent}%` }} />
        </span>
      </GameTooltip>
      {detail.length > 0 && <div className="status-detail-list">{detail.map(({ key, value }) => <GameTooltip key={key} explanation={statusExplanation(key) ?? GAME_TERMS.poison}><span className="status-detail"><small>{statusName(key)}</small><strong>{value}</strong></span></GameTooltip>)}</div>}
    </div>
  );
}

function Stat({ icon, label, value, tone, explanation }: { icon: string; label: string; value: number; tone: string; explanation: GameExplanation }) { return <GameTooltip className={`stat ${tone}`} explanation={explanation}><span className="stat-icon">{icon}</span><span className="stat-copy"><small>{label}</small><strong>{value}</strong></span></GameTooltip>; }
function Pile({ label, count }: { label: string; count: number }) { return <GameTooltip focusable={false} className="pile-tooltip" explanation={label === "抽牌" ? GAME_TERMS.drawPile : GAME_TERMS.discardPile}><span className="pile"><span>{label}</span><strong>{count}</strong></span></GameTooltip>; }
function statusName(key: string) { return ({ form: "形态", karma: "业力", satiety: "饱食", agility: "敏捷", momentum: "动能", sacrifice_layers: "献祭", heartlink_layers: "心连心" } as Record<string, string>)[key] ?? key; }

function RuleText({ text }: { text: string }) {
  return <>{text.split(inlineRulePattern).map((part, index) => {
    const entry = INLINE_RULE_TERMS.find(({ term }) => term === part);
    return entry
      ? <GameTooltip key={`${part}-${index}`} focusable={false} className="rule-keyword" explanation={entry.explanation}><span>{part}</span></GameTooltip>
      : part;
  })}</>;
}

function cardTone(type = "卡牌") { return type.includes("物品") ? "item" : type.includes("生物") ? "creature" : type.includes("见闻") ? "discovery" : type.includes("技能") ? "skill" : "attack"; }

function cardImage(characterId: number, cardId: number) {
  return characterId === 1 ? `/cards/1/img-${cardId}.jpg` : null;
}

function GameCard({ card, characterId = 1, cardId, cost, index, discardState, creatureHealth, creatureShell, stackCount }: { card?: CardDefinition; characterId?: number; cardId: number; cost: number | null; index: number; discardState: "none" | "available" | "selected" | "blocked"; creatureHealth?: number; creatureShell?: boolean; stackCount?: number }) {
  const cardType = card?.card_type ?? "卡牌";
  const image = card ? cardImage(characterId, card.card_id) : null;
  const discardLabel = discardState === "selected" ? "− 退回" : discardState === "blocked" ? "不可弃置" : "+ 选择弃置";
  if (image) {
    // 有完整卡面的角色（战士）直接展示图片，数值都在图上，不再包一层外观。
    return <article className={`game-card game-card-image ${discardState !== "none" ? "discard-mode" : ""} ${discardState === "selected" ? "discard-selected" : ""}`}>
      <Image className="card-art-image" src={image} alt="" width={320} height={220} />
      {typeof stackCount === "number" && <span className="stack-count-badge">× {stackCount}</span>}
      {discardState !== "none" && <em>{discardLabel}</em>}
    </article>;
  }
  return <article className={`game-card ${cardTone(cardType)} ${discardState !== "none" ? "discard-mode" : ""} ${discardState === "selected" ? "discard-selected" : ""}`}>
    <div className="card-top">
      <GameTooltip focusable={false} className="card-type-tooltip" explanation={cardTypeExplanation(cardType)}><span>{cardType}</span></GameTooltip>
      <div className="card-flags">
        {card?.exhausted && <GameTooltip focusable={false} className="exhaust-tooltip" explanation={GAME_TERMS.exhaust}><span>消耗</span></GameTooltip>}
        <GameTooltip focusable={false} className="card-cost-tooltip" explanation={cardCostExplanation(cost, card?.cost)}><b>{cost ?? "—"}</b></GameTooltip>
      </div>
    </div>
    {typeof card?.unlock_condition === "string" && <span className="unlock-condition">解锁：{card.unlock_condition}</span>}
    {image ? <Image className="card-art-image" src={image} alt="" width={320} height={220} /> : <div className="card-art"><span>{card?.name?.slice(0, 1) ?? "?"}</span></div>}
    {typeof creatureHealth === "number" && <span className="creature-health-badge">♥ {creatureHealth}{creatureShell === false ? " · 破甲" : ""}</span>}
    <div className="card-copy"><strong>{card?.name ?? `卡牌 ${cardId}`}</strong><p><RuleText text={card?.description || "暂无卡牌说明"} /></p></div>
    {typeof stackCount === "number" && <span className="stack-count-badge">× {stackCount}</span>}
    <small>#{String(index + 1).padStart(2, "0")} · ID {cardId}</small>
    {discardState !== "none" && <em>{discardLabel}</em>}
  </article>;
}

function CreatureChip({ creature, card }: { creature: Creature; card?: CardDefinition }) {
  if (!card) return null;
  return <div className="creature-chip">
    <div>
      <strong>{card.name}</strong>
      <GameTooltip focusable={false} explanation={GAME_TERMS.creatureHealth}>
        <small>♥ {creature.health}{creature.shell === false ? " · 破甲" : ""}</small>
      </GameTooltip>
    </div>
  </div>;
}

function SettingsDialog({ layout, interaction, onChangeLayout, onChangeInteraction, close }: {
  layout: LayoutSettings;
  interaction: InteractionSettings;
  onChangeLayout: (patch: Partial<LayoutSettings>) => void;
  onChangeInteraction: (patch: Partial<InteractionSettings>) => void;
  close: () => void;
}) {
  const updateLayout = (next: Partial<LayoutSettings>) => onChangeLayout(next);
  const updateInteraction = (next: Partial<InteractionSettings>) => onChangeInteraction(next);
  return <div className="modal-backdrop">
    <section className="choice-dialog settings-dialog" role="dialog" aria-modal="true" aria-labelledby="layout-settings-title">
      <p className="eyebrow">INTERFACE</p>
      <h2 id="layout-settings-title">界面与出牌设置</h2>
      <div className="settings-grid">
        {[["cardHeight", "手牌高度", 170, 340], ["cardWidth", "手牌宽度", 120, 220], ["chatFontSize", "聊天字号", 11, 20], ["chatHeight", "聊天高度", 200, 460], ["sideColumnWidth", "侧栏宽度", 260, 480]].map(([key, label, minimum, maximum]) => (
          <label key={key as string}>
            <span>{label as string}<b>{layout[key as keyof LayoutSettings]}</b></span>
            <input type="range" min={minimum as number} max={maximum as number} value={layout[key as keyof LayoutSettings]} onChange={(event) => onChangeLayout({ [key as keyof LayoutSettings]: Number(event.target.value) } as Partial<LayoutSettings>)} />
          </label>
        ))}
      </div>
      <fieldset>
        <legend>出牌方式</legend>
        <div className="segmented">
          {[["double", "双击出牌"], ["single", "松开出牌"]].map(([value, label]) => (
            <button key={value} type="button" className={interaction.clickMode === value ? "active" : ""} onClick={() => onChangeInteraction({ clickMode: value as InteractionSettings["clickMode"] })}>{label}</button>
          ))}
        </div>
        <label className="settings-delay">
          <span>出牌间隔<b>{interaction.playGapMs}ms</b></span>
          <input type="range" min={260} max={2000} step={20} value={interaction.playGapMs} onChange={(event) => onChangeInteraction({ playGapMs: Number(event.target.value) })} />
        </label>
        <small>松开模式：按住后移出卡牌会取消，在原牌上松开才打出。双击模式：第一次点击选中，500ms 内再次点击确认。两种模式都会保留出牌间隔。</small>
      </fieldset>
      <footer><button type="button" onClick={() => { updateLayout(DEFAULT_LAYOUT_SETTINGS); updateInteraction(DEFAULT_INTERACTION_SETTINGS); }}>恢复默认</button><button type="button" className="primary-action" onClick={close}>完成</button></footer>
    </section>
  </div>;
}

function LogPanel({ logs, chatText, setChatText, submitChat, compact = false, handView, creatureCount, cardCount, onChangeHandView }: { logs: LogEntry[]; chatText: string; setChatText: (value: string) => void; submitChat: (event: FormEvent) => void; compact?: boolean; handView?: "cards" | "creatures"; creatureCount?: number; cardCount?: number; onChangeHandView?: (view: "cards" | "creatures") => void }) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);
  return <section className={`log-panel ${compact ? "compact" : ""}`}>
    <div className="log-heading"><span>对局记录</span><small>LIVE LOG</small></div>
    <div className="log-scroll">{logs.length ? logs.map((entry) => <p key={entry.id} className={entry.tone}><i />{entry.text}</p>) : <p className="muted"><i />等待消息…</p>}<div ref={endRef} /></div>
    {handView && onChangeHandView && (
      <button
        type="button"
        className={`hand-view-toggle ${handView === "creatures" ? "active" : ""}`}
        aria-label={handView === "cards" ? `切换到手中生物，共 ${creatureCount ?? 0} 张` : `切换到手牌，共 ${cardCount ?? 0} 张`}
        onClick={() => onChangeHandView(handView === "cards" ? "creatures" : "cards")}
      >
        <span>{handView === "cards" ? "生" : "牌"}</span>
        <b>{handView === "cards" ? creatureCount ?? 0 : cardCount ?? 0}</b>
      </button>
    )}
    <form onSubmit={submitChat}><input aria-label="聊天消息" value={chatText} onChange={(event) => setChatText(event.target.value)} maxLength={200} placeholder="发送消息…" /><button type="submit">发送</button></form>
  </section>;
}

function ChoiceDialog({ pending, value, setValue, selected, setSelected, match, resolve, cancel }: { pending: PendingChoice; value: number | string | null; setValue: (value: number | string | null) => void; selected: number[]; setSelected: (value: number[]) => void; match: MatchView; resolve: (value: unknown) => void; cancel: () => void }) {
  const prompt = pending.choice;
  const myCharacter = match.character_ids[String(match.player_id)];
  const catalog = match.card_catalogs?.[String(myCharacter)] ?? [];
  const cardById = (id: number) => catalog.find((card) => card.card_id === id);
  const integerMinimum = prompt.minimum ?? 0;
  const integerMaximum = prompt.maximum ?? integerMinimum;
  const integerValue = Number(value ?? prompt.default ?? integerMinimum);
  const setInteger = (nextValue: number) => setValue(Math.max(integerMinimum, Math.min(integerMaximum, nextValue)));
  const choiceComplete = prompt.kind === "integer"
    ? Number.isInteger(integerValue) && integerValue >= integerMinimum && integerValue <= integerMaximum
    : prompt.kind === "option"
      ? prompt.options?.includes(String(value)) === true
      : selected.length === (prompt.count ?? 0);
  const toggleIndex = (index: number) => {
    setSelected(toggleLimitedIndex(selected, index, prompt.count ?? 0));
  };
  return <div className="modal-backdrop"><section className="choice-dialog" role="dialog" aria-modal="true" aria-labelledby="choice-title"><p className="eyebrow">ACTION REQUIRED</p><h2 id="choice-title">{prompt.title}</h2><p><RuleText text={prompt.prompt} /></p>
    {prompt.kind === "integer" && <div className="integer-choice"><div className="integer-stepper"><button type="button" aria-label="减少选择数" disabled={integerValue <= integerMinimum} onClick={() => setInteger(integerValue - 1)}>−</button><strong>{integerValue}</strong><button type="button" aria-label="增加选择数" disabled={integerValue >= integerMaximum} onClick={() => setInteger(integerValue + 1)}>+</button></div><input aria-label={prompt.prompt} type="range" min={integerMinimum} max={integerMaximum} value={integerValue} onChange={(event) => setInteger(Number(event.target.value))} /><div><span>{integerMinimum}</span><span>{integerMaximum}</span></div></div>}
    {prompt.kind === "option" && <div className="option-choice">{prompt.options?.map((option) => <button className={value === option ? "selected" : ""} type="button" key={option} onClick={() => setValue(option)}>{option}</button>)}</div>}
    {prompt.kind === "card_indexes" && <><div className="choice-progress"><span>已选择 {selected.length} / {prompt.count ?? 0}</span><small>再次点击带“−”的卡牌即可退回</small></div><div className="choice-cards">{prompt.hand?.map((cardId, index) => { const excluded = cardId === prompt.excluded_card_id; const isSelected = selected.includes(index); const limitReached = selected.length >= (prompt.count ?? 0); return <button aria-pressed={isSelected} type="button" key={`${cardId}-${index}`} disabled={excluded || (!isSelected && limitReached)} className={isSelected ? "selected" : ""} onClick={() => toggleIndex(index)}><span>{cardById(cardId)?.name ?? `卡牌 ${cardId}`}</span><small>索引 {index + 1}{excluded ? " · 不可选" : ""}</small><b>{isSelected ? "− 退回" : "+ 选择"}</b></button>; })}</div></>}
    <footer><button type="button" className="ghost-action" onClick={cancel}>取消动作</button><button type="button" className="primary-action" disabled={!choiceComplete} onClick={() => resolve(prompt.kind === "card_indexes" ? selected : prompt.kind === "integer" ? integerValue : value)}>确认选择 <span>→</span></button></footer>
  </section></div>;
}

function Notice({ message, close }: { message: string; close: () => void }) { 
  return (
    <motion.div 
      className="notice" 
      role="alert"
      initial={{ opacity: 0, x: 50, scale: 0.9 }}
      animate={{ opacity: 1, x: 0, scale: 1 }}
      exit={{ opacity: 0, x: 50, scale: 0.9 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
    >
      <span>!</span><p>{message}</p><button type="button" onClick={close}>×</button>
    </motion.div>
  ); 
}
