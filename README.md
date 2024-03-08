# 5G-NTN-simulator

## Overview

This project implements a 5G NTN simulation platform. Driven by real ephemeris information, the platform calculates satellite positions in real time to determine topological connectivity and delay information; it deploys a routing learning algorithm that can automatically learn global routing information on a regular basis.

The platform uses containers to represent satellites or ground stations, and supports user-defined deployment of software-based base stations or MEC and other 5G services. In addition, we have deployed video end-to-end services on the ue side.

## Usage

- Start NTN platform:

  In the main method in the system.py file, modify **flag=1** and run system.py to start the NTN platform. Enter the Groundstation-ue container use ``` ping -I uesimtun0 baidu.com ```  If you can receive a return packet, it means that the NTN platform is running normally.

- Stop NTN platform:

  In the main method in the system.py file, modify **flag=0** and run system.py to stop the NTN platform.

- Video end-to-end testing:

  We use webrtc technology to deploy end-to-end video services in ue .

  The project code used is (https://github.com/Dirvann/mediasoup-sfu-webrtc-video-rooms)

  run ``` npm install ``` & ``` npm run ``` to open the webrtc server. open ```xxx (IP address of the webrtc server):3016``` at firefox browser that opens when ue is started. Enter the room number and user name to simulate a multi-UE video call.



## Note

1.The image **firefox-ue**、**gnb_ntn3** and **core_ntn3** used in system.py needs to be downloaded (), where the firefox-ue image is the image in which we independently wrote the dockerfile (We also provide the dockerfile above) to combine ue with the firefox browser to support the video end-to-end deployment experiment. 

If you do not deploy end-to-end video services, it is enough to use the **ue_ntn3** image.

2.In order to simulate all data flowing through the 5G core network, you need to use the following command to modify the routing rules in ue:

``` ip route add xxx (ip address of webrtc server) dev uesimtun0```

## Demo










