import logging
import sys

from threading import Timer
import datetime

class task:
    def __init__(self, exec_time, func, name = None, logger = None, *args, **kwargs):
        self.exec_time = exec_time
        self.name = name
        self.func = func
        if logger is not None:
            self.logger = logger
        else:
            logger = logging.getLogger('task')
            ch = logging.StreamHandler(sys.stdout)
            ch.setLevel(logging.INFO)
            formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            ch.setFormatter(formatter)
            logger.addHandler(ch)
            logger.setLevel(logging.INFO)
            self.logger = logger

    def run(self):
        delta_t = (self.exec_time-datetime.datetime.today()).total_seconds()
        self.logger.debug("Running Job '"+ self.name + "' in " + str(delta_t) + " seconds, that is at " + str(self.exec_time))
        Timer(delta_t, self.func).start()


class task_manager:
    """ makes sure that tasks are being executed without blocking the main thread and without permanent checking while still allowing
    for external steering (e.g. via blynk-app)"""
    def __init__(self, is_active, description, weekdays, start_time, devices, actions, *args, **kwargs):
        # initialize task_list by parsing actions.json and run it.
        self.task_list = []
        logger = logging.getLogger('task_manager')
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        logger.setLevel(logging.INFO)
        self.logger = logger

    def create_task_list(self):
        # updates the task-list for the next 12h including an update at the end of the cycle for itself.
        # the task-list contains all actions like starting and stopping pumps. It needs to be sorted, so that the first task 
        # in the list is the next one to do. The last task is creating the task_list again (for the next 12h).
        pass

    def run(self):
        #search for task wich should be executed next, wrap it's function and execute
        next_task = self.task_list.pop(0)
        next_task.func = self.wrap_task(next_task.func)
        next_task.run()

    def add_task(self):
        # add task to task_list with appropriate position (according to exec_time)
        pass

    def wrap_task(self, func):

        def return_func(func):
            
            #start function
            func()
            #run next task from task list
            self.run()

        return(return_func(func))

