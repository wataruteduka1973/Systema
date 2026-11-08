#!/usr/bin/env bash
# Start Systema for development on Linux (the counterpart of run_systema.bat).
#
# Creates the virtual environment, installs requirements, checks the PostgreSQL connection,
# applies migrations, collects static files and runs the development server on 127.0.0.1:8000
# with the hourly alert scheduler (set SYSTEMA_ALERT_SCHEDULER=false to turn it off).
#
# Database settings already in the environment are kept. Missing ones are read from
# ${XDG_CONFIG_HOME:-~/.config}/systema/database.env (outside the project folder, mode 600),
# and anything still missing is asked for. After a successful connection the script offers to
# save what was asked. Linux has no DPAPI; the file is readable only by you, like ~/.pgpass.
set -euo pipefail

cd "$(dirname "$0")"

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systema"
saved_settings="$config_dir/database.env"
prompted=""

fail() {
    echo >&2
    echo "Systema failed to start: $*" >&2
    exit 1
}

load_saved_settings() {
    [ -f "$saved_settings" ] || return 0
    local line key value
    while IFS= read -r line || [ -n "$line" ]; do
        # Only plain DB_* assignments are read; the file is never executed.
        [[ "$line" =~ ^(DB_(NAME|USER|PASSWORD|HOST|PORT|SSLMODE))=(.*)$ ]] || continue
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[3]}"
        if [ -z "${!key:-}" ]; then
            export "$key=$value"
        fi
    done < "$saved_settings"
}

save_settings() {
    local answer
    read -r -p "Save these PostgreSQL settings to $saved_settings (readable only by you)? [y/N] " answer
    case "$answer" in
        [yY]*) ;;
        *) return 0 ;;
    esac
    (
        umask 077
        mkdir -p "$config_dir"
        {
            echo "# Systema PostgreSQL settings (run_systema.sh). Delete this file to be asked again."
            for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT DB_SSLMODE; do
                printf '%s=%s\n' "$key" "${!key}"
            done
        } > "$saved_settings"
        chmod 600 "$saved_settings"
    ) && echo "Saved." || echo "The settings were not saved. Systema continues without saving them."
}

export DB_ENGINE="${DB_ENGINE:-postgresql}"
if [ "$DB_ENGINE" = "postgresql" ]; then
    load_saved_settings
    export DB_NAME="${DB_NAME:-Yahuoku_analyze_DB}"
    export DB_HOST="${DB_HOST:-localhost}"
    export DB_PORT="${DB_PORT:-5432}"
    export DB_SSLMODE="${DB_SSLMODE:-prefer}"
    if [ -z "${DB_USER:-}" ]; then
        read -r -p "PostgreSQL user: " DB_USER
        export DB_USER
        prompted=1
    fi
    if [ -z "${DB_PASSWORD:-}" ]; then
        read -r -s -p "PostgreSQL password: " DB_PASSWORD
        echo
        export DB_PASSWORD
        prompted=1
    fi
    [ -n "$DB_USER" ] || fail "DB_USER is required for PostgreSQL."
    [ -n "$DB_PASSWORD" ] || fail "DB_PASSWORD is required for PostgreSQL."
fi

base_python=""
for candidate in python3.13 python3; do
    if command -v "$candidate" > /dev/null 2>&1; then
        base_python="$candidate"
        break
    fi
done
[ -n "$base_python" ] || fail "Python was not found. Install Python 3.13 and try again."

# Prevent an old server process from sharing port 8000 with a new process.
if "$base_python" -c "import socket, sys; s = socket.socket(); sys.exit(s.connect_ex(('127.0.0.1', 8000)) != 0)"; then
    fail "Port 8000 is already in use. Systema may already be running; stop it with Ctrl+C first."
fi

# A folder shared with Windows may already hold a Windows .venv; keep that one untouched.
venv=".venv"
if [ -d ".venv/Scripts" ] && [ ! -d ".venv/bin" ]; then
    venv=".venv-linux"
fi
if [ -x "$venv/bin/python" ] && ! "$venv/bin/python" --version > /dev/null 2>&1; then
    echo "Recreating the invalid $venv environment..."
    rm -rf "$venv"
fi
if [ ! -x "$venv/bin/python" ]; then
    echo "Creating virtual environment in $venv..."
    "$base_python" -m venv "$venv" || fail "Could not create $venv (on Debian/Ubuntu install python3-venv)."
fi
python="$venv/bin/python"

"$python" -m pip install --upgrade pip || fail "pip could not be updated."
"$python" -m pip install -r requirements.txt || fail "The required packages could not be installed."

# Check the connection first so a wrong user or password is reported clearly (and never saved).
if ! "$python" manage.py check_database > /dev/null; then
    echo >&2
    echo "Could not connect to the database. Check that PostgreSQL is running and that" >&2
    echo "the user and password are correct." >&2
    if [ -f "$saved_settings" ]; then
        echo "If the saved password changed, delete $saved_settings and start again." >&2
    fi
    fail "database connection"
fi
if [ -n "$prompted" ]; then
    save_settings
fi

if ! "$python" manage.py migrate --check > /dev/null 2>&1; then
    echo "Applying migrations..."
    "$python" manage.py migrate || fail "migrations"
else
    echo "No migrations needed."
fi

# DEBUG is false by default, so collect assets for WhiteNoise before startup.
echo "Collecting static files..."
"$python" manage.py collectstatic --noinput > /dev/null || fail "collectstatic"

# Run saved searches and alert rules hourly from the server process (ADR 0006).
export SYSTEMA_ALERT_SCHEDULER="${SYSTEMA_ALERT_SCHEDULER:-true}"

exec "$python" manage.py runserver 127.0.0.1:8000 --insecure
