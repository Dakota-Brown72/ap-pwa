#!/usr/bin/env python3

import subprocess
import os
import json
import time
import signal
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Configuration
STREAM_TIMEOUT = 120
PID_DIR = "/tmp/ffmpeg"
SEGMENT_DIR = "/segments"

# Camera URLs
CAMERA_URLS = {
    "frontyard": "rtsp://Dakota:%23Dakman7214@192.168.1.112:554/h264Preview_01_sub",
    "backyard": "rtsp://Dakota:%23Dakman7214@192.168.1.113:554/h264Preview_01_sub", 
    "living_room": "rtsp://Dakota:%23Dakman7214@192.168.1.114:554/h264Preview_01_main",
    "nursery": "rtsp://Dakota:%23Dakman7214@192.168.1.115:554/h264Preview_01_main"
}

class StreamManager:
    def __init__(self):
        os.makedirs(PID_DIR, exist_ok=True)
        for camera in CAMERA_URLS:
            os.makedirs(f"{SEGMENT_DIR}/{camera}", exist_ok=True)
        
        # Start cleanup daemon
        self.cleanup_thread = threading.Thread(target=self.cleanup_daemon, daemon=True)
        self.cleanup_thread.start()
    
    def start_camera(self, camera):
        """Start FFmpeg stream for a camera"""
        if camera not in CAMERA_URLS:
            return False, f"Unknown camera: {camera}"
        
        if self.is_running(camera):
            return True, f"Stream {camera} already running"
        
        url = CAMERA_URLS[camera]
        segment_dir = f"{SEGMENT_DIR}/{camera}"
        
        # Clean up old files
        subprocess.run(f"rm -f {segment_dir}/*.ts {segment_dir}/playlist.m3u8", shell=True)
        
        # FFmpeg command
        cmd = [
            "ffmpeg",
            "-hide_banner", "-loglevel", "warning",
            "-fflags", "+genpts+discardcorrupt",
            "-rtsp_transport", "tcp",
            "-timeout", "10000000",
            "-i", url,
            "-c:v", "libx264", "-preset", "veryfast", "-tune", "zerolatency",
            "-profile:v", "baseline", "-level", "3.1", "-pix_fmt", "yuv420p",
            "-s", "960x540", "-b:v", "1000k", "-maxrate", "1200k", "-bufsize", "600k",
            "-g", "30", "-keyint_min", "15", "-sc_threshold", "0",
            "-c:a", "aac", "-b:a", "64k", "-ar", "44100", "-ac", "2",
            "-f", "hls", "-hls_time", "4", "-hls_list_size", "6",
            "-hls_flags", "delete_segments+append_list+independent_segments",
            "-hls_segment_type", "mpegts", "-hls_playlist_type", "event",
            "-hls_segment_filename", f"{segment_dir}/segment_%05d.ts",
            f"{segment_dir}/playlist.m3u8"
        ]
        
        # Start process
        try:
            with open(f"{PID_DIR}/{camera}.log", "w") as log_file:
                process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
            
            # Save PID and access time
            with open(f"{PID_DIR}/{camera}.pid", "w") as f:
                f.write(str(process.pid))
            
            self.update_access(camera)
            return True, f"Started {camera} with PID {process.pid}"
            
        except Exception as e:
            return False, f"Failed to start {camera}: {e}"
    
    def stop_camera(self, camera):
        """Stop FFmpeg stream for a camera"""
        if camera not in CAMERA_URLS:
            return False, f"Unknown camera: {camera}"
        
        pid_file = f"{PID_DIR}/{camera}.pid"
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    pid = int(f.read().strip())
                
                # Try graceful shutdown first
                os.kill(pid, signal.SIGTERM)
                time.sleep(2)
                
                # Force kill if still running
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                    
            except (ValueError, ProcessLookupError):
                pass
            
            # Clean up files
            os.remove(pid_file)
            if os.path.exists(f"{PID_DIR}/{camera}.lastaccess"):
                os.remove(f"{PID_DIR}/{camera}.lastaccess")
            
            # Clean up segments
            subprocess.run(f"rm -f {SEGMENT_DIR}/{camera}/*.ts {SEGMENT_DIR}/{camera}/playlist.m3u8", shell=True)
        
        return True, f"Stopped {camera}"
    
    def is_running(self, camera):
        """Check if camera stream is running"""
        pid_file = f"{PID_DIR}/{camera}.pid"
        
        if not os.path.exists(pid_file):
            return False
        
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            os.kill(pid, 0)
            return True
            
        except (ValueError, ProcessLookupError):
            # Clean up stale PID file
            if os.path.exists(pid_file):
                os.remove(pid_file)
            return False
    
    def update_access(self, camera):
        """Update last access time for a camera"""
        if camera in CAMERA_URLS:
            access_file = f"{PID_DIR}/{camera}.lastaccess"
            with open(access_file, "w") as f:
                f.write(str(time.time()))
            return True
        return False
    
    def get_status(self, camera=None):
        """Get status of streams"""
        if camera:
            if camera in CAMERA_URLS:
                return {
                    "camera": camera,
                    "running": self.is_running(camera)
                }
            else:
                return {"error": f"Unknown camera: {camera}"}
        
        # Return status for all cameras
        status = {"service": "ffmpeg-streamer", "cameras": {}}
        for cam in CAMERA_URLS:
            status["cameras"][cam] = self.is_running(cam)
        return status
    
    def cleanup_daemon(self):
        """Background cleanup of stale streams"""
        while True:
            try:
                current_time = time.time()
                
                for camera in CAMERA_URLS:
                    access_file = f"{PID_DIR}/{camera}.lastaccess"
                    
                    if os.path.exists(access_file) and self.is_running(camera):
                        access_time = os.path.getmtime(access_file)
                        age = current_time - access_time
                        
                        if age > STREAM_TIMEOUT:
                            print(f"Stream {camera} is stale ({age:.0f}s), stopping...")
                            self.stop_camera(camera)
                
                time.sleep(30)
            except Exception as e:
                print(f"Cleanup error: {e}")
                time.sleep(30)

class APIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, stream_manager=None, **kwargs):
        self.stream_manager = stream_manager
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        self.handle_request()
    
    def do_POST(self):
        self.handle_request()
    
    def handle_request(self):
        """Handle HTTP requests"""
        try:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            
            # Set response headers
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            
            # Route requests
            if path.startswith('/api/stream/'):
                parts = path.split('/')
                if len(parts) >= 5:
                    camera = parts[3]
                    action = parts[4]
                    
                    if action == 'start':
                        success, message = self.stream_manager.start_camera(camera)
                        response = {"status": "ok" if success else "error", "message": message}
                    elif action == 'stop':
                        success, message = self.stream_manager.stop_camera(camera)
                        response = {"status": "ok" if success else "error", "message": message}
                    elif action == 'access':
                        success = self.stream_manager.update_access(camera)
                        response = {"status": "ok" if success else "error"}
                    elif action == 'status':
                        response = self.stream_manager.get_status(camera)
                    else:
                        response = {"status": "error", "message": f"Unknown action: {action}"}
                else:
                    response = {"status": "error", "message": "Invalid API path"}
                    
            elif path == '/api/status':
                response = self.stream_manager.get_status()
            else:
                response = {"status": "error", "message": "Unknown endpoint"}
            
            # Send response
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Request error: {e}")
            error_response = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(error_response).encode())
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print("Shutting down FFmpeg API server...")
    sys.exit(0)

def main():
    print("Starting FFmpeg API Server...")
    
    # Create stream manager
    stream_manager = StreamManager()
    
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create HTTP server with custom handler
    def handler_factory(*args, **kwargs):
        return APIHandler(*args, stream_manager=stream_manager, **kwargs)
    
    server = HTTPServer(('0.0.0.0', 8080), handler_factory)
    
    print("FFmpeg API Server running on port 8080")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Server interrupted")
    finally:
        server.server_close()

if __name__ == '__main__':
    main() 