export interface RuleItem {
  id: string
  rule_id: string
  title: string
  category: string
  subcategory?: string
  content: string
  keywords: string[]
  related_rules: string[]
  examples: string[]
  version: string
  source?: string
  is_published: boolean
  created_at: string
  updated_at: string
}

export interface UserItem {
  id: string
  username: string
  email: string
  display_name: string
  role_id: string
  is_active: boolean
}

export interface DashboardStats {
  total_rules: number
  total_qa: number
  today_qa: number
  week_qa: number
  total_users: number
  updated_at: string
}

export interface ApiResponse<T = any> {
  success: boolean
  code: string
  message: string
  timestamp: number
  data: T
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: {
    id: string
    username: string
    email: string
    display_name?: string
    role_id: string
    is_active: boolean
  }
}

export interface LoginPayload {
  username: string
  password: string
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
}
