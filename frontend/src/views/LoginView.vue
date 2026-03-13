<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

onMounted(() => {
  if (route.query.reason === 'tm1') {
    authStore.error = 'TM1 session expired — please log in again'
  }
})

const username = ref('mc@tremly.com')
const password = ref('Number55dip')
const tm1User = ref('mc')
const tm1Password = ref('pass')
const showAdvanced = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) {
    authStore.error = 'Please enter username and password'
    return
  }
  const success = await authStore.login(
    username.value,
    password.value,
    tm1User.value,
    tm1Password.value
  )
  if (success) {
    authStore.startAutoRefresh()
    router.push('/')
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') handleLogin()
}
</script>

<template>
  <div class="login-page" @keydown="handleKeydown">
    <div class="login-card">
      <!-- Logo -->
      <div class="flex flex-col items-center mb-8">
        <div
          class="w-14 h-14 rounded-xl bg-[--klikk-primary] flex items-center justify-center font-bold text-white text-2xl mb-4 shadow-lg"
        >
          K
        </div>
        <h1 class="text-xl font-semibold text-[--klikk-text]">Klikk AI Portal</h1>
        <p class="text-sm text-[--klikk-text-muted] mt-1">Sign in to continue</p>
      </div>

      <!-- Error message -->
      <div
        v-if="authStore.error"
        class="mb-4 px-4 py-3 rounded-lg bg-[--klikk-danger]/10 border border-[--klikk-danger]/30 text-[--klikk-danger] text-sm"
      >
        <i class="pi pi-exclamation-circle mr-2" />
        {{ authStore.error }}
      </div>

      <!-- Username -->
      <div class="field mb-4">
        <label class="block text-sm text-[--klikk-text-secondary] mb-1.5">Username</label>
        <InputText
          v-model="username"
          placeholder="Enter your username"
          class="w-full"
          :disabled="authStore.loading"
          autofocus
        />
      </div>

      <!-- Password -->
      <div class="field mb-4">
        <label class="block text-sm text-[--klikk-text-secondary] mb-1.5">Password</label>
        <Password
          v-model="password"
          placeholder="Enter your password"
          class="w-full"
          :feedback="false"
          :toggleMask="true"
          :disabled="authStore.loading"
          inputClass="w-full"
        />
      </div>

      <!-- TM1 Advanced Section -->
      <div class="mb-6">
        <button
          type="button"
          class="flex items-center gap-2 text-xs text-[--klikk-text-muted] hover:text-[--klikk-text-secondary] transition-colors cursor-pointer bg-transparent border-none p-0"
          @click="showAdvanced = !showAdvanced"
        >
          <i class="pi text-xs" :class="showAdvanced ? 'pi-chevron-down' : 'pi-chevron-right'" />
          TM1 Connection Settings
        </button>
        <transition name="expand">
          <div v-if="showAdvanced" class="mt-3 space-y-3 pl-4 border-l-2 border-[--klikk-border]">
            <div class="field">
              <label class="block text-xs text-[--klikk-text-muted] mb-1">TM1 User</label>
              <InputText
                v-model="tm1User"
                placeholder="admin"
                class="w-full"
                :disabled="authStore.loading"
              />
            </div>
            <div class="field">
              <label class="block text-xs text-[--klikk-text-muted] mb-1">TM1 Password</label>
              <Password
                v-model="tm1Password"
                placeholder="Leave empty if none"
                class="w-full"
                :feedback="false"
                :toggleMask="true"
                :disabled="authStore.loading"
                inputClass="w-full"
              />
            </div>
          </div>
        </transition>
      </div>

      <!-- Login Button -->
      <Button
        label="Sign In"
        icon="pi pi-sign-in"
        class="w-full p-button-primary"
        :loading="authStore.loading"
        @click="handleLogin"
      />

      <!-- Footer -->
      <div class="mt-6 text-center text-xs text-[--klikk-text-muted]">
        Planning V3
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--klikk-bg);
}

.login-card {
  width: 100%;
  max-width: 400px;
  padding: 2.5rem;
  background: var(--klikk-surface);
  border: 1px solid var(--klikk-border);
  border-radius: 16px;
  box-shadow: var(--klikk-shadow-lg);
}

.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.expand-enter-to,
.expand-leave-from {
  opacity: 1;
  max-height: 200px;
}

/* Ensure Password component spans full width */
:deep(.p-password) {
  width: 100%;
}
:deep(.p-password-input) {
  width: 100%;
}
</style>
