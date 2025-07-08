<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <!-- Header -->
    <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-2">Live Camera Feeds</h1>
        <p class="text-base-content text-opacity-70">
          Real-time monitoring of all cameras
        </p>
      </div>
      <div class="flex items-center gap-3">
        <button 
          @click="toggleAutoRefresh" 
          class="btn btn-outline btn-sm"
          :class="{ 'btn-active': autoRefreshEnabled }"
        >
          <span v-if="autoRefreshEnabled" class="loading loading-spinner loading-xs"></span>
          <span v-else>⏱️</span>
          {{ autoRefreshEnabled ? 'Auto-Refresh On' : 'Auto-Refresh Off' }}
        </button>
        <button 
          @click="toggleFullscreen" 
          class="btn btn-outline btn-sm"
          :class="{ 'btn-active': isFullscreen }"
        >
          <span v-if="isFullscreen">↺</span>
          <span v-else>⛶</span>
          {{ isFullscreen ? 'Exit Fullscreen' : 'Fullscreen' }}
        </button>
        <button 
          @click="refreshCameras" 
          class="btn btn-primary btn-sm"
          :disabled="loading"
        >
          <span v-if="loading" class="loading loading-spinner loading-xs"></span>
          <span v-else>↻</span>
          Refresh
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div v-for="i in 2" :key="i" class="aspect-video bg-base-300 rounded-xl animate-pulse"></div>
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
          <!-- HLS.js player for Frontyard/Backyard -->
          <video
            v-if="camera.hlsUrl"
            :ref="`hlsVideo-${camera.id}`"
            class="w-full h-full object-cover absolute inset-0"
            controls
            autoplay
            muted
            playsinline
          ></video>
          <!-- Dual video for other cameras -->
          <template v-else>
            <video
              v-show="camera.activeVideo === 0"
              :key="camera.id + '-A'"
              :ref="`videoA-${camera.id}`"
              :src="camera.videoSources[0]"
              class="w-full h-full object-cover absolute inset-0 transition-opacity duration-200"
              :style="{ opacity: camera.activeVideo === 0 ? 1 : 0 }"
              muted
              autoplay
              playsinline
              @ended="handleVideoEnded(camera)"
              @canplay="handleCanPlay(camera, 0)"
              @error="handleVideoError(camera)"
            ></video>
            <video
              v-show="camera.activeVideo === 1"
              :key="camera.id + '-B'"
              :ref="`videoB-${camera.id}`"
              :src="camera.videoSources[1]"
              class="w-full h-full object-cover absolute inset-0 transition-opacity duration-200"
              :style="{ opacity: camera.activeVideo === 1 ? 1 : 0 }"
              muted
              autoplay
              playsinline
              @ended="handleVideoEnded(camera)"
              @canplay="handleCanPlay(camera, 1)"
              @error="handleVideoError(camera)"
            ></video>
          </template>
          <!-- Fallback to Snapshot -->
          <img
            v-if="!camera.hlsUrl && !camera.videoSources[0] && !camera.videoSources[1]"
            :ref="`image-${camera.id}`"
            :src="camera.snapshotUrl"
            class="w-full h-full object-cover transition-opacity duration-300"
            @error="handleImageError(camera)"
            @load="handleImageLoad(camera)"
            alt="Camera feed"
          />
          <!-- Loading Overlay -->
          <div 
            v-if="camera.loading" 
            class="absolute inset-0 bg-base-300 flex items-center justify-center"
          >
            <span class="loading loading-spinner loading-lg text-primary"></span>
          </div>
          <!-- Error Overlay -->
          <div 
            v-if="camera.error" 
            class="absolute inset-0 bg-base-300 flex flex-col items-center justify-center p-4"
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
          <!-- Fullscreen Button -->
          <button 
            @click="toggleCameraFullscreen(camera)"
            class="absolute bottom-2 right-2 btn btn-circle btn-sm btn-primary opacity-70 hover:opacity-100 transition-opacity duration-200"
            :title="camera.fullscreen ? 'Exit Fullscreen' : 'Fullscreen'"
          >
            <span v-if="camera.fullscreen">↺</span>
            <span v-else>⛶</span>
          </button>
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
      :key="`fullscreen-${fullscreenCamera.id}`"
      ref="fullscreen-overlay"
    >

      <!-- Fullscreen Header -->
      <div class="flex items-center justify-between p-4 bg-base-300 bg-opacity-90">
        <div class="flex items-center gap-4">
          <h2 class="text-xl font-bold text-primary-content">{{ fullscreenCamera.id }}</h2>
          <div v-if="fullscreenCamera.recordingUrl" class="flex gap-2">
            <div class="badge badge-info">RECORDING</div>
            <div v-if="fullscreenCamera.recordingTimestamp" class="badge badge-success">
              {{ formatRecordingTime(fullscreenCamera.recordingTimestamp) }}
            </div>
            <div v-if="fullscreenCamera.bufferStatus" class="badge badge-warning">
              Buffer: {{ fullscreenCamera.bufferStatus.currentIndex + 1 }}/{{ fullscreenCamera.bufferStatus.totalRecordings }}
            </div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button 
            @click="exitFullscreen"
            class="btn btn-circle btn-primary"
          >
            <span>✕</span>
          </button>
        </div>
      </div>
      
      <!-- Fullscreen Video/Image Container -->
      <div class="flex-1 relative bg-black">
        <!-- Dual Video for Fullscreen -->
        <video
          v-show="fullscreenCamera.activeVideo === 0"
          :key="fullscreenCamera.id + '-A'"
          :ref="`fullscreenVideoA-${fullscreenCamera.id}`"
          :src="fullscreenCamera.videoSources[0]"
          class="w-full h-full object-contain absolute inset-0 transition-opacity duration-200"
          :style="{ opacity: fullscreenCamera.activeVideo === 0 ? 1 : 0 }"
          muted
          autoplay
          playsinline
          @ended="handleFullscreenVideoEnded"
          @canplay="handleFullscreenCanPlay(0)"
          @error="handleFullscreenVideoError"
        ></video>
        <video
          v-show="fullscreenCamera.activeVideo === 1"
          :key="fullscreenCamera.id + '-B'"
          :ref="`fullscreenVideoB-${fullscreenCamera.id}`"
          :src="fullscreenCamera.videoSources[1]"
          class="w-full h-full object-contain absolute inset-0 transition-opacity duration-200"
          :style="{ opacity: fullscreenCamera.activeVideo === 1 ? 1 : 0 }"
          muted
          autoplay
          playsinline
          @ended="handleFullscreenVideoEnded"
          @canplay="handleFullscreenCanPlay(1)"
          @error="handleFullscreenVideoError"
        ></video>
        <!-- Fallback to Snapshot -->
        <img
          v-if="!fullscreenCamera.videoSources[0] && !fullscreenCamera.videoSources[1]"
          :ref="`fullscreen-image-${fullscreenCamera.id}`"
          :src="fullscreenCamera.snapshotUrl"
          class="w-full h-full object-contain transition-opacity duration-300"
          @error="handleFullscreenImageError"
          @load="handleFullscreenImageLoad"
          alt="Camera feed"
        />
        <!-- Loading Overlay -->
        <div 
          v-if="fullscreenCamera.loading" 
          class="absolute inset-0 bg-base-300 flex items-center justify-center"
        >
          <span class="loading loading-spinner loading-lg text-primary"></span>
        </div>
        <!-- Error Overlay -->
        <div 
          v-if="fullscreenCamera.error" 
          class="absolute inset-0 bg-base-300 flex flex-col items-center justify-center p-4"
        >
          <svg class="w-12 h-12 text-error mb-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z"/>
          </svg>
          <p class="text-error text-sm text-center">{{ fullscreenCamera.error }}</p>
          <button 
            @click="retryFullscreenCamera" 
            class="btn btn-sm btn-outline mt-2"
          >
            Retry
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import apiService from '@/services/api.js';
// Import hls.js for HLS playback
import Hls from 'hls.js';

export default {
  name: 'CameraMultiview',
  data() {
    return {
      loading: false,
      error: null,
      cameras: [],
      isFullscreen: false,
      // No longer using HLS instances since we're using direct video files
      autoRefreshEnabled: true, // Auto-refresh enabled by default
      autoRefreshInterval: null, // Interval for auto-refresh
      recordingRefreshInterval: null, // Separate interval for recording refresh
      fullscreenCamera: null, // Currently fullscreen camera
      // Buffer management system
      bufferManagers: new Map(), // Map of camera ID to buffer manager
      bufferSize: 6, // 1 minute buffer (6 x 10-second clips)
      bufferRefreshInterval: null, // Interval for buffer refresh
      hlsPlayers: {}, // Store hls.js instances by camera id
    };
  },

  // Buffer Manager Class for handling seamless video transitions
  beforeCreate() {
    // Define BufferManager class
    this.BufferManager = class BufferManager {
      constructor(cameraId, bufferSize = 6) {
        this.cameraId = cameraId;
        this.bufferSize = bufferSize;
        this.recordings = []; // Array of recording objects
        this.currentIndex = 0; // Current playing recording index
        this.preloadedVideos = new Map(); // Map of recording ID to preloaded video element
        this.isBuffering = false;
        this.lastUpdateTime = 0;
      }

      // Add recordings to buffer
      updateRecordings(newRecordings) {
        if (!newRecordings || newRecordings.length === 0) return false;
        
        // Sort recordings by start_time (oldest first for chronological playback)
        const sortedRecordings = [...newRecordings].sort((a, b) => a.start_time - b.start_time);
        
        // Check if we have new recordings
        if (this.recordings.length === 0) {
          this.recordings = sortedRecordings.slice(0, this.bufferSize);
          this.currentIndex = 0; // Start from oldest
          this.lastUpdateTime = Date.now();
          return true;
        }

        // Check if we have newer recordings to add to the buffer
        const currentOldest = this.recordings[0];
        const currentNewest = this.recordings[this.recordings.length - 1];
        
        // Find recordings that are newer than our current newest
        const newerRecordings = sortedRecordings.filter(r => r.start_time > currentNewest.start_time);
        
        if (newerRecordings.length > 0) {
          // Add newer recordings to the end of the buffer
          this.recordings = [...this.recordings, ...newerRecordings];
          
          // Keep only the bufferSize most recent recordings, but don't remove the current playing recording
          if (this.recordings.length > this.bufferSize) {
            // Find the current playing recording
            const currentRecording = this.recordings[this.currentIndex];
            if (currentRecording) {
              // Keep recordings from current index onwards, plus some newer ones
              const keepFromIndex = Math.max(0, this.currentIndex);
              const recordingsToKeep = this.recordings.slice(keepFromIndex);
              
              // If we still have too many, trim from the end
              if (recordingsToKeep.length > this.bufferSize) {
                this.recordings = recordingsToKeep.slice(0, this.bufferSize);
              } else {
                this.recordings = recordingsToKeep;
              }
              
              // Adjust current index since we removed older recordings
              this.currentIndex = 0;
            } else {
              // Fallback: keep most recent recordings
              this.recordings = this.recordings.slice(-this.bufferSize);
            }
          }
          
          this.lastUpdateTime = Date.now();
          
          // Clear old preloaded videos
          this.clearPreloadedVideos();
          
          return true;
        }
        
        return false;
      }

      // Get current recording
      getCurrentRecording() {
        if (this.recordings.length === 0) return null;
        return this.recordings[this.currentIndex];
      }

      // Get next recording in buffer
      getNextRecording() {
        if (this.recordings.length === 0) return null;
        const nextIndex = this.currentIndex + 1;
        
        // If we've reached the end, loop back to the beginning (oldest)
        if (nextIndex >= this.recordings.length) {
          return this.recordings[0];
        }
        
        return this.recordings[nextIndex];
      }

      // Move to next recording
      advanceToNext() {
        if (this.recordings.length === 0) return false;
        this.currentIndex = this.currentIndex + 1;
        
        // If we've reached the end, loop back to the beginning
        if (this.currentIndex >= this.recordings.length) {
          this.currentIndex = 0;
        }
        
        return true;
      }

      // Preload a recording
      async preloadRecording(recording, apiService) {
        if (!recording || !recording.file_path) return false;
        
        const recordingId = recording.id;
        if (this.preloadedVideos.has(recordingId)) return true; // Already preloaded
        
        try {
          const videoUrl = apiService.getRecordingUrl(this.cameraId, recording.file_path);
          
          // Create hidden video element for preloading
          const video = document.createElement('video');
          video.style.position = 'absolute';
          video.style.top = '-9999px';
          video.style.left = '-9999px';
          video.style.width = '1px';
          video.style.height = '1px';
          video.muted = true;
          video.preload = 'auto';
          video.playsInline = true;
          
          // Add to DOM temporarily
          document.body.appendChild(video);
          
          // Set up preload promise
          const preloadPromise = new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
              reject(new Error('Preload timeout'));
            }, 10000); // 10 second timeout
            
            const handleCanPlay = () => {
              clearTimeout(timeout);
              video.removeEventListener('canplay', handleCanPlay);
              video.removeEventListener('error', handleError);
              resolve(video);
            };
            
            const handleError = (error) => {
              clearTimeout(timeout);
              video.removeEventListener('canplay', handleCanPlay);
              video.removeEventListener('error', handleError);
              reject(error);
            };
            
            video.addEventListener('canplay', handleCanPlay);
            video.addEventListener('error', handleError);
          });
          
          // Start preloading
          video.src = videoUrl;
          
          // Wait for preload to complete
          await preloadPromise;
          
          // Store preloaded video
          this.preloadedVideos.set(recordingId, video);
          
          return true;
        } catch (error) {
          console.warn(`Failed to preload recording ${recordingId} for ${this.cameraId}:`, error);
          return false;
        }
      }

      // Get preloaded video
      getPreloadedVideo(recordingId) {
        return this.preloadedVideos.get(recordingId);
      }

      // Clear preloaded videos
      clearPreloadedVideos() {
        this.preloadedVideos.forEach(video => {
          if (video && video.parentNode) {
            video.parentNode.removeChild(video);
          }
        });
        this.preloadedVideos.clear();
      }

      // Check if buffer is complete
      isBufferComplete() {
        return this.recordings.length >= this.bufferSize;
      }

      // Get buffer status
      getBufferStatus() {
        return {
          totalRecordings: this.recordings.length,
          currentIndex: this.currentIndex,
          bufferComplete: this.isBufferComplete(),
          preloadedCount: this.preloadedVideos.size
        };
      }
    };
  },
  
  async mounted() {
    await this.loadCameras(true);
    // Start auto-refresh if enabled
    if (this.autoRefreshEnabled) {
      this.startAutoRefresh();
    }
    
    // Add keyboard event listener for fullscreen
    document.addEventListener('keydown', this.handleKeydown);
    this.$nextTick(() => {
      this.initAllHlsPlayers();
    });
  },
  
  updated() {
    // Re-initialize HLS players if cameras change
    this.$nextTick(() => {
      this.initAllHlsPlayers();
    });
  },
  
  beforeUnmount() {
    // Cleanup all intervals
    this.stopAutoRefresh();
    this.stopRecordingRefresh();
    this.stopBufferRefresh();
    this.cleanupAllHlsPlayers();
    
    // No longer using HLS instances
    
    // Cleanup video and image event listeners
    this.cameras.forEach(camera => {
      const videoElement = this.$refs[`videoA-${camera.id}`];
      if (videoElement && videoElement[0]) {
        this.removeVideoEventListeners(videoElement[0]);
        // Clear video source to stop loading
        videoElement[0].src = '';
        videoElement[0].load();
      }
      const videoElementB = this.$refs[`videoB-${camera.id}`];
      if (videoElementB && videoElementB[0]) {
        this.removeVideoEventListeners(videoElementB[0]);
        videoElementB[0].src = '';
        videoElementB[0].load();
      }
      
      const imageElement = this.$refs[`image-${camera.id}`];
      if (imageElement && imageElement[0]) {
        this.removeImageEventListeners(imageElement[0]);
        // Clear image source
        imageElement[0].src = '';
      }
    });
    
    // Cleanup buffer managers
    this.bufferManagers.forEach(bufferManager => {
      bufferManager.clearPreloadedVideos();
    });
    this.bufferManagers.clear();
    
    // Remove keyboard event listener
    document.removeEventListener('keydown', this.handleKeydown);
    
    // Clear camera data
    this.cameras = [];
  },
  
  methods: {
    async loadCameras(showLoading = true) {
      try {
        if (showLoading) {
          this.loading = true;
          this.error = null;
        }
        // Fetch camera list and latest recordings
        const camerasResponse = await apiService.getCameras();
        const newCameras = camerasResponse.cameras || [];
        // Build a map for quick lookup of existing cameras
        const cameraMap = new Map(this.cameras.map(cam => [cam.id, cam]));
        // Track IDs seen in new response
        const seenIds = new Set();
        // Update or add cameras
        newCameras.forEach(newCam => {
          seenIds.add(newCam.id);
          const existing = cameraMap.get(newCam.id);
          if (existing) {
            // Update properties in-place
            Object.assign(existing, newCam, {
              snapshotUrl: newCam.snapshot_url || null,
              // Keep existing video/buffer state unless you want to reset
            });
            cameraMap.delete(newCam.id);
          } else {
            // Add new camera
            this.cameras.push({
              ...newCam,
              snapshotUrl: newCam.snapshot_url || null,
              loading: true,
              error: null,
              recordingUrl: null,
              recordingTimestamp: null,
              bufferStatus: null,
              videoSources: [null, null],
              activeVideo: 0
            });
          }
        });
        // Remove cameras that are no longer present
        for (const [id, cam] of cameraMap) {
          const idx = this.cameras.indexOf(cam);
          if (idx !== -1) this.cameras.splice(idx, 1);
        }
        // HLS is currently not working properly with go2rtc
        // Using MP4 recording buffer for all cameras for now
        this.cameras.forEach(camera => {
          camera.hlsUrl = null; // Disable HLS for all cameras
        });
        // Initialize buffers for each camera (skip cameras with HLS URLs)
        await Promise.all(this.cameras.map(async (camera) => {
          try {
            // Skip buffer initialization for cameras that use HLS
            if (camera.hlsUrl) {
              console.log(`Skipping buffer initialization for ${camera.id} - using HLS stream`);
              return;
            }
            
            // Try to initialize buffer first
            const bufferInitialized = await this.initializeBufferForCamera(camera);
            if (!bufferInitialized) {
              // Fall back to latest recording if buffer initialization fails
              const latestRecording = await apiService.getLatestRecording(camera.id);
              if (latestRecording && !latestRecording.error && latestRecording.file_path) {
                camera.recordingUrl = apiService.getRecordingUrl(camera.id, latestRecording.file_path);
                camera.recordingTimestamp = latestRecording.start_time;
              }
            }
          } catch (error) {
            console.warn(`Failed to initialize buffer for ${camera.id}:`, error);
          }
        }));
        // Initialize video and image elements after a short delay
        this.$nextTick(() => {
          setTimeout(() => {
            this.initializeAllCameras();
          }, 200);
        });
      } catch (error) {
        console.error('❌ Failed to load cameras:', error);
        this.error = 'Failed to load cameras. Please check your connection and try again.';
      } finally {
        if (showLoading) {
          this.loading = false;
        }
        console.log(`✅ loadCameras completed`);
      }
    },
    
    async refreshCameras() {
      await this.loadCameras(true);
      // Only re-initialize video/image if the src actually needs to change
      this.$nextTick(() => {
        this.cameras.forEach(camera => {
          // Skip HLS cameras - they are handled by initHlsPlayer
          if (camera.hlsUrl) {
            console.log(`refreshCameras: Skipping ${camera.id} - using HLS`);
            return;
          }
          
          // Only call initializeVideo if the video src is not already correct
          if (camera.recordingUrl) {
            const videoElement = this.$refs[`videoA-${camera.id}`];
            if (videoElement && videoElement[0]) {
              const video = videoElement[0];
              if (video.src !== camera.recordingUrl) {
                this.initializeVideo(camera);
              } else {
                console.log(`refreshCameras: Video src for ${camera.id} is already correct, skipping.`);
              }
            } else {
              this.initializeVideo(camera);
            }
          } else {
            this.initializeImage(camera);
          }
        });
      });
    },
    
    initializeVideo(camera) {
      console.log(`Initializing video for ${camera.id}`);
      const videoElement = this.$refs[`videoA-${camera.id}`];
      console.log(`Video element found for ${camera.id}:`, !!videoElement);
      if (videoElement && videoElement[0] && camera.recordingUrl) {
        const video = videoElement[0];
        // Only set src if it is different
        if (video.src !== camera.recordingUrl) {
          console.log(`Setting video source for ${camera.id}:`, camera.recordingUrl);
          // Remove existing event listeners to prevent memory leaks
          this.removeVideoEventListeners(video);
          video.src = camera.recordingUrl;
          // Add event listeners with bound functions for proper cleanup
          const boundHandlers = {
            loadstart: () => this.handleVideoLoadStart(camera),
            loadeddata: () => this.handleVideoLoaded(camera),
            canplay: () => this.handleVideoCanPlay(camera),
            error: () => this.handleVideoError(camera),
            ended: () => this.handleVideoEnded(camera)
          };
          video._boundHandlers = boundHandlers;
          Object.entries(boundHandlers).forEach(([event, handler]) => {
            video.addEventListener(event, handler);
          });
          // Try to play the video
          video.play().catch(e => console.log(`Auto-play prevented for ${camera.id}:`, e));
        } else {
          console.log(`Video src for ${camera.id} is already correct, skipping re-initialization.`);
        }
        return true; // Success
      } else {
        console.error(`Failed to initialize video for ${camera.id}:`, {
          videoElement: !!videoElement,
          recordingUrl: camera.recordingUrl
        });
        return false; // Failure
      }
    },

    // Removed updateVideoSeamlessly - now using buffer system
    
    removeVideoEventListeners(video) {
      if (video._boundHandlers) {
        Object.entries(video._boundHandlers).forEach(([event, handler]) => {
          video.removeEventListener(event, handler);
        });
        delete video._boundHandlers;
      }
    },
    
    initializeAllCameras() {
      let allInitialized = true;
      
      this.cameras.forEach(camera => {
        console.log(`Initializing ${camera.id}:`, {
          hasHlsUrl: !!camera.hlsUrl,
          hlsUrl: camera.hlsUrl,
          hasRecordingUrl: !!camera.recordingUrl,
          recordingUrl: camera.recordingUrl,
          hasSnapshotUrl: !!camera.snapshotUrl
        });
        
        if (camera.hlsUrl) {
          console.log(`Using HLS for ${camera.id}: ${camera.hlsUrl}`);
          this.initHlsPlayer(camera);
        } else if (camera.recordingUrl) {
          console.log(`Using MP4 recording for ${camera.id}: ${camera.recordingUrl}`);
          const success = this.initializeVideo(camera);
          if (!success) allInitialized = false;
        } else {
          console.log(`Using snapshot for ${camera.id}`);
          const success = this.initializeImage(camera);
          if (!success) allInitialized = false;
        }
      });
      
      // If not all cameras were initialized, retry after a delay
      if (!allInitialized) {
        console.log('Some cameras failed to initialize, retrying...');
        setTimeout(() => {
          this.initializeAllCameras();
        }, 500);
      }
    },
    
    initializeImage(camera) {
      const imageElement = this.$refs[`image-${camera.id}`];
      
      if (imageElement && imageElement[0]) {
        const img = imageElement[0];
        
        // Remove existing event listeners
        this.removeImageEventListeners(img);
        
        // Set up image event listeners with bound functions
        const boundHandlers = {
          load: () => this.handleImageLoad(camera),
          error: () => this.handleImageError(camera)
        };
        
        // Store bound handlers for cleanup
        img._boundHandlers = boundHandlers;
        
        Object.entries(boundHandlers).forEach(([event, handler]) => {
          img.addEventListener(event, handler);
        });
        
        return true; // Success
      } else {
        console.error(`Failed to initialize image for ${camera.id}: image element not found`);
        return false; // Failure
      }
    },
    
    removeImageEventListeners(img) {
      if (img._boundHandlers) {
        Object.entries(img._boundHandlers).forEach(([event, handler]) => {
          img.removeEventListener(event, handler);
        });
        delete img._boundHandlers;
      }
    },
    
    initializeFullscreenVideo(camera) {
      // Add a small delay to ensure DOM is fully updated
      return new Promise((resolve) => {
        setTimeout(async () => {
          const videoElement = this.$refs[`fullscreenVideoA-${camera.id}`];
          
          // Handle Vue ref properly - it might be an array or direct element
          let video = null;
          if (videoElement) {
            if (Array.isArray(videoElement)) {
              video = videoElement[0];
            } else {
              video = videoElement;
            }
          }
          
          // Try to find the video element in the DOM manually if ref fails
          if (!video) {
            const manualVideoElement = document.querySelector(`video[ref="fullscreenVideoA-${camera.id}"]`);
            if (manualVideoElement) {
              video = manualVideoElement;
            }
          }
          
          if (video && camera.recordingUrl) {
            // Remove existing event listeners to prevent memory leaks
            this.removeVideoEventListeners(video);
            
            // Set the video source to the recording URL
            video.src = camera.recordingUrl;
            
            // Add event listeners with bound functions for proper cleanup
            const boundHandlers = {
              loadstart: () => this.handleFullscreenVideoLoadStart(),
              loadeddata: () => this.handleFullscreenVideoLoaded(),
              canplay: () => this.handleFullscreenVideoCanPlay(),
              error: () => this.handleFullscreenVideoError(),
              ended: () => this.handleFullscreenVideoEnded()
            };
            
            // Store bound handlers for cleanup
            video._boundHandlers = boundHandlers;
            
            // Add event listeners
            Object.entries(boundHandlers).forEach(([event, handler]) => {
              video.addEventListener(event, handler);
            });
            
            // Try to play the video
            video.play().catch(e => console.log(`Auto-play prevented for fullscreen ${camera.id}:`, e));
            
            // Ensure buffer is properly initialized and preloaded for fullscreen
            const bufferManager = this.bufferManagers.get(camera.id);
            if (bufferManager) {
              try {
                await this.preloadBufferRecordings(camera, bufferManager);
              } catch (error) {
                console.error(`Fullscreen buffer preloading failed for ${camera.id}:`, error);
              }
            }
            
            resolve(true); // Success
          } else {
            resolve(false); // Failure
          }
        }, 100); // Small delay to ensure DOM is updated
      });
    },
    
    initializeFullscreenImage(camera) {
      const imageElement = this.$refs[`fullscreen-image-${camera.id}`];
      
      if (imageElement && imageElement[0]) {
        const img = imageElement[0];
        
        // Remove existing event listeners
        this.removeImageEventListeners(img);
        
        // Set up image event listeners with bound functions
        const boundHandlers = {
          load: () => this.handleFullscreenImageLoad(),
          error: () => this.handleFullscreenImageError()
        };
        
        // Store bound handlers for cleanup
        img._boundHandlers = boundHandlers;
        
        Object.entries(boundHandlers).forEach(([event, handler]) => {
          img.addEventListener(event, handler);
        });
        
        return true; // Success
      } else {
        return false; // Failure
      }
    },
    
    handleImageLoad(camera) {
      camera.loading = false;
      camera.error = null;
    },
    
    handleImageError(camera) {
      camera.loading = false;
      camera.error = 'Failed to load camera feed';
      console.error(`Image error for camera ${camera.id}:`, camera.error);
    },
    
    handleVideoLoadStart(camera) {
      camera.loading = true;
      camera.error = null;
      console.log(`Video load started for camera ${camera.id}`);
    },
    
    handleVideoLoaded(camera) {
      camera.loading = false;
      camera.error = null;
      console.log(`Video loaded for camera ${camera.id}`);
    },
    
    handleVideoCanPlay(camera) {
      camera.loading = false;
      camera.error = null;
      console.log(`Video can play for camera ${camera.id}`);
    },
    
    handleVideoError(camera) {
      camera.loading = false;
      camera.error = 'Failed to load recording';
      console.error(`Video error for camera ${camera.id}`);
    },
    
    handleVideoEnded(camera) {
      // Switch to next recording in buffer
      this.switchToNextRecording(camera);
    },
    
    // Removed stream and MJPEG handlers - no longer needed
    
    // Fullscreen event handlers
    handleFullscreenVideoLoadStart() {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.loading = true;
        this.fullscreenCamera.error = null;
      }
    },
    
    handleFullscreenVideoLoaded() {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.loading = false;
        this.fullscreenCamera.error = null;
      }
    },
    
    handleFullscreenVideoCanPlay() {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.loading = false;
        this.fullscreenCamera.error = null;
      }
    },
    
    handleFullscreenVideoError() {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.loading = false;
        this.fullscreenCamera.error = 'Failed to load recording';
      }
    },
    
    handleFullscreenVideoEnded() {
      if (this.fullscreenCamera) {
        // Switch to next recording in buffer
        this.switchToNextRecording(this.fullscreenCamera);
      }
    },
    
    handleFullscreenImageLoad() {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.loading = false;
        this.fullscreenCamera.error = null;
      }
    },
    
    handleFullscreenImageError() {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.loading = false;
        this.fullscreenCamera.error = 'Failed to load camera feed';
      }
    },
    
    async retryFullscreenCamera() {
      if (this.fullscreenCamera) {
        this.fullscreenCamera.loading = true;
        this.fullscreenCamera.error = null;
        
        if (this.fullscreenCamera.recordingUrl) {
          this.initializeFullscreenVideo(this.fullscreenCamera);
        } else {
          this.initializeFullscreenImage(this.fullscreenCamera);
        }
      }
    },
    
    handleKeydown(event) {
      // Exit fullscreen with Escape key
      if (event.key === 'Escape' && this.fullscreenCamera) {
        this.exitFullscreen();
      }
    },
    
    // Removed updateFullscreenVideo - now using buffer system for fullscreen too
    
    startAutoRefresh() {
      // Stop any existing intervals
      this.stopAutoRefresh();
      this.stopRecordingRefresh();
      this.stopBufferRefresh();
      
      if (!this.autoRefreshEnabled) return;
      
      // Refresh snapshots every 5 seconds (only for cameras without recordings)
      this.autoRefreshInterval = setInterval(() => {
        this.cameras.forEach(camera => {
          if (camera.snapshotUrl && !camera.recordingUrl) {
            const imageElement = this.$refs[`image-${camera.id}`];
            if (imageElement && imageElement[0]) {
              const img = imageElement[0];
              // Add timestamp to prevent caching
              img.src = `${camera.snapshotUrl}?t=${Date.now()}`;
            }
          }
        });
      }, 5000);
      
      // Refresh recordings every 8 seconds (check for new recordings)
      // This timing ensures we catch most 10-second clips with minimal delay
      this.recordingRefreshInterval = setInterval(async () => {
        await this.refreshRecordings();
      }, 8000);
      
      // Refresh buffer every 10 seconds (less frequent than recordings)
      this.bufferRefreshInterval = setInterval(async () => {
        await this.refreshBuffers();
      }, 10000);
    },
    
    stopAutoRefresh() {
      if (this.autoRefreshInterval) {
        clearInterval(this.autoRefreshInterval);
        this.autoRefreshInterval = null;
      }
    },
    
    stopRecordingRefresh() {
      if (this.recordingRefreshInterval) {
        clearInterval(this.recordingRefreshInterval);
        this.recordingRefreshInterval = null;
      }
    },
    
    stopBufferRefresh() {
      if (this.bufferRefreshInterval) {
        clearInterval(this.bufferRefreshInterval);
        this.bufferRefreshInterval = null;
      }
    },
    
    // Buffer management methods
    async initializeBufferForCamera(camera) {
      try {
        // Create buffer manager if it doesn't exist
        if (!this.bufferManagers.has(camera.id)) {
          this.bufferManagers.set(camera.id, new this.BufferManager(camera.id, this.bufferSize));
        }
        const bufferManager = this.bufferManagers.get(camera.id);
        // Get buffered recordings
        const bufferResponse = await apiService.getBufferedRecordings(camera.id, this.bufferSize, 2);
        if (bufferResponse && bufferResponse.recordings && bufferResponse.recordings.length > 0) {
          // Update buffer with new recordings
          const updated = bufferManager.updateRecordings(bufferResponse.recordings);
          if (updated || bufferManager.recordings.length > 0) {
            // Get current recording from buffer (start with oldest)
            const currentRecording = bufferManager.getCurrentRecording();
            if (currentRecording) {
              camera.recordingUrl = apiService.getRecordingUrl(camera.id, currentRecording.file_path);
              camera.recordingTimestamp = currentRecording.start_time;
              camera.bufferStatus = bufferManager.getBufferStatus();
              // After buffer is ready, set up dual video sources
              if (!camera.videoSources || camera.videoSources.length !== 2) {
                camera.videoSources = [null, null];
              }
              camera.activeVideo = 0;
              // Set first two clips if available, only mutate
              if (bufferManager.recordings.length > 0) {
                camera.videoSources[0] = apiService.getRecordingUrl(camera.id, bufferManager.recordings[0].file_path);
                if (bufferManager.recordings.length > 1) {
                  camera.videoSources[1] = apiService.getRecordingUrl(camera.id, bufferManager.recordings[1].file_path);
                }
              }
              // Start preloading next recordings in buffer
              this.preloadBufferRecordings(camera, bufferManager);
              return true;
            }
          }
        }
        return false;
      } catch (error) {
        console.warn(`Failed to initialize buffer for ${camera.id}:`, error);
        return false;
      }
    },
    
    async preloadBufferRecordings(camera, bufferManager) {
      try {
        // Preload next few recordings in chronological order
        const currentIndex = bufferManager.currentIndex;
        const recordingsToPreload = [];
        
        // Get next 3 recordings (or fewer if we don't have that many)
        for (let i = 0; i < 3; i++) {
          const nextIndex = (currentIndex + i + 1) % bufferManager.recordings.length;
          recordingsToPreload.push(bufferManager.recordings[nextIndex]);
        }
        
        for (const recording of recordingsToPreload) {
          await bufferManager.preloadRecording(recording, apiService);
        }
      } catch (error) {
        console.warn(`Failed to preload recordings for ${camera.id}:`, error);
      }
    },
    
    async refreshBuffers() {
      // Refresh buffers for all cameras with recordings
      for (const camera of this.cameras) {
        if (camera.recordingUrl) {
          await this.refreshBufferForCamera(camera);
        }
      }
    },
    
    async refreshBufferForCamera(camera) {
      try {
        const bufferManager = this.bufferManagers.get(camera.id);
        if (!bufferManager) return;
        // Get latest buffered recordings
        const bufferResponse = await apiService.getBufferedRecordings(camera.id, this.bufferSize, 2);
        if (bufferResponse && bufferResponse.recordings && bufferResponse.recordings.length > 0) {
          // Update buffer with new recordings
          const updated = bufferManager.updateRecordings(bufferResponse.recordings);
          if (updated) {
            console.log(`Buffer updated for ${camera.id} - added ${bufferManager.recordings.length} recordings`);
            // Don't change the current recording - let it continue playing through the buffer
            // Just update the buffer status
            camera.bufferStatus = bufferManager.getBufferStatus();
            // Only update the hidden video's src (mutate, don't replace array)
            const nextIdx = (bufferManager.currentIndex + 1) % bufferManager.recordings.length;
            const nextRecording = bufferManager.recordings[nextIdx];
            if (nextRecording && camera.videoSources && camera.videoSources.length === 2) {
              camera.videoSources[1 - camera.activeVideo] = apiService.getRecordingUrl(camera.id, nextRecording.file_path);
            }
            // Preload new recordings
            this.preloadBufferRecordings(camera, bufferManager);
          }
        }
      } catch (error) {
        console.warn(`Failed to refresh buffer for ${camera.id}:`, error);
      }
    },
    
    // Seamless video switching using buffer
    switchToNextRecording(camera) {
      const bufferManager = this.bufferManagers.get(camera.id);
      if (!bufferManager) {
        return false;
      }
      
      // Get next recording from buffer
      const nextRecording = bufferManager.getNextRecording();
      if (!nextRecording) {
        return false;
      }
      
      // Check if next recording is preloaded
      const preloadedVideo = bufferManager.getPreloadedVideo(nextRecording.id);
      
      // Determine if we're in fullscreen mode
      const isFullscreen = this.fullscreenCamera && this.fullscreenCamera.id === camera.id;
      
      if (preloadedVideo) {
        // Get the appropriate video element (regular or fullscreen)
        let videoElement = null;
        if (isFullscreen) {
          videoElement = this.$refs[`fullscreenVideoA-${camera.id}`];
          
          // Handle Vue ref properly - it might be an array or direct element
          if (videoElement) {
            if (Array.isArray(videoElement)) {
              videoElement = videoElement[0];
            }
            // If it's still not an element, try to find it in the DOM
            if (!videoElement || !(videoElement instanceof HTMLVideoElement)) {
              const manualVideoElement = document.querySelector(`video[ref*="fullscreenVideoA-${camera.id}"]`);
              if (manualVideoElement) {
                videoElement = manualVideoElement;
              }
            }
          }
        } else {
          videoElement = this.$refs[`videoA-${camera.id}`];
          if (videoElement && Array.isArray(videoElement)) {
            videoElement = videoElement[0];
          }
        }
        
        if (videoElement && videoElement instanceof HTMLVideoElement) {
          const video = videoElement;
          
          // Store current playback state
          const wasPlaying = !video.paused;
          
          // Temporarily reduce opacity for smoother transition
          video.style.opacity = '0.7';
          
          // Remove existing event listeners
          this.removeVideoEventListeners(video);
          
          // Copy preloaded video properties to visible video
          video.src = preloadedVideo.src;
          video.currentTime = 0;
          
          // Add event listeners based on whether we're in fullscreen or not
          let boundHandlers;
          if (isFullscreen) {
            boundHandlers = {
              loadstart: () => this.handleFullscreenVideoLoadStart(),
              loadeddata: () => this.handleFullscreenVideoLoaded(),
              canplay: () => {
                video.style.opacity = '1';
                this.handleFullscreenVideoCanPlay();
              },
              error: () => this.handleFullscreenVideoError(),
              ended: () => this.handleFullscreenVideoEnded()
            };
          } else {
            boundHandlers = {
              loadstart: () => this.handleVideoLoadStart(camera),
              loadeddata: () => this.handleVideoLoaded(camera),
              canplay: () => {
                video.style.opacity = '1';
                this.handleVideoCanPlay(camera);
              },
              error: () => this.handleVideoError(camera),
              ended: () => this.handleVideoEnded(camera)
            };
          }
          
          video._boundHandlers = boundHandlers;
          Object.entries(boundHandlers).forEach(([event, handler]) => {
            video.addEventListener(event, handler);
          });
          
          // Resume playback if it was playing before
          if (wasPlaying) {
            video.play().catch(e => console.log(`Auto-play prevented for ${camera.id}:`, e));
          }
          
          // Update camera state
          camera.recordingUrl = apiService.getRecordingUrl(camera.id, nextRecording.file_path);
          camera.recordingTimestamp = nextRecording.start_time;
          camera.bufferStatus = bufferManager.getBufferStatus();
          
          // Advance buffer index
          bufferManager.advanceToNext();
          
          // Preload next recordings after successful switch
          this.preloadBufferRecordings(camera, bufferManager);
          
          return true;
        }
      } else {
        // Fall back to direct update if not preloaded
        camera.recordingUrl = apiService.getRecordingUrl(camera.id, nextRecording.file_path);
        camera.recordingTimestamp = nextRecording.start_time;
        camera.bufferStatus = bufferManager.getBufferStatus();
        bufferManager.advanceToNext();
        
        this.$nextTick(() => {
          if (isFullscreen) {
            // For fullscreen, we need to update the video source directly
            const fullscreenVideoElement = this.$refs[`fullscreenVideoA-${camera.id}`];
            if (fullscreenVideoElement && fullscreenVideoElement[0]) {
              const video = fullscreenVideoElement[0];
              
              // Remove existing event listeners
              this.removeVideoEventListeners(video);
              
              // Update video source
              video.src = camera.recordingUrl;
              video.currentTime = 0;
              
              // Add fullscreen event listeners
              const boundHandlers = {
                loadstart: () => this.handleFullscreenVideoLoadStart(),
                loadeddata: () => this.handleFullscreenVideoLoaded(),
                canplay: () => this.handleFullscreenVideoCanPlay(),
                error: () => this.handleFullscreenVideoError(),
                ended: () => this.handleFullscreenVideoEnded()
              };
              
              video._boundHandlers = boundHandlers;
              Object.entries(boundHandlers).forEach(([event, handler]) => {
                video.addEventListener(event, handler);
              });
              
              // Try to play the video
              video.play().catch(e => console.log(`Auto-play prevented for fullscreen ${camera.id}:`, e));
            }
          } else {
            this.initializeVideo(camera);
          }
        });
        
        // Preload next recordings after successful switch
        this.preloadBufferRecordings(camera, bufferManager);
        
        return true;
      }
    },
    
    // Removed checkForNewerRecording - now using buffer system
    
    async refreshRecordings() {
      // Use buffer system instead of individual recording checks
      // The buffer refresh is handled by refreshBuffers() which is called separately
      console.log('🔄 Recording refresh - using buffer system instead of individual checks');
    },
    
    toggleAutoRefresh() {
      this.autoRefreshEnabled = !this.autoRefreshEnabled;
      
      if (this.autoRefreshEnabled) {
        this.startAutoRefresh();
      } else {
        this.stopAutoRefresh();
        this.stopRecordingRefresh();
        this.stopBufferRefresh();
      }
    },
    
    toggleCameraFullscreen(camera) {
      if (this.fullscreenCamera === camera) {
        this.exitFullscreen();
      } else {
        this.enterFullscreen(camera);
      }
    },
    
    enterFullscreen(camera) {
      // Set the fullscreen camera first
      this.fullscreenCamera = camera;
      
      // Force Vue to update the DOM
      this.$forceUpdate();
      
      // Wait for the fullscreen overlay to be rendered before initializing
      this.$nextTick(() => {
        // Add an additional delay to ensure DOM is fully rendered
        setTimeout(() => {
          this.waitForRefsAndInitialize(camera);
        }, 300);
      });
    },
    
    waitForRefsAndInitialize(camera) {
      let attempts = 0;
      const maxAttempts = 10;
      
      const checkRefs = () => {
        attempts++;
        
        const videoRefA = this.$refs[`fullscreenVideoA-${camera.id}`];
        const videoRefB = this.$refs[`fullscreenVideoB-${camera.id}`];
        const overlayRef = this.$refs['fullscreen-overlay'];
        
        if (videoRefA && videoRefB && overlayRef) {
          this.initializeFullscreenContent(camera);
        } else if (attempts < maxAttempts) {
          setTimeout(checkRefs, 100);
        } else {
          this.initializeFullscreenContent(camera);
        }
      };
      
      checkRefs();
    },
    
    async initializeFullscreenContent(camera) {
      if (camera.recordingUrl) {
        const success = await this.initializeFullscreenVideo(camera);
        
        if (!success) {
          // Retry after a short delay if video initialization failed
          setTimeout(async () => {
            if (this.fullscreenCamera && this.fullscreenCamera.id === camera.id) {
              await this.initializeFullscreenVideo(camera);
            }
          }, 500);
        }
      } else {
        const success = this.initializeFullscreenImage(camera);
        
        if (!success) {
          // Retry after a short delay if image initialization failed
          setTimeout(() => {
            if (this.fullscreenCamera && this.fullscreenCamera.id === camera.id) {
              this.initializeFullscreenImage(camera);
            }
          }, 500);
        }
      }
    },
    
    exitFullscreen() {
      if (this.fullscreenCamera) {
        const exitingCamera = this.fullscreenCamera;
        
        // Clear fullscreen state
        exitingCamera.fullscreen = false;
        this.fullscreenCamera = null;
        
        // Force refresh the regular camera feed after exiting fullscreen
        this.$nextTick(() => {
          // Force re-initialize the regular video element
          if (exitingCamera.recordingUrl) {
            this.initializeVideo(exitingCamera);
          } else if (exitingCamera.snapshotUrl) {
            this.initializeImage(exitingCamera);
          }
          
          // Get the current recording timestamp from the exiting camera to sync all cameras
          const syncTimestamp = exitingCamera.recordingTimestamp;
          
          // Refresh all cameras and sync them to the same time
          setTimeout(async () => {
            // First, refresh all buffers
            for (const camera of this.cameras) {
              if (camera.recordingUrl) {
                await this.refreshBufferForCamera(camera);
              }
            }
            
            // Then sync all cameras to the same timestamp
            for (const camera of this.cameras) {
              if (camera.recordingUrl) {
                const bufferManager = this.bufferManagers.get(camera.id);
                if (bufferManager && bufferManager.recordings.length > 0) {
                  // Find the recording that's closest to the sync timestamp
                  let closestRecording = bufferManager.recordings[0];
                  let minTimeDiff = Math.abs(closestRecording.start_time - syncTimestamp);
                  
                  for (const recording of bufferManager.recordings) {
                    const timeDiff = Math.abs(recording.start_time - syncTimestamp);
                    if (timeDiff < minTimeDiff) {
                      minTimeDiff = timeDiff;
                      closestRecording = recording;
                    }
                  }
                  
                  // Only sync if the time difference is reasonable (within 10 seconds)
                  if (closestRecording && minTimeDiff <= 10) {
                    camera.recordingUrl = apiService.getRecordingUrl(camera.id, closestRecording.file_path);
                    camera.recordingTimestamp = closestRecording.start_time;
                    
                    // Re-initialize the video with the new recording
                    this.$nextTick(() => {
                      this.initializeVideo(camera);
                    });
                  }
                }
              }
            }
            
            // Temporarily disable buffer refresh to prevent drift
            this.stopBufferRefresh();
            
            // Re-enable buffer refresh after 5 seconds to allow cameras to stabilize
            setTimeout(() => {
              if (this.autoRefreshEnabled) {
                this.startAutoRefresh();
              }
            }, 5000);
          }, 100);
        });
      }
    },
    
    async retryCamera(camera) {
      camera.loading = true;
      camera.error = null;
      
      if (camera.recordingUrl) {
        // Retry recording video
        this.initializeVideo(camera);
      } else {
        // Retry image
        const imageElement = this.$refs[`image-${camera.id}`];
        if (imageElement && imageElement[0]) {
          const img = imageElement[0];
          try {
            await img.decode();
          } catch (error) {
            camera.error = 'Failed to reload camera feed';
          }
        }
      }
    },
    
    toggleFullscreen() {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
        this.isFullscreen = true;
      } else {
        document.exitFullscreen();
        this.isFullscreen = false;
      }
    },
    
    formatTimestamp(timestamp) {
      if (!timestamp) return '';
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'America/Chicago'
      });
    },
    
    formatRecordingTime(timestamp) {
      if (!timestamp) return '';
      const date = new Date(timestamp * 1000); // Convert Unix timestamp to milliseconds
      const now = new Date();
      const diffMs = now - date;
      const diffMinutes = Math.floor(diffMs / (1000 * 60));
      
      if (diffMinutes < 1) return 'Now';
      if (diffMinutes < 60) return `${diffMinutes}m ago`;
      
      const diffHours = Math.floor(diffMinutes / 60);
      if (diffHours < 24) return `${diffHours}h ago`;
      
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    },

    handleCanPlay(camera, idx) {
      camera.loading = false;
      camera.error = null;
    },

    // HLS.js player setup/cleanup
    initAllHlsPlayers() {
      this.cameras.forEach(camera => {
        if (camera.hlsUrl) {
          this.initHlsPlayer(camera);
        } else {
          this.cleanupHlsPlayer(camera);
        }
      });
    },
    initHlsPlayer(camera) {
      console.log(`Initializing HLS player for ${camera.id}`);
      const videoRef = this.$refs[`hlsVideo-${camera.id}`];
      console.log(`HLS video ref for ${camera.id}:`, !!videoRef, videoRef);
      
      if (!videoRef || !videoRef[0]) {
        console.error(`HLS video element not found for ${camera.id}`);
        return;
      }
      
      const video = videoRef[0];
      console.log(`HLS video element for ${camera.id}:`, video);
      
      // Clean up any existing hls.js instance
      this.cleanupHlsPlayer(camera);
      
      if (Hls.isSupported()) {
        console.log(`HLS.js is supported, creating player for ${camera.id}`);
        const hls = new Hls();
        
        // Add event listeners to debug HLS loading
        hls.on(Hls.Events.MANIFEST_LOADED, () => {
          console.log(`HLS manifest loaded for ${camera.id}`);
        });
        
        hls.on(Hls.Events.LEVEL_LOADED, () => {
          console.log(`HLS level loaded for ${camera.id}`);
        });
        
        hls.on(Hls.Events.ERROR, (event, data) => {
          console.error(`HLS error for ${camera.id}:`, data);
        });
        
        hls.on(Hls.Events.MEDIA_ATTACHED, () => {
          console.log(`HLS media attached for ${camera.id}`);
        });
        
        console.log(`Loading HLS source for ${camera.id}: ${camera.hlsUrl}`);
        hls.loadSource(camera.hlsUrl);
        hls.attachMedia(video);
        this.hlsPlayers[camera.id] = hls;
        console.log(`HLS player created for ${camera.id}`);
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        console.log(`Native HLS support detected for ${camera.id}`);
        video.src = camera.hlsUrl;
      } else {
        console.error(`HLS not supported for ${camera.id}`);
      }
    },
    cleanupHlsPlayer(camera) {
      const hls = this.hlsPlayers[camera.id];
      if (hls) {
        hls.destroy();
        delete this.hlsPlayers[camera.id];
      }
      const videoRef = this.$refs[`hlsVideo-${camera.id}`];
      if (videoRef && videoRef[0]) {
        videoRef[0].src = '';
      }
    },
    cleanupAllHlsPlayers() {
      Object.keys(this.hlsPlayers).forEach(id => {
        this.hlsPlayers[id].destroy();
      });
      this.hlsPlayers = {};
    }
  }
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