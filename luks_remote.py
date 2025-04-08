#!/usr/bin/env python3
import os
import sys
import configparser
from pathlib import Path
import subprocess
import shutil
import getpass
import socket
from typing import Optional, Dict, List

# Configuration handling - updated paths
CONFIG_DIR = Path.home() / ".LUKS-VAULT"
CONFIG_FILE = CONFIG_DIR / "config"
MOUNT_DIR = CONFIG_DIR / "mnt"

class RemoteLUKSVault:
    def __init__(self):
        self.ssh_config: Optional[Dict] = None
        self.luks_config: Optional[Dict] = None
        self.connected: bool = False
        self.mounted: bool = False
        # Setup directories
        CONFIG_DIR.mkdir(exist_ok=True, parents=True)
        MOUNT_DIR.mkdir(exist_ok=True, parents=True)

    def check_dependencies(self):
        """Check if required programs are installed"""
        missing = []
        for cmd in ['sshpass', 'sshfs', 'fusermount', 'umount']:
            if not shutil.which(cmd):
                missing.append(cmd)
        if missing:
            print("Error: Missing required dependencies:")
            for cmd in missing:
                print(f" - {cmd}")
            if 'sshfs' in missing:
                print("To install on Debian/Ubuntu: sudo apt install sshfs sshpass")
                print("To install on Arch: sudo pacman -S sshfs sshpass")
                print("To install on Fedora: sudo dnf install fuse-sshfs sshpass")
            sys.exit(1)

    def load_configs(self) -> List[Dict]:
        """Load all saved configurations"""
        configs = []
        if CONFIG_FILE.exists():
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE)
            for section in config.sections():
                cfg = dict(config[section])
                cfg['name'] = section
                configs.append(cfg)
        return configs

    def save_config(self, name: str, config: Dict):
        """Save a new configuration"""
        parser = configparser.ConfigParser()
        if CONFIG_FILE.exists():
            parser.read(CONFIG_FILE)
        parser[name] = config
        with open(CONFIG_FILE, 'w') as f:
            parser.write(f)

    def select_config(self) -> Optional[Dict]:
        """Prompt user to select a saved configuration"""
        configs = self.load_configs()
        if not configs:
            return None
        print("\nSaved configurations:")
        for i, cfg in enumerate(configs, 1):
            print(f"{i}. {cfg['name']} ({cfg.get('hostname', '')}:{cfg.get('port', '22')}")
        print("\n0. Create new configuration")
        try:
            choice = int(input("\nSelect configuration (number): "))
            if 1 <= choice <= len(configs):
                return configs[choice-1]
            return None
        except ValueError:
            return None

    def get_ssh_credentials(self) -> Dict:
        """Prompt for SSH credentials"""
        print("\nEnter SSH connection details:")
        while True:
            hostname = input("Hostname/IP: ").strip()
            if hostname:
                break
            print("Hostname cannot be empty")
                
        port = input("Port [22]: ").strip() or "22"
        username = input("Username: ").strip()
        
        while True:
            password = getpass.getpass("Password: ")
            if password:
                break
            print("Password cannot be empty")
                
        return {
            'hostname': hostname,
            'port': port,
            'username': username,
            'password': password
        }

    def get_luks_details(self) -> Dict:
        """Prompt for LUKS details"""
        print("\nEnter LUKS volume details:")
        while True:
            device = input("Device (e.g. /dev/sdb1): ").strip()
            if device:
                break
            print("Device cannot be empty")
                
        mapper = input("Mapper name [encrypted_vault]: ").strip() or "encrypted_vault"
        mount_point = input("Mount point [/mnt/encrypted]: ").strip() or "/mnt/encrypted"
        
        return {
            'device': device,
            'mapper': mapper,
            'mount_point': mount_point
        }

    def check_port_open(self, host: str, port: int) -> bool:
        """Check if remote port is reachable"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                result = s.connect_ex((host, port))
                return result == 0
        except Exception as e:
            print(f"Network error: {str(e)}")
            return False

    def connect_ssh(self, config: Dict) -> bool:
        """Establish SSH connection with public IP support"""
        try:
            # Check port availability first
            if not self.check_port_open(config['hostname'], int(config['port'])):
                print(f"Error: Port {config['port']} not reachable on {config['hostname']}")
                print("Check firewall/port forwarding settings")
                return False

            # Test SSH connection with verbose output
            test_cmd = [
                'sshpass', '-p', config['password'],
                'ssh', '-p', config['port'],
                '-v',  # Verbose mode for debugging
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'ConnectTimeout=15',
                f"{config['username']}@{config['hostname']}",
                'echo "CONNECTION_TEST_SUCCESS"'
            ]
            result = subprocess.run(test_cmd, capture_output=True, text=True)
            
            if "CONNECTION_TEST_SUCCESS" not in result.stdout:
                print(f"SSH connection failed: {result.stderr}")
                print("Potential issues:")
                print("- Incorrect credentials")
                print("- SSH server configuration")
                print("- Network restrictions")
                return False

            # Verify cryptsetup availability
            cryptsetup_cmd = [
                'sshpass', '-p', config['password'],
                'ssh', '-p', config['port'],
                f"{config['username']}@{config['hostname']}",
                'command -v cryptsetup || which cryptsetup || sudo which cryptsetup'
            ]
            result = subprocess.run(cryptsetup_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print("Error: cryptsetup not found on remote server")
                print("Install with: sudo apt install cryptsetup")
                return False

            self.ssh_config = config
            self.connected = True
            return True
        except Exception as e:
            print(f"SSH connection error: {str(e)}")
            return False

    def mount_luks(self, config: Dict) -> bool:
        """Mount the LUKS volume with public IP support"""
        if not self.connected:
            print("Not connected to SSH server")
            return False
            
        passphrase = getpass.getpass("Enter LUKS passphrase: ")
        try:
            print("\n[1/3] Unlocking LUKS container...")
            ssh_cmd = f"echo {passphrase} | sudo -S cryptsetup luksOpen {config['device']} {config['mapper']}"
            cmd = [
                'sshpass', '-p', self.ssh_config['password'],
                'ssh', '-p', self.ssh_config['port'],
                '-t',  # Force pseudo-terminal allocation
                '-o', 'ConnectTimeout=20',
                f"{self.ssh_config['username']}@{self.ssh_config['hostname']}",
                ssh_cmd
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Failed to unlock LUKS: {result.stderr}")
                if "No key available" in result.stderr:
                    print("Error: Wrong passphrase or not a LUKS device")
                return False

            print("[2/3] Mounting LUKS volume on remote...")
            ssh_cmd = (
                f"echo {passphrase} | sudo -S mkdir -p {config['mount_point']} && "
                f"sudo mount /dev/mapper/{config['mapper']} {config['mount_point']} && "
                f"sudo chmod -R 777 {config['mount_point']}"
            )
            cmd = [
                'sshpass', '-p', self.ssh_config['password'],
                'ssh', '-p', self.ssh_config['port'],
                '-t',
                '-o', 'ConnectTimeout=20',
                f"{self.ssh_config['username']}@{self.ssh_config['hostname']}",
                ssh_cmd
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Failed to mount: {result.stderr}")
                self.remote_luks_close(config['mapper'])
                return False

            print("[3/3] Mounting via SSHFS locally...")
            MOUNT_DIR.mkdir(exist_ok=True)
            cmd = [
                'sshfs',
                '-p', self.ssh_config['port'],
                '-o', 'reconnect',
                '-o', 'ServerAliveInterval=20',
                '-o', 'ServerAliveCountMax=5',
                '-o', 'ConnectTimeout=20',
                '-o', 'password_stdin',
                '-o', f"uid={os.getuid()}",
                '-o', f"gid={os.getgid()}",
                '-o', 'allow_other',
                f"{self.ssh_config['username']}@{self.ssh_config['hostname']}:{config['mount_point']}",
                str(MOUNT_DIR)
            ]
            
            result = subprocess.run(
                cmd, 
                input=self.ssh_config['password'],
                text=True,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"SSHFS mount failed: {result.stderr}")
                self.remote_unmount(config['mount_point'])
                self.remote_luks_close(config['mapper'])
                return False
                
            self.luks_config = config
            self.mounted = True
            print("\nSuccessfully mounted!")
            print(f"Access files at: {MOUNT_DIR}")
            
            # Automatically open file manager upon successful mount
            self.open_file_manager()
            return True
            
        except subprocess.TimeoutExpired:
            print("Operation timed out - check network connection")
            return False
        except Exception as e:
            print(f"Mount error: {str(e)}")
            return False

    def open_file_manager(self):
        """Automatically open preferred file manager after successful mount"""
        if not os.environ.get('DISPLAY'):
            print("No GUI environment detected - skipping file manager launch")
            return

        # Preferred file managers in order of preference
        file_managers = [
	    ('thunar', 'Thunar (XFCE)'),	
            ('dolphin', 'Dolphin (KDE)'),
            ('nautilus', 'Nautilus (GNOME)'),
            ('pcmanfm', 'PCManFM (LXDE)'),
            ('nemo', 'Nemo (Cinnamon)')
        ]

        for cmd, name in file_managers:
            if shutil.which(cmd):
                try:
                    subprocess.Popen(
                        [cmd, str(MOUNT_DIR)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    print(f"Automatically opened {name} file manager")
                    return
                except Exception as e:
                    print(f"Failed to open {name}: {str(e)}")
                    continue

        print("No supported file manager found - mounted at:", MOUNT_DIR)

    def remote_unmount(self, mount_point: str) -> bool:
        """Unmount remote filesystem"""
        try:
            cmd = [
                'sshpass', '-p', self.ssh_config['password'],
                'ssh', '-p', self.ssh_config['port'],
                f"{self.ssh_config['username']}@{self.ssh_config['hostname']}",
                f"sudo umount {mount_point}"
            ]
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    def remote_luks_close(self, mapper: str) -> bool:
        """Close LUKS container remotely"""
        try:
            cmd = [
                'sshpass', '-p', self.ssh_config['password'],
                'ssh', '-p', self.ssh_config['port'],
                f"{self.ssh_config['username']}@{self.ssh_config['hostname']}",
                f"sudo cryptsetup luksClose {mapper}"
            ]
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        except Exception:
            return False

    def unmount(self):
        """Unmount and lock the LUKS volume"""
        if not self.mounted:
            return
            
        success = True
        print("\n[1/3] Unmounting SSHFS...")
        unmounted = False
        
        # Try multiple unmount methods
        for umount_cmd in [['fusermount', '-u', str(MOUNT_DIR)],
                          ['umount', '-l', str(MOUNT_DIR)],
                          ['umount', str(MOUNT_DIR)],
                          ['sudo', 'umount', str(MOUNT_DIR)]]:
            result = subprocess.run(umount_cmd, capture_output=True)
            if result.returncode == 0:
                unmounted = True
                break
                
        if not unmounted:
            print(f"Warning: Could not unmount {MOUNT_DIR}")
            print("Try manually: sudo umount -f " + str(MOUNT_DIR))
            success = False

        print("[2/3] Unmounting remote volume...")
        if not self.remote_unmount(self.luks_config['mount_point']):
            success = False
            
        print("[3/3] Locking LUKS container...")
        if not self.remote_luks_close(self.luks_config['mapper']):
            success = False
            
        self.mounted = False
        if success:
            print("Volume successfully unmounted and locked")
        return success

    def disconnect(self):
        """Disconnect from SSH"""
        if self.mounted:
            self.unmount()
        self.connected = False
        print("Disconnected")

    def run(self):
        """Main application loop"""
        print("\n=== Remote LUKS Vault Manager ===")
        self.check_dependencies()
        
        config = self.select_config()
        if config:
            print(f"\nUsing configuration: {config['name']}")
            if input("Use this configuration? [Y/n]: ").lower() == 'n':
                config = None
                
        if not config:
            print("\nCreate new configuration:")
            name = input("Configuration name: ").strip()
            ssh_config = self.get_ssh_credentials()
            luks_config = self.get_luks_details()
            config = {
                'name': name,
                **ssh_config,
                **luks_config
            }
            self.save_config(name, config)

        print("\nConnecting to remote server...")
        if not self.connect_ssh(config):
            print("Connection failed")
            sys.exit(1)
            
        print("Mounting LUKS volume...")
        if not self.mount_luks(config):
            self.disconnect()
            sys.exit(1)
        
        try:
            input("\nPress Enter to unmount and disconnect...")
        except KeyboardInterrupt:
            print("\nInterrupt received, unmounting...")
            
        self.disconnect()
        print("\nOperation completed")

if __name__ == "__main__":
    vault = RemoteLUKSVault()
    vault.run()
