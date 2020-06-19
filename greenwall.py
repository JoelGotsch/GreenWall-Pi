import gpiozero
import json
import logging

class device:
    def __init__(self, name, gpiopin, blynk_vpin, *args, **kwargs):
        self.name = name
        self.gpiopin = gpiopin
        self.vpin = blynk_vpin
        self.gpio_obj = gpiozero.LED(gpiopin)

    def turn_on(self):
        self.gpio_obj.on()
        #send info to blynk (via thread!)

    def turn_off(self):
        self.gpio_obj.off()
        #send info to blynk

    def get_value(self):
        return(self.gpio_obj.value)
    
    #define 
    

class greenwall:
    """ Contains all the appliances on the wall such as the pumps, the light and the camera """
    def __init__(self, gpio_settings, name, platform, *args, **kwargs):
        self.name = name
        self.platform = platform # Raspberry or Onion
        self.devices = []
        # init logger
        # check if all devices are in the right status; according to actions.json
        # should taskmanager be a part of greenwall? Or vice versa? Or in parallel?


    def get_device_name(self, name):
        """returns a device object when you ask for the name"""
        return(self.devices[name])
        
        # for dev in self.devices:
        #     if dev.name == name:
        #         return(dev)
        # raise KeyError

    def get_device_vpin(self, vpin):
        """returns a device object when you ask for its vpin"""
        for dev in self.devices:
            if dev.vpin == vpin:
                return(dev)
        raise KeyError

    def get_value_vpin(self, vpin):
        """returns the value of a device (0 or 1) when you ask for its vpin"""
        dev = self.get_device_vpin(vpin)
        return(dev.get_value())


    