<!-- src/views/Home.vue -->
<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <!-- Header -->
    <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-2">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-1">AnchorPoint Dashboard</h1>
        <p class="text-base-content text-opacity-70">Your security at a glance</p>
      </div>
      <button 
        @click="refreshSnapshots" 
        class="btn btn-primary btn-sm flex items-center gap-2 self-start md:self-end"
        :disabled="loading"
      >
        <span v-if="loading" class="loading loading-spinner loading-xs"></span>
        <span v-else>↻</span>
        Refresh
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
              <img 
                :src="getSnapshotImage(camera.id)" 
                :alt="`${camera.name} snapshot`" 
                class="w-full h-56 object-cover transition-transform group-hover:scale-105 duration-200"
                @error="handleImageError"
              />
              <!-- Overlay: Camera name and time -->
              <div class="absolute bottom-0 left-0 w-full bg-gradient-to-t from-black/70 to-transparent p-3 flex flex-col gap-1">
                <span class="text-lg font-semibold text-white drop-shadow">{{ camera.name }}</span>
                <span v-if="getSnapshotInfo(camera.id)" class="text-xs text-gray-200 opacity-80">
                  Last updated: {{ formatTimestamp(getSnapshotInfo(camera.id).timestamp) }}
                </span>
                <span v-if="getSnapshotInfo(camera.id) && getSnapshotInfo(camera.id).label" class="badge badge-accent badge-sm mt-1 self-start">
                  {{ getSnapshotInfo(camera.id).label }}
                </span>
              </div>
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
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15 10l4.553-2.276A2 2 0 0021 6.382V5a2 2 0 00-2-2H5a2 2 0 00-2 2v1.382a2 2 0 001.447 1.342L9 10m6 0v10a2 2 0 01-2 2H7a2 2 0 01-2-2V10m6 0h6"/></svg>
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
      events: [
        { id: 1, type: 'Motion', description: 'Backyard motion detected', time: '10:15 AM' },
        { id: 2, type: 'Person', description: 'Front door visitor', time: '9:30 AM' },
        { id: 3, type: 'Motion', description: 'Garage activity', time: '8:45 AM' },
      ],
    };
  },
  
  async mounted() {
    await this.loadData();
  },
  
  methods: {
    async loadData(refresh = false) {
      try {
        this.loading = true;
        
        // Load cameras and snapshots in parallel
        const [camerasResponse, snapshotsResponse] = await Promise.all([
          apiService.getCameras(),
          apiService.getSnapshots(refresh)
        ]);
        
        this.cameras = camerasResponse.cameras || [];
        this.snapshots = snapshotsResponse.snapshots || {};
        
      } catch (error) {
        console.error('Failed to load data:', error);
        // For now, just log the error. In production, you'd show a user-friendly message
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
    }
  }
};
</script>