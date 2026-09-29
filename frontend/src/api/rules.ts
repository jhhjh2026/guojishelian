import request from './index'
import type { RuleItem, ApiResponse } from '../types'

export const rulesApi = {
  list(params: { keyword?: string; category?: string; version?: string; page?: number; page_size?: number }) {
    return request.get<ApiResponse<{ items: RuleItem[]; pagination: any }>>('/api/rules', { params })
  },
  detail(ruleId: string) {
    return request.get<ApiResponse<RuleItem>>(`/api/rules/${encodeURIComponent(ruleId)}`)
  },
  adminList(params: { keyword?: string; category?: string; version?: string; page?: number; page_size?: number }) {
    return request.get<ApiResponse<{ items: RuleItem[]; pagination: any }>>('/api/admin/rules', { params })
  },
  create(payload: Partial<RuleItem>) {
    return request.post<ApiResponse>('/api/admin/rules', payload)
  },
  update(ruleId: string, payload: Partial<RuleItem>) {
    return request.put<ApiResponse>(`/api/admin/rules/${encodeURIComponent(ruleId)}`, payload)
  },
  delete(ruleId: string) {
    return request.delete<ApiResponse>(`/api/admin/rules/${encodeURIComponent(ruleId)}`)
  },
}

export default rulesApi
