#! /home/pi/GreenWall-Pi/venv/bin/python3
import datetime, time
try:
    from src.greenwall import greenwall
    from src.taskmanager import task_manager, task
    from src.misc import initializeBlynk, initializeLogger
    from src.blynklogger import attachBlynkLogger
except ModuleNotFoundError:
    from greenwall import greenwall
    from taskmanager import task_manager, task
    from misc import initializeBlynk, initializeLogger
    from blynklogger import attachBlynkLogger
import logging, sys
import threading
#TODOS:
# - integrate docker
# - create api for changing the watering-plans (in flask?)
# DONE:
# - send info-logs to blynk
# - integrate camera

def run_blynk_loop(blynk):
    def wrapper():
        while True:
            blynk.run()
    return(wrapper)

if __name__ == "__main__":
    logger = initializeLogger(filename='logs/app.log', log_level=logging.DEBUG, logger_name="app")
    gw = greenwall(name="Joels Green Wall :)", platform="Raspberry Pi 4", logger=logger)
    blynk = initializeBlynk()
    #sending logging messages to blynk via vpin set in blynk_settings for logger
    tm = task_manager(green_wall=gw, logger=logger, blynk = blynk)
    logger=attachBlynkLogger(logger, blynk, tm)
    gw.addTm(tm)
    gw.addBlynk(blynk)
    # tm.add_task(task(func=blynk.run, exec_time=datetime.datetime.today(), repeat=0.5, name="Blynk update", logger=logger))
    tm.add_task(task(func=run_blynk_loop(blynk), exec_time=datetime.datetime.today(), name="Blynk update", logger=logger))
    while True:
        tm.run()
        time.sleep(1)
        
#run via 
# cd GreenWall-Pi/
# nohup ./src/app.py &
# sudo nohup /home/pi/GreenWall-Pi/venv/bin/python3 /home/pi/GreenWall-Pi/src/app.py &
