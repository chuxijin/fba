export type BasicCalculationOrder = 'asc' | 'desc' | 'random'
export type BasicCalculationMode = 'standard' | 'power'
export type BasicCalculationOperator = '+' | '-' | '×' | '÷'
export type BasicCalculationSecondMode = 'random_digits' | 'fixed' | 'range'

export interface BasicCalculationType {
  title: string
  hint: string
}

export interface BasicCalculationQuestion {
  expression: string
  answer: number
}

export interface BasicCalculationCustomConfig {
  mode: BasicCalculationMode
  firstDigits: number
  operators: BasicCalculationOperator[]
  secondMode: BasicCalculationSecondMode
  secondDigits: number
  fixedSecond: number
  rangeStart: number
  rangeEnd: number
}

export const BASIC_CALCULATION_CUSTOM_CONFIG_KEY = 'basic_calculation_custom_config'

export const DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG: BasicCalculationCustomConfig = {
  mode: 'standard',
  firstDigits: 2,
  operators: ['+'],
  secondMode: 'random_digits',
  secondDigits: 2,
  fixedSecond: 11,
  rangeStart: 10,
  rangeEnd: 99,
}

export const BASIC_CALCULATION_TYPES: BasicCalculationType[] = [
  { title: '两位数加减', hint: '两位数加法和减法混合出现，适合热身和基础口算训练。' },
  { title: '凑整百练习', hint: '围绕补数和凑整百设计，训练资料分析里常用的快速拆分。' },
  { title: '三位数加法', hint: '三位数连续加法训练，重点练进位稳定性和数字保持。' },
  { title: '三位数减法', hint: '三位数减法训练，重点练退位判断和差值敏感度。' },
  { title: '三位数加减', hint: '三位数加减混合训练，提升连续运算时的抗干扰能力。' },
  { title: '多数相加', hint: '多个数字连续相加，训练分组、归并和短时记忆。' },
  { title: '混合加减', hint: '加减随机混排，训练快速识别符号并选择计算路径。' },
  { title: '两位数乘一位数', hint: '基础乘法拆分训练，为更复杂乘法和估算打底。' },
  { title: '三位数乘一位数', hint: '三位数乘一位数，强化拆位乘法和进位处理。' },
  { title: '两位数乘11', hint: '练习乘 11 的规律速算，适合建立数字结构感。' },
  { title: '两位数乘15', hint: '练习乘 15 的拆分算法，提高特定倍数的速算能力。' },
  { title: '两位数乘两位数', hint: '两位数乘法训练，重点练拆分、交叉计算和校验。' },
  { title: '三位数除一位数', hint: '基础除法训练，强化商的判断和余数处理。' },
  { title: '三位数除两位数', hint: '两位数除法训练，重点练试商、估商和修正。' },
  { title: '乘法估算', hint: '快速判断乘积范围，适合资料分析中的选项排除。' },
  { title: '五位数除三位数', hint: '大数除法估算，训练比例、倍数类计算的速度。' },
  { title: '三位数除四位数', hint: '小数型除法关系训练，提升比值、占比和增长率敏感度。' },
  { title: '自定义', hint: '自由设置数字位数、运算类型和题量，适合针对性补弱。' },
]

function randomInt(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min
}

function sample<T>(items: T[]) {
  return items[randomInt(0, items.length - 1)]
}

function roundToTen(value: number) {
  return Math.round(value / 10) * 10
}

function normalizeDigits(digits: number) {
  return Math.max(1, Math.min(4, Math.trunc(Number(digits || 1))))
}

function minByDigits(digits: number) {
  if (digits <= 1) {
    return 1
  }
  return 10 ** (digits - 1)
}

function maxByDigits(digits: number) {
  return 10 ** digits - 1
}

function randomByDigits(digits: number) {
  const safeDigits = normalizeDigits(digits)
  return randomInt(minByDigits(safeDigits), maxByDigits(safeDigits))
}

export function normalizeBasicCalculationCustomConfig(
  config?: Partial<BasicCalculationCustomConfig> | null,
): BasicCalculationCustomConfig {
  const operators = Array.isArray(config?.operators)
    ? config.operators.filter((item): item is BasicCalculationOperator => ['+', '-', '×', '÷'].includes(item))
    : []

  const rangeStart = Math.trunc(Number(config?.rangeStart || DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG.rangeStart))
  const rangeEnd = Math.trunc(Number(config?.rangeEnd || DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG.rangeEnd))
  const minRange = Math.max(1, Math.min(rangeStart, rangeEnd))
  const maxRange = Math.max(minRange, Math.max(rangeStart, rangeEnd))

  return {
    mode: config?.mode === 'power' ? 'power' : 'standard',
    firstDigits: normalizeDigits(config?.firstDigits || DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG.firstDigits),
    operators: operators.length ? operators : [...DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG.operators],
    secondMode: ['fixed', 'range', 'random_digits'].includes(String(config?.secondMode))
      ? config?.secondMode as BasicCalculationSecondMode
      : 'random_digits',
    secondDigits: normalizeDigits(config?.secondDigits || DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG.secondDigits),
    fixedSecond: Math.max(1, Math.trunc(Number(config?.fixedSecond || DEFAULT_BASIC_CALCULATION_CUSTOM_CONFIG.fixedSecond))),
    rangeStart: minRange,
    rangeEnd: maxRange,
  }
}

export function encodeBasicCalculationCustomConfig(config: BasicCalculationCustomConfig) {
  return encodeURIComponent(JSON.stringify(config))
}

export function decodeBasicCalculationCustomConfig(value?: string | null) {
  if (!value) {
    return normalizeBasicCalculationCustomConfig()
  }

  try {
    return normalizeBasicCalculationCustomConfig(JSON.parse(decodeURIComponent(value)))
  }
  catch {
    return normalizeBasicCalculationCustomConfig()
  }
}

function createSecondNumber(config: BasicCalculationCustomConfig) {
  if (config.secondMode === 'fixed') {
    return config.fixedSecond
  }
  if (config.secondMode === 'range') {
    return randomInt(config.rangeStart, config.rangeEnd)
  }
  return randomByDigits(config.secondDigits)
}

function createCustomQuestion(config?: Partial<BasicCalculationCustomConfig> | null): BasicCalculationQuestion {
  const normalized = normalizeBasicCalculationCustomConfig(config)
  const first = randomByDigits(normalized.firstDigits)
  const second = createSecondNumber(normalized)

  if (normalized.mode === 'power') {
    const exponent = Math.max(2, Math.min(4, second))
    return { expression: `${first}^${exponent}=`, answer: first ** exponent }
  }

  const operator = sample(normalized.operators)
  if (operator === '+') {
    return { expression: `${first}+${second}=`, answer: first + second }
  }
  if (operator === '-') {
    const max = Math.max(first, second)
    const min = Math.min(first, second)
    return { expression: `${max}-${min}=`, answer: max - min }
  }
  if (operator === '×') {
    return { expression: `${first}×${second}=`, answer: first * second }
  }

  const divisor = Math.max(1, second)
  const quotient = first
  return { expression: `${divisor * quotient}÷${divisor}=`, answer: quotient }
}

function createQuestion(
  typeIndex: number,
  customConfig?: Partial<BasicCalculationCustomConfig> | null,
): BasicCalculationQuestion {
  const typeTitle = BASIC_CALCULATION_TYPES[typeIndex]?.title || '两位数加减'

  if (typeTitle === '凑整百练习') {
    const base = randomInt(1, 8) * 100
    const value = base - randomInt(11, 89)
    return { expression: `${value}+□=${base}`, answer: base - value }
  }

  if (typeTitle === '三位数加法') {
    const first = randomInt(100, 899)
    const second = randomInt(100, 899)
    return { expression: `${first}+${second}=`, answer: first + second }
  }

  if (typeTitle === '三位数减法') {
    const first = randomInt(200, 999)
    const second = randomInt(100, first - 1)
    return { expression: `${first}-${second}=`, answer: first - second }
  }

  if (typeTitle === '三位数加减') {
    const first = randomInt(100, 700)
    const second = randomInt(100, 299)
    const third = randomInt(40, 199)
    const isAddThenSub = Math.random() > 0.5
    if (isAddThenSub) {
      return { expression: `${first}+${second}-${third}=`, answer: first + second - third }
    }
    return { expression: `${first}-${third}+${second}=`, answer: first - third + second }
  }

  if (typeTitle === '多数相加') {
    const nums = Array.from({ length: 4 }, () => randomInt(20, 199))
    return { expression: `${nums.join('+')}=`, answer: nums.reduce((sum, item) => sum + item, 0) }
  }

  if (typeTitle === '混合加减') {
    const first = randomInt(80, 300)
    const second = randomInt(20, 120)
    const third = randomInt(20, 120)
    return { expression: `${first}+${second}-${third}=`, answer: first + second - third }
  }

  if (typeTitle === '两位数乘一位数') {
    const first = randomInt(12, 99)
    const second = randomInt(2, 9)
    return { expression: `${first}×${second}=`, answer: first * second }
  }

  if (typeTitle === '三位数乘一位数') {
    const first = randomInt(101, 999)
    const second = randomInt(2, 9)
    return { expression: `${first}×${second}=`, answer: first * second }
  }

  if (typeTitle === '两位数乘11') {
    const first = randomInt(12, 99)
    return { expression: `${first}×11=`, answer: first * 11 }
  }

  if (typeTitle === '两位数乘15') {
    const first = randomInt(12, 99)
    return { expression: `${first}×15=`, answer: first * 15 }
  }

  if (typeTitle === '两位数乘两位数') {
    const first = randomInt(12, 99)
    const second = randomInt(12, 99)
    return { expression: `${first}×${second}=`, answer: first * second }
  }

  if (typeTitle === '三位数除一位数') {
    const divisor = randomInt(2, 9)
    const quotient = randomInt(12, 99)
    return { expression: `${divisor * quotient}÷${divisor}=`, answer: quotient }
  }

  if (typeTitle === '三位数除两位数') {
    const divisor = randomInt(11, 49)
    const quotient = randomInt(4, 20)
    return { expression: `${divisor * quotient}÷${divisor}=`, answer: quotient }
  }

  if (typeTitle === '乘法估算') {
    const first = randomInt(21, 98)
    const second = randomInt(21, 98)
    return { expression: `${first}×${second}≈`, answer: roundToTen(first) * roundToTen(second) }
  }

  if (typeTitle === '五位数除三位数') {
    const divisor = randomInt(101, 999)
    const quotient = randomInt(12, 99)
    return { expression: `${divisor * quotient}÷${divisor}=`, answer: quotient }
  }

  if (typeTitle === '三位数除四位数') {
    const numerator = randomInt(100, 999)
    const denominator = randomInt(1000, 9999)
    return { expression: `${numerator}÷${denominator}≈`, answer: Number((numerator / denominator).toFixed(2)) }
  }

  if (typeTitle === '自定义') {
    return createCustomQuestion(customConfig)
  }

  const first = randomInt(10, 99)
  const second = randomInt(10, 99)
  const operator = sample(['+', '-'])
  if (operator === '+') {
    return { expression: `${first}+${second}=`, answer: first + second }
  }
  const max = Math.max(first, second)
  const min = Math.min(first, second)
  return { expression: `${max}-${min}=`, answer: max - min }
}

export function createBasicCalculationQuestions(
  typeIndex: number,
  count: number,
  customConfig?: Partial<BasicCalculationCustomConfig> | null,
): BasicCalculationQuestion[] {
  const safeCount = Math.max(1, Math.min(100, Number(count || 10)))
  return Array.from({ length: safeCount }, () => createQuestion(typeIndex, customConfig))
}

export function getKeyboardKeys(order: BasicCalculationOrder): string[] {
  const asc = ['1', '2', '3', '4', '5', '6', '7', '8', '9']
  if (order === 'desc') {
    return [...asc].reverse()
  }
  if (order === 'random') {
    return [...asc].sort(() => Math.random() - 0.5)
  }
  return asc
}
