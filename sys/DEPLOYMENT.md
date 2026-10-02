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

## Billing (Stripe)

The code ships dormant. Deploying it runs the migration and installs the
`stripe` package but changes nothing for users: limits apply only when
`BILLING_ENABLED=true`, and payments only work once the three `STRIPE_*`
settings exist. Neither is set by the deploy, so turning billing on is a
deliberate, reversible sequence. Do it in this order.

### 1. Stripe dashboard

Do this first in **test mode**, then repeat it in live mode.

- **Product and Price.** One product, one recurring Price: **$6.00 per month**.
  The Pricing page advertises exactly that, and `billing-check` fails if the
  Price differs. Copy the Price id (`price_...`).
- **Customer portal.** Settings > Billing > Customer portal: allow customers to
  cancel subscriptions and update payment methods. Live mode has no
  configuration until someone saves one here, and without it "Manage
  subscription" fails for everyone.
- **Webhook.** Developers > Webhooks > add an endpoint for
  `https://pkanban.pearachute.com/api/billing/webhook` with these events:
  `checkout.session.completed`, `customer.subscription.created`,
  `customer.subscription.updated`, `customer.subscription.deleted`,
  `invoice.payment_failed`. Copy its signing secret (`whsec_...`).
- **API key.** The secret key, or a restricted key that can create Checkout
  Sessions and Customer portal sessions and read Subscriptions. Whichever you
  pick, the smoke test below is what proves it works.

### 2. Server settings

Add to `/opt/pkanban/.env` (the deploy does not manage this file), leaving
`BILLING_ENABLED` **unset** for now:

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

```bash
sudo systemctl restart pkanban
```

### 3. Preflight

`billing-check` is read-only. It never prints a secret. It exits 1 if anything
would break payments or mislead a customer.

```bash
sudo -u pkanban bash -c 'set -a; . /opt/pkanban/.env; set +a; cd /opt/pkanban && venv/bin/python manage.py billing-check'
```

It checks the settings, that the Price is recurring and matches the Pricing
page, that the webhook points here and is subscribed to all five events, and
that a Customer portal exists. It also lists the free accounts that would be
blocked from creating anything the moment limits switch on. Use `--no-stripe`
to skip the Stripe calls and `--json` for a machine-readable report.

A check the key is not permitted to make shows as `warn`, not `FAIL`; verify
that one in the dashboard.

### 4. Put the accounts it listed on Pro

Anyone the preflight lists is at a limit already. **Start with the owner of the
Dev board**: it holds about a hundred cards, so without this the project's own
board stops accepting cards the moment limits switch on. Admin > Users > Edit >
Plan > Pro. (An account Stripe knows about has its plan reset by Stripe's next
event for that customer; for these, that means subscribing instead.)

### 5. Smoke test, in test mode, with limits still off

Subscribing works whether or not limits are on, which is what makes this safe.
With the test keys from step 2, as a brand new account:

1. Settings > Plan > **Upgrade to Pro**; pay with Stripe's test card
   `4242 4242 4242 4242`, any future expiry, any CVC.
2. You return to Settings > Plan. It should say it is waiting, then flip to
   **Pro** by itself within a few seconds. If it gives up instead, the webhook
   is not arriving: Developers > Webhooks > the endpoint shows the deliveries
   and the error.
3. **Manage subscription** opens the portal. Cancel there. After the webhook,
   the account is Free again.

### 6. Go live

Swap in the **live** key, live Price id and the live webhook's signing secret
in `.env`, restart, and run the preflight again. It should say `Ready.` and
`(live mode)`. Then switch limits on:

```
BILLING_ENABLED=true
```

```bash
sudo systemctl restart pkanban
```

Re-run the preflight to confirm it reports limits as enforced, then repeat the
smoke test with a real card on a new account (refund yourself in the
dashboard afterwards):

1. Create boards until the sixth is refused. You should get the "Board limit
   reached" notice, not an error.
2. Upgrade. The limit should lift.
3. Cancel in the portal. The account returns to Free **with every board and
   card still there**: over a limit you can read, edit, reorder and delete, but
   not create.

### Turning it back off

- **Stop enforcing limits:** unset `BILLING_ENABLED` and restart. Immediate, and
  nothing is touched: every account keeps its data and its plan.
- **Stop taking new payments:** unset `STRIPE_PRICE_ID` and restart; the
  Upgrade button disappears (the API answers 503). Existing subscriptions keep
  renewing and the webhook keeps syncing plans as long as the other two
  settings stay.

### Watching it

```bash
sudo journalctl -u pkanban | grep -i stripe
```

A webhook that answers 502 means Stripe could not be reached while applying an
event; Stripe retries those by itself. A 400 means a bad signature (check
`STRIPE_WEBHOOK_SECRET` matches the endpoint); a 503 means it is unset.

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