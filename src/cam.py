
# import picamera
import json
# import time
import datetime
from subprocess import call
import weakref
# import requests
import cloudinary
from cloudinary.uploader import upload
try:
    from src.taskmanager import task
except ModuleNotFoundError:
    from taskmanager import task

#cloudinary:
#cloud name: druswp5o9
# api key:188849741371281
# api secret: wDVCYTLBEs7xNAqNZtfsEkK9NRo
# environment variable:  cloudinary://188849741371281:wDVCYTLBEs7xNAqNZtfsEkK9NRo@druswp5o9

class camera:
    """We will also need a little https server for the blynk app to load the pictures.."""

    def __init__(self, blynk_vpin, repeat_sec, name, res="1280x720", usb_port=0, logger=None, *args, **kwargs):
        self.vpin = blynk_vpin
        self.repeat_sec = repeat_sec
        self.res = res
        self.usb_port = usb_port
        self.camera = 1  # TODO
        self.service = None
        self.name = name
        self.blynk=None
        self.logger=logger
        cld = cloudinary.config(
            cloud_name = 'druswp5o9',  
            api_key = '188849741371281',  
            api_secret = 'wDVCYTLBEs7xNAqNZtfsEkK9NRo'  
        )

        self.cloudinary = cld

    def take_picture(self, filename=""):
        # save as png
        if filename=="":
            fn = "./pics/"+datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S")+".png"
        else:
            fn = filename
        call(["fswebcam", "-d", "/dev/video"+str(self.usb_port),
              "-r", self.res, "--no-banner", fn])
        #call(["fswebcam", "-d", "/dev/video"+str(0), "-r", "1280x720", "--no-banner", fn])
        image_url=self._upload_picture(fn)
        self.logger.info("Took picture and uploaded. "+str(image_url))
        self.updateLastNURLs(n=5)

        return(fn)

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
    
    def _getLastUrlsN(self, n=5):
        #get the last n pictures by looking up in uploaded_images.json
        with open("settings/uploaded_images.json") as file_settings:
            uploaded_images = dict(json.load(file_settings))
        #use the filenames - keys
        ks = list(uploaded_images.keys())
        ks.sort(reverse=True)
        urls=[uploaded_images[k]["url"] for k in ks]

        return(urls[:n])

    def updateLastNURLs(self, n=5):
        urls=self._getLastUrlsN(n=n)
        self.blynk().set_property(self.vpin, "urls", *urls)
        self.blynk().virtual_write(self.vpin, 1)# shows the newest picture
    
    def addTm(self, tm):
        self.logger.debug("Added Taskmanager to camera object.")
        self.tm = weakref.ref(tm)
        

    def addBlynk(self, blynk):
        self.blynk=weakref.ref(blynk)
        self.updateLastNURLs(n=5)
        self.tm().add_task(task(func=self.take_picture, exec_time=datetime.datetime.today(), repeat=self.repeat_sec, name="Taking picture with " + self.name, logger=self.logger))


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