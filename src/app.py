from greenwall import greenwall
from taskmanager import task_manager

if __name__ == "__main__":
    gw = greenwall(name="Joels Green Wall :)", platform="Raspberry Pi 4")
    tm = task_manager(green_wall=gw)
    tm.run()
