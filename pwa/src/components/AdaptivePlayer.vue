<template>
  <div class="adaptive-player relative">
    <video
      ref="videoElement"
      class="w-full h-full object-cover select-none touch-manipulation"
      :class="{ 
        'hidden': error,
        'cursor-pointer': !isIOS,
        'active:scale-95 transition-transform duration-150': isIOS,
        'ios-video': isIOS && isPWA
      }"
      :muted="isIOS ? (!isPWA) : true"
      playsinline
      webkit-playsinline
      :controls="true"
      :preload="isPWA ? 'metadata' : 'none'"
      :autoplay="false"
      :disablePictureInPicture="isIOS"
      x5-video-player-type="h5"
      x5-video-orientation="portrait"
      crossorigin="anonymous"
      @loadstart="handleLoadStart"
      @loadedmetadata="handleLoadedMetadata"
      @canplay="handleCanPlay"
      @canplaythrough="handleCanPlayThrough"
      @waiting="handleWaiting"
      @playing="handlePlaying"
      @error="handleError"
      @click="handleVideoClick"
      @touchstart="handleTouchStart"
      @touchend="handleTouchEnd"
      @progress="handleProgress"
      @stalled="handleStalled"
    ></video>
    
    <!-- Loading Overlay -->
    <div 
      v-if="loading" 
      class="absolute inset-0 bg-base-300 bg-opacity-75 flex items-center justify-center"
    >
      <span class="loading loading-spinner loading-lg text-primary"></span>
      <div class="ml-2 text-sm">
                 <div>Loading {{ currentFormat?.toUpperCase() || 'ADAPTIVE' }} stream...</div>
         <div class="text-xs opacity-70">{{ streamDescription }}</div>
      </div>
    </div>
    
    <!-- Error Overlay with Format Info -->
    <div 
      v-if="error" 
      class="absolute inset-0 bg-base-300 bg-opacity-75 flex flex-col items-center justify-center p-4"
    >
      <svg class="w-12 h-12 text-error mb-2" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01M21 12A9 9 0 113 12a9 9 0 0118 0z"/>
      </svg>
             <p class="text-error text-sm text-center mb-2">{{ error }}</p>
       <p class="text-xs opacity-70 mb-2">Format: {{ currentFormat?.toUpperCase() || 'UNKNOWN' }}</p>
      <div class="flex gap-2">
        <button 
          @click="retry" 
          class="btn btn-sm btn-outline"
        >
          Retry
        </button>
                 <button 
           v-if="canSwitchFormat" 
           @click="switchFormat" 
           class="btn btn-sm btn-primary"
         >
           Try {{ alternateFormat?.toUpperCase() || 'OTHER' }}
         </button>
      </div>
    </div>
    
    <!-- Format Badge -->
    <!-- Removed format badge for a cleaner look -->
  </div>
</template>

<script>
import apiService from '@/services/api.js';
import Hls from 'hls.js';

export default {
  name: 'AdaptivePlayer',
  props: {
    camera: {
      type: Object,
      required: true
    }
  },
  
  data() {
    return {
      loading: false,
      error: null,
      playing: false,
      currentFormat: 'hls', // Start with HLS since we have FFmpeg generating it
      isIOS: false,
      iosVersion: 0,
      isSafari: false,
      isPWA: false,
      supportsAdvancedFeatures: false,
      hasNativeHLS: false,
      canSwitchFormat: true,
      retryCount: 0,
      maxRetries: 3,
      hls: null, // HLS.js instance
      touchStartTime: null,
      touchStartPos: null
    };
  },
  
  computed: {
    streamDescription() {
      if (this.currentFormat === 'hls') {
        if (this.hasNativeHLS) {
          return 'Native HLS streaming';
        } else {
          return 'HLS.js adaptive streaming';
        }
      } else if (this.currentFormat === 'mp4') {
        return 'Direct H.264 stream';
      } else {
        return 'Adaptive streaming';
      }
    },
    
    alternateFormat() {
      if (this.currentFormat === 'hls') {
        return 'mp4';
      } else if (this.currentFormat === 'mp4') {
        return 'hls';
      } else {
        return 'hls'; // Default to HLS as alternate
      }
    },
    
    currentStreamUrl() {
      if (!this.camera) return null;
      
      const token = localStorage.getItem('auth_token');
      if (!token) return null;
      
      const baseUrl = this.currentFormat === 'hls' ? this.camera.hls_url : this.camera.mp4_url;
      return `${baseUrl}?token=${encodeURIComponent(token)}&t=${Date.now()}`;
    }
  },
  
  created() {
    this.detectDevice();
  },
  
  async mounted() {
    await this.initializeStream();
  },
  
  beforeUnmount() {
    this.cleanup();
  },
  
  methods: {
    detectDevice() {
      const userAgent = navigator.userAgent.toLowerCase();
      const platform = navigator.platform || '';
      
      // Enhanced iOS 18.5+ detection
      this.isIOS = this.detectiOS(userAgent, platform);
      this.iosVersion = this.detectiOSVersion(userAgent);
      this.isSafari = this.detectSafari(userAgent);
      this.isPWA = this.detectPWA();
      
      // Advanced HLS capability detection
      const video = document.createElement('video');
      this.hasNativeHLS = this.testNativeHLS(video);
      
      // iOS 18.5+ specific optimizations
      this.supportsAdvancedFeatures = this.iosVersion >= 18.5;
      
      // Default to HLS with iOS-optimized settings
      this.currentFormat = 'hls';
      
      console.log(`Device: ${this.getDeviceInfo()}, Format: ${this.currentFormat.toUpperCase()}`);
    },

    detectiOS(userAgent, platform) {
      // Comprehensive iOS detection for iOS 18.5+
      const iosRegex = /iphone|ipad|ipod/;
      const macTouchDevice = platform === 'MacIntel' && navigator.maxTouchPoints > 1;
      const visionOSDevice = /vision\s?os/i.test(userAgent);
      
      return iosRegex.test(userAgent) || macTouchDevice || visionOSDevice;
    },

    detectiOSVersion(userAgent) {
      // Extract iOS version for iOS 18.5+ feature detection
      const match = userAgent.match(/os (\d+)_(\d+)/i);
      if (match) {
        return parseFloat(`${match[1]}.${match[2]}`);
      }
      
      // Safari version mapping for iOS version detection
      const safariMatch = userAgent.match(/version\/(\d+)\.(\d+)/i);
      if (safariMatch && this.isIOS) {
        const safariVersion = parseFloat(`${safariMatch[1]}.${safariMatch[2]}`);
        // Safari 17.0+ generally corresponds to iOS 17.0+
        return safariVersion >= 17 ? safariVersion + 1 : safariVersion;
      }
      
      return 0;
    },

    detectSafari(userAgent) {
      return /safari/i.test(userAgent) && !/chrome|chromium|edge/i.test(userAgent);
    },

    detectPWA() {
      // Detect if running as PWA (added to home screen)
      return window.matchMedia('(display-mode: standalone)').matches ||
             window.navigator.standalone === true ||
             document.referrer.includes('android-app://');
    },

    testNativeHLS(video) {
      // Enhanced HLS support detection for iOS 18.5+
      const hlsTypes = [
        'application/vnd.apple.mpegurl',
        'application/x-mpegURL',
        'video/mp4; codecs="avc1.640028"',
        'video/mp4; codecs="avc1.42E01E"'
      ];
      
      return hlsTypes.some(type => video.canPlayType(type) !== '');
    },

    getDeviceInfo() {
      const device = this.isIOS ? 'iOS' : 'Desktop';
      const version = this.iosVersion > 0 ? ` ${this.iosVersion}` : '';
      const safari = this.isSafari ? ' Safari' : '';
      const pwa = this.isPWA ? ' PWA' : '';
      const advanced = this.supportsAdvancedFeatures ? ' (Advanced)' : '';
      
      return `${device}${version}${safari}${pwa}${advanced}, Native HLS: ${this.hasNativeHLS}, HLS.js: ${Hls.isSupported()}`;
    },
    
    async initializeStream() {
      if (!this.camera || !this.currentStreamUrl) {
        this.error = 'Camera configuration missing';
        return;
      }
      
      this.loading = true;
      this.error = null;
      this.retryCount = 0;
      
      try {
        await this.loadStream();
      } catch (error) {
        console.error('Failed to initialize stream:', error);
        this.handleStreamError('Failed to initialize stream');
      }
    },
    
    async loadStream() {
      const video = this.$refs.videoElement;
      if (!video) return;
      
      console.log(`Loading ${this.currentFormat.toUpperCase()} stream:`, this.currentStreamUrl);
      console.log('hasNativeHLS:', this.hasNativeHLS, 'Hls.isSupported:', Hls.isSupported(), 'isIOS:', this.isIOS, 'UserAgent:', navigator.userAgent);
      
      // Clean up any existing HLS instance
      this.destroyHls();
      
      // Configure video element based on platform
      if (this.isIOS) {
        this.configureVideoForIOS(video);
      } else {
        this.configureVideoForPC(video);
      }
      
      if (this.currentFormat === 'hls') {
        // Force HLS.js for all non-iOS browsers
        if (!this.isIOS && Hls.isSupported()) {
          console.log('Using HLS.js for HLS playback (forced for desktop)');
          this.hls = new Hls(this.getHLSConfig());
          this.hls.loadSource(this.currentStreamUrl);
          this.hls.attachMedia(video);
          this.setupHLSEventHandlers();
        } else if (this.hasNativeHLS) {
          // Use native HLS support (Safari, iOS)
          console.log('Using native HLS support');
          video.src = this.currentStreamUrl;
          video.load();
        } else {
          this.handleStreamError('HLS not supported by this browser');
          return;
        }
      } else {
        // MP4 Stream Handling
        console.log('Using direct MP4 streaming');
        video.src = this.currentStreamUrl;
        video.load();
      }
      
      // iOS-aware timeout (longer for mobile)
      const timeoutDuration = this.isIOS ? 20000 : 15000;
      const loadTimeout = setTimeout(() => {
        if (this.loading) {
          this.handleStreamError('Stream loading timeout');
        }
      }, timeoutDuration);
      
      this.loadTimeout = loadTimeout;
    },

    configureVideoForIOS(video) {
      // iOS 18.5+ optimizations
      video.setAttribute('playsinline', 'true');
      video.setAttribute('webkit-playsinline', 'true');
      
      // Disable picture-in-picture for security cameras
      video.disablePictureInPicture = true;
      
      // iOS battery optimization
      video.preload = this.isPWA ? 'metadata' : 'none';
      
      // Advanced iOS features for 18.5+
      if (this.supportsAdvancedFeatures) {
        video.controlsList = 'nodownload nofullscreen noremoteplayback';
        
        // Enhanced autoplay handling for iOS 18.5+
        if (this.isPWA) {
          video.muted = false; // PWAs can autoplay with audio
          video.autoplay = true;
        } else {
          video.muted = true; // Browser requires muted autoplay
        }
      }
    },

    configureVideoForPC(video) {
      // PC browser specific optimizations
      video.controls = true; // Ensure controls are always visible
      video.preload = 'metadata'; // Preload metadata for better UX
      video.muted = true; // Required for autoplay in most browsers
      video.autoplay = false; // Manual play for better user control
      video.disablePictureInPicture = false; // Allow PIP on desktop
      
      // Remove mobile-specific attributes that might interfere
      video.removeAttribute('webkit-playsinline');
      video.removeAttribute('x5-video-player-type');
      video.removeAttribute('x5-video-orientation');
      
      console.log('Configured video for PC browser');
    },

    getHLSConfig() {
      const baseConfig = {
        debug: false,
        enableWorker: true,
        lowLatencyMode: false,
        backBufferLength: this.isIOS ? 30 : 90
      };

      // iOS 18.5+ specific HLS.js optimizations
      if (this.isIOS) {
        return {
          ...baseConfig,
          maxBufferLength: this.isPWA ? 60 : 30,
          maxMaxBufferLength: 120,
          liveSyncDurationCount: 3,
          liveMaxLatencyDurationCount: 10,
          enableWebVTT: false, // Disable WebVTT for security cameras
          enableCEA708Captions: false,
          // iOS battery optimizations
          progressive: false,
          preferManagedMediaSource: true
        };
      }

      return baseConfig;
    },

    setupHLSEventHandlers() {
      if (!this.hls) return;

      this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log('HLS manifest parsed successfully');
        
        // iOS 18.5+ post-manifest optimizations
        if (this.supportsAdvancedFeatures) {
          this.optimizeQualityForDevice();
        }
      });
      
      this.hls.on(Hls.Events.ERROR, (event, data) => {
        console.error('HLS.js error:', event, data);
        
        // Enhanced error recovery for iOS
        if (data.fatal) {
          if (this.isIOS && data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            console.log('Attempting iOS-specific media error recovery');
            this.hls.recoverMediaError();
            return;
          }
          this.handleStreamError(`HLS Error: ${data.details}`);
        }
      });

      // iOS-specific events
      if (this.isIOS) {
        this.hls.on(Hls.Events.BUFFER_STALLED, () => {
          console.log('Buffer stalled on iOS - attempting recovery');
        });
      }
    },

    optimizeQualityForDevice() {
      if (!this.hls || !this.isIOS) return;

      // Detect device performance tier for iOS 18.5+
      const performanceTier = this.detectPerformanceTier();
      
      // Set appropriate quality level
      if (performanceTier === 'high') {
        this.hls.currentLevel = -1; // Auto quality
      } else if (performanceTier === 'medium') {
        this.hls.currentLevel = Math.min(1, this.hls.levels.length - 1);
      } else {
        this.hls.currentLevel = 0; // Lowest quality
      }
    },

    detectPerformanceTier() {
      // iOS device performance detection
      const memory = navigator.deviceMemory || 4;
      const cores = navigator.hardwareConcurrency || 2;
      
      if (memory >= 6 && cores >= 6) return 'high';
      if (memory >= 4 && cores >= 4) return 'medium';
      return 'low';
    },
    
    async switchFormat() {
      console.log(`Switching from ${this.currentFormat} to ${this.alternateFormat}`);
      
      this.currentFormat = this.alternateFormat;
      this.retryCount = 0;
      
      await this.loadStream();
    },
    
    async retry() {
      if (this.retryCount >= this.maxRetries) {
        this.error = 'Max retries exceeded. Please refresh the page.';
        return;
      }
      
      this.retryCount++;
      console.log(`Retrying stream (attempt ${this.retryCount}/${this.maxRetries})`);
      
      this.error = null;
      await this.loadStream();
    },
    
    cleanup() {
      const video = this.$refs.videoElement;
      if (video) {
        video.pause();
        video.src = '';
        video.load();
      }
      
      this.destroyHls();
      
      if (this.loadTimeout) {
        clearTimeout(this.loadTimeout);
      }
    },
    
    destroyHls() {
      if (this.hls) {
        console.log('Destroying HLS.js instance');
        this.hls.destroy();
        this.hls = null;
      }
    },
    
    // Video event handlers
    handleLoadStart() {
      console.log(`${this.currentFormat.toUpperCase()} stream load started`);
      this.loading = true;
      this.error = null;
      
      if (this.loadTimeout) {
        clearTimeout(this.loadTimeout);
      }
    },
    
    handleLoadedMetadata() {
      console.log(`${this.currentFormat.toUpperCase()} metadata loaded`);
      this.loading = false;
    },
    
    handleCanPlay() {
      console.log(`${this.currentFormat.toUpperCase()} stream can play`);
      this.loading = false;
      this.error = null;
      this.$emit('stream-ready');
    },
    
    handleCanPlayThrough() {
      console.log(`${this.currentFormat.toUpperCase()} stream can play through`);
      this.loading = false;
    },
    
    handleWaiting() {
      console.log(`${this.currentFormat.toUpperCase()} stream waiting for data`);
      // Don't show loading for brief waits
    },
    
    handlePlaying() {
      console.log(`${this.currentFormat.toUpperCase()} stream playing`);
      this.loading = false;
      this.playing = true;
      this.$emit('stream-playing');
    },
    
    handleError(event) {
      console.error(`${this.currentFormat.toUpperCase()} stream error:`, event);
      
      const video = this.$refs.videoElement;
      const error = video?.error;
      
      let errorMessage = 'Stream failed to load';
      if (error) {
        switch (error.code) {
          case error.MEDIA_ERR_ABORTED:
            errorMessage = 'Stream loading was aborted';
            break;
          case error.MEDIA_ERR_NETWORK:
            errorMessage = 'Network error occurred';
            break;
          case error.MEDIA_ERR_DECODE:
            errorMessage = 'Stream decode error';
            break;
          case error.MEDIA_ERR_SRC_NOT_SUPPORTED:
            errorMessage = 'Stream format not supported';
            break;
          default:
            errorMessage = `Stream error (code: ${error.code})`;
        }
      }
      
      this.handleStreamError(errorMessage);
    },
    
    handleStreamError(message) {
      this.loading = false;
      this.playing = false;
      this.error = message;
      
      if (this.loadTimeout) {
        clearTimeout(this.loadTimeout);
      }
      
      this.$emit('stream-error', { format: this.currentFormat, error: message });
      
      console.error(`${this.currentFormat.toUpperCase()} stream failed:`, message);
    },
    
    handleClick() {
      this.$emit('click');
    },
    
    handleProgress() {
      // Video is loading data
    },
    
    handleStalled() {
      console.warn(`${this.currentFormat.toUpperCase()} stream stalled`);
    },
    
    // Public methods
    async playVideo() {
      const video = this.$refs.videoElement;
      if (video) {
        try {
          await video.play();
          return true;
        } catch (error) {
          console.error('Play failed:', error);
          this.handleStreamError('Failed to start playback');
          return false;
        }
      }
      return false;
    },
    
    pauseVideo() {
      const video = this.$refs.videoElement;
      if (video) {
        video.pause();
      }
    },

    // iOS 18.5+ Touch Handlers
    handleVideoClick(event) {
      // Enhanced click handling for iOS
      if (this.isIOS) {
        event.preventDefault();
        this.handleIOSVideoInteraction(event);
      } else {
        this.$emit('click', event);
      }
    },

    handleTouchStart(event) {
      if (!this.isIOS) return;
      
      this.touchStartTime = Date.now();
      this.touchStartPos = {
        x: event.touches[0].clientX,
        y: event.touches[0].clientY
      };
    },

    handleTouchEnd(event) {
      if (!this.isIOS || !this.touchStartTime) return;
      
      const touchDuration = Date.now() - this.touchStartTime;
      const touch = event.changedTouches[0];
      const touchDistance = Math.sqrt(
        Math.pow(touch.clientX - this.touchStartPos.x, 2) + 
        Math.pow(touch.clientY - this.touchStartPos.y, 2)
      );
      
      // Detect tap vs drag
      if (touchDuration < 500 && touchDistance < 10) {
        this.handleIOSVideoInteraction(event);
      }
      
      this.touchStartTime = null;
      this.touchStartPos = null;
    },

    handleIOSVideoInteraction(event) {
      const video = this.$refs.videoElement;
      if (!video) return;
      
      // iOS 18.5+ enhanced video interaction
      if (video.paused) {
        // Attempt to play
        video.play().catch(error => {
          console.log('iOS autoplay prevented:', error);
          
          // Show user-friendly play prompt for iOS
          if (this.supportsAdvancedFeatures) {
            this.showIOSPlayPrompt();
          }
        });
      } else {
        // Toggle controls or emit click
        if (this.isPWA) {
          video.controls = !video.controls;
        } else {
          this.$emit('click', event);
        }
      }
    },

    showIOSPlayPrompt() {
      // Show a native-like iOS play prompt
      this.$emit('show-play-prompt', {
        message: 'Tap to play video',
        camera: this.camera
      });
    }
  }
};
</script>

<style scoped>
.adaptive-player {
  position: relative;
  width: 100%;
  height: 100%;
  background-color: #1a1a1a;
}

video {
  background-color: #1a1a1a;
}

/* iOS 18.5+ Specific Styles */
.ios-video {
  /* Enhanced video rendering on iOS PWAs */
  -webkit-transform: translateZ(0);
  transform: translateZ(0);
  -webkit-backface-visibility: hidden;
  backface-visibility: hidden;
}

/* Touch interaction optimizations for iOS */
@supports (-webkit-touch-callout: none) {
  video {
    -webkit-touch-callout: none;
    -webkit-user-select: none;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
  }
  
  .adaptive-player {
    -webkit-tap-highlight-color: transparent;
    touch-action: manipulation;
  }
}

/* PWA-specific enhancements */
@media (display-mode: standalone) {
  .adaptive-player {
    /* Better fullscreen experience */
    background-color: #000;
  }
  
  video {
    /* Improve video quality in PWA mode */
    image-rendering: -webkit-optimize-contrast;
    image-rendering: crisp-edges;
  }
}

/* iPhone specific optimizations */
@media screen and (max-device-width: 430px) {
  video {
    /* Battery optimization for smaller iPhones */
    will-change: auto;
  }
}

/* iOS Safari safe area support */
.adaptive-player {
  padding: env(safe-area-inset-top) env(safe-area-inset-right) env(safe-area-inset-bottom) env(safe-area-inset-left);
}

/* Ensure video fills container properly */
video::-webkit-media-controls-fullscreen-button {
  display: none;
}

video::-webkit-media-controls-picture-in-picture-button {
  display: none;
}
</style> 