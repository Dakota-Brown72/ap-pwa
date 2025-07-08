// API service for communicating with Flask backend
const API_BASE_URL = 'http://localhost:5003/api';

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
        if (response.status === 401) {
          // Token expired or invalid
          this.clearToken();
          throw new Error('Authentication required');
        }
        throw new Error(`API request failed: ${response.status}`);
      }

      return await response.json();
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

  // Cameras
  async getCameras() {
    // Use public endpoint for now to avoid authentication issues
    return await this.request('/public/cameras');
  }

  async getSnapshots(refresh = false) {
    const url = refresh ? '/cameras/snapshots?refresh=true' : '/cameras/snapshots';
    return await this.request(url);
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

  async getFrigateEvents(camera = null, before = null, after = null, limit = 100) {
    const params = new URLSearchParams();
    if (camera) params.append('camera', camera);
    if (before) params.append('before', before);
    if (after) params.append('after', after);
    params.append('limit', limit.toString());
    
    const url = `/frigate/events?${params.toString()}`;
    return await this.request(url);
  }

  getFrigateEventClipUrl(eventId) {
    return `${API_BASE_URL}/frigate/events/${eventId}/clip.mp4`;
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