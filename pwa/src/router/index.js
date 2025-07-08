// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/layouts/Layout.vue'
import Home from '@/views/Home.vue'
import CameraMultiview from '@/views/CameraMultiview.vue'
import CameraView from '@/views/CameraView.vue'
import CameraReview from '@/views/CameraReview.vue'
import Settings from '@/views/Settings.vue'
import Login from '@/views/Login.vue'

const routes = [
  {
    path: '/',
    component: Layout,
    children: [
      { path: '/', redirect: '/dashboard' },
      { path: '/login', component: Login },
      { path: '/dashboard', component: Home },
      { path: '/multiview', component: CameraMultiview },
      { path: '/camera/:id', component: CameraView },
      { path: '/review', component: CameraReview },
      { path: '/settings', component: Settings },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
