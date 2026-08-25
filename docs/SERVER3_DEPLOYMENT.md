# Server3 Deployment

Target: Debian 13 test server for the InnAware PMS Emulator.

## 1. Generate a dedicated GitHub deploy key

Run as the normal deployment user (`installer` in the InnAware lab):

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -a 100 -f ~/.ssh/innaware_pms_emulator_github -C "server3 innaware-pms-emulator deploy key"
chmod 600 ~/.ssh/innaware_pms_emulator_github
chmod 644 ~/.ssh/innaware_pms_emulator_github.pub
```

For unattended Git pulls, leave the key passphrase empty. If interactive-only access is preferred, use a passphrase and ssh-agent.

Display the public key:

```bash
cat ~/.ssh/innaware_pms_emulator_github.pub
```

Add that public key in GitHub under the repository's **Settings -> Deploy keys -> Add deploy key**. Read-only access is sufficient for server3 deployment. Do not enable write access unless server3 genuinely needs to push commits.

## 2. Pin GitHub host identity

```bash
ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts
chmod 600 ~/.ssh/known_hosts
```

For higher assurance, compare the returned GitHub host-key fingerprint to GitHub's currently published SSH host-key fingerprints before trusting it.

## 3. Configure SSH to use only the dedicated key

```bash
cat >> ~/.ssh/config <<'EOF'
Host github-innaware-pms-emulator
    HostName github.com
    User git
    IdentityFile ~/.ssh/innaware_pms_emulator_github
    IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

Test authentication:

```bash
ssh -T git@github-innaware-pms-emulator
```

GitHub should report successful authentication while noting that shell access is not provided.

## 4. Clone the repository

```bash
sudo mkdir -p /opt/innaware
sudo chown installer:installer /opt/innaware
cd /opt/innaware
git clone git@github-innaware-pms-emulator:MusicCityTelecom/innaware-pms-emulator.git
cd innaware-pms-emulator
```

Existing clone:

```bash
cd /opt/innaware/innaware-pms-emulator
git remote set-url origin git@github-innaware-pms-emulator:MusicCityTelecom/innaware-pms-emulator.git
git fetch --all --prune
git status
```

## 5. Install runtime dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git
cd /opt/innaware/innaware-pms-emulator
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
pip install -e . pytest
pytest -q
```

If server3 will use physical serial ports, add the service user to the serial-device group:

```bash
sudo usermod -aG dialout installer
```

Log out and back in before testing serial access.

## 6. Initial manual launch

```bash
cd /opt/innaware/innaware-pms-emulator
. .venv/bin/activate
uvicorn innaware_pms_emulator.main:app --app-dir src --host 0.0.0.0 --port 8080
```

From another machine:

```bash
curl http://SERVER3_IP:8080/api/v1/health
curl http://SERVER3_IP:8080/api/v1/protocols
```

The permanent systemd unit and production-style configuration storage will be added after the interface manager and operator console stabilize.
