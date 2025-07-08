import cv2
import numpy as np
import base64
import os
import time
import threading
from datetime import datetime, timedelta
import requests
from io import BytesIO
from PIL import Image
import logging

logger = logging.getLogger(__name__)

class FrameCapture:
    def __init__(self, frigate_host="http://frigate:5000"):
        self.frigate_host = frigate_host
        self.cache_dir = "/tmp/frame_cache"
        self.cache_duration = 60  # Cache frames for 60 seconds
        self.frame_cache = {}  # In-memory cache
        
        # Create cache directory
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def get_local_time_str(self, dt=None):
        if dt is None:
            dt = datetime.now()
        local_time_str = dt.strftime('%b %-d, %Y, %-I:%M %p')
        tz_abbr = time.strftime('%Z')
        return f"{local_time_str} {tz_abbr}"

    def capture_frame_from_hls(self, camera_id, max_retries=3):
        """Capture a frame from Frigate snapshot endpoint"""
        snapshot_url = f"{self.frigate_host}/api/{camera_id}/latest.jpg"
        
        for attempt in range(max_retries):
            try:
                # Use requests to get the snapshot
                import requests
                
                response = requests.get(snapshot_url, timeout=10)
                response.raise_for_status()
                
                jpeg_data = response.content
                
                if not jpeg_data:
                    raise Exception("No image data received")
                
                # Convert to base64
                base64_data = base64.b64encode(jpeg_data).decode('utf-8')
                # Get local time string
                now = datetime.now()
                local_time_str = now.strftime('%b %-d, %Y, %-I:%M %p')
                tz_abbr = time.strftime('%Z')
                local_time_str = f"{local_time_str} {tz_abbr}"
                return {
                    'image': f"data:image/jpeg;base64,{base64_data}",
                    'timestamp': now.isoformat(),
                    'local_time': local_time_str,
                    'source': 'frigate_snapshot'
                }
                
            except Exception as e:
                logger.error(f"Attempt {attempt + 1} failed for camera {camera_id}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)  # Wait before retry
                else:
                    raise e
    
    def capture_frame_from_rtsp(self, camera_id, rtsp_url, max_retries=3):
        """Capture a frame from RTSP stream (fallback method)"""
        for attempt in range(max_retries):
            try:
                cap = cv2.VideoCapture(rtsp_url)
                
                if not cap.isOpened():
                    raise Exception(f"Could not open RTSP stream: {rtsp_url}")
                
                # Read a frame
                ret, frame = cap.read()
                cap.release()
                
                if not ret or frame is None:
                    raise Exception("Could not read frame from RTSP stream")
                
                # Convert to JPEG
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                jpeg_data = buffer.tobytes()
                
                # Convert to base64
                base64_data = base64.b64encode(jpeg_data).decode('utf-8')
                
                return {
                    'image': f"data:image/jpeg;base64,{base64_data}",
                    'timestamp': datetime.now().isoformat(),
                    'source': 'rtsp_stream'
                }
                
            except Exception as e:
                logger.error(f"RTSP attempt {attempt + 1} failed for camera {camera_id}: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    raise e
    
    def get_cached_frame(self, camera_id):
        """Get cached frame if it's still valid"""
        if camera_id in self.frame_cache:
            cached_data = self.frame_cache[camera_id]
            cached_time = datetime.fromisoformat(cached_data['timestamp'])
            
            if datetime.now() - cached_time < timedelta(seconds=self.cache_duration):
                return cached_data
        
        return None
    
    def cache_frame(self, camera_id, frame_data):
        """Cache frame data"""
        self.frame_cache[camera_id] = frame_data
        
        # Limit cache size
        if len(self.frame_cache) > 20:
            # Remove oldest entries
            oldest_key = min(self.frame_cache.keys(), 
                           key=lambda k: self.frame_cache[k]['timestamp'])
            del self.frame_cache[oldest_key]
    
    def capture_frame(self, camera_id, force_refresh=False):
        """Main method to capture frame with caching"""
        try:
            # Check cache first
            if not force_refresh:
                cached_frame = self.get_cached_frame(camera_id)
                if cached_frame:
                    # Add local_time if missing
                    if 'local_time' not in cached_frame:
                        cached_frame['local_time'] = self.get_local_time_str(datetime.fromisoformat(cached_frame['timestamp']))
                    logger.debug(f"[DEBUG] Returning cached_frame for {camera_id}: {cached_frame}")
                    return cached_frame
            # Try HLS stream first
            try:
                frame_data = self.capture_frame_from_hls(camera_id)
                frame_data['local_time'] = self.get_local_time_str(datetime.fromisoformat(frame_data['timestamp']))
                self.cache_frame(camera_id, frame_data)
                logger.debug(f"[DEBUG] Returning fresh HLS frame for {camera_id}: {frame_data}")
                return frame_data
            except Exception as hls_error:
                logger.error(f"HLS capture failed for {camera_id}: {str(hls_error)}")
                # Fallback: try to get RTSP URL from Frigate config
                try:
                    config_response = requests.get(f"{self.frigate_host}/api/config")
                    if config_response.status_code == 200:
                        config = config_response.json()
                        camera_config = config.get('cameras', {}).get(camera_id, {})
                        # Try to find RTSP URL in camera config
                        inputs = camera_config.get('ffmpeg', {}).get('inputs', [])
                        for input_config in inputs:
                            if 'path' in input_config and input_config['path'].startswith('rtsp://'):
                                rtsp_url = input_config['path']
                                frame_data = self.capture_frame_from_rtsp(camera_id, rtsp_url)
                                frame_data['local_time'] = self.get_local_time_str(datetime.fromisoformat(frame_data['timestamp']))
                                self.cache_frame(camera_id, frame_data)
                                logger.debug(f"[DEBUG] Returning fresh RTSP frame for {camera_id}: {frame_data}")
                                return frame_data
                except Exception as rtsp_error:
                    logger.error(f"RTSP fallback failed for {camera_id}: {str(rtsp_error)}")
                # If all else fails, return error
                now = datetime.now()
                error_frame = {
                    'error': f'Failed to capture frame: {str(hls_error)}',
                    'timestamp': now.isoformat(),
                    'local_time': self.get_local_time_str(now),
                    'source': 'error'
                }
                logger.debug(f"[DEBUG] Returning error frame for {camera_id}: {error_frame}")
                return error_frame
        except Exception as e:
            now = datetime.now()
            error_frame = {
                'error': f'Frame capture error: {str(e)}',
                'timestamp': now.isoformat(),
                'local_time': self.get_local_time_str(now),
                'source': 'error'
            }
            logger.error(f"[DEBUG] Returning exception error frame for {camera_id}: {error_frame}")
            return error_frame
    
    def capture_all_frames(self, camera_ids, force_refresh=False):
        """Capture frames for multiple cameras"""
        results = {}
        
        for camera_id in camera_ids:
            try:
                results[camera_id] = self.capture_frame(camera_id, force_refresh)
                logger.debug(f"[DEBUG] capture_all_frames result for {camera_id}: {results[camera_id]}")
            except Exception as e:
                error_frame = {
                    'error': f'Capture failed: {str(e)}',
                    'timestamp': datetime.now().isoformat(),
                    'local_time': self.get_local_time_str(),
                    'source': 'error'
                }
                logger.error(f"[DEBUG] capture_all_frames exception for {camera_id}: {error_frame}")
                results[camera_id] = error_frame
        
        return results

# Global instance
frame_capture = FrameCapture() 