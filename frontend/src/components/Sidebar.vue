<script setup>
import { useRoute, useRouter } from 'vue-router'
import Icon from '@/components/Icon.vue'

const route = useRoute()
const router = useRouter()

const navItems = [
  { route: '/workbench', label: '工作台', icon: 'layout-grid' },
  { route: '/conversation', label: '执行', icon: 'play' },
  { route: '/agents', label: 'Agents', icon: 'robot' },
  { route: '/tools', label: '工具', icon: 'wrench' },
  { route: '/schedules', label: '定时', icon: 'clock' },
]

function isActive(itemRoute) {
  return route.path === itemRoute || route.path.startsWith(itemRoute + '/')
}
</script>

<template>
  <nav class="sidebar">
    <div class="sidebar-header">
      <Icon name="workflow" :size="20" />
      <span>CortexFlow</span>
    </div>
    <div class="sidebar-nav">
      <div
        v-for="item in navItems"
        :key="item.route"
        class="nav-item"
        :class="{ active: isActive(item.route) }"
        @click="router.push(item.route)"
      >
        <span class="icon"><Icon :name="item.icon" :size="16" /></span>
        <span>{{ item.label }}</span>
      </div>
    </div>
    <div class="sidebar-footer">
      <span>v0.1.0</span>
    </div>
  </nav>
</template>
