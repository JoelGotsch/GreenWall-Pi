try:
    from src.greenwall import greenwall
    from src.taskmanager import task_manager
    from src.misc import initializeBlynk, initializeLogger
    from src.blynklogger import attachBlynkLogger
except ModuleNotFoundError:
    from greenwall import greenwall
    from taskmanager import task_manager
    from misc import initializeBlynk, initializeLogger
    from blynklogger import attachBlynkLogger
import logging, sys
import threading
#TODOS:
# - send info-logs to blynk
# - integrate camera
# - integrate docker
# - create api for changing the watering-plans

if __name__ == "__main__":
    logger = initializeLogger(filename='logs/app.log', log_level=logging.DEBUG, logger_name="app")
    gw = greenwall(name="Joels Green Wall :)", platform="Raspberry Pi 4", logger=logger)
    blynk = initializeBlynk()
    #sending logging messages to blynk via vpin set in blynk_settings for logger
    tm = task_manager(green_wall=gw, logger=logger, blynk = blynk)
    logger=attachBlynkLogger(logger, blynk, tm)
    gw.addTm(tm)
    gw.addBlynk(blynk)
    while True:
        tm.run()
        blynk.run() # maybe as a task in tm in its own thread?
        
