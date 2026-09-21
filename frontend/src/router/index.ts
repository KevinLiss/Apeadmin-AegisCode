import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

const modules = import.meta.glob('@/views/**/*.vue')

export function generateDynamicRoutes(menus: any[]): RouteRecordRaw[] {
  const routes: RouteRecordRaw[] = []
  function buildPath(parentPath: string, childPath: string): string {
    if (childPath.startsWith('/')) return childPath
    return `${parentPath.replace(/\/$/, '')}/${childPath}`
  }
  function traverse(menuList: any[], parentPath: string) {
    for (const menu of menuList) {
      if (menu.type === 'C' && menu.component) {
        const fullPath = buildPath(parentPath, menu.path || '')
        const relativePath = fullPath.replace(/^\//, '')
        const componentKey1 = `/src/views/${menu.component}.vue`
        const componentKey2 = `/src/views/${menu.component}/index.vue`
        const component = modules[componentKey1] || modules[componentKey2]
        if (component) {
          // Menu labels are not unique (for example, system and plugin users
          // pages can both be named "用户管理"). Vue Router replaces a route
          // when a duplicate name is added, so derive a stable name from the
          // full path while keeping the label in route meta.
          const routeName = `dynamic_${relativePath.replace(/[^a-zA-Z0-9_]/g, '_')}`
          routes.push({ path: relativePath, name: routeName, component: component as any, meta: { title: menu.name, icon: menu.icon, permission: menu.permission || undefined } })
        }
      }
      if (menu.children?.length) {
        const currentPath = menu.type === 'M' && menu.path ? menu.path.replace(/^\//, '') : parentPath
        traverse(menu.children, currentPath)
      }
    }
  }
  traverse(menus, '')
  return routes
}

const staticRoutes: RouteRecordRaw[] = [
  { path: '/login', name: 'Login', component: () => import('@/views/login/index.vue'), meta: { title: '登录' } },
  { path: '/404', name: 'NotFound', component: () => import('@/views/error/404.vue'), meta: { title: '404' } },
  // 工作台 — 独立 Layout，不走底座 ApeSidebar
  { path: '/workspace', name: 'Workspace', component: () => import('@/views/workspace/index.vue'), meta: { title: 'AegisCode 工作台' } },
  // 工作台独立登录页（与管理后台同一套用户体系）
  { path: '/workspace/login', name: 'WorkspaceLogin', component: () => import('@/views/workspace/login.vue'), meta: { title: 'AegisCode 登录' } },
  { path: '/', name: 'Layout', component: () => import('@/layout/index.vue'), redirect: '/dashboard-monitor', children: [
    { path: 'profile', name: 'Profile', component: () => import('@/views/system/profile/index.vue'), meta: { title: '个人中心', icon: 'User' } },
  ] },
  { path: '/:pathMatch(.*)*', name: 'CatchAll', component: () => import('@/views/error/404.vue'), meta: { title: '404' } },
]

const router = createRouter({ history: createWebHistory('/admin/'), routes: staticRoutes })
let dynamicRoutesLoaded = false

function registerDynamicRoutes(menus: any[]) {
  for (const route of generateDynamicRoutes(menus)) router.addRoute('Layout', route)
  dynamicRoutesLoaded = true
}

router.beforeEach(async (to, _from, next) => {
  const token = localStorage.getItem('apeadmin_token')

  // 工作台登录页：已登录直接进工作台
  if (to.path === '/workspace/login') { if (token) next('/workspace'); else next(); return }
  if (to.path === '/login') { if (token) next('/dashboard-monitor'); else next(); return }

  // 工作台及其子路由：未登录跳工作台登录页（带 redirect 回跳）
  if (to.path.startsWith('/workspace') && !token) {
    next({ path: '/workspace/login', query: { redirect: to.fullPath } })
    return
  }

  if (!token) { next('/login'); return }
  if (!dynamicRoutesLoaded) {
    const userStore = useUserStore()
    try {
      if (!userStore.menus.length) await userStore.fetchUserInfo()
      registerDynamicRoutes(userStore.menus)
      // 注意：必须用 fullPath（含 query），且 next() 支持字符串地址
      next(to.fullPath)
    } catch { userStore.reset(); next('/login') }
    return
  }
  const permission = to.meta?.permission as string | undefined
  if (permission && !useUserStore().hasPermission(permission)) { next('/404'); return }
  next()
})

export function resetRouter() {
  dynamicRoutesLoaded = false
  const staticNames = new Set(['Login', 'NotFound', 'CatchAll', 'Layout', 'Profile', 'Workspace', 'WorkspaceLogin'])
  router.getRoutes().forEach((route) => { if (route.name && !staticNames.has(route.name as string)) router.removeRoute(route.name) })
}

export function refreshDynamicRoutes(menus: any[]) {
  resetRouter()
  registerDynamicRoutes(menus)
}

export default router
