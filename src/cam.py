
# import picamera
import json
import os
import time
# import time
import datetime
from subprocess import call
import weakref
# import requests
import cloudinary
from cloudinary.uploader import upload
# try:
#     from src.taskmanager import task
# except ModuleNotFoundError:
#     from taskmanager import task

class CameraException(Exception):
    def __init__(self, *args, **kwargs):
        self.message="Could not take picture. All tries to reset the camera failed."

#cloudinary:
#cloud name: druswp5o9
# api key:188849741371281
# api secret: wDVCYTLBEs7xNAqNZtfsEkK9NRo
# environment variable:  cloudinary://188849741371281:wDVCYTLBEs7xNAqNZtfsEkK9NRo@druswp5o9

class camera:
    """We will also need a little https server for the blynk app to load the pictures.."""

    def __init__(self, blynk_vpin, repeat_sec, name, res="1280x720", usb_port=0, *args, **kwargs):
        self.vpin = blynk_vpin
        # self.repeat_sec = repeat_sec
        self.res = res
        self.usb_port = usb_port
        self.camera = 1  # TODO
        self.service = None
        self.name = name
        # self.logger=logger
        cld = cloudinary.config(
            cloud_name = 'druswp5o9',  
            api_key = '188849741371281',  
            api_secret = 'wDVCYTLBEs7xNAqNZtfsEkK9NRo'  
        )

        self.cloudinary = cld

    def take_picture(self, filename="", tries=5):
        # save as png
        if filename=="":
            fn = "./pics/"+datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S")+".png"
        else:
            fn = filename
        call(["fswebcam", "-d", "/dev/video"+str(self.usb_port),
              "-r", self.res, "--no-banner", fn])
        #call(["fswebcam", "-d", "/dev/video"+str(0), "-r", "1280x720", "--no-banner", fn])
        # fswebcam -d /dev/video0 -r 1280x720 --no-banner test.jpg
        if not os.path.exists(fn):
            if tries > 1:
                self.reset_camera()
                self.take_picture(tries=tries-1)
            else:
                raise CameraException
        else:
            image_url=self._upload_picture(fn)
            return(fn, image_url)

    def _upload_picture(self, fn):
        fn_part = fn.split("/")
        fn_part = fn_part[len(fn_part)-1]
        resp = upload(fn) #many options possible. TODO for the future
        image_url = resp["secure_url"]
        try:
            with open("settings/uploaded_images.json") as file_settings:
                uploaded_images = dict(json.load(file_settings))
        except:
            uploaded_images={}
        uploaded_images[fn_part] = {"url": image_url, "cam": self.name}
        with open('settings/uploaded_images.json', 'w') as outfile:
            json.dump(uploaded_images, outfile)
        return(image_url)

    def reset_camera(self):
        #see: https://github.com/mvp/uhubctl#raspberry-pi-4b for installation guideline
        os.system("sudo /home/pi/uhubctl/uhubctl -a cycle -p 1-4 -l 2")
        # command not found!
        time.sleep(5)


#### GOOGLE DRIVE DOESNT WORK ''''''''''''''''

# fn = "./pics/"+datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S")+".png"
# call(["fswebcam", "-d", "/dev/video"+str(0), "-r", "1280x720", "--no-banner", fn])
# fn_part = fn.split("/")
# fn_part = fn_part[len(fn_part)-1]
# resp = upload(fn) #many options possible. TODO for the future
# image_url = resp["secure_url"]
# try:
#     with open("settings/uploaded_images.json") as file_settings:
#         uploaded_images = dict(json.load(file_settings))
# except:
#     uploaded_images={}
# uploaded_images[fn_part] = {"url": image_url, "cam": "camera_1"}
# with open('settings/uploaded_images.json', 'w') as outfile:
#     json.dump(uploaded_images, outfile)

# blynk.set_property(7, "urls", *urls)