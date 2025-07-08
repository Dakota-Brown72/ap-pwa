import os
import sqlite3
import jwt
import bcrypt
import requests
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, jsonify, request, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import logging
from logging.handlers import RotatingFileHandler

# Set up logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEBUG' if os.environ.get('FLASK_ENV') == 'development' else 'INFO')
LOG_FORMAT = '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
LOG_FILE = os.environ.get('BACKEND_LOG_FILE', '/tmp/anchorpoint-backend.log')

handler = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=2)
handler.setFormatter(logging.Formatter(LOG_FORMAT))
logging.basicConfig(level=LOG_LEVEL, handlers=[handler, logging.StreamHandler()])
logger = logging.getLogger(__name__)

# Memory management settings
import gc
import threading
import time

# Try to import psutil for memory monitoring (optional)
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - memory monitoring disabled")

# Global cache for API responses (with TTL)
API_CACHE = {}
CACHE_TTL = 30  # seconds
CACHE_CLEANUP_INTERVAL = 60  # seconds

def cleanup_cache():
    """Periodically clean up expired cache entries"""
    while True:
        try:
            current_time = time.time()
            expired_keys = []
            
            for key, (data, timestamp) in API_CACHE.items():
                if current_time - timestamp > CACHE_TTL:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del API_CACHE[key]
                
            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                
            # Force garbage collection periodically
            gc.collect()
            
        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
        
        time.sleep(CACHE_CLEANUP_INTERVAL)

# Start cache cleanup thread
cache_cleanup_thread = threading.Thread(target=cleanup_cache, daemon=True)
cache_cleanup_thread.start()

# Import frame capture service
try:
    from frame_capture import frame_capture
    FRAME_CAPTURE_AVAILABLE = True
except ImportError:
    logger.warning("Warning: Frame capture not available (OpenCV not installed)")
    FRAME_CAPTURE_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['DATABASE'] = os.environ.get('DATABASE_PATH', '../data/anchorpoint.db')

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://localhost:5173"]}})

# Frigate API configuration
FRIGATE_HOST = os.environ.get('FRIGATE_HOST', 'http://frigate:5000')

# go2rtc API configuration
GO2RTC_HOST = os.environ.get('GO2RTC_HOST', 'http://go2rtc:1984')
GO2RTC_USERNAME = os.environ.get('GO2RTC_USERNAME', 'Dakota')
GO2RTC_PASSWORD = os.environ.get('GO2RTC_PASSWORD', '#Dakman7214')

@app.route('/api/go2rtc/streams', methods=['GET'])
def get_go2rtc_streams():
    """Proxy go2rtc streams API"""
    try:
        url = f"{GO2RTC_HOST}/api/streams"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        return jsonify(response.json())
    except requests.RequestException as e:
        logger.error(f"go2rtc streams API error: {e}")
        return jsonify({'error': 'Failed to fetch go2rtc streams'}), 500

@app.route('/api/go2rtc/stream/<stream_name>/hls/<path:subpath>', methods=['GET'])
def proxy_go2rtc_hls(stream_name, subpath):
    """Proxy go2rtc HLS streams"""
    try:
        # Build the go2rtc HLS URL - use the correct format
        url = f"{GO2RTC_HOST}/api/stream.m3u8?src={stream_name}"
        
        # Stream the response from go2rtc
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Return the file with proper headers
        headers = {
            'Content-Type': response.headers.get('Content-Type', 'application/vnd.apple.mpegurl'),
            'Content-Length': response.headers.get('Content-Length'),
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'no-cache',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Origin, Accept-Encoding, Content-Type'
        }
        
        return response.content, response.status_code, headers
    except requests.RequestException as e:
        logger.error(f"go2rtc HLS proxy error for {stream_name}: {e}")
        return jsonify({'error': 'Failed to fetch HLS stream'}), 500

@app.route('/api/go2rtc/stream/<stream_name>/webrtc', methods=['GET'])
def proxy_go2rtc_webrtc(stream_name):
    """Proxy go2rtc WebRTC streams"""
    try:
        # Build the go2rtc WebRTC URL - use the correct format
        url = f"{GO2RTC_HOST}/api/stream.webrtc?src={stream_name}"
        
        # Stream the response from go2rtc
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Return the file with proper headers
        headers = {
            'Content-Type': response.headers.get('Content-Type', 'text/html'),
            'Content-Length': response.headers.get('Content-Length'),
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Origin, Accept-Encoding, Content-Type'
        }
        
        return response.content, response.status_code, headers
    except requests.RequestException as e:
        logger.error(f"go2rtc WebRTC proxy error for {stream_name}: {e}")
        return jsonify({'error': 'Failed to fetch WebRTC stream'}), 500

@app.route('/api/go2rtc/stream/<stream_name>/mjpeg', methods=['GET'])
def proxy_go2rtc_mjpeg(stream_name):
    """Proxy go2rtc MJPEG streams"""
    try:
        # Build the go2rtc MJPEG URL - use the correct format
        url = f"{GO2RTC_HOST}/api/stream.mjpeg?src={stream_name}"
        
        # Stream the response from go2rtc
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Return the file with proper headers
        headers = {
            'Content-Type': response.headers.get('Content-Type', 'multipart/x-mixed-replace'),
            'Content-Length': response.headers.get('Content-Length'),
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Origin, Accept-Encoding, Content-Type'
        }
        
        return response.content, response.status_code, headers
    except requests.RequestException as e:
        logger.error(f"go2rtc MJPEG proxy error for {stream_name}: {e}")
        return jsonify({'error': 'Failed to fetch MJPEG stream'}), 500

@app.route('/api/go2rtc/stream/<stream_name>/snapshot', methods=['GET'])
def proxy_go2rtc_snapshot(stream_name):
    """Proxy go2rtc snapshot"""
    try:
        # Build the go2rtc snapshot URL - use the correct format
        url = f"{GO2RTC_HOST}/api/stream.snapshot?src={stream_name}"
        
        # Stream the response from go2rtc
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()
        
        # Return the file with proper headers
        headers = {
            'Content-Type': response.headers.get('Content-Type', 'image/jpeg'),
            'Content-Length': response.headers.get('Content-Length'),
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Range, Origin, Accept-Encoding, Content-Type'
        }
        
        return response.content, response.status_code, headers
    except requests.RequestException as e:
        logger.error(f"go2rtc snapshot proxy error for {stream_name}: {e}")
        return jsonify({'error': 'Failed to fetch snapshot'}), 500

@app.route('/api/frigate/recordings/<camera_name>', methods=['GET'])
def get_frigate_recordings(camera_name):
    """Proxy Frigate recordings API"""
    try:
        # Get query parameters
        before = request.args.get('before')
        after = request.args.get('after')
        
        # Build Frigate API URL
        url = f"{FRIGATE_HOST}/api/{camera_name}/recordings"
        params = {}
        if before:
            params['before'] = before
        if after:
            params['after'] = after
            
        # Make request to Frigate
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        return jsonify(response.json())
    except requests.RequestException as e:
        logger.error(f"Frigate recordings API error: {e}")
        return jsonify({'error': 'Failed to fetch recordings'}), 500

@app.route('/api/frigate/events', methods=['GET'])
def get_frigate_events():
    """Proxy Frigate events API"""
    try:
        # Get query parameters
        camera = request.args.get('camera')
        before = request.args.get('before')
        after = request.args.get('after')
        limit = request.args.get('limit', '100')
        
        # Build Frigate API URL
        url = f"{FRIGATE_HOST}/api/events"
        params = {'limit': limit}
        if camera:
            params['camera'] = camera
        if before:
            params['before'] = before
        if after:
            params['after'] = after
            
        # Make request to Frigate
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        return jsonify(response.json())
    except requests.RequestException as e:
        logger.error(f"Frigate events API error: {e}")
        return jsonify({'error': 'Failed to fetch events'}), 500

@app.route('/api/frigate/events/<event_id>/clip.mp4', methods=['GET'])
def get_frigate_event_clip(event_id):
    """Proxy Frigate event clip files"""
    try:
        # Build Frigate API URL for the specific event clip
        url = f"{FRIGATE_HOST}/api/events/{event_id}/clip.mp4"
        
        # Stream the file from Frigate
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Return the file with proper headers
        return response.content, response.status_code, {
            'Content-Type': response.headers.get('Content-Type', 'video/mp4'),
            'Content-Length': response.headers.get('Content-Length'),
            'Accept-Ranges': 'bytes'
        }
    except requests.RequestException as e:
        logger.error(f"Frigate event clip API error: {e}")
        return jsonify({'error': 'Failed to fetch event clip'}), 500

@app.route('/api/frigate/cameras', methods=['GET'])
def get_frigate_cameras():
    """Proxy Frigate cameras API - extract from config"""
    try:
        url = f"{FRIGATE_HOST}/api/config"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        config = response.json()
        cameras = config.get('cameras', {})
        
        # Extract camera information
        camera_list = []
        for camera_name, camera_config in cameras.items():
            camera_info = {
                'name': camera_name,
                'enabled': camera_config.get('enabled', True),
                'live': camera_config.get('live', {}),
                'detect': camera_config.get('detect', {}),
                'record': camera_config.get('record', {}),
                'snapshots': camera_config.get('snapshots', {}),
                'ui': camera_config.get('ui', {})
            }
            camera_list.append(camera_info)
        
        return jsonify(camera_list)
    except requests.RequestException as e:
        logger.error(f"Frigate cameras API error: {e}")
        return jsonify({'error': 'Failed to fetch cameras'}), 500

@app.route('/api/frigate/recordings/<camera_name>/latest', methods=['GET'])
def get_latest_recording(camera_name):
    """Get the latest recording for a camera with thorough filesystem scanning"""
    try:
        # Get query parameter for minimum age (to avoid serving incomplete files)
        min_age = request.args.get('min_age', '2', type=int)  # Default 2 seconds
        
        recording_dir = f"/media/frigate/recordings"
        if not os.path.exists(recording_dir):
            return jsonify({'error': 'No recent recordings found'}), 200
        
        # Find the most recent recording file with thorough scanning
        latest_file = None
        latest_time = 0
        current_time = time.time()
        
        # Scan all date directories (last 7 days to be thorough)
        date_dirs = sorted(os.listdir(recording_dir), reverse=True)[:7]
        
        for date_dir in date_dirs:
            date_path = os.path.join(recording_dir, date_dir)
            if not os.path.isdir(date_path):
                continue
                
            # Scan all hour directories
            hour_dirs = sorted(os.listdir(date_path), reverse=True)
            
            for hour_dir in hour_dirs:
                hour_path = os.path.join(date_path, hour_dir)
                if not os.path.isdir(hour_path):
                    continue
                    
                # Check if camera directory exists
                camera_path = os.path.join(hour_path, camera_name)
                if not os.path.exists(camera_path):
                    continue
                    
                # Find the most recent file in this directory
                try:
                    files = [f for f in os.listdir(camera_path) if f.endswith('.mp4')]
                    files.sort(reverse=True)  # Most recent first
                    
                    for filename in files:
                        file_path = os.path.join(camera_path, filename)
                        
                        # Check if file is complete (not being written)
                        try:
                            file_time = os.path.getmtime(file_path)
                            file_size = os.path.getsize(file_path)
                            
                            # Skip files that are too recent (might be incomplete)
                            if current_time - file_time < min_age:
                                continue
                                
                            # Skip files that are too small (likely incomplete)
                            if file_size < 1000:  # Less than 1KB
                                continue
                            
                            if file_time > latest_time:
                                latest_time = file_time
                                latest_file = {
                                    'file_path': f"{date_dir}/{hour_dir}/{camera_name}/{filename}",
                                    'start_time': int(file_time),
                                    'end_time': int(file_time) + 10,  # Assume 10 second duration
                                    'duration': 10.0,
                                    'motion': 0,
                                    'objects': 0,
                                    'segment_size': 6.0,
                                    'id': f"{int(file_time)}.0-filesystem",
                                    'file_size': file_size,
                                    'age_seconds': int(current_time - file_time)
                                }
                                break  # Found the most recent file in this hour
                        except (OSError, IOError) as e:
                            logger.warning(f"Error accessing file {file_path}: {e}")
                            continue
                            
                except (OSError, IOError) as e:
                    logger.warning(f"Error reading directory {camera_path}: {e}")
                    continue
                    
                # If we found a file in this hour, we can stop looking at older hours
                if latest_file:
                    break
                    
            # If we found a file in this date, we can stop looking at older dates
            if latest_file:
                break
        
        if latest_file:
            logger.debug(f"Found latest recording for {camera_name}: {latest_file['file_path']} (age: {latest_file['age_seconds']}s)")
            return jsonify(latest_file)
        else:
            return jsonify({'error': 'No recent recordings found'}), 200
            
    except Exception as e:
        logger.error(f"Error getting latest recording for {camera_name}: {e}")
        return jsonify({'error': 'Failed to fetch latest recording'}), 500

@app.route('/api/frigate/recordings/<camera_name>/<path:recording_path>', methods=['GET'])
def serve_recording_file(camera_name, recording_path):
    """Serve a specific recording file from Frigate"""
    try:
        # Build the full path to the recording file
        # Frigate stores recordings in /media/frigate/recordings/
        recording_dir = f"/media/frigate/recordings"
        
        # The recording_path should be something like "2025-07-06/18/Living_Room/28.53.mp4"
        full_path = os.path.join(recording_dir, recording_path)
        
        # Security check: ensure the path is within the recordings directory
        if not os.path.abspath(full_path).startswith(os.path.abspath(recording_dir)):
            return jsonify({'error': 'Invalid path'}), 400
        
        if not os.path.exists(full_path):
            return jsonify({'error': 'Recording not found'}), 404
        
        # Serve the file with proper headers for video streaming
        response = send_from_directory(
            os.path.dirname(full_path),
            os.path.basename(full_path)
        )
        
        # Add headers for video streaming
        response.headers['Content-Type'] = 'video/mp4'
        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['Cache-Control'] = 'public, max-age=3600'
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Range, Origin, Accept-Encoding, Content-Type'
        
        return response
    except Exception as e:
        logger.error(f"Error serving recording file: {e}")
        return jsonify({'error': 'Failed to serve recording'}), 500

@app.route('/api/frigate/recordings/<camera_name>/list', methods=['GET'])
def list_recordings(camera_name):
    """List available recordings for a camera"""
    try:
        # Get query parameters
        days = request.args.get('days', '1', type=int)
        
        # Calculate the date range using Unix timestamp
        now = datetime.now()
        after_timestamp = int((now - timedelta(days=days)).timestamp())
        
        url = f"{FRIGATE_HOST}/api/{camera_name}/recordings"
        params = {'after': after_timestamp}
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        recordings = response.json()
        
        # Add file paths for easy access
        for recording in recordings:
            # Extract the file path from the recording data
            if 'start_time' in recording:
                start_time = datetime.fromtimestamp(recording['start_time'])
                # Format: YYYY-MM-DD/HH/camera_name/filename.mp4
                # The filename is based on the start_time (minute.second.mp4)
                # Round down to the nearest 10-second interval
                minute = start_time.minute
                second = (start_time.second // 10) * 10  # Round down to nearest 10
                filename = f"{minute:02d}.{second:02d}.mp4"
                recording['file_path'] = f"{start_time.strftime('%Y-%m-%d')}/{start_time.strftime('%H')}/{camera_name}/{filename}"
        
        return jsonify(recordings)
    except requests.RequestException as e:
        logger.error(f"Frigate recordings list API error: {e}")
        return jsonify({'error': 'Failed to fetch recordings list'}), 500

@app.route('/api/frigate/recordings/<camera_name>/recent', methods=['GET'])
def get_recent_recordings(camera_name):
    """Get recent recordings for a camera with thorough filesystem scanning"""
    try:
        # Get query parameters
        count = int(request.args.get('count', '6'))  # Default 6 recordings (1 minute buffer)
        min_age = int(request.args.get('min_age', '2'))  # Default 2 seconds
        
        recording_dir = f"/media/frigate/recordings"
        if not os.path.exists(recording_dir):
            return jsonify([])
        
        recordings = []
        current_time = time.time()
        
        # Scan all date directories (last 3 days to be thorough)
        date_dirs = sorted(os.listdir(recording_dir), reverse=True)[:3]
        
        for date_dir in date_dirs:
            if len(recordings) >= count:
                break
                
            date_path = os.path.join(recording_dir, date_dir)
            if not os.path.isdir(date_path):
                continue
                
            # Scan all hour directories
            hour_dirs = sorted(os.listdir(date_path), reverse=True)
            
            for hour_dir in hour_dirs:
                if len(recordings) >= count:
                    break
                    
                hour_path = os.path.join(date_path, hour_dir)
                if not os.path.isdir(hour_path):
                    continue
                    
                # Check if camera directory exists
                camera_path = os.path.join(hour_path, camera_name)
                if not os.path.exists(camera_path):
                    continue
                    
                # Find recent files in this directory
                try:
                    files = [f for f in os.listdir(camera_path) if f.endswith('.mp4')]
                    files.sort(reverse=True)  # Most recent first
                    
                    for filename in files:
                        if len(recordings) >= count:
                            break
                            
                        file_path = os.path.join(camera_path, filename)
                        
                        # Check if file is complete (not being written)
                        try:
                            file_time = os.path.getmtime(file_path)
                            file_size = os.path.getsize(file_path)
                            
                            # Skip files that are too recent (might be incomplete)
                            if current_time - file_time < min_age:
                                continue
                                
                            # Skip files that are too small (likely incomplete)
                            if file_size < 1000:  # Less than 1KB
                                continue
                            
                            recording = {
                                'file_path': f"{date_dir}/{hour_dir}/{camera_name}/{filename}",
                                'start_time': int(file_time),
                                'end_time': int(file_time) + 10,  # Assume 10 second duration
                                'duration': 10.0,
                                'motion': 0,
                                'objects': 0,
                                'segment_size': 6.0,
                                'id': f"{int(file_time)}.0-filesystem",
                                'file_size': file_size,
                                'age_seconds': int(current_time - file_time)
                            }
                            
                            recordings.append(recording)
                            
                        except (OSError, IOError) as e:
                            logger.warning(f"Error accessing file {file_path}: {e}")
                            continue
                            
                except (OSError, IOError) as e:
                    logger.warning(f"Error reading directory {camera_path}: {e}")
                    continue
        
        # Sort by start_time (most recent first) and return requested count
        recordings.sort(key=lambda x: x['start_time'], reverse=True)
        return jsonify(recordings[:count])
        
    except Exception as e:
        logger.error(f"Error getting recent recordings for {camera_name}: {e}")
        return jsonify([])

@app.route('/api/frigate/recordings/<camera_name>/buffer', methods=['GET'])
def get_buffered_recordings(camera_name):
    """Get a 1-minute buffer of recordings for seamless streaming"""
    try:
        # Get query parameters
        buffer_size = int(request.args.get('buffer_size', '6'))  # Default 6 recordings (1 minute)
        min_age = int(request.args.get('min_age', '2'))  # Default 2 seconds
        
        recording_dir = f"/media/frigate/recordings"
        if not os.path.exists(recording_dir):
            return jsonify({'recordings': [], 'buffer_complete': False})
        
        recordings = []
        current_time = time.time()
        
        # Scan all date directories (last 3 days to be thorough)
        date_dirs = sorted(os.listdir(recording_dir), reverse=True)[:3]
        
        for date_dir in date_dirs:
            if len(recordings) >= buffer_size:
                break
                
            date_path = os.path.join(recording_dir, date_dir)
            if not os.path.isdir(date_path):
                continue
                
            # Scan all hour directories
            hour_dirs = sorted(os.listdir(date_path), reverse=True)
            
            for hour_dir in hour_dirs:
                if len(recordings) >= buffer_size:
                    break
                    
                hour_path = os.path.join(date_path, hour_dir)
                if not os.path.isdir(hour_path):
                    continue
                    
                # Check if camera directory exists
                camera_path = os.path.join(hour_path, camera_name)
                if not os.path.exists(camera_path):
                    continue
                    
                # Find recent files in this directory
                try:
                    files = [f for f in os.listdir(camera_path) if f.endswith('.mp4')]
                    files.sort(reverse=True)  # Most recent first
                    
                    for filename in files:
                        if len(recordings) >= buffer_size:
                            break
                            
                        file_path = os.path.join(camera_path, filename)
                        
                        # Check if file is complete (not being written)
                        try:
                            file_time = os.path.getmtime(file_path)
                            file_size = os.path.getsize(file_path)
                            
                            # Skip files that are too recent (might be incomplete)
                            if current_time - file_time < min_age:
                                continue
                                
                            # Skip files that are too small (likely incomplete)
                            if file_size < 1000:  # Less than 1KB
                                continue
                            
                            # Parse timestamp from filename (e.g., "00.40.mp4" -> 40 seconds)
                            try:
                                # Extract seconds from filename (remove .mp4 extension)
                                seconds_str = filename.replace('.mp4', '')
                                # Split by dot to get minutes and seconds
                                if '.' in seconds_str:
                                    minutes, seconds = seconds_str.split('.')
                                    start_seconds = int(minutes) * 60 + int(seconds)
                                else:
                                    start_seconds = int(seconds_str)
                                
                                # Construct the full timestamp from date_dir, hour_dir, and start_seconds
                                # date_dir format: "2025-07-01", hour_dir format: "18"
                                date_obj = datetime.strptime(date_dir, "%Y-%m-%d")
                                hour = int(hour_dir)
                                # Create datetime object for the start of the hour
                                hour_start = date_obj.replace(hour=hour, minute=0, second=0, microsecond=0)
                                # Add the start_seconds to get the actual start time
                                actual_start_time = hour_start + timedelta(seconds=start_seconds)
                                start_timestamp = int(actual_start_time.timestamp())
                                
                            except (ValueError, AttributeError) as e:
                                logger.warning(f"Failed to parse timestamp from filename {filename}: {e}")
                                # Fall back to file modification time
                                start_timestamp = int(file_time)
                            
                            recording = {
                                'file_path': f"{date_dir}/{hour_dir}/{camera_name}/{filename}",
                                'start_time': start_timestamp,
                                'end_time': start_timestamp + 10,  # Assume 10 second duration
                                'duration': 10.0,
                                'motion': 0,
                                'objects': 0,
                                'segment_size': 6.0,
                                'id': f"{start_timestamp}.0-filesystem",
                                'file_size': file_size,
                                'age_seconds': int(current_time - start_timestamp)
                            }
                            
                            recordings.append(recording)
                            
                        except (OSError, IOError) as e:
                            logger.warning(f"Error accessing file {file_path}: {e}")
                            continue
                            
                except (OSError, IOError) as e:
                    logger.warning(f"Error reading directory {camera_path}: {e}")
                    continue
        
        # Sort by start_time (oldest first for chronological playback)
        recordings.sort(key=lambda x: x['start_time'])
        
        # Check if we have a complete buffer
        buffer_complete = len(recordings) >= buffer_size
        
        # If we have recordings, check if they form a continuous sequence
        if recordings and len(recordings) > 1:
            # Sort by start_time (oldest first for sequence checking)
            sorted_recordings = sorted(recordings, key=lambda x: x['start_time'])
            
            # Check if recordings are sequential (within 15 seconds of each other)
            for i in range(len(sorted_recordings) - 1):
                current_end = sorted_recordings[i]['start_time'] + 10
                next_start = sorted_recordings[i + 1]['start_time']
                
                # If gap is more than 15 seconds, buffer is incomplete
                if next_start - current_end > 15:
                    buffer_complete = False
                    break
        
        return jsonify({
            'recordings': recordings[:buffer_size],
            'buffer_complete': buffer_complete,
            'buffer_size': len(recordings),
            'target_size': buffer_size
        })
        
    except Exception as e:
        logger.error(f"Error getting buffered recordings for {camera_name}: {e}")
        return jsonify({'recordings': [], 'buffer_complete': False, 'error': str(e)})

# --- HLS Proxy for Frontyard and Backyard (via go2rtc in Frigate) ---
from requests.auth import HTTPBasicAuth

@app.route('/api/proxy/hls/frontyard/<path:subpath>', methods=['GET'])
def proxy_hls_frontyard(subpath):
    """Proxy HLS playlist and segments for Frontyard_main via go2rtc"""
    return proxy_hls_stream('Frontyard_main', subpath)

@app.route('/api/proxy/hls/backyard/<path:subpath>', methods=['GET'])
def proxy_hls_backyard(subpath):
    """Proxy HLS playlist and segments for Backyard_main via go2rtc"""
    return proxy_hls_stream('Backyard_main', subpath)


def proxy_hls_stream(stream_name, subpath):
    # Build the go2rtc HLS URL (Frigate's internal go2rtc)
    # Example: http://frigate:1984/api/stream.m3u8?src=Frontyard_main
    # For segments: http://frigate:1984/api/stream.m3u8?src=Frontyard_main&segment=... (handled by go2rtc)
    go2rtc_base = os.environ.get('GO2RTC_HOST', 'http://frigate:1984')
    # Determine if this is the playlist or a segment
    if subpath.endswith('.m3u8'):
        url = f"{go2rtc_base}/api/stream.m3u8?src={stream_name}"
    else:
        # For .ts segments, go2rtc uses the same endpoint with segment param
        url = f"{go2rtc_base}/api/stream.m3u8?src={stream_name}&segment={subpath}"
    # Use HTTP Basic Auth if required (not usually needed for Frigate's go2rtc)
    auth = HTTPBasicAuth('Dakota', '#Dakman7214') if 'go2rtc' in go2rtc_base else None
    try:
        r = requests.get(url, timeout=15, auth=auth)
        r.raise_for_status()
        
        # Debug logging
        logger.debug(f"HLS proxy for {stream_name}: status={r.status_code}, content_length={len(r.content)}, content={repr(r.text[:200])}")
        
        # Set appropriate content type
        if subpath.endswith('.m3u8'):
            content_type = 'application/vnd.apple.mpegurl'
        elif subpath.endswith('.ts'):
            content_type = 'video/MP2T'
        else:
            content_type = r.headers.get('Content-Type', 'application/octet-stream')
        
        # Return the response directly with proper headers
        response = Response(r.content, content_type=content_type)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Range, Origin, Accept-Encoding, Content-Type'
        response.headers['Cache-Control'] = 'no-cache'
        return response
    except requests.RequestException as e:
        logger.error(f"HLS proxy error for {stream_name}: {e}")
        return jsonify({'error': f'Failed to fetch HLS stream for {stream_name}'}), 502

def get_db():
    """Get database connection"""
    db = sqlite3.connect(app.config['DATABASE'])
    db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database with schema"""
    with app.app_context():
        db = get_db()
        with open('database_schema.sql', 'r') as f:
            db.executescript(f.read())
        db.commit()
        db.close()

def token_required(f):
    """Decorator to require JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            token = token.split(' ')[1]  # Remove 'Bearer ' prefix
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            db = get_db()
            user = db.execute('SELECT * FROM users WHERE id = ?', (data['user_id'],)).fetchone()
            if not user:
                return jsonify({'error': 'Invalid token'}), 401
            request.current_user = user
        except Exception as e:
            return jsonify({'error': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Decorator to require admin privileges"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not hasattr(request, 'current_user') or not request.current_user['is_admin']:
            return jsonify({'error': 'Admin privileges required'}), 403
        return f(*args, **kwargs)
    return decorated

# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE username = ? AND is_active = 1', (username,)).fetchone()
    
    if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
        # Update last login
        db.execute('UPDATE users SET last_login = ? WHERE id = ?', (datetime.now(), user['id']))
        
        # Create session token
        token = jwt.encode({
            'user_id': user['id'],
            'username': user['username'],
            'exp': datetime.utcnow() + timedelta(days=7)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        # Store session
        db.execute('''
            INSERT INTO user_sessions (user_id, session_token, device_info, ip_address, expires_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (user['id'], token, request.headers.get('User-Agent'), request.remote_addr, 
              datetime.utcnow() + timedelta(days=7)))
        db.commit()
        
        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'full_name': user['full_name'],
                'is_admin': user['is_admin']
            }
        })
    
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout():
    token = request.headers.get('Authorization').split(' ')[1]
    db = get_db()
    db.execute('DELETE FROM user_sessions WHERE session_token = ?', (token,))
    db.commit()
    return jsonify({'message': 'Logged out successfully'})

# User management endpoints
@app.route('/api/users', methods=['GET'])
@token_required
def get_users():
    db = get_db()
    users = db.execute('''
        SELECT u.id, u.username, u.email, u.full_name, u.is_admin, u.is_active, u.created_at, u.last_login
        FROM users u
        JOIN user_households uh ON u.id = uh.user_id
        JOIN user_households current_user_household ON current_user_household.user_id = ?
        WHERE uh.household_id = current_user_household.household_id
    ''', (request.current_user['id'],)).fetchall()
    
    return jsonify([dict(user) for user in users])

@app.route('/api/users', methods=['POST'])
@token_required
@admin_required
def create_user():
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password', 'full_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    # Hash password
    password_hash = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    db = get_db()
    try:
        # Get current user's household
        household = db.execute('''
            SELECT household_id FROM user_households WHERE user_id = ?
        ''', (request.current_user['id'],)).fetchone()
        
        # Create user
        cursor = db.execute('''
            INSERT INTO users (username, email, password_hash, full_name, is_admin)
            VALUES (?, ?, ?, ?, ?)
        ''', (data['username'], data['email'], password_hash, data['full_name'], data.get('is_admin', False)))
        
        user_id = cursor.lastrowid
        
        # Add user to household
        db.execute('''
            INSERT INTO user_households (user_id, household_id, role)
            VALUES (?, ?, ?)
        ''', (user_id, household['household_id'], data.get('role', 'member')))
        
        db.commit()
        return jsonify({'message': 'User created successfully', 'user_id': user_id}), 201
        
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Username or email already exists'}), 400

# Device management endpoints
@app.route('/api/devices', methods=['GET'])
@token_required
def get_devices():
    db = get_db()
    devices = db.execute('''
        SELECT id, device_name, device_type, is_active, last_seen, created_at
        FROM devices WHERE user_id = ?
    ''', (request.current_user['id'],)).fetchall()
    
    return jsonify([dict(device) for device in devices])

@app.route('/api/devices', methods=['POST'])
@token_required
def register_device():
    data = request.get_json()
    
    required_fields = ['device_name', 'device_type', 'push_token']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    db = get_db()
    cursor = db.execute('''
        INSERT INTO devices (user_id, device_name, device_type, push_token, fcm_token)
        VALUES (?, ?, ?, ?, ?)
    ''', (request.current_user['id'], data['device_name'], data['device_type'], 
          data['push_token'], data.get('fcm_token')))
    
    db.commit()
    return jsonify({'message': 'Device registered successfully', 'device_id': cursor.lastrowid}), 201

# Frigate API integration
@app.route('/api/cameras', methods=['GET'])
@token_required
def get_cameras():
    """Get cameras from Frigate API with cached snapshots"""
    try:
        # Check if we need to refresh snapshots (every hour)
        force_refresh = request.args.get('refresh', 'false').lower() == 'true'
        
        response = requests.get(f'{FRIGATE_HOST}/api/config')
        if response.status_code == 200:
            config = response.json()
            cameras = []
            
            for camera_id, camera_config in config.get('cameras', {}).items():
                # Generate URLs for different stream types
                # Use public snapshot endpoint to avoid authentication issues
                snapshot_url = f'/api/public/camera/{camera_id}/snapshot'
                # Remove go2rtc stream URLs
                cameras.append({
                    'id': camera_id,
                    'name': camera_config.get('name', camera_id),
                    'enabled': camera_config.get('enabled', True),
                    'snapshot_url': snapshot_url,
                    'live_streams': {},
                    'last_updated': datetime.now().isoformat()
                })
            
            return jsonify({
                'cameras': cameras,
                'refresh_available': True,
                'next_refresh': (datetime.now() + timedelta(hours=1)).isoformat()
            })
        else:
            return jsonify({'error': 'Failed to fetch cameras from Frigate'}), 500
    except Exception as e:
        return jsonify({'error': f'Error connecting to Frigate: {str(e)}'}), 500

@app.route('/api/public/cameras', methods=['GET'])
def get_public_cameras():
    """Get cameras from Frigate API (public endpoint, no authentication required)"""
    try:
        response = requests.get(f'{FRIGATE_HOST}/api/config')
        if response.status_code == 200:
            config = response.json()
            cameras = []
            
            for camera_id, camera_config in config.get('cameras', {}).items():
                # Generate URLs for different stream types
                snapshot_url = f'/api/public/camera/{camera_id}/snapshot'
                # Remove go2rtc stream URLs
                cameras.append({
                    'id': camera_id,
                    'name': camera_config.get('name', camera_id),
                    'enabled': camera_config.get('enabled', True),
                    'snapshot_url': snapshot_url,
                    'live_streams': {},
                    'last_updated': datetime.now().isoformat()
                })
            
            return jsonify({
                'cameras': cameras,
                'refresh_available': True,
                'next_refresh': (datetime.now() + timedelta(hours=1)).isoformat()
            })
        else:
            return jsonify({'error': 'Failed to fetch cameras from Frigate'}), 500
    except Exception as e:
        return jsonify({'error': f'Error connecting to Frigate: {str(e)}'}), 500

@app.route('/api/public/stream/<camera_id>', methods=['GET'])
def get_public_stream(camera_id):
    """Proxy endpoint for camera streams to hide actual URLs (public endpoint, no authentication required)"""
    try:
        # Remove go2rtc redirect logic
        return jsonify({'error': 'Live streaming is not available.'}), 404
    except Exception as e:
        return jsonify({'error': f'Error accessing stream: {str(e)}'}), 500

@app.route('/api/events', methods=['GET'])
@token_required
def get_events():
    """Get events from Frigate API"""
    try:
        # Get events from the last 24 hours
        end_time = datetime.now().isoformat()
        start_time = (datetime.now() - timedelta(days=1)).isoformat()
        
        response = requests.get(f'{FRIGATE_HOST}/api/events', params={
            'start_time': start_time,
            'end_time': end_time,
            'limit': 50
        })
        
        if response.status_code == 200:
            events = response.json()
            return jsonify(events)
        else:
            return jsonify({'error': 'Failed to fetch events from Frigate'}), 500
    except Exception as e:
        return jsonify({'error': f'Error fetching events: {str(e)}'}), 500

# System status endpoint
@app.route('/api/system/status', methods=['GET'])
@token_required
def get_system_status():
    """Get system status including Frigate and storage info"""
    try:
        # Get Frigate status
        frigate_status = requests.get(f'{FRIGATE_HOST}/api/stats').json()
        
        # Get storage info (you'll need to implement this based on your setup)
        storage_info = {
            'total_space': 1000000000000,  # 1TB in bytes
            'used_space': 500000000000,    # 500GB in bytes
            'free_space': 500000000000     # 500GB in bytes
        }
        
        return jsonify({
            'frigate': frigate_status,
            'storage': storage_info,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching system status: {str(e)}'}), 500

# Notification preferences
@app.route('/api/notifications/preferences', methods=['GET'])
@token_required
def get_notification_preferences():
    db = get_db()
    preferences = db.execute('''
        SELECT camera_id, event_type, notification_type, is_enabled
        FROM notification_preferences WHERE user_id = ?
    ''', (request.current_user['id'],)).fetchall()
    
    return jsonify([dict(pref) for pref in preferences])

@app.route('/api/notifications/preferences', methods=['POST'])
@token_required
def update_notification_preferences():
    data = request.get_json()
    
    db = get_db()
    db.execute('''
        INSERT OR REPLACE INTO notification_preferences 
        (user_id, camera_id, event_type, notification_type, is_enabled)
        VALUES (?, ?, ?, ?, ?)
    ''', (request.current_user['id'], data.get('camera_id'), data.get('event_type'),
          data.get('notification_type', 'push'), data.get('is_enabled', True)))
    
    db.commit()
    return jsonify({'message': 'Preferences updated successfully'})

# Health check endpoint (no authentication required)
@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint for Docker"""
    try:
        # Test database connection
        db = get_db()
        db.execute('SELECT 1').fetchone()
        db.close()
        
        # Test Frigate connection
        response = requests.get(f'{FRIGATE_HOST}/api/config', timeout=5)
        frigate_status = 'healthy' if response.status_code == 200 else 'unhealthy'
        
        # Get memory usage if available
        memory_info = {}
        if PSUTIL_AVAILABLE:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = round(memory_info.rss / 1024 / 1024, 2)
        else:
            memory_mb = None
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'frigate': frigate_status,
            'memory_mb': memory_mb,
            'cache_entries': len(API_CACHE),
            'timestamp': datetime.now().isoformat()
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/system/memory', methods=['GET'])
def get_memory_usage():
    """Get detailed memory usage information"""
    try:
        if not PSUTIL_AVAILABLE:
            return jsonify({
                'error': 'Memory monitoring not available (psutil not installed)',
                'cache': {
                    'entries': len(API_CACHE),
                    'ttl_seconds': CACHE_TTL
                }
            }), 503
        
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return jsonify({
            'process_memory': {
                'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
                'vms_mb': round(memory_info.vms / 1024 / 1024, 2),
                'percent': round(process.memory_percent(), 2)
            },
            'system_memory': {
                'total_mb': round(psutil.virtual_memory().total / 1024 / 1024, 2),
                'available_mb': round(psutil.virtual_memory().available / 1024 / 1024, 2),
                'percent': round(psutil.virtual_memory().percent, 2)
            },
            'cache': {
                'entries': len(API_CACHE),
                'ttl_seconds': CACHE_TTL
            }
        })
    except Exception as e:
        logger.error(f"Memory usage check failed: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize database if it doesn't exist
    if not os.path.exists(app.config['DATABASE']):
        init_db()
    
    app.run(host='0.0.0.0', port=5003, debug=True)