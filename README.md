# AnchorPoint Surveillance System

A self-hosted surveillance system with multi-user support, built on Frigate NVR with a modern Vue.js PWA frontend.

## 🏗️ Architecture Overview

### Core Components
- **Frigate NVR**: AI-powered video recording and motion detection
- **Vue.js PWA**: Modern web interface for viewing cameras and managing users
- **Flask Backend**: Multi-user authentication and API management
- **SQLite Database**: User management and system configuration
- **Caddy Reverse Proxy**: Automatic HTTPS and secure routing
- **Netdata**: System monitoring and health metrics
- **Mosquitto MQTT**: Real-time communication for events

### Key Features
- ✅ Multi-user support with role-based access
- ✅ Device management for push notifications
- ✅ Real-time camera feeds and snapshots
- ✅ Event timeline and filtering
- ✅ System health monitoring
- ✅ Automated backup system
- ✅ Secure remote access via Tailscale
- ✅ Mobile-responsive PWA

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- NVIDIA GPU (optional, for hardware acceleration)
- Tailscale account (for remote access)

### 1. Clone and Setup
```bash
git clone <repository-url>
cd anchorpoint
```

### 2. Configure Environment
```bash
# Create environment file
cp .env.example .env

# Edit environment variables
nano .env
```

### 3. Configure Cameras
Edit `frigate/config/config.yml` with your camera details:
```yaml
cameras:
  front_door:
    ffmpeg:
      inputs:
        - path: rtsp://username:password@camera-ip:554/stream
          roles:
            - detect
            - record
    detect:
      width: 1920
      height: 1080
      fps: 5
```

### 4. Start the System
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps
```

### 5. Access the System
- **Local Access**: https://localhost (accept self-signed certificate)
- **Remote Access**: Via Tailscale (configure your domain)
- **Default Login**: 
  - Username: `admin`
  - Password: `admin123`

## 📁 Directory Structure

```
anchorpoint/
├── docker-compose.yml          # Main orchestration file
├── caddy/
│   └── Caddyfile              # Reverse proxy configuration
├── frigate/
│   ├── config/
│   │   └── config.yml         # Frigate configuration
│   └── media/                 # Recordings and snapshots
├── pwa/
│   ├── backend/
│   │   ├── app.py             # Flask API server
│   │   ├── requirements.txt   # Python dependencies
│   │   └── database_schema.sql # Database schema
│   └── src/                   # Vue.js frontend
├── mosquitto/
│   └── config/                # MQTT configuration
├── netdata/
│   └── config/                # Monitoring configuration
├── data/                      # Persistent data storage
└── configs/
    └── backup.sh              # Backup script
```

## 🔧 Configuration

### Environment Variables
```bash
# Security
SECRET_KEY=your-secret-key-here

# Database
DATABASE_PATH=/data/anchorpoint.db

# Frigate
FRIGATE_HOST=http://frigate:5000

# Caddy (for production)
DOMAIN=your-domain.com
EMAIL=your-email@domain.com
```

### Camera Configuration
Each camera in `frigate/config/config.yml` supports:
- Multiple input streams (detect, record, live)
- Hardware acceleration
- Motion detection zones
- Recording retention policies
- AI object detection

### User Management
- **Admin Users**: Full system access, can create/manage users
- **Member Users**: Access to cameras and events
- **Viewer Users**: Read-only access to cameras

## 🔒 Security Features

### Authentication
- JWT-based authentication
- Session management
- Password hashing with bcrypt
- Role-based access control

### Network Security
- HTTPS with automatic certificates
- Security headers
- CORS protection
- Tailscale for secure remote access

### Data Protection
- Encrypted database storage
- Automated backups
- Audit logging
- Secure credential management

## 📱 Mobile Access

### PWA Features
- Installable on mobile devices
- Offline capability
- Push notifications
- Responsive design

### Device Registration
Users can register multiple devices for push notifications:
1. Access PWA on mobile device
2. Register device in settings
3. Configure notification preferences
4. Receive real-time alerts

## 🔄 Backup and Recovery

### Automated Backups
```bash
# Manual backup
./configs/backup.sh

# Automated daily backup (add to crontab)
0 2 * * * /path/to/anchorpoint/configs/backup.sh
```

### Backup Contents
- SQLite user database
- Frigate configuration
- System settings
- Caddy configuration
- Backup manifest

### Recovery Process
1. Stop all services: `docker-compose down`
2. Restore backup files
3. Restart services: `docker-compose up -d`
4. Verify system functionality

## 📊 Monitoring

### Netdata Integration
- Real-time system metrics
- Performance monitoring
- Resource utilization
- Alert notifications

### System Health
- Service status monitoring
- Storage capacity alerts
- Camera connectivity checks
- Performance metrics

## 🚀 Production Deployment

### 1. Domain Configuration
```bash
# Update Caddyfile with your domain
sed -i 's/localhost/your-domain.com/g' caddy/Caddyfile
```

### 2. SSL Certificate
```bash
# Uncomment TLS line in Caddyfile
# tls your-email@domain.com
```

### 3. Security Hardening
```bash
# Change default passwords
# Update SECRET_KEY
# Configure firewall rules
# Enable automatic updates
```

### 4. Performance Optimization
- Enable hardware acceleration
- Configure storage retention
- Optimize camera settings
- Monitor resource usage

## 🛠️ Troubleshooting

### Common Issues

**Port Conflicts**
```bash
# Check port usage
netstat -tulpn | grep :5000
```

**Database Issues**
```bash
# Reset database
rm /data/anchorpoint.db
docker-compose restart pwa-backend
```

**Camera Connection Issues**
```bash
# Test camera connectivity
ffmpeg -i rtsp://camera-url -t 5 -f null -
```

**Permission Issues**
```bash
# Fix file permissions
sudo chown -R 1000:1000 ./data
```

### Logs
```bash
# View service logs
docker-compose logs frigate
docker-compose logs pwa-backend
docker-compose logs caddy
```

## 🤝 Support

### Documentation
- [Frigate Documentation](https://docs.frigate.video/)
- [Vue.js Documentation](https://vuejs.org/guide/)
- [Caddy Documentation](https://caddyserver.com/docs/)

### Community
- GitHub Issues for bug reports
- Feature requests welcome
- Community forum (coming soon)

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🔄 Updates

### Updating the System
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Version History
- v1.0.0: Initial release with multi-user support
- Future: Mobile app, cloud backup, advanced analytics 