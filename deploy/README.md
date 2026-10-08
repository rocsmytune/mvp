# 生产部署（内网 920B 单机）

> 服务器：华为鲲鹏 920B，Ubuntu 20.04，aarch64，`141.61.65.32`，内网无外网。
> 构建机：Mac（arm64，有外网）。两者同架构，镜像直接复用、无需交叉编译。

## 架构与端口

| 组件 | 镜像 | 端口 | 说明 |
|---|---|---|---|
| frontend | `mvp-frontend`（nginx 托管静态 + 反代 `/api`） | 80（可用 `FRONTEND_PORT` 改） | 唯一对外入口 |
| backend | `mvp-backend`（FastAPI） | 不对外，仅容器内 8000 | 启动自动 `alembic upgrade head` |
| db | `postgres:16` | 不对外 | 数据卷 `db_data` 持久化 |

访问：`http://<服务器IP>/`；域名 `darwin.inhuawei.com` 解析到该 IP 后可用域名访问。

## 1. 服务器装 Docker（离线 deb）

在有外网的机器下载 5 个 arm64 deb（Ubuntu 20.04 focal）：
`https://download.docker.com/linux/ubuntu/dists/focal/pool/stable/arm64/`

- `containerd.io_1.7.27-1_arm64.deb`
- `docker-ce_28.1.1-1~ubuntu.20.04~focal_arm64.deb`
- `docker-ce-cli_28.1.1-1~ubuntu.20.04~focal_arm64.deb`
- `docker-buildx-plugin_0.23.0-1~ubuntu.20.04~focal_arm64.deb`
- `docker-compose-plugin_2.35.1-1~ubuntu.20.04~focal_arm64.deb`

`scp` 到服务器后安装：

```bash
sudo dpkg -i *.deb          # 若报缺依赖：sudo apt-get -f install
sudo systemctl enable --now docker
docker --version && docker compose version
```

## 2. 构建镜像（Mac 上，arm64 有外网）

```bash
cd <仓库根目录>
cp deploy/env.example .env      # 改掉两个 change-me 占位值！
docker build -t mvp-backend ./backend
docker build -t mvp-frontend -f frontend/Dockerfile.prod ./frontend
docker save mvp-backend mvp-frontend postgres:16 -o mvp-images.tar
```

## 3. 传到服务器并启动

```bash
# Mac
scp mvp-images.tar docker-compose.prod.yml .env root@141.61.65.32:/opt/mvp/

# 服务器
cd /opt/mvp
docker load -i mvp-images.tar
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps        # 三容器 running
curl -s http://localhost/health                     # {"status":"ok","db":"ok"}
```

## 4. 首次建账号（seed）

```bash
docker compose -f docker-compose.prod.yml exec backend python seed.py
```

创建 4 个角色账号 + 字典基础值（**不含演示数据**；演示数据需 `SEED_DEMO=1` 才会建）。
默认密码见 `docs/进度.md`「开发账号」表，上线后请立即在「用户管理」页改掉。

## 5. 每日备份

```bash
chmod +x deploy/backup.sh
sudo mkdir -p /opt/mvp-backup
sudo crontab -e
# 加一行：
7 2 * * * /opt/mvp/deploy/backup.sh >> /opt/mvp-backup/backup.log 2>&1
```

## 6. 升级 / 回滚

功能更新后，重新构建镜像 → save → scp → load → 重启（数据库结构由 alembic 自动升级）：

```bash
# Mac
docker build -t mvp-backend ./backend
docker build -t mvp-frontend -f frontend/Dockerfile.prod ./frontend
docker save mvp-backend mvp-frontend -o mvp-images.tar
scp mvp-images.tar root@141.61.65.32:/opt/mvp/

# 服务器
cd /opt/mvp && docker load -i mvp-images.tar && docker compose -f docker-compose.prod.yml up -d
```

## 7. 常见运维

```bash
docker compose -f docker-compose.prod.yml logs -f backend    # 看后端日志
docker compose -f docker-compose.prod.yml restart backend    # 重启后端
docker compose -f docker-compose.prod.yml down               # 停止（数据卷保留）
```

## 待办 / 已知限制

- HTTPS 未配（当前 HTTP 80）；需要时由工具团队签发 `darwin.inhuawei.com` 内网证书，再在 nginx 层加 443。
- `seed.py` 演示数据已用 `SEED_DEMO` 环境变量门控，生产默认不建。
