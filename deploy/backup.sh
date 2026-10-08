#!/usr/bin/env bash
# 每日数据库备份：pg_dump 到宿主机目录，保留最近 KEEP 份。
# 用法（cron，凌晨 2:07）：
#   7 2 * * * /opt/mvp/deploy/backup.sh >> /opt/mvp-backup/backup.log 2>&1
set -euo pipefail

# 脚本所在目录的上级 = 仓库根目录（compose 文件与 .env 所在）。
cd "$(dirname "$0")/.."

# 读取 .env 里的 POSTGRES_USER / POSTGRES_DB（若存在）。
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

BACKUP_DIR="${BACKUP_DIR:-/opt/mvp-backup}"
KEEP="${KEEP:-14}"
COMPOSE_FILE="docker-compose.prod.yml"
DB_USER="${POSTGRES_USER:-mvp}"
DB_NAME="${POSTGRES_DB:-mvp}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%F_%H%M%S)"
OUT="$BACKUP_DIR/mvp_${STAMP}.sql.gz"

docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$OUT"

# 只保留最近 KEEP 份。
ls -1t "$BACKUP_DIR"/mvp_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

echo "备份完成：$OUT"
