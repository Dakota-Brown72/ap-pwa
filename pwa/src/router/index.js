// src/router/index.js
import { createRouter, createWebHistory } from 'vue-router'
import Layout from '@/layouts/Layout.vue'
import Home from '@/views/Home.vue'
import CameraMultiview from '@/views/CameraMultiview.vue'
import CameraView from '@/views/CameraView.vue'
import CameraReview from '@/views/CameraReview.vue'
import Events from '@/views/Events.vue'
import Settings from '@/views/Settings.vue'
import Login from '@/views/Login.vue'
import Profile from '@/views/Profile.vue'
import AdminLoginAttempts from '@/views/AdminLoginAttempts.vue'
import AdminUsers from '@/views/AdminUsers.vue'
import Quarantine from '@/views/Quarantine.vue'

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
        path: '/events', 
        name: 'Events',
        component: Events,
        meta: { requiresAuth: true }
      },
      { 
        path: '/settings', 
        name: 'Settings',
        component: Settings,
        meta: { requiresAuth: true }
      },
      { 
        path: '/profile', 
        name: 'Profile',
        component: Profile,
        meta: { requiresAuth: true }
      },
      {
        path: '/admin/logins',
        name: 'AdminLoginAttempts',
        component: AdminLoginAttempts,
        meta: { requiresAuth: true }
      },
      {
        path: '/admin/users',
        name: 'AdminUsers',
        component: AdminUsers,
        meta: { requiresAuth: true }
      },
      {
        path: '/quarantine',
        name: 'Quarantine',
        component: Quarantine,
        meta: { requiresAuth: false }
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
  let user
  try { user = JSON.parse(localStorage.getItem('user_info') || '{}') } catch {}
  const requiresAuth = to.matched.some(record => record.meta.requiresAuth !== false)
  
  if (requiresAuth && !token) {
    // Redirect to login if authentication is required but no token exists
    next('/login')
  } else if (to.path === '/login' && token) {
    // Redirect to dashboard if already authenticated and trying to access login
    // If disabled, send to quarantine
    if (user && user.is_active === false) next('/quarantine')
    else next('/dashboard')
  } else if (token && user && user.is_active === false) {
    // Disabled users: restrict to quarantine and login only
    if (to.path !== '/quarantine' && to.path !== '/login') {
      next('/quarantine')
    } else {
      next()
    }
  } else {
    // Proceed normally
    next()
  }
})

export default router
