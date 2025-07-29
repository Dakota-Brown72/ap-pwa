import os
import logging
import sqlite3
import requests
import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify, Response, send_from_directory, send_file
from flask_cors import CORS
from stream_buffer import get_stream_buffer, shutdown_stream_buffer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# CORS configuration - domains from environment variable
cors_origins = os.getenv('CORS_ORIGINS', 'http://localhost:5173,http://localhost:3000').split(',')
CORS(app, origins=cors_origins, supports_credentials=True)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
DATABASE_PATH = os.getenv('DATABASE_PATH', '/data/anchorpoint.db')
FRIGATE_HOST = os.getenv('FRIGATE_HOST', 'http://frigate:5000')
GO2RTC_HOST = os.getenv('GO2RTC_HOST', 'http://frigate:1984')
HLS_SEGMENTS_PATH = os.getenv('HLS_SEGMENTS_PATH', '/segments')
FFMPEG_SERVICE_HOST = os.getenv('FFMPEG_SERVICE_HOST', 'http://ffmpeg-streamer:8080')  # On-demand FFmpeg service

# Database helper functions
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def verify_password(plain_password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_token(user_id):
    """Create JWT token"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

# On-demand FFmpeg streaming functions
def start_ffmpeg_stream(camera_id):
    """Start FFmpeg stream for a camera via the on-demand service"""
    try:
        response = requests.post(f"{FFMPEG_SERVICE_HOST}/api/stream/{camera_id}/start", timeout=10)
        logger.info(f"Started FFmpeg stream for {camera_id} - Response: {response.status_code}")
        return True  # Consider success if we get any response
    except Exception as e:
        logger.error(f"Error starting FFmpeg stream for {camera_id}: {e}")
        return False

def stop_ffmpeg_stream(camera_id):
    """Stop FFmpeg stream for a camera via the on-demand service"""
    try:
        response = requests.post(f"{FFMPEG_SERVICE_HOST}/api/stream/{camera_id}/stop", timeout=10)
        logger.info(f"Stopped FFmpeg stream for {camera_id} - Response: {response.status_code}")
        return True  # Consider success if we get any response
    except Exception as e:
        logger.error(f"Error stopping FFmpeg stream for {camera_id}: {e}")
        return False

def update_ffmpeg_access(camera_id):
    """Update access time for FFmpeg stream to keep it alive"""
    try:
        response = requests.post(f"{FFMPEG_SERVICE_HOST}/api/stream/{camera_id}/access", timeout=5)
        logger.debug(f"Updated FFmpeg access time for {camera_id}")
        return True  # Consider success if we get any response
    except Exception as e:
        logger.warning(f"Error updating FFmpeg access time for {camera_id}: {e}")
        return False

def get_ffmpeg_stream_status(camera_id):
    """Get FFmpeg stream status for a camera"""
    try:
        response = requests.get(f"{FFMPEG_SERVICE_HOST}/api/stream/{camera_id}/status", timeout=5)
        return True  # Consider running if we get any response
    except Exception as e:
        logger.warning(f"Error checking FFmpeg stream status for {camera_id}: {e}")
        return False

def init_database():
    """Initialize database with hardcoded user and security tables"""
    try:
        conn = get_db_connection()
        
        # Create users table if it doesn't exist
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                full_name TEXT,
                is_admin BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Create login attempts table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address VARCHAR(45) NOT NULL,
                username VARCHAR(50),
                success BOOLEAN NOT NULL DEFAULT FALSE,
                attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_agent TEXT
            )
        ''')
        
        # Create blocked IPs table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS blocked_ips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address VARCHAR(45) NOT NULL UNIQUE,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                blocked_until TIMESTAMP NOT NULL,
                failed_attempts INTEGER NOT NULL,
                reason VARCHAR(100) DEFAULT 'Too many failed login attempts'
            )
        ''')
        
        # Create indexes for performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_login_attempts_time ON login_attempts(attempt_time)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_blocked_ips_address ON blocked_ips(ip_address)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_blocked_ips_until ON blocked_ips(blocked_until)')
        
        # Check if admin user exists
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        user = conn.execute('SELECT id FROM users WHERE username = ?', (admin_username,)).fetchone()
        
        if not user:
            # Create the default admin user from environment variables
            admin_username = os.getenv('ADMIN_USERNAME', 'admin')
            admin_password = os.getenv('ADMIN_PASSWORD', 'change-this-secure-password')
            admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
            admin_full_name = os.getenv('ADMIN_FULL_NAME', 'System Administrator')
            
            password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn.execute('''
                INSERT INTO users (username, password_hash, email, full_name, is_admin, is_active)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (admin_username, password_hash, admin_email, admin_full_name, True, True))
            logger.info(f"Created default admin user: {admin_username}")
        else:
            logger.info(f"Admin user {admin_username} already exists")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")

# Rate limiting configuration
MAX_LOGIN_ATTEMPTS = 4
BLOCK_DURATION_HOURS = 1

def get_client_ip():
    """Get client IP address, handling proxies and load balancers"""
    # Check for forwarded IP from reverse proxy
    if 'X-Forwarded-For' in request.headers:
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    elif 'X-Real-IP' in request.headers:
        return request.headers['X-Real-IP']
    else:
        return request.environ.get('REMOTE_ADDR', '127.0.0.1')

def cleanup_expired_blocks():
    """Clean up expired IP blocks and old login attempts"""
    try:
        conn = get_db_connection()
        
        # Remove expired blocks
        conn.execute('DELETE FROM blocked_ips WHERE blocked_until < CURRENT_TIMESTAMP')
        
        # Clean up old login attempts (older than 24 hours)
        conn.execute('''
            DELETE FROM login_attempts 
            WHERE attempt_time < datetime('now', '-24 hours')
        ''')
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error cleaning up expired blocks: {e}")

def is_ip_blocked(ip_address):
    """Check if an IP address is currently blocked"""
    try:
        conn = get_db_connection()
        blocked = conn.execute('''
            SELECT id FROM blocked_ips 
            WHERE ip_address = ? AND blocked_until > CURRENT_TIMESTAMP
        ''', (ip_address,)).fetchone()
        conn.close()
        
        return blocked is not None
        
    except Exception as e:
        logger.error(f"Error checking blocked IP: {e}")
        return False

def get_failed_attempts_count(ip_address, hours=1):
    """Get count of failed login attempts from an IP in the last N hours"""
    try:
        conn = get_db_connection()
        count = conn.execute('''
            SELECT COUNT(*) as count FROM login_attempts 
            WHERE ip_address = ? 
            AND success = FALSE 
            AND attempt_time > datetime('now', '-{} hours')
        '''.format(hours), (ip_address,)).fetchone()
        conn.close()
        
        return count['count'] if count else 0
        
    except Exception as e:
        logger.error(f"Error getting failed attempts count: {e}")
        return 0

def record_login_attempt(ip_address, username, success, user_agent=None):
    """Record a login attempt"""
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO login_attempts (ip_address, username, success, user_agent)
            VALUES (?, ?, ?, ?)
        ''', (ip_address, username, success, user_agent))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error recording login attempt: {e}")

def block_ip(ip_address, failed_attempts):
    """Block an IP address for the configured duration"""
    try:
        conn = get_db_connection()
        
        # Calculate block expiry time
        block_until = datetime.utcnow() + timedelta(hours=BLOCK_DURATION_HOURS)
        
        # Insert or update the block
        conn.execute('''
            INSERT OR REPLACE INTO blocked_ips 
            (ip_address, blocked_until, failed_attempts, reason)
            VALUES (?, ?, ?, ?)
        ''', (ip_address, block_until, failed_attempts, f'Too many failed login attempts ({failed_attempts})'))
        
        conn.commit()
        conn.close()
        
        logger.warning(f"Blocked IP {ip_address} for {BLOCK_DURATION_HOURS} hours after {failed_attempts} failed attempts")
        
    except Exception as e:
        logger.error(f"Error blocking IP {ip_address}: {e}")

def check_rate_limit(ip_address, username):
    """Check if the IP should be rate limited and handle blocking"""
    # Clean up expired blocks first
    cleanup_expired_blocks()
    
    # Check if IP is already blocked
    if is_ip_blocked(ip_address):
        return False, "IP address is temporarily blocked due to too many failed login attempts"
    
    # Get failed attempts count
    failed_count = get_failed_attempts_count(ip_address, hours=1)
    
    # If we're at the limit, this attempt will put us over
    if failed_count >= MAX_LOGIN_ATTEMPTS:
        return False, f"Too many failed login attempts. Please try again in {BLOCK_DURATION_HOURS} hour(s)"
    
    return True, None

# Initialize database on startup
init_database()

def auth_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check for token in Authorization header first
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        else:
            # For streaming endpoints, also check query parameters
            token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = payload['user_id']
            
            # Fetch user details from the database
            conn = get_db_connection()
            user = conn.execute('SELECT id, username, is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
            conn.close()

            if not user:
                return jsonify({'error': 'User not found'}), 401

            # Update last login timestamp
            conn = get_db_connection()
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (current_user_id,))
            conn.commit()
            conn.close()

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

# Authentication endpoints
@app.route('/api/auth/login', methods=['POST'])
def login():
    """User login endpoint with rate limiting"""
    client_ip = get_client_ip()
    user_agent = request.headers.get('User-Agent', '')
    username = None
    
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'error': 'Username and password are required'}), 400
        
        # Check rate limiting before processing login
        rate_limit_ok, rate_limit_message = check_rate_limit(client_ip, username)
        if not rate_limit_ok:
            logger.warning(f"Rate limit exceeded for IP {client_ip}, username: {username}")
            return jsonify({'error': rate_limit_message}), 429
        
        conn = get_db_connection()
        user = conn.execute('SELECT id, username, password_hash, is_admin, is_active FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        # Check if user exists and is active
        if not user or not user['is_active']:
            # Record failed attempt
            record_login_attempt(client_ip, username, False, user_agent)
            
            # Check if we need to block this IP
            failed_count = get_failed_attempts_count(client_ip, hours=1)
            if failed_count >= MAX_LOGIN_ATTEMPTS:
                block_ip(client_ip, failed_count)
                return jsonify({'error': f'Too many failed attempts. IP blocked for {BLOCK_DURATION_HOURS} hour(s)'}), 429
            
            remaining_attempts = MAX_LOGIN_ATTEMPTS - failed_count
            return jsonify({
                'error': 'Invalid credentials',
                'attempts_remaining': remaining_attempts
            }), 401

        # Verify password
        if not verify_password(password, user['password_hash']):
            # Record failed attempt
            record_login_attempt(client_ip, username, False, user_agent)
            
            # Check if we need to block this IP
            failed_count = get_failed_attempts_count(client_ip, hours=1)
            if failed_count >= MAX_LOGIN_ATTEMPTS:
                block_ip(client_ip, failed_count)
                return jsonify({'error': f'Too many failed attempts. IP blocked for {BLOCK_DURATION_HOURS} hour(s)'}), 429
            
            remaining_attempts = MAX_LOGIN_ATTEMPTS - failed_count
            return jsonify({
                'error': 'Invalid credentials',
                'attempts_remaining': remaining_attempts
            }), 401

        # Successful login
        record_login_attempt(client_ip, username, True, user_agent)
        
        token = create_token(user['id'])
        
        # Update last login
        conn = get_db_connection()
        conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (user['id'],))
        conn.commit()
        conn.close()
        
        logger.info(f"Successful login for user {username} from IP {client_ip}")
        
        return jsonify({
            'token': token,
            'user': {
                'id': user['id'],
                'username': user['username'],
                'is_admin': bool(user['is_admin'])
            }
        })
        
    except Exception as e:
        logger.error(f"Login error for IP {client_ip}, username {username}: {e}")
        # Record failed attempt even for server errors
        if username:
            record_login_attempt(client_ip, username, False, user_agent)
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
@auth_required
def logout(current_user_id):
    """User logout endpoint"""
    # In a more complete implementation, you'd invalidate the token
    # For now, just return success
    return jsonify({'message': 'Logged out successfully'})

@app.route('/api/auth/me', methods=['GET'])
@auth_required
def get_current_user(current_user_id):
    """Get current user information"""
    try:
        conn = get_db_connection()
        user = conn.execute('SELECT username, email, full_name, is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        conn.close()

        if not user:
            return jsonify({'error': 'User not found'}), 500

        return jsonify({
            'user': {
                'id': current_user_id,
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name'],
                'is_admin': bool(user['is_admin'])
            }
        })
        
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return jsonify({'error': 'Failed to get user information'}), 500

@app.route('/api/go2rtc/streams', methods=['GET'])
@auth_required
def get_go2rtc_streams(current_user_id):
    """Get go2rtc stream information"""
    try:
        response = requests.get(f"{GO2RTC_HOST}/api/streams", timeout=10)
        response.raise_for_status()
        return jsonify(response.json())
    except requests.RequestException as e:
        logger.error(f"Failed to fetch go2rtc streams: {e}")
        return jsonify({'error': 'Failed to fetch stream information'}), 500

@app.route('/api/stream-buffer/status', methods=['GET'])
@auth_required
def get_stream_buffer_status(current_user_id):
    """Get stream buffer status"""
    try:
        buffer = get_stream_buffer()
        status = buffer.get_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Failed to get stream buffer status: {e}")
        return jsonify({'error': 'Failed to get buffer status'}), 500



@app.route('/api/cameras/<camera_id>/stream/mse', methods=['GET'])
@auth_required
def get_camera_mse_stream(current_user_id, camera_id):
    """Get MSE stream URL for a camera"""
    try:
        camera_stream_mapping = {
            'frontyard': 'Frontyard_live',
            'backyard': 'Backyard_live',
            'living_room': 'Living_Room_live',
            'nursery': 'Nursery_live'
        }

        stream_name = camera_stream_mapping.get(camera_id.lower())
        if not stream_name:
            return jsonify({'error': f'Unknown camera: {camera_id}'}), 404

        mse_url = f"/api/go2rtc/mse/{stream_name}"

        return jsonify({
            'camera_id': camera_id,
            'stream_name': stream_name,
            'mse_url': mse_url,
            'type': 'mse'
        })

    except Exception as e:
        logger.error(f"Failed to get MSE stream for {camera_id}: {e}")
        return jsonify({'error': 'Failed to get MSE stream'}), 500



@app.route('/api/go2rtc/mse/<stream_name>', methods=['GET'])
@auth_required
def proxy_go2rtc_mse(current_user_id, stream_name):
    """Proxy go2rtc MSE streams with proper connection cleanup and mobile optimization"""
    try:
        url = f"{GO2RTC_HOST}/api/stream.mp4?src={stream_name}"

        headers = {
            'Accept': 'video/mp4',
            'Range': request.headers.get('Range', 'bytes=0-')
        }

        session = requests.Session()

        try:
            # Stream the response from go2rtc with longer timeout for NVENC transcoding
            response = session.get(url, headers=headers, stream=True, timeout=60)
            response.raise_for_status()

            return_headers = {
                'Content-Type': response.headers.get('Content-Type', 'video/mp4'),
                'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Range, Origin, Accept-Encoding, Content-Type',
                'Access-Control-Expose-Headers': 'Content-Length, Content-Range',
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY'
            }

            if 'Content-Range' in response.headers:
                return_headers['Content-Range'] = response.headers['Content-Range']
            if 'Content-Length' in response.headers:
                return_headers['Content-Length'] = response.headers['Content-Length']
            if 'Accept-Ranges' in response.headers:
                return_headers['Accept-Ranges'] = response.headers['Accept-Ranges']

            def generate():
                try:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                except Exception as e:
                    logger.error(f"Error streaming MSE data for {stream_name}: {e}")
                finally:
                    try:
                        response.close()
                        session.close()
                    except:
                        pass

            return Response(generate(), status=response.status_code, headers=return_headers)

        except Exception as e:
            try:
                session.close()
            except:
                pass
            raise e

    except requests.RequestException as e:
        logger.error(f"MSE proxy error for {stream_name}: {e}")
        return jsonify({'error': 'Failed to fetch MSE stream'}), 500

# WebRTC endpoints removed - now using MP4 streaming for better iOS compatibility

# All WebRTC proxy endpoints removed - using MP4 streaming only

# WebRTC subscription endpoints removed - MP4 streaming doesn't require subscriptions

@app.route('/api/cameras', methods=['GET'])
@auth_required
def get_cameras(current_user_id):
    """Get camera list - now requires authentication"""
    return get_authenticated_cameras(current_user_id)

@app.route('/api/cameras/start-streaming', methods=['POST'])
@auth_required
def start_all_camera_streaming(current_user_id):
    """Start on-demand streaming for all cameras when client accesses multiview"""
    try:
        # Get camera list
        response = requests.get(f"{FRIGATE_HOST}/api/config", timeout=10)
        response.raise_for_status()
        config = response.json()
        
        cameras = config.get('cameras', {})
        started_streams = []
        failed_streams = []
        
        for camera_name in cameras.keys():
            camera_id = camera_name.lower()  # Convert to lowercase for FFmpeg service
            if start_ffmpeg_stream(camera_id):
                started_streams.append(camera_id)
                # Also ensure go2rtc stream is active
                buffer = get_stream_buffer()
                buffer.ensure_stream_active(f"{camera_name}_live")
            else:
                failed_streams.append(camera_id)
        
        logger.info(f"Started streaming for {len(started_streams)} cameras: {started_streams}")
        if failed_streams:
            logger.warning(f"Failed to start streaming for {len(failed_streams)} cameras: {failed_streams}")
        
        return jsonify({
            'status': 'success',
            'started_streams': started_streams,
            'failed_streams': failed_streams,
            'message': f'Started streaming for {len(started_streams)} cameras'
        })
        
    except Exception as e:
        logger.error(f"Error starting camera streaming: {e}")
        return jsonify({'error': 'Failed to start camera streaming'}), 500

@app.route('/api/cameras/stop-streaming', methods=['POST'])
@auth_required  
def stop_all_camera_streaming(current_user_id):
    """Stop on-demand streaming for all cameras when client leaves multiview"""
    try:
        # Get camera list
        response = requests.get(f"{FRIGATE_HOST}/api/config", timeout=10)
        response.raise_for_status()
        config = response.json()
        
        cameras = config.get('cameras', {})
        stopped_streams = []
        
        for camera_name in cameras.keys():
            camera_id = camera_name.lower()  # Convert to lowercase for FFmpeg service
            if stop_ffmpeg_stream(camera_id):
                stopped_streams.append(camera_id)
        
        logger.info(f"Stopped streaming for {len(stopped_streams)} cameras: {stopped_streams}")
        
        return jsonify({
            'status': 'success',
            'stopped_streams': stopped_streams,
            'message': f'Stopped streaming for {len(stopped_streams)} cameras'
        })
        
    except Exception as e:
        logger.error(f"Error stopping camera streaming: {e}")
        return jsonify({'error': 'Failed to stop camera streaming'}), 500

@app.route('/api/cameras/<camera_id>/start-stream', methods=['POST'])
@auth_required
def start_single_camera_stream(current_user_id, camera_id):
    """Start streaming for a single camera"""
    try:
        if start_ffmpeg_stream(camera_id.lower()):
            # Also ensure go2rtc stream is active
            buffer = get_stream_buffer()
            buffer.ensure_stream_active(f"{camera_id}_live")
            
            return jsonify({
                'status': 'success',
                'camera': camera_id,
                'message': f'Started streaming for {camera_id}'
            })
        else:
            return jsonify({
                'status': 'error',
                'camera': camera_id,
                'message': f'Failed to start streaming for {camera_id}'
            }), 500
            
    except Exception as e:
        logger.error(f"Error starting stream for {camera_id}: {e}")
        return jsonify({'error': f'Failed to start stream for {camera_id}'}), 500

@app.route('/api/cameras/<camera_id>/keep-alive', methods=['POST'])
@auth_required
def keep_camera_stream_alive(current_user_id, camera_id):
    """Keep camera stream alive by updating access time"""
    try:
        # Update FFmpeg stream access time
        ffmpeg_updated = update_ffmpeg_access(camera_id.lower())
        
        # Update go2rtc stream access time
        buffer = get_stream_buffer()
        buffer.ensure_stream_active(f"{camera_id}_live")
        
        return jsonify({
            'status': 'success',
            'camera': camera_id,
            'ffmpeg_updated': ffmpeg_updated,
            'message': f'Updated access time for {camera_id}'
        })
        
    except Exception as e:
        logger.error(f"Error keeping stream alive for {camera_id}: {e}")
        return jsonify({'error': f'Failed to keep stream alive for {camera_id}'}), 500

@app.route('/api/public/cameras', methods=['GET'])
def get_public_cameras():
    """Get camera list for public access - DEPRECATED, use /api/cameras instead"""
    # This endpoint should be deprecated in favor of authenticated access
    # For now, return a limited response
    return jsonify({'error': 'Authentication required', 'message': 'Please use /api/cameras with authentication'}), 401

def get_authenticated_cameras(current_user_id):
    """Get camera list for authenticated users"""
    try:
        # Get Frigate config
        response = requests.get(f"{FRIGATE_HOST}/api/config", timeout=10)
        response.raise_for_status()
        config = response.json()

        cameras = []
        if 'cameras' in config:
            for camera_name, camera_config in config['cameras'].items():
                # Use correct snapshot endpoint (no /api prefix since frontend adds it)
                snapshot_url = f"/camera/{camera_name}/snapshot"

                camera_data = {
                    'id': camera_name,
                    'name': camera_name.replace('_', ' ').title(),
                    'snapshot_url': snapshot_url,
                    # Provide both MP4 and HLS for adaptive streaming
                    'mp4_url': f'/api/camera/{camera_name}/stream.mp4',
                    'hls_url': f'/api/camera/{camera_name}/stream.m3u8',
                    # Additional streaming format info for frontend
                    'adaptive_urls': {
                        'mp4': f'/api/camera/{camera_name}/stream.mp4',
                        'hls': f'/api/camera/{camera_name}/stream.m3u8'
                    }
                }
                
                logger.info(f"Generated camera config for {camera_name}: {camera_data}")
                cameras.append(camera_data)

            # Pre-activate streams to ensure they're ready for frontend
            buffer = get_stream_buffer()
            for camera_data in cameras:
                stream_name = f"{camera_data['id']}_live"
                buffer.ensure_stream_active(stream_name)
                logger.debug(f"Pre-activated stream: {stream_name}")

            logger.info(f"Returning {len(cameras)} cameras to frontend with pre-activated streams")
            return jsonify({
                'cameras': cameras
            })
        else:
            logger.warning("No cameras found in Frigate config")
            return jsonify({'cameras': []}), 200

    except Exception as e:
        logger.error(f"Error getting cameras: {e}")
        return jsonify({'error': 'Failed to get camera list'}), 500

@app.route('/api/camera/<camera_id>/stream.mp4', methods=['GET'])
def get_camera_mp4_stream(camera_id):
    """Get authenticated MP4 stream for a camera - supports both header and query token auth"""
    try:
        # Check for token in Authorization header first
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        else:
            # For video elements, check query parameters
            token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Validate the token
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = payload['user_id']
            logger.info(f"Video stream authenticated for user {current_user_id}")
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        # Map camera ID to stream name
        stream_name = f"{camera_id}_live"
        
        # Build go2rtc URL
        go2rtc_url = f"{GO2RTC_HOST}/api/stream.mp4?src={stream_name}"
        
        # Add any query parameters from the original request (like cache buster)
        if request.query_string:
            go2rtc_url += f"&{request.query_string.decode()}"
        
        # FORCE desktop User-Agent to prevent go2rtc mobile redirects
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': request.headers.get('Accept', '*/*'),
            'Range': request.headers.get('Range', '')
        }
        
        # Remove empty headers
        headers = {k: v for k, v in headers.items() if v}
        
        logger.info(f"Proxying authenticated MP4 stream: {camera_id} -> {stream_name}")
        
        # Stream the response from go2rtc
        response = requests.get(go2rtc_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # Return streaming response with proper headers
        def generate():
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
        
        # Build response headers, excluding empty ones
        response_headers = {
            'Content-Type': response.headers.get('Content-Type', 'video/mp4'),
            'Accept-Ranges': 'bytes',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Expose-Headers': 'Accept-Ranges, Content-Length, Content-Range',
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'X-Content-Type-Options': 'nosniff'
        }
        
        # Only add Content-Length and Content-Range if they exist
        if response.headers.get('Content-Length'):
            response_headers['Content-Length'] = response.headers.get('Content-Length')
        if response.headers.get('Content-Range'):
            response_headers['Content-Range'] = response.headers.get('Content-Range')
            
        return Response(
            generate(),
            status=response.status_code,
            headers=response_headers
        )
        
    except requests.RequestException as e:
        logger.error(f"MP4 stream proxy error for {camera_id}: {e}")
        return jsonify({'error': 'Stream unavailable'}), 503
    except Exception as e:
        logger.error(f"Unexpected MP4 stream error for {camera_id}: {e}")
        return jsonify({'error': 'Stream failed'}), 500

@app.route('/api/camera/<camera_id>/stream.m3u8', methods=['GET'])
def get_camera_hls_playlist(camera_id):
    """Get authenticated HLS playlist for a camera - served from FFmpeg-generated files"""
    try:
        # Check for token in Authorization header first
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        else:
            # For video elements, check query parameters
            token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Validate the token
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = payload['user_id']
            logger.info(f"HLS playlist authenticated for user {current_user_id}")
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Map camera ID to directory name (convert to lowercase, keep underscores)
        camera_lowercase = camera_id.lower()
        
        # Try to update FFmpeg access time (best effort)
        try:
            update_ffmpeg_access(camera_lowercase)
        except:
            pass  # Ignore FFmpeg service API issues
        
        # Map camera ID to directory name (convert to lowercase, keep underscores)
        camera_dir = camera_lowercase
        playlist_path = os.path.join(HLS_SEGMENTS_PATH, camera_dir, 'playlist.m3u8')
        
        # Check if playlist file exists (wait up to 10 seconds for it to appear)
        max_wait = 10
        wait_count = 0
        while not os.path.exists(playlist_path) and wait_count < max_wait:
            time.sleep(1)
            wait_count += 1
        
        if not os.path.exists(playlist_path):
            logger.error(f"HLS playlist not found after {max_wait}s: {playlist_path}")
            return jsonify({'error': 'Stream not ready yet, please try again in a few seconds'}), 503
        
        logger.info(f"Serving HLS playlist for {camera_id}: {playlist_path}")
        
        # Read playlist and modify segment URLs to include authentication
        try:
            with open(playlist_path, 'r') as f:
                playlist_content = f.read()
            
            # Modify segment URLs to include token
            lines = playlist_content.split('\n')
            modified_lines = []
            
            for line in lines:
                if line.endswith('.ts'):
                    # Add authentication token to segment URL
                    auth_url = f"/api/camera/{camera_id}/hls/{line}?token={token}"
                    modified_lines.append(auth_url)
                else:
                    modified_lines.append(line)
            
            modified_playlist = '\n'.join(modified_lines)
            
            # Return playlist with proper headers
            response_headers = {
                'Content-Type': 'application/vnd.apple.mpegurl',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Expose-Headers': 'Content-Length',
                'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
            
            return Response(
                modified_playlist,
                status=200,
                headers=response_headers
            )
            
        except IOError as e:
            logger.error(f"Error reading HLS playlist {playlist_path}: {e}")
            return jsonify({'error': 'Failed to read playlist'}), 500
        
    except Exception as e:
        logger.error(f"Unexpected HLS playlist error for {camera_id}: {e}")
        return jsonify({'error': 'HLS playlist failed'}), 500

@app.route('/api/camera/<camera_id>/hls/<segment>', methods=['GET'])
def get_camera_hls_segment(camera_id, segment):
    """Get authenticated HLS segment for a camera - served from FFmpeg-generated files"""
    try:
        # Check for token in Authorization header first
        token = request.headers.get('Authorization')
        if token and token.startswith('Bearer '):
            token = token[7:]
        else:
            # For segment requests, check query parameters
            token = request.args.get('token')
        
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Validate the token
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user_id = payload['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        
        # Update FFmpeg access time to keep stream alive
        camera_lowercase = camera_id.lower()
        update_ffmpeg_access(camera_lowercase)
        
        # Security: Only allow .ts files and basic filename validation
        if not segment.endswith('.ts') or '/' in segment or '..' in segment:
            logger.warning(f"Invalid segment request: {segment}")
            return jsonify({'error': 'Invalid segment'}), 400
        
        # Map camera ID to directory name (convert to lowercase)
        camera_dir = camera_lowercase
        segment_path = os.path.join(HLS_SEGMENTS_PATH, camera_dir, segment)
        
        # Check if segment file exists
        if not os.path.exists(segment_path):
            logger.warning(f"HLS segment not found: {segment_path}")
            return jsonify({'error': 'Segment not found'}), 404
        
        logger.debug(f"Serving HLS segment for {camera_id}: {segment}")
        
        # Serve the segment file directly
        response_headers = {
            'Content-Type': 'video/mp2t',  # MPEG-2 Transport Stream
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Expose-Headers': 'Accept-Ranges, Content-Length',
            'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
            'Accept-Ranges': 'bytes'
        }
        
        return send_file(
            segment_path,
            mimetype='video/mp2t',
            as_attachment=False,
            conditional=True  # Support range requests
        )
        
    except Exception as e:
        logger.error(f"Unexpected HLS segment error for {camera_id}/{segment}: {e}")
        return jsonify({'error': 'HLS segment failed'}), 500

@app.route('/api/camera/<camera_id>/snapshot', methods=['GET'])
@auth_required  
def get_camera_snapshot(current_user_id, camera_id):
    """Get latest snapshot for a camera - requires authentication"""
    try:
        # Get snapshot from Frigate - use correct API endpoint
        response = requests.get(f"{FRIGATE_HOST}/api/{camera_id}/latest.jpg", timeout=10)
        response.raise_for_status()

        # Add security headers
        headers = {
            'Content-Type': 'image/jpeg',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'X-Content-Type-Options': 'nosniff'
        }

        return Response(response.content, headers=headers)

    except requests.RequestException as e:
        logger.error(f"Error getting snapshot for {camera_id}: {e}")
        return jsonify({'error': 'Failed to get camera snapshot'}), 500

@app.route('/api/public/camera/<camera_id>/snapshot', methods=['GET'])
def get_public_camera_snapshot(camera_id):
    """DEPRECATED: Use /api/camera/<camera_id>/snapshot with authentication"""
    return jsonify({'error': 'Authentication required', 'message': 'Please use /api/camera/<camera_id>/snapshot with authentication'}), 401

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

# Admin endpoints for security management
@app.route('/api/admin/security/blocked-ips', methods=['GET'])
@auth_required
def get_blocked_ips(current_user_id):
    """Get list of blocked IP addresses (admin only)"""
    try:
        # Check if user is admin
        conn = get_db_connection()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        
        if not user or not user['is_admin']:
            conn.close()
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get blocked IPs
        blocked_ips = conn.execute('''
            SELECT ip_address, blocked_at, blocked_until, failed_attempts, reason
            FROM blocked_ips 
            WHERE blocked_until > CURRENT_TIMESTAMP
            ORDER BY blocked_at DESC
        ''').fetchall()
        
        conn.close()
        
        blocked_list = []
        for ip in blocked_ips:
            blocked_list.append({
                'ip_address': ip['ip_address'],
                'blocked_at': ip['blocked_at'],
                'blocked_until': ip['blocked_until'],
                'failed_attempts': ip['failed_attempts'],
                'reason': ip['reason']
            })
        
        return jsonify({'blocked_ips': blocked_list})
        
    except Exception as e:
        logger.error(f"Error getting blocked IPs: {e}")
        return jsonify({'error': 'Failed to get blocked IPs'}), 500

@app.route('/api/admin/security/unblock-ip', methods=['POST'])
@auth_required
def unblock_ip(current_user_id):
    """Unblock an IP address (admin only)"""
    try:
        # Check if user is admin
        conn = get_db_connection()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        
        if not user or not user['is_admin']:
            conn.close()
            return jsonify({'error': 'Admin access required'}), 403
        
        data = request.get_json()
        ip_address = data.get('ip_address')
        
        if not ip_address:
            conn.close()
            return jsonify({'error': 'IP address is required'}), 400
        
        # Remove the IP from blocked list
        result = conn.execute('DELETE FROM blocked_ips WHERE ip_address = ?', (ip_address,))
        conn.commit()
        conn.close()
        
        if result.rowcount > 0:
            logger.info(f"Admin unblocked IP: {ip_address}")
            return jsonify({'message': f'IP {ip_address} has been unblocked'})
        else:
            return jsonify({'error': 'IP address not found in blocked list'}), 404
        
    except Exception as e:
        logger.error(f"Error unblocking IP: {e}")
        return jsonify({'error': 'Failed to unblock IP'}), 500

@app.route('/api/admin/security/login-attempts', methods=['GET'])
@auth_required
def get_login_attempts(current_user_id):
    """Get recent login attempts (admin only)"""
    try:
        # Check if user is admin
        conn = get_db_connection()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        
        if not user or not user['is_admin']:
            conn.close()
            return jsonify({'error': 'Admin access required'}), 403
        
        # Get recent login attempts (last 24 hours)
        attempts = conn.execute('''
            SELECT ip_address, username, success, attempt_time, user_agent
            FROM login_attempts 
            WHERE attempt_time > datetime('now', '-24 hours')
            ORDER BY attempt_time DESC
            LIMIT 100
        ''').fetchall()
        
        conn.close()
        
        attempts_list = []
        for attempt in attempts:
            attempts_list.append({
                'ip_address': attempt['ip_address'],
                'username': attempt['username'],
                'success': bool(attempt['success']),
                'attempt_time': attempt['attempt_time'],
                'user_agent': attempt['user_agent']
            })
        
        return jsonify({'login_attempts': attempts_list})
        
    except Exception as e:
        logger.error(f"Error getting login attempts: {e}")
        return jsonify({'error': 'Failed to get login attempts'}), 500





@app.route('/api/go2rtc/mse/<stream_name>', methods=['OPTIONS'])
def cors_preflight_mse(stream_name):
    """Handle CORS preflight requests for MSE streams"""
    headers = {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, OPTIONS',
        'Access-Control-Allow-Headers': 'Range, Origin, Accept-Encoding, Content-Type, Authorization',
        'Access-Control-Max-Age': '86400',
    }
    return '', 204, headers

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up database connections"""
    pass

def cleanup():
    """Clean up resources when app shuts down"""
    shutdown_stream_buffer()

import atexit
import threading
import time

def periodic_cleanup():
    """Periodically clean up expired blocks and old login attempts"""
    while True:
        try:
            cleanup_expired_blocks()
            time.sleep(3600)  # Run every hour
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

# Start background cleanup thread
cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()

atexit.register(cleanup)

if __name__ == '__main__':
    # Disable debug mode in production
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5003, debug=debug_mode)