<template>
  <div class="dropdown dropdown-end">
    <button tabindex="0" class="btn btn-outline btn-sm sm:btn-md text-primary-content hover:bg-primary-focus">
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
      tabindex="0"
      class="menu menu-compact sm:menu-sm dropdown-content mt-2 sm:mt-3 z-[1] p-2 shadow bg-base-200 rounded-box w-40 sm:w-52"
    >
      <li><router-link to="/profile">Profile</router-link></li>
      <li><router-link to="/settings">Settings</router-link></li>
      <li><a @click="logout">Logout</a></li>
    </ul>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router';
import apiService from '@/services/api.js';

const router = useRouter();

const logout = async () => {
  try {
    await apiService.logout();
    // Force page reload to reset authentication state
    window.location.reload();
  } catch (error) {
    console.error('Logout failed:', error);
    // Still reload to clear local state
    window.location.reload();
  }
};
</script>

<style scoped>
/* Ensure button has touch-friendly tap area */
.btn {
  min-height: 44px;
  min-width: 44px;
}
</style>