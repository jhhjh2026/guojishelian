import axios from 'axios'

const urlApiBase = import.meta.env.VITE_API_BASE;

function inferApiBase(): string {
  const trimmed = (urlApiBase || '').trim();
  if (trimmed) return trimmed.replace(/\/+$/, '');
  const host = window.location.host;
  const protocol = window.location.protocol || 'http:';
  if (host && host !== '') return `${protocol}//${host}`;
  return 'http://127.0.0.1:8000';
}

const request = axios.create({
  baseURL: inferApiBase(),
  timeout: 60000,
})

request.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default request
