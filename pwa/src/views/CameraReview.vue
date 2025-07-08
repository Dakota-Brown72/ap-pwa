<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <!-- Header -->
    <div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-2">Camera Review</h1>
        <p class="text-base-content text-opacity-70">Review recordings with event markers</p>
      </div>
      <div class="flex items-center gap-3">
        <select 
          v-model="selectedCamera" 
          @change="loadCameraData"
          class="select select-bordered select-sm"
        >
          <option value="">Select Camera</option>
          <option v-for="camera in cameras" :key="camera" :value="camera">
            {{ camera }}
          </option>
        </select>
        <button 
          @click="goLive" 
          class="btn btn-primary btn-sm"
          :disabled="!selectedCamera"
        >
          Go Live
        </button>
      </div>
    </div>

    <!-- Camera Selection Required -->
    <div v-if="!selectedCamera" class="text-center py-12">
      <svg class="w-16 h-16 text-base-content text-opacity-30 mx-auto mb-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M15 10l4.553-2.276A2 2 0 0021 6.382V5a2 2 0 00-2-2H5a2 2 0 00-2 2v1.382a2 2 0 001.447 1.342L9 10m6 0v10a2 2 0 01-2 2H7a2 2 0 01-2-2V10m6 0h6"/>
      </svg>
      <h3 class="text-lg font-semibold text-base-content mb-2">Select a Camera</h3>
      <p class="text-base-content text-opacity-70">Choose a camera to review recordings and events.</p>
    </div>

    <!-- Review Interface -->
    <div v-else class="space-y-6">
      <!-- Video Player -->
      <div class="bg-base-100 rounded-xl overflow-hidden shadow-lg">
        <div class="aspect-video relative">
          <video
            ref="videoPlayer"
            class="w-full h-full object-cover"
            controls
            @timeupdate="handleTimeUpdate"
            @loadedmetadata="handleVideoLoaded"
            @ended="handleVideoEnded"
          >
            <source :src="currentVideoSrc" type="video/mp4">
            Your browser does not support the video tag.
          </video>

          <!-- Loading Overlay -->
          <div 
            v-if="loading" 
            class="absolute inset-0 bg-base-300 bg-opacity-75 flex items-center justify-center"
          >
            <span class="loading loading-spinner loading-lg text-primary"></span>
          </div>

          <!-- Error Overlay -->
          <div 
            v-if="error" 
            class="absolute inset-0 bg-base-300 bg-opacity-75 flex flex-col items-center justify-center p-4"
          >
            <svg class="w-12 h-12 text-error mb-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z"/>
            </svg>
            <p class="text-error text-sm text-center">{{ error }}</p>
            <button 
              @click="loadCameraData" 
              class="btn btn-sm btn-outline mt-2"
            >
              Retry
            </button>
          </div>
        </div>
      </div>

      <!-- Timeline -->
      <div class="bg-base-100 rounded-xl p-4 shadow-lg">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-lg font-semibold">Timeline</h3>
          <div class="flex items-center gap-2 text-sm text-base-content text-opacity-70">
            <span>{{ formatTimestamp(currentTime) }}</span>
            <span>/</span>
            <span>{{ formatTimestamp(totalDuration) }}</span>
          </div>
        </div>

        <!-- Timeline Slider -->
        <div class="relative mb-4">
          <input
            type="range"
            v-model="timelinePosition"
            min="0"
            max="100"
            step="0.1"
            class="range range-primary w-full"
            @input="handleTimelineChange"
          />
          
          <!-- Event Markers -->
          <div class="absolute top-0 left-0 right-0 h-2 pointer-events-none">
            <div
              v-for="event in visibleEvents"
              :key="event.id"
              class="absolute h-full bg-warning rounded-sm opacity-75"
              :style="{
                left: `${getEventPosition(event)}%`,
                width: `${getEventWidth(event)}%`
              }"
              :title="`${event.label} at ${formatTimestamp(event.start_time)}`"
            ></div>
          </div>
        </div>

        <!-- Event List -->
        <div class="max-h-48 overflow-y-auto">
          <div 
            v-for="event in events" 
            :key="event.id"
            class="flex items-center gap-3 p-2 hover:bg-base-200 rounded cursor-pointer"
            @click="seekToEvent(event)"
          >
            <div class="w-3 h-3 rounded-full bg-warning"></div>
            <div class="flex-1">
              <div class="font-medium">{{ event.label }}</div>
              <div class="text-sm text-base-content text-opacity-70">
                {{ formatTimestamp(event.start_time) }} - {{ formatTimestamp(event.end_time) }}
              </div>
            </div>
            <div class="text-xs text-base-content text-opacity-50">
              {{ Math.round(event.score * 100) }}%
            </div>
          </div>
        </div>
      </div>

      <!-- Recording Segments -->
      <div class="bg-base-100 rounded-xl p-4 shadow-lg">
        <h3 class="text-lg font-semibold mb-4">Recording Segments</h3>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div 
            v-for="recording in recordings" 
            :key="recording.start_time"
            class="p-3 border border-base-300 rounded-lg cursor-pointer hover:bg-base-200"
            @click="playRecording(recording)"
          >
            <div class="text-sm font-medium">{{ formatTimestamp(recording.start_time) }}</div>
            <div class="text-xs text-base-content text-opacity-70">
              Duration: {{ formatDuration(recording.end_time - recording.start_time) }}
            </div>
            <div class="text-xs text-base-content text-opacity-50">
              Size: {{ formatFileSize(recording.file_size) }}
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
  name: 'CameraReview',
  data() {
    return {
      cameras: [],
      selectedCamera: '',
      events: [],
      recordings: [],
      currentVideoSrc: '',
      currentTime: 0,
      totalDuration: 0,
      timelinePosition: 0,
      loading: false,
      error: null,
      currentEventIndex: 0
    };
  },
  
  computed: {
    currentEvent() {
      return this.events[this.currentEventIndex] || null;
    },
    
    visibleEvents() {
      // Return events that are within the current video's time range
      if (!this.currentEvent) return [];
      
      const videoStart = this.currentEvent.start_time;
      const videoEnd = this.currentEvent.end_time;
      
      return this.events.filter(event => 
        event.start_time >= videoStart && event.end_time <= videoEnd
      );
    }
  },
  
  async mounted() {
    await this.loadCameras();
  },
  
  methods: {
    async loadCameras() {
      try {
        const response = await apiService.getFrigateCameras();
        this.cameras = Object.keys(response || {});
      } catch (error) {
        console.error('Failed to load cameras:', error);
        this.error = 'Failed to load cameras';
      }
    },
    
    async loadCameraData() {
      if (!this.selectedCamera) return;
      
      this.loading = true;
      this.error = null;
      
      try {
        // Load events
        const eventsResponse = await apiService.getFrigateEvents(this.selectedCamera);
        this.events = eventsResponse || [];
        
        // Sort events by start time (newest first)
        this.events.sort((a, b) => b.start_time - a.start_time);
        
        // Load recordings
        const recordingsResponse = await apiService.getFrigateRecordings(this.selectedCamera);
        this.recordings = recordingsResponse || [];
        
        // Sort recordings by start time (newest first)
        this.recordings.sort((a, b) => b.start_time - a.start_time);
        
        // Load the most recent event
        if (this.events.length > 0) {
          this.currentEventIndex = 0;
          await this.loadCurrentEvent();
        }
        
      } catch (error) {
        console.error('Failed to load camera data:', error);
        this.error = 'Failed to load camera data';
      } finally {
        this.loading = false;
      }
    },
    
    async loadCurrentEvent() {
      if (!this.events[this.currentEventIndex]) return;
      
      const event = this.events[this.currentEventIndex];
      this.currentVideoSrc = apiService.getFrigateEventClipUrl(event.id);
      
      // Wait for video to load
      await this.$nextTick();
      if (this.$refs.videoPlayer) {
        this.$refs.videoPlayer.load();
      }
    },
    
    async playEvent(event) {
      const index = this.events.findIndex(e => e.id === event.id);
      if (index !== -1) {
        this.currentEventIndex = index;
        await this.loadCurrentEvent();
      }
    },
    
    async playRecording(recording) {
      // For recordings, we need to construct a different URL
      // This would require additional backend support for recording files
      console.log('Playing recording:', recording);
      // TODO: Implement recording playback
    },
    
    async goLive() {
      if (this.events.length > 0) {
        this.currentEventIndex = 0;
        await this.loadCurrentEvent();
      }
    },
    
    handleTimeUpdate() {
      if (this.$refs.videoPlayer) {
        this.currentTime = this.$refs.videoPlayer.currentTime;
        this.updateTimelinePosition();
      }
    },
    
    handleVideoLoaded() {
      if (this.$refs.videoPlayer) {
        this.totalDuration = this.$refs.videoPlayer.duration;
        this.updateTimelinePosition();
      }
    },
    
    handleVideoEnded() {
      // Auto-play next event if available
      if (this.currentEventIndex < this.events.length - 1) {
        this.currentEventIndex++;
        this.loadCurrentEvent();
      }
    },
    
    handleTimelineChange() {
      if (this.$refs.videoPlayer) {
        const newTime = (this.timelinePosition / 100) * this.totalDuration;
        this.$refs.videoPlayer.currentTime = newTime;
      }
    },
    
    updateTimelinePosition() {
      if (this.totalDuration > 0) {
        this.timelinePosition = (this.currentTime / this.totalDuration) * 100;
      }
    },
    
    seekToEvent(event) {
      const index = this.events.findIndex(e => e.id === event.id);
      if (index !== -1) {
        this.currentEventIndex = index;
        this.loadCurrentEvent();
      }
    },
    
    getEventPosition(event) {
      if (!this.currentEvent || this.totalDuration === 0) return 0;
      
      // Calculate position relative to current video
      const eventStart = event.start_time;
      const videoStart = this.currentEvent.start_time;
      const relativeStart = eventStart - videoStart;
      
      return (relativeStart / this.totalDuration) * 100;
    },
    
    getEventWidth(event) {
      if (!this.currentEvent || this.totalDuration === 0) return 5;
      
      // Calculate width based on event duration
      const eventDuration = event.end_time - event.start_time;
      return (eventDuration / this.totalDuration) * 100;
    },
    
    formatTimestamp(timestamp) {
      if (!timestamp) return '--:--';
      const date = new Date(timestamp * 1000);
      return date.toLocaleTimeString();
    },
    
    formatDuration(seconds) {
      const mins = Math.floor(seconds / 60);
      const secs = Math.floor(seconds % 60);
      return `${mins}:${secs.toString().padStart(2, '0')}`;
    },
    
    formatFileSize(bytes) {
      if (!bytes) return '0 B';
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(1024));
      return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    }
  }
};
</script>

<style scoped>
.range {
  height: 8px;
}

.range::-webkit-slider-thumb {
  height: 20px;
  width: 20px;
}

.range::-moz-range-thumb {
  height: 20px;
  width: 20px;
}
</style> 