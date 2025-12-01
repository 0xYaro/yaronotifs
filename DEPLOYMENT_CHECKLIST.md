# Deployment Checklist

Use this checklist to ensure proper deployment of the Yaronotifs bot.

## Pre-Deployment (Local Machine)

- [ ] Clone repository
- [ ] Create `.env` file from `.env.example`
- [ ] Add Telegram API credentials to `.env`:
  - [ ] `TELEGRAM_API_ID`
  - [ ] `TELEGRAM_API_HASH`
  - [ ] `TELEGRAM_PHONE`
- [ ] Add output channel ID to `.env`:
  - [ ] `OUTPUT_CHANNEL_ID` (format: -1001234567890)
  - [ ] Verify listener account is channel admin with full permissions
- [ ] Add status destination ID to `.env` (optional):
  - [ ] `STATUS_DESTINATION_ID` (leave empty to disable status reports)
- [ ] Add Gemini API key to `.env`:
  - [ ] `GEMINI_API_KEY`
- [ ] Install local dependencies: `pip install -r requirements.txt`
- [ ] Run session creation: `python scripts/create_session.py`
- [ ] Verify `.session` file was created
- [ ] Test locally (optional): `python main.py`

## AWS Server Setup

- [ ] Provision Ubuntu server (20.04+)
- [ ] Configure security group (allow SSH)
- [ ] Set up SSH key authentication
- [ ] Upload project files: `scp -r yaronotifs/ user@server:~/`
- [ ] Upload `.env` file: `scp .env user@server:~/yaronotifs/`
- [ ] Upload `.session` file: `scp *.session user@server:~/yaronotifs/`

## Installation on Server

- [ ] SSH into server: `ssh user@server`
- [ ] Navigate to project: `cd ~/yaronotifs`
- [ ] Run setup script: `./scripts/setup.sh`
- [ ] Verify Python version: `python3 --version` (should be 3.10+)
- [ ] Verify virtual environment: `source venv/bin/activate`
- [ ] Verify dependencies: `pip list`

## Testing

- [ ] Test manual run: `python main.py`
- [ ] Verify Telegram connection
- [ ] Verify channel monitoring
- [ ] Send test message to monitored channel
- [ ] Confirm message appears in output channel
- [ ] Test Chinese translation (if applicable)
- [ ] Test PDF analysis (if applicable)
- [ ] Check for errors in logs: `tail -f logs/bot.log`

## Production Deployment

- [ ] Stop manual test: `Ctrl+C`
- [ ] Enable systemd service: `sudo systemctl enable yaronotifs`
- [ ] Start service: `sudo systemctl start yaronotifs`
- [ ] Check service status: `sudo systemctl status yaronotifs`
- [ ] Verify logs: `tail -f logs/bot.log`
- [ ] Test auto-restart: `sudo systemctl restart yaronotifs`
- [ ] Verify service survives reboot: `sudo reboot` then check status

## Post-Deployment

- [ ] Monitor logs for 24 hours
- [ ] Verify all pipelines are working
- [ ] Set up log rotation (optional)
- [ ] Set up monitoring/alerts (optional)
- [ ] Document any custom configuration
- [ ] Schedule regular backups of `.session` file

## Channel Permissions Verification

- [ ] Listener account is added to output channel
- [ ] Listener account has Administrator role with full permissions
- [ ] Test by sending a message to monitored channel
- [ ] Verify message appears in output channel
- [ ] If using STATUS_DESTINATION_ID, verify admin access to that channel too

## Verification Commands

```bash
# Check service status
sudo systemctl status yaronotifs

# View real-time logs
tail -f logs/bot.log

# View error logs
tail -f logs/bot_error.log

# View systemd logs
sudo journalctl -u yaronotifs -f

# Check if bot is connected
grep "Connected as" logs/bot.log | tail -1

# Check message processing
grep "New message" logs/bot.log | tail -10
```

## Troubleshooting

If any step fails, refer to the [Troubleshooting section in README.md](README.md#troubleshooting).

## Security Verification

- [ ] `.env` file is not world-readable: `ls -la .env`
- [ ] Session file is not world-readable: `ls -la *.session`
- [ ] `.gitignore` excludes sensitive files
- [ ] SSH password authentication is disabled
- [ ] Firewall is configured properly
- [ ] API keys are valid and active

## Success Criteria

Your deployment is successful when:

1. ✅ Service status shows "active (running)"
2. ✅ Logs show "BOT IS RUNNING"
3. ✅ Logs show "Connected as: [your name]"
4. ✅ Test messages are processed and forwarded
5. ✅ No errors in logs after 1 hour of operation
6. ✅ Service automatically restarts after server reboot

## Rollback Plan

If deployment fails:

1. Stop the service: `sudo systemctl stop yaronotifs`
2. Review logs: `tail -100 logs/bot_error.log`
3. Fix issues identified
4. Test manually: `python main.py`
5. Restart service once fixed

## Support

For issues during deployment:
- Check README.md troubleshooting section
- Review logs in `logs/` directory
- Verify all checklist items are complete
