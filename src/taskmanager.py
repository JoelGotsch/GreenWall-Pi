import logging
import sys
import threading
import datetime
import json
import time
from collections import OrderedDict
import os


try:
    from src.misc import get_duration, next_date_wday, add_plan
except ModuleNotFoundError:
    from misc import get_duration, next_date_wday, add_plan
    from cam import CameraException


class task:
    """ repeat in seconds: task repeats itself every so often. """

    def __init__(self, func, exec_time=datetime.datetime.today(), name="Task", logger=None, func_kwargs={}, args=[], *add_args, **kwargs):
        self.exec_time = exec_time
        self.name = name
        self.func = func
        self.logger = logger
        self.func_kwargs = func_kwargs  # function arguments
        self.args = args
        self.run()

    def __str__(self):
        return("Execute function " + self.name + " at " + str(self.exec_time))

    def run(self):
        delta_t = (self.exec_time-datetime.datetime.today()).total_seconds()
        if self.logger is not None:
            self.logger.debug("Running Job '" + self.name + "' in " +
                              str(delta_t) + " seconds, that is at " + str(self.exec_time))
        threading.Timer(delta_t, self.func, *self.args,
                        **self.func_kwargs).start()


class task_manager:
    """ makes sure that tasks are being executed without blocking the main thread and without permanent checking while still allowing
    for external steering (e.g. via blynk-app)"""

    def __init__(self, green_wall, blynk, logger=None, *args, **kwargs):
        # initialize task_list by parsing plans.json and run it.
        # self.task_list = []
        # In here will be dicts with {exec_time: "2020-08-01 08:00", plan: "turn_on_light"} ordered by exec_time. last entry is {exec_time: "2020-08-01 09:00", plan: "refresh_plan_schedule"}
        self.plan_schedule = []
        # plans are then parsed when their exec_time is reached. That means tasks are only generated then.
        if logger is None:
            logging.basicConfig(filename='logs/task_manager.log', level=logging.INFO,
                                format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            logger = logging.getLogger('task_manager')
            ch = logging.StreamHandler(sys.stdout)
            logger.addHandler(ch)
        self.logger = logger
        self.green_wall = green_wall
        self.schedule_change_date = os.path.getmtime("settings/schedule.json")
        self.refresh_schedule()
        self.blynk = blynk
        self.logger.debug("Task Manager initialized")
        self.sent_plans = []
        self.blynk.addEvent(event_name="read v*", func=self.get_value_device)
        self.blynk.addEvent(event_name="write v*",
                            func=self.set_value_device_vpin)

    def calculate_schedule(self, hours=24):
        next_plans_list = []
        plan_time_start = datetime.datetime.today()
        plan_time_end = plan_time_start + datetime.timedelta(hours=hours)
        with open("settings/plans.json") as file_plans:
            plans_dict = OrderedDict(json.load(file_plans))

        for plan_k in plans_dict:
            plan = plans_dict[plan_k]
            if not plan['is_active']:
                continue
            # check if one of weekday + time combinations is between plan_time_start and plan_time_end
            hours_, minutes = plan["start_time"].split(":")
            possible_times = [next_date_wday(wday)+datetime.timedelta(
                hours=float(hours_), minutes=float(minutes)) for wday in plan['weekdays']]
            # necessary if action is running currently
            duration_adjustment = sum([get_duration(plan["actions"][action])
                                       for action in plan["actions"]])
            # if it should, it may re-run the commands which ran before already, e.g. the big pump may run a 2nd time
            plan_times = [possible_time for possible_time in possible_times if plan_time_start +
                          datetime.timedelta(seconds=-duration_adjustment) < possible_time < plan_time_end]
            if len(plan_times) <= 0:
                continue
            for plan_time in plan_times:
                # add to self._next_plans
                add_plan(plan_name=plan_k, plan_datetime=plan_time,
                         next_plans_list=next_plans_list)
        add_plan(plan_datetime=plan_time_end,
                 plan_name="refresh_schedule", next_plans_list=next_plans_list)
        return(next_plans_list)

    def refresh_schedule(self, hours=24):
        # updates the self._next_plans list
        next_plans_list = self.calculate_schedule()
        self.logger.info("Finished creating schedule")
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
            raise NotImplementedError

    def execute_plan(self, plan_name):
        self.logger.info("Executing "+plan_name)
        if plan_name == "refresh_schedule":
            self.refresh_schedule()
            return(1)
        plan = self.load_plan(plan_name)
        for action_name in plan["actions"].keys():
            action = plan["actions"][action_name]
            for device in action["devices"]:
                dev = self.green_wall.get_device_name(device)
                kwargs = {}
                if action["task"] == "turn_on":
                    task1 = dev.turn_on
                    task2 = dev.turn_off
                elif action["task"] == "turn_off":
                    task1 = dev.turn_off
                    task2 = dev.turn_on
                elif action["task"] == "take_picture":
                    task1 = self.take_picture,
                    kwargs = {"cam_name": device}
                else:
                    self.logger.exception(
                        "The specified action '" + str(action["task"])+"' is not implemented.")
                    task(exec_time=plan_time, func=task1,
                         name=action_name, logger=self.logger, kwargs=kwargs)
                if "duration" in action.keys():
                    task(exec_time=plan_time+datetime.timedelta(
                        seconds=action["duration"]), func=task2, name=action_name)
                    if "duration" in action.keys():
                        plan_time = plan_time + \
                            datetime.timedelta(seconds=action["duration"])

    def run(self, cycle_time_s=1):
        # search for task wich should be executed next, wrap it's function and execute
        if self.plan_schedule[0]["exec_time"] > datetime.datetime.today() + datetime.timedelta(seconds=cycle_time_s) or self.schedule_change_date != os.path.getmtime("settings/schedule.json"):
            plan = self.plan_schedule.pop(0)
            self.execute_plan(plan["plan_name"])

    def send_next_plans(self):
        # sends the next plans as text to blynk. only the ones which differ from self.sent_plans
        with open("settings/blynk_settings.json") as file_settings:
            blynk_settings = OrderedDict(json.load(file_settings))
        vpins = blynk_settings["plan_viewer"]["vpins"]
        for i, vpin in enumerate(vpins):
            if i > len(self.plan_schedule):
                continue
            send_str = self.plan_schedule[i]["exec_time"].strftime(
                format="%Y-%m-%d %H:%M") + ": " + self.plan_schedule[i]["plan"]
            if i >= len(self.sent_plans):
                self.sent_plans.insert(i, send_str)
            elif self.sent_plans[i] != send_str:
                self.sent_plans[i] = send_str
                task(func=self.blynk.virtual_write,
                     name="send plan "+str(i),
                     logger=self.logger,
                     func_kwargs={"vpin": vpin, "val": send_str})

##### here starts the APIP implementation of functions to control the green_wall and blynk ################
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
        return(dev.getValue)

    def set_value_device_vpin(self, vpin, val, *args, **kwargs):
        self.logger.debug("Set value to " + str(val) + " on " +
                          str(vpin) + " args= " + str(args) + " kwargs= " + str(kwargs))
        if len(args) > 0:
            # from blynk, here is the value as a string:
            val = int(args[0][0])
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
        # get camera object from device list
        if cam_name is not None:
            cam = self.green_wall.get_device_name(name=cam_name)
        else:
            cam = self.green_wall.camera_devices[0]
        try:
            fn, image_url = cam.take_picture()
        except CameraException:
            self.logger.error(
                "Could not take picture. Tried to reset camera, but failed.")
        self.blynk.set_property(cam.vpin, "urls", image_url)
        self.blynk.virtual_write(cam.vpin, 1)  # shows the newest picture
        pass

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
        task_name = "Write " + str(val) + " to vpin " + str(virt_pin)
        task(func=self.blynk.virtual_write, exec_time=datetime.datetime.today(),
             name=task_name, args=[virt_pin, val], logger=self.logger)

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
        task_name = "Write " + str(val) + " to vpin " + str(virt_pin)
        task(func=self.blynk.virtual_write, exec_time=datetime.datetime.today(),
             name=task_name, args=[virt_pin, val], logger=self.logger)

    # def add_task(self, task):
    #     # add task to task_list with appropriate position (according to exec_time)
    #     self.logger.debug("Added task: " + str(task))
    #     i = 0
    #     if len(self.task_list) == 0:
    #         self.task_list.insert(i, task)
    #         return()
    #     while i < len(self.task_list) and task.exec_time > self.task_list[i].exec_time:
    #         i += 1
    #     self.task_list.insert(i, task)
