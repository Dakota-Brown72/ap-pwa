import os
import logging
import sqlite3
import requests
import jwt
import bcrypt
import subprocess
import shutil
from pathlib import Path
import ipaddress
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
GEOIP_PROVIDER = os.getenv('GEOIP_PROVIDER', 'disabled')  # 'disabled' or 'ipapi'

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
        
        # IP geolocation cache table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ip_geo_cache (
                ip_address VARCHAR(45) PRIMARY KEY,
                country TEXT,
                region TEXT,
                city TEXT,
                lat REAL,
                lon REAL,
                isp TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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

# Safe startup migration: relax unique constraint on users.email if present

def relax_users_email_unique_constraint():
    """Drop UNIQUE index on users.email if it exists, without rebuilding the table.
    This avoids UNIQUE constraint failures when inserting placeholder/empty emails
    until real email collection is implemented.
    """
    try:
        conn = get_db_connection()
        try:
            indexes = conn.execute('PRAGMA index_list(users)').fetchall()
            for idx in indexes or []:
                try:
                    idx_name = idx['name'] if isinstance(idx, sqlite3.Row) else idx[1]
                    is_unique = bool(idx['unique'] if isinstance(idx, sqlite3.Row) else idx[2])
                except Exception:
                    continue
                if not is_unique or not idx_name:
                    continue
                # Check which columns are in this index
                try:
                    info_rows = conn.execute(f"PRAGMA index_info('{idx_name}')").fetchall()
                    cols = []
                    for r in info_rows or []:
                        try:
                            cols.append(r['name'] if isinstance(r, sqlite3.Row) else r[2])
                        except Exception:
                            pass
                    # If the index is exactly on email, drop it
                    if len(cols) == 1 and cols[0] == 'email':
                        conn.execute(f"DROP INDEX IF EXISTS \"{idx_name}\"")
                        logger.info(f"Dropped UNIQUE index on users.email: {idx_name}")
                except Exception as e:
                    logger.warning(f"Could not inspect index {idx_name}: {e}")
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Email unique constraint relax migration skipped: {e}")

# Run migration at startup
relax_users_email_unique_constraint()

def migrate_users_table_if_needed():
    """Rebuild users table to allow NULL email/full_name and remove UNIQUE(email) if present."""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        try:
            cols = conn.execute("PRAGMA table_info(users)").fetchall() or []
            email_notnull = False
            for c in cols:
                try:
                    if c['name'] == 'email' and int(c['notnull']) == 1:
                        email_notnull = True
                        break
                except Exception:
                    pass

            # Detect unique index involving email
            email_unique = False
            try:
                idxs = conn.execute("PRAGMA index_list(users)").fetchall() or []
                for idx in idxs:
                    try:
                        idx_name = idx['name']
                        is_unique = bool(idx['unique'])
                    except Exception:
                        continue
                    if not is_unique:
                        continue
                    info = conn.execute(f"PRAGMA index_info('{idx_name}')").fetchall() or []
                    cols_in_idx = []
                    for r in info:
                        try:
                            cols_in_idx.append(r['name'])
                        except Exception:
                            pass
                    if 'email' in cols_in_idx:
                        email_unique = True
                        break
            except Exception:
                pass

            needs = email_notnull or email_unique
            if not needs:
                return

            logger.warning("Rebuilding users table to relax constraints on email/full_name")
            conn.execute("BEGIN IMMEDIATE")

            # Create new table with desired schema
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users_new (
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

            # Copy data, converting empty strings to NULL for email/full_name
            conn.execute('''
                INSERT INTO users_new (id, username, password_hash, email, full_name, is_admin, is_active, created_at, last_login)
                SELECT id, username, password_hash,
                       NULLIF(email, ''), NULLIF(full_name, ''),
                       is_admin, is_active, created_at, last_login
                FROM users
            ''')

            # Drop old and rename
            conn.execute('DROP TABLE users')
            conn.execute('ALTER TABLE users_new RENAME TO users')

            conn.commit()
            logger.info("Users table rebuilt successfully; email/full_name now nullable and non-unique")
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            logger.error(f"Users table migration failed: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Users table migration error: {e}")

# Run guarded table migration
migrate_users_table_if_needed()

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
            user = conn.execute('SELECT id, username, is_admin, is_active FROM users WHERE id = ?', (current_user_id,)).fetchone()
            conn.close()

            if not user:
                return jsonify({'error': 'User not found'}), 401

            # Update last login timestamp
            conn = get_db_connection()
            conn.execute('UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?', (current_user_id,))
            conn.commit()
            conn.close()

            # If user is disabled and not admin, restrict API access to quarantine-safe endpoints only
            if not user['is_admin'] and not user['is_active']:
                allowed = {'/api/auth/me', '/api/auth/logout', '/health'}
                if request.path not in allowed:
                    return jsonify({'error': 'Account disabled', 'disabled': True}), 403

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

        # Check if user exists
        if not user:
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

        # Disabled users are permitted to authenticate; access is restricted by auth_required

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

        # Successful authentication (including disabled accounts)
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
                'is_admin': bool(user['is_admin']),
                'is_active': bool(user['is_active'])
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
        user = conn.execute('SELECT username, email, full_name, is_admin, created_at, last_login FROM users WHERE id = ?', (current_user_id,)).fetchone()
        conn.close()

        if not user:
            return jsonify({'error': 'User not found'}), 500

        return jsonify({
            'user': {
                'id': current_user_id,
                'username': user['username'],
                'email': user['email'],
                'full_name': user['full_name'],
                'is_admin': bool(user['is_admin']),
                'created_at': user['created_at'],
                'last_login': user['last_login']
            }
        })
        
    except Exception as e:
        logger.error(f"Get user error: {e}")
        return jsonify({'error': 'Failed to get user information'}), 500

@app.route('/api/auth/change-username', methods=['POST'])
@auth_required
def change_username(current_user_id):
    """Change the current user's username with validation and uniqueness check."""
    try:
        data = request.get_json(silent=True) or {}
        current_name = (data.get('current_username') or '').strip()
        new1 = (data.get('new_username') or '').strip()
        new2 = (data.get('confirm_username') or '').strip()

        if not current_name or not new1 or not new2:
            return jsonify({'error': 'All fields are required'}), 400
        if new1 != new2:
            return jsonify({'error': 'New usernames do not match'}), 400
        if len(new1) < 3 or len(new1) > 32:
            return jsonify({'error': 'Username must be 3-32 characters'}), 400
        if not all(c.isalnum() or c in ('_', '-') for c in new1):
            return jsonify({'error': 'Username may contain letters, numbers, _ and - only'}), 400

        conn = get_db_connection()
        user = conn.execute('SELECT username FROM users WHERE id = ?', (current_user_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({'error': 'User not found'}), 404
        if user['username'] != current_name:
            conn.close()
            return jsonify({'error': 'Current username is incorrect'}), 400

        # Check uniqueness
        exists = conn.execute('SELECT 1 FROM users WHERE username = ? AND id != ?', (new1, current_user_id)).fetchone()
        if exists:
            conn.close()
            return jsonify({'error': 'Username already taken'}), 409

        # Update
        conn.execute('UPDATE users SET username = ? WHERE id = ?', (new1, current_user_id))
        conn.commit()
        conn.close()

        logger.info(f"User {current_user_id} changed username")
        return jsonify({'changed': True, 'username': new1})
    except Exception as e:
        logger.error(f"Change username error: {e}")
        return jsonify({'error': 'Failed to change username'}), 500

@app.route('/api/auth/change-password', methods=['POST'])
@auth_required
def change_password(current_user_id):
    """Change the current user's password securely (bcrypt verification + update)."""
    try:
        data = request.get_json(silent=True) or {}
        current_password = data.get('current_password') or ''
        new_password = data.get('new_password') or ''
        confirm_password = data.get('confirm_password') or ''

        # Basic validation
        if not current_password or not new_password or not confirm_password:
            return jsonify({'error': 'All fields are required'}), 400
        if new_password != confirm_password:
            return jsonify({'error': 'New passwords do not match'}), 400

        # Password policy: min 8 chars, must include upper, lower, digit, and symbol
        if len(new_password) < 8 or \
           not any(c.islower() for c in new_password) or \
           not any(c.isupper() for c in new_password) or \
           not any(c.isdigit() for c in new_password) or \
           not any(not c.isalnum() for c in new_password):
            return jsonify({'error': 'Password must be 8+ chars with upper, lower, number, and symbol'}), 400

        conn = get_db_connection()
        row = conn.execute('SELECT password_hash FROM users WHERE id = ?', (current_user_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        stored_hash = row['password_hash'] or ''
        try:
            ok = bcrypt.checkpw(current_password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception:
            ok = False
        if not ok:
            conn.close()
            return jsonify({'error': 'Current password is incorrect'}), 400

        # Update with new hash
        new_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        conn.execute('UPDATE users SET password_hash = ? WHERE id = ?', (new_hash, current_user_id))
        conn.commit()
        conn.close()

        # Do not log sensitive data
        logger.info(f"User {current_user_id} changed password")
        return jsonify({'changed': True})
    except Exception as e:
        logger.error(f"Change password error: {e}")
        return jsonify({'error': 'Failed to change password'}), 500

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

# ---------- Frigate events proxy (Phase 1) ----------
@app.route('/api/frigate/events', methods=['GET'])
@app.route('/api/events', methods=['GET'])
@auth_required
def proxy_frigate_events(current_user_id):
    """Proxy to Frigate /api/events with optional filters: camera, zone, label, before, after, limit."""
    try:
        params = {}
        for key in ['camera', 'label', 'before', 'after', 'limit']:
            val = request.args.get(key)
            if val:
                params[key] = val

        r = requests.get(f"{FRIGATE_HOST}/api/events", params=params, timeout=15)
        r.raise_for_status()
        events = r.json() or []

        # Optional zone post-filter
        zone = request.args.get('zone')
        if zone:
            zone_name = zone.strip()
            events = [e for e in events if isinstance(e, dict) and zone_name in (e.get('zones') or [])]

        return jsonify(events)
    except Exception as e:
        logger.error(f"Frigate events proxy error: {e}")
        return jsonify([]), 200


@app.route('/api/frigate/events/<event_id>/clip.mp4', methods=['GET'])
@app.route('/api/events/<event_id>/clip.mp4', methods=['GET'])
@auth_required
def proxy_frigate_event_clip(current_user_id, event_id):
    """Proxy Frigate event clip for authenticated playback in the PWA (Range-aware)."""
    try:
        # Forward Range header for partial content requests
        forward_headers = {
            'Accept': 'video/mp4'
        }
        incoming_range = request.headers.get('Range')
        if incoming_range:
            forward_headers['Range'] = incoming_range

        upstream = requests.get(
            f"{FRIGATE_HOST}/api/events/{event_id}/clip.mp4",
            headers=forward_headers,
            stream=True,
            timeout=60
        )
        upstream.raise_for_status()

        # Build response headers, preserving range-related metadata
        headers = {
            'Content-Type': upstream.headers.get('Content-Type', 'video/mp4'),
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Access-Control-Allow-Origin': '*',
        }
        content_length = upstream.headers.get('Content-Length')
        content_range = upstream.headers.get('Content-Range')
        accept_ranges = upstream.headers.get('Accept-Ranges', 'bytes')
        if content_length:
            headers['Content-Length'] = content_length
        if content_range:
            headers['Content-Range'] = content_range
        if accept_ranges:
            headers['Accept-Ranges'] = accept_ranges

        status_code = upstream.status_code  # 200 or 206 for partial content

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        yield chunk
            finally:
                try:
                    upstream.close()
                except:
                    pass

        return Response(generate(), status=status_code, headers=headers)
    except Exception as e:
        logger.error(f"Frigate event clip proxy error for {event_id}: {e}")
        return jsonify({'error': 'Failed to fetch event clip'}), 500


@app.route('/api/events/summary', methods=['GET'])
@auth_required
def events_summary(current_user_id):
    """Return a small summary for dashboard cards: latest per zone of interest."""
    try:
        # Zones of interest can be configured later; for now use Driveway and Front_Door
        zones_of_interest = request.args.get('zones')
        if zones_of_interest:
            zones = [z.strip() for z in zones_of_interest.split(',') if z.strip()]
        else:
            zones = ['Driveway', 'Front_Door']

        # Pull latest 100 events and pick the most recent per zone
        r = requests.get(f"{FRIGATE_HOST}/api/events", params={'limit': '100'}, timeout=10)
        r.raise_for_status()
        events = r.json() or []

        latest_by_zone = {}
        for ev in events:
            ev_zones = ev.get('zones') or []
            for z in zones:
                if z in ev_zones:
                    prev = latest_by_zone.get(z)
                    if not prev or (ev.get('start_time') or 0) > (prev.get('start_time') or 0):
                        latest_by_zone[z] = ev

        # Shape a simple payload for UI
        items = []
        for z in zones:
            ev = latest_by_zone.get(z)
            if ev:
                items.append({
                    'zone': z,
                    'id': ev.get('id'),
                    'camera': ev.get('camera'),
                    'label': ev.get('label'),
                    'time': ev.get('start_time'),
                })

        return jsonify({'items': items})
    except Exception as e:
        logger.error(f"Events summary error: {e}")
        return jsonify({'items': []}), 200

@app.route('/api/events/<event_id>/snapshot.jpg', methods=['GET'])
@auth_required
def proxy_frigate_event_snapshot(current_user_id, event_id):
    try:
        upstream = requests.get(f"{FRIGATE_HOST}/api/events/{event_id}/snapshot.jpg", stream=True, timeout=30)
        upstream.raise_for_status()
        headers = {
            'Content-Type': upstream.headers.get('Content-Type', 'image/jpeg'),
            'Cache-Control': 'no-store, no-cache, must-revalidate, max-age=0',
            'Pragma': 'no-cache',
            'Access-Control-Allow-Origin': '*',
        }
        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            finally:
                try:
                    upstream.close()
                except:
                    pass
        return Response(generate(), status=200, headers=headers)
    except Exception as e:
        logger.error(f"Frigate event snapshot proxy error for {event_id}: {e}")
        return jsonify({'error': 'Failed to fetch event snapshot'}), 500

@app.route('/api/events/<event_id>/clip.m3u8', methods=['GET'])
@auth_required
def get_event_clip_hls(current_user_id, event_id):
    """Generate and serve HLS playlist for a Frigate event clip (on-demand VOD)."""
    try:
        base_dir = Path(HLS_SEGMENTS_PATH) / 'events' / event_id
        playlist_path = base_dir / 'playlist.m3u8'

        # Ensure directory exists
        base_dir.mkdir(parents=True, exist_ok=True)

        # If playlist missing or empty, (re)generate
        if not playlist_path.exists() or playlist_path.stat().st_size == 0:
            source_url = f"{FRIGATE_HOST}/api/events/{event_id}/clip.mp4"
            segment_pattern = str(base_dir / 'segment_%05d.ts')
            cmd = [
                'ffmpeg',
                '-hide_banner', '-loglevel', 'error',
                '-i', source_url,
                '-c:v', 'libx264', '-preset', 'veryfast', '-profile:v', 'baseline', '-level', '3.1', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-b:a', '96k',
                '-movflags', '+faststart',
                '-f', 'hls', '-hls_time', '4', '-hls_list_size', '0',
                '-hls_segment_type', 'mpegts', '-hls_playlist_type', 'vod',
                '-hls_segment_filename', segment_pattern,
                str(playlist_path)
            ]
            try:
                logger.info(f"Generating HLS for event {event_id} -> {playlist_path}")
                subprocess.run(cmd, check=True, timeout=300)
            except subprocess.TimeoutExpired:
                logger.error(f"HLS generation timeout for event {event_id}")
                return jsonify({'error': 'HLS generation timed out'}), 504
            except subprocess.CalledProcessError as e:
                logger.error(f"HLS generation failed for event {event_id}: {e}")
                return jsonify({'error': 'Failed to generate HLS'}), 500

        # Read and rewrite playlist segment URIs to go through our authenticated segment endpoint
        try:
            content = playlist_path.read_text()
            lines = content.split('\n')
            rewritten = []
            token = request.headers.get('Authorization')
            if token and token.startswith('Bearer '):
                token = token[7:]
            else:
                token = request.args.get('token')

            for line in lines:
                if line.strip().endswith('.ts'):
                    seg = line.strip()
                    url = f"/api/events/hls/{event_id}/{seg}"
                    if token:
                        url += f"?token={token}"
                    rewritten.append(url)
                else:
                    rewritten.append(line)
            playlist_mod = '\n'.join(rewritten)
            headers = {
                'Content-Type': 'application/vnd.apple.mpegurl',
                'Cache-Control': 'no-cache, no-store, must-revalidate, max-age=0',
                'Access-Control-Allow-Origin': '*',
            }
            return Response(playlist_mod, status=200, headers=headers)
        except Exception as e:
            logger.error(f"Error reading HLS playlist for event {event_id}: {e}")
            return jsonify({'error': 'Failed to read playlist'}), 500

    except Exception as e:
        logger.error(f"Event HLS error for {event_id}: {e}")
        return jsonify({'error': 'HLS failed'}), 500

@app.route('/api/events/hls/<event_id>/<segment>', methods=['GET'])
@auth_required
def get_event_hls_segment(current_user_id, event_id, segment):
    """Serve generated HLS segments for an event clip with auth."""
    try:
        if not segment.endswith('.ts') or '/' in segment or '..' in segment:
            return jsonify({'error': 'Invalid segment'}), 400
        seg_path = Path(HLS_SEGMENTS_PATH) / 'events' / event_id / segment
        if not seg_path.exists():
            return jsonify({'error': 'Segment not found'}), 404
        return send_file(str(seg_path), mimetype='video/mp2t', as_attachment=False, conditional=True)
    except Exception as e:
        logger.error(f"Event HLS segment error for {event_id}/{segment}: {e}")
        return jsonify({'error': 'Failed to serve segment'}), 500

@app.route('/api/events/<event_id>/hls', methods=['DELETE'])
@auth_required
def delete_event_hls(current_user_id, event_id):
    """Delete generated HLS assets for an event (cleanup on UI close)."""
    try:
        event_dir = Path(HLS_SEGMENTS_PATH) / 'events' / event_id
        if event_dir.exists() and event_dir.is_dir():
            try:
                shutil.rmtree(event_dir)
                logger.info(f"Deleted HLS directory for event {event_id}: {event_dir}")
            except Exception as e:
                logger.warning(f"Failed to delete HLS directory for event {event_id}: {e}")
                return jsonify({'deleted': False, 'error': 'Delete failed'}), 500
        return jsonify({'deleted': True})
    except Exception as e:
        logger.error(f"Event HLS delete error for {event_id}: {e}")
        return jsonify({'deleted': False, 'error': 'Unexpected error'}), 500

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

        # Helper: determine if IP was blocked at attempt time
        def was_ip_blocked_at(ip_addr, when_ts):
            try:
                c = get_db_connection()
                row = c.execute('''
                    SELECT 1 FROM blocked_ips
                    WHERE ip_address = ?
                    AND blocked_at <= ?
                    AND blocked_until >= ?
                    LIMIT 1
                ''', (ip_addr, when_ts, when_ts)).fetchone()
                c.close()
                return row is not None
            except Exception:
                return False

        # Helper: best-effort IP location (cached)
        def get_ip_location(ip_addr):
            # Private/reserved networks
            try:
                ip_obj = ipaddress.ip_address(ip_addr)
                if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved:
                    return 'Private Network'
            except Exception:
                return 'Unknown'

            if GEOIP_PROVIDER.lower() != 'ipapi':
                return 'Unknown'

            # Check cache (valid for 7 days)
            try:
                c = get_db_connection()
                cached = c.execute('''
                    SELECT country, region, city, updated_at FROM ip_geo_cache WHERE ip_address = ?
                ''', (ip_addr,)).fetchone()
                if cached:
                    # Assume cache fresh enough
                    country = cached['country'] or ''
                    region = cached['region'] or ''
                    city = cached['city'] or ''
                    c.close()
                    loc = ', '.join([p for p in [city, region, country] if p])
                    return loc if loc else 'Unknown'
                c.close()
            except Exception:
                pass

            # Lookup via ip-api.com (no key, best-effort)
            try:
                r = requests.get(f"http://ip-api.com/json/{ip_addr}?fields=status,country,regionName,city,query&lang=en", timeout=4)
                data = r.json() if r and r.headers.get('Content-Type','').startswith('application/json') else {}
                if data.get('status') == 'success':
                    country = data.get('country')
                    region = data.get('regionName')
                    city = data.get('city')
                    # Save to cache
                    try:
                        c = get_db_connection()
                        c.execute('''
                            INSERT OR REPLACE INTO ip_geo_cache (ip_address, country, region, city, updated_at)
                            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ''', (ip_addr, country, region, city))
                        c.commit()
                        c.close()
                    except Exception:
                        pass
                    loc = ', '.join([p for p in [city, region, country] if p])
                    return loc if loc else 'Unknown'
            except Exception:
                pass

            return 'Unknown'

        attempts_list = []
        for attempt in attempts:
            ip_addr = attempt['ip_address']
            when_ts = attempt['attempt_time']
            attempts_list.append({
                'ip_address': ip_addr,
                'username': attempt['username'],
                'success': bool(attempt['success']),
                'attempt_time': when_ts,
                'user_agent': attempt['user_agent'],
                'blocked': was_ip_blocked_at(ip_addr, when_ts),
                'location': get_ip_location(ip_addr)
            })
        
        return jsonify({'login_attempts': attempts_list})
        
    except Exception as e:
        logger.error(f"Error getting login attempts: {e}")
        return jsonify({'error': 'Failed to get login attempts'}), 500

@app.route('/api/admin/users', methods=['POST'])
@auth_required
def admin_create_user(current_user_id):
    """Admin-only: create a new user with username, password (hashed), and role."""
    try:
        # Verify admin
        conn = get_db_connection()
        me = conn.execute('SELECT is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        if not me or not me['is_admin']:
            conn.close()
            return jsonify({'error': 'Admin access required'}), 403

        data = request.get_json(silent=True) or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''
        is_admin = bool(data.get('is_admin') or False)

        # Validate username
        if not username or len(username) < 3 or len(username) > 32:
            conn.close()
            return jsonify({'error': 'Username must be 3-32 characters'}), 400
        if not all(c.isalnum() or c in ('_', '-') for c in username):
            conn.close()
            return jsonify({'error': 'Username may contain letters, numbers, _ and - only'}), 400

        # Validate password (reuse same policy)
        if len(password) < 8 or \
           not any(c.islower() for c in password) or \
           not any(c.isupper() for c in password) or \
           not any(c.isdigit() for c in password) or \
           not any(not c.isalnum() for c in password):
            conn.close()
            return jsonify({'error': 'Password must be 8+ chars with upper, lower, number, and symbol'}), 400

        # Uniqueness
        exists = conn.execute('SELECT 1 FROM users WHERE username = ?', (username,)).fetchone()
        if exists:
            conn.close()
            return jsonify({'error': 'Username already taken'}), 409

        # Create user
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur = conn.execute('''
            INSERT INTO users (username, password_hash, email, full_name, is_admin, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, password_hash, None, None, 1 if is_admin else 0, 1))
        user_id = cur.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Admin {current_user_id} created user {username} (admin={is_admin})")
        return jsonify({'created': True, 'user': {'id': user_id, 'username': username, 'is_admin': is_admin}}), 201
    except Exception as e:
        logger.error(f"Admin create user error: {e}")
        return jsonify({'error': 'Failed to create user'}), 500

@app.route('/api/admin/users', methods=['GET'])
@auth_required
def admin_list_users(current_user_id):
    """Admin-only: list users with id, username, role, status, and timestamps."""
    try:
        conn = get_db_connection()
        me = conn.execute('SELECT is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        if not me or not me['is_admin']:
            conn.close()
            return jsonify({'error': 'Admin access required'}), 403

        rows = conn.execute('''
            SELECT id, username, is_admin, is_active, created_at, last_login
            FROM users
            ORDER BY username COLLATE NOCASE ASC
        ''').fetchall()
        conn.close()

        users = []
        for r in rows:
            users.append({
                'id': r['id'],
                'username': r['username'],
                'is_admin': bool(r['is_admin']),
                'is_active': bool(r['is_active']),
                'created_at': r['created_at'],
                'last_login': r['last_login']
            })
        return jsonify({'users': users})
    except Exception as e:
        logger.error(f"Admin list users error: {e}")
        return jsonify({'error': 'Failed to list users'}), 500

@app.route('/api/admin/users/<int:user_id>/active', methods=['POST'])
@auth_required
def admin_toggle_user_active(current_user_id, user_id):
    """Admin-only: enable/disable a user account by toggling is_active."""
    try:
        data = request.get_json(silent=True) or {}
        is_active = bool(data.get('is_active'))

        conn = get_db_connection()
        me = conn.execute('SELECT is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        if not me or not me['is_admin']:
            conn.close()
            return jsonify({'error': 'Admin access required'}), 403

        # Prevent self-disabling via API
        if user_id == current_user_id:
            conn.close()
            return jsonify({'error': 'Cannot modify your own active status'}), 400

        # Fetch target user
        target = conn.execute('SELECT id, is_admin FROM users WHERE id = ?', (user_id,)).fetchone()
        if not target:
            conn.close()
            return jsonify({'error': 'User not found'}), 404

        # Optional: prevent disabling admins (leave enabled) unless future policy says otherwise
        if target['is_admin'] and not is_active:
            conn.close()
            return jsonify({'error': 'Cannot disable an admin account'}), 400

        conn.execute('UPDATE users SET is_active = ? WHERE id = ?', (1 if is_active else 0, user_id))
        conn.commit()
        conn.close()
        logger.info(f"Admin {current_user_id} set user {user_id} active={is_active}")
        return jsonify({'updated': True, 'is_active': is_active})
    except Exception as e:
        logger.error(f"Admin toggle user error: {e}")
        return jsonify({'error': 'Failed to update user status'}), 500

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
import gc
import os

# Memory management configuration
MEMORY_CHECK_INTERVAL = 300  # Check memory every 5 minutes
MAX_UPTIME_HOURS = 72       # Trigger more aggressive cleanup after 3 days

def get_process_memory_info():
    """Get basic memory information without external dependencies"""
    try:
        pid = os.getpid()
        
        # Read basic memory info from /proc/self/status
        memory_info = {}
        with open('/proc/self/status', 'r') as f:
            for line in f:
                if line.startswith('VmRSS:'):
                    memory_info['rss_kb'] = int(line.split()[1])
                elif line.startswith('VmSize:'):
                    memory_info['vms_kb'] = int(line.split()[1])
                elif line.startswith('VmSwap:'):
                    memory_info['swap_kb'] = int(line.split()[1])
        
        # Calculate uptime using process start time
        try:
            with open('/proc/self/stat', 'r') as f:
                stat_data = f.read().split()
                # starttime is the 22nd field (index 21) in clock ticks
                starttime_ticks = int(stat_data[21])
                # Get system boot time and convert to uptime
                with open('/proc/uptime', 'r') as uptime_file:
                    system_uptime = float(uptime_file.read().split()[0])
                # Clock ticks per second (usually 100)
                ticks_per_sec = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                process_uptime = system_uptime - (starttime_ticks / ticks_per_sec)
                memory_info['uptime_hours'] = process_uptime / 3600
        except Exception:
            memory_info['uptime_hours'] = 0
        
        return memory_info
        
    except Exception as e:
        logger.error(f"Error getting memory info: {e}")
        return None

def force_garbage_collection():
    """Force Python garbage collection and return collected object count"""
    try:
        # Get initial object count
        before_gc = len(gc.get_objects())
        
        # Run all generations of garbage collection
        collected_counts = []
        for generation in range(3):
            collected = gc.collect(generation)
            collected_counts.append(collected)
        
        after_gc = len(gc.get_objects())
        total_collected = sum(collected_counts)
        
        logger.info(f"Garbage collection: freed {before_gc - after_gc} objects ({total_collected} collected)")
        return total_collected
        
    except Exception as e:
        logger.error(f"Error in garbage collection: {e}")
        return 0

def cleanup_application_resources():
    """Clean up application-specific resources that might be leaking"""
    cleaned_count = 0
    
    try:
        # Force garbage collection
        gc_count = force_garbage_collection()
        cleaned_count += gc_count
        
        # Clear any module-level caches
        if hasattr(gc, 'garbage'):
            gc.garbage.clear()
        
        logger.info(f"Application resource cleanup completed: {cleaned_count} objects cleaned")
        return cleaned_count
        
    except Exception as e:
        logger.error(f"Error in application resource cleanup: {e}")
        return cleaned_count

def check_and_cleanup_memory():
    """Check memory usage and trigger cleanup if needed"""
    try:
        memory_info = get_process_memory_info()
        if not memory_info:
            return False
            
        rss_mb = memory_info.get('rss_kb', 0) / 1024
        swap_mb = memory_info.get('swap_kb', 0) / 1024
        uptime_hours = memory_info.get('uptime_hours', 0)
        
        # Log current memory status every 5th check (every 25 minutes)
        if hasattr(check_and_cleanup_memory, 'check_count'):
            check_and_cleanup_memory.check_count += 1
        else:
            check_and_cleanup_memory.check_count = 1
            
        if check_and_cleanup_memory.check_count % 5 == 0:
            logger.info(f"Memory status: RSS={rss_mb:.1f}MB, Swap={swap_mb:.1f}MB, Uptime={uptime_hours:.1f}h")
        
        # Determine if cleanup is needed
        cleanup_needed = False
        reasons = []
        
        # Cleanup triggers
        if swap_mb > 30:  # More than 30MB swap
            cleanup_needed = True
            reasons.append(f"swap({swap_mb:.1f}MB > 30MB)")
            
        if rss_mb > 50:  # More than 50MB resident
            cleanup_needed = True
            reasons.append(f"rss({rss_mb:.1f}MB > 50MB)")
            
        if uptime_hours > MAX_UPTIME_HOURS:  # Running for more than 3 days
            cleanup_needed = True
            reasons.append(f"uptime({uptime_hours:.1f}h > {MAX_UPTIME_HOURS}h)")
        
        if cleanup_needed:
            logger.warning(f"Memory cleanup triggered: {', '.join(reasons)}")
            cleaned = cleanup_application_resources()
            
            # Check memory after cleanup
            new_memory_info = get_process_memory_info()
            if new_memory_info:
                new_swap = new_memory_info.get('swap_kb', 0) / 1024
                new_rss = new_memory_info.get('rss_kb', 0) / 1024
                swap_saved = swap_mb - new_swap
                rss_saved = rss_mb - new_rss
                
                logger.info(f"Cleanup results: Swap saved {swap_saved:.1f}MB, RSS saved {rss_saved:.1f}MB")
            
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error in memory check and cleanup: {e}")
        return False

def periodic_cleanup():
    """Enhanced periodic cleanup including memory management and expired blocks"""
    logger.info("Starting enhanced periodic cleanup thread")
    
    while True:
        try:
            # Database cleanup (existing)
            cleanup_expired_blocks()
            
            # Memory management (new)
            check_and_cleanup_memory()
            
            # Sleep for memory check interval (5 minutes)
            time.sleep(MEMORY_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}")
            time.sleep(60)  # Wait 1 minute before retrying

# Memory monitoring API endpoints (lightweight versions)

@app.route('/api/debug/memory', methods=['GET'])
@auth_required
def get_memory_status(current_user_id):
    """Get current memory usage information - requires authentication"""
    try:
        memory_info = get_process_memory_info()
        if not memory_info:
            return jsonify({'error': 'Could not get memory information'}), 500
            
        # Convert to MB for readability
        memory_mb = {
            'rss_mb': memory_info.get('rss_kb', 0) / 1024,
            'vms_mb': memory_info.get('vms_kb', 0) / 1024,
            'swap_mb': memory_info.get('swap_kb', 0) / 1024,
            'uptime_hours': memory_info.get('uptime_hours', 0)
        }
        
        return jsonify({
            'memory': memory_mb,
            'thresholds': {
                'swap_mb': 30,
                'rss_mb': 50,
                'max_uptime_hours': MAX_UPTIME_HOURS
            },
            'gc_stats': {
                'counts': gc.get_count(),
                'threshold': gc.get_threshold()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting memory status: {e}")
        return jsonify({'error': 'Failed to get memory status'}), 500

@app.route('/api/debug/memory/cleanup', methods=['POST'])
@auth_required  
def trigger_memory_cleanup(current_user_id):
    """Manually trigger memory cleanup - requires authentication"""
    try:
        # Check if user is admin
        conn = get_db_connection()
        user = conn.execute('SELECT is_admin FROM users WHERE id = ?', (current_user_id,)).fetchone()
        conn.close()
        
        if not user or not user['is_admin']:
            return jsonify({'error': 'Admin access required'}), 403
            
        # Get memory before cleanup
        before_memory = get_process_memory_info()
        
        # Run cleanup
        cleaned = cleanup_application_resources()
        
        # Get memory after cleanup  
        after_memory = get_process_memory_info()
        
        result = {
            'cleanup_triggered': True,
            'objects_cleaned': cleaned,
            'memory_before': before_memory,
            'memory_after': after_memory
        }
        
        if before_memory and after_memory:
            result['memory_saved'] = {
                'rss_mb': (before_memory.get('rss_kb', 0) - after_memory.get('rss_kb', 0)) / 1024,
                'swap_mb': (before_memory.get('swap_kb', 0) - after_memory.get('swap_kb', 0)) / 1024
            }
        
        logger.info(f"Manual memory cleanup triggered by admin user {current_user_id}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error in manual memory cleanup: {e}")
        return jsonify({'error': 'Memory cleanup failed'}), 500

# Start background cleanup thread
cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
cleanup_thread.start()

atexit.register(cleanup)

if __name__ == '__main__':
    # Log startup memory info
    startup_memory = get_process_memory_info()
    if startup_memory:
        logger.info(f"Backend starting - Initial memory: RSS={startup_memory.get('rss_kb', 0)/1024:.1f}MB, Swap={startup_memory.get('swap_kb', 0)/1024:.1f}MB")
    
    # Disable debug mode in production
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=5003, debug=debug_mode)