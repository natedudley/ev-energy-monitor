# ev-energy-monitor
System to monitor electricity usage for electric vehicle

# Raspberry Pi Setup
## Building a Raspberry Pi Image
* [Instructions](https://www.raspberrypi.org/documentation/installation/installing-images/windows.md)
* I use 2020-08-20 version 10 buster
* [Setting up Google Drive](http://www.open-electronics.org/how-send-data-from-arduino-to-google-docs-spreadsheet/)
```
sudo apt update
sudo apt dist-upgrade
```

### Installing aruino support software
```
sudo apt update 
sudo apt install arduino 
```

### Installing python supporting packages
```
sudo su 
pip install requests
pip3 install requests 
```

### Auto starting python file
/home/pi/.config/autostart/tesla.desktop should contain:
```
[Desktop Entry]
Type=Application
Exec=lxterminal -e python /home/pi/git/ev-energy-monitor/python/tesla.py "/home/pi/git/ev-energy-monitor/python/"
```

### starting python ide 
```
sudo idle 
```

