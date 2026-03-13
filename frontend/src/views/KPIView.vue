<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Button from 'primevue/button'
import KPICard from '../components/widgets/KPICard.vue'
import PeriodPicker from '../components/common/PeriodPicker.vue'

const loading = ref(false)
const kpiData = ref<any>(null)
const error = ref('')
const year = ref('')
const month = ref('')

async function loadKPIs() {
  loading.value = true
  error.value = ''
  try {
    const params = new URLSearchParams()
    if (year.value) params.set('year', year.value)
    if (month.value) params.set('month', month.value)
    const res = await fetch(`/api/kpis/values?${params}`)
    kpiData.value = await res.json()
    if (kpiData.value?.error) error.value = kpiData.value.error
  } catch (e: any) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

// KPI definitions
const definitions = ref<any>(null)

async function loadDefinitions() {
  const res = await fetch('/api/kpis/')
  definitions.value = await res.json()
}

async function removeKPI(kpiId: string) {
  await fetch(`/api/kpis/${kpiId}`, { method: 'DELETE' })
  await loadDefinitions()
}

onMounted(loadDefinitions)
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-6">
      <div>
        <h2 class="text-xl font-bold text-[--klikk-text]">KPI Dashboard</h2>
        <p class="text-sm text-[--klikk-text-secondary] mt-0.5">
          Key performance indicators from TM1
        </p>
      </div>
      <div class="flex items-center gap-3">
        <PeriodPicker v-model:year="year" v-model:month="month" />
        <Button label="Refresh KPIs" icon="pi pi-refresh" :loading="loading" @click="loadKPIs" />
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="mb-4 text-sm text-[--klikk-danger] bg-[--klikk-danger]/10 rounded-lg px-4 py-3">
      {{ error }}
    </div>

    <!-- KPI Cards -->
    <div v-if="kpiData?.categories" class="space-y-8">
      <div v-for="(kpis, category) in kpiData.categories" :key="category">
        <h3 class="text-sm font-semibold text-[--klikk-text-secondary] uppercase tracking-wide mb-3">
          {{ category }}
        </h3>
        <div class="grid grid-cols-4 gap-4">
          <KPICard
            v-for="kpi in kpis"
            :key="kpi.id"
            :title="kpi.name"
            :value="kpi.value"
            :format="kpi.format || 'number'"
            :status="kpi.status || 'ok'"
            :subtitle="kpi.description"
          />
        </div>
      </div>

      <!-- Period info -->
      <div v-if="kpiData.period" class="text-xs text-[--klikk-text-muted]">
        Period: {{ kpiData.period.month }} {{ kpiData.period.year }}
      </div>
    </div>

    <!-- Empty state -->
    <div v-else-if="!loading" class="text-center py-16">
      <i class="pi pi-chart-bar text-3xl text-[--klikk-text-muted] mb-3" />
      <p class="text-[--klikk-text-secondary]">
        Click <strong>Refresh KPIs</strong> to load metrics from TM1
      </p>
    </div>

    <!-- KPI Management -->
    <div class="mt-12">
      <h3 class="text-lg font-semibold text-[--klikk-text] mb-4">Defined KPIs</h3>

      <div v-if="definitions?.categories" class="space-y-3">
        <div
          v-for="(items, cat) in definitions.categories"
          :key="cat"
          class="glass-card p-4"
        >
          <h4 class="text-sm font-medium text-[--klikk-text-secondary] mb-2">{{ cat }}</h4>
          <div class="space-y-2">
            <div
              v-for="kpi in items"
              :key="kpi.id"
              class="flex items-center justify-between px-3 py-2 rounded bg-[--klikk-surface-hover]/50"
            >
              <div>
                <span class="text-sm font-medium text-[--klikk-text]">{{ kpi.name }}</span>
                <span class="text-xs text-[--klikk-text-muted] ml-2 font-mono">{{ kpi.id }}</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="text-xs text-[--klikk-text-muted]">{{ kpi.source_type }} · {{ kpi.format }}</span>
                <Button
                  icon="pi pi-trash"
                  size="small"
                  severity="danger"
                  text
                  @click="removeKPI(kpi.id)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="text-sm text-[--klikk-text-muted]">
        No KPIs defined. Use the AI Chat to create them interactively.
      </div>
    </div>
  </div>
</template>
