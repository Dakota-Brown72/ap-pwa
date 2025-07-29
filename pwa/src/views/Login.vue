<!-- src/views/Login.vue -->
<template>
  <div class="min-h-screen bg-base-200 flex items-center justify-center p-4">
    <div class="card w-full max-w-md bg-base-100 shadow-xl">
      <div class="card-body">
        <div class="flex flex-col items-center mb-6">
          <h1 class="text-3xl font-bold text-primary mb-2">AnchorPoint</h1>
          <p class="text-base-content/70">Security Camera System</p>
        </div>
        
        <div v-if="error" class="alert alert-error mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{{ error }}</span>
        </div>
        
        <div v-if="success" class="alert alert-success mb-4">
          <svg xmlns="http://www.w3.org/2000/svg" class="stroke-current shrink-0 h-6 w-6" fill="none" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{{ success }}</span>
        </div>
        
        <form @submit.prevent="handleLogin" class="space-y-4">
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium">Username</span>
            </label>
            <input 
              v-model="form.username" 
              type="text" 
              class="input input-bordered w-full" 
              placeholder="Enter your username"
              required
              :disabled="loading"
              autocomplete="username"
            />
          </div>
          
          <div class="form-control">
            <label class="label">
              <span class="label-text font-medium">Password</span>
            </label>
            <input 
              v-model="form.password" 
              type="password" 
              class="input input-bordered w-full" 
              placeholder="Enter your password"
              required
              :disabled="loading"
              autocomplete="current-password"
            />
          </div>
          
          <button 
            type="submit" 
            class="btn btn-primary w-full"
            :disabled="loading"
          >
            <span v-if="loading" class="loading loading-spinner loading-sm"></span>
            {{ loading ? 'Signing in...' : 'Sign In' }}
          </button>
        </form>
        
        <div class="divider text-xs">Secure Access</div>
        
        <div class="text-center text-sm text-base-content/70">
          <p>Access to live camera feeds and recordings</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import apiService from '@/services/api.js'

export default {
  name: 'Login',
  setup() {
    const router = useRouter()
    
    const form = ref({
      username: '',
      password: ''
    })
    
    const loading = ref(false)
    const error = ref('')
    const success = ref('')
    
    const handleLogin = async () => {
      if (!form.value.username || !form.value.password) {
        error.value = 'Please enter both username and password'
        return
      }
      
      try {
        loading.value = true
        error.value = ''
        success.value = ''
        
        const response = await apiService.login(form.value.username, form.value.password)
        
        if (response.token) {
          success.value = 'Login successful! Redirecting...'
          
          // Store user info if available
          if (response.user) {
            localStorage.setItem('user_info', JSON.stringify(response.user))
          }
          
          // Clear form
          form.value.username = ''
          form.value.password = ''
          
          // Redirect to dashboard after a brief delay
          setTimeout(() => {
            router.push('/dashboard')
          }, 1000)
        } else {
          error.value = 'Login failed. No token received.'
        }
        
      } catch (err) {
        console.error('Login error:', err)
        
        // Handle enhanced error responses from API service
        if (err.status === 429) {
          // Rate limited or IP blocked
          error.value = err.message || 'Too many failed attempts. Please try again later.'
        } else if (err.status === 401) {
          // Invalid credentials
          if (err.data?.attempts_remaining !== undefined) {
            const remaining = err.data.attempts_remaining
            if (remaining > 0) {
              error.value = `Invalid credentials. ${remaining} attempt${remaining === 1 ? '' : 's'} remaining.`
            } else {
              error.value = 'Account temporarily locked due to too many failed attempts.'
            }
          } else {
            error.value = 'Invalid username or password'
          }
        } else if (err.message.includes('Authentication required')) {
          error.value = 'Authentication failed. Please try again.'
        } else if (err.message.includes('fetch') || err.message.includes('network')) {
          error.value = 'Unable to connect to server. Please try again.'
        } else {
          error.value = err.message || 'Login failed. Please try again.'
        }
      } finally {
        loading.value = false
      }
    }
    
    // Check if already authenticated
    onMounted(() => {
      const token = localStorage.getItem('auth_token')
      if (token) {
        // User is already logged in, redirect to dashboard
        router.push('/dashboard')
      }
    })
    
    return {
      form,
      loading,
      error,
      success,
      handleLogin
    }
  }
}
</script>

<style scoped>
/* Custom styles for the login page */
.card {
  backdrop-filter: blur(10px);
}

.alert {
  border-radius: 0.5rem;
}

.form-control {
  position: relative;
}

.input:focus {
  border-color: hsl(var(--p));
  box-shadow: 0 0 0 2px hsl(var(--p) / 0.2);
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading-spinner {
  margin-right: 0.5rem;
}
</style>
