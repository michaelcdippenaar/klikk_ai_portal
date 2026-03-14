<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useCredentialsStore } from '../stores/credentials'
import type { Credential } from '../stores/credentials'
import Button from 'primevue/button'

const store = useCredentialsStore()

const editingKey = ref<string | null>(null)
const editValue = ref('')
const showValue = ref<Record<string, boolean>>({})

// Group credentials
const groupedCredentials = computed(() => {
  const groups: Record<string, Credential[]> = {}
  for (const cred of store.credentials) {
    const g = cred.group || 'Other'
    if (!groups[g]) groups[g] = []
    groups[g].push(cred)
  }
  return Object.entries(groups)
})

function startEdit(key: string) {
  editingKey.value = key
  editValue.value = ''
}

function cancelEdit() {
  editingKey.value = null
  editValue.value = ''
}

async function saveEdit(key: string, label: string) {
  if (!editValue.value.trim()) return
  const ok = await store.setCredential(key, editValue.value.trim(), label)
  if (ok) {
    editingKey.value = null
    editValue.value = ''
  }
}

function handleKeydown(e: KeyboardEvent, key: string, label: string) {
  if (e.key === 'Enter') {
    e.preventDefault()
    saveEdit(key, label)
  } else if (e.key === 'Escape') {
    cancelEdit()
  }
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return 'Never'
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return d.toLocaleDateString()
}

onMounted(() => {
  store.fetchCredentials()
})
</script>

<template>
  <div class="h-[calc(100vh-8rem)]">
    <!-- Top Bar -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-xl font-bold text-[--klikk-text]">Setup</h2>
        <p class="text-sm text-[--klikk-text-secondary] mt-0.5">
          Manage API keys and credentials — stored in database, no restart needed
        </p>
      </div>
      <Button
        label="Refresh"
        icon="pi pi-refresh"
        severity="secondary"
        size="small"
        :loading="store.loading"
        @click="store.fetchCredentials()"
      />
    </div>

    <!-- Error -->
    <div v-if="store.error" class="mb-4 text-sm text-[--klikk-danger] bg-[--klikk-danger]/10 rounded-lg px-4 py-3 flex items-center justify-between">
      <span>{{ store.error }}</span>
      <button @click="store.error = ''" class="text-[--klikk-danger] hover:opacity-70">
        <i class="pi pi-times text-xs" />
      </button>
    </div>

    <!-- Loading -->
    <div v-if="store.loading && store.credentials.length === 0" class="flex items-center justify-center py-24">
      <i class="pi pi-spin pi-spinner text-2xl text-[--klikk-primary]" />
    </div>

    <!-- Credentials grouped -->
    <div v-else class="space-y-6 overflow-y-auto max-h-[calc(100vh-14rem)] pr-1">
      <div v-for="[group, creds] in groupedCredentials" :key="group" class="glass-card p-0 overflow-hidden">
        <!-- Group header -->
        <div class="px-5 py-3 border-b border-[--klikk-border] bg-[--klikk-surface]/50">
          <h3 class="text-sm font-semibold text-[--klikk-text]">{{ group }}</h3>
        </div>

        <!-- Credential rows -->
        <div class="divide-y divide-[--klikk-border]">
          <div
            v-for="cred in creds"
            :key="cred.key"
            class="px-5 py-4"
          >
            <div class="flex items-start justify-between gap-4">
              <!-- Left: label + status -->
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="text-sm font-medium text-[--klikk-text]">{{ cred.label }}</span>
                  <span
                    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                    :class="cred.has_value
                      ? 'bg-green-500/10 text-green-400'
                      : 'bg-yellow-500/10 text-yellow-400'"
                  >
                    <i :class="cred.has_value ? 'pi pi-check-circle' : 'pi pi-exclamation-circle'" class="text-[10px]" />
                    {{ cred.has_value ? 'Set' : 'Not set' }}
                  </span>
                </div>
                <div class="text-xs text-[--klikk-text-muted] mt-0.5 font-mono">{{ cred.key }}</div>
                <div v-if="cred.has_value" class="text-xs text-[--klikk-text-muted] mt-1">
                  <span>{{ cred.hint }}</span>
                  <span class="ml-3">Updated {{ formatTime(cred.updated_at) }}</span>
                </div>

                <!-- Test result -->
                <div v-if="store.testResult[cred.key]" class="mt-2">
                  <span
                    class="text-xs px-2 py-1 rounded"
                    :class="store.testResult[cred.key].ok
                      ? 'bg-green-500/10 text-green-400'
                      : 'bg-red-500/10 text-red-400'"
                  >
                    {{ store.testResult[cred.key].ok
                      ? store.testResult[cred.key].detail || 'OK'
                      : store.testResult[cred.key].error || 'Failed' }}
                  </span>
                </div>
              </div>

              <!-- Right: actions -->
              <div class="flex items-center gap-2 flex-shrink-0">
                <Button
                  v-if="cred.has_value && ['anthropic_api_key', 'openai_api_key', 'voyage_api_key'].includes(cred.key)"
                  label="Test"
                  icon="pi pi-bolt"
                  size="small"
                  severity="info"
                  text
                  :loading="store.testing === cred.key"
                  @click="store.testCredential(cred.key)"
                />
                <Button
                  :label="editingKey === cred.key ? 'Cancel' : (cred.has_value ? 'Update' : 'Set')"
                  :icon="editingKey === cred.key ? 'pi pi-times' : 'pi pi-pencil'"
                  size="small"
                  :severity="editingKey === cred.key ? 'secondary' : 'primary'"
                  text
                  @click="editingKey === cred.key ? cancelEdit() : startEdit(cred.key)"
                />
                <Button
                  v-if="cred.has_value"
                  icon="pi pi-trash"
                  size="small"
                  severity="danger"
                  text
                  @click="store.deleteCredential(cred.key)"
                />
              </div>
            </div>

            <!-- Edit input -->
            <div v-if="editingKey === cred.key" class="mt-3 flex items-center gap-2">
              <input
                v-model="editValue"
                :type="showValue[cred.key] ? 'text' : 'password'"
                :placeholder="`Enter ${cred.label}...`"
                class="flex-1 bg-[--klikk-surface] border border-[--klikk-border] rounded-lg px-4 py-2 text-sm text-[--klikk-text] font-mono placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary] transition-colors"
                @keydown="handleKeydown($event, cred.key, cred.label)"
                autofocus
              />
              <button
                @click="showValue[cred.key] = !showValue[cred.key]"
                class="p-2 text-[--klikk-text-muted] hover:text-[--klikk-text] transition-colors"
              >
                <i :class="showValue[cred.key] ? 'pi pi-eye-slash' : 'pi pi-eye'" class="text-sm" />
              </button>
              <Button
                label="Save"
                icon="pi pi-check"
                size="small"
                severity="success"
                :disabled="!editValue.trim()"
                @click="saveEdit(cred.key, cred.label)"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Info box -->
      <div class="glass-card p-4 text-xs text-[--klikk-text-muted] leading-relaxed">
        <div class="flex items-start gap-2">
          <i class="pi pi-info-circle text-[--klikk-primary] mt-0.5 flex-shrink-0" />
          <div>
            <p>Credentials stored here override values from the <code class="text-[--klikk-text-secondary]">.env</code> file.</p>
            <p class="mt-1">Changes take effect within 60 seconds — no restart required.</p>
            <p class="mt-1">Deleting a credential reverts to the <code class="text-[--klikk-text-secondary]">.env</code> fallback value.</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
