<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import * as api from '@/api.js'

const router = useRouter()

const mode = ref('login') // login | setup
const username = ref('')
const password = ref('')
const confirm = ref('')
const error = ref('')
const busy = ref(false)

onMounted(async () => {
  try {
    const st = await api.setupRequired()
    if (st.required) mode.value = 'setup'
  } catch (e) {
    // backend down — allow manual toggle
  }
})

async function submit() {
  error.value = ''
  if (mode.value === 'setup' && password.value !== confirm.value) {
    error.value = '两次密码不一致'
    return
  }
  busy.value = true
  try {
    const res = mode.value === 'setup'
      ? await api.doSetup(username.value, password.value)
      : await api.doLogin(username.value, password.value)
    api.setToken(res.token)
    router.push('/workbench')
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div style="height: 100vh; display: flex; align-items: center; justify-content: center; background: var(--bg-inset)">
    <div style="width: 380px; padding: var(--space-3xl); background: var(--bg-secondary); border: 1px solid var(--border); border-radius: var(--radius-lg); box-shadow: var(--shadow-md)">
      <div style="display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-md)">
        <span style="font-size: var(--text-xl); font-weight: 700; color: var(--accent)">CortexFlow</span>
      </div>
      <h3 style="font-size: var(--text-md); color: var(--text-secondary); margin-bottom: var(--space-lg)">
        {{ mode === 'setup' ? '创建管理员账号' : '登录' }}
      </h3>
      <div style="display: flex; flex-direction: column; gap: var(--space-md)">
        <input v-model="username" placeholder="用户名" class="input" autocomplete="username" @keyup.enter="submit" />
        <input v-model="password" type="password" placeholder="密码" class="input" autocomplete="current-password" @keyup.enter="submit" />
        <input v-if="mode === 'setup'" v-model="confirm" type="password" placeholder="确认密码" class="input" autocomplete="new-password" @keyup.enter="submit" />
      </div>
      <div v-if="error" style="color: var(--danger); font-size: var(--text-sm); margin-top: var(--space-sm)">{{ error }}</div>
      <button class="btn btn-primary" style="width: 100%; margin-top: var(--space-lg)" :disabled="busy" @click="submit">
        {{ busy ? '处理中…' : (mode === 'setup' ? '创建并进入' : '登录') }}
      </button>
      <p style="font-size: var(--text-2xs); color: var(--text-muted); margin-top: var(--space-md); text-align: center">
        首次使用先创建管理员账号；凭证本地 SQLite 存储（PBKDF2）。
      </p>
    </div>
  </div>
</template>