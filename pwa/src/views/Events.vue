<template>
  <div class="p-4 md:p-8 bg-base-200 min-h-screen">
    <div class="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-3">
      <div>
        <h1 class="text-3xl font-bold text-primary-content mb-1">Events</h1>
        <p class="text-base-content text-opacity-70">Review detections by zone and camera</p>
      </div>
      <div class="flex gap-2">
        <button class="btn btn-sm" @click="refresh" :disabled="loading">
          <span v-if="loading" class="loading loading-spinner loading-xs"></span>
          <span v-else>↻</span>
          Refresh
        </button>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Filters -->
      <div class="card bg-base-50 shadow-md rounded-xl">
        <div class="card-body p-4 space-y-3 text-base-content">
          <h2 class="card-title mb-2 text-base-content">Filters</h2>
          <div class="grid grid-cols-[80px_1fr] items-center gap-2">
            <label for="filter-camera" class="text-sm text-base-content">Camera</label>
            <select id="filter-camera" v-model="filters.camera" class="select select-bordered select-sm text-base-content w-full md:w-56">
              <option value="">All</option>
              <option v-for="c in cameras" :key="c" :value="c">{{ prettyText(c) }}</option>
            </select>
          </div>
          <div class="grid grid-cols-[80px_1fr] items-center gap-2">
            <label for="filter-zone" class="text-sm text-base-content">Zone</label>
            <select id="filter-zone" v-model="filters.zone" class="select select-bordered select-sm text-base-content w-full md:w-56">
              <option value="">All</option>
              <option v-for="z in zones" :key="z" :value="z">{{ prettyText(z) }}</option>
            </select>
          </div>
          <div class="grid grid-cols-[80px_1fr] items-center gap-2">
            <label for="filter-label" class="text-sm text-base-content">Label</label>
            <select id="filter-label" v-model="filters.label" class="select select-bordered select-sm text-base-content w-full md:w-56">
              <option value="">All</option>
              <option v-for="l in labels" :key="l" :value="l">{{ prettyText(l) }}</option>
            </select>
          </div>
          <button class="btn btn-primary btn-sm w-full" @click="refresh">Apply</button>
        </div>
      </div>

      <!-- Events list -->
      <div class="lg:col-span-2 card bg-base-100 shadow-md rounded-xl">
        <div class="card-body p-4 text-base-content">
          <div class="flex items-center justify-between mb-3">
            <h2 class="card-title">Results</h2>
            <div class="text-sm text-opacity-60">{{ events.length }} events</div>
          </div>
          <div class="overflow-y-auto max-h-[65vh] divide-y divide-base-200">
            <div v-for="ev in events" :key="ev.id" class="py-3 flex items-center gap-3">
              <div class="w-24 h-16 bg-base-300 rounded overflow-hidden flex items-center justify-center">
                <img v-if="thumbnails[ev.id]" :src="thumbnails[ev.id]" class="w-full h-full object-cover" />
                <span v-else class="text-xs text-opacity-60">No preview</span>
              </div>
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="badge badge-accent badge-sm min-w-[72px] justify-center">{{ prettyText(ev.label) }}</span>
                  <span class="badge badge-ghost badge-sm min-w-[72px] justify-center">{{ prettyText(ev.camera) }}</span>
                  <span v-for="z in ev.zones || []" :key="z" class="badge badge-outline badge-sm">{{ prettyText(z) }}</span>
                </div>
                <div class="text-sm truncate mt-1 tabular-nums text-opacity-80">
                  {{ formatWhen(ev.start_time) }}
                </div>
              </div>
              <div class="flex items-center gap-2">
                <button class="btn btn-xs btn-outline" @click="play(ev)">Play</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Drawer / modal for clip playback -->
    <dialog ref="playerModal" class="modal">
      <div class="modal-box max-w-4xl">
        <h3 class="font-bold text-lg mb-2">{{ current?.label }} • {{ current?.camera }} • {{ currentZoneText }}</h3>
        <video v-if="current" ref="player" class="w-full rounded" controls autoplay playsinline>
          <source v-if="!isIOS" :src="clipUrl" type="video/mp4" />
          <source v-else :src="clipUrlHls" type="application/vnd.apple.mpegurl" />
        </video>
        <div class="modal-action">
          <form method="dialog">
            <button class="btn" @click.prevent="closePlayer">Close</button>
          </form>
        </div>
      </div>
    </dialog>
  </div>
</template>

<script>
import api from '@/services/api.js'

export default {
  name: 'Events',
  data() {
    return {
      loading: false,
      cameras: [],
      zones: ['Driveway', 'Front_Door'],
      labels: ['person', 'car', 'truck', 'motorcycle', 'bicycle', 'bus'],
      filters: { camera: '', zone: '', label: '' },
      events: [],
      thumbnails: {},
      current: null,
    }
  },
  computed: {
    clipUrl() {
      return this.current ? api.getEventClipUrl(this.current.id) : ''
    },
    clipUrlHls() {
      return this.current ? api.getEventClipHlsUrl(this.current.id) : ''
    },
    isIOS() {
      if (typeof navigator === 'undefined') return false
      return /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
    },
    currentZoneText() {
      if (!this.current) return ''
      const zs = this.current.zones || []
      return zs.length ? zs.map(this.prettyText).join(', ') : 'No Zone'
    }
  },
  async mounted() {
    await this.bootstrap()
    await this.refresh()
    // Cleanup on route leave/unmount
    window.addEventListener('beforeunload', this.cleanupHls)
  },
  beforeUnmount() {
    window.removeEventListener('beforeunload', this.cleanupHls)
    this.cleanupHls()
  },
  methods: {
    prettyText(value) {
      if (!value || typeof value !== 'string') return value || '';
      const spaced = value.replace(/_/g, ' ');
      return spaced.replace(/\b\w/g, (c) => c.toUpperCase());
    },
    async bootstrap() {
      try {
        this.loading = true
        // cameras
        const cfg = await api.getFrigateCameras()
        this.cameras = Object.keys(cfg || {})
      } finally {
        this.loading = false
      }
    },
    async refresh() {
      this.loading = true
      try {
        const { camera, zone, label } = this.filters
        this.events = await api.getFrigateEvents(camera || null, null, null, 100, zone || null, label || null)
        // Load thumbnails
        this.thumbnails = {}
        for (const ev of this.events) {
          let url = api.getEventSnapshotUrl(ev.id)
          // Add cache buster to avoid stale
          url += (url.includes('?') ? '&' : '?') + `t=${Date.now()}`
          this.thumbnails[ev.id] = url
        }
      } catch (e) {
        console.error('Failed to load events', e)
        this.events = []
      } finally {
        this.loading = false
      }
    },
    formatWhen(ts) {
      if (!ts) return ''
      const d = new Date(ts * 1000)
      return d.toLocaleString()
    },
    play(ev) {
      this.current = ev
      if (this.$refs.playerModal) this.$refs.playerModal.showModal()
      // Force reload player element
      this.$nextTick(() => {
        if (this.$refs.player) {
          this.$refs.player.load()
        }
      })
    },
    async closePlayer() {
      try {
        await this.cleanupHls()
      } finally {
        if (this.$refs.playerModal) this.$refs.playerModal.close()
        this.current = null
      }
    },
    async cleanupHls() {
      try {
        if (this.current && this.current.id) {
          await api.deleteEventHls(this.current.id)
        }
      } catch (e) {
        // Non-fatal
      }
    }
  }
}
</script> 