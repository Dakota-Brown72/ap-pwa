<template>
  <div v-if="!isAuthenticated" class="min-h-screen bg-base-200 flex items-center justify-center">
    <div class="card w-96 bg-base-100 shadow-xl">
      <div class="card-body">
        <h2 class="card-title justify-center mb-4">AnchorPoint Login</h2>
        
        <div v-if="loginError" class="alert alert-error mb-4">
          <span>{{ loginError }}</span>
        </div>
        
        <form @submit.prevent="handleLogin" class="space-y-4">
          <div class="form-control">
            <label class="label">
              <span class="label-text">Username</span>
            </label>
            <input 
              v-model="loginForm.username" 
              type="text" 
              class="input input-bordered" 
              required
            />
          </div>
          
          <div class="form-control">
            <label class="label">
              <span class="label-text">Password</span>
            </label>
            <input 
              v-model="loginForm.password" 
              type="password" 
              class="input input-bordered" 
              required
            />
          </div>
          
          <button 
            type="submit" 
            class="btn btn-primary w-full"
            :disabled="loggingIn"
          >
            {{ loggingIn ? 'Logging in...' : 'Login' }}
          </button>
        </form>
      </div>
    </div>
  </div>
  
  <div v-else>
    <router-view />
  </div>
</template>

<script>
import apiService from './services/api.js';

export default {
  name: 'App',
  data() {
    return {
      isAuthenticated: false,
      loggingIn: false,
      loginError: '',
      loginForm: {
        username: '',
        password: ''
      }
    };
  },
  
  mounted() {
    // Check if we have a stored token
    const token = localStorage.getItem('auth_token');
    if (token) {
      this.isAuthenticated = true;
    }
  },
  
  methods: {
    async handleLogin() {
      try {
        this.loggingIn = true;
        this.loginError = '';
        
        const response = await apiService.login(
          this.loginForm.username, 
          this.loginForm.password
        );
        
        this.isAuthenticated = true;
        
        // Clear form
        this.loginForm.username = '';
        this.loginForm.password = '';
        
      } catch (error) {
        console.error('Login failed:', error);
        this.loginError = 'Login failed. Please check your credentials.';
      } finally {
        this.loggingIn = false;
      }
    }
  }
};
</script>

<style scoped>

</style>
