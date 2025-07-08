<template>
  <div class="min-h-screen bg-secondary text-secondary-content">
    <AppHeader />
    <main class="p-4">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import AppHeader from '@/components/AppHeader.vue'
</script>
