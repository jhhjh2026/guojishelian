import request from './index'
import type { ApiResponse } from '../types'

export type DashboardStats = {
  total_rules: number
  total_qa: number
  today_qa: number
  week_qa: number
  total_users: number
}

export const statsApi = {
  dashboard() {
    return request.get<ApiResponse<DashboardStats>>('/api/admin/dashboard')
  },
}

export default statsApi
