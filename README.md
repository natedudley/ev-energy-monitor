# ev-energy-monitor
System to monitor electricity usage for electric vehicle


#Raspberry Pi Setup

##auto starting python file
/home/pi/.config/autostart/tesla.desktop should contain:
```
[Desktop Entry]
Type=Application
Exec=lxterminal -e python /home/pi/git/ev-energy-monitor/python/tesla.py "/home/pi/git/ev-energy-monitor/python/"
```
