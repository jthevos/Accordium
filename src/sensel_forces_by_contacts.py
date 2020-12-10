import sys
sys.path.append('../sensel-api-master/sensel-lib-wrappers/sensel-lib-python')
import sensel
import binascii
import threading

from pythonosc.udp_client import SimpleUDPClient

enter_pressed = False;
ip = ""
port = 1337

analysis_frame = None

def waitForEnter():
    global enter_pressed
    input("Press Enter to exit...")
    enter_pressed = True
    return

def openSensel():
    """
    Finds the sensel device, if none is detected, return None. This None
    should throw an error in subsequent functions.
    """
    handle = None
    (error, device_list) = sensel.getDeviceList()
    if device_list.num_devices != 0:
        (error, handle) = sensel.openDeviceByID(device_list.devices[0].idx)
    return handle

def initFrame():
    """
    Initializes the sensel to capture all contacts. Returns the initial frame.
    """
    error = sensel.setFrameContent(handle, sensel.FRAME_CONTENT_CONTACTS_MASK)
    (error, frame) = sensel.allocateFrameData(handle)
    error = sensel.startScanning(handle)
    return frame

def scanFrames(frame, info):
    error = sensel.readSensor(handle)
    (error, num_frames) = sensel.getNumAvailableFrames(handle)

    for i in range(num_frames):
        #print(num_frames)

        error = sensel.getFrame(handle, frame)
        printFrame(frame,info)

def printFrame(frame, info):
    """
    Loops through each contact, extracts its data, and sends osc.
    """
    global analysis_frame
    if frame.n_contacts > 0:
        if analysis_frame == None:
            analysis_frame = frame
            # print("analysis_frame: ", analysis_frame.__dir__(),"\n")
            # #print("n_contact: ", analysis_frame.n_contacts.contents.__dir__(),"\n")
            # print("contacts: ", analysis_frame.contacts.contents.__dir__(),"\n")
            # print("accel_data: ", analysis_frame.accel_data.contents.__dir__(),"\n")
            # # print("n_contact: ", analysis_frame.n_contacts.contents,"\n")
            # print("contacts: ", analysis_frame.contacts.contents.content_bit_mask.__dir__(),"\n")
            # print("accel_data: ", analysis_frame.accel_data.contents.__dir__(),"\n")

        #print("\nNum Contacts: ", frame.n_contacts)
        for n in range(frame.n_contacts):
            c = frame.contacts[n]
            #print("Contact ID: ", c.id)
            #print("Contact x, y position: ", c.x_pos, c.y_pos)
            #print("Contact Total Force: ", c.total_force)

            # send osc
            client.send_message("/this/is/a/different/channel", [c.id, c.x_pos, c.y_pos, c.total_force])
            client.send_message("/this/is/a/channel", [c.id, c.x_pos, c.y_pos, c.total_force])

            if c.state == sensel.CONTACT_START:
                sensel.setLEDBrightness(handle, c.id, 100)
            elif c.state == sensel.CONTACT_END:
                sensel.setLEDBrightness(handle, c.id, 0)

def closeSensel(frame):
    error = sensel.freeFrameData(handle, frame)
    error = sensel.stopScanning(handle)
    error = sensel.close(handle)

if __name__ == "__main__":
    #global enter_pressed
    handle = openSensel()
    client = SimpleUDPClient("192.168.1.4", 1337)

    for x in sensel.__dir__():
        print(x)

    print(sensel.getScanDetail(handle))
    print("framerate: ", sensel.getFrame)
    # set scan detail to high
    sensel.setScanDetail(handle, 0)
    #sensel.setMaxFrameRate(handle, 60)
    print(sensel.getScanDetail(handle))
    #print(sensel.getSensorInfo(handle).__dir__())
    print(handle.__dir__())
    if handle != None:
        (error, info) = sensel.getSensorInfo(handle)
        frame = initFrame()

        t = threading.Thread(target=waitForEnter)
        t.start()
        while(enter_pressed == False):
            scanFrames(frame, info)
        closeSensel(frame)
