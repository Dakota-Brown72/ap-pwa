<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <div class="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-3">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-1">Login Attempts</h1>
        <p class="text-base-content text-opacity-70">Recent authentication activity</p>
      </div>
      <div class="flex gap-2">
        <button class="btn btn-sm" @click="refresh" :disabled="loading">
          <span v-if="loading" class="loading loading-spinner loading-xs"></span>
          <span v-else>↻</span>
          Refresh
        </button>
      </div>
    </div>

    <div class="card bg-base-100 shadow-md rounded-xl">
      <div class="card-body p-4 text-base-content">
        <div class="overflow-x-auto">
          <table class="table table-sm">
            <thead>
              <tr>
                <th class="whitespace-nowrap">Time</th>
                <th class="whitespace-nowrap">Username</th>
                <th class="whitespace-nowrap">IP</th>
                <th class="whitespace-nowrap">Location</th>
                <th class="whitespace-nowrap">Status</th>
                <th class="whitespace-nowrap">User Agent</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(a, idx) in attempts" :key="idx">
                <td class="tabular-nums whitespace-nowrap">{{ formatDate(a.attempt_time) }}</td>
                <td class="whitespace-nowrap">{{ a.username || '—' }}</td>
                <td class="whitespace-nowrap">{{ a.ip_address }}</td>
                <td class="whitespace-nowrap">{{ a.location || 'Unknown' }}</td>
                <td class="whitespace-nowrap">
                  <span :class="['badge badge-sm', a.blocked ? 'badge-error' : (a.success ? 'badge-success' : 'badge-warning')]">
                    {{ a.blocked ? 'Blocked' : (a.success ? 'Success' : 'Failed') }}
                  </span>
                </td>
                <td class="truncate max-w-[320px]">{{ a.user_agent || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api.js'

export default {
  name: 'AdminLoginAttempts',
  data() {
    return {
      loading: false,
      attempts: [],
    }
  },
  async mounted() {
    await this.refresh()
  },
  methods: {
    async refresh() {
      this.loading = true
      try {
        const res = await api.request('/admin/security/login-attempts')
        this.attempts = res.login_attempts || []
      } catch (e) {
        this.attempts = []
      } finally {
        this.loading = false
      }
    },
    formatDate(value) {
      if (!value) return '—'
      try { return new Date(value).toLocaleString() } catch { return '—' }
    }
  }
}
</script> 