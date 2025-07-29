#!/bin/bash

# Simple On-Demand FFmpeg HLS Streaming Service
echo "Starting FFmpeg On-Demand Service..."

# Create directories
mkdir -p /segments/frontyard /segments/backyard /segments/living_room /segments/nursery
mkdir -p /tmp/ffmpeg

# Stream timeout (stop after X seconds of no requests)
STREAM_TIMEOUT=120
PID_DIR="/tmp/ffmpeg"
SEGMENT_DIR="/segments"

# Camera URLs
FRONTYARD_URL="rtsp://Dakota:%23Dakman7214@192.168.1.112:554/h264Preview_01_sub"
BACKYARD_URL="rtsp://Dakota:%23Dakman7214@192.168.1.113:554/h264Preview_01_sub"
LIVING_ROOM_URL="rtsp://Dakota:%23Dakman7214@192.168.1.114:554/h264Preview_01_main"
NURSERY_URL="rtsp://Dakota:%23Dakman7214@192.168.1.115:554/h264Preview_01_main"

# Function to start a camera stream
start_camera() {
    local camera="$1"
    
    case "$camera" in
        "frontyard") local url="$FRONTYARD_URL";;
        "backyard") local url="$BACKYARD_URL";;
        "living_room") local url="$LIVING_ROOM_URL";;
        "nursery") local url="$NURSERY_URL";;
        *) echo "Unknown camera: $camera"; return 1;;
    esac
    
    echo "Starting stream for $camera..."
    
    # Ensure directory exists
    mkdir -p "$SEGMENT_DIR/$camera"
    
    # Clean up old files
    rm -f "$SEGMENT_DIR/$camera"/*.ts "$SEGMENT_DIR/$camera"/playlist.m3u8
    
    # Start FFmpeg process
    nohup ffmpeg \
        -hide_banner -loglevel warning \
        -fflags +genpts+discardcorrupt \
        -rtsp_transport tcp \
        -timeout 10000000 \
        -i "$url" \
        -c:v libx264 -preset veryfast -tune zerolatency \
        -profile:v baseline -level 3.1 -pix_fmt yuv420p \
        -s 960x540 -b:v 1000k -maxrate 1200k -bufsize 600k \
        -g 30 -keyint_min 15 -sc_threshold 0 \
        -c:a aac -b:a 64k -ar 44100 -ac 2 \
        -f hls -hls_time 4 -hls_list_size 6 \
        -hls_flags delete_segments+append_list+independent_segments \
        -hls_segment_type mpegts -hls_playlist_type event \
        -hls_segment_filename "$SEGMENT_DIR/$camera/segment_%05d.ts" \
        "$SEGMENT_DIR/$camera/playlist.m3u8" \
        > "$PID_DIR/${camera}.log" 2>&1 &
    
    local ffmpeg_pid=$!
    echo "$ffmpeg_pid" > "$PID_DIR/${camera}.pid"
    touch "$PID_DIR/${camera}.lastaccess"
    
    echo "Started $camera with PID $ffmpeg_pid"
    return 0
}

# Function to stop a camera stream
stop_camera() {
    local camera="$1"
    local pid_file="$PID_DIR/${camera}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null
            fi
        fi
        rm -f "$pid_file" "$PID_DIR/${camera}.lastaccess"
        rm -f "$SEGMENT_DIR/$camera"/*.ts "$SEGMENT_DIR/$camera"/playlist.m3u8
    fi
    echo "Stopped $camera"
}

# Function to check if stream is running
is_running() {
    local camera="$1"
    local pid_file="$PID_DIR/${camera}.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    return 1
}

# Function to cleanup stale streams
cleanup_stale() {
    local current_time=$(date +%s)
    
    for camera in frontyard backyard living_room nursery; do
        local access_file="$PID_DIR/${camera}.lastaccess"
        
        if [ -f "$access_file" ] && is_running "$camera"; then
            local access_time=$(date -r "$access_file" +%s)
            local age=$((current_time - access_time))
            
            if [ $age -gt $STREAM_TIMEOUT ]; then
                echo "Stream $camera is stale (${age}s), stopping..."
                stop_camera "$camera"
            fi
        fi
    done
}

# Simple HTTP server using netcat
http_server() {
    local port=8080
    echo "Starting HTTP API on port $port..."
    
    while true; do
        # Process one request
        {
            read -r request_line
            echo "$request_line" | grep -E "^(GET|POST)" > /tmp/request.log
            
            # Skip headers
            while read -r line && [ "$line" != $'\r' ]; do
                :
            done
            
            # Parse request
            local method=$(echo "$request_line" | cut -d' ' -f1)
            local path=$(echo "$request_line" | cut -d' ' -f2)
            
            # Response headers
            echo -e "HTTP/1.1 200 OK\r"
            echo -e "Content-Type: application/json\r"
            echo -e "Access-Control-Allow-Origin: *\r"
            echo -e "\r"
            
            # Handle requests
            case "$path" in
                "/api/stream/frontyard/start") start_camera "frontyard"; echo '{"status":"ok"}';;
                "/api/stream/backyard/start") start_camera "backyard"; echo '{"status":"ok"}';;
                "/api/stream/living_room/start") start_camera "living_room"; echo '{"status":"ok"}';;
                "/api/stream/nursery/start") start_camera "nursery"; echo '{"status":"ok"}';;
                "/api/stream/frontyard/stop") stop_camera "frontyard"; echo '{"status":"ok"}';;
                "/api/stream/backyard/stop") stop_camera "backyard"; echo '{"status":"ok"}';;
                "/api/stream/living_room/stop") stop_camera "living_room"; echo '{"status":"ok"}';;
                "/api/stream/nursery/stop") stop_camera "nursery"; echo '{"status":"ok"}';;
                "/api/stream/frontyard/access") touch "$PID_DIR/frontyard.lastaccess"; echo '{"status":"ok"}';;
                "/api/stream/backyard/access") touch "$PID_DIR/backyard.lastaccess"; echo '{"status":"ok"}';;
                "/api/stream/living_room/access") touch "$PID_DIR/living_room.lastaccess"; echo '{"status":"ok"}';;
                "/api/stream/nursery/access") touch "$PID_DIR/nursery.lastaccess"; echo '{"status":"ok"}';;
                "/api/status") echo '{"status":"active","service":"ffmpeg-streamer"}';;
                *) echo '{"status":"error","message":"Unknown endpoint"}';;
            esac
        } | nc -l -p $port -q 1
        
        sleep 0.1
    done
}

# Cleanup daemon
cleanup_daemon() {
    while true; do
        sleep 30
        cleanup_stale
    done &
    echo $! > "$PID_DIR/cleanup.pid"
}

# Handle signals
trap 'pkill -P $$; exit 0' SIGTERM SIGINT

# Main execution
case "${1:-daemon}" in
    "start")
        start_camera "$2"
        ;;
    "stop")
        if [ -n "$2" ]; then
            stop_camera "$2"
        else
            for cam in frontyard backyard living_room nursery; do
                stop_camera "$cam"
            done
        fi
        ;;
    "status")
        echo "Stream Status:"
        for cam in frontyard backyard living_room nursery; do
            if is_running "$cam"; then
                echo "  $cam: RUNNING"
            else
                echo "  $cam: STOPPED"
            fi
        done
        ;;
    "daemon")
        cleanup_daemon
        http_server
        ;;
    *)
        echo "Usage: $0 {start <camera>|stop [camera]|status|daemon}"
        echo "Cameras: frontyard backyard living_room nursery"
        ;;
esac 