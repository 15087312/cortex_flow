import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/workbench' },
  {
    path: '/workbench',
    name: 'Workbench',
    component: () => import('@/pages/Workbench.vue'),
  },
  {
    path: '/conversation',
    name: 'Conversation',
    component: () => import('@/pages/Conversation.vue'),
  },
  {
    path: '/conversation/:workflowId',
    name: 'ConversationWorkflow',
    component: () => import('@/pages/Conversation.vue'),
    props: true,
  },
  {
    path: '/agents',
    name: 'Agents',
    component: () => import('@/pages/Agents.vue'),
  },
  {
    path: '/tools',
    name: 'Tools',
    component: () => import('@/pages/Tools.vue'),
  },
  {
    path: '/schedules',
    name: 'Schedules',
    component: () => import('@/pages/Schedules.vue'),
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/pages/Login.vue'),
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

export default router
