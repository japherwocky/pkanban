#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOY_DIR="/opt/pkanban"

# The commit the server was on before this deploy pulled. Change detection has
# to compare against it rather than HEAD~1: a push of several commits moves
# HEAD by more than one, so HEAD~1 sees only the final commit of the push. A
# requirements.txt change in any earlier commit was invisible, and the service
# restarted without its new dependencies.
PREVIOUS_SHA=""

# Did anything matching $1 change between the pre-deploy commit and now?
changed_since_previous() {
    if [ -z "$PREVIOUS_SHA" ]; then
        # No baseline to compare against, so do the work rather than silently
        # skip it -- a needless pip install is cheap, a missing one is not.
        return 0
    fi
    git diff --name-only "$PREVIOUS_SHA" HEAD | grep -q "$1"
}

echo -e "${GREEN}🚀 Deploying Kanban Board updates${NC}"
echo "Deploy Directory: $DEPLOY_DIR"
echo ""

# Check if running as pkanban user
check_user() {
    CURRENT_USER=$(whoami)
    if [ "$CURRENT_USER" != "pkanban" ]; then
        echo -e "${RED}This script must be run as the pkanban user:${NC}"
        echo "  sudo -u pkanban $DEPLOY_DIR/sys/scripts/deploy.sh"
        exit 1
    fi
}

# Function to git pull
git_pull() {
    echo -e "${YELLOW}📥 Pulling latest changes...${NC}"

    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo "Current branch: $CURRENT_BRANCH"

    # Captured before the reset, so change detection can see the whole push.
    #
    # DEPLOY_PREVIOUS_SHA wins when set. deploy-production.yml does its own
    # `git reset --hard origin/main` before invoking this script -- so that a
    # change to this file takes effect on the deploy that ships it, rather than
    # the one after -- which means HEAD here is already the new commit and
    # capturing it locally yields an empty diff every time. The workflow passes
    # the real pre-deploy SHA instead. The fallback covers running this script
    # by hand.
    PREVIOUS_SHA="${DEPLOY_PREVIOUS_SHA:-$(git rev-parse HEAD)}"

    git fetch origin
    git reset --hard origin/$CURRENT_BRANCH

    echo "Code updated ($PREVIOUS_SHA -> $(git rev-parse HEAD))"
}

# Function to update dependencies
update_dependencies() {
    echo -e "${YELLOW}📦 Installing Python dependencies...${NC}"

    # Unconditional, deliberately, even though changed_since_previous() is
    # correct again. The costs are lopsided: a redundant pip install is a few
    # seconds, a skipped one restarts the service against a missing module.
    #
    # This is not hypothetical. The deploy that introduced peewee-migrate
    # skipped this step and died at run_migrations with ModuleNotFoundError,
    # because the workflow's own `git reset --hard` had already moved HEAD
    # before git_pull() captured a baseline, leaving every diff empty.
    #
    # It also has to stay ahead of run_migrations, which imports the package
    # this installs.
    $DEPLOY_DIR/venv/bin/pip install -q -r $DEPLOY_DIR/backend/requirements.txt

    echo "Dependencies up to date"
}

# Function to build frontend
build_frontend() {
    echo -e "${YELLOW}🏗️ Building frontend...${NC}"

    cd $DEPLOY_DIR/frontend
    # npm ci, not npm install: the build is reproducible now.
    #
    # This used to delete package-lock.json first, because the committed
    # lockfile had been generated on Windows and npm records only the optional
    # dependencies of the platform it resolved on (npm/cli#4828). It listed
    # @rollup/rollup-win32-* and nothing else, so npm ci installed no native
    # binary here and vite died with "Cannot find module
    # @rollup/rollup-linux-x64-gnu". Deleting it worked, at the cost of
    # re-resolving floating versions on every deploy -- two deploys of the same
    # commit could ship different dependency trees.
    #
    # The lockfile now carries the whole platform matrix (linux, win32, darwin
    # -- see frontend/LOCKFILE.md), so npm ci picks the linux binaries
    # here and the win32 ones on a dev laptop, from the same file.
    rm -rf node_modules
    npm ci
    npm run build
    echo "Frontend rebuilt"
}

# Function to run database migrations
run_migrations() {
    echo -e "${YELLOW}🗄️ Running database migrations...${NC}"

    # Deliberately NOT gated on changed_since_previous, unlike the pip step
    # above. That helper answers "did migration files change in this push",
    # but the question that matters is "does this database have unapplied
    # migrations" -- and only the migratehistory table knows. A deploy that
    # failed partway, a rollback and re-deploy, or a database restored from an
    # older backup all leave migrations pending with no diff to detect them.
    # peewee-migrate skips what it has already applied, so always asking costs
    # one query.
    #
    # This must happen before restart_service. The old code is still serving
    # traffic at this point and does not know about the new columns, so
    # migrating first means the new code never starts against an old schema.
    cd $DEPLOY_DIR

    # Migrate the database the SERVICE uses, which is not necessarily the one
    # manage.py would pick on its own. systemd sets DATABASE_PATH from
    # /opt/pkanban/.env (EnvironmentFile) falling back to the Environment= line
    # in pkanban.service; this shell has neither, so without the lookup below
    # manage.py defaults to ./pkanban.db and would happily migrate the wrong
    # file -- leaving the live database untouched and unmigrated.
    #
    # Read rather than sourced: .env is systemd-format, where values are
    # literal to end of line, so `RESEND_FROM=Kanban <noreply@...>` is valid
    # there but would be a redirect to bash.
    DB_PATH=""
    if [ -f "$DEPLOY_DIR/.env" ]; then
        DB_PATH=$(grep -E '^[[:space:]]*DATABASE_PATH=' "$DEPLOY_DIR/.env" \
            | tail -1 | cut -d= -f2- | tr -d '"'"'"'' | xargs)
    fi
    # Matches Environment=DATABASE_PATH in sys/systemd/pkanban.service.
    DB_PATH="${DB_PATH:-$DEPLOY_DIR/pkanban.db}"

    echo "Target database: $DB_PATH"
    DATABASE_PATH="$DB_PATH" $DEPLOY_DIR/venv/bin/python manage.py migrate

    echo "Migrations complete"
}

# Function to install the systemd unit when it has changed
install_unit() {
    echo -e "${YELLOW}⚙️ Checking systemd unit...${NC}"

    REPO_UNIT="$DEPLOY_DIR/sys/systemd/pkanban.service"
    LIVE_UNIT="/etc/systemd/system/pkanban.service"

    if [ ! -f "$REPO_UNIT" ]; then
        echo "No unit file in the repo, skipping"
        return 0
    fi

    # The common case: nothing to do, and no sudo needed to find that out.
    if cmp -s "$REPO_UNIT" "$LIVE_UNIT"; then
        echo "Unit unchanged"
        return 0
    fi

    if [ -f "$LIVE_UNIT" ]; then
        echo "Installed unit differs from the repo:"
        diff "$LIVE_UNIT" "$REPO_UNIT" || true
    else
        echo "No unit installed yet, installing for the first time"
    fi

    # -n so a missing sudoers rule fails immediately instead of blocking on a
    # password prompt that nothing can answer.
    if sudo -n cp "$REPO_UNIT" "$LIVE_UNIT" 2>/dev/null &&
       sudo -n systemctl daemon-reload 2>/dev/null; then
        echo "Unit installed, systemd reloaded"
        return 0
    fi

    # Deliberately fatal. Restarting now would come up on the stale unit and
    # report success, which is the exact failure this step exists to end: an
    # EnvironmentFile line sat in the repo for weeks while the running service
    # knew nothing about it, so /opt/pkanban/.env was never read and signup
    # sent no mail while looking healthy.
    echo -e "${RED}❌ Cannot install the unit -- deploy user lacks sudo rights${NC}"
    echo ""
    echo "Grant them once, as root:"
    echo "  cat > /etc/sudoers.d/pkanban-restart <<'EOF'"
    echo "pkanban ALL=(ALL) NOPASSWD: /bin/systemctl restart pkanban"
    echo "pkanban ALL=(ALL) NOPASSWD: /bin/systemctl daemon-reload"
    echo "pkanban ALL=(ALL) NOPASSWD: /bin/cp $REPO_UNIT $LIVE_UNIT"
    echo "EOF"
    echo "  chmod 440 /etc/sudoers.d/pkanban-restart"
    echo ""
    echo "Or apply this one change by hand and re-run the deploy:"
    echo "  sudo cp $REPO_UNIT $LIVE_UNIT"
    echo "  sudo systemctl daemon-reload"
    echo ""
    echo "Check what is currently permitted with: sudo -n -l"
    exit 1
}

# Function to install the nginx config when it has changed
install_nginx_config() {
    echo -e "${YELLOW}🌐 Checking nginx config...${NC}"

    REPO_CONF="$DEPLOY_DIR/sys/nginx/pkanban.pearachute.com.conf"
    LIVE_CONF="/etc/nginx/sites-available/pkanban.pearachute.com.conf"

    if [ ! -f "$REPO_CONF" ]; then
        echo "No nginx config in the repo, skipping"
        return 0
    fi

    # The common case: nothing to do, and no sudo needed to find that out.
    if cmp -s "$REPO_CONF" "$LIVE_CONF"; then
        echo "Nginx config unchanged"
        return 0
    fi

    if [ -f "$LIVE_CONF" ]; then
        echo "Installed nginx config differs from the repo:"
        diff "$LIVE_CONF" "$REPO_CONF" || true
    else
        echo "No nginx config installed yet, installing for the first time"
    fi

    print_nginx_sudoers_help() {
        echo ""
        echo "Grant them once, as root:"
        echo "  cat > /etc/sudoers.d/pkanban-nginx <<'EOF'"
        echo "pkanban ALL=(ALL) NOPASSWD: /bin/cp $REPO_CONF $LIVE_CONF"
        echo "pkanban ALL=(ALL) NOPASSWD: /usr/sbin/nginx -t"
        echo "pkanban ALL=(ALL) NOPASSWD: /bin/systemctl reload nginx"
        echo "EOF"
        echo "  chmod 440 /etc/sudoers.d/pkanban-nginx"
        echo ""
        echo "Or apply this one change by hand and re-run the deploy:"
        echo "  sudo cp $REPO_CONF $LIVE_CONF"
        echo "  sudo nginx -t && sudo systemctl reload nginx"
        echo ""
        echo "Check what is currently permitted with: sudo -n -l"
    }

    # -n so a missing sudoers rule fails immediately instead of blocking on a
    # password prompt that nothing can answer.
    #
    # Deliberately fatal, same as install_unit above: this step exists because
    # a config change (like PR #28's rate limiting) could otherwise sit
    # unapplied on the box indefinitely while the deploy reports success.
    if ! sudo -n cp "$REPO_CONF" "$LIVE_CONF" 2>/dev/null; then
        echo -e "${RED}❌ Cannot install the nginx config -- deploy user lacks sudo rights${NC}"
        print_nginx_sudoers_help
        exit 1
    fi

    # Unlike the systemd unit, a bad config must never reach `systemctl reload`
    # -- that would take the site down. Test what's now on disk first; if sudo
    # itself blocked the test (no NOPASSWD rule yet), nginx never runs at all
    # and its output has no "nginx:" lines, which is how we tell that apart
    # from a real config error below.
    # The `if` guards the assignment against `set -e`: a bare
    # `X=$(cmd)` with a failing cmd would abort the script right here,
    # before NGINX_TEST_STATUS is ever read below.
    if NGINX_TEST_OUTPUT=$(sudo -n nginx -t 2>&1); then
        NGINX_TEST_STATUS=0
    else
        NGINX_TEST_STATUS=$?
    fi

    if [ $NGINX_TEST_STATUS -ne 0 ] && ! echo "$NGINX_TEST_OUTPUT" | grep -q "^nginx:"; then
        echo -e "${RED}❌ Cannot test the nginx config -- deploy user lacks sudo rights${NC}"
        echo "$NGINX_TEST_OUTPUT"
        print_nginx_sudoers_help
        exit 1
    fi

    if [ $NGINX_TEST_STATUS -ne 0 ]; then
        echo -e "${RED}❌ New nginx config failed validation -- NOT reloading:${NC}"
        echo "$NGINX_TEST_OUTPUT"
        echo "The previous config is still live in the running nginx process."
        echo "Fix $REPO_CONF and re-run the deploy."
        exit 1
    fi

    if ! sudo -n systemctl reload nginx 2>/dev/null; then
        echo -e "${RED}❌ Cannot reload nginx -- deploy user lacks sudo rights${NC}"
        print_nginx_sudoers_help
        exit 1
    fi

    echo "Nginx config installed and reloaded"
}

# Function to restart service
restart_service() {
    echo -e "${YELLOW}🔄 Restarting pkanban service...${NC}"
    sudo systemctl restart pkanban
    sleep 2

    # Check if service is running
    if systemctl is-active --quiet pkanban; then
        echo -e "${GREEN}✅ Service restarted successfully${NC}"
    else
        echo -e "${RED}❌ Service failed to start${NC}"
        systemctl status pkanban --no-pager
        exit 1
    fi
}

# Main deployment flow
main() {
    check_user

    cd $DEPLOY_DIR

    echo -e "${GREEN}Step 1: Pull updates${NC}"
    git_pull

    echo -e "${GREEN}Step 2: Update dependencies${NC}"
    update_dependencies

    echo -e "${GREEN}Step 3: Build frontend${NC}"
    build_frontend

    echo -e "${GREEN}Step 4: Run migrations${NC}"
    run_migrations

    # Before the restart, so the restart is what picks up a changed unit.
    echo -e "${GREEN}Step 5: Install systemd unit${NC}"
    install_unit

    # Also before the restart -- reloading nginx is independent of the pkanban
    # service restart below, but keeping config changes together with the
    # restart step means a deploy either applies everything or fails loudly.
    echo -e "${GREEN}Step 6: Install nginx config${NC}"
    install_nginx_config

    echo -e "${GREEN}Step 7: Restart service${NC}"
    restart_service

    echo ""
    echo -e "${GREEN}✅ Deployment complete!${NC}"
    echo ""
    echo "Useful commands:"
    echo "  Check service status: systemctl status pkanban"
    echo "  View logs: journalctl -u pkanban -f"
}

# Run deployment
main "$@"
