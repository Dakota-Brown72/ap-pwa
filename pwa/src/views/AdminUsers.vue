<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <div class="mb-6 flex items-end justify-between">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-1">Manage Users</h1>
        <p class="text-base-content text-opacity-70">View usernames and roles</p>
      </div>
    </div>

    <div class="card bg-base-100 shadow-md rounded-xl">
      <div class="card-body p-4 text-base-content">
        <div class="overflow-x-auto">
          <table class="table table-sm">
            <thead>
              <tr>
                <th>Username</th>
                <th>Role</th>
                <th>Active</th>
                <th class="w-40">Access</th>
                <th>Created</th>
                <th>Last Login</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id">
                <td class="whitespace-nowrap">{{ u.username }}</td>
                <td class="whitespace-nowrap">
                  <span :class="['badge badge-sm', u.is_admin ? 'badge-primary' : 'badge-ghost']">{{ u.is_admin ? 'Admin' : 'User' }}</span>
                </td>
                <td class="whitespace-nowrap">
                  <span :class="['badge badge-sm', u.is_active ? 'badge-success' : 'badge-neutral']">{{ u.is_active ? 'Yes' : 'No' }}</span>
                </td>
                <td class="whitespace-nowrap">
                  <button class="btn btn-xs btn-accent dark:btn-primary" @click="openAccess(u)">Edit Access</button>
                </td>
                <td class="whitespace-nowrap tabular-nums">{{ formatDate(u.created_at) }}</td>
                <td class="whitespace-nowrap tabular-nums">{{ formatDate(u.last_login) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Access Modal -->
    <dialog ref="accessModal" class="modal">
      <div class="modal-box max-w-md text-base-content">
        <h3 class="font-bold text-lg mb-3">Edit Camera Access</h3>
        <div v-if="accessUser" class="space-y-3">
          <p class="text-sm text-opacity-70">User: <span class="font-medium">{{ accessUser.username }}</span></p>
          <div class="space-y-2">
            <div class="flex gap-2">
              <button :class="['btn btn-sm', accessSelection.mode==='all' ? 'btn-primary' : '']" @click="accessSelection.mode='all'">All</button>
              <button :class="['btn btn-sm', accessSelection.mode==='custom' ? 'btn-primary' : '']" @click="accessSelection.mode='custom'">Custom</button>
            </div>
            <div v-if="accessSelection.mode==='custom'" class="grid grid-cols-2 gap-2 mt-2">
              <button v-for="cam in accessCameras" :key="cam" :class="['btn btn-sm', accessSelection.cameras.has(cam) ? 'btn-accent dark:btn-primary' : '']" @click="toggleCamera(cam)">
                {{ cam.replace('_',' ').replace('_',' ') }}
              </button>
            </div>
          </div>
        </div>
        <div class="modal-action">
          <button class="btn btn-ghost" @click="closeAccess">Cancel</button>
          <button class="btn btn-primary" @click="saveAccess">Save</button>
        </div>
      </div>
    </dialog>
  </div>
</template>

<script>
import api from '@/services/api.js'

export default {
  name: 'AdminUsers',
  data() {
    return {
      users: [],
      savingId: 0,
      accessUser: null,
      accessCameras: ['Frontyard', 'Backyard', 'Living_Room', 'Nursery'],
      accessSelection: { mode: 'all', cameras: new Set() },
    }
  },
  async mounted() {
    await this.load()
  },
  methods: {
    async load() {
      try {
        const res = await api.listUsers()
        this.users = res.users || []
      } catch (e) {
        this.users = []
      }
    },
    openAccess(user) {
      this.accessUser = user
      // Default selection mode to all for now
      this.accessSelection = { mode: 'all', cameras: new Set() }
      if (this.$refs.accessModal) this.$refs.accessModal.showModal()
    },
    closeAccess() {
      if (this.$refs.accessModal) this.$refs.accessModal.close()
    },
    toggleCamera(cam) {
      if (this.accessSelection.cameras.has(cam)) this.accessSelection.cameras.delete(cam)
      else this.accessSelection.cameras.add(cam)
    },
    async saveAccess() {
      // Placeholder: will call backend later
      this.closeAccess()
    },
    formatDate(value) {
      if (!value) return '—'
      try { return new Date(value).toLocaleString() } catch { return '—' }
    }
  }
}
</script> 