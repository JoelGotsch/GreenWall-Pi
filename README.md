# GreenWall-Pi
Automating my Green wall system via a Raspberry Pi 4, dockerized in Python. It is used to automatically pump the water with a big pump to a reservoir, from where it is distributed with small pumps to 4 different sections. All of which is monitored by a Webcam.
Everything is syncronized with a blynk app so that I can control everything remotely, including seeing a picture of the wall currently.

## How-to:
- Install usbhc on RaspberryPi: https://github.com/mvp/uhubctl#raspberry-pi-4b
- ""sudo crontab -e -u root"": ""@reboot cd /home/pi/GreenWall-Pi && /home/pi/GreenWall-Pi/venv/bin/python3 /home/pi/GreenWall-Pi/app.py > /home/pi/GreenWall-Pi/cronlog.txt""
- ""sudo chmod a+x app.py""

# Settings explanation

## devices.json

Contains all the GPIO devices which are controlled by the GPIOs like light and pumps as well as cameras.

### GPIO devices

Declared in the sub-dictionary of "GPIO". The names of the lists are irrelevant. The have the following parameters:
- "name": a string, identifying the device. Is used in logs mainly and must be unique. All lights should contain the phrase "light"
- "gpio_pin": an integer, refers to which pin on the Raspberry-Pi is used to control the device
- "vpin": an integer, used for the blynk app to output or change the value (usually a button or switch)
- "on_value": an integer, either 0 or 1. 0 means that the device is turned on, if the gpio value is set to 0. This comes in handy with some relays which are by default turned on. NOT YET TESTED.
- "min_pause": an integer indicating the time in seconds which have to go by in between turning on a device.


### Cameras

Note: Sudo rights are needed to reset the USB camera. There is a bug in the library which takes the pictures which freezes the Camera and the only way to reset it is to reset the USB hub for which sudo rights are needed. Thats also why usbhc is installed in the How-to.
- "name": a string, must be unique and should contain "cam"
- "gpio_pin": a string, not yet used.
- "vpin": an integer, indicating which virutal pin from blynk is assigned to the photo gallery.
- "repeat_sec": an integer, indicating how many seconds should pass between taking pictures.
- "res": a string like "1280x720" indicating the resolution. Must be supported by the camera.
- "usb_port": an integer, used to identify the proper usb-port where the camera is attached.