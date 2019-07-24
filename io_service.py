#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import time
import threading
import sys
if sys.version_info[0] < 3:
    import Queue as queue
else:
    import queue

import paho.mqtt.client as mqtt
import gpio_next as gpio


class LEDPattern(object):
    led = []

    def __init__(self):
        if not self.led:
            pins = [64, 65, 66, 67]
            for i in range(4):
                self.led.append(gpio.Output(pins[i], default_value=1))

        self.queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def on_press(self):
        self.led[1].write(0)
        self.led[2].write(0)
        time.sleep(0.05)
        self.led[3].write(0)
        self.led[0].write(0)

    def on_release(self):
        self.led[3].write(1)
        self.led[0].write(1)
        time.sleep(0.05)
        self.led[1].write(1)
        self.led[2].write(1)

    def on_listen(self):
        self.all(0)
        
    def on_finish(self):
        self.all(1)

    def all(self, value):
        for i in range(4):
            self.led[i].write(value)

    def blink(self, mask=0xF): 
        print('mask: {}'.format(mask))
        value = 0
        while self.queue.empty():
            for i in range(4):
                if mask & (1 << i):
                    self.led[i].write(value)

            value = 1 - value
            time.sleep(0.5)
        
        if value:
            for i in range(4):
                self.led[i].write(1)


    def acall(self, func):
        self.queue.put(func)

    def _run(self):
        while True:
            func, args, kargs = self.queue.get()
            func(*args, **kargs)


class Pattern(object):
    pattern = None

    def __init__(self):
        if self.pattern is None:
            Pattern.pattern = LEDPattern()

    def __getattr__(self, attr):

        func = getattr(self.pattern, attr)

        def func_warp(*args, **kargs):
            self.pattern.acall((func, args, kargs))

        return func_warp


pattern = Pattern()
amp_power = gpio.Output(2)
amp_mute =gpio.Output(3)


def button_task(mqttc):
    button = gpio.Input(203)
    result = button.wait(0)
    if result and result[0] == 1:
        print('wait for button release')
        button.wait()

    while True:
        result = button.wait()
        if result and result[0] == 1:
            pattern.on_press()
            t1 = result[1]

            for i in range(0, 4):
                result = button.wait(1)
                if result is not None:
                    break

                pattern.blink((2**(1+i)) - 1)

            if result is None:
                result = button.wait()

            t2 = result[1]
            dt = t2 - t1
            print(dt)

            if dt >= 4:
                if os.system('systemctl is-active hey_wifi.service') != 0:
                    os.system('systemctl start hey_wifi.service')
                    continue
                else:
                    os.system('systemctl stop hey_wifi.service')


            pattern.on_release()


def on_message(mqttc, obj, msg):
    print(msg.topic)
    if msg.topic.startswith('/voicen/io/amp'):
        if msg.payload == b'1':
            print('amp on')
            # os.system('sunxi-pio -m PA2=1 && sunxi-pio -m PA3=1')
            amp_power.write(1)
            amp_mute.write(1)
        else:
            print('amp off')
            # os.system('sunxi-pio -m PA3=0 && sunxi-pio -m PA2=0')
            amp_power.write(0)
            amp_mute.write(0)

    elif msg.topic.startswith('/voicen/io/leds/off'):
        pattern.all(1)
    elif msg.topic.startswith('/voicen/io/leds/on'):
        pattern.all(0)



def on_connect(mqttc, obj, flags, rc):
    print('connected - rc: ' + str(rc))
    mqttc.subscribe('/voicen/io/#', 0)


def on_publish(mqttc, obj, mid):
    print("mid: " + str(mid))


def on_subscribe(mqttc, obj, mid, granted_qos):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


def on_log(mqttc, obj, level, string):
    print(string)


# If you want to use a specific client id, use
# mqttc = mqtt.Client("client-id")
# but note that the client id must be unique on the broker. Leaving the client
# id parameter empty will generate a random id for you.
mqttc = mqtt.Client()
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe
# Uncomment to enable debug messages
# mqttc.on_log = on_log
mqttc.connect('localhost', 1883, 60)


threading.Thread(target=button_task, args=(mqttc,), daemon=True).start()

mqttc.loop_forever()

