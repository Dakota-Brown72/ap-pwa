<script setup>
import { ref, computed, onMounted } from 'vue';

const currentTheme = ref('anchorpoint');

const isDark = computed(() => currentTheme.value === 'anchorpointdark');

const toggleTheme = () => {
  const html = document.documentElement;
  currentTheme.value = isDark.value ? 'anchorpoint' : 'anchorpointdark';
  html.setAttribute('data-theme', currentTheme.value);
  localStorage.setItem('theme', currentTheme.value);
};

onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'anchorpoint';
  currentTheme.value = savedTheme;
  document.documentElement.setAttribute('data-theme', savedTheme);
});
</script>

<template>
  <button
    @click="toggleTheme"
    class="btn btn-outline btn-sm sm:btn-md text-primary-content"
    :aria-label="isDark ? 'Switch to light theme' : 'Switch to dark theme'"
  >
    <span>{{ isDark ? '🌞' : '🌙' }}</span>
  </button>
</template>

<style scoped>
.btn {
  min-height: 40px;
  min-width: 40px;
  padding: 0.5rem;
}
</style>