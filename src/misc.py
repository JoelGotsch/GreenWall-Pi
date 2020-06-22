import datetime
import json
import logging, sys
try:
    from src.blynklib import Blynk
except ModuleNotFoundError:
    from blynklib import Blynk


def prev_date_wday(wday):
    """ returns datetime object of last date at 00:00 which has the weekday given by wday.
    E.g. if today is Friday, 20th of June and wday = 0, then it will return Monday, 15th of June 00:00"""
    today = datetime.datetime.today().date()
    tw = today.weekday()
    return(datetime.datetime.combine(today + datetime.timedelta(days=-((tw-wday) % 7)), datetime.datetime.min.time()))


def calc_last_runtime(wdays, start_time):
    hours, minutes = start_time.split(":")
    possible_times = [prev_date_wday(
        wday)+datetime.timedelta(hours=float(hours), minutes=float(minutes)) for wday in wdays]
    possible_times = [
        possible_time for possible_time in possible_times if possible_time < datetime.datetime.today()]
    return(max(possible_times))


def get_duration(action):
    if "duration" in action.keys():
        return(action["duration"])
    else:
        return(0)


def next_date_wday(wday):
    """ returns datetime object of next date at 00:00 which has the weekday given by wday.
    E.g. if today is Friday, 20th of June and wday = 0, then it will return Monday, 22nd of June 00:00"""
    today = datetime.datetime.today().date()
    tw = today.weekday()
    return(datetime.datetime.combine(today + datetime.timedelta(days=(wday-tw) % 7), datetime.datetime.min.time()))


def initializeBlynk():

    with open("settings/blynk_settings.json") as file_settings:
        Blynk_settings = dict(json.load(file_settings))
    Auth_token = Blynk_settings["AUTH_TOKEN"]
    blynk = Blynk(token=Auth_token)
    blynk.run()#run it once to connect
    return(blynk)


def initializeLogger(filename='logs/app.log', log_level=logging.DEBUG, logger_name="app"):
    logging.basicConfig(filename=filename, level=log_level,
                        format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
    logger = logging.getLogger(logger_name)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)
    return(logger)
