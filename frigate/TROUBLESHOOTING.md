# Frigate Troubleshooting Guide

## Common Restart Issues and Solutions

### 1. MQTT Connection Issues

**Symptoms:**
- Frigate keeps restarting
- Logs show MQTT connection errors
- Mosquitto not accessible

**Solutions:**
```bash
# Check if Mosquitto is running
docker-compose ps mosquitto

# Check Mosquitto logs
docker-compose logs mosquitto

# Test MQTT connection manually
docker exec -it mosquitto mosquitto_pub -h localhost -p 1883 -u frigate -P '#Frigate7214' -t test/topic -m "test message"
```

### 2. GPU/Hardware Acceleration Issues

**Symptoms:**
- Frigate fails to start with TensorRT errors
- GPU not detected
- CUDA errors in logs

**Solutions:**
```bash
# Check if NVIDIA GPU is available
nvidia-smi

# Check if Docker has GPU access
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# If GPU issues persist, use CPU detector temporarily
# Edit config.yml and change detector to:
detectors:
  cpu1:
    type: cpu
    num_threads: 3
```

### 3. Camera Connection Issues

**Symptoms:**
- Frigate starts but cameras show as offline
- RTSP connection errors
- Timeout errors

**Solutions:**
```bash
# Test camera connectivity manually
ffmpeg -i rtsp://admin:%23Dakman7214@192.168.1.112:554/h264Preview_01_main -t 5 -f null -

# Check if cameras are accessible from host
curl -I http://192.168.1.112:554

# Verify camera credentials and URLs
```

### 4. Configuration File Issues

**Symptoms:**
- YAML syntax errors
- Invalid configuration parameters
- Missing required fields

**Solutions:**
```bash
# Validate YAML syntax
python3 -c "import yaml; yaml.safe_load(open('config.yml'))"

# Use the test configuration first
cp config_test.yml config.yml
docker-compose restart frigate
```

### 5. Permission Issues

**Symptoms:**
- Cannot write to media directory
- Configuration file not readable
- Database access denied

**Solutions:**
```bash
# Fix directory permissions
sudo chown -R 1000:1000 /home/dakota/anchorpoint/frigate/
sudo chmod -R 755 /home/dakota/anchorpoint/frigate/

# Check if directories exist
ls -la /home/dakota/anchorpoint/frigate/media/
ls -la /home/dakota/anchorpoint/frigate/config/
```

## Step-by-Step Debugging Process

### Step 1: Check Container Status
```bash
docker-compose ps
docker-compose logs frigate
```

### Step 2: Test Individual Components
```bash
# Test Mosquitto
docker-compose logs mosquitto

# Test camera connectivity
ffmpeg -i rtsp://admin:%23Dakman7214@192.168.1.112:554/h264Preview_01_main -t 5 -f null -

# Test GPU access
nvidia-smi
```

### Step 3: Use Minimal Configuration
```bash
# Backup current config
cp config.yml config.yml.backup

# Use test configuration
cp config_test.yml config.yml

# Restart Frigate
docker-compose restart frigate
```

### Step 4: Gradually Add Features
1. Start with CPU detector
2. Add one camera at a time
3. Enable recording after detection works
4. Add hardware acceleration last

## Log Analysis

### Common Log Messages and Meanings

**MQTT Connection:**
```
ERROR - MQTT connection failed
```
- Check Mosquitto is running
- Verify credentials
- Check network connectivity

**GPU Issues:**
```
ERROR - TensorRT model loading failed
```
- Check NVIDIA drivers
- Verify Docker GPU access
- Try CPU detector

**Camera Issues:**
```
ERROR - Failed to connect to camera
```
- Check camera IP and credentials
- Verify RTSP URL format
- Test network connectivity

## Recovery Commands

### Reset Everything
```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: This deletes all data)
docker-compose down -v

# Rebuild and start
docker-compose up -d --build
```

### Reset Just Frigate
```bash
# Remove Frigate container and volumes
docker-compose stop frigate
docker rm -f frigate
docker volume prune

# Restart Frigate
docker-compose up -d frigate
```

### Check System Resources
```bash
# Check disk space
df -h

# Check memory usage
free -h

# Check CPU usage
top

# Check GPU usage
nvidia-smi
```

## Getting Help

If issues persist:
1. Collect logs: `docker-compose logs frigate > frigate_logs.txt`
2. Check system resources
3. Try minimal configuration
4. Post logs and configuration to GitHub issues 