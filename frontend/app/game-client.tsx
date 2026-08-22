"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { motion, AnimatePresence } from "framer-motion";

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
type RoomPlayer = { player_id: number; character_id: number | null; ready: boolean };
type RoomView = {
  room_code: string;
  status: string;
  settings: { first_player: string; seed: number | null; round1_no_damage: boolean };
  players: RoomPlayer[];
  characters: CharacterOption[];
};

type CardDefinition = {
  card_id: number;
  name: string;
  card_type: string;
  cost: number | null;
  description: string;
  exhausted: boolean;
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
  statuses: {
    hand_creatures: Creature[];
    creature_threats: Creature[];
    [key: string]: unknown;
  };
  character_data: Record<string, unknown> | null;
};

type MatchView = {
  room_code: string;
  revision: number;
  player_id: number;
  character_ids: Record<string, number>;
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
    card_costs?: Array<number | null>;
    card_discardable?: boolean[];
    effective_hand_size?: number;
    draw_count: number;
    discard_count: number;
  };
  opponent: { hand_count: number; draw_count: number; discard_count: number };
};

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

const phaseIndex: Record<string, number> = {
  "回合开始时": 0,
  "抽牌阶段": 1,
  "出牌阶段": 2,
  "弃牌阶段": 3,
  "回合结束时": 4,
};

const phases = ["回合开始", "抽牌", "出牌", "弃牌", "回合结束"];
const inlineRulePattern = new RegExp(`(${INLINE_RULE_TERMS.map(({ term }) => term).join("|")})`, "g");

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
  const [endpoint, setEndpoint] = useState(defaultEndpoint);
  const [connection, setConnection] = useState<ConnectionStatus>("idle");
  const [playerId, setPlayerId] = useState<number | null>(null);
  const [room, setRoom] = useState<RoomView | null>(null);
  const [match, setMatch] = useState<MatchView | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [chatText, setChatText] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [notice, setNotice] = useState<string | null>(null);
  const [lastPlayed, setLastPlayed] = useState<{ character_id: number; card_id: number } | null>(null);
  const [choice, setChoice] = useState<PendingChoice | null>(null);
  const [choiceValue, setChoiceValue] = useState<number | string | null>(null);
  const [selectedIndexes, setSelectedIndexes] = useState<number[]>([]);
  const [firstPlayer, setFirstPlayer] = useState("random");
  const [seed, setSeed] = useState("");
  const [roundOneSafe, setRoundOneSafe] = useState(true);

  const addLog = (text: string, tone = "normal") => {
    setLogs((current) => [
      ...current.slice(-119),
      { id: ++logCounter.current, tone, text },
    ]);
  };

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
        setMatch(null);
        setFirstPlayer(nextRoom.settings.first_player);
        setSeed(nextRoom.settings.seed === null ? "" : String(nextRoom.settings.seed));
        setRoundOneSafe(nextRoom.settings.round1_no_damage);
        break;
      }
      case "match_started":
        setMatch(data.state as MatchView);
        setRoom(null);
        setChoice(null);
        if (!(data.state as MatchView).card_catalogs) {
          setNotice("后端进程尚未提供卡牌目录；请重启 card-duel-web 以显示完整卡面");
        }
        addLog("对局开始", "turn");
        break;
      case "state": {
        const nextMatch = data.state as MatchView;
        setMatch(nextMatch);
        if (!nextMatch.pending_choice) {
          setChoice(null);
          setSelectedIndexes([]);
        }
        break;
      }
      case "chat":
        addLog(`玩家${data.player_id}：${data.message}`, "chat");
        break;
      case "announcement":
        addLog(String(data.message), /伤害|失去|流血/.test(String(data.message)) ? "damage" : "normal");
        break;
      case "private_announcement":
        addLog(String(data.message), "private");
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
    send("configure_room", {
      first_player: firstPlayer,
      seed: numericSeed,
      round1_no_damage: roundOneSafe,
    });
  };

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
        seed={seed}
        setSeed={setSeed}
        roundOneSafe={roundOneSafe}
        setRoundOneSafe={setRoundOneSafe}
        configureRoom={configureRoom}
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
                <button type="button" className="mode-card" onClick={() => send("create_room")}>
                  <small>HOST</small><strong>创建房间</strong><span>生成 6 位房间号</span>
                </button>
                <div className="mode-card join-card">
                  <small>JOIN</small><strong>加入对局</strong>
                  <div><input aria-label="房间号" maxLength={6} placeholder="000000" value={joinCode} onChange={(event) => setJoinCode(event.target.value.replace(/\D/g, ""))} />
                  <button type="button" onClick={() => send("join_room", { room_code: joinCode })}>→</button></div>
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
  seed: string; setSeed: (value: string) => void; roundOneSafe: boolean;
  setRoundOneSafe: (value: boolean) => void; configureRoom: () => void;
  children: ReactNode;
}) {
  const { room, playerId, send } = props;
  const local = room.players.find((player) => player.player_id === playerId);
  const isHost = playerId === 1;
  return (
    <main className="lobby-shell">
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
              return <button key={character.character_id} type="button" disabled={!implemented} className={`character-card char-${character.character_id} ${selected ? "selected" : ""}`} onClick={() => send("select_character", { character_id: character.character_id })}>
                <span className="character-number">0{character.character_id}</span><div className="character-glyph">{character.character_id === 1 ? "战" : character.character_id === 4 ? "猫" : "?"}</div><small>{implemented ? "PLAYABLE" : "IN DEVELOPMENT"}</small><strong>{character.name}</strong><p><RuleText text={character.character_id === 1 ? "防御 · 力量 · 献祭" : character.character_id === 4 ? "敏捷 · 业力 · 生物" : "角色机制开发中"} /></p>{selected && <b>已选择</b>}
              </button>;
            })}
          </div>

          <div className="player-slots">
            {[1, 2].map((id) => {
              const player = room.players.find((item) => item.player_id === id);
              const character = room.characters.find((item) => item.character_id === player?.character_id);
              return <div className={`player-slot ${player?.ready ? "ready" : ""}`} key={id}><span>玩家 {id} · {id === 1 ? "房主" : "客机"}</span><strong>{player ? character?.name ?? "未选择角色" : "等待加入…"}</strong><i>{player?.ready ? "READY" : player ? "NOT READY" : "EMPTY"}</i></div>;
            })}
          </div>
        </div>

        <aside className="lobby-sidebar">
          <div className="rules-panel">
            <div className="panel-heading"><span>房间规则</span><b>02</b></div>
            <span className="rule-label">先手方</span>
            <div className="segmented">{[["host", "房主"], ["guest", "客机"], ["random", "随机"]].map(([value, label]) => <button key={value} type="button" disabled={!isHost} className={props.firstPlayer === value ? "active" : ""} onClick={() => props.setFirstPlayer(value)}>{label}</button>)}</div>
            <label htmlFor="match-seed">随机种子</label>
            <input id="match-seed" className="rule-input" disabled={!isHost} placeholder="留空则随机" value={props.seed} onChange={(event) => props.setSeed(event.target.value)} />
            <div className="toggle-row"><label htmlFor="round-one-safe"><strong>首回合无伤</strong><small>先手第一回合无法扣除对方生命</small></label><input id="round-one-safe" aria-label="首回合无伤" type="checkbox" disabled={!isHost} checked={props.roundOneSafe} onChange={(event) => props.setRoundOneSafe(event.target.checked)} /></div>
            {isHost && <button className="secondary-action" type="button" onClick={props.configureRoom}>应用房间规则</button>}
          </div>
          <LogPanel logs={props.logs} chatText={props.chatText} setChatText={props.setChatText} submitChat={props.submitChat} compact />
        </aside>
      </section>
      <div className="lobby-ready-bar"><p>{local?.character_id ? `已选择 ${room.characters.find((item) => item.character_id === local.character_id)?.name}` : "请先选择角色"}</p><button type="button" disabled={!local?.character_id} className={local?.ready ? "ready-active" : ""} onClick={() => send("set_ready", { ready: !local?.ready })}>{local?.ready ? "取消准备" : "准备对局"}<span>→</span></button></div>
      {props.children}
    </main>
  );
}

function MatchScreen(props: {
  match: MatchView; logs: LogEntry[]; chatText: string; setChatText: (value: string) => void;
  submitChat: (event: FormEvent) => void; send: (action: string, data?: Record<string, unknown>) => void;
  lastPlayed: { character_id: number; card_id: number } | null; connection: ConnectionStatus; children: ReactNode;
}) {
  const { match } = props;
  const [discardDraft, setDiscardDraft] = useState({
    revision: match.revision,
    activePlayerId: match.active_player_id,
    mode: false,
    indexes: [] as number[],
  });
  const me = match.players[String(match.player_id)];
  const opponentId = match.player_id === 1 ? 2 : 1;
  const opponent = match.players[String(opponentId)];
  const myCharacter = match.character_ids[String(match.player_id)];
  const opponentCharacter = match.character_ids[String(opponentId)];
  const myTurn = match.active_player_id === match.player_id;
  const inPlay = match.current_phase === "出牌阶段";
  const inDiscard = match.current_phase === "弃牌阶段";
  const draftIsCurrent = discardDraft.revision === match.revision && discardDraft.activePlayerId === match.active_player_id;
  const discardMode = draftIsCurrent && discardDraft.mode;
  const discardSelection = draftIsCurrent ? discardDraft.indexes : [];
  const selectingDiscard = discardMode || inDiscard;
  const effectiveHandSize = match.you.effective_hand_size ?? match.you.hand_cards.length;
  const excessCards = Math.max(0, effectiveHandSize - match.hand_limit);
  const currentPhase = phaseIndex[match.current_phase ?? ""] ?? -1;
  const catalogs = match.card_catalogs ?? {};
  const getCard = (characterId: number, cardId: number) => catalogs[String(characterId)]?.find((card) => card.card_id === cardId);
  const lastCard = props.lastPlayed ? getCard(props.lastPlayed.character_id, props.lastPlayed.card_id) : null;
  const creatures = me.statuses.hand_creatures.filter((creature) => creature.card_id !== 26);

  const toggleDiscard = (index: number) => {
    const discardable = match.you.card_discardable?.[index] ?? ![49, 50].includes(match.you.hand_cards[index]);
    if (!discardable) return;
    setDiscardDraft((current) => {
      const currentIndexes = current.revision === match.revision && current.activePlayerId === match.active_player_id ? current.indexes : [];
      return {
        revision: match.revision,
        activePlayerId: match.active_player_id,
        mode: true,
        indexes: toggleLimitedIndex(currentIndexes, index, match.you.hand_cards.length),
      };
    });
  };

  const startDiscard = () => setDiscardDraft({ revision: match.revision, activePlayerId: match.active_player_id, mode: true, indexes: [] });
  const clearDiscard = () => setDiscardDraft({ revision: match.revision, activePlayerId: match.active_player_id, mode: inDiscard, indexes: [] });

  const confirmDiscard = () => {
    if (!discardSelection.length) return;
    props.send("discard_cards", { indexes: [...discardSelection].sort((left, right) => left - right) });
  };

  return (
    <main className="match-shell">
      <header className="match-topbar"><Brand connection={props.connection} compact /><div className="turn-track">{phases.map((phase, index) => <div key={phase} className={`${index === currentPhase ? "active" : ""} ${index < currentPhase ? "done" : ""}`}><span>{index + 1}</span><GameTooltip className="phase-name" explanation={phaseExplanation(phase)}><b>{phase}</b></GameTooltip></div>)}</div><GameTooltip className="round-tooltip" explanation={{ title: "轮次", description: "双方各完成一个回合后，轮次增加。新轮次会重新分配双方能量。" }}><span className="round-chip"><small>ROUND</small><strong>{String(match.round_number).padStart(2, "0")}</strong></span></GameTooltip></header>

      <section className="opponent-zone">
        <PlayerStatus label={`玩家 ${opponentId}`} character={opponentCharacter} player={opponent} active={match.active_player_id === opponentId} />
        <div className="opponent-hand" aria-label={`对方有 ${match.opponent.hand_count} 张手牌`}>{Array.from({ length: Math.min(match.opponent.hand_count, 9) }).map((_, index) => <div key={index} style={{ transform: `translateX(${index * -14}px) rotate(${(index - match.opponent.hand_count / 2) * 2}deg)` }} />)}</div>
        <div className="opponent-piles"><Pile label="抽牌" count={match.opponent.draw_count} /><Pile label="弃牌" count={match.opponent.discard_count} /></div>
      </section>

      <section className="battlefield">
        <div className="creature-lane opponent-creatures">{opponent.statuses.hand_creatures.map((creature, index) => <CreatureChip key={`${creature.card_id}-${index}`} creature={creature} card={getCard(opponentCharacter, creature.card_id)} />)}</div>
        <div className="last-played">{lastCard ? <MiniCard card={lastCard} cost={lastCard.cost} /> : <div className="empty-played"><span>LAST PLAYED</span><b>等待出牌</b></div>}</div>
        <div className="creature-lane own-creatures">{creatures.map((creature, index) => <button key={`${creature.card_id}-${index}`} type="button" disabled={!myTurn || !inPlay || match.pending_choice} onClick={() => props.send("play_card", { source: "creature", index })}><CreatureChip creature={creature} card={getCard(myCharacter, creature.card_id)} /></button>)}</div>
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
              <i /><span>{myTurn ? "你的回合" : `玩家 ${opponentId} 行动中`}</span><i />
            </div>
            <small>{match.current_phase}</small>
          </motion.div>
        </AnimatePresence>
      </section>

      <section className="player-zone">
        <PlayerStatus label={`玩家 ${match.player_id} · 你`} character={myCharacter} player={me} active={myTurn} />
        <div className="hand-stage">
          <div className="hand-toolbar">
            <div><Pile label="抽牌" count={match.you.draw_count} /><Pile label="弃牌" count={match.you.discard_count} /></div>
            <GameTooltip className="hand-limit-tooltip" explanation={GAME_TERMS.handLimit}><span>{effectiveHandSize} / {match.hand_limit} 有效手牌{excessCards > 0 && <em>还需弃 {excessCards} 张</em>}</span></GameTooltip>
            <div className="hand-actions">
              {!selectingDiscard && <button type="button" className="discard-toggle" disabled={!myTurn || match.pending_choice || !inPlay} onClick={startDiscard}>选择弃牌</button>}
              {selectingDiscard && <button type="button" className="discard-toggle" disabled={inDiscard && discardSelection.length === 0} onClick={clearDiscard}>{inDiscard ? "清空选择" : "取消弃牌"}</button>}
              {selectingDiscard && <button type="button" className="discard-confirm" disabled={!myTurn || match.pending_choice || discardSelection.length === 0} onClick={confirmDiscard}>确认弃置 {discardSelection.length} 张</button>}
              <button type="button" className="turn-end" disabled={!myTurn || match.pending_choice || (!inPlay && !inDiscard) || excessCards > 0 || discardSelection.length > 0} onClick={() => props.send("end_turn")}>{excessCards > 0 ? `还需弃 ${excessCards} 张` : "结束回合"} <b>→</b></button>
            </div>
          </div>
          <div className={`hand-cards ${selectingDiscard ? "selecting-discard" : ""}`}>
            <AnimatePresence>
              {match.you.hand_cards.map((cardId, index) => {
                const card = getCard(myCharacter, cardId);
                const cost = match.you.card_costs?.[index] ?? card?.cost ?? null;
                const discardable = match.you.card_discardable?.[index] ?? ![49, 50].includes(cardId);
                const selected = discardSelection.includes(index);
                
                // Calculate arc geometry explicitly with dynamic spread
                const totalCards = match.you.hand_cards.length;
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
                      y: selected ? translateY - 40 : translateY, 
                      x: translateX, 
                      scale: selected ? 1.1 : 1, 
                      rotate: selected ? 0 : rotate,
                      zIndex: selected ? 50 : index // Natural left-to-right stacking
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
                    aria-pressed={selectingDiscard ? selected : undefined}
                    className={`hand-card-button ${selected ? "discard-selected" : ""}`}
                    key={`${cardId}-${index}-${match.revision}`} // Force re-animation on draw by ensuring unique keys if needed, but index is standard. Let's stick to unique cardId if possible, but the game uses index for playing. Using cardId-index is okay.
                    type="button"
                    disabled={!myTurn || match.pending_choice || (selectingDiscard ? !discardable : !inPlay)}
                    onClick={() => selectingDiscard ? toggleDiscard(index) : props.send("play_card", { source: "hand", index })}
                  >
                    <GameCard card={card} cardId={cardId} cost={cost} index={index} discardState={selectingDiscard ? selected ? "selected" : discardable ? "available" : "blocked" : "none"} />
                  </motion.button>
                );
              })}
            </AnimatePresence>
          </div>
        </div>
        <LogPanel logs={props.logs} chatText={props.chatText} setChatText={props.setChatText} submitChat={props.submitChat} />
      </section>
      {props.children}
    </main>
  );
}

function PlayerStatus({ label, character, player, active }: { label: string; character: number; player: PublicPlayer; active: boolean }) {
  const name = character === 1 ? "战士" : character === 4 ? "蛞蝓猫" : `角色 ${character}`;
  const data = player.character_data ?? {};
  const maxHealth = Math.max(1, player.max_health ?? (character === 4 ? 5 : 30));
  const healthPercent = Math.max(0, Math.min(100, player.health / maxHealth * 100));
  const healthTone = healthPercent <= 25 ? "critical" : healthPercent <= 50 ? "wounded" : "healthy";
  const detail = Object.entries(data)
    .filter(([key, value]) => typeof value === "number" && statusExplanation(key))
    .map(([key, value]) => ({
      key,
      value: key === "karma" && typeof data.karma_max === "number" ? `${value}/${data.karma_max}` : String(value),
    }));
  if (typeof data.form === "string") detail.unshift({ key: "form", value: data.form });
  return (
    <div className={`player-status ${active ? "active" : ""}`}>
      <div className="player-identity">
        <div className={`avatar char-${character}`}>{character === 1 ? "战" : "猫"}</div>
        <div className="identity"><small>{label}</small><strong>{name}</strong></div>
      </div>
      <GameTooltip className="energy-core" explanation={{ ...GAME_TERMS.energy, description: `当前拥有 ${player.energy} 点能量。${GAME_TERMS.energy.description}` }}>
        <span className="energy-glyph">◆</span><span className="energy-copy"><small>能量</small><strong>{player.energy}</strong></span>
      </GameTooltip>
      <div className="secondary-stats">
        <Stat icon="⬟" label="防御" value={player.defence} tone="defence" explanation={GAME_TERMS.defence} />
        <Stat icon="↑" label="力量" value={player.strength} tone="strength" explanation={GAME_TERMS.strength} />
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
function Pile({ label, count }: { label: string; count: number }) { return <GameTooltip className="pile-tooltip" explanation={label === "抽牌" ? GAME_TERMS.drawPile : GAME_TERMS.discardPile}><span className="pile"><span>{label}</span><strong>{count}</strong></span></GameTooltip>; }
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

function GameCard({ card, cardId, cost, index, discardState }: { card?: CardDefinition; cardId: number; cost: number | null; index: number; discardState: "none" | "available" | "selected" | "blocked" }) {
  const cardType = card?.card_type ?? "卡牌";
  return <article className={`game-card ${cardTone(cardType)} ${discardState !== "none" ? "discard-mode" : ""} ${discardState === "selected" ? "discard-selected" : ""}`}><div className="card-top"><GameTooltip focusable={false} className="card-type-tooltip" explanation={cardTypeExplanation(cardType)}><span>{cardType}</span></GameTooltip><div className="card-flags">{card?.exhausted && <GameTooltip focusable={false} className="exhaust-tooltip" explanation={GAME_TERMS.exhaust}><span>消耗</span></GameTooltip>}<GameTooltip focusable={false} className="card-cost-tooltip" explanation={cardCostExplanation(cost, card?.cost)}><b>{cost ?? "—"}</b></GameTooltip></div></div><div className="card-art"><span>{card?.name?.slice(0, 1) ?? "?"}</span></div><div className="card-copy"><strong>{card?.name ?? `卡牌 ${cardId}`}</strong><p><RuleText text={card?.description || "暂无卡牌说明"} /></p></div><small>#{String(index + 1).padStart(2, "0")} · ID {cardId}</small>{discardState !== "none" && <em>{discardState === "selected" ? "− 退回" : discardState === "blocked" ? "不可弃置" : "+ 选择弃置"}</em>}</article>;
}

function MiniCard({ card, cost }: { card: CardDefinition; cost: number | null }) { return <div className={`mini-card ${cardTone(card.card_type)}`}><GameTooltip focusable={false} className="mini-card-cost" explanation={cardCostExplanation(cost, card.cost)}><b>{cost ?? "—"}</b></GameTooltip><GameTooltip focusable={false} explanation={cardTypeExplanation(card.card_type)}><span>{card.card_type}</span></GameTooltip><strong>{card.name}</strong></div>; }
function CreatureChip({ creature, card }: { creature: Creature; card?: CardDefinition }) { return <div className="creature-chip"><span>{card?.name?.slice(0, 1) ?? "生"}</span><div><strong>{card?.name ?? `生物 ${creature.card_id}`}</strong><GameTooltip focusable={false} explanation={GAME_TERMS.creatureHealth}><small>♥ {creature.health}{creature.shell === false ? " · 破甲" : ""}</small></GameTooltip></div></div>; }

function LogPanel({ logs, chatText, setChatText, submitChat, compact = false }: { logs: LogEntry[]; chatText: string; setChatText: (value: string) => void; submitChat: (event: FormEvent) => void; compact?: boolean }) {
  const endRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);
  return <section className={`log-panel ${compact ? "compact" : ""}`}><div className="log-heading"><span>对局记录</span><small>LIVE LOG</small></div><div className="log-scroll">{logs.length ? logs.map((entry) => <p key={entry.id} className={entry.tone}><i />{entry.text}</p>) : <p className="muted"><i />等待消息…</p>}<div ref={endRef} /></div><form onSubmit={submitChat}><input aria-label="聊天消息" value={chatText} onChange={(event) => setChatText(event.target.value)} maxLength={200} placeholder="发送消息…" /><button type="submit">发送</button></form></section>;
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
