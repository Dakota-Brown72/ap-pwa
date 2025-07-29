# 📱 Mobile Browser Stream Testing Guide

## 🎯 **Testing Checklist for iOS Safari**

### ✅ **Pre-Test Setup**
- [ ] Ensure you're on a mobile device or using Safari DevTools
- [ ] Clear browser cache and cookies
- [ ] Disable any content blockers or VPN
- [ ] Test on both WiFi and cellular data

### ✅ **Video Element Requirements (iOS Safari)**
- [ ] `muted` attribute present ✅
- [ ] `autoplay` attribute present ✅
- [ ] `playsinline` attribute present ✅
- [ ] `controls` attribute present ✅

### ✅ **Stream Technology Priority (Per Frigate Docs)**
- [ ] **WebRTC** - Primary for mobile (most compatible) ✅
- [ ] **MSE** - Fallback for desktop browsers ✅
- [ ] **HLS** - Last resort fallback ✅

### ✅ **Network Headers Check**
Use browser DevTools Network tab to verify:
- [ ] WebRTC connections on port 8555
- [ ] `Access-Control-Allow-Origin: *`
- [ ] `Cache-Control: no-store, no-cache, must-revalidate`
- [ ] `CF-Cache-Status: BYPASS` (Cloudflare)

---

## 🔍 **Debugging Steps**

### **1. Safari DevTools (macOS)**
```bash
# Connect iPhone to Mac, then:
# Safari → Develop → Your iPhone → Inspect Page
```

### **2. Check Network Tab**
- Look for WebRTC connections
- Verify WebRTC endpoint responses
- Check for CORS errors
- Verify authentication headers

### **3. Console Errors**
Common mobile streaming errors:
- `MEDIA_ERR_ABORTED` (1) - Stream interrupted
- `MEDIA_ERR_NETWORK` (2) - Network issues
- `MEDIA_ERR_DECODE` (3) - Format not supported
- `MEDIA_ERR_SRC_NOT_SUPPORTED` (4) - Source not supported

### **4. Test Stream URLs Directly**
```bash
# Test WebRTC endpoint
curl -I "https://dakota.anchorpointsystems.com/api/go2rtc/webrtc?src=frontyard_live&token=YOUR_TOKEN"

# Test MSE endpoint
curl -I "https://dakota.anchorpointsystems.com/api/go2rtc/mse/frontyard_live?token=YOUR_TOKEN"
```

---

## 🚨 **Common Mobile Issues & Solutions**

### **Issue: WebRTC Connection Failed**
**Cause:** Missing WebRTC candidates or port forwarding
**Solution:** ✅ Fixed - Added WebRTC candidates to go2rtc config

### **Issue: MSE Not Supported on Mobile**
**Cause:** iOS Safari MSE limitations
**Solution:** ✅ Fixed - WebRTC prioritized for mobile browsers

### **Issue: Autoplay Blocked**
**Cause:** Missing `muted` attribute
**Solution:** ✅ Fixed - Video elements have `muted` attribute

### **Issue: Fullscreen Hijack**
**Cause:** Missing `playsinline` attribute
**Solution:** ✅ Fixed - Video elements have `playsinline` attribute

### **Issue: Cloudflare Caching**
**Cause:** Cloudflare caching streaming data
**Solution:** ✅ Fixed - Cache bypass headers added

---

## 📊 **Performance Monitoring**

### **Stream Metrics to Monitor**
- Initial load time (should be < 3 seconds)
- WebRTC connection establishment time (should be < 2 seconds)
- Buffer health (should maintain stable connection)
- Error rate (should be < 1%)

### **Mobile-Specific Metrics**
- Battery usage during streaming
- Memory usage
- Network data consumption
- CPU usage for video decoding

---

## 🔧 **Advanced Debugging**

### **Enable WebRTC Debug Logging**
```javascript
// Add to browser console
localStorage.setItem('webrtc-debug', 'true');
```

### **Test Different Video Formats**
- **WebRTC** (`.webrtc`) - Primary format for mobile
- **MSE** (`.mp4`) - Fallback format for desktop
- **HLS** (`.m3u8`) - Last resort fallback

### **Network Conditions Testing**
- Test on slow 3G connection
- Test with packet loss simulation
- Test with high latency (>200ms)

---

## 📱 **Device-Specific Testing**

### **iOS Safari (Most Critical)**
- iPhone 12+ (iOS 15+)
- iPad (iOS 15+)
- Safari DevTools on macOS

### **Android Chrome**
- Samsung Galaxy S21+
- Google Pixel 6+
- Chrome DevTools

### **Other Mobile Browsers**
- Firefox Mobile
- Edge Mobile
- Samsung Internet

---

## 🎯 **Success Criteria**

### **✅ Stream Should Work When:**
- [ ] Video plays automatically on page load
- [ ] No console errors related to video
- [ ] Stream continues playing for >5 minutes
- [ ] Works on both WiFi and cellular
- [ ] No authentication errors
- [ ] Proper video controls visible
- [ ] Fullscreen mode works correctly

### **✅ Performance Targets:**
- [ ] Initial load: <3 seconds
- [ ] WebRTC connection: <2 seconds
- [ ] No buffering after initial load
- [ ] Smooth playback at 30fps
- [ ] Low battery usage
- [ ] Responsive UI during streaming

---

## 🆘 **Emergency Fallbacks**

### **If WebRTC Fails:**
1. Try MSE format
2. Try HLS format
3. Show static snapshot
4. Display error with retry button

### **If Authentication Fails:**
1. Redirect to login
2. Refresh token automatically
3. Show "Session expired" message

### **If Network Fails:**
1. Show "Check connection" message
2. Auto-retry after 5 seconds
3. Graceful degradation to snapshot 