#! /home/pi/GreenWall-Pi/venv/bin/python3
import datetime, time
from src.greenwall import greenwall
from src.taskmanager import task_manager
from src.misc import initializeBlynk, initializeLogger
from src.blynklogger import attachBlynkLogger
import logging, sys
import threading
#TODOS:
# - create api for changing the watering-plans (in flask?)
# DONE:
# - send info-logs to blynk
# - integrate camera
import threading

def run_blynk_loop(blynk):
    def wrapper():
        while True:
            blynk.run()
    return(wrapper)

if __name__ == "__main__":
    logger = initializeLogger(filename='logs/app.log', log_level=logging.DEBUG, logger_name="app")
    gw = greenwall(name="Joels Green Wall :)", platform="Raspberry Pi 4")
    blynk = initializeBlynk()
    #sending logging messages to blynk via vpin set in blynk_settings for logger
    tm = task_manager(green_wall=gw, logger=logger, blynk = blynk)
    logger=attachBlynkLogger(logger, blynk, tm)
    threading.Timer(0, function=run_blynk_loop(blynk)).start()
    sleep_time=1
    while True:
        tm.run(cycle_time_s=sleep_time)
        time.sleep(sleep_time)
        
#run via 
# cd GreenWall-Pi/
# sudo nohup /home/pi/GreenWall-Pi/venv/bin/python3 /home/pi/GreenWall-Pi/app.py &
