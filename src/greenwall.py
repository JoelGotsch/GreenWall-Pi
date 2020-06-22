import gpiozero
import json
import logging
import datetime
import sys
import weakref
import threading

from collections import OrderedDict

try:
    from src.misc import calc_last_runtime
    from src.blynklib import Blynk
    from src.taskmanager import task_manager, task
except ModuleNotFoundError:
    from misc import calc_last_runtime
    from blynklib import Blynk
    from taskmanager import task_manager, task


class device:
    """A class for GPIO devices which handles turning them on and off."""

    def __init__(self, name, gpiopin, blynk_vpin, min_pause, logger, *args, **kwargs):
        self.name = name
        self.gpiopin = gpiopin
        self.vpin = blynk_vpin
        self.tm = None
        self.blynk = None
        try:
            self.gpio_obj = gpiozero.LED(gpiopin)
        except gpiozero.exc.GPIOPinInUse:
            logger.error(
                "A Gpio-Pin is assigned to at least two devices. Check devices.json")
            raise gpiozero.exc.GPIOPinInUse
        self.min_pause = min_pause
        self.logger = logger
        try:
            with open("settings/last_turned_on.json") as file_settings:
                last_turned_on = dict(json.load(file_settings))
        except FileNotFoundError:
            last_turned_on = dict()
            last_turned_on[name] = str(
                datetime.datetime.today()+datetime.timedelta(days=-1))
        if name not in last_turned_on.keys():
            last_turned_on[name] = str(
                datetime.datetime.today()+datetime.timedelta(days=-1))
            with open('settings/last_turned_on.json', 'w') as outfile:
                json.dump(last_turned_on, outfile)
        self.last_date_turned_on = datetime.datetime.strptime(
            last_turned_on[name], "%Y-%m-%d %H:%M:%S.%f")
        self.logger.info("Initialized device " + name)
    
    def addTm(self, tm):
        self.tm = tm
    
    def addBlynk(self, blynk):
        self.blynk=weakref.ref(blynk)
        self.blynk().addEvent(event_name= "read v"+str(self.vpin), func=self.getValue)
        self.blynk().addEvent(event_name= "write v"+str(self.vpin), func=self.setValue)
        # self.blynk._events['{}{}'.format("write v", self.vpin)] = self.setValue
        self.WriteToBlynk()
        self.logger.debug("Initiated blynk on device " + self.name)

    def WriteToBlynk(self, val=None):
        if self.blynk is None:
            self.logger.debug("Tried writing to Blynk before blynk was added to device " + self.name)
            return(0)
        if val is None:
            val = self.getValue()
        virt_pin = self.vpin
        def wrap_f():
            #more sophisticated error handling, multiple tries or checking the status on server could go here:
            self.blynk().virtual_write(virt_pin, val)
        task_name="Write " + str(val) + " to vpin " + str(virt_pin)
        if self.tm is not None:
            self.tm.add_task(task(exec_time=datetime.datetime.today(), func=wrap_f,
                           name=task_name, logger=self.logger))
        else:
            th = threading.Thread(target=wrap_f,name=task_name)
            th.start()
        return(1)
    
    def setValue(self, val, *args, **kwargs):
        if len(args) > 0:
            # from blynk, here is the value as a string:
            val = int(args[0][0])
        self.logger.debug("Set value to " + str(val) + " on " + self.name + " args= " + str(args) + " kwargs= "+ str(kwargs))
        if val == self.getValue():
            return(1)
        if val == 1:
            self.turn_on()
        else:
            self.turn_off()
        return(1)

    def turn_on(self):
        if datetime.datetime.today() <= self.last_date_turned_on + datetime.timedelta(seconds=self.min_pause):
            self.logger.info("Tried to turn on device '" + self.name + "' before min_pause= " +
                             str(self.min_pause) + " seconds since the last turn on event.")
            self.WriteToBlynk()
            return(0)
        self.gpio_obj.on()
        self.last_date_turned_on = datetime.datetime.today()
        self.logger.debug(self.name + ": turned on")
        # write to last_turned_on
        with open("settings/last_turned_on.json") as file_settings:
            last_turned_on = dict(json.load(file_settings))
        last_turned_on[self.name] = str(datetime.datetime.today())
        with open('settings/last_turned_on.json', 'w') as outfile:
            json.dump(last_turned_on, outfile)
        # send info to blynk (via thread!)
        self.WriteToBlynk()
        return(1)
        

    def turn_off(self):
        self.gpio_obj.off()
        self.logger.debug(self.name + ": turned off")
        self.WriteToBlynk()
        # send info to blynk

    def getValue(self):
        return(self.gpio_obj.value)

    def get_targetValue(self):
        """Returns the state in which the device should be at the current time, derived from last set value in plans.json for device with this name.
        Returns None if Dive is not described in plans.json"""
        with open("settings/plans.json") as file_plans:
            plans_dict = OrderedDict(json.load(file_plans))
        # (1)filter for actions for that device, save plan
        # (2)calculate last time action should have been set for each action and save latest of possible times
        # (3) step through actions of plan and check if action started/finished and if device was used.
        #  if action = turn_on, then value = 1. But if duration is given, then flip value (1-value)
        # (1); contains the whole action, (is_active, description, weekdays, start_time,..)
        filtered_plans = OrderedDict()
        for plan in plans_dict:
            if plans_dict[plan]["is_active"] is True and any([self.name in devices for devices in plans_dict[plan]["actions"]]):
                filtered_plans[plan] = plans_dict[plan]
        # (2)
        last_plan = OrderedDict(last_time=datetime.datetime.min)
        for ac in filtered_plans:
            filtered_plans[ac]["last_time"] = calc_last_runtime(
                wdays=filtered_plans[ac]["weekdays"], start_time=filtered_plans[ac]["start_time"])
            if filtered_plans[ac]["last_time"] > last_plan["last_time"]:
                last_plan = filtered_plans[ac]

        if len(filtered_plans) == 0:
            self.logger.debug(
                "All actions filtered in function get_targetValue for device " + self.name)
            return(None)
        # (3)
        last_time = last_plan["last_time"]
        last_time_new = last_time
        last_action_task = ""
        last_action_finished = False
        last_action_had_duration = False
        # last_action_started = False
        for action in last_plan["actions"].keys():
            if "duration" in last_plan["actions"][action].keys():
                last_time_new = last_time + \
                    datetime.timedelta(
                        seconds=last_plan["actions"][action]["duration"])
            if self.name in last_plan["actions"][action]["devices"]:
                # last_action_started=True
                last_action_task = last_plan["actions"][action]["task"]
                if "duration" in last_plan["actions"][action].keys():
                    last_action_had_duration = True
            if last_time_new > datetime.datetime.today():
                last_action_finished = last_action_finished and (
                    self.name not in last_plan["actions"][action]["devices"])
                if last_action_task == "":
                    # this is the case where the plan already started, but the task which involves the device didn't start yet.
                    # E.g. Now is 11:01 and the device is a small pump, the pumping plan starts with the big pump for 10s at 11:00,
                    # so the small pump didn't start.
                    # action which is coming will be used where the value will be flipped due to last_action_finished=False.
                    # this is an assumption! correct would be to look up the previous action in filtered_plans.
                    # In the example above it works out.. If this should be improved, probably a last_action_started variable is needed to determine
                    # one needs to use the previous action
                    last_action_task = [last_plan[action]["task"]
                                        for action in last_plan["actions"]][0]
                else:
                    break
            else:
                last_time = last_time_new
                last_action_finished = last_action_finished or (
                    self.name in last_plan["actions"][action]["devices"])

        if last_action_task == "turn_on":
            value = 1
        elif last_action_task == "turn_off":
            value = 0
        else:
            self.logger.exception("While checking the target value, task '" + last_action_task +
                                  "' for device " + self.name + " was tried, which isn't defined.")
            return(None)
        if not last_action_finished:
            value = 1-value
        if last_action_had_duration:
            value = 1-value
        return(value)


class camera:
    """We will also need a little https server for the blynk app to load the pictures.."""

    def __init__(self, *args, **kwargs):
        self.camera = 1  # TODO

    def take_picture(self, filename=""):
        # save as png
        pass


class greenwall:
    """ Contains all the appliances on the wall such as the pumps, the light and the camera """

    def __init__(self, name, platform, blynk="", logger=None, *args, **kwargs):
        self.name = name
        self.platform = platform  # Raspberry or Onion
        self.devices = []
        self.tm = None
        self.blynk = None
        # self.blynk=blynk
        # init logger
        if logger is None:
            logging.basicConfig(filename='logs/green_wall.log', level=logging.INFO,
                                format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            logger = logging.getLogger('green_wall')
            ch = logging.StreamHandler(sys.stdout)
            logger.addHandler(ch)
        self.logger = logger
        # read device list from devices.json:
        with open("settings/devices.json") as file_settings:
            device_settings = dict(json.load(file_settings))
            gpio_settings = device_settings["GPIO"]
        for k in gpio_settings.keys():
            curr_device = gpio_settings[k]
            self.devices.append(device(name=curr_device["name"], gpiopin=curr_device["gpio_pin"],
                                       blynk_vpin=curr_device["vpin"], min_pause=curr_device["min_pause"], blynk=blynk, logger=self.logger))
        # check if all devices are in the right status; according to plans.json and send current state to blynk
        for dev in self.devices:
            tv = dev.get_targetValue()
            if tv is not None and tv != dev.getValue():
                self.logger.info(
                    "Device '" + dev.name + "' was in the wrong state and value is now set to " + str(tv))
                if tv == 1:
                    dev.turn_on()
                else:
                    dev.turn_off()

        self.logger.info("Initiated green wall named '" +
                         name + "' on " + platform)

    def get_device_name(self, name):
        """returns a device object when you ask for the name"""
        for dev in self.devices:
            if dev.name == name:
                return(dev)
        raise KeyError

    def get_device_vpin(self, vpin):
        """returns a device object when you ask for its vpin"""
        for dev in self.devices:
            if dev.vpin == vpin:
                return(dev)
        raise KeyError

    def getValue_vpin(self, vpin):
        """returns the value of a device (0 or 1) when you ask for its vpin"""
        dev = self.get_device_vpin(vpin)
        return(dev.getValue())

    def addTm(self, tm):
        """adding a task-manager by weak-ref to the green-wall and all devices so that they can schedule tasks."""
        self.logger.debug("Added Taskmanager to greenwall object.")
        self.tm = weakref.ref(tm)
        for dev in self.devices:
            dev.addTm(tm)


    def addBlynk(self, blynk):
        """adding a blynk object by weak-ref to the green-wall and all devices so that they can send infos to the app."""
        self.blynk=weakref.ref(blynk)
        for dev in self.devices:
            dev.addBlynk(blynk)
