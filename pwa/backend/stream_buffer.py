import threading
import time
import requests
import logging
from typing import Dict, Set
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class StreamBuffer:
    """
    Maintains persistent connections to go2rtc streams to keep transcoding alive.
    This ensures HLS streams remain available for frontend consumption through
    Cloudflare tunnels where WebRTC is not supported.
    """
    
    def __init__(self, go2rtc_host="http://172.18.0.1:1984", buffer_duration=30):
        self.go2rtc_host = go2rtc_host
        self.buffer_duration = buffer_duration  # Keep streams alive for 30 seconds after last request
        self.active_streams: Dict[str, dict] = {}  # stream_name -> {last_access, consumer_thread, stop_event}
        self.cleanup_interval = 10  # Check for stale streams every 10 seconds
        self.running = True
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.cleanup_thread.start()
        
        logger.info("StreamBuffer initialized with %d second buffer duration", buffer_duration)
    
    def ensure_stream_active(self, stream_name: str) -> bool:
        """
        Ensure a stream is actively being consumed to keep go2rtc transcoding alive.
        Returns True if stream is active, False if failed to start.
        """
        try:
            # Update last access time
            current_time = datetime.now()
            
            if stream_name in self.active_streams:
                # Stream already active, just update access time
                self.active_streams[stream_name]['last_access'] = current_time
                logger.debug(f"Updated access time for active stream: {stream_name}")
                return True
            
            # Start new consumer for this stream
            logger.info(f"Starting new consumer for stream: {stream_name}")
            
            # Create stop event for this consumer
            stop_event = threading.Event()
            
            # Start consumer thread
            consumer_thread = threading.Thread(
                target=self._consume_stream,
                args=(stream_name, stop_event),
                daemon=True
            )
            consumer_thread.start()
            
            # Track the active stream
            self.active_streams[stream_name] = {
                'last_access': current_time,
                'consumer_thread': consumer_thread,
                'stop_event': stop_event,
                'started': current_time
            }
            
            logger.info(f"Successfully started consumer for stream: {stream_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure stream active for {stream_name}: {e}")
            return False
    
    def _consume_stream(self, stream_name: str, stop_event: threading.Event):
        """
        Continuously consume a stream to keep go2rtc transcoding active.
        Uses MSE endpoint which is more efficient than HLS for this purpose.
        """
        mse_url = f"{self.go2rtc_host}/api/stream.mp4?src={stream_name}"
        
        try:
            logger.info(f"Starting MSE consumer for {stream_name}: {mse_url}")
            
            # Use streaming request to keep connection alive
            session = requests.Session()
            
            while not stop_event.is_set() and self.running:
                try:
                    with session.get(mse_url, stream=True, timeout=30) as response:
                        response.raise_for_status()
                        
                        logger.debug(f"MSE consumer connected for {stream_name}")
                        
                        # Consume the stream in chunks to keep it alive
                        for chunk in response.iter_content(chunk_size=8192):
                            if stop_event.is_set() or not self.running:
                                break
                            
                            # We don't need to store the chunks, just consume them
                            # This keeps go2rtc transcoding active
                            pass
                            
                except requests.RequestException as e:
                    if not stop_event.is_set() and self.running:
                        logger.warning(f"MSE consumer error for {stream_name}: {e}")
                        # Wait before retrying
                        if not stop_event.wait(5):  # 5 second retry delay
                            continue
                    break
                    
        except Exception as e:
            logger.error(f"MSE consumer failed for {stream_name}: {e}")
        finally:
            logger.info(f"MSE consumer stopped for {stream_name}")
            session.close()
    
    def _cleanup_loop(self):
        """
        Periodically clean up stale streams that haven't been accessed recently.
        """
        while self.running:
            try:
                current_time = datetime.now()
                stale_streams = []
                
                for stream_name, stream_info in self.active_streams.items():
                    last_access = stream_info['last_access']
                    time_since_access = current_time - last_access
                    
                    if time_since_access > timedelta(seconds=self.buffer_duration):
                        stale_streams.append(stream_name)
                
                # Stop stale streams
                for stream_name in stale_streams:
                    self._stop_stream(stream_name)
                
                if stale_streams:
                    logger.info(f"Cleaned up {len(stale_streams)} stale streams: {stale_streams}")
                
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
            
            # Wait before next cleanup
            time.sleep(self.cleanup_interval)
    
    def _stop_stream(self, stream_name: str):
        """
        Stop consuming a specific stream.
        """
        try:
            if stream_name in self.active_streams:
                stream_info = self.active_streams[stream_name]
                
                # Signal the consumer thread to stop
                stream_info['stop_event'].set()
                
                # Wait for thread to finish (with timeout)
                stream_info['consumer_thread'].join(timeout=5)
                
                # Remove from active streams
                del self.active_streams[stream_name]
                
                logger.info(f"Stopped stream consumer: {stream_name}")
                
        except Exception as e:
            logger.error(f"Error stopping stream {stream_name}: {e}")
    
    def stop_all_streams(self):
        """
        Stop all active stream consumers.
        """
        logger.info("Stopping all stream consumers...")
        self.running = False
        
        # Stop all active streams
        stream_names = list(self.active_streams.keys())
        for stream_name in stream_names:
            self._stop_stream(stream_name)
        
        logger.info("All stream consumers stopped")
    
    def get_status(self) -> dict:
        """
        Get status of all active streams.
        """
        current_time = datetime.now()
        status = {
            'active_streams': len(self.active_streams),
            'buffer_duration': self.buffer_duration,
            'streams': {}
        }
        
        for stream_name, stream_info in self.active_streams.items():
            last_access = stream_info['last_access']
            started = stream_info['started']
            time_since_access = current_time - last_access
            uptime = current_time - started
            
            status['streams'][stream_name] = {
                'last_access_seconds_ago': time_since_access.total_seconds(),
                'uptime_seconds': uptime.total_seconds(),
                'thread_alive': stream_info['consumer_thread'].is_alive()
            }
        
        return status

# Global stream buffer instance
stream_buffer = None

def get_stream_buffer() -> StreamBuffer:
    """
    Get the global stream buffer instance, creating it if necessary.
    """
    global stream_buffer
    if stream_buffer is None:
        stream_buffer = StreamBuffer()
    return stream_buffer

def shutdown_stream_buffer():
    """
    Shutdown the global stream buffer instance.
    """
    global stream_buffer
    if stream_buffer is not None:
        stream_buffer.stop_all_streams()
        stream_buffer = None 