#!/bin/bash
# Setup automated memory garbage collection for PWA backend

echo "Setting up automated memory garbage collection..."

# Create the cron job script
cat > /tmp/memory_gc_cron.sh << 'EOF'
#!/bin/bash
# Automated memory garbage collection for PWA backend
cd /home/dakota/Desktop/anchorpoint
python3 memory_gc.py >> /tmp/memory_gc.log 2>&1
EOF

chmod +x /tmp/memory_gc_cron.sh

# Add cron job to run every 6 hours
CRON_JOB="0 */6 * * * /tmp/memory_gc_cron.sh"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "memory_gc_cron.sh"; then
    echo "Memory GC cron job already exists"
else
    # Add to crontab
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "Added memory GC cron job: runs every 6 hours"
fi

# Create a manual trigger script
cat > memory_gc_manual.sh << 'EOF'
#!/bin/bash
# Manual memory garbage collection trigger
echo "Running manual memory garbage collection..."
cd /home/dakota/Desktop/anchorpoint
python3 memory_gc.py
echo "Done. Check /tmp/memory_gc.log for detailed logs."
EOF

chmod +x memory_gc_manual.sh

echo "Setup complete!"
echo "- Automatic GC runs every 6 hours"
echo "- Manual trigger: ./memory_gc_manual.sh"
echo "- Logs saved to: /tmp/memory_gc.log"
echo ""
echo "Current swap usage:"
cat /proc/3768841/status | grep VmSwap 