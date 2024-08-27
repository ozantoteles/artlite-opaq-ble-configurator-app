#!/bin/bash

# Define the source directory and tarball name
SOURCE_DIR="/home/mobaxterm/artlite-opaq-ble-configurator-app"
TARBALL_NAME="artlite-opaq-ble-configurator-app.tar.gz"
TEMP_DIR="/tmp/artlite-opaq-ble-configurator-app-tarball"

echo "Creating a tarball from the source directory..."
# Create a tarball excluding .pyc files, __pycache__ directory, .vscode, .git directory, and .gitignore file
mkdir -p $TEMP_DIR
tar --exclude='*.pyc' --exclude='__pycache__' --exclude='.vscode' --exclude='.git' --exclude='.gitignore' -czf $TEMP_DIR/$TARBALL_NAME -C $(dirname $SOURCE_DIR) $(basename $SOURCE_DIR)
echo "Tarball created: $TEMP_DIR/$TARBALL_NAME"

# Create the service file
SERVICE_FILE_PATH="$SOURCE_DIR/artlite-opaq-ble-configurator-app.service"
cat <<EOL > $SERVICE_FILE_PATH
[Unit]
Description=Artlite Opaq BLE Configurator APP
RequiresMountsFor=/run
After=artlite-opaq-app.service

[Service]
Type=simple
Restart=always
RestartSec=3
User=root
Group=root
PermissionsStartOnly=true
StandardError=journal
StandardOutput=journal
WorkingDirectory=/usr/local/artlite-opaq-ble-configurator-app
ExecStart=/usr/bin/python /usr/local/artlite-opaq-ble-configurator-app/src/main.py

[Install]
WantedBy=multi-user.target
EOL

echo "Service file created: $SERVICE_FILE_PATH"

# Function to execute commands over SSH
function ssh_execute {
  local target=$1
  local command=$2
  echo "Executing command on $target: $command"
  ssh root@$target "$command"
}

# Loop through each target
for target in 192.168.1.110; do
  echo "Copying tarball and service file to $target..."
  # Copy the tarball and service file to the remote target
  scp $TEMP_DIR/$TARBALL_NAME root@$target:/usr/local/
  scp $SERVICE_FILE_PATH root@$target:/usr/local/artlite-opaq-ble-configurator-app.service

  echo "Running setup commands on $target..."
  # Commands to execute on the remote target
  ssh_execute $target "
    
    echo 'Extracting tarball...'
    # Extract the tarball and remove it
    tar -xzf /usr/local/$TARBALL_NAME -C /usr/local/ && rm /usr/local/$TARBALL_NAME
    echo 'Tarball extracted and removed.'

    echo 'Setting up systemd service...'
    # Copy the service file to systemd directory and enable/start the service
    cp /usr/local/artlite-opaq-ble-configurator-app.service /lib/systemd/system/
    systemctl daemon-reload
    systemctl enable artlite-opaq-ble-configurator-app.service
    systemctl start artlite-opaq-ble-configurator-app.service
    echo 'Systemd service setup complete.'
  "
done

# Clean up the local tarball
echo 'Cleaning up local tarball...'
rm -r $TEMP_DIR
echo 'Local cleanup complete.'
