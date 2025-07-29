<!-- src/views/Home.vue -->
<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <!-- Header -->
    <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-2">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-1">AnchorPoint Dashboard</h1>
        <p class="text-base-content text-opacity-70">Your system at a glance</p>
        <!-- Removed last update and next refresh info -->
      </div>
      <button 
        @click="refreshSnapshots" 
        class="btn btn-primary btn-sm flex items-center gap-2 self-start md:self-end"
        :disabled="loading"
      >
        <span v-if="loading" class="loading loading-spinner loading-xs"></span>
        <span v-else>↻</span>
        Refresh Now
      </button>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <!-- Main: Camera Snapshots -->
      <div class="lg:col-span-2 flex flex-col gap-8">
        <div>
          <h2 class="text-xl font-semibold text-primary-content mb-4">Live Camera Snapshots</h2>
          <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div v-for="i in 4" :key="i" class="h-56 bg-base-300 rounded-xl animate-pulse"></div>
          </div>
          <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div 
              v-for="camera in cameras" 
              :key="camera.id" 
              class="relative group rounded-xl overflow-hidden shadow-lg bg-base-100 hover:shadow-2xl transition-shadow cursor-pointer"
              @click="viewMultiview"
            >
              <div class="aspect-video bg-base-300">
                <img 
                  :src="getSnapshotImage(camera.id)" 
                  :alt="`${camera.name} snapshot`" 
                  class="w-full h-full object-contain transition-transform group-hover:scale-105 duration-200"
                  @error="handleImageError"
                />
              </div>
              <!-- Removed all overlays: camera name, last updated, and offline badge -->
            </div>
          </div>
        </div>
      </div>

      <!-- Sidebar: Events, Notifications, Metrics, Actions -->
      <div class="flex flex-col gap-8">
        <!-- Recent Events -->
        <div class="card bg-base-100 shadow-md rounded-xl">
          <div class="card-body p-4">
            <h2 class="card-title text-base-content mb-2">Recent Camera Events</h2>
            <ul class="divide-y divide-base-200 max-h-56 overflow-y-auto">
              <li v-for="event in events" :key="event.id" class="py-2 flex items-center gap-2">
                <span class="badge badge-accent badge-sm">{{ event.type }}</span>
                <span class="text-sm text-base-content">{{ event.description }}</span>
                <span class="ml-auto text-xs text-base-content text-opacity-60">{{ event.time }}</span>
              </li>
            </ul>
          </div>
        </div>
        <!-- System Notifications -->
        <div class="card bg-base-100 shadow-md rounded-xl">
          <div class="card-body p-4">
            <h2 class="card-title text-base-content mb-2">System Notifications</h2>
            <div class="flex flex-col gap-2">
              <div class="alert alert-error flex items-center gap-2 py-2 px-3">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z"/></svg>
                <span>Camera 1 offline</span>
              </div>
              <div class="alert alert-warning flex items-center gap-2 py-2 px-3">
                <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z"/></svg>
                <span>Storage 75% full</span>
              </div>
            </div>
          </div>
        </div>
        <!-- System Metrics -->
        <div class="card bg-base-100 shadow-md rounded-xl">
          <div class="card-body p-4">
            <h2 class="card-title text-base-content mb-2">System Metrics</h2>
            <div class="flex flex-col gap-2">
              <div class="flex items-center gap-2">
                <span class="badge badge-success badge-sm">●</span>
                <span class="text-sm">Cameras Online</span>
                <span class="ml-auto font-semibold">4/4</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="badge badge-info badge-sm">●</span>
                <span class="text-sm">Events Today</span>
                <span class="ml-auto font-semibold">12</span>
              </div>
              <div class="flex items-center gap-2">
                <span class="badge badge-neutral badge-sm">●</span>
                <span class="text-sm">Storage Free</span>
                <span class="ml-auto font-semibold">380GB</span>
              </div>
            </div>
          </div>
        </div>
        <!-- Quick Actions -->
        <div class="card bg-base-100 shadow-md rounded-xl">
          <div class="card-body p-4">
            <h2 class="card-title text-base-content mb-2">Quick Actions</h2>
            <div class="flex flex-wrap gap-2">
              <router-link to="/multiview" class="btn btn-primary btn-sm flex items-center gap-1">
                <!-- Replaced with a simple camera icon -->
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <rect x="3" y="7" width="18" height="13" rx="2" ry="2"/>
                  <circle cx="12" cy="13.5" r="3.5"/>
                  <path d="M8 7V5a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
                Live View
              </router-link>
              <router-link to="/review" class="btn btn-accent btn-sm flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6 1a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                Review
              </router-link>
              <router-link to="/settings" class="btn btn-outline btn-sm flex items-center gap-1">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                Settings
              </router-link>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import apiService from '@/services/api.js';

export default {
  name: 'Home',
  data() {
    return {
      loading: false,
      cameras: [],
      snapshots: {},
      autoRefreshInterval: null,
      lastRefreshTime: null,
      events: [
        { id: 1, type: 'Motion', description: 'Backyard motion detected', time: '10:15 AM' },
        { id: 2, type: 'Person', description: 'Front door visitor', time: '9:30 AM' },
        { id: 3, type: 'Motion', description: 'Garage activity', time: '8:45 AM' },
      ],
    };
  },
  
  async mounted() {
    await this.loadData();
    this.startAutoRefresh();
  },
  
  beforeUnmount() {
    this.stopAutoRefresh();
    this.cleanupBlobUrls();
  },
  
  methods: {
    cleanupBlobUrls() {
      // Clean up blob URLs to prevent memory leaks
      Object.values(this.snapshots).forEach(snapshot => {
        if (snapshot.image && snapshot.image.startsWith('blob:')) {
          URL.revokeObjectURL(snapshot.image);
        }
      });
    },
    
    async loadData(refresh = false) {
      try {
        this.loading = true;
        
        // Clean up old blob URLs
        this.cleanupBlobUrls();
        
        // Load cameras using authenticated endpoint
        const camerasResponse = await apiService.getCameras();
        this.cameras = camerasResponse.cameras || [];
        
        // Fetch authenticated snapshots and convert to blob URLs
        this.snapshots = {};
        const snapshotPromises = this.cameras.map(async (camera) => {
          if (camera.snapshot_url) {
            try {
              // Fetch snapshot with authentication
              const response = await apiService.request(`${camera.snapshot_url}${refresh ? `?t=${Date.now()}` : ''}`, {
                headers: {
                  'Accept': 'image/jpeg,image/png,image/*'
                }
              });
              
              // Convert response to blob URL
              const blob = await response.blob();
              const blobUrl = URL.createObjectURL(blob);
              
              this.snapshots[camera.id] = {
                image: blobUrl,
                timestamp: Date.now(),
                label: camera.enabled ? 'Online' : 'Offline'
              };
            } catch (error) {
              console.error(`Failed to load snapshot for ${camera.id}:`, error);
              this.snapshots[camera.id] = {
                image: `https://picsum.photos/200/150?random=${camera.id}`,
                timestamp: Date.now(),
                label: 'Error',
                error: true
              };
            }
          }
        });
        
        // Wait for all snapshots to load
        await Promise.all(snapshotPromises);
        
        // Track when snapshots were last refreshed
        this.lastRefreshTime = Date.now();
        
      } catch (error) {
        console.error('Failed to load data:', error);
        // Check if it's an authentication error
        if (error.message.includes('Authentication required')) {
          // Force re-authentication
          localStorage.removeItem('auth_token');
          this.$router.push('/login');
          return;
        }
        // For other errors, show user-friendly message
        this.loginError = 'Failed to load camera data. Please refresh the page.';
      } finally {
        this.loading = false;
      }
    },
    
    async refreshSnapshots() {
      await this.loadData(true);
    },
    
    getSnapshotImage(cameraId) {
      const snapshot = this.snapshots[cameraId];
      if (snapshot && snapshot.image) {
        return snapshot.image;
      }
      // Fallback to placeholder
      return `https://picsum.photos/200/150?random=${cameraId}`;
    },
    
    getSnapshotInfo(cameraId) {
      const snapshot = this.snapshots[cameraId];
      if (snapshot && !snapshot.error) {
        return {
          label: snapshot.label,
          score: snapshot.score,
          timestamp: snapshot.timestamp
        };
      }
      return null;
    },
    
    formatTimestamp(ts) {
      if (!ts) return '';
      const d = new Date(ts);
      return d.toLocaleString('en-US', {
        dateStyle: 'short',
        timeStyle: 'short',
        timeZone: 'America/Chicago'
      });
    },
    
    handleImageError(event) {
      // Replace broken image with placeholder
      event.target.src = `https://picsum.photos/200/150?random=${Math.random()}`;
    },
    
    viewMultiview() {
      this.$router.push('/multiview');
    },
    
    startAutoRefresh() {
      // Stop any existing interval
      this.stopAutoRefresh();
      
      // Auto-refresh snapshots every hour (3600000 ms)
      this.autoRefreshInterval = setInterval(async () => {
        console.log('🔄 Auto-refreshing camera snapshots...');
        try {
          await this.loadData(true); // Force refresh with timestamp
        } catch (error) {
          console.error('Auto-refresh failed:', error);
        }
      }, 3600000); // 1 hour = 60 * 60 * 1000 ms
      
      console.log('✅ Auto-refresh started: snapshots will update every hour');
    },
    
    stopAutoRefresh() {
      if (this.autoRefreshInterval) {
        clearInterval(this.autoRefreshInterval);
        this.autoRefreshInterval = null;
        console.log('🛑 Auto-refresh stopped');
      }
    },
    
    getNextRefreshTime() {
      if (!this.lastRefreshTime) return '';
      const nextRefresh = new Date(this.lastRefreshTime + 3600000); // +1 hour
      return nextRefresh.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Chicago'
      });
    }
  }
};
</script>