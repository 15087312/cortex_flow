<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import StatusBar from '@/components/StatusBar.vue'
import * as api from '@/api.js'

const router = useRouter()

onMounted(async () => {
  // Guard: when auth is required and no token, send to the login page.
  try {
    const st = await api.setupRequired()
    if (st.required && !api.getToken()) {
      router.push('/login')
    }
  } catch {
    // backend down — leave the current page alone
  }
})
</script>

<template>
  <div class="app-shell">
    <div class="app-body">
      <Sidebar />
      <main class="main-content">
        <div class="page-view">
          <router-view v-slot="{ Component }">
            <Suspense>
              <component :is="Component" />
              <template #fallback>
                <div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted)">
                  <span class="spinner"></span>
                </div>
              </template>
            </Suspense>
          </router-view>
        </div>
      </main>
    </div>
    <StatusBar />
  </div>
</template>