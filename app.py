import os
import json
import uuid
import datetime
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import paramiko

app = Flask(__name__)

BASE_DIR = Path(__file__).parent
CONFIG_DIR = BASE_DIR / "config"
CERTS_DIR = BASE_DIR / "certs"
BACKUPS_DIR = BASE_DIR / "backups"

CONFIG_DIR.mkdir(exist_ok=True)
CERTS_DIR.mkdir(exist_ok=True)
BACKUPS_DIR.mkdir(exist_ok=True)

def load_json(filename):
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filename, data):
    path = CONFIG_DIR / filename
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_config():
    return load_json("config.json")

def load_servers():
    data = load_json("servers.json")
    return data.get("servers", [])

def save_servers(servers):
    save_json("servers.json", {"servers": servers})

def load_history():
    data = load_json("history.json")
    return data.get("records", [])

def save_history(records):
    save_json("history.json", {"records": records})

def parse_cert_expire(cert_path):
    try:
        from datetime import timezone, timedelta
        with open(cert_path, 'rb') as f:
            cert_data = f.read()
            if b'BEGIN CERTIFICATE' not in cert_data:
                return None
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            china_tz = timezone(timedelta(hours=8))
            expire_utc = cert.not_valid_after_utc
            expire_local = expire_utc.astimezone(china_tz)
            return expire_local.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"Parse cert error: {e}")
        return None

def get_remote_cert_expire(host, port, username, password, cert_path):
    import tempfile
    import os
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=username, password=password, timeout=10)
        
        sftp = ssh.open_sftp()
        files = sftp.listdir(cert_path)
        
        cert_files = [f for f in files if f.endswith(('.crt', '.pem')) and not f.endswith('.key')]
        
        if not cert_files:
            sftp.close()
            ssh.close()
            return None
        
        cert_file = cert_files[0]
        remote_full_path = f"{cert_path}/{cert_file}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pem') as tmp:
            local_tmp_path = tmp.name
        
        sftp.get(remote_full_path, local_tmp_path)
        sftp.close()
        ssh.close()
        
        with open(local_tmp_path, 'rb') as f:
            cert_data = f.read()
        
        os.remove(local_tmp_path)
        
        if b'BEGIN CERTIFICATE' in cert_data:
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            from datetime import timezone, timedelta
            china_tz = timezone(timedelta(hours=8))
            expire_utc = cert.not_valid_after_utc
            expire_local = expire_utc.astimezone(china_tz)
            expire_date = expire_local.strftime('%Y-%m-%d')
            print(f"证书文件: {cert_file}, UTC时间: {expire_utc}, 本地时间: {expire_date}")
            return expire_date
        
    except Exception as e:
        print(f"get_remote_cert_expire error: {e}")
        return None
    return None

def ssh_deploy_cert(server, local_crt, local_key, remote_cert_path, cert_mapping=None):
    host = server['host']
    port = server.get('port', 22)
    username = server['username']
    password = server['password']
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(host, port=port, username=username, password=password, timeout=10)
    
    sftp = ssh.open_sftp()
    
    backup_path = BACKUPS_DIR / server['id'] / datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path.mkdir(parents=True, exist_ok=True)
    
    backup_log = []
    
    if cert_mapping:
        for remote_filename, local_filename in cert_mapping.items():
            remote_full_path = f"{remote_cert_path}/{remote_filename}"
            local_file = CERTS_DIR / local_filename
            
            if local_file.exists():
                try:
                    sftp.get(remote_full_path, str(backup_path / remote_filename))
                    backup_log.append(f"已备份: {remote_filename}")
                except Exception as e:
                    backup_log.append(f"备份失败 {remote_filename}: {str(e)}")
                
                try:
                    sftp.put(str(local_file), remote_full_path)
                    backup_log.append(f"已上传: {remote_filename}")
                except Exception as e:
                    backup_log.append(f"上传失败 {remote_filename}: {str(e)}")
            else:
                backup_log.append(f"本地文件不存在: {local_filename}")
    
    sftp.close()
    ssh.close()
    
    return str(backup_path), "\n".join(backup_log) if backup_log else "No files processed"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())

@app.route('/api/servers', methods=['GET'])
def get_servers():
    servers = load_servers()
    for server in servers:
        if server.get('cert_path'):
            expire = get_remote_cert_expire(
                server['host'], 
                server.get('port', 22),
                server['username'], 
                server['password'],
                server['cert_path']
            )
            server['cert_expire'] = expire
    return jsonify(servers)

@app.route('/api/servers', methods=['POST'])
def add_server():
    servers = load_servers()
    data = request.json
    data['id'] = str(uuid.uuid4())
    servers.append(data)
    save_servers(servers)
    return jsonify({"success": True, "server": data})

@app.route('/api/servers/<server_id>', methods=['PUT'])
def update_server(server_id):
    servers = load_servers()
    data = request.json
    for i, s in enumerate(servers):
        if s['id'] == server_id:
            data['id'] = server_id
            servers[i] = data
            break
    save_servers(servers)
    return jsonify({"success": True})

@app.route('/api/servers/<server_id>', methods=['DELETE'])
def delete_server(server_id):
    servers = load_servers()
    servers = [s for s in servers if s['id'] != server_id]
    save_servers(servers)
    return jsonify({"success": True})

@app.route('/api/certs', methods=['GET'])
def get_local_certs():
    files = []
    for f in CERTS_DIR.iterdir():
        if f.suffix in ['.crt', '.key', '.pem']:
            files.append({
                'name': f.name,
                'path': str(f),
                'size': f.stat().st_size,
                'modified': datetime.datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            })
    return jsonify(files)

@app.route('/api/certs/<filename>', methods=['DELETE'])
def delete_cert(filename):
    file_path = CERTS_DIR / filename
    if file_path.exists():
        file_path.unlink()
        return jsonify({"success": True})
    return jsonify({"error": "File not found"}), 404

@app.route('/api/upload', methods=['POST'])
def upload_cert():
    files = request.files.getlist('file')
    if not files:
        return jsonify({"error": "No file provided"}), 400
    
    uploaded = []
    for file in files:
        if file.filename == '':
            continue
        save_path = CERTS_DIR / file.filename
        file.save(save_path)
        uploaded.append(file.filename)
    
    return jsonify({"success": True, "filename": uploaded})

@app.route('/api/deploy', methods=['POST'])
def deploy_cert():
    data = request.json
    server_id = data.get('server_id')
    cert_mapping = data.get('cert_mapping', {})
    remote_path = data.get('remote_path')
    work_dir = data.get('work_dir', '')
    
    servers = load_servers()
    server = next((s for s in servers if s['id'] == server_id), None)
    
    if not server:
        return jsonify({"error": "Server not found"}), 404
    
    for remote_filename, local_filename in cert_mapping.items():
        local_file = CERTS_DIR / local_filename
        if not local_file.exists():
            return jsonify({"error": f"Certificate file not found: {local_filename}"}), 404
    
    try:
        backup_path, upload_result = ssh_deploy_cert(server, None, None, remote_path, cert_mapping)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
    commands = server.get('restart_cmd', '').strip().split('\n') if server.get('restart_cmd') else []
    commands = [c.strip() for c in commands if c.strip()]
    
    new_expire = None
    for local_filename in cert_mapping.values():
        local_file = CERTS_DIR / local_filename
        if local_file.exists():
            exp = parse_cert_expire(local_file)
            if exp:
                new_expire = exp
                break
    
    history = load_history()
    history.insert(0, {
        "id": str(uuid.uuid4()),
        "server_id": server_id,
        "server_name": server['name'],
        "cert_mapping": cert_mapping,
        "new_expire": new_expire,
        "operated_at": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "backup_path": backup_path,
        "restart_result": upload_result,
        "commands": commands,
        "work_dir": work_dir
    })
    save_history(history)
    
    return jsonify({
        "success": True, 
        "backup_path": backup_path,
        "upload_result": upload_result,
        "new_expire": new_expire,
        "commands": commands,
        "work_dir": work_dir
    })

@app.route('/api/exec_command', methods=['POST'])
def exec_command():
    data = request.json
    server_id = data.get('server_id')
    command = data.get('command')
    work_dir = data.get('work_dir', '')
    
    servers = load_servers()
    server = next((s for s in servers if s['id'] == server_id), None)
    
    if not server:
        return jsonify({"error": "Server not found"}), 404
    
    host = server['host']
    port = server.get('port', 22)
    username = server['username']
    password = server['password']
    
    print(f"exec_command: work_dir='{work_dir}', command='{command}'")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=username, password=password, timeout=60)
        
        # 使用 cd 方式
        if work_dir:
            full_cmd = f"cd {work_dir} && {command}"
        else:
            full_cmd = command
        
        print(f"执行命令: {full_cmd}")
        
        stdin, stdout, stderr = ssh.exec_command(full_cmd, timeout=45)
        
        # 等待命令完成
        exit_status = stdout.channel.recv_exit_status()
        
        # 读取输出
        full_output = stdout.read().decode('utf-8', errors='replace') + stderr.read().decode('utf-8', errors='replace')
        
        ssh.close()
        
        return jsonify({
            "success": True,
            "output": full_output,
            "exit_status": exit_status,
            "command": full_cmd
        })
        
        full_output = ''.join(output_lines) + err_output
        
        return jsonify({
            "success": True,
            "output": full_output,
            "exit_status": exit_status,
            "command": command
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/remote_certs', methods=['POST'])
def get_remote_certs():
    data = request.json
    server_id = data.get('server_id')
    remote_path = data.get('remote_path')
    
    servers = load_servers()
    server = next((s for s in servers if s['id'] == server_id), None)
    
    if not server:
        return jsonify({"error": "Server not found"}), 404
    
    host = server['host']
    port = server.get('port', 22)
    username = server['username']
    password = server['password']
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, port=port, username=username, password=password, timeout=10)
        
        sftp = ssh.open_sftp()
        files = sftp.listdir(remote_path)
        sftp.close()
        ssh.close()
        
        cert_files = [f for f in files if f.endswith(('.crt', '.pem', '.key'))]
        
        return jsonify({"success": True, "files": cert_files})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(load_history())

@app.route('/api/history/<record_id>', methods=['DELETE'])
def delete_history(record_id):
    data = request.json or {}
    delete_backup = data.get('delete_backup', False)
    
    history = load_history()
    record_to_delete = None
    new_history = []
    
    for h in history:
        if h['id'] == record_id:
            record_to_delete = h
        else:
            new_history.append(h)
    
    if delete_backup and record_to_delete and record_to_delete.get('backup_path'):
        backup_path = Path(record_to_delete['backup_path'])
        if backup_path.exists():
            import shutil
            try:
                shutil.rmtree(backup_path)
            except Exception as e:
                print(f"删除备份失败: {e}")
    
    save_history(new_history)
    return jsonify({"success": True})

@app.route('/api/certs/parse', methods=['POST'])
def parse_cert():
    data = request.json
    filename = data.get('filename')
    cert_path = CERTS_DIR / filename
    
    if not cert_path.exists():
        return jsonify({"error": "File not found"}), 404
    
    expire = parse_cert_expire(cert_path)
    return jsonify({"filename": filename, "expire": expire})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
