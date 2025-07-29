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
  // Login route outside of layout (no navigation)
  {
    path: '/login',
    name: 'Login',
    component: Login,
    meta: { requiresAuth: false }
  },
  // Protected routes with layout
  {
    path: '/',
    component: Layout,
    meta: { requiresAuth: true },
    children: [
      { 
        path: '', 
        redirect: '/dashboard' 
      },
      { 
        path: '/dashboard', 
        name: 'Dashboard',
        component: Home,
        meta: { requiresAuth: true }
      },
      { 
        path: '/multiview', 
        name: 'Multiview',
        component: CameraMultiview,
        meta: { requiresAuth: true }
      },
      { 
        path: '/camera/:id', 
        name: 'Camera',
        component: CameraView,
        meta: { requiresAuth: true }
      },
      { 
        path: '/review', 
        name: 'Review',
        component: CameraReview,
        meta: { requiresAuth: true }
      },
      { 
        path: '/settings', 
        name: 'Settings',
        component: Settings,
        meta: { requiresAuth: true }
      },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Authentication guard
router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('auth_token')
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth !== false)
  
  if (requiresAuth && !token) {
    // Redirect to login if authentication is required but no token exists
    next('/login')
  } else if (to.path === '/login' && token) {
    // Redirect to dashboard if already authenticated and trying to access login
    next('/dashboard')
  } else {
    // Proceed normally
    next()
  }
})

export default router
