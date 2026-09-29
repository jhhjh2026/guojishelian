/**
 * detection-service.ts
 * 前端检测服务：内容合规检测、敏感词识别、安全监控
 */

export interface DetectionResult {
  passed: boolean
  violations: string[]
  score: number
  timestamp: number
}

export interface DetectionOptions {
  detectSensitiveWords?: boolean
  detectPromptInjection?: boolean
  maxLength?: number
  allowedDomains?: string[]
}

const SENSITIVE_WORDS = [
  '暴力', '色情', '赌博', '毒品', '武器', '爆炸', '恐怖', '诈骗', '盗窃', '谋杀', '自杀', '自残'
]

const PROMPT_INJECTION_PATTERNS = [
  /ignore\s+previous\s+instructions/i,
  /ignore\s+all\s+previous\s+instructions/i,
  /do\s+not\s+follow/i,
  /system\s+prompt/i,
  /you\s+are\s+now/i,
  /new\s+instructions/i,
  /override/i,
  /bypass/i,
  /jailbreak/i
]

export class DetectionService {
  private options: DetectionOptions

  constructor(options: DetectionOptions = {}) {
    this.options = {
      detectSensitiveWords: options.detectSensitiveWords ?? true,
      detectPromptInjection: options.detectPromptInjection ?? true,
      maxLength: options.maxLength ?? 5000,
      allowedDomains: options.allowedDomains ?? []
    }
  }

  async detect(text: string): Promise<DetectionResult> {
    const violations: string[] = []
    const timestamp = Date.now()

    if (!text || text.trim().length === 0) {
      return { passed: true, violations: [], score: 100, timestamp }
    }

    const trimmed = text.trim()

    if (this.options.detectSensitiveWords) {
      const lower = SENSITIVE_WORDS.find(w => trimmed.includes(w))
      if (lower) {
        violations.push(`sensitive:${lower}`)
      }
    }

    if (this.options.detectPromptInjection) {
      const matched = PROMPT_INJECTION_PATTERNS.find(p => p.test(trimmed))
      if (matched) {
        violations.push('prompt_injection')
      }
    }

    if (trimmed.length > (this.options.maxLength ?? 5000)) {
      violations.push('too_long')
    }

    const score = this.calculateScore(violations.length)
    return {
      passed: violations.length === 0,
      violations,
      score,
      timestamp
    }
  }

  calculateScore(violations: number): number {
    if (violations === 0) {
      return 100
    }
    return Math.max(0, 100 - violations * 25)
  }

  maskSensitive(text: string): string {
    let masked = text
    SENSITIVE_WORDS.forEach(word => {
      const regex = new RegExp(word, 'gi')
      masked = masked.replace(regex, '***')
    })
    return masked
  }
}

export const detectionService = new DetectionService()
export default detectionService
