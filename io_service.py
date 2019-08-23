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


class LED1x4(object):
    leds = []

    def __init__(self):
        if not self.leds:
            pins = [64, 65, 66, 67]
            for i in range(4):
                self.leds.append(gpio.Output(pins[i], default_value=1))

        self.queue = queue.Queue()
        threading.Thread(target=self._run, daemon=True).start()

    def on_press(self):
        self.leds[1].write(0)
        self.leds[2].write(0)
        time.sleep(0.05)
        self.leds[3].write(0)
        self.leds[0].write(0)

    def on_release(self):
        self.leds[3].write(1)
        self.leds[0].write(1)
        time.sleep(0.05)
        self.leds[1].write(1)
        self.leds[2].write(1)

    def on_wakeup(self):
        value = 0b1111000
        for _ in range(4):
            self.value(value)
            value = value >> 1
            time.sleep(0.5)

    def on_listen(self):
        self.value(0xF)

    def on_wait(self):

        value = 0b1010
        self.repeat(value)

    def on_finish(self):
        self.value(0x0)

    def same(self, value):
        for i in range(4):
            self.leds[i].write(value)

    def raw(self, value):
        for i in range(4):
            self.leds[i].write((value >> i) & 1)

    def value(self, value):
        self.raw(~value)

    def mask(self, value, mask):
        value = 1 - value
        for i in range(4):
            if (mask >> i) & 1:
                self.leds[i].write(value)

    def repeat(self, value):
        while self.queue.empty():
            self.value(value)

            value = ~value
            time.sleep(0.5)

        self.value(0x0)

    def step(self):
        step = 0
        while self.queue.empty():
            self.value(1 << step)
            step = (step + 1) & 0x3
            time.sleep(0.5)

    def loop(self):
        delta = 1
        step = 0
        while self.queue.empty():
            self.value(1 << step)
            if 0 == step:
                delta = 1
            elif 3 == step:
                delta = -1
            step += delta
            time.sleep(0.5)

    def wipe(self):
        value = 0b0111
        for _ in range(4):
            self.value(value)
            value = value >> 1
            time.sleep(0.5)

    def blink(self, mask=0xF):
        value = 0
        while self.queue.empty():
            self.mask(value, mask)

            value = 1 - value
            time.sleep(0.5)

        if value:
            for i in range(4):
                self.leds[i].write(1)

    def call(self, func):
        self.queue.put(func)

    def _run(self):
        while True:
            func, args, kargs = self.queue.get()
            func(*args, **kargs)


class LEDAgent(object):
    leds = None

    def __init__(self):
        if self.leds is None:
            LEDAgent.leds = LED1x4()

    def __getattr__(self, attr):

        func = getattr(self.leds, attr)

        def func_warp(*args, **kargs):
            self.leds.call((func, args, kargs))

        return func_warp


class Amplifier(object):
    def __init__(self, power=2, mute=3):
        self.power = gpio.Output(power)
        self.mute = gpio.Output(mute)

    def on(self):
        # os.system('sunxi-pio -m PA2=1 && sunxi-pio -m PA3=1')
        self.power.write(1)
        self.mute.write(1)

    def off(self):
        self.mute.write(0)
        self.power.write(0)


class HeyWifiService(object):
    def __init__(self):
        self.state = 0

    def is_active(self):
        return 0 == os.system('systemctl is-active hey_wifi.service')

    def start(self):
        return os.system('systemctl start hey_wifi.service')

    def stop(self):
        return os.system('systemctl stop hey_wifi.service')


leds = LEDAgent()
amplifier = Amplifier()
hey_wifi_service = HeyWifiService()


def button_task(mqttc):
    button = gpio.Input(203)
    result = button.wait(0)
    if result and result[0] == 1:
        print('wait for button release')
        button.wait()

    while True:
        result = button.wait()
        if result and result[0] == 1:
            leds.on_press()
            t1 = result[1]

            hey_wifi_active = hey_wifi_service.is_active()

            for i in range(0, 4):
                result = button.wait(1)
                if result is not None:
                    break
                if not hey_wifi_active:
                    leds.blink((2**(1 + i)) - 1)
                else:
                    leds.value(0xF << (i + 1))

            if result is None:
                result = button.wait()

            t2 = result[1]
            dt = t2 - t1
            print(dt)

            if dt >= 4:
                if not hey_wifi_active:
                    hey_wifi_service.start()
                else:
                    hey_wifi_service.stop()

                continue
            elif hey_wifi_active:
                mask = 0xF >> hey_wifi_service.state
                leds.mask(1, ~mask)
                leds.blink(mask)
                continue

            leds.on_release()


def str2int(s):
    if s.startswith('0x'):
        return int(s, 16)
    elif s.startswith('0b'):
        return int(s, 2)
    else:
        return int(s)


def on_message(mqttc, obj, msg):
    print(msg.topic)
    if msg.topic == '/voicen/amplifier':
        if msg.payload == b'1':
            print('amp on')
            amplifier.on()
        else:
            print('amp off')
            amplifier.off()

    elif msg.topic == '/voicen/leds/value':
        leds.value(str2int(msg.payload.decode()))
    elif msg.topic == '/voicen/hey_wifi':
        hey_wifi_service.state = (int(msg.payload.decode()))
        if hey_wifi_service.state:
            mask = 0xF >> hey_wifi_service.state
            leds.mask(1, ~mask)
            leds.blink(mask)
        else:
            leds.value(0x0)


def on_connect(mqttc, obj, flags, rc):
    print('connected - rc: ' + str(rc))
    mqttc.subscribe('/voicen/leds/#', 0)
    mqttc.subscribe('/voicen/amplifier', 0)
    mqttc.subscribe('/voicen/hey_wifi', 0)


def on_publish(mqttc, obj, mid):
    print("mid: " + str(mid))


def on_subscribe(mqttc, obj, mid, granted_qos):
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


# If you want to use a specific client id, use
# mqttc = mqtt.Client("client-id")
# but note that the client id must be unique on the broker. Leaving the client
# id parameter empty will generate a random id for you.
mqttc = mqtt.Client()
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

mqttc.connect('localhost', 1883, 60)


threading.Thread(target=button_task, args=(mqttc,), daemon=True).start()

mqttc.loop_forever()
