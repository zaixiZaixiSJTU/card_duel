export type GameExplanation = {
  title: string;
  description: string;
  detail?: string;
};

export const GAME_TERMS = {
  health: {
    title: "生命",
    description: "受到未被防御或角色能力抵消的伤害时减少。",
    detail: "生命归零通常会败北；部分角色能力会改变死亡结算。",
  },
  energy: {
    title: "能量",
    description: "打出卡牌和发动部分效果时支付的资源。",
    detail: "每轮开始时双方会获得 4–6 点能量，未花费的能量不会保留到下一轮。",
  },
  defence: {
    title: "防御",
    description: "受到伤害时优先消耗，等量抵消伤害。",
    detail: "大多数防御只持续有限回合；部分卡牌可以让防御持续存在。",
  },
  strength: {
    title: "力量",
    description: "通常会提高攻击牌和部分生物造成的伤害。",
    detail: "负力量会降低伤害；具体计算仍以卡牌说明和结算记录为准。",
  },
  poison: {
    title: "中毒",
    description: "由卡牌或延迟效果施加的负面层数。",
    detail: "具体触发时机和消耗方式以造成中毒的卡牌说明为准。",
  },
  handLimit: {
    title: "有效手牌",
    description: "回合结束时计入手牌上限的卡牌数量。",
    detail: "超过上限时必须先弃牌。部分卡牌或角色能力可能不计入有效手牌。",
  },
  drawPile: {
    title: "抽牌堆",
    description: "尚未抽到的卡牌。抽牌阶段会从这里取得卡牌。",
    detail: "普通牌堆耗尽时，弃牌堆会重新洗入抽牌堆。特殊牌池可能采用独立规则。",
  },
  discardPile: {
    title: "弃牌堆",
    description: "已打出或主动弃置、并且仍可循环使用的卡牌。",
    detail: "抽牌堆需要补充时，弃牌堆会洗牌后重新加入抽牌堆。",
  },
  cardCost: {
    title: "能量费用",
    description: "打出这张牌时需要支付的能量。",
    detail: "界面显示的是当前实际费用，可能受到角色状态或其他卡牌效果修正。",
  },
  exhaust: {
    title: "消耗",
    description: "这张牌成功打出后会从本局牌堆循环中移除。",
    detail: "被消耗的牌不会进入弃牌堆，也不会在本局中再次抽到。",
  },
  creatureHealth: {
    title: "生物生命",
    description: "生物可以承受的伤害。生命降至零时，生物死亡并离场。",
  },
} satisfies Record<string, GameExplanation>;

const PHASE_TERMS: Record<string, GameExplanation> = {
  "回合开始": {
    title: "回合开始",
    description: "结算持续状态、延迟效果和角色的回合开始能力。",
  },
  "抽牌": {
    title: "抽牌阶段",
    description: "当前玩家自动从自己的牌堆抽取本回合手牌。",
  },
  "出牌": {
    title: "出牌阶段",
    description: "当前玩家可以支付费用打出手牌或处理生物。",
  },
  "弃牌": {
    title: "弃牌阶段",
    description: "整理手牌；有效手牌超过上限时必须弃到上限以内。",
  },
  "回合结束": {
    title: "回合结束",
    description: "结算生物攻击和角色的回合结束能力，然后轮到对手。",
  },
};

const STATUS_TERMS: Record<string, GameExplanation> = {
  form: {
    title: "形态",
    description: "蛞蝓猫当前采用的持续形态；不同形态可能改变可用卡牌与结算规则。",
  },
  karma: {
    title: "业力",
    description: "蛞蝓猫抵抗死亡的核心资源。",
    detail: "生命归零时消耗 1 点；消耗后业力仍大于零则恢复生命，业力归零时败北。",
  },
  satiety: {
    title: "饱食度",
    description: "蛞蝓猫通过觅食获得、并被部分生存能力消耗的资源。",
  },
  agility: {
    title: "敏捷",
    description: "优先抵挡即将受到的普通伤害。",
    detail: "直接失去生命的效果不会被敏捷阻止，但可能减少敏捷。",
  },
  momentum: {
    title: "动能",
    description: "强化蛞蝓猫下一次矛、石子等物品攻击的伤害。",
    detail: "动能在用于攻击或进入自己的下个回合时通常会清零。",
  },
  sacrifice_layers: {
    title: "献祭",
    description: "强化战士部分以生命换取收益的卡牌效果。",
  },
  heartlink_layers: {
    title: "心连心",
    description: "战士回合开始时，双方各受到等同层数的伤害。",
    detail: "拥有献祭层数时，心连心还会为战士抽取额外卡牌。",
  },
};

const CARD_TYPE_TERMS: Record<string, GameExplanation> = {
  "技能": { title: "技能牌", description: "提供移动、资源或其他战术效果的卡牌类型。" },
  "物品": { title: "物品牌", description: "武器、工具和可交互物品。部分效果会消耗或插入物品。" },
  "生物": { title: "生物牌", description: "具有生命和独立行为的生物，可能被携带、转移或发动攻击。" },
  "见闻": { title: "见闻牌", description: "蛞蝓猫通过探索获得的特殊卡牌，通常使用独立牌池。" },
  "形态": { title: "形态牌", description: "改变蛞蝓猫状态或玩法规则的持续性能力。" },
  "卡牌": { title: "卡牌", description: "打出后执行说明中的效果，通常进入弃牌堆等待再次循环。" },
};

export function phaseExplanation(phase: string): GameExplanation {
  return PHASE_TERMS[phase] ?? { title: phase, description: "对局的一个固定结算阶段。" };
}

export function statusExplanation(key: string): GameExplanation | undefined {
  return STATUS_TERMS[key];
}

export function cardTypeExplanation(cardType = "卡牌"): GameExplanation {
  return CARD_TYPE_TERMS[cardType] ?? {
    title: cardType,
    description: "卡牌类型可能被其他卡牌、角色能力或结算规则引用。",
  };
}

export function cardCostExplanation(currentCost: number | null, baseCost?: number | null): GameExplanation {
  if (currentCost === null) {
    return {
      title: "特殊费用",
      description: "这张牌没有固定的常规能量费用，支付方式由卡牌说明或当前状态决定。",
    };
  }
  const changed = baseCost !== undefined && baseCost !== null && baseCost !== currentCost;
  return {
    ...GAME_TERMS.cardCost,
    description: `当前打出需要 ${currentCost} 点能量。`,
    detail: changed
      ? `基础费用为 ${baseCost}，当前状态将费用修正为 ${currentCost}。`
      : GAME_TERMS.cardCost.detail,
  };
}

export const INLINE_RULE_TERMS: ReadonlyArray<{ term: string; explanation: GameExplanation }> = [
  { term: "有效手牌", explanation: GAME_TERMS.handLimit },
  { term: "饱食度", explanation: STATUS_TERMS.satiety },
  { term: "心连心", explanation: STATUS_TERMS.heartlink_layers },
  { term: "抽牌堆", explanation: GAME_TERMS.drawPile },
  { term: "弃牌堆", explanation: GAME_TERMS.discardPile },
  { term: "生命", explanation: GAME_TERMS.health },
  { term: "能量", explanation: GAME_TERMS.energy },
  { term: "防御", explanation: GAME_TERMS.defence },
  { term: "力量", explanation: GAME_TERMS.strength },
  { term: "业力", explanation: STATUS_TERMS.karma },
  { term: "饱食", explanation: STATUS_TERMS.satiety },
  { term: "敏捷", explanation: STATUS_TERMS.agility },
  { term: "动能", explanation: STATUS_TERMS.momentum },
  { term: "献祭", explanation: STATUS_TERMS.sacrifice_layers },
];
