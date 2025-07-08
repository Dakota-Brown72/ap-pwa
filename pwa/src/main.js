const savedTheme = localStorage.getItem('theme')
if (savedTheme) {
    document.documentElement.setAttribute('data-theme',savedTheme)
}
import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'

createApp(App).use(router).mount('#app')
