<template>
  <div ref="rootEl" class="dropdown dropdown-end" :class="{ 'dropdown-open': isOpen }">
    <button @click.stop="toggleOpen" class="btn btn-outline btn-sm sm:btn-md text-primary-content hover:bg-primary-focus">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        class="h-8 w-8 sm:h-6 sm:w-6"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M4 6h16M4 12h16M4 18h16"
        />
      </svg>
    </button>

    <ul
      class="menu menu-compact sm:menu-sm dropdown-content mt-2 sm:mt-3 z-[100] p-2 shadow bg-base-200 rounded-box w-40 sm:w-52"
      @click="close"
    >
      <li><router-link to="/profile" @click="close">Profile</router-link></li>
      <li><router-link to="/settings" @click="close">Settings</router-link></li>
      <li><a @click.prevent="handleLogout">Logout</a></li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import apiService from '@/services/api.js'

const router = useRouter()
const route = useRoute()
const isOpen = ref(false)
const rootEl = ref(null)

const toggleOpen = () => {
  isOpen.value = !isOpen.value
}
const close = () => {
  isOpen.value = false
}

const onDocumentClick = (e) => {
  if (!rootEl.value) return
  if (!rootEl.value.contains(e.target)) {
    close()
  }
}
const onKeydown = (e) => {
  if (e.key === 'Escape') close()
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick, { capture: true })
  document.addEventListener('keydown', onKeydown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick, { capture: true })
  document.removeEventListener('keydown', onKeydown)
})

// Auto-close on any route change
watch(() => route.fullPath, () => close())

const handleLogout = async () => {
  try {
    close()
    await apiService.logout()
    window.location.reload()
  } catch (error) {
    console.error('Logout failed:', error)
    window.location.reload()
  }
}
</script>

<style scoped>
/* Ensure button has touch-friendly tap area */
.btn {
  min-height: 44px;
  min-width: 44px;
}
</style>