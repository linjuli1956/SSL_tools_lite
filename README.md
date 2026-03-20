# SSL证书管理工具

远程管理多台云服务器的SSL证书，支持一键部署、自动备份、更换记录。
<img width="1235" height="1254" alt="image" src="https://github.com/user-attachments/assets/204cedc6-d3b9-4b3e-a54c-b3270717b67c" />

## 功能特性

- **多服务器管理** - 支持Linux和Windows服务器
- **多Web服务支持** - Nginx、Apache、IIS
- **一键部署** - SSH上传证书 → 自动备份 → 重启服务
- **证书管理** - 本地证书文件管理、到期时间查看
- **更换记录** - 完整记录每次更换的时间、备份路径、重启结果
- **到期提醒** - 证书30天内到期自动标红预警

## 支持平台

- Windows
- Linux
- macOS

## 环境要求

- Python 3.8 或更高版本

## 项目结构

```
SSL_Auto/
├── app.py              # Flask后端主程序
├── start.bat          # Windows启动脚本
├── start.sh           # Linux/Mac启动脚本
├── install.bat        # Windows安装脚本
├── install.sh         # Linux/Mac安装脚本
├── README.md          # 项目文档
├── requirements.txt   # Python依赖
├── config/            # 配置文件目录
│   ├── servers.json   # 服务器配置
│   ├── history.json  # 更换记录
│   └── config.json   # 全局配置
├── certs/             # 证书文件目录（放置新的.crt、.key、.pem文件）
├── backups/           # 旧证书备份目录
└── templates/
    └── index.html    # 前端页面
```

## 快速开始

### Windows

1. 双击 `install.bat` 安装依赖
2. 双击 `start.bat` 启动服务
3. 浏览器打开 http://localhost:5000

### Linux/Mac

1. 打开终端
2. 运行安装脚本：
   ```bash
   chmod +x install.sh start.sh
   ./install.sh
   ```
3. 启动服务：
   ```bash
   ./start.sh
   ```
4. 浏览器打开 http://localhost:5000

## 配置说明

### 添加服务器

| 字段 | 说明 | 示例 |
|------|------|------|
| 服务器名称 | 便于识别 | 生产服务器 |
| 服务器地址 | IP或域名 | 192.168.1.100 |
| 端口 | SSH端口，默认22 | 22 |
| SSH用户名 | 服务器登录用户名 | root |
| SSH密码 | 服务器登录密码 | ***** |
| 服务器类型 | Linux或Windows | linux |
| Web服务器 | nginx/apache/iis | nginx |
| 证书路径 | 服务器上证书存放目录 | /etc/nginx/ssl |
| 服务路径 | 执行命令的工作目录 | /opt/docker |
| 重启命令 | 支持多行，每行一条命令 | docker-compose down |

### 证书文件

将申请好的证书文件放到 `certs/` 目录，或通过网页上传：
- `.pem` - 证书文件
- `.crt` - 证书文件
- `.key` - 私钥文件

### 部署模式

| 模式 | 说明 |
|------|------|
| 上传证书 + 执行命令 | 上传证书并执行选中的命令 |
| 仅上传证书 | 只上传证书，不执行命令 |
| 仅执行命令 | 只执行命令，不上传证书 |

## 配置文件说明

### config.json - 全局配置

```json
{
  "default_cert_folder": "certs",
  "backup_folder": "backups",
  "web_server_cmds": {
    "nginx": "systemctl reload nginx",
    "apache": "systemctl reload httpd",
    "iis": "iisreset"
  }
}
```

### servers.json - 服务器配置

```json
{
  "servers": [
    {
      "id": "uuid",
      "name": "生产服务器",
      "host": "192.168.1.100",
      "port": 22,
      "username": "root",
      "password": "xxx",
      "type": "linux",
      "web_server": "nginx",
      "cert_path": "/etc/nginx/ssl",
      "work_dir": "/opt/docker",
      "restart_cmd": "docker-compose down\ndocker-compose up -d"
    }
  ]
}
```

### history.json - 更换记录

```json
{
  "records": [
    {
      "server_id": "uuid",
      "server_name": "生产服务器",
      "cert_mapping": {"server.crt": "server.crt"},
      "new_expire": "2026-03-20",
      "operated_at": "2025-03-20 10:30:00",
      "backup_path": "./backups/xxx",
      "commands": ["docker-compose down", "docker-compose up -d"],
      "work_dir": "/opt/docker"
    }
  ]
}
```

## 常见问题

### SSH连接失败

- 检查服务器SSH端口是否开放
- 确认用户名密码正确
- 防火墙是否允许22端口

### 证书解析失败

- 确认证书格式为PEM（.crt/.key/.pem）
- 证书文件编码是否为UTF-8

### 服务重启失败

- 检查重启命令是否正确
- 确认是否有执行权限
- 检查服务路径是否正确

## 技术栈

- 后端：Python + Flask
- SSH：paramiko
- 证书解析：cryptography
- 前端：原生JavaScript + HTML/CSS

## 许可证

MIT License
