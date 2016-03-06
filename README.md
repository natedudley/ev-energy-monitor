# ev-energy-monitor
System to monitor electricity usage for electric vehicle

# Raspberry Pi Setup
## Building a Raspberry Pi Image
* [Instructions](https://www.raspberrypi.org/documentation/installation/installing-images/windows.md)
* I use 2015-02-16-raspbian-wheezy.img 
* [Setting up Google Drive](http://www.open-electronics.org/how-send-data-from-arduino-to-google-docs-spreadsheet/)
```
sudo apt-get update
sudo apt-get dist-upgrade
```

### Installing aruino support software
```
sudo apt-get update 
sudo apt-get install arduino 
```

### Setting timezone 
```
sudo dpkg-reconfigure tzdata 
```

### Fixing keyboard special shift characters 
```
sudo nano /etc/default/keyboard XKBLAYOUT="us" 
```

### Installing pip 
```
sudo apt-get install python-setuptools 
sudo easy_install pip 
```

### Installing python supporting packages
```
sudo su 
pip install requests 
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

