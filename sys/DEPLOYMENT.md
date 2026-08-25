# Production Deployment Guide

This guide will help you deploy the Kanban Board application to production on an Ubuntu LTS server with nginx.

## Prerequisites

- Ubuntu LTS server with root/sudo access
- Domain name `pkanban.pearachute.com` pointing to your server
- Git installed

## Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/japherwocky/pkanban.git /opt/pkanban
   cd /opt/pkanban
   ```

2. Make scripts executable:
   ```bash
   chmod +x sys/scripts/*.sh
   ```

3. Run the deployment script:
   ```bash
   sudo sys/scripts/deploy.sh
   ```

## Manual Deployment Steps

If you prefer to deploy manually, follow these steps:

### 1. System Setup

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y python3-venv python3-pip nginx certbot python3-certbot-nginx git
```

### 2. Application User

```bash
# Create system user
sudo useradd --system --home /opt/pkanban --shell /bin/bash pkanban

# Create directories
sudo mkdir -p /opt/pkanban/{data,logs}
sudo mkdir -p /var/www/certbot
sudo chown -R pkanban:pkanban /opt/pkanban
```

### 3. Application Setup

```bash
# Clone repository
sudo -u pkanban git clone https://github.com/japherwocky/pkanban.git /opt/pkanban

# Setup virtual environment
sudo -u pkanban python3 -m venv /opt/pkanban/venv

# Install Python dependencies
sudo -u pkanban /opt/pkanban/venv/bin/pip install --upgrade pip
sudo -u pkanban /opt/pkanban/venv/bin/pip install -r /opt/pkanban/backend/requirements.txt

# Build frontend
sudo -u pkanban bash -c "cd /opt/pkanban/frontend && npm install && npm run build"
```

### 4. Database Setup

```bash
# Initialize database
sudo -u pkanban /opt/pkanban/venv/bin/python /opt/pkanban/manage.py init

# Create admin user
sudo -u pkanban /opt/pkanban/venv/bin/python /opt/pkanban/manage.py user-create admin yourpassword --admin
```

### 5. Systemd Service

```bash
# Copy service file
sudo cp /opt/pkanban/sys/systemd/pkanban.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable pkanban
sudo systemctl start pkanban
```

### 6. Nginx Configuration

```bash
# Copy nginx config
sudo cp /opt/pkanban/sys/nginx/pkanban.pearachute.com.conf /etc/nginx/sites-available/
sudo ln -sf /etc/nginx/sites-available/pkanban.pearachute.com.conf /etc/nginx/sites-enabled/

# Test and reload nginx
sudo nginx -t
sudo systemctl reload nginx
```

### 7. SSL Certificate

```bash
# Run SSL setup script
sudo /opt/pkanban/sys/scripts/setup-ssl.sh

# Or manually:
sudo certbot --nginx -d pkanban.pearachute.com
```

## Configuration

### Environment Variables

Copy the environment template and customize:

```bash
sudo -u pkanban cp /opt/pkanban/sys/config/production.env /opt/pkanban/.env
```

Edit `/opt/pkanban/.env` to configure:
- Database path
- JWT secret key (optional -- see below)
- CORS origins
- Email settings (optional)

The systemd unit loads this file via `EnvironmentFile=`. If you are upgrading
an install from before that line existed, reinstall the unit so your settings
actually reach the service:

```bash
sudo cp /opt/pkanban/sys/systemd/pkanban.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl restart pkanban
```

Confirm what the running service actually has:

```bash
systemctl show pkanban --property=Environment
```

### JWT signing key

You do not have to set one. With `JWT_SECRET_KEY` unset the service generates a
random key on first start and stores it in `.jwt_secret` beside the database
(mode 0600), reusing it across restarts.

To manage the key yourself, generate one and put it in `/opt/pkanban/.env`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

The service **refuses to start** if `JWT_SECRET_KEY` is left as an example
value from this repository. The repo is public, so those values are known to
everyone -- a token signed with one can be forged for any account.

Changing the key invalidates every existing session, so expect users to log in
again after the first restart.

### Service Management

```bash
# Check service status
sudo systemctl status pkanban

# View logs
sudo journalctl -u pkanban -f

# Restart service
sudo systemctl restart pkanban

# Stop service
sudo systemctl stop pkanban
```

## Maintenance

### Updates

To update the application:

```bash
# Pull latest changes
cd /opt/pkanban
sudo -u pkanban git pull

# Rebuild frontend (if needed)
sudo -u pkanban bash -c "cd frontend && npm install && npm run build"

# Restart service
sudo systemctl restart pkanban
```

### Database Management

```bash
# Check database status
sudo -u pkanban /opt/pkanban/venv/bin/python /opt/pkanban/manage.py status

# Backup database
sudo cp /opt/pkanban/data/pkanban.db /opt/pkanban/data/pkanban.db.backup.$(date +%Y%m%d)
```

### SSL Certificate Renewal

Let's Encrypt certificates are automatically renewed via cron. To test renewal:

```bash
sudo certbot renew --dry-run
```

## Troubleshooting

### Service Won't Start

Check logs for errors:
```bash
sudo journalctl -u pkanban -f
```

Common issues:
- Missing dependencies: `sudo -u pkanban /opt/pkanban/venv/bin/pip install -r backend/requirements.txt`
- Permissions: Ensure `/opt/pkanban` is owned by `pkanban` user
- Database: Run `sudo -u pkanban /opt/pkanban/venv/bin/python /opt/pkanban/manage.py init`

### Nginx Issues

Test nginx configuration:
```bash
sudo nginx -t
```

Check nginx logs:
```bash
sudo tail -f /var/log/nginx/pkanban.pearachute.com.error.log
```

### SSL Issues

Check certificate status:
```bash
sudo certbot certificates
```

Request new certificate:
```bash
sudo certbot --nginx -d pkanban.pearachute.com --force-renewal
```

## Security Considerations

1. **JWT Secret**: Never run on an example key. The service generates a real
   one if you set nothing, and refuses to start on a placeholder -- but verify
   with `systemctl show pkanban --property=Environment` that what you *think*
   is configured is what the process actually received
2. **Regular Updates**: Keep system packages updated
3. **Backups**: Regularly backup the SQLite database
4. **Firewall**: Configure UFW or similar firewall
5. **Monitoring**: Set up monitoring for service health

## Performance Tuning

For higher traffic scenarios, consider:

1. **Process Management**: Use gunicorn with uvicorn workers instead of uvicorn directly
2. **Database**: Migrate to PostgreSQL for better performance
3. **Caching**: Add Redis caching for frequently accessed data
4. **CDN**: Use CDN for static assets

## Directory Structure

```
/opt/pkanban/
├── backend/                 # FastAPI backend
├── frontend/                # Svelte frontend
├── sys/                     # Deployment configuration
│   ├── nginx/              # Nginx configs
│   ├── systemd/            # Service files
│   ├── scripts/            # Deployment scripts
│   └── config/             # Environment configs
├── data/                   # Database files
├── venv/                   # Python virtual environment
└── .env                    # Environment variables
```

## Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review service logs: `sudo journalctl -u pkanban`
3. Review nginx logs: `sudo tail -f /var/log/nginx/pkanban.pearachute.com.error.log`
4. Check the GitHub repository for known issues