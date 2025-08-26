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
        class="relative group bg-base-100 rounded-xl overflow-hidden shadow-lg hover:shadow-2xl transition-all duration-300 camera-container"
      >
        <div class="aspect-video relative video-wrapper">
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
              <div v-if="!autoPlaybackAttempted">Initializing camera stream...</div>
              <div v-else>Starting adaptive stream...</div>
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
      keepAliveInterval: null, // New property for keep-alive interval
      touchStartY: 0, // Track touch position for mobile handling
      autoPlaybackAttempted: false // Track if we've tried auto-playback
    };
  },
  
  async mounted() {
    await this.loadCameras();
    document.addEventListener('keydown', this.handleKeydown);
    
    // Add mobile-specific touch event handling
    this.setupMobileTouchHandling();
    
    // Start on-demand streaming when multiview loads
    await this.startStreaming();
    
    // Auto-start video playback after everything is loaded
    await this.initializeVideoPlayback();
    
    // Set up keep-alive interval to maintain streams
    this.keepAliveInterval = setInterval(() => {
      this.keepStreamsAlive();
    }, 30000); // Every 30 seconds
  },
  
  beforeUnmount() {
    document.removeEventListener('keydown', this.handleKeydown);
    
    // Clean up mobile touch handlers
    document.removeEventListener('touchstart', this.handleTouchStart);
    document.removeEventListener('touchmove', this.handleTouchMove);
    
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
      
      // Also restart streaming and auto-playback after refresh
      await this.startStreaming();
      await this.initializeVideoPlayback();
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

    async initializeVideoPlayback() {
      try {
        // Set all cameras to loading state during initialization
        this.cameras.forEach(camera => {
          camera.loading = true;
          camera.error = null;
        });
        
        // Wait for DOM to be fully updated with camera components
        await this.$nextTick();
        
        // Give a small delay to ensure AdaptivePlayer components are fully mounted
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        // Check if we have cameras and AdaptivePlayer components
        if (this.cameras.length > 0 && this.$refs.adaptivePlayers) {
          console.log('Auto-starting video playback for all cameras...');
          
          // Trigger playback on all cameras
          await this.playAllVideos();
          
          // Mark that we've attempted auto-playback
          this.autoPlaybackAttempted = true;
          
          console.log('Auto-playback initialized successfully');
        } else {
          console.log('No cameras or players available for auto-playback');
          
          // Clear loading state if no players found
          this.cameras.forEach(camera => {
            camera.loading = false;
          });
        }
      } catch (error) {
        console.error('Error initializing video playback:', error);
        
        // Clear loading state on error
        this.cameras.forEach(camera => {
          camera.loading = false;
          camera.error = 'Failed to initialize playback';
        });
      }
    },
    
    async playAllVideos() {
      console.log('Attempting to play all videos');
      
      // Ensure we have adaptive players
      if (!this.$refs.adaptivePlayers || this.$refs.adaptivePlayers.length === 0) {
        console.log('No AdaptivePlayer components found');
        return;
      }
      
      // Trigger play on all AdaptivePlayer components
      const playPromises = this.$refs.adaptivePlayers.map(async (player, index) => {
        if (player && player.playVideo) {
          try {
            console.log(`Starting playback for camera ${index + 1}`);
            await player.playVideo();
            
            // Update camera state to show it's playing
            if (this.cameras[index]) {
              this.cameras[index].loading = false;
              this.cameras[index].streaming = true;
              this.cameras[index].showSnapshot = false;
            }
          } catch (error) {
            console.log(`Failed to play video for camera ${index + 1}:`, error);
            
            // Keep snapshot visible if video fails
            if (this.cameras[index]) {
              this.cameras[index].loading = false;
              this.cameras[index].showSnapshot = true;
            }
          }
        }
      });
      
      // Wait for all play attempts to complete
      await Promise.allSettled(playPromises);
      console.log('Finished attempting to start all videos');
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

    // Setup mobile-specific touch handling
    setupMobileTouchHandling() {
      // Prevent iOS momentum scrolling from affecting video containers
      document.addEventListener('touchstart', this.handleTouchStart, { passive: true });
      document.addEventListener('touchmove', this.handleTouchMove, { passive: false });
    },

    handleTouchStart(event) {
      // Store initial touch position for potential scroll intervention
      this.touchStartY = event.touches[0].clientY;
    },

    handleTouchMove(event) {
      // Prevent rubber band scrolling on video containers
      const target = event.target.closest('.video-wrapper');
      if (target) {
        // Allow normal scrolling but prevent extreme momentum
        const touchY = event.touches[0].clientY;
        const deltaY = touchY - this.touchStartY;
        
        // If scrolling too fast over video, slightly dampen it
        if (Math.abs(deltaY) > 50) {
          event.preventDefault();
        }
      }
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

/* Mobile video containment fixes */
.camera-container {
  /* Force hardware acceleration and proper containment */
  transform: translateZ(0);
  -webkit-transform: translateZ(0);
  will-change: auto;
  contain: layout style paint;
}

.video-wrapper {
  /* Ensure videos stay contained during scroll */
  overflow: hidden;
  position: relative;
  /* Force GPU layer for better performance */
  transform: translate3d(0, 0, 0);
  -webkit-transform: translate3d(0, 0, 0);
  /* Prevent content from breaking out during scroll */
  contain: strict;
}

/* Global video element constraints for mobile */
:deep(video) {
  /* Ensure video respects container bounds */
  max-width: 100% !important;
  max-height: 100% !important;
  object-fit: cover;
  /* Prevent video from being affected by scroll transforms */
  transform: translate3d(0, 0, 0);
  -webkit-transform: translate3d(0, 0, 0);
  /* Lock video position during scroll */
  position: absolute !important;
  top: 0 !important;
  left: 0 !important;
  width: 100% !important;
  height: 100% !important;
  /* Prevent zoom/scale issues on mobile */
  -webkit-background-size: cover;
  background-size: cover;
}

/* iOS Safari specific fixes */
@supports (-webkit-touch-callout: none) {
  .video-wrapper {
    /* iOS-specific containment */
    -webkit-overflow-scrolling: auto;
    isolation: isolate;
  }
  
  :deep(video) {
    /* Prevent iOS video scaling issues */
    -webkit-transform: translate3d(0, 0, 0);
    transform: translate3d(0, 0, 0);
    -webkit-backface-visibility: hidden;
    backface-visibility: hidden;
    /* Force proper video sizing on iOS */
    object-position: center center;
  }
}

/* Mobile-specific adjustments */
@media (max-width: 768px) {
  /* Prevent body scroll interference with videos */
  :deep(body) {
    -webkit-overflow-scrolling: touch;
    overflow-scrolling: touch;
  }
  
  .camera-container {
    /* Enhanced mobile containment */
    overflow: hidden;
    isolation: isolate;
    /* Prevent touch action propagation to videos */
    touch-action: pan-y;
  }
  
  .video-wrapper {
    /* Stronger containment for mobile */
    contain: layout style paint size;
    /* Prevent momentum scroll interference */
    -webkit-overflow-scrolling: auto;
    /* Prevent touch manipulation of videos */
    touch-action: none;
  }
  
  :deep(video) {
    /* Mobile video optimization */
    -webkit-video-autoplay: auto;
    /* Prevent mobile browser video manipulation */
    -webkit-transform-style: preserve-3d;
    transform-style: preserve-3d;
    /* Prevent video zoom/pan but allow clicks */
    touch-action: manipulation;
  }
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