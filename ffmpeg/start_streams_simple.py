#!/usr/bin/env python3

import subprocess
import sys
import os

# Camera URLs
CAMERA_URLS = {
    "frontyard": os.getenv("CAMERA_FRONTYARD_URL", "rtsp://username:password@192.168.1.xxx:554/h264Preview_01_sub"),
    "backyard": os.getenv("CAMERA_BACKYARD_URL", "rtsp://username:password@192.168.1.xxx:554/h264Preview_01_sub"),
    "living_room": os.getenv("CAMERA_LIVING_ROOM_URL", "rtsp://username:password@192.168.1.xxx:554/h264Preview_01_main"),
    "nursery": os.getenv("CAMERA_NURSERY_URL", "rtsp://username:password@192.168.1.xxx:554/h264Preview_01_main")
}

def start_camera_stream(camera):
    """Start FFmpeg stream for a camera"""
    if camera not in CAMERA_URLS:
        print(f"Unknown camera: {camera}")
        return False
    
    url = CAMERA_URLS[camera]
    segment_dir = f"/segments/{camera}"
    
    # Ensure directory exists
    os.makedirs(segment_dir, exist_ok=True)
    
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
    
    print(f"Starting FFmpeg for {camera}...")
    print(f"Command: {' '.join(cmd[:8])}...")  # Don't show credentials
    
    try:
        # Start process in background
        with open(f"/tmp/ffmpeg/{camera}.log", "w") as log_file:
            process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file)
        
        # Save PID
        with open(f"/tmp/ffmpeg/{camera}.pid", "w") as f:
            f.write(str(process.pid))
        
        print(f"Started {camera} with PID {process.pid}")
        return True
        
    except Exception as e:
        print(f"Failed to start {camera}: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 start_streams_simple.py <camera>")
        print("Cameras: frontyard, backyard, living_room, nursery")
        sys.exit(1)
    
    camera = sys.argv[1].lower()
    
    # Ensure temp directory exists
    os.makedirs("/tmp/ffmpeg", exist_ok=True)
    
    success = start_camera_stream(camera)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 