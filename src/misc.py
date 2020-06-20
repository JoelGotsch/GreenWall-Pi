import datetime


def prev_date_wday(wday):
    """ returns datetime object of last date at 00:00 which has the weekday given by wday.
    E.g. if today is Friday, 20th of June and wday = 0, then it will return Monday, 15th of June 00:00"""
    today = datetime.datetime.today().date()
    tw = today.weekday()
    return(datetime.datetime.combine(today + datetime.timedelta(days=-((tw-wday) % 7)), datetime.datetime.min.time()))


def calc_last_runtime(wdays, start_time):
    hours, minutes = plan["start_time"].split(":")
    possible_times = [prev_date_wday(
        wday)+datetime.timedelta(hours=float(hours), minutes=float(minutes)) for wday in wdays]
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
