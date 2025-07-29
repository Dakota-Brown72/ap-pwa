<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <!-- Header -->
    <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-2">Live Feeds</h1>
        <!-- Removed subtitle and autoplay info -->
      </div>
      <div class="flex items-center gap-3">
        <button 
          @click="refreshCameras" 
          class="btn btn-primary btn-sm"
          :disabled="loading"
        >
          <span v-if="loading" class="loading loading-spinner loading-xs"></span>
          <span v-else>↻</span>
          Refresh
        </button>
        <button 
          @click="playAllVideos" 
          class="btn btn-success btn-sm"
          :disabled="loading"
        >
          <span>▶</span>
          Play All
        </button>
        <!-- Removed Fullscreen button -->
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div v-for="i in 4" :key="i" class="aspect-video bg-base-300 rounded-xl animate-pulse"></div>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="alert alert-error mb-6">
      <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z"/>
      </svg>
      <span>{{ error }}</span>
      <button @click="loadCameras" class="btn btn-sm">Retry</button>
    </div>

    <!-- Camera Grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div 
        v-for="camera in cameras" 
        :key="camera.id" 
        class="relative group bg-base-100 rounded-xl overflow-hidden shadow-lg hover:shadow-2xl transition-all duration-300"
      >
        <div class="aspect-video relative">
          <!-- Adaptive Player (HLS for iOS, MP4 for Desktop) -->
          <AdaptivePlayer
            ref="adaptivePlayers"
            :camera="camera"
            @click="handleCameraClick(camera)"
            @stream-error="handleAdaptiveError(camera, $event)"
            @stream-ready="handleAdaptiveReady(camera)"
            @stream-playing="handleAdaptivePlaying(camera)"
          />
          
          <!-- Fallback to Snapshot -->
          <img
            v-if="camera.showSnapshot && camera.snapshotBlobUrl"
            :src="camera.snapshotBlobUrl"
            class="w-full h-full object-cover absolute inset-0 cursor-pointer"
            @error="handleImageError(camera)"
            @load="handleImageLoad(camera)"
            @click="handleCameraClick(camera)"
            alt="Camera feed"
          />
          
          <!-- Loading Overlay -->
          <div 
            v-if="camera.loading" 
            class="absolute inset-0 bg-base-300 bg-opacity-75 flex items-center justify-center"
          >
            <span class="loading loading-spinner loading-lg text-primary"></span>
            <div class="ml-2 text-sm">
              <div>Starting adaptive stream...</div>
              <div class="text-xs opacity-70">Optimized for your device</div>
            </div>
          </div>
          
          <!-- Error Overlay -->
          <div 
            v-if="camera.error" 
            class="absolute inset-0 bg-base-300 bg-opacity-75 flex flex-col items-center justify-center p-4"
          >
            <svg class="w-12 h-12 text-error mb-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z"/>
            </svg>
            <p class="text-error text-sm text-center">{{ camera.error }}</p>
            <button 
              @click="retryCamera(camera)" 
              class="btn btn-sm btn-outline mt-2"
            >
              Retry
            </button>
          </div>
          
          <!-- Stream Status Badge -->
          <!-- Removed all badges and overlays for a cleaner look -->

          <!-- Camera Name -->
          <!-- Removed camera name overlay for a cleaner look -->

          <!-- Fullscreen Button -->
          <!-- Removed overlay fullscreen button for a cleaner look -->
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="!loading && !error && cameras.length === 0" class="text-center py-12">
      <svg class="w-16 h-16 text-base-content text-opacity-30 mx-auto mb-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 10l4.553-2.276A2 2 0 0021 6.382V5a2 2 0 00-2-2H5a2 2 0 00-2 2v1.382a2 2 0 001.447 1.342L9 10m6 0v10a2 2 0 01-2 2H7a2 2 0 01-2-2V10m6 0h6"/>
      </svg>
      <h3 class="text-lg font-semibold text-base-content mb-2">No Cameras Found</h3>
      <p class="text-base-content text-opacity-70 mb-4">No cameras are currently available or configured.</p>
      <button @click="loadCameras" class="btn btn-primary">Refresh Cameras</button>
    </div>
    
    <!-- Fullscreen Camera Overlay -->
    <div 
      v-if="fullscreenCamera" 
      class="fixed inset-0 z-50 bg-black flex flex-col"
      @keydown.esc="exitFullscreen"
    >
      <!-- Fullscreen Header -->
      <div class="flex items-center justify-between p-4 bg-base-300 bg-opacity-90">
        <div class="flex items-center gap-4">
          <h2 class="text-xl font-bold text-primary-content">{{ fullscreenCamera.name || fullscreenCamera.id }}</h2>
          <div class="flex gap-2">
            <div v-if="fullscreenCamera.streaming" class="badge badge-success">LIVE</div>
            <div class="badge badge-info">ADAPTIVE</div>
          </div>
        </div>
        <button 
          @click="exitFullscreen"
          class="btn btn-circle btn-primary"
        >
          <span>✕</span>
        </button>
      </div>
      
      <!-- Fullscreen Video -->
      <div class="flex-1 relative bg-black">
        <AdaptivePlayer
          v-if="fullscreenCamera"
          :camera="fullscreenCamera"
          @stream-error="handleFullscreenAdaptiveError"
        />
        
        <!-- Loading Overlay -->
        <div 
          v-if="fullscreenCamera.loading" 
          class="absolute inset-0 bg-base-300 bg-opacity-75 flex items-center justify-center"
        >
          <span class="loading loading-spinner loading-lg text-primary"></span>
          <div class="ml-4 text-lg">
            <div>Initializing adaptive stream...</div>
            <div class="text-sm opacity-70">Optimized for your device</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import apiService from '@/services/api.js';
import AdaptivePlayer from '@/components/AdaptivePlayer.vue';

export default {
  name: 'CameraMultiview',
  components: {
    AdaptivePlayer
  },
  data() {
    return {
      loading: false,
      error: null,
      cameras: [],
      fullscreenCamera: null,
      // Removed isFullscreen state
      userInteracted: false,
      keepAliveInterval: null // New property for keep-alive interval
    };
  },
  
  async mounted() {
    await this.loadCameras();
    document.addEventListener('keydown', this.handleKeydown);
    
    // Start on-demand streaming when multiview loads
    await this.startStreaming();
    
    // Set up keep-alive interval to maintain streams
    this.keepAliveInterval = setInterval(() => {
      this.keepStreamsAlive();
    }, 30000); // Every 30 seconds
  },
  
  beforeUnmount() {
    document.removeEventListener('keydown', this.handleKeydown);
    
    // Stop streaming when leaving multiview
    this.stopStreaming();
    
    // Clear keep-alive interval
    if (this.keepAliveInterval) {
      clearInterval(this.keepAliveInterval);
    }
    
    // Clean up blob URLs
    this.cleanupBlobUrls();
  },
  
  methods: {
    async loadCameras() {
      try {
        this.loading = true;
        this.error = null;
        
        // Get camera list from authenticated endpoint
        const camerasResponse = await apiService.getCameras();
        const newCameras = camerasResponse.cameras || [];
        
        // Initialize camera objects for adaptive streaming
        this.cameras = newCameras.map(cam => {
          return {
            ...cam,
            loading: false,
            error: null,
            streaming: false,
            showSnapshot: true, // Show snapshot until stream loads
            snapshotUrl: cam.snapshot_url || null,
            snapshotBlobUrl: null, // Will be set after fetching
          };
        });
        
        // Fetch snapshots for all cameras
        await this.loadSnapshots();
        
        console.log(`Loaded ${this.cameras.length} cameras for adaptive streaming`);
        
      } catch (error) {
        console.error('Failed to load cameras:', error);
        // Check if it's an authentication error
        if (error.message.includes('Authentication required')) {
          // Force re-authentication
          localStorage.removeItem('auth_token');
          this.$router.push('/login');
          return;
        }
        this.error = 'Failed to load cameras. Please check your connection and try again.';
      } finally {
        this.loading = false;
      }
    },
    
    async refreshCameras() {
      await this.loadCameras();
    },
    
    async startStreaming() {
      try {
        console.log('Starting on-demand streaming for all cameras...');
        const response = await apiService.request('/cameras/start-streaming', {
          method: 'POST'
        });
        
        if (response.ok) {
          const result = await response.json();
          console.log(`Started streaming for ${result.started_streams?.length || 0} cameras:`, result.started_streams);
          if (result.failed_streams?.length > 0) {
            console.warn('Failed to start streaming for cameras:', result.failed_streams);
          }
        } else {
          console.error('Failed to start streaming:', response.status);
        }
      } catch (error) {
        console.error('Error starting streaming:', error);
      }
    },
    
    async stopStreaming() {
      try {
        console.log('Stopping on-demand streaming for all cameras...');
        const response = await apiService.request('/cameras/stop-streaming', {
          method: 'POST'
        });
        
        if (response.ok) {
          const result = await response.json();
          console.log(`Stopped streaming for ${result.stopped_streams?.length || 0} cameras:`, result.stopped_streams);
        } else {
          console.error('Failed to stop streaming:', response.status);
        }
      } catch (error) {
        console.error('Error stopping streaming:', error);
      }
    },
    
    async keepStreamsAlive() {
      // Keep streams alive for cameras that are currently being viewed
      const keepAlivePromises = this.cameras.map(async (camera) => {
        try {
          const response = await apiService.request(`/cameras/${camera.id}/keep-alive`, {
            method: 'POST'
          });
          
          if (response.ok) {
            console.debug(`Kept stream alive for ${camera.id}`);
          } else {
            console.warn(`Failed to keep stream alive for ${camera.id}:`, response.status);
          }
        } catch (error) {
          console.warn(`Error keeping stream alive for ${camera.id}:`, error);
        }
      });
      
      await Promise.allSettled(keepAlivePromises);
    },
    
    async playAllVideos() {
      console.log('Attempting to play all videos');
      // Trigger play on all AdaptivePlayer components
      this.$refs.adaptivePlayers?.forEach(async (player) => {
        if (player && player.playVideo) {
          try {
            await player.playVideo();
          } catch (error) {
            console.log('Failed to play video:', error);
          }
        }
      });
    },
    
    retryCamera(camera) {
      camera.error = null;
      camera.loading = true;
      
      // Retry adaptive streaming after a short delay
      setTimeout(async () => {
        console.log(`Retrying adaptive stream for camera: ${camera.id}`);
        camera.loading = false;
      }, 1000);
    },
    
    handleVideoLoadStart(camera) {
      camera.loading = true;
      camera.error = null;
    },
    
    handleVideoCanPlay(camera) {
      camera.loading = false;
      camera.streaming = true;
      camera.showSnapshot = false;
    },
    
    handleVideoError(camera) {
      console.error(`Video error for ${camera.id}:`, camera.error);
      camera.loading = false;
      camera.streaming = false;
      camera.showSnapshot = true;
      camera.error = 'Stream failed to load. Please try again.';
    },
    
    toggleCameraFullscreen(camera) {
      if (this.fullscreenCamera?.id === camera.id) {
        this.exitFullscreen();
      } else {
        this.fullscreenCamera = { ...camera };
        this.isFullscreen = true;
      }
    },
    
    exitFullscreen() {
      this.fullscreenCamera = null;
      this.isFullscreen = false;
    },
    
    // Handle camera tile clicks
    async handleCameraClick(camera) {
      console.log(`Camera ${camera.id} clicked`);
    },
    
    toggleFullscreen() {
      // Removed fullscreen toggle functionality
    },
    
    handleKeydown(event) {
      if (event.key === 'Escape') {
        this.exitFullscreen();
      }
    },
    
    handleFullscreenAdaptiveError(errorData) {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.error = `Fullscreen ${errorData.format.toUpperCase()} stream failed: ${errorData.error}`;
        this.fullscreenCamera.loading = false;
      }
    },
    
    async loadSnapshots() {
      // Fetch snapshots for all cameras and convert to blob URLs
      const snapshotPromises = this.cameras.map(async (camera) => {
        if (camera.snapshotUrl) {
          try {
            // Fetch snapshot with authentication using apiService
            const response = await apiService.request(`${camera.snapshotUrl}?t=${Date.now()}`, {
              headers: {
                'Accept': 'image/jpeg,image/png,image/*'
              }
            });
            
            // Convert response to blob URL
            const blob = await response.blob();
            const blobUrl = URL.createObjectURL(blob);
            
            camera.snapshotBlobUrl = blobUrl;
            camera.showSnapshot = true;
            camera.error = null;
            
            console.log(`Snapshot loaded for ${camera.id}`);
          } catch (error) {
            console.error(`Failed to load snapshot for ${camera.id}:`, error);
            camera.showSnapshot = false;
            camera.error = 'Snapshot unavailable';
          }
        }
      });
      
      await Promise.allSettled(snapshotPromises);
    },
    
    handleImageError(camera) {
      console.warn(`Snapshot failed for ${camera.id}`);
      // Clean up blob URL if it exists
      if (camera.snapshotBlobUrl) {
        URL.revokeObjectURL(camera.snapshotBlobUrl);
        camera.snapshotBlobUrl = null;
      }
      camera.showSnapshot = false;
      camera.error = 'Snapshot unavailable';
    },
    
    handleImageLoad(camera) {
      // Snapshot loaded successfully
    },
    
    handleAdaptiveError(camera, errorData) {
      console.log(`${errorData.format.toUpperCase()} failed for ${camera.id}: ${errorData.error}`);
      camera.error = null; // Clear error to show snapshot instead
      camera.loading = false;
      camera.streaming = false;
      camera.showSnapshot = true; // Force snapshot to show
      
      // Ensure snapshot is visible and video is hidden
      setTimeout(() => {
        camera.error = null; // Make sure no error overlay
      }, 100);
    },

    handleAdaptiveReady(camera) {
      console.log(`Adaptive stream ready for ${camera.id}`);
      camera.loading = false;
      camera.streaming = true;
      camera.showSnapshot = false;
      camera.error = null;
    },

    handleAdaptivePlaying(camera) {
      console.log(`Adaptive stream playing for ${camera.id}`);
      camera.loading = false;
      camera.streaming = true;
      camera.showSnapshot = false;
    },

    // Clean up blob URLs to prevent memory leaks
    cleanupBlobUrls() {
      this.cameras.forEach(camera => {
        if (camera.snapshotBlobUrl) {
          URL.revokeObjectURL(camera.snapshotBlobUrl);
          camera.snapshotBlobUrl = null;
        }
      });
    },
  },
};
</script>

<style scoped>
/* Custom video player styles */
video {
  background-color: #1a1a1a;
}

/* Fullscreen styles */
:fullscreen {
  background-color: #000;
}

:-webkit-full-screen {
  background-color: #000;
}

:-moz-full-screen {
  background-color: #000;
}

/* Responsive grid adjustments for 2 cameras */
@media (max-width: 640px) {
  .grid {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 641px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>