#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEPLOY_USER="pkanban"
DEPLOY_DIR="/opt/pkanban"
SOURCE_DIR="${SOURCE_DIR:-/tmp/pkanban}"
SERVICE_NAME="pkanban"
DOMAIN="pkanban.pearachute.com"

echo -e "${GREEN}🚀 Installing Kanban Board to production${NC}"
echo "Source: $SOURCE_DIR"
echo "Deploy: $DEPLOY_DIR"
echo "Domain: $DOMAIN"
echo "User: $DEPLOY_USER"
echo ""

# Function to check if running as root
check_root() {
    if [ "$(id -u)" -ne 0 ]; then
        echo -e "${RED}This script must be run as root (use sudo)${NC}"
        exit 1
    fi
}

# Function to create user
create_user() {
    echo -e "${YELLOW}👤 Setting up deployment user...${NC}"

    # Create user if not exists
    if ! getent passwd "$DEPLOY_USER" > /dev/null 2>&1; then
        useradd --system --home $DEPLOY_DIR --shell /bin/bash $DEPLOY_USER
        echo "User $DEPLOY_USER created"
    else
        echo "User $DEPLOY_USER already exists"
    fi

    # Ensure home directory exists and has correct ownership
    mkdir -p $DEPLOY_DIR
    chown $DEPLOY_USER:$DEPLOY_USER $DEPLOY_DIR

}

# Function to generate SSH key
generate_ssh_key() {
    echo -e "${YELLOW}👤 Setting up SSH key for deployment...${NC}"

    # Create .ssh directory
    mkdir -p $DEPLOY_DIR/.ssh
    chmod 700 $DEPLOY_DIR/.ssh
    chown $DEPLOY_USER:$DEPLOY_USER $DEPLOY_DIR/.ssh

    # Generate SSH key if not exists
    SSH_KEY="$DEPLOY_DIR/.ssh/id_ed25519"
    if [ ! -f "$SSH_KEY" ]; then
        echo -e "${BLUE}🔑 Generating ED25519 SSH key for $DEPLOY_USER...${NC}"
        sudo -u $DEPLOY_USER ssh-keygen -t ed25519 -f $SSH_KEY -N "" -C "$DEPLOY_USER@$DOMAIN"
    else
        echo "SSH key already exists at $SSH_KEY"
    fi

    # Display public key (for adding to GitHub)
    echo ""
    echo -e "${GREEN}📋 Add this public key to GitHub as a deploy key:${NC}"
    echo ""
    cat $SSH_KEY.pub
    echo ""
}

# Function to copy repo from source
copy_repo() {
    echo -e "${YELLOW}📥 Copying repository from $SOURCE_DIR...${NC}"

    if [ ! -d "$SOURCE_DIR" ]; then
        echo -e "${RED}Source directory $SOURCE_DIR does not exist${NC}"
        exit 1
    fi

    if [ -d "$DEPLOY_DIR" ]; then
        echo "Removing existing $DEPLOY_DIR..."
        rm -rf $DEPLOY_DIR
    fi

    cp -r $SOURCE_DIR $DEPLOY_DIR
    chown -R $DEPLOY_USER:$DEPLOY_USER $DEPLOY_DIR
    echo "Repository copied to $DEPLOY_DIR"
}

# Function to setup virtual environment
setup_virtualenv() {
    echo -e "${YELLOW}🐍 Setting up Python virtual environment...${NC}"

    if [ -f "$DEPLOY_DIR/venv/bin/python" ]; then
        echo "Virtualenv already exists"
    else
        sudo -u $DEPLOY_USER python3 -m venv $DEPLOY_DIR/venv
        echo "Virtualenv created"
    fi
}

# Function to install dependencies
install_dependencies() {
    echo -e "${YELLOW}📦 Installing system dependencies...${NC}"
    apt-get update
    apt-get install -y python3-venv python3-pip nginx git curl

    # Install Node.js 20 (required for frontend)
    echo -e "${YELLOW}📦 Installing Node.js 20...${NC}"
    if ! command -v node &>/dev/null || [ "$(node --version | cut -d'v' -f2 | cut -d'.' -f1)" -lt 20 ]; then
        curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
        apt-get install -y nodejs
        echo "Node.js $(node --version) installed"
    else
        echo "Node.js $(node --version) already installed"
    fi

    # Install certbot via snap (recommended by certbot)
    echo -e "${YELLOW}📦 Installing certbot via snap...${NC}"
    if ! command -v snap &>/dev/null; then
        apt-get install -y snapd
    fi
    
    # Ensure snap is up to date
    snap install core; snap refresh core
    
    # Install certbot
    if ! command -v certbot &>/dev/null; then
        snap install --classic certbot
        ln -sf /snap/bin/certbot /usr/bin/certbot
        echo "Certbot installed via snap"
    else
        echo "Certbot already installed"
    fi

    echo -e "${YELLOW}📦 Installing Python dependencies...${NC}"
    sudo -u $DEPLOY_USER $DEPLOY_DIR/venv/bin/pip install --upgrade pip
    sudo -u $DEPLOY_USER $DEPLOY_DIR/venv/bin/pip install -r $DEPLOY_DIR/backend/requirements.txt
}

# Function to build frontend
build_frontend() {
    echo -e "${YELLOW}🏗️ Building frontend...${NC}"
    sudo -u $DEPLOY_USER bash -c "cd $DEPLOY_DIR/frontend && rm -rf node_modules package-lock.json"
    sudo -u $DEPLOY_USER bash -c "cd $DEPLOY_DIR/frontend && npm install"
    sudo -u $DEPLOY_USER bash -c "cd $DEPLOY_DIR/frontend && npm run build"
}

# Function to setup database
setup_database() {
    echo -e "${YELLOW}🗄️ Setting up database...${NC}"
    if [ ! -f "$DEPLOY_DIR/pkanban.db" ]; then
        sudo -u $DEPLOY_USER DATABASE_PATH=$DEPLOY_DIR/pkanban.db $DEPLOY_DIR/venv/bin/python $DEPLOY_DIR/manage.py init
        echo "Database initialized"
    else
        echo "Database already exists"
    fi
}

# Function to setup systemd service
setup_systemd() {
    echo -e "${YELLOW}⚙️ Setting up systemd service...${NC}"
    cp $DEPLOY_DIR/sys/systemd/pkanban.service /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable pkanban
    # Restart service if it's already running to pick up config changes
    if systemctl is-active --quiet pkanban; then
        systemctl restart pkanban
        echo "Kanban service restarted with new configuration"
    fi
    echo "Systemd service configured"
}

# Function to setup nginx
setup_nginx() {
    echo -e "${YELLOW}🌐 Setting up nginx...${NC}"
    # Install nginx config but don't test/reload yet (certs don't exist)
    cp $DEPLOY_DIR/sys/nginx/pkanban.pearachute.com.conf /etc/nginx/sites-available/
    ln -sf /etc/nginx/sites-available/pkanban.pearachute.com.conf /etc/nginx/sites-enabled/
    echo "Nginx config installed (SSL pending certbot)"
}

# Function to setup sudoers for pkanban user
setup_sudoers() {
    echo -e "${YELLOW}🔐 Setting up sudoers permissions...${NC}"

    # Three narrowly scoped rules, no blanket NOPASSWD:
    #   restart          - what deploy.sh has always needed
    #   daemon-reload    - and the cp below, so deploy.sh can install a changed
    #   cp <exact args>    unit itself. Without these a unit edit reaches the
    #                      repo and the box but never the running service, and
    #                      says nothing about it -- which is how EnvironmentFile
    #                      went unapplied long enough for /opt/pkanban/.env to be
    #                      silently ignored.
    #
    # The cp rule pins both paths, so it grants exactly "install this project's
    # unit file" and not "copy anything anywhere". Note it does let anyone who
    # can write $DEPLOY_DIR/sys/systemd/pkanban.service choose what the unit
    # says, including User=root -- acceptable here only because pushing to main
    # already runs arbitrary code as this user. Do not widen it further.
    cat > /etc/sudoers.d/pkanban-restart <<EOF
pkanban ALL=(ALL) NOPASSWD: /bin/systemctl restart pkanban
pkanban ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload
pkanban ALL=(ALL) NOPASSWD: /bin/cp $DEPLOY_DIR/sys/systemd/pkanban.service /etc/systemd/system/pkanban.service
EOF
    chmod 440 /etc/sudoers.d/pkanban-restart

    # A malformed sudoers file locks out every rule in it, including the
    # restart that deploys depend on. Fail the install rather than discover
    # that on the next deploy.
    if ! visudo -c -f /etc/sudoers.d/pkanban-restart; then
        echo -e "${RED}Sudoers file is invalid, removing it${NC}"
        rm -f /etc/sudoers.d/pkanban-restart
        exit 1
    fi

    echo "Sudoers configured - pkanban can restart, daemon-reload, and install the unit"
}

# Function to setup SSL with Let's Encrypt
setup_ssl() {
    echo -e "${YELLOW}🔒 Setting up SSL with Let's Encrypt...${NC}"
    
    # First, temporarily disable nginx config to get certificates
    echo "Temporarily disabling nginx SSL config for certificate generation..."

    # Start nginx if it's not running
    if ! systemctl is-active --quiet nginx; then
        systemctl start nginx
    fi

    # Disable any existing pkanban configs
    if [ -L "/etc/nginx/sites-enabled/$DOMAIN.conf" ] || [ -f "/etc/nginx/sites-enabled/$DOMAIN.conf" ]; then
        rm -f /etc/nginx/sites-enabled/$DOMAIN.conf
        echo "Disabled existing pkanban nginx config"
    fi

    # Create a simple nginx config for HTTP only to pass certbot challenges
    cat > /etc/nginx/sites-available/$DOMAIN-http.conf << EOF
server {
    listen 80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://\$server_name\$request_uri;
    }
}
EOF
    ln -sf /etc/nginx/sites-available/$DOMAIN-http.conf /etc/nginx/sites-enabled/

    # Test and reload nginx
    if nginx -t; then
        systemctl reload nginx
        echo "Nginx reloaded successfully"
    else
        echo "Nginx configuration test failed"
        return 1
    fi
    
    # Get certificates using webroot method (more reliable than nginx plugin)
    echo "Obtaining SSL certificates..."
    certbot certonly --webroot -w /var/www/html \
        --non-interactive --agree-tos --email admin@$DOMAIN \
        -d $DOMAIN && {
        echo "SSL certificates obtained successfully"
    } || {
        echo -e "${RED}Certificate setup failed. You may need to run certbot manually:${NC}"
        echo "certbot certonly --webroot -w /var/www/html -d $DOMAIN"
        # Restore original config and exit
        rm -f /etc/nginx/sites-enabled/$DOMAIN-http.conf
        if [ -f "/etc/nginx/sites-enabled/$DOMAIN.conf.bak" ]; then
            mv /etc/nginx/sites-enabled/$DOMAIN.conf.bak /etc/nginx/sites-enabled/$DOMAIN.conf
        fi
        return 1
    }
    
    # Remove temporary HTTP config
    rm -f /etc/nginx/sites-enabled/$DOMAIN-http.conf
    rm -f /etc/nginx/sites-available/$DOMAIN-http.conf

    # Restore original nginx config with SSL
    if [ -f "/etc/nginx/sites-enabled/$DOMAIN.conf.bak" ]; then
        mv /etc/nginx/sites-enabled/$DOMAIN.conf.bak /etc/nginx/sites-enabled/$DOMAIN.conf
    else
        # Re-enable the pkanban config if it wasn't backed up
        ln -sf /etc/nginx/sites-available/$DOMAIN.conf /etc/nginx/sites-enabled/
    fi
    
    # Test and reload nginx with SSL config
    nginx -t && systemctl reload nginx && {
        echo "Nginx reloaded with SSL configuration"
    } || {
        echo -e "${RED}Nginx configuration test failed after SSL setup${NC}"
        return 1
    }
    
    # Setup automatic certificate renewal
    echo "Setting up automatic certificate renewal..."
    (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet --deploy-hook 'systemctl reload nginx'") | crontab -
    
    echo "SSL setup complete!"
}

# Function to create admin user
create_admin_user() {
    echo -e "${YELLOW}👔 Creating admin user...${NC}"
    read -p "Enter admin username: " ADMIN_USER
    echo -n "Enter admin password: "
    stty -echo
    read ADMIN_PASS
    stty echo
    echo
    sudo -u $DEPLOY_USER DATABASE_PATH=$DEPLOY_DIR/pkanban.db $DEPLOY_DIR/venv/bin/python $DEPLOY_DIR/manage.py user-create $ADMIN_USER $ADMIN_PASS --admin
}

# Function to start service
start_service() {
    echo -e "${GREEN}🚀 Starting pkanban service...${NC}"
    systemctl restart pkanban  # Use restart to ensure it picks up any config changes
    systemctl status pkanban --no-pager
}

# Main installation flow
main() {
    check_root

    echo -e "${GREEN}Step 1: User setup${NC}"
    create_user

    echo -e "${GREEN}Step 2: Copy repository${NC}"
    copy_repo

    echo -e "${GREEN}Step 3: SSH key setup${NC}"
    generate_ssh_key

    echo -e "${GREEN}Step 4: Application setup${NC}"
    setup_virtualenv
    install_dependencies
    build_frontend

    echo -e "${GREEN}Step 5: Database setup${NC}"
    setup_database

    echo -e "${GREEN}Step 6: Service configuration${NC}"
    setup_systemd
    setup_nginx
    setup_sudoers

    echo -e "${GREEN}Step 7: SSL setup${NC}"
    setup_ssl

    echo -e "${GREEN}Step 8: Admin user${NC}"
    create_admin_user

    echo -e "${GREEN}Step 9: Start service${NC}"
    start_service

    echo ""
    echo -e "${GREEN}✅ Installation complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Add the SSH public key above to GitHub as a deploy key"
    echo "2. Test deployment with: sudo -u pkanban $DEPLOY_DIR/sys/scripts/deploy.sh"
    echo ""
    echo "Your Kanban board is now running at: https://$DOMAIN"
    echo ""
    echo "Useful commands:"
    echo "  Check service status: systemctl status pkanban"
    echo "  View logs: journalctl -u pkanban -f"
    echo "  Restart service: sudo systemctl restart pkanban"
    echo "  Update application: sudo -u pkanban $DEPLOY_DIR/sys/scripts/deploy.sh"
}

# Run installation
main "$@"
