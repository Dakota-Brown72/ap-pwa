// API service for communicating with Flask backend
// Use relative URL to work with Vite proxy for network access
const API_BASE_URL = '/api';

class ApiService {
  constructor() {
    this.token = localStorage.getItem('auth_token');
  }

  setToken(token) {
    this.token = token;
    localStorage.setItem('auth_token', token);
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('auth_token');
  }

  async request(endpoint, options = {}) {
    const url = `${API_BASE_URL}${endpoint}`;
    const config = {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
      ...options,
    };

    if (this.token) {
      config.headers.Authorization = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, config);
      
      if (!response.ok) {
        // Try to get error details from response
        let errorData = null;
        try {
          errorData = await response.json();
        } catch (e) {
          // Response is not JSON
        }

        if (response.status === 401) {
          // Token expired or invalid (but not for login endpoint)
          if (endpoint !== '/auth/login') {
            this.clearToken();
            // Redirect to login page
            if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
              window.location.href = '/login';
            }
            throw new Error('Authentication required');
          }
        }
        
        // Create enhanced error with response data
        const error = new Error(errorData?.error || `API request failed: ${response.status}`);
        error.status = response.status;
        error.data = errorData;
        throw error;
      }

      // Handle different response types
      const contentType = response.headers.get('Content-Type');
      if (contentType && contentType.includes('image/')) {
        return response; // Return the response object for blob handling
      } else {
        return await response.json();
      }
    } catch (error) {
      console.error('API request error:', error);
      throw error;
    }
  }

  // Authentication
  async login(username, password) {
    const response = await this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    });
    
    if (response.token) {
      this.setToken(response.token);
    }
    
    return response;
  }

  async logout() {
    await this.request('/auth/logout', { method: 'POST' });
    this.clearToken();
  }

  // User
  async getCurrentUser() {
    return this.request('/auth/me');
  }

  async changeUsername(currentUsername, newUsername, confirmUsername) {
    return this.request('/auth/change-username', {
      method: 'POST',
      body: JSON.stringify({
        current_username: currentUsername,
        new_username: newUsername,
        confirm_username: confirmUsername,
      }),
    });
  }

  async changePassword(currentPassword, newPassword, confirmPassword) {
    return this.request('/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      }),
    });
  }

  // Admin
  async createUser(username, password, isAdmin = false) {
    return this.request('/admin/users', {
      method: 'POST',
      body: JSON.stringify({ username, password, is_admin: !!isAdmin }),
    });
  }

  async listUsers() {
    return this.request('/admin/users');
  }

  async toggleUserActive(userId, isActive) {
    return this.request(`/admin/users/${userId}/active`, {
      method: 'POST',
      body: JSON.stringify({ is_active: !!isActive })
    });
  }

  // Cameras
  async getCameras() {
    return this.request('/cameras');
  }

  // Public endpoint that doesn't require authentication
  async getPublicCameras() {
    const url = `${API_BASE_URL}/public/cameras`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        throw new Error(`API request failed: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('API request error:', error);
      throw error;
    }
  }

  // Optimized streaming endpoints for hardware-accelerated on-demand streams
  async getCameraStream(cameraId, streamType = 'hls') {
    // Get optimized stream URL for a camera with hardware acceleration
    return await this.request(`/cameras/${cameraId}/stream/${streamType}`);
  }

  getCameraHlsUrl(cameraId) {
    // Get direct HLS URL for a camera (hardware-accelerated, on-demand)
    return `/api/cameras/${cameraId}/stream/hls`;
  }

  getCameraMseUrl(cameraId) {
    // Get direct MSE/MP4 URL for a camera (best browser compatibility)
    return `${API_BASE_URL}/cameras/${cameraId}/stream/mse`;
  }

  getDirectMp4Url(streamName) {
    // Get direct MP4 URL from go2rtc for mobile compatibility
    return `/api/go2rtc/stream.mp4?src=${streamName}`;
  }

  // Authenticated stream URLs
  getAuthenticatedMp4Url(cameraId) {
    // Get authenticated MP4 stream URL with token
    const token = this.token;
    if (!token) {
      throw new Error('No authentication token available');
    }
    return `/api/camera/${cameraId}/stream.mp4?token=${encodeURIComponent(token)}`;
  }

  getAuthenticatedHlsUrl(cameraId) {
    // Get authenticated HLS stream URL with token
    const token = this.token;
    if (!token) {
      throw new Error('No authentication token available');
    }
    return `/api/camera/${cameraId}/stream.m3u8?token=${encodeURIComponent(token)}`;
  }



  // Events
  async getEvents() {
    return await this.request('/events');
  }

  // Frigate API endpoints
  async getFrigateCameras() {
    return await this.request('/frigate/cameras');
  }

  async getFrigateRecordings(cameraName, before = null, after = null) {
    const params = new URLSearchParams();
    if (before) params.append('before', before);
    if (after) params.append('after', after);
    
    const query = params.toString();
    const url = `/frigate/recordings/${cameraName}${query ? `?${query}` : ''}`;
    return await this.request(url);
  }

  // Events (Phase 1 proxies)
  async getFrigateEvents(camera = null, before = null, after = null, limit = 100, zone = null, label = null) {
    const params = new URLSearchParams();
    if (camera) params.append('camera', camera);
    if (before) params.append('before', before);
    if (after) params.append('after', after);
    if (label) params.append('label', label);
    params.append('limit', limit.toString());
    if (zone) params.append('zone', zone);
    return await this.request(`/events?${params.toString()}`);
  }

  async getEventsSummary(zones = ['Driveway', 'Front_Door']) {
    const params = new URLSearchParams();
    if (zones && zones.length) params.append('zones', zones.join(','));
    return await this.request(`/events/summary?${params.toString()}`);
  }

  getEventClipUrl(eventId) {
    const token = this.token;
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${API_BASE_URL}/events/${eventId}/clip.mp4${qs}`;
  }

  getEventClipHlsUrl(eventId) {
    const token = this.token;
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${API_BASE_URL}/events/${eventId}/clip.m3u8${qs}`;
  }

  async deleteEventHls(eventId) {
    return await this.request(`/events/${eventId}/hls`, { method: 'DELETE' });
  }

  getEventSnapshotUrl(eventId) {
    const token = this.token;
    const qs = token ? `?token=${encodeURIComponent(token)}` : '';
    return `${API_BASE_URL}/events/${eventId}/snapshot.jpg${qs}`;
  }

  // Frigate Recordings API endpoints
  async getLatestRecording(cameraName, minAge = 2) {
    return await this.request(`/frigate/recordings/${cameraName}/latest?min_age=${minAge}`);
  }

  async getRecentRecordings(cameraName, count = 5, minAge = 2) {
    return await this.request(`/frigate/recordings/${cameraName}/recent?count=${count}&min_age=${minAge}`);
  }

  async getBufferedRecordings(cameraName, bufferSize = 6, minAge = 2) {
    return await this.request(`/frigate/recordings/${cameraName}/buffer?buffer_size=${bufferSize}&min_age=${minAge}`);
  }

  async listRecordings(cameraName, days = 1) {
    return await this.request(`/frigate/recordings/${cameraName}/list?days=${days}`);
  }

  getRecordingUrl(cameraName, recordingPath) {
    return `${API_BASE_URL}/frigate/recordings/${cameraName}/${recordingPath}`;
  }

  // System
  async getSystemStatus() {
    return await this.request('/system/status');
  }
}

export default new ApiService(); 