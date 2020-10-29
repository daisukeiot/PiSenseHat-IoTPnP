# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for
# license information.
# --------------------------------------------------------------------------
import os
import asyncio
import random
import logging
import json
from sense_hat import SenseHat
from azure.iot.device.aio import IoTHubDeviceClient
from azure.iot.device.aio import ProvisioningDeviceClient
from azure.iot.device import constant, Message, MethodResponse
from datetime import date, timedelta, datetime


logging.basicConfig(level=logging.ERROR)
sense = SenseHat()
sense.clear()
sense.set_imu_config(True, True, True)

# This id can change according to the company the user is from
# and the name user wants to call this pnp device
model_id = "dtmi:com:example:sensehat;1"


#####################################################
# COMMAND HANDLERS : User will define these handlers
# depending on what commands the DTMI defines

async def led_text_handler(values):
    if values:
        print(
            "Will show '{typecmd}' on SenseHat LED matrix".format(
                typecmd=values
            )
        )
        sense.show_message(values, text_colour=[0, 255, 0])
    print("Done")

###################################################
# TELEMETRY TASKS

async def send_telemetry_from_thermostat(device_client, telemetry_msg):
    msg = Message(json.dumps(telemetry_msg))
    msg.content_encoding = "utf-8"
    msg.content_type = "application/json"
    print("Sent message")
    await device_client.send_message(msg)

# END TELEMETRY TASKS
#####################################################


#####################################################
# CREATE COMMAND LISTENERS

async def execute_command_listener(
    device_client, method_name, user_command_handler, create_user_response_handler
):
    while True:
        if method_name:
            command_name = method_name
        else:
            command_name = None

        command_request = await device_client.receive_method_request(command_name)
        print("Command request received with payload")
        print(command_request.payload)

        values = {}
        if not command_request.payload:
            print("Payload was empty.")
        else:
            values = command_request.payload

        await user_command_handler(values)

        response_status = 200
        response_payload = create_user_response_handler(values)

        command_response = MethodResponse.create_from_method_request(
            command_request, response_status, response_payload
        )

        try:
            await device_client.send_method_response(command_response)
        except Exception:
            print("responding to the {command} command failed".format(command=method_name))


# END COMMAND LISTENERS
#####################################################
async def execute_property_listener(device_client):
    ignore_keys = ["__t", "$version"]
    while True:
        patch = await device_client.receive_twin_desired_properties_patch()  # blocking call

        print("the data in the desired properties patch was: {}".format(patch))
        print(patch)
        version = patch["$version"]
        prop_dict = {}
        for prop_name, prop_value in patch.items():
            if prop_name in ignore_keys:
                continue
            else:
                prop_dict[prop_name] = {
                    "ac": 200,
                    "ad": "Successfully executed patch",
                    "av": version,
                    "value": prop_value,
                }
        await device_client.patch_twin_reported_properties(prop_dict)

        component_prefix = list(patch.keys())[0]
        values = patch[component_prefix]
        if values == 1:
            sense.show_message("", back_colour=[255, 0, 0])
        elif values == 2:
            sense.show_message("", back_colour=[0, 255, 0])
        elif values == 3:
            sense.show_message("", back_colour=[0, 0, 255])    
        elif values == 4:
            sense.show_message("", back_colour=[255, 255, 255])
        elif values == 5:
            sense.show_message("", back_colour=[255, 255, 0])
        elif values == 6:
            sense.show_message("", back_colour=[148, 0, 211])
        elif values == 7:
            sense.show_message("", back_colour=[0, 255, 255])
        else:
            sense.show_message("", back_colour=[0, 0, 0])
       

async def execute_listener(
    device_client,
    component_name=None,
    method_name=None,
    user_command_handler=None,
    create_user_response_handler=None,
):
    """
    Coroutine for executing listeners. These will listen for command requests.
    They will take in a user provided handler and call the user provided handler
    according to the command request received.
    :param device_client: The device client
    :param component_name: The name of the device like "sensor"
    :param method_name: (optional) The specific method name to listen for. Eg could be "blink", "turnon" etc.
    If not provided the listener will listen for all methods.
    :param user_command_handler: (optional) The user provided handler that needs to be executed after receiving "command requests".
    If not provided nothing will be executed on receiving command.
    :param create_user_response_handler: (optional) The user provided handler that will create a response.
    If not provided a generic response will be created.
    :return:
    """
    while True:
        if component_name and method_name:
            command_name = component_name + "*" + method_name
        elif method_name:
            command_name = method_name
        else:
            command_name = None

        command_request = await device_client.receive_method_request(command_name)
        print("Command request received with payload")
        print(command_request.payload)

        values = pnp_helper.retrieve_values_dict_from_payload(command_request)

        if user_command_handler:
            await user_command_handler(values)
        else:
            print("No handler provided to execute")

        if method_name:
            response_status = 200
        else:
            response_status = 404
        if not create_user_response_handler:
            response_payload = pnp_helper.create_command_response_payload(method_name)
        else:
            response_payload = create_user_response_handler(values)
        command_response = MethodResponse.create_from_method_request(
            command_request, response_status, response_payload
        )

        try:
            await device_client.send_method_response(command_response)
        except Exception:
            print("responding to the {command} command failed".format(command=method_name))

#####################################################
# CREATE RESPONSES TO COMMANDS

def create_led_text_report_response(values):
    response = {"result": True, "data": "show text succeeded"}
    return response

####################################################
# An # END KEYBOARD INPUT LISTENER to quit application
def stdin_listener():
    """
    Listener for quitting the sample
    """
    while True:
        selection = input("Press Q to quit\n")
        if selection == "Q" or selection == "q":
            print("Quitting...")
            break

# END KEYBOARD INPUT LISTENER
#####################################################
def change_led():
    print("***")

#####################################################
# MAIN STARTS
async def provision_device(provisioning_host, id_scope, registration_id, symmetric_key, model_id):
    provisioning_device_client = ProvisioningDeviceClient.create_from_symmetric_key(
        provisioning_host=provisioning_host,
        registration_id=registration_id,
        id_scope=id_scope,
        symmetric_key=symmetric_key,
    )
    provisioning_device_client.provisioning_payload = {"modelId": model_id}
    return await provisioning_device_client.register()


async def main():
    switch = os.getenv("IOTHUB_DEVICE_SECURITY_TYPE")
    if switch == "DPS":
        provisioning_host = os.getenv("IOTHUB_DEVICE_DPS_ENDPOINT")
        id_scope = os.getenv("IOTHUB_DEVICE_DPS_ID_SCOPE")
        registration_id = os.getenv("IOTHUB_DEVICE_DPS_DEVICE_ID")
        symmetric_key = os.getenv("IOTHUB_DEVICE_DPS_DEVICE_KEY")

        registration_result = await provision_device(
            provisioning_host, id_scope, registration_id, symmetric_key, model_id
        )

        if registration_result.status == "assigned":
            device_client = IoTHubDeviceClient.create_from_symmetric_key(
                symmetric_key=symmetric_key,
                hostname=registration_result.registration_state.assigned_hub,
                device_id=registration_result.registration_state.device_id,
                product_info=model_id
            )
        else:
            raise RuntimeError("Could not provision device. Aborting PNP device connection.")
    else:
        conn_str = os.getenv("IOTHUB_DEVICE_CONNECTION_STRING")
        print("Connecting using Connection String " + conn_str)
        device_client = IoTHubDeviceClient.create_from_connection_string(
            conn_str, product_info=model_id
        )

    # Connect the client.
    await device_client.connect()

    ################################################
    # Register callback and Handle command (reboot)
    print("Listening for command requests and property updates")

    listeners = asyncio.gather(
        execute_command_listener(
            device_client,
            method_name="show_text",
            user_command_handler=led_text_handler,
            create_user_response_handler=create_led_text_report_response,
        ),
        execute_property_listener(device_client)  
    )



    ################################################
    # Send telemetry 

    async def send_telemetry():
        print("Sending telemetry for SenseHat")

        while True:
            temperature_hts221 = sense.get_temperature() 
            humidity = sense.get_humidity()
            temperature_lps25h = ((sense.get_temperature_from_pressure()/5)*9)+32
            pressure = sense.get_pressure()
            orientation_rad = sense.get_orientation_radians()
            lsm9ds1_accelerometer = sense.get_accelerometer_raw()
            lsm9ds1_gyroscope = sense.get_gyroscope_raw()
            lsm9ds1_compass = sense.get_compass_raw()  
            imu_yaw = orientation_rad['yaw']
            imu_roll = orientation_rad['roll']
            imu_pitch = orientation_rad['pitch']
            lsm9ds1_compass_x = lsm9ds1_compass['x']
            lsm9ds1_compass_y = lsm9ds1_compass['y']
            lsm9ds1_compass_z = lsm9ds1_compass['z']
            lsm9ds1_gyroscope_x = lsm9ds1_gyroscope['x']
            lsm9ds1_gyroscope_y = lsm9ds1_gyroscope['y']
            lsm9ds1_gyroscope_z = lsm9ds1_gyroscope['z']
            lsm9ds1_accelerometer_x = lsm9ds1_accelerometer['x']
            lsm9ds1_accelerometer_y = lsm9ds1_accelerometer['y']
            lsm9ds1_accelerometer_z = lsm9ds1_accelerometer['z']
#           temperature_msg1 = {"temperature_hts221": temperature_hts221,"humidity": humidity,"temperature_lps25h": temperature_lps25h,"pressure": pressure,"imu": orientation_rad,"lsm9ds1_accelerometer": lsm9ds1_accelerometer,"lsm9ds1_gyroscope": lsm9ds1_gyroscope,"lsm9ds1_compass": lsm9ds1_compass}
            temperature_msg1 = {"temperature_hts221": temperature_hts221,"humidity": humidity,"temperature_lps25h": temperature_lps25h,"pressure": pressure,"imu_yaw": imu_yaw,"imu_roll": imu_roll,"imu_pitch": imu_pitch,"lsm9ds1_accelerometer_x": lsm9ds1_accelerometer_x,"lsm9ds1_accelerometer_y": lsm9ds1_accelerometer_y,"lsm9ds1_accelerometer_z": lsm9ds1_accelerometer_z,"lsm9ds1_gyroscope_x": lsm9ds1_gyroscope_x,"lsm9ds1_gyroscope_y": lsm9ds1_gyroscope_y,"lsm9ds1_gyroscope_z": lsm9ds1_gyroscope_z,"lsm9ds1_compass_x": lsm9ds1_compass_x,"lsm9ds1_compass_y": lsm9ds1_compass_y,"lsm9ds1_compass_z": lsm9ds1_compass_z}
            await send_telemetry_from_thermostat(device_client, temperature_msg1)
            await device_client.patch_twin_reported_properties({"manufacturer": "Pi Fundation"})
            await asyncio.sleep(8)

    send_telemetry_task = asyncio.create_task(send_telemetry())

    # Run the stdin listener in the event loop
    loop = asyncio.get_running_loop()
    user_finished = loop.run_in_executor(None, stdin_listener)
    # # Wait for user to indicate they are done listening for method calls
    await user_finished

    if not listeners.done():
        listeners.set_result("DONE")

    listeners.cancel()

    send_telemetry_task.cancel()

    # finally, disconnect
    await device_client.disconnect()


#####################################################
# EXECUTE MAIN

if __name__ == "__main__":
    asyncio.run(main())

    # If using Python 3.6 or below, use the following code instead of asyncio.run(main()):
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(main())
    # loop.close()
