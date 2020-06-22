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
    def __init__(self, exec_time, func, name=None, logger=None, *args, **kwargs):
        self.exec_time = exec_time
        self.name = name
        self.func = func
        if logger is not None:
            self.logger = logger
        else:
            logger = logging.getLogger('task')
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            formatter = logging.Formatter(
                '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
            logger.setLevel(logging.INFO)
            self.logger = logger

    def __str__(self):
        return("Execute function " + self.name + " at " + str(self.exec_time))

    def run(self):
        delta_t = (self.exec_time-datetime.datetime.today()).total_seconds()
        self.logger.debug("Running Job '" + self.name + "' in " +
                          str(delta_t) + " seconds, that is at " + str(self.exec_time))
        threading.Timer(delta_t, self.func).start()


class task_manager:
    """ makes sure that tasks are being executed without blocking the main thread and without permanent checking while still allowing
    for external steering (e.g. via blynk-app)"""

    def __init__(self, green_wall, logger=None, *args, **kwargs):
        # initialize task_list by parsing plans.json and run it.
        self.task_list = []
        if logger is None:
            logging.basicConfig(filename='logs/task_manager.log', level=logging.INFO,
                                format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            logger = logging.getLogger('task_manager')
            ch = logging.StreamHandler(sys.stdout)
            logger.addHandler(ch)
        self.logger = logger
        self.green_wall = green_wall
        self.create_task_list()
        self.logger.debug("Task Manager initialized")

    def create_task_list(self):
        # updates the task-list for the next 12h including an update at the end of the cycle for itself.
        # the task-list contains all actions like starting and stopping pumps. It needs to be sorted, so that the first task
        # in the list is the next one to do. The last task is creating the task_list again (for the next 12h).
        plan_time_start = datetime.datetime.today()
        plan_time_end = plan_time_start + datetime.timedelta(hours=12.0)
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
                            self.add_task(task(exec_time=plan_time+datetime.timedelta(
                                seconds=action["duration"]), func=task2, name=action_name, logger=self.logger))
                    if "duration" in action.keys():
                        plan_time = plan_time + \
                            datetime.timedelta(seconds=action["duration"])
        self.add_task(task(exec_time=plan_time_end, func=self.create_task_list,
                           name="Update Task List", logger=self.logger))
        self.logger.debug("Finished creating task-list")
        self.logger.debug("There are " + str(threading.active_count()) + " threads active.")

    def run(self):
        # search for task wich should be executed next, wrap it's function and execute
        while len(self.task_list) > 0:
            next_task = self.task_list.pop(0)
            next_task.run()

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
