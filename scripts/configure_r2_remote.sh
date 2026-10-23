#!/usr/bin/env bash
# Interactive remote-only R2 S3 secret onboarding for the owned OVH VPS.
# Never pass access keys in shell args, chat, code review, or tool logs.
set -euo pipefail
if [[ ! -t 0 || ! -t 1 ]]; then
    printf 'BLOCKED: interactive terminal required (run locally through ssh -tt)\n' >&2
    exit 2
fi
if [[ ! -d "$HOME" || -L "$HOME" ]]; then
    printf 'BLOCKED: unsafe HOME path\n' >&2
    exit 2
fi
config_dir="$HOME/.config/shorts-studio"
dest="$config_dir/r2.env"
if [[ -e "$dest" || -L "$dest" ]]; then
    printf 'BLOCKED: R2 config already exists; do not overwrite it\n' >&2
    exit 2
fi
printf 'Cloudflare R2 S3 credentials — input stays in this SSH terminal.\n'
printf 'Use a bucket-scoped Object Read & Write R2 token, not a general Cloudflare API token.\n'
read -r -p 'Account ID (32 hexadecimal characters): ' account
read -r -p 'Existing R2 bucket name: ' bucket
read -r -s -p 'R2 S3 Access Key ID (hidden): ' access
printf '\n'
read -r -s -p 'R2 S3 Secret Access Key (hidden): ' secret
printf '\n'
if [[ ! "$account" =~ ^[a-fA-F0-9]{32}$ ]] ||
   [[ ! "$bucket" =~ ^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$ ]] ||
   [[ ! "$access" =~ ^.{16,256}$ ]] ||
   [[ ! "$secret" =~ ^.{16,256}$ ]] ||
   [[ "$access" =~ [[:space:]] ]] ||
   [[ "$secret" =~ [[:space:]] ]]; then
    unset account bucket access secret
    printf 'BLOCKED: invalid account, bucket or key format. No secrets saved.\n' >&2
    exit 2
fi
umask 077
if [[ -L "$HOME/.config" || -L "$config_dir" ]]; then
    printf 'BLOCKED: config path must not be a symlink\n' >&2
    exit 2
fi
install -d -m 700 "$config_dir"
temp="$(mktemp "$config_dir/.r2-tmp.XXXXXX")"
trap 'rm -f "$temp"' EXIT
{
    printf 'export R2_ACCOUNT_ID=%q\n' "$account"
    printf 'export R2_BUCKET=%q\n' "$bucket"
    printf 'export R2_ACCESS_KEY_ID=%q\n' "$access"
    printf 'export R2_SECRET_ACCESS_KEY=%q\n' "$secret"
} > "$temp"
chmod 600 "$temp"
# Hardlink fails atomically if another process already created the config.
ln "$temp" "$dest"
rm -f "$temp"
trap - EXIT
unset account bucket access secret
printf 'R2_CREDENTIAL_FILE_READY; permissions restricted to owner.\n'
printf 'This step did NOT connect, transfer files, rent GPU or create a bucket.\n'
