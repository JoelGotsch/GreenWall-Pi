import logging
import sys
import threading
import datetime
import json
import time
from collections import OrderedDict
import os
import inspect
import math


from src.misc import get_duration, next_date_wday, add_plan, calc_last_runtime
from src.cam import CameraException

class task_manager:
    """ makes sure that tasks are being executed without blocking the main thread and without permanent checking while still allowing
    for external steering (e.g. via blynk-app)"""

    def __init__(self, green_wall, blynk, logger=None, *args, **kwargs):
        # initialize task_list by parsing plans.json and run it.
        # self.task_list = []
        # In here will be dicts with {exec_time: "2020-08-01 08:00", plan: "turn_on_light"} ordered by exec_time. last entry is {exec_time: "2020-08-01 09:00", plan: "refresh_plan_schedule"}
        self.plan_schedule = []
        self.sent_plans = []
        self.executed_plans = []
        # plans are then parsed when their exec_time is reached. That means tasks are only generated then.
        if logger is None:
            logging.basicConfig(filename='logs/task_manager.log', level=logging.INFO,
                                format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            logger = logging.getLogger('task_manager')
            ch = logging.StreamHandler(sys.stdout)
            logger.addHandler(ch)
        self.logger = logger
        self.green_wall = green_wall
        self.blynk = blynk
        self.schedule_change_date = os.path.getmtime("settings/schedule.json")
        self.refresh_schedule()
        #TODO: doesnt work, maybe per device?
        eh1 = self.blynk.handle_event(event_name="read V*")
        eh1(func=self.get_value_device)
        eh2 = self.blynk.handle_event(event_name="write V*")
        eh2(func=self.set_value_device_vpin)
        #TODO: sync current state of devices
        for dev in self.green_wall.gpio_devices:
            self.blynk.virtual_write(dev.vpin, dev.getValue())
        self.logger.debug("Task Manager initialized")

    def plan_already_executed(self, plan_name, plan_time):
        i = 0
        while i < len(self.executed_plans) and self.executed_plans[i]["exec_time"] >= plan_time:
            if self.executed_plans[i]["plan_name"] == plan_name:
                return(True)
            i += 1
        return(False)

    def calculate_schedule(self, hours=24, min_plans=3):
        # calculate which plans should be run next, checks in executed_plans of plans are already in execution and dismisses them.
        next_plans_list = []
        # to not add the plan which is currently executing
        plan_time_start = datetime.datetime.today() # + datetime.timedelta(seconds=2)
        plan_time_end = plan_time_start + datetime.timedelta(hours=hours)
        with open("settings/plans.json") as file_plans:
            plans_dict = OrderedDict(json.load(file_plans))
        with open("settings/schedule.json") as file_schedule:
            schedule_dict = OrderedDict(json.load(file_schedule))
        self.logger.debug("Calculating schedule...")

        for schedule_name in schedule_dict.keys():
            plan_k = schedule_dict[schedule_name]["plan"]
            if plan_k not in plans_dict.keys():
                self.logger.exception(
                    "Could not find plan '" + str(plan_k) + "' in plans.json")
                continue
            plan = plans_dict[plan_k]
            schedule = schedule_dict[schedule_name]

            if "repeat_s" in schedule.keys():
                # get last time execution and add repeat_s for ceiling(now-plan_time/repeat_s) times
                prev_exec_time = calc_last_runtime(
                    wdays=schedule['weekdays'], start_time=schedule["start_time"])
                next_exec_time = prev_exec_time + datetime.timedelta(seconds=schedule["repeat_s"]*math.ceil(
                    (plan_time_start-prev_exec_time).seconds/schedule["repeat_s"]))
                # check if this plan was already executed. If so, calc next one.
                if self.plan_already_executed(plan_k, next_exec_time):
                    next_exec_time += datetime.timedelta(seconds=schedule["repeat_s"])
                next_plans_list = add_plan(plan_name=plan_k, plan_datetime=next_exec_time,
                                           next_plans_list=next_plans_list)
            else:
                # check if one of weekday + time combinations is between plan_time_start and plan_time_end
                hours_, minutes = schedule["start_time"].split(":")
                possible_times = [next_date_wday(wday)+datetime.timedelta(
                    hours=float(hours_), minutes=float(minutes)) for wday in schedule['weekdays']]
                # necessary if action is running currently
                duration_adjustment = sum([get_duration(plan["actions"][action])
                                           for action in plan["actions"]])
                # if it should, it may re-run the commands which ran before already, e.g. the big pump may run a 2nd time
                plan_times = [possible_time for possible_time in possible_times if plan_time_start +
                              datetime.timedelta(seconds=-duration_adjustment) < possible_time < plan_time_end]
                if len(plan_times) <= 0:
                    continue
                for plan_time in plan_times:
                    if not self.plan_already_executed(plan_k, plan_time):
                        next_plans_list = add_plan(plan_name=plan_k, plan_datetime=plan_time,
                                                next_plans_list=next_plans_list)
        next_plans_list = add_plan(plan_datetime=plan_time_end,
                                   plan_name="refresh_schedule", next_plans_list=next_plans_list)
        self.logger.debug("Schedule calculated...")
        return(next_plans_list)

    def refresh_schedule(self, hours=24):
        # updates the self._next_plans list
        next_plans_list = self.calculate_schedule()
        self.plan_schedule = next_plans_list
        self.logger.info(
            "There are " + str(threading.active_count()) + " threads active.")
        self.send_next_plans()

    def load_plan(self, plan_name):
        with open("settings/plans.json") as file_plans:
            plans_dict = OrderedDict(json.load(file_plans))
        if plan_name in plans_dict.keys():
            return(plans_dict[plan_name])
        else:
            self.logger.error("Tried to load undefined plan: "+plan_name)
            raise KeyError

    def execute_plan(self, plan_name):
        self.logger.info("Executing "+plan_name)
        if plan_name == "refresh_schedule":
            self.refresh_schedule()
            return(1)
        plan = self.load_plan(plan_name)
        for action_name in plan["actions"].keys():
            action = plan["actions"][action_name]
            for device in action["devices"]:
                if action["task"] == "turn_on":
                    self.turn_on(device)
                elif action["task"] == "turn_off":
                    self.turn_off(device)
                elif action["task"] == "take_picture":
                    self.take_picture(device)
                else:
                    self.logger.exception(
                        "The specified action '" + str(action["task"])+"' is not implemented.")
            if "duration" in action.keys():
                time.sleep(action["duration"])
                for device in action["devices"]:
                    if action["task"] == "turn_on":
                        self.turn_off(device)
                    elif action["task"] == "turn_off":
                        self.turn_on(device)
                    else:
                        self.logger.exception(
                            "The specified action '" + str(action["task"])+"' is not implemented.")

    def run(self, cycle_time_s=1):
        # search for task wich should be executed next, wrap it's function and execute
        if self.schedule_change_date != os.path.getmtime("settings/schedule.json"):
            self.refresh_schedule()
            self.schedule_change_date = os.path.getmtime("settings/schedule.json")
            return()
        if self.plan_schedule[0]["exec_time"] < datetime.datetime.today() + datetime.timedelta(seconds=cycle_time_s):
            plan = self.plan_schedule.pop(0)
            #TODO: Pumping won't start, taking picture works
            delta_t = (plan["exec_time"]-datetime.datetime.today()).total_seconds()
            self.logger.info("Executing plan " + plan["plan_name"] + " in " + str(delta_t) + " seconds.")
            threading.Timer(delta_t,function = self.execute_plan, args=[plan["plan_name"]]).start()
            self.executed_plans.insert(0, plan)
            #TODO: trim executed_plans to only have last time a plan was executed. Don't need to store more.
            self.refresh_schedule()



    def send_next_plans(self):
        # sends the next plans as text to blynk. only the ones which differ from self.sent_plans
        with open("settings/blynk_settings.json") as file_settings:
            blynk_settings = OrderedDict(json.load(file_settings))
        vpins = blynk_settings["plan_viewer"]["vpins"]
        for i, vpin in enumerate(vpins):
            if i > len(self.plan_schedule):
                continue
            send_str = self.plan_schedule[i]["exec_time"].strftime(
                format="%Y-%m-%d %H:%M") + ": " + self.plan_schedule[i]["plan_name"]
            sending = False
            if i >= len(self.sent_plans):
                self.sent_plans.insert(i, send_str)
                sending = True
            elif self.sent_plans[i] != send_str:
                self.sent_plans[i] = send_str
                sending = True
            if sending is True:
                self.logger.debug("Send plan " + send_str + " to vpin " + str(vpin))
                threading.Timer(0, self.blynk.virtual_write, args=[vpin, send_str]).start()

##### here starts the API implementation of functions to control the green_wall and blynk ################
    def get_value_device(self, vpin=None, name="", *args, **kwargs):
        self.logger.debug("Get value from " + str(vpin) +
                          " args= " + str(args) + " kwargs= " + str(kwargs))
        if vpin is None and name == "":
            raise KeyError
        try:
            if vpin is not None:
                dev = self.green_wall.get_device_vpin(vpin)
            else:
                dev = self.green_wall.get_device_name(name)
        except:
            self.logger.exception(
                "Could not find device vpin="+str(vpin) + " , name="+name)
        return(dev.getValue())

    def set_value_device_vpin(self, vpin, val=-1, *args, **kwargs):
        self.logger.debug("Set value to " + str(val) + " on " +
                          str(vpin) + " args= " + str(args) + " kwargs= " + str(kwargs))
        if len(args) > 0:
            # from blynk, here is the value as a string:
            val = int(args[0][0])
        if not isinstance(val, int):
            try:
                val = int(val[0][0])
            except:
                self.logger.exception(
                    "set_value_device_vpin: Couldn't get value from passed arguments val and args.")
        try:
            dev = self.green_wall.get_device_vpin(vpin)
        except:
            self.logger.exception("Could not find device vpin="+str(vpin))
        if val == dev.getValue():
            return(1)
        if val == 1:
            self.turn_on(dev.name)
        else:
            self.turn_off(dev.name)
        return(1)

    def take_picture(self, cam_name=None, tries=5):
        # check if light is on, otherwise don't take picture:
        dev_light = self.green_wall.get_device_regex("light")
        if any([dev.getValue() == 0 for dev in dev_light]):
            self.logger.debug("Light is turned off, therefore no picture is taken.")
            return(0)
        # get camera object from device list
        self.logger.debug("Taking picture with cam " + str(cam_name))
        if cam_name is not None:
            cam = self.green_wall.get_device_name(name=cam_name)
        else:
            cam = self.green_wall.camera_devices[0]
        try:
            fn, image_url = cam.take_picture()
        except CameraException:
            self.logger.error(
                "Could not take picture. Tried to reset camera, but failed.")
            return(0)
        threading.Timer(0, self.blynk.set_property, args=[cam.vpin, "urls", image_url]).start()
        threading.Timer(0, self.blynk.virtual_write, args=[cam.vpin, 1]).start()
        # self.blynk.set_property(cam.vpin, "urls", image_url)
        # self.blynk.virtual_write(cam.vpin, 1)  # shows the newest picture
        return(1)

    def turn_on(self, device):
        dev = self.green_wall.get_device_name(name=device)
        try:
            dev.turn_on()
        except:
            self.logger.exception("Turning on device "+device+" failed.")
        self.logger.debug(device + ": turned on")
        # send value to blynk:
        val = dev.getValue()
        virt_pin = dev.vpin
        threading.Timer(0, self.blynk.virtual_write, args=[virt_pin, val]).start()
        # self.blynk.virtual_write(virt_pin, val)

    def turn_off(self, device):
        dev = self.green_wall.get_device_name(name=device)
        try:
            dev.turn_off()
        except:
            self.logger.exception("Turning off device "+device+" failed.")
        self.logger.debug(device + ": turned off")
        # send value to blynk:
        val = dev.getValue()
        virt_pin = dev.vpin
        threading.Timer(0, self.blynk.virtual_write, args=[virt_pin, val]).start()
        # self.blynk.virtual_write(virt_pin, val)
