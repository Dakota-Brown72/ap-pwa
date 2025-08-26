<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <div class="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-3">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-1">My Profile</h1>
        <p class="text-base-content text-opacity-70">Manage your account info and preferences</p>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Summary -->
      <div class="lg:col-span-1 card bg-base-100 shadow-md rounded-xl">
        <div class="card-body p-4 text-base-content space-y-3">
          <h2 class="card-title">Summary</h2>
          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-sm text-opacity-70">Username</span>
              <span class="font-medium">{{ user.username }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-opacity-70">Role</span>
              <span>
                <span :class="['badge badge-sm', user.is_admin ? 'badge-primary' : 'badge-ghost']">
                  {{ user.is_admin ? 'Admin' : 'User' }}
                </span>
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-opacity-70">Created</span>
              <span class="tabular-nums">{{ formatDate(user.created_at) }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-sm text-opacity-70">Last Login</span>
              <span class="tabular-nums">{{ formatDate(user.last_login) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Details & Preferences -->
      <div class="lg:col-span-2 flex flex-col gap-6">
        <!-- Contact / Identity -->
        <div class="card bg-base-100 shadow-md rounded-xl">
          <div class="card-body p-4 text-base-content space-y-3">
            <h2 class="card-title">Profile</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label class="label"><span class="label-text">Full Name</span></label>
                <input v-model="form.full_name" type="text" class="input input-bordered input-sm w-full" placeholder="Full name" />
              </div>
              <div>
                <label class="label"><span class="label-text">Email</span></label>
                <input v-model="form.email" type="email" class="input input-bordered input-sm w-full" placeholder="email@example.com" />
              </div>
            </div>
            <div class="flex gap-2 justify-end">
              <button class="btn btn-sm" :disabled="saving" @click="resetProfile">Reset</button>
              <button class="btn btn-primary btn-sm" :disabled="saving" @click="saveProfile">
                <span v-if="saving" class="loading loading-spinner loading-xs"></span>
                <span v-else>Save</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Preferences -->
        <div class="card bg-base-100 shadow-md rounded-xl">
          <div class="card-body p-4 text-base-content space-y-3">
            <h2 class="card-title">Preferences</h2>
            <div class="grid grid-cols-[120px_1fr] gap-2 items-center">
              <label class="text-sm">Theme</label>
              <select v-model="prefs.theme" class="select select-bordered select-sm w-full md:w-56">
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
            <div class="grid grid-cols-[120px_1fr] gap-2 items-center">
              <label class="text-sm">Time Zone</label>
              <select v-model="prefs.timezone" class="select select-bordered select-sm w-full md:w-56">
                <option v-for="tz in timezones" :key="tz" :value="tz">{{ tz }}</option>
              </select>
            </div>
            <div class="grid grid-cols-[120px_1fr] gap-2 items-center">
              <label class="text-sm">Time Format</label>
              <select v-model="prefs.timeFormat" class="select select-bordered select-sm w-full md:w-56">
                <option value="12h">12-hour</option>
                <option value="24h">24-hour</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Security -->
        <div class="card bg-base-100 shadow-md rounded-xl">
          <div class="card-body p-4 text-base-content space-y-3">
            <h2 class="card-title">Security</h2>
            <div class="flex flex-col sm:flex-row gap-2">
              <button class="btn btn-sm w-full sm:w-auto btn-accent dark:btn-primary" @click="openPwdModal">Change Password</button>
              <button class="btn btn-sm w-full sm:w-auto btn-accent dark:btn-primary" @click="openChangeUsername">Change Username</button>
              <router-link v-if="user.is_admin" to="/admin/logins" class="btn btn-sm w-full sm:w-auto btn-accent dark:btn-primary">View Login Logs</router-link>
              <button v-if="user.is_admin" class="btn btn-sm w-full sm:w-auto btn-accent dark:btn-primary" @click="openAddUser">Add User</button>
              <router-link v-if="user.is_admin" to="/admin/users" class="btn btn-sm w-full sm:w-auto btn-accent dark:btn-primary">Manage Users</router-link>
            </div>
          </div>
        </div>
        
        <!-- Change Password Modal -->
        <dialog ref="pwdModal" class="modal">
          <div class="modal-box max-w-md text-base-content">
            <h3 class="font-bold text-lg mb-3">Change Password</h3>
            <div class="space-y-3">
              <div>
                <label class="label"><span class="label-text text-base-content">Current Password</span></label>
                <input v-model="pwd.current" type="password" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <div>
                <label class="label"><span class="label-text text-base-content">New Password</span></label>
                <input v-model="pwd.new1" type="password" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <div>
                <label class="label"><span class="label-text text-base-content">Confirm New Password</span></label>
                <input v-model="pwd.new2" type="password" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <p v-if="pwdError" class="text-error text-sm">{{ pwdError }}</p>
              <p v-if="pwdSuccess" class="text-success text-sm">Password updated.</p>
            </div>
            <div class="modal-action">
              <button class="btn btn-ghost" @click="closePwdModal">Cancel</button>
              <button class="btn btn-primary" :disabled="changingPwd || !canSubmitPwd" @click="submitPwdModal">
                <span v-if="changingPwd" class="loading loading-spinner loading-xs"></span>
                <span v-else>Update</span>
              </button>
            </div>
          </div>
        </dialog>

        <!-- Change Username Modal -->
        <dialog ref="userModal" class="modal">
          <div class="modal-box max-w-md text-base-content">
            <h3 class="font-bold text-lg mb-3">Change Username</h3>
            <div class="space-y-3">
              <div>
                <label class="label"><span class="label-text text-base-content">Current Username</span></label>
                <input v-model="uname.current" type="text" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <div>
                <label class="label"><span class="label-text text-base-content">New Username</span></label>
                <input v-model="uname.new1" type="text" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <div>
                <label class="label"><span class="label-text text-base-content">Confirm New Username</span></label>
                <input v-model="uname.new2" type="text" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <p v-if="uname.error" class="text-error text-sm">{{ uname.error }}</p>
              <p v-if="uname.success" class="text-success text-sm">Username updated.</p>
            </div>
            <div class="modal-action">
              <button class="btn btn-ghost" @click="closeChangeUsername">Cancel</button>
              <button class="btn btn-primary" :disabled="changingUser || !canSubmitUsername" @click="submitChangeUsername">
                <span v-if="changingUser" class="loading loading-spinner loading-xs"></span>
                <span v-else>Update</span>
              </button>
            </div>
          </div>
        </dialog>

        <!-- Add User Modal (Admin only) -->
        <dialog ref="addUserModal" class="modal">
          <div class="modal-box max-w-md text-base-content">
            <h3 class="font-bold text-lg mb-3">Add User</h3>
            <div class="space-y-3">
              <div>
                <label class="label"><span class="label-text text-base-content">Username</span></label>
                <input v-model="newUser.username" type="text" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <div>
                <label class="label"><span class="label-text text-base-content">Password</span></label>
                <input v-model="newUser.password" type="password" class="input input-bordered input-sm w-full text-base-content" />
              </div>
              <div class="form-control">
                <label class="label cursor-pointer justify-start gap-2">
                  <input type="checkbox" class="checkbox checkbox-sm" v-model="newUser.is_admin" />
                  <span class="label-text text-base-content">Grant admin access</span>
                </label>
              </div>
              <p v-if="newUser.error" class="text-error text-sm">{{ newUser.error }}</p>
              <p v-if="newUser.success" class="text-success text-sm">User created.</p>
            </div>
            <div class="modal-action">
              <button class="btn btn-ghost" @click="closeAddUser">Cancel</button>
              <button class="btn btn-primary" :disabled="creatingUser || !canSubmitNewUser" @click="submitAddUser">
                <span v-if="creatingUser" class="loading loading-spinner loading-xs"></span>
                <span v-else>Create</span>
              </button>
            </div>
          </div>
        </dialog>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/services/api.js'

export default {
  name: 'Profile',
  data() {
    return {
      user: { username: '', is_admin: false, email: '', full_name: '', created_at: null, last_login: null },
      form: { email: '', full_name: '' },
      prefs: { theme: 'system', timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC', timeFormat: '12h' },
      timezones: ['UTC', 'America/Chicago', 'America/New_York', 'America/Los_Angeles', 'Europe/London'],
      pwd: { current: '', new1: '', new2: '' },
      pwdError: '',
      pwdSuccess: false,
      uname: { current: '', new1: '', new2: '', error: '', success: false },
      newUser: { username: '', password: '', is_admin: false, error: '', success: false },
      saving: false,
      changingPwd: false,
      changingAll: false,
      changingUser: false,
      creatingUser: false,
    }
  },
  async mounted() {
    await this.load()
  },
  computed: {
    canSubmitPwd() {
      const p = this.pwd || {}
      return !!(p.current && p.new1 && p.new2 && p.new1 === p.new2)
    },
    canSubmitUsername() {
      const u = this.uname || {}
      return !!(u.current && u.new1 && u.new2 && u.new1 === u.new2 && u.new1.length >= 3 && u.new1.length <= 32)
    },
    canSubmitNewUser() {
      const n = this.newUser || {}
      return !!(n.username && n.password && n.username.length >= 3 && n.username.length <= 32 && n.password.length >= 8)
    }
  },
  methods: {
    async load() {
      const me = await api.getCurrentUser()
      this.user = me.user || {}
      this.form.email = this.user.email || ''
      this.form.full_name = this.user.full_name || ''
    },
    resetProfile() {
      this.form.email = this.user.email || ''
      this.form.full_name = this.user.full_name || ''
    },
    async saveProfile() {
      // Stub: wire later to backend update endpoint
      this.saving = true
      try {
        await new Promise(r => setTimeout(r, 600))
        this.user.email = this.form.email
        this.user.full_name = this.form.full_name
      } finally {
        this.saving = false
      }
    },
    openPwdModal() {
      if (this.$refs.pwdModal) this.$refs.pwdModal.showModal()
    },
    closePwdModal() {
      if (this.$refs.pwdModal) this.$refs.pwdModal.close()
    },
    async submitPwdModal() {
      if (!this.canSubmitPwd) return
      this.changingPwd = true
      this.pwdError = ''
      this.pwdSuccess = false
      try {
        await api.changePassword(this.pwd.current, this.pwd.new1, this.pwd.new2)
        this.pwd.current = this.pwd.new1 = this.pwd.new2 = ''
        this.pwdSuccess = true
        setTimeout(() => {
          this.closePwdModal()
          this.pwdSuccess = false
        }, 800)
      } catch (e) {
        this.pwdError = (e && e.data && e.data.error) ? e.data.error : 'Failed to change password'
      } finally {
        // If backend returned an error, it would throw; capture in catch on caller
        this.changingPwd = false
      }
    },
    async logoutAll() {
      // Stub: would invalidate tokens server-side later
      this.changingAll = true
      try {
        await new Promise(r => setTimeout(r, 600))
      } finally {
        this.changingAll = false
      }
    },
    openAddUser() {
      this.newUser = { username: '', password: '', is_admin: false, error: '', success: false }
      if (this.$refs.addUserModal) this.$refs.addUserModal.showModal()
    },
    openChangeUsername() {
      this.uname.current = this.user.username || ''
      this.uname.new1 = this.uname.new2 = ''
      this.uname.error = ''
      this.uname.success = false
      if (this.$refs.userModal) this.$refs.userModal.showModal()
    },
    closeChangeUsername() {
      if (this.$refs.userModal) this.$refs.userModal.close()
    },
    closeAddUser() {
      if (this.$refs.addUserModal) this.$refs.addUserModal.close()
    },
    async submitChangeUsername() {
      if (!this.canSubmitUsername) return
      this.changingUser = true
      this.uname.error = ''
      this.uname.success = false
      try {
        const res = await api.changeUsername(this.uname.current, this.uname.new1, this.uname.new2)
        if (res && res.changed) {
          this.user.username = res.username
          this.uname.success = true
          setTimeout(() => {
            this.closeChangeUsername()
          }, 600)
        }
      } catch (e) {
        this.uname.error = (e && e.data && e.data.error) ? e.data.error : 'Failed to change username'
      } finally {
        this.changingUser = false
      }
    },
    async submitAddUser() {
      if (!this.canSubmitNewUser) return
      this.creatingUser = true
      this.newUser.error = ''
      this.newUser.success = false
      try {
        await api.createUser(this.newUser.username, this.newUser.password, this.newUser.is_admin)
        this.newUser.success = true
        setTimeout(() => {
          this.closeAddUser()
        }, 800)
      } catch (e) {
        this.newUser.error = (e && e.data && e.data.error) ? e.data.error : 'Failed to create user'
      } finally {
        this.creatingUser = false
      }
    },
    formatDate(value) {
      if (!value) return '—'
      try {
        const d = new Date(value)
        return d.toLocaleString()
      } catch {
        return '—'
      }
    }
  }
}
</script> 