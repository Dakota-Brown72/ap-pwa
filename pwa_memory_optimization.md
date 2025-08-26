# PWA Backend Memory Optimization Guide

## Current Situation Analysis
- **PWA Backend PID**: 3768841 using 48MB swap (main culprit)
- **Runtime**: 4+ days without restart
- **Memory Profile**: 1.4GB virtual, 8.6MB resident, 48MB swapped

## Identified Memory Leak Sources

### 1. Database Connection Leaks
**Issue**: Some error paths in `app.py` don't guarantee `conn.close()`
**Impact**: Accumulates over 4+ days of runtime

**Fix Locations in app.py**:
- Lines 355-357: Login endpoint database handling
- Lines 399-402: User update after login
- Lines 435-437: Get current user
- Lines 1048-1063: Admin endpoints

**Recommended Pattern**:
```python
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Instead of:
conn = get_db_connection()
# ... code that might fail ...
conn.close()

# Use context manager:
with get_db_connection() as conn:
    # ... database operations ...
    # Connection automatically closed even on exceptions
```

### 2. HTTP Session Leaks
**Issue**: `requests.Session()` objects not always closed (lines 525, 570)
**Impact**: Accumulates connection pools and memory

**Fix**:
```python
# In proxy_go2rtc_mse() around line 525
session = requests.Session()
try:
    # ... existing code ...
finally:
    session.close()  # Ensure cleanup
```

### 3. Stream Buffer Memory Growth
**Issue**: `stream_buffer.py` maintains growing buffers
**Impact**: Memory usage increases with stream activity

**Monitor**: Check buffer sizes in `/api/stream-buffer/status`

### 4. Background Thread Memory
**Issue**: Cleanup thread running every hour for 4+ days (lines 1185-1196)
**Impact**: Potential resource accumulation

## Implemented Solutions

### 1. Automated Memory Garbage Collection
- **Script**: `memory_gc.py` - runs targeted cleanup
- **Schedule**: Every 6 hours via cron job
- **Manual**: `./memory_gc_manual.sh`
- **Logs**: `/tmp/memory_gc.log`

### 2. System-Level Optimizations
- Cache clearing with `vm.drop_caches=1`
- Swappiness reduction during cleanup
- Memory pressure triggers

## Monitoring Commands

### Check Current Swap Usage:
```bash
for pid in $(ps -eo pid --no-headers); do 
  if [ -r /proc/$pid/smaps ]; then 
    swap=$(grep '^Swap:' /proc/$pid/smaps 2>/dev/null | awk '{sum+=$2} END {print sum}')
    if [ "$swap" -gt 1000 ] 2>/dev/null; then 
      echo "PID $pid: ${swap}kB - $(ps -p $pid -o comm= 2>/dev/null)"
    fi
  fi
done | sort -k3 -nr | head -10
```

### Check PWA Backend Memory:
```bash
cat /proc/3768841/status | grep -E '^(VmSize|VmRSS|VmSwap|VmPeak)'
```

### Monitor Memory Over Time:
```bash
tail -f /tmp/memory_monitor.log
```

## Recommendations for Code Fixes

### High Priority (Immediate):
1. **Add context managers for database connections**
2. **Fix HTTP session cleanup in MSE proxy**
3. **Add memory monitoring endpoint**: `/api/debug/memory`

### Medium Priority (Next Update):
1. **Reduce health check frequency** from 30s to 5min
2. **Add periodic stream buffer cleanup**
3. **Implement connection pooling with limits**

### Low Priority (Future):
1. **Move to async framework** (FastAPI) for better memory efficiency
2. **Add memory limits** to Docker container
3. **Implement request-scoped database connections**

## Expected Results
- **Immediate**: Reduced swap usage through garbage collection
- **Short-term**: Prevented memory growth with automated cleanup
- **Long-term**: Stable memory usage under 100MB resident

## Emergency Actions
If swap usage exceeds 100MB:
```bash
# Manual cleanup
./memory_gc_manual.sh

# If critical, restart PWA backend only:
docker restart pwa-backend
``` 