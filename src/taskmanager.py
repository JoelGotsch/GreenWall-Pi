import logging
import sys
import threading
import datetime
import json
import time
from collections import OrderedDict


try:
    from src.misc import get_duration, next_date_wday
except ModuleNotFoundError:
    from misc import get_duration, next_date_wday


class task:
    """ repeat in seconds: task repeats itself every so often. """
    def __init__(self, func, exec_time=datetime.datetime.today(), repeat=0, name="Task", logger=None, *args, **kwargs):
        self.exec_time = exec_time
        self.name = name
        self.func = func
        self.repeat = repeat
        self.logger = logger

    def __str__(self):
        if self.repeat is None or self.repeat == 0:
            return("Execute function " + self.name + " at " + str(self.exec_time))
        else:
            return("Execute function " + self.name + " at " + str(self.exec_time))
    
    def repeat_func(self, repeat):
        def wrap_f():
            self.func()
            tsk = task(func=self.func, exec_time=self.exec_time+datetime.timedelta(seconds=repeat), repeat = repeat, name=self.name, logger=self.logger)
            tsk.run()
        return(wrap_f)

    def run(self):
        delta_t = (self.exec_time-datetime.datetime.today()).total_seconds()
        if self.logger is not None:
            self.logger.debug("Running Job '" + self.name + "' in " +
                            str(delta_t) + " seconds, that is at " + str(self.exec_time))
        if self.repeat is None or self.repeat == 0:
            threading.Timer(delta_t, self.func).start()
        else:
            threading.Timer(delta_t, self.repeat_func(self.repeat)).start()


class task_manager:
    """ makes sure that tasks are being executed without blocking the main thread and without permanent checking while still allowing
    for external steering (e.g. via blynk-app)"""

    def __init__(self, green_wall, blynk, logger=None, *args, **kwargs):
        # initialize task_list by parsing plans.json and run it.
        self.task_list = []
        self._next_plans = [] #just of internal use, tasks are kept here even if task has already his thread and is popped from task_list until task is really run.
        if logger is None:
            logging.basicConfig(filename='logs/task_manager.log', level=logging.INFO,
                                format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            logger = logging.getLogger('task_manager')
            ch = logging.StreamHandler(sys.stdout)
            logger.addHandler(ch)
        self.logger = logger
        self.green_wall = green_wall
        self.create_task_list()
        self.blynk = blynk
        self.logger.debug("Task Manager initialized")
    
    def _add_plan(self, plan_name, plan_datetime):
        # add task to _next_plans with appropriate position (according to exec_time)
        plan = {"plan_name":plan_name, "exec_time":plan_datetime}
        i = 0
        if len(self._next_plans) == 0:
            self._next_plans.insert(i, plan)
            return()
        while i < len(self._next_plans) and plan_datetime > self._next_plans[i]["exec_time"]:
            i += 1
        self._next_plans.insert(i, plan)

    def _refresh_next_plans(self):
        while len(self._next_plans) > 0 and datetime.datetime.today() > self._next_plans[0]["exec_time"]:
           self._next_plans.pop(0)

    def create_task_list(self, hours=12.0, logging_enabled=True):
        # updates the task-list for the next 12h including an update at the end of the cycle for itself.
        # the task-list contains all actions like starting and stopping pumps. It needs to be sorted, so that the first task
        # in the list is the next one to do. The last task is creating the task_list again (for the next 12h).
        plan_time_start = datetime.datetime.today()
        plan_time_end = plan_time_start + datetime.timedelta(hours=hours)
        with open("settings/plans.json") as file_plans:
            plans_dict = OrderedDict(json.load(file_plans))

        for plan_k in plans_dict:
            plan = plans_dict[plan_k]
            if not plan['is_active']:
                continue
            # check if one of weekday + time combinations is between plan_time_start and plan_time_end
            hours, minutes = plan["start_time"].split(":")
            possible_times = [next_date_wday(wday)+datetime.timedelta(
                hours=float(hours), minutes=float(minutes)) for wday in plan['weekdays']]
            # necessary if action is running currently
            duration_adjustment = sum([get_duration(plan["actions"][action])
                                       for action in plan["actions"]])
            # if it should, it may re-run the commands which ran before already, e.g. the big pump may run a 2nd time
            plan_times = [possible_time for possible_time in possible_times if plan_time_start +
                          datetime.timedelta(seconds=-duration_adjustment) < possible_time < plan_time_end]
            if len(plan_times) <= 0:
                continue
            for plan_time in plan_times:
                #add to self._next_plans
                self._add_plan(plan_name=plan_k, plan_datetime=plan_time)
                for action_name in plan["actions"].keys():
                    action = plan["actions"][action_name]
                    for device in action["devices"]:
                        dev = self.green_wall.get_device_name(device)
                        if action["task"] == "turn_on":
                            task1 = dev.turn_on
                            task2 = dev.turn_off
                        elif action["task"] == "turn_off":
                            task1 = dev.turn_off
                            task2 = dev.turn_on
                        else:
                            self.logger.exception(
                                "The specified action '" + str(action["task"])+"' is not implemented.")
                        self.add_task(
                            task(exec_time=plan_time, func=task1, name=action_name, logger=self.logger))
                        if "duration" in action.keys():
                            if logging_enabled:
                                self.add_task(task(exec_time=plan_time+datetime.timedelta(
                                    seconds=action["duration"]), func=task2, name=action_name, logger=self.logger))
                            else:
                                self.add_task(task(exec_time=plan_time+datetime.timedelta(
                                    seconds=action["duration"]), func=task2, name=action_name))
                    if "duration" in action.keys():
                        plan_time = plan_time + datetime.timedelta(seconds=action["duration"])
        if logging_enabled:
            self.add_task(task(exec_time=plan_time_end, func=self.create_task_list,
                           name="Update Task List", logger=self.logger))
            self.logger.info("Finished creating task-list")
            self.logger.info("There are " + str(threading.active_count()) + " threads active.")
            self.send_next_plans()
        else:
            self.add_task(task(exec_time=plan_time_end, func=self.create_task_list,
                           name="Update Task List"))


    def run(self):
        # search for task wich should be executed next, wrap it's function and execute
        while len(self.task_list) > 0:
            next_task = self.task_list.pop(0)
            next_task.run()
    
    def _get_next_plans(self, no_plans=3):
        # could be implemented in the future via looking up the threads in threading module and a naming convention for interesting threads?
        # will be used to show the next 3 tasks in the app like: 2020-06-25 17:00: Watering all, 2020-06-25 22:00: Turn off light, 2020-06-26 07:00: Turn on light
        task_list_save = self.task_list
        self._next_plans = []
        plan_time=12 #hours
        while len(self._next_plans)<no_plans and plan_time < 24*7:
            plan_time += 12
            self.create_task_list(hours=plan_time, logging_enabled=False)
            self._refresh_next_plans()
        self.task_list=task_list_save
        return(self._next_plans[:no_plans])
    
    def send_next_plans(self):
        with open("settings/blynk_settings.json") as file_settings:
            blynk_settings = OrderedDict(json.load(file_settings))
        vpins=blynk_settings["plan_viewer"]["vpins"]
        next_plans=self._get_next_plans(no_plans=len(vpins))
        for i, vpin in enumerate(vpins):
            def wrap_sending(vpin, plan_name, plan_time):
                def send_plan():
                    send_str=plan_time.strftime(format="%Y-%m-%d %H:%M") + ": " + plan_name
                    print(send_str)
                    self.blynk.virtual_write(vpin, send_str)
                return(send_plan)
            func = wrap_sending(vpin, next_plans[i]["plan_name"], next_plans[i]["exec_time"])
            self.add_task(task(func=func,name="send plan",logger=self.logger))


    def add_task(self, task):
        # add task to task_list with appropriate position (according to exec_time)
        self.logger.debug("Added task: " + str(task))
        i = 0
        if len(self.task_list) == 0:
            self.task_list.insert(i, task)
            return()
        while i < len(self.task_list) and task.exec_time > self.task_list[i].exec_time:
            i += 1
        self.task_list.insert(i, task)
