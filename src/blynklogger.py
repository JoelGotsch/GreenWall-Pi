import weakref, json, logging, datetime
import threading

class BlynkLogStream:
    """needs to implement flush and write methods"""
    def __init__(self, blynk, tm, vpin, *args, **kwargs):
        self.blynk = weakref.ref(blynk)
        self.tm = weakref.ref(tm)
        self.vpin = vpin
        # self.last_message = ""
    
    def write(self, message):
        def write_to_blynk():
            self.blynk().virtual_write(self.vpin, message)
        threading.Timer(0, write_to_blynk).start()
        # self.last_message = message
    
    def flush(self):
        # def write_to_blynk():
        #     self.blynk().virtual_write(self.vpin, "")

        pass



def attachBlynkLogger(logger, blynk, tm):
    with open("settings/blynk_settings.json") as file_settings:
        Blynk_settings = dict(json.load(file_settings))
    logger_settings = Blynk_settings["logger"]
    loglevel = logging.INFO
    if logger_settings["log-level"]=="DEBUG": 
        loglevel = logging.DEBUG
    stream_object = BlynkLogStream(blynk = blynk, tm = tm, vpin = logger_settings["vpin"])
    sh = logging.StreamHandler(stream=stream_object)
    fmt = logging.Formatter('%(asctime)s %(message)s', datefmt="%H:%M:%S")
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    sh.setLevel(loglevel)
    return(logger)