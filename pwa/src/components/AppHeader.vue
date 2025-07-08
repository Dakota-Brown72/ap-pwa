<template>
  <header class="navbar bg-primary text-primary-content shadow-md px-4 py-2 sm:px-6 sm:py-3">
    <!-- Left: Logo + Title -->
    <div class="flex items-center gap-2 sm:gap-3">
      <router-link to="/" class="flex items-center gap-2 cursor-pointer">
        <img src="/icons/icon-192x192.png" alt="Logo" class="h-14 w-14 sm:h-12" />
        <span class="text-xl font-bold sm:text-l">AnchorPoint</span>
      </router-link>
    </div>

    <!-- Right: Controls -->
    <div class="ml-auto flex items-center gap-3 sm:gap-4">
      <ThemeToggle />
      <DropdownMenu />
      <UserIcon />
    </div>
  </header>
</template>

<script setup>
import ThemeToggle from './ThemeToggle.vue';
import DropdownMenu from './DropdownMenu.vue';
import UserIcon from './UserIcon.vue';
</script>