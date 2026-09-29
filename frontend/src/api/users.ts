import request from './index'
import type { UserItem } from '../types'

export interface UsersResponse {
  items: UserItem[]
  pagination: { total: number; page: number; page_size: number }
}

export const usersApi = {
  list(params: { keyword?: string; page?: number; page_size?: number }) {
    return request.get<{ success: boolean; data: UsersResponse }>('/api/admin/users', { params })
  },
  update(userId: string, payload: Partial<UserItem>) {
    return request.put(`/api/admin/users/${encodeURIComponent(userId)}`, payload)
  },
}

export default usersApi
