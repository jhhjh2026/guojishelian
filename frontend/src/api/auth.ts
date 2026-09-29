import request from './index'

export const authApi = {
  login(username: string, password: string) {
    return request.post('/api/auth/login', { username, password })
  },
  register(data: { username: string; email: string; password: string }) {
    return request.post('/api/auth/register', data)
  }
}

export default authApi
