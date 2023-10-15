import senec
import time
import threading
import math
import pigpio

SENEC_IP = "192.168.2.22"
PULSES_PER_KWH = 2000           # 2000 is the current default of the iDM Navigator control
POLLING_INTERVAL_S = 30         # updating power value from the senec
MIN_HPULSE_S = 0.050            # High Level for S0 pulse should last > 30 ms
LONGEST_PULSE_S = 60            # Maximum Pulse duration, serves as keep-alive even whithout any generated power
CHARGE_THRESHOLD_PCT = 60       # Below this percentage, only a fraction of the real power will be displayed to the heat pump
excess_mode = True

PIN_S0OUT = 17
#PIN_EXCESS_SWITCH = 3
#PIN_STATUS_LED = 4

SHORTEST_PULSE_S = 2 * MIN_HPULSE_S
LOWER_LIMIT_W = 3600 * 1000 / (LONGEST_PULSE_S * PULSES_PER_KWH)
UPPER_LIMIT_W = 3600 * 1000 / (SHORTEST_PULSE_S * PULSES_PER_KWH)

pulse_s = LONGEST_PULSE_S

MY_REQUEST = {
    'ENERGY': {
        'GUI_BAT_DATA_FUEL_CHARGE': '',     # Remaining battery (percent)
        'GUI_GRID_POW': '',                 # Grid power: negative if exporting, positiv if importing (W)
        'GUI_HOUSE_POW': '',                # House power consumption (W)
        'GUI_INVERTER_POWER': '',           # PV production (W)
    }
}

print("S0-Resolution:" , PULSES_PER_KWH , "Imp/kWh")
print("Longest pulse of", LONGEST_PULSE_S, "s equates to", LOWER_LIMIT_W, "W; highest power is", UPPER_LIMIT_W , "W")
print("Full Power output at" , CHARGE_THRESHOLD_PCT , "% charge level and more.")


api = senec.Senec(SENEC_IP)

pi = pigpio.pi()
pi.set_mode(PIN_S0OUT, pigpio.OUTPUT)


def valueUpdater():
    
    global pulse_s

    solarPower_W = 0.0
    excessPower_W = 0.0
    chargeLvl_pct = 0.0
    limitFactor = 1.0

    ### PERMANENT LOOP ###
    while True:

        valueSet = api.get_values(MY_REQUEST)

        if "error" in valueSet:
            print("FAILED TO RETRIEVE DATA. Slowly reducing assumed values now...")

            # cutting down assumed power values for every missed connection
            excessPower_W *= 0.7
            solarPower_W  *= 0.7

            # slowly decrease assumed charge level by worst case assumption of 100 % drained in one hour
            if chargeLvl_pct > 0:
                chargeLvl_pct -= POLLING_INTERVAL_S / 36;
             
        else:
            chargeLvl_pct =  valueSet['ENERGY']['GUI_BAT_DATA_FUEL_CHARGE']
            excessPower_W = -valueSet['ENERGY']['GUI_GRID_POW']        # Invert, to have excess power and generated power both consistent with positive values
            solarPower_W =   valueSet['ENERGY']['GUI_INVERTER_POWER']

        # Use either full PV power, or only what is fed into the grid
        if excess_mode:
            realPower_W = max(excessPower_W, 0)
        else:
            realPower_W = max(solarPower_W, 0)
        
        # "Hiding" some of the actual power while the battery is rather empty
        if chargeLvl_pct < 0:                       # should never happen, just being overcautious here...
            limitFactor = 0.0
        elif chargeLvl_pct > CHARGE_THRESHOLD_PCT:  # no filtering, battery is full enough
            limitFactor = 1.0
        else:                                       # smooth the transition with a sine-section
            limitFactor = math.sin(chargeLvl_pct * 0.5 * math.pi / CHARGE_THRESHOLD_PCT)**2

        # Trim to S0 specs while applying limit factor
        allowedPower_W = max(realPower_W * limitFactor, LOWER_LIMIT_W)

        # Calculate S0 pulse length
        pulse_s = 3600 * 1000 / PULSES_PER_KWH / allowedPower_W
        
        print("Bat:" , round(chargeLvl_pct,1) , "% \t", "Solar:" , round(solarPower_W) , "W \t" , "to Grid:" , round(excessPower_W) , "W")
        print("Limit factor:", round(limitFactor, 2), " \tPulse duration:", round(pulse_s, 1), "s")

        time.sleep(POLLING_INTERVAL_S)



def pulseGenerator():
    while True:
        pi.write(PIN_S0OUT, 1)
        time.sleep(MIN_HPULSE_S)
        
        pi.write(PIN_S0OUT, 0)
        time.sleep(pulse_s - MIN_HPULSE_S)



threading.Thread(target=valueUpdater).start()
threading.Thread(target=pulseGenerator).start()
