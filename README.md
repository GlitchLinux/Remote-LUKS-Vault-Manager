# **Remote LUKS Vault Manager** 🔒  

*A Python script to securely mount and manage LUKS-encrypted remote drives over SSHFS.*  

![Demo](https://img.shields.io/badge/status-working-brightgreen) ![Python](https://img.shields.io/badge/python-3.6+-blue) ![License](https://img.shields.io/badge/license-MIT-green)  

---

## **📌 Features**  
✅ **Secure Remote Access** – Mount LUKS-encrypted drives over SSH.  
✅ **Automated Mounting** – Unlock, mount, and access files with one command.  
✅ **GUI Integration** – Open mounted files in your preferred file manager (Thunar, Nautilus, etc.).  
✅ **Config Management** – Save multiple remote LUKS configurations.  

---

## **⚠️ Important Note: LUKS Volume Setup**  
**This script does not create the LUKS volume for you.** You must **manually** set it up on the remote server first.  

### **🔧 Prerequisites on Remote Server**  
1. **A pre-existing LUKS-encrypted partition** (e.g., `/dev/sda2`).  
   - If not set up, use:  
     ```bash
     sudo cryptsetup luksFormat /dev/sdX  # Replace sdX with your device
     sudo cryptsetup luksOpen /dev/sdX remote_vault
     sudo mkfs.ext4 /dev/mapper/remote_vault
     sudo mount /dev/mapper/remote_vault /mnt/encrypted
     ```
2. **SSH access** with `sudo` privileges for mounting/unmounting.  

---

## **🛠 Installation (Local Machine)**  

### **Dependencies**  
```bash
# Debian/Ubuntu
sudo apt install sshpass sshfs python3 python3-paramiko openssh-server

# Arch Linux
sudo pacman -S sshpass sshfs python python3-paramiko openssh-server

# Fedora
sudo dnf install sshpass fuse-sshfs python3 python3-paramiko openssh-server
```

🚀 Installation
 ```bash
git clone https://github.com/GlitchLinux/Remote-LUKS-Vault-Manager.git
cd Remote-LUKS-Vault-Manager
chmod +x luks_remote.py
./luks_remote.py
First run creates ~/.LUKS-VAULT/ for configs.

## **🚀 Usage**  
1. **First run:**  
   - The script creates `~/.LUKS-VAULT/` for configs.  
   - Follow prompts to add a new remote LUKS volume.  

2. **Mounting:**  
   - Select a saved config → Enter LUKS passphrase.  
   - Files appear in `~/.LUKS-VAULT/mnt/`.  

3. **Unmounting:**  
   - Press `Enter` in the script → Cleanly unmounts everything.  
   ```

---

## **🔄 Manual Commands (For Debugging)**  
| **Action**               | **Command**                                                                 |
|--------------------------|----------------------------------------------------------------------------|
| **Force Unmount**         | `sudo umount -f ~/.LUKS-VAULT/mnt/`                                        |
| **Check Mount Status**    | `mount | grep LUKS-VAULT` or `ls ~/.LUKS-VAULT/mnt/`                     |
| **Kill Stuck Processes** | `sudo lsof +D ~/.LUKS-VAULT/mnt/` → `sudo kill -9 <PID>`                  |

---

## **❓ FAQ**  

### **Q: Why can’t I see files after mounting?**  
- **Cause:** Permissions or unmount issues.  
- **Fix:** Run `sudo chmod -R 777 /mnt/encrypted` on the **remote server**.  

### **Q: Can I use SSH keys instead of passwords?**  
- **Yes!** Set up SSH keys first (`ssh-copy-id`), then modify the script to remove `sshpass`.  

### **Q: How do I add multiple LUKS volumes?**  
- Just run the script again and create a new config.  

---

## **📜 License**  
MIT © [Your Name]  

---

**🌟 Enjoy secure remote storage!**  
*Contributions welcome!* 🛠️
