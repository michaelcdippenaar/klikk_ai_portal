<script setup lang="ts">
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useSkillsStore } from '../stores/skills'
import Button from 'primevue/button'

const skillsStore = useSkillsStore()

// UI State
const selectedSkill = ref<{ type: 'widget' | 'tool'; name: string } | null>(null)
const expandedWidget = ref<string | null>(null)
const expandedTool = ref<string | null>(null)
const toolSourceCache = ref<Record<string, string>>({})
const toolSourceLoading = ref<string | null>(null)
const showVersionPanel = ref(false)
const chatInput = ref('')
const chatContainer = ref<HTMLElement>()
const deleteConfirm = ref<string | null>(null)
const error = ref('')

// Computed
const widgetTypeEntries = computed(() => Object.entries(skillsStore.widgetTypes))
const totalSkillCount = computed(() => widgetTypeEntries.value.length + skillsStore.toolModules.length)
const toolModuleGroups = computed(() => {
  const groups: Record<string, any[]> = {}
  for (const mod of skillsStore.toolModules) {
    const label = mod.source_label || 'mcp_server/skills'
    if (!groups[label]) groups[label] = []
    groups[label].push(mod)
  }
  return Object.entries(groups).map(([label, modules]) => ({
    label: label === 'mcp_tm1_server' ? 'MCP TM1 Server' : 'Agent Skills',
    modules,
  }))
})

// Format YAML-like display for widget definitions
function formatDefinition(def: any): string {
  return JSON.stringify(def, null, 2)
}

// Toggle widget expansion
function toggleWidget(name: string) {
  expandedWidget.value = expandedWidget.value === name ? null : name
  expandedTool.value = null
}

// Toggle tool expansion and load source
async function toggleTool(moduleName: string) {
  if (expandedTool.value === moduleName) {
    expandedTool.value = null
    return
  }
  expandedTool.value = moduleName
  expandedWidget.value = null

  if (!toolSourceCache.value[moduleName]) {
    toolSourceLoading.value = moduleName
    try {
      const data = await skillsStore.getToolSource(moduleName)
      toolSourceCache.value[moduleName] = data.source || '# No source available'
    } catch {
      toolSourceCache.value[moduleName] = '# Failed to load source'
    } finally {
      toolSourceLoading.value = null
    }
  }
}

// Delete widget type
async function handleDelete(name: string) {
  if (deleteConfirm.value !== name) {
    deleteConfirm.value = name
    return
  }
  try {
    await skillsStore.deleteWidgetType(name)
    deleteConfirm.value = null
    if (expandedWidget.value === name) expandedWidget.value = null
  } catch (e: any) {
    error.value = `Failed to delete: ${e.message}`
  }
}

// Restore version
async function handleRestore(versionId: string) {
  try {
    await skillsStore.restoreVersion(versionId)
    showVersionPanel.value = false
  } catch (e: any) {
    error.value = `Failed to restore: ${e.message}`
  }
}

// Chat
function scrollChatToBottom() {
  nextTick(() => {
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  })
}

watch(() => skillsStore.chatHistory.length, scrollChatToBottom)
watch(() => skillsStore.chatLoading, scrollChatToBottom)

async function handleChatSend() {
  const text = chatInput.value.trim()
  if (!text || skillsStore.chatLoading) return
  chatInput.value = ''
  await skillsStore.sendChatMessage(text)
}

function handleChatKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleChatSend()
  }
}

async function handleApplyChanges(changes: any, msgIndex: number) {
  try {
    await skillsStore.applyChatChanges(changes)
    // Mark as applied
    skillsStore.chatHistory[msgIndex].proposed_changes = null
    skillsStore.chatHistory[msgIndex].content += '\n\n*Changes applied successfully.*'
  } catch (e: any) {
    error.value = `Failed to apply changes: ${e.message}`
  }
}

function handleRejectChanges(msgIndex: number) {
  skillsStore.chatHistory[msgIndex].proposed_changes = null
  skillsStore.chatHistory[msgIndex].content += '\n\n*Changes rejected.*'
}

// Format relative time
function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

onMounted(async () => {
  await Promise.all([
    skillsStore.fetchSkills(),
    skillsStore.fetchVersions(),
  ])
})
</script>

<template>
  <div class="h-[calc(100vh-8rem)]">
    <!-- Top Bar -->
    <div class="flex items-center justify-between mb-4">
      <div>
        <h2 class="text-xl font-bold text-[--klikk-text]">Skills Management</h2>
        <p class="text-sm text-[--klikk-text-secondary] mt-0.5">
          View, edit, and version AI agent skills
        </p>
      </div>
      <div class="flex items-center gap-3">
        <span class="text-xs font-medium text-[--klikk-text-muted] bg-[--klikk-surface] px-2.5 py-1 rounded-full">
          {{ totalSkillCount }} skills
        </span>
        <div class="relative">
          <Button
            label="Version History"
            icon="pi pi-history"
            severity="secondary"
            size="small"
            @click="showVersionPanel = !showVersionPanel"
          />
          <!-- Version dropdown -->
          <transition name="fade">
            <div
              v-if="showVersionPanel"
              class="absolute right-0 top-full mt-2 w-80 glass-card p-0 z-50 shadow-xl border border-[--klikk-border] rounded-lg overflow-hidden"
            >
              <div class="px-4 py-3 border-b border-[--klikk-border]">
                <span class="text-sm font-semibold text-[--klikk-text]">Version History</span>
              </div>
              <div class="max-h-64 overflow-y-auto">
                <div
                  v-for="ver in skillsStore.versions"
                  :key="ver.id"
                  class="flex items-center justify-between px-4 py-2.5 hover:bg-[--klikk-surface-hover] transition-colors"
                >
                  <div>
                    <div class="text-sm text-[--klikk-text]">{{ ver.label || ver.id }}</div>
                    <div class="text-xs text-[--klikk-text-muted]">
                      {{ ver.created_at ? formatTime(ver.created_at) : ver.id }}
                    </div>
                  </div>
                  <Button
                    label="Restore"
                    icon="pi pi-replay"
                    size="small"
                    text
                    @click="handleRestore(ver.id)"
                  />
                </div>
                <div v-if="skillsStore.versions.length === 0" class="px-4 py-6 text-center text-sm text-[--klikk-text-muted]">
                  No versions yet
                </div>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 text-sm text-[--klikk-danger] bg-[--klikk-danger]/10 rounded-lg px-4 py-3 flex items-center justify-between">
      <span>{{ error }}</span>
      <button @click="error = ''" class="text-[--klikk-danger] hover:opacity-70">
        <i class="pi pi-times text-xs" />
      </button>
    </div>

    <!-- Main Layout: Two Panels -->
    <div class="flex gap-4 h-[calc(100%-4rem)]">

      <!-- Left Panel: Skills List -->
      <div class="w-1/2 glass-card flex flex-col overflow-hidden">
        <div class="px-4 py-3 border-b border-[--klikk-border] flex items-center gap-2">
          <i class="pi pi-list text-[--klikk-primary]" />
          <span class="text-sm font-semibold text-[--klikk-text]">Skills</span>
        </div>

        <div class="flex-1 overflow-y-auto px-4 py-3 space-y-6">
          <!-- Loading -->
          <div v-if="skillsStore.loading" class="flex items-center justify-center py-12">
            <i class="pi pi-spin pi-spinner text-2xl text-[--klikk-primary]" />
          </div>

          <template v-else>
            <!-- Widget Types Section -->
            <div>
              <h3 class="text-xs font-semibold text-[--klikk-text-secondary] uppercase tracking-wide mb-2">
                Widget Types
              </h3>
              <div v-if="widgetTypeEntries.length === 0" class="text-sm text-[--klikk-text-muted] py-3">
                No widget types defined.
              </div>
              <div class="space-y-1">
                <div v-for="[name, def] in widgetTypeEntries" :key="name">
                  <!-- Widget item row -->
                  <div
                    class="flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors"
                    :class="expandedWidget === name ? 'bg-[--klikk-primary]/10' : 'hover:bg-[--klikk-surface-hover]'"
                    @click="toggleWidget(name)"
                  >
                    <div class="flex items-center gap-3 min-w-0">
                      <i class="pi pi-box text-[--klikk-primary] text-sm flex-shrink-0" />
                      <div class="min-w-0">
                        <div class="text-sm font-medium text-[--klikk-text] truncate">{{ name }}</div>
                        <div class="text-xs text-[--klikk-text-muted] truncate">
                          {{ def.description || 'No description' }}
                        </div>
                      </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                      <span class="text-[10px] text-[--klikk-text-muted] bg-[--klikk-surface] px-1.5 py-0.5 rounded">
                        {{ Object.keys(def.props || {}).length }} props
                      </span>
                      <span v-if="def.default_size" class="text-[10px] text-[--klikk-text-muted] bg-[--klikk-surface] px-1.5 py-0.5 rounded">
                        {{ def.default_size?.w || '?' }}x{{ def.default_size?.h || '?' }}
                      </span>
                      <Button
                        icon="pi pi-pencil"
                        size="small"
                        text
                        @click.stop
                      />
                      <Button
                        :icon="deleteConfirm === name ? 'pi pi-check' : 'pi pi-trash'"
                        size="small"
                        :severity="deleteConfirm === name ? 'warning' : 'danger'"
                        text
                        @click.stop="handleDelete(name)"
                      />
                    </div>
                  </div>

                  <!-- Expanded definition -->
                  <transition name="fade">
                    <div v-if="expandedWidget === name" class="ml-8 mt-1 mb-2">
                      <pre class="text-xs font-mono text-[--klikk-text-secondary] bg-[--klikk-surface] rounded-lg p-3 overflow-x-auto max-h-64 overflow-y-auto">{{ formatDefinition(def) }}</pre>
                    </div>
                  </transition>
                </div>
              </div>
            </div>

            <!-- Tool Modules Section -->
            <div v-for="group in toolModuleGroups" :key="group.label">
              <h3 class="text-xs font-semibold text-[--klikk-text-secondary] uppercase tracking-wide mb-2">
                {{ group.label }}
              </h3>
              <div v-if="group.modules.length === 0" class="text-sm text-[--klikk-text-muted] py-3">
                No tool modules found.
              </div>
              <div class="space-y-1">
                <div v-for="mod in group.modules" :key="mod.module">
                  <!-- Tool module row -->
                  <div
                    class="flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors"
                    :class="expandedTool === mod.module ? 'bg-[--klikk-secondary]/10' : 'hover:bg-[--klikk-surface-hover]'"
                    @click="toggleTool(mod.module)"
                  >
                    <div class="flex items-center gap-3 min-w-0">
                      <i class="pi pi-code text-[--klikk-secondary] text-sm flex-shrink-0" />
                      <div class="min-w-0">
                        <div class="text-sm font-medium text-[--klikk-text] truncate">{{ mod.module }}</div>
                        <div class="text-xs text-[--klikk-text-muted] truncate max-w-md">
                          {{ mod.description ? mod.description.split('\n')[0].slice(0, 80) : (mod.tools || []).map((t: any) => t.name || t).join(', ') || 'No tools' }}
                        </div>
                      </div>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0">
                      <span class="text-[10px] text-[--klikk-text-muted] bg-[--klikk-surface] px-1.5 py-0.5 rounded">
                        {{ mod.tool_count || (mod.tools || []).length }} tools
                      </span>
                    </div>
                  </div>

                  <!-- Expanded tool details -->
                  <transition name="fade">
                    <div v-if="expandedTool === mod.module" class="ml-8 mt-1 mb-2 space-y-2">
                      <!-- Module description -->
                      <div v-if="mod.description" class="text-xs text-[--klikk-text-secondary] bg-[--klikk-surface] rounded-lg p-2.5 whitespace-pre-wrap">
                        {{ mod.description }}
                      </div>

                      <!-- Tool list -->
                      <div v-if="mod.tools && mod.tools.length > 0" class="space-y-1">
                        <div
                          v-for="tool in mod.tools"
                          :key="tool.name || tool"
                          class="text-xs bg-[--klikk-surface] rounded-lg p-2.5"
                        >
                          <div class="font-mono font-medium text-[--klikk-text]">{{ tool.name || tool }}</div>
                          <div v-if="tool.description" class="text-[--klikk-text-muted] mt-0.5">{{ tool.description }}</div>
                          <pre v-if="tool.parameters" class="font-mono text-[--klikk-text-secondary] mt-1 overflow-x-auto">{{ JSON.stringify(tool.parameters, null, 2) }}</pre>
                        </div>
                      </div>

                      <!-- Source code -->
                      <div>
                        <div class="text-xs font-medium text-[--klikk-text-secondary] mb-1">Source Code</div>
                        <div v-if="toolSourceLoading === mod.module" class="flex items-center gap-2 text-xs text-[--klikk-text-muted] py-2">
                          <i class="pi pi-spin pi-spinner text-xs" />
                          Loading source...
                        </div>
                        <pre
                          v-else-if="toolSourceCache[mod.module]"
                          class="text-xs font-mono text-[--klikk-text-secondary] bg-[--klikk-surface] rounded-lg p-3 overflow-x-auto max-h-64 overflow-y-auto"
                        >{{ toolSourceCache[mod.module] }}</pre>
                      </div>
                    </div>
                  </transition>
                </div>
              </div>
            </div>

            <!-- Empty state for all -->
            <div v-if="widgetTypeEntries.length === 0 && skillsStore.toolModules.length === 0" class="text-center py-12">
              <i class="pi pi-cog text-3xl text-[--klikk-text-muted] mb-3 block" />
              <p class="text-[--klikk-text-secondary] text-sm">
                No skills loaded yet.
              </p>
              <p class="text-[--klikk-text-muted] text-xs mt-1">
                Use the chat to create new widget types or check the server configuration.
              </p>
            </div>
          </template>
        </div>
      </div>

      <!-- Right Panel: Skills Agent Chat -->
      <div class="w-1/2 glass-card flex flex-col overflow-hidden">
        <div class="px-4 py-3 border-b border-[--klikk-border] flex items-center justify-between">
          <div class="flex items-center gap-2">
            <i class="pi pi-sparkles text-[--klikk-primary]" />
            <span class="text-sm font-semibold text-[--klikk-text]">Skills Agent</span>
            <span class="text-xs text-[--klikk-text-muted] ml-1">
              Edit skills with natural language
            </span>
          </div>
          <button
            v-if="skillsStore.chatHistory.length > 0"
            @click="skillsStore.clearChat()"
            class="text-[10px] text-[--klikk-text-muted] hover:text-[--klikk-danger] transition-colors"
          >
            Clear chat
          </button>
        </div>

        <!-- Chat Messages -->
        <div ref="chatContainer" class="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          <!-- Empty state -->
          <div v-if="skillsStore.chatHistory.length === 0" class="flex flex-col items-center justify-center h-full text-center">
            <i class="pi pi-sparkles text-4xl text-[--klikk-text-muted] mb-3" />
            <p class="text-[--klikk-text-secondary] text-sm">
              Describe changes to widget types or skills
            </p>
            <p class="text-[--klikk-text-muted] text-xs mt-1">
              e.g. "Add a new chart widget type with bar and line options"
            </p>
          </div>

          <!-- Messages -->
          <div
            v-for="(msg, i) in skillsStore.chatHistory"
            :key="i"
            class="flex items-start gap-3 animate-fade-in"
            :class="msg.role === 'user' ? 'flex-row-reverse' : ''"
          >
            <!-- Avatar -->
            <div
              class="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              :class="msg.role === 'user' ? 'bg-[--klikk-secondary]/20' : 'bg-[--klikk-primary]/20'"
            >
              <i
                :class="msg.role === 'user' ? 'pi pi-user text-[--klikk-secondary]' : 'pi pi-sparkles text-[--klikk-primary]'"
                class="text-sm"
              />
            </div>

            <!-- Content -->
            <div class="max-w-[85%] space-y-2">
              <div
                :class="msg.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'"
                class="px-4 py-3 text-sm leading-relaxed"
              >
                <div class="whitespace-pre-wrap">{{ msg.content }}</div>
              </div>

              <!-- Proposed changes diff -->
              <div v-if="msg.proposed_changes" class="rounded-lg border border-[--klikk-border] overflow-hidden">
                <div class="px-3 py-2 bg-[--klikk-surface] border-b border-[--klikk-border] flex items-center gap-2">
                  <i class="pi pi-file-edit text-[--klikk-warning] text-xs" />
                  <span class="text-xs font-medium text-[--klikk-text]">Proposed Changes</span>
                </div>
                <pre class="text-xs font-mono text-[--klikk-text-secondary] p-3 overflow-x-auto max-h-48 overflow-y-auto bg-[--klikk-bg]">{{ JSON.stringify(msg.proposed_changes, null, 2) }}</pre>
                <div class="px-3 py-2 bg-[--klikk-surface] border-t border-[--klikk-border] flex items-center gap-2">
                  <Button
                    label="Apply"
                    icon="pi pi-check"
                    size="small"
                    severity="success"
                    @click="handleApplyChanges(msg.proposed_changes, i)"
                  />
                  <Button
                    label="Reject"
                    icon="pi pi-times"
                    size="small"
                    severity="danger"
                    text
                    @click="handleRejectChanges(i)"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Thinking indicator -->
          <div v-if="skillsStore.chatLoading" class="flex items-start gap-3 animate-fade-in">
            <div class="w-8 h-8 rounded-lg bg-[--klikk-primary]/20 flex items-center justify-center flex-shrink-0">
              <i class="pi pi-spin pi-spinner text-[--klikk-primary] text-sm" />
            </div>
            <div class="chat-message-assistant px-4 py-3 text-sm">
              <div class="flex items-center gap-2 text-[--klikk-text-secondary]">
                <span>Thinking</span>
                <span class="animate-pulse">...</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Chat Input -->
        <div class="px-4 py-3 border-t border-[--klikk-border] bg-[--klikk-bg]">
          <div class="flex items-end gap-2">
            <textarea
              v-model="chatInput"
              @keydown="handleChatKeydown"
              placeholder="Describe skill changes... e.g. 'Add a pie chart widget type'"
              rows="1"
              class="flex-1 resize-none bg-[--klikk-surface] border border-[--klikk-border] rounded-lg px-4 py-2.5 text-sm text-[--klikk-text] placeholder:text-[--klikk-text-muted] focus:outline-none focus:border-[--klikk-primary] transition-colors"
              :disabled="skillsStore.chatLoading"
            />
            <button
              @click="handleChatSend"
              :disabled="!chatInput.trim() || skillsStore.chatLoading"
              class="p-2.5 rounded-lg bg-[--klikk-primary] text-white hover:bg-[--klikk-primary]/80 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <i class="pi pi-send text-sm" />
            </button>
          </div>
          <div class="mt-1.5">
            <span class="text-[10px] text-[--klikk-text-muted]">
              Shift+Enter for new line
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
