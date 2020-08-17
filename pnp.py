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

# The device "TemperatureController" that is getting implemented using the above interfaces.
# This id can change according to the company the user is from
# and the name user wants to call this pnp device
model_id = "dtmi:com:example:sensehat;1"


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

#####################################################
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

    async def execute_property_listener():
        ignore_keys = ["__t", "$version"]
        while True:
            patch = await device_client.receive_twin_desired_properties_patch()  # blocking call
            print("the data in the desired properties patch was: {}".format(patch))

            component_prefix = list(patch.keys())[0]
            values = patch[component_prefix]
            print("previous values")
            print(values)

            version = patch["$version"]
            inner_dict = {}

            for prop_name, prop_value in values.items():
                if prop_name in ignore_keys:
                    continue
                else:
                    inner_dict["ac"] = 200
                    inner_dict["ad"] = "Successfully executed patch"
                    inner_dict["av"] = version
                    inner_dict["value"] = prop_value
                    values[prop_name] = inner_dict

            iotin_dict = dict()
            if component_prefix:
                iotin_dict[component_prefix] = values
                # print(iotin_dict)
            else:
                iotin_dict = values

            await device_client.patch_twin_reported_properties(iotin_dict)

    ################################################
    # Send telemetry (current temperature)

    async def send_telemetry():
        print("Sending telemetry for SenseHat")

        while True:
            currentTemp = sense.get_temperature() # Current temperature in Celsius
            humidity = sense.get_humidity()
            currentTemp_2 = ((sense.get_temperature_from_pressure()/5)*9)+32
            pressure = sense.get_pressure()
            orientation_rad = sense.get_orientation_radians()

            temperature_msg1 = {"temperature": currentTemp,"humidity": humidity,"temperature_LPS25H": currentTemp_2,"pressure": pressure,"IMU": orientation_rad}
            await send_telemetry_from_thermostat(device_client, temperature_msg1)
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
