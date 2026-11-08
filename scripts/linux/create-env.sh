#!/usr/bin/env bash
# Create .env for Docker Compose with a random Django secret key and database password.
#
#   scripts/linux/create-env.sh --domain example.com   # production behind an HTTPS reverse proxy
#   scripts/linux/create-env.sh --local                # trial over plain HTTP on 127.0.0.1
#
# The file is created with mode 600 and is never overwritten; delete it first to start over.
set -euo pipefail

cd "$(dirname "$0")/../.."
target=".env"
mode=""
domain=""
while [ $# -gt 0 ]; do
    case "$1" in
        --domain) mode="production"; domain="${2:-}"; shift 2 ;;
        --local) mode="local"; shift ;;
        *) echo "usage: $0 --domain <host> | --local" >&2; exit 2 ;;
    esac
done
if [ -z "$mode" ] || { [ "$mode" = "production" ] && [ -z "$domain" ]; }; then
    echo "usage: $0 --domain <host> | --local" >&2
    exit 2
fi
if [[ -n "$domain" && ! "$domain" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "The domain may contain only letters, digits, dots and hyphens." >&2
    exit 2
fi
if [ -e "$target" ]; then
    echo "$target already exists; it was not changed." >&2
    exit 1
fi

random() { python3 -c "import secrets; print(secrets.token_urlsafe($1))"; }

if [ "$mode" = "production" ]; then
    environment="production"; hosts="$domain"; origins="https://$domain"; proxy="true"
else
    environment="development"; hosts="127.0.0.1,localhost"; origins=""; proxy="false"
fi

umask 077
sed \
    -e "s|^SYSTEMA_ENV=.*|SYSTEMA_ENV=$environment|" \
    -e "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$(random 50)|" \
    -e "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$hosts|" \
    -e "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=$origins|" \
    -e "s|^DJANGO_BEHIND_HTTPS_PROXY=.*|DJANGO_BEHIND_HTTPS_PROXY=$proxy|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(random 24)|" \
    deploy/env.example > "$target"
chmod 600 "$target"
echo "Created $target ($environment). Review it, then run: docker compose up -d --build"
