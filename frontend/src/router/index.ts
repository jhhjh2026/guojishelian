import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Login from '../views/Login.vue'
import Layout from '../views/Layout.vue'
import Rules from '../views/admin/Rules.vue'
import Users from '../views/admin/Users.vue'
import Dashboard from '../views/admin/Dashboard.vue'
import Ask from '../views/Ask.vue'

const PUBLIC_PATHS = ['/login', '/ask']

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { title: '登录', public: true }
  },
  {
    path: '/',
    component: Layout,
    redirect: '/ask',
    children: [
      { path: 'ask', name: 'Ask', component: Ask, meta: { title: '规则问答', public: true } },
      {
        path: 'admin',
        redirect: '/admin/dashboard',
        children: [
          { path: 'dashboard', name: 'Dashboard', component: Dashboard, meta: { title: '数据看板' } },
          { path: 'rules', name: 'Rules', component: Rules, meta: { title: '规则管理' } },
          { path: 'users', name: 'Users', component: Users, meta: { title: '用户管理' } }
        ]
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  const metaPublic = Boolean((to.meta as any)?.public)
  const isPublic = metaPublic || PUBLIC_PATHS.includes(to.path)
  if (!isPublic && !token) {
    return '/login'
  }
})

export default router
