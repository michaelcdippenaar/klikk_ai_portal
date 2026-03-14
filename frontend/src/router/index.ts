import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { title: 'Login', public: true },
    },
    {
      path: '/',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { title: 'Dashboard', icon: 'pi pi-objects-column' },
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('../views/ChatView.vue'),
      meta: { title: 'AI Chat', icon: 'pi pi-comments' },
    },
    {
      path: '/explorer',
      name: 'explorer',
      component: () => import('../views/ExplorerView.vue'),
      meta: { title: 'Explorer', icon: 'pi pi-database' },
    },
    {
      path: '/kpis',
      name: 'kpis',
      component: () => import('../views/KPIView.vue'),
      meta: { title: 'KPIs', icon: 'pi pi-chart-bar' },
    },
    {
      path: '/datasources',
      name: 'datasources',
      component: () => import('../views/DataSourcesView.vue'),
      meta: { title: 'Data Sources', icon: 'pi pi-server' },
    },
    {
      path: '/context',
      name: 'context',
      component: () => import('../views/ContextView.vue'),
      meta: { title: 'AI Context', icon: 'pi pi-book' },
    },
    {
      path: '/skills',
      name: 'skills',
      component: () => import('../views/SkillsView.vue'),
      meta: { title: 'Skills', icon: 'pi pi-cog' },
    },
    {
      path: '/setup',
      name: 'setup',
      component: () => import('../views/SetupView.vue'),
      meta: { title: 'Setup', icon: 'pi pi-wrench' },
    },
    {
      path: '/settings/paw',
      name: 'paw-diagnostics',
      component: () => import('../views/PAWDiagnosticsView.vue'),
      meta: { title: 'PAW Diagnostics', icon: 'pi pi-desktop' },
    },
    {
      path: '/settings/monitor',
      name: 'agent-monitor',
      component: () => import('../views/MonitorView.vue'),
      meta: { title: 'Agent Monitor', icon: 'pi pi-chart-line' },
    },
  ],
})

router.beforeEach((to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.public || auth.isAuthenticated) {
    // If already authenticated and going to login, redirect to dashboard
    if (to.name === 'login' && auth.isAuthenticated) {
      next('/')
    } else {
      next()
    }
  } else {
    next('/login')
  }
})

export default router
