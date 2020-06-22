try:
    from src.greenwall import greenwall
    from src.taskmanager import task_manager
    from src.misc import initializeBlynk, initializeLogger
except ModuleNotFoundError:
    from greenwall import greenwall
    from taskmanager import task_manager
    from misc import initializeBlynk, initializeLogger
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
    tm = task_manager(green_wall=gw, logger=logger)
    blynk = initializeBlynk()
    gw.addTm(tm)
    gw.addBlynk(blynk)
    while True:
        tm.run()
        blynk.run() # maybe as a task in tm in its own thread?
        
