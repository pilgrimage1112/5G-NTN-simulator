from skyfield.api import load, wgs84
import skyfield.positionlib as pos
import math
import os
import socket
from enum import Enum
import time
from datetime import datetime, timezone
import subprocess

from typing import Dict


def do_cmd(cmd):
    print(cmd)
    # print("going to execute cmd: [{}]".format(cmd))
    # time.sleep(0.5)
    os.system(cmd)


class Container:
    def __init__(self, container_name, index=0):
        self.container_name = container_name
        self.index = index
        self.eth1 = {}
        self.eth_dict = {}
        self.use = {}

    def add_eth1_filter(self, ip_str, delay):  # ip-str delay-float
        self.index += 1
        true_index = 0
        if self.index < 17:
            true_index = self.index
        else:
            for i in range(1, 17):
                if self.use[i] == 0:
                    true_index = i
                    break
            if true_index == 0:
                print("OUT OF RANGE!!!")
                return
        self.use[true_index] = 1
        ip = int.from_bytes(socket.inet_aton(ip_str), byteorder='big')
        self.eth1[ip] = {'delay': delay, 'index': true_index}
        if self.index == 1:
            cmd = "docker exec -id " + self.container_name + " tc qdisc add dev eth1 root handle 1: prio"
            do_cmd(cmd)
        elif self.index >= 4:
            cmd = "docker exec -id " + self.container_name + " tc qdisc change dev eth1 root handle 1: prio bands 16"
            do_cmd(cmd)
        cmd = "docker exec -id " + self.container_name + " tc filter add dev eth1 protocol ip parent 1: prio 1 u32 match ip dst " + ip_str + " flowid 1:" + str(
            true_index)
        do_cmd(cmd)
        cmd = "docker exec -id " + self.container_name + " tc qdisc add dev eth1 parent 1:" + str(
            true_index) + " netem delay " + str(delay) + "s"
        do_cmd(cmd)

    def modify_eth1_filter(self, ip_str, delay):  # ip-str delay-float
        ip = int.from_bytes(socket.inet_aton(ip_str), byteorder='big')
        i = self.eth1[ip]['index']
        self.eth1[ip]['delay'] = delay
        cmd = "docker exec -id " + self.container_name + " tc qdisc change dev eth1 parent 1:" + str(
            i) + " netem delay " + str(delay) + "s"
        do_cmd(cmd)

    def remove_eth1_delay(self, ip_str):  # ip-str delay-float
        ip = int.from_bytes(socket.inet_aton(ip_str), byteorder='big')
        if ip not in self.eth1:
            error = "Error! " + self.container_name + " eth1 has no filter to " + ip_str + " !"
            print(error)
            return
        i = self.eth1[ip]['index']
        self.use[i] = 0
        del self.eth1[ip]
        cmd = "docker exec -id " + self.container_name + " tc filter del dev eth1 protocol ip parent 1: prio 1 u32 match ip dst " + ip_str + " flowid 1:" + str(i)
        do_cmd(cmd)
        cmd = "docker exec -id " + self.container_name + " tc qdisc del dev eth1 parent 1:" + str(i)
        do_cmd(cmd)

    def add_eth1_delay(self, ip_str, delay):
        ip = int.from_bytes(socket.inet_aton(ip_str), byteorder='big')
        if ip in self.eth1:
            self.modify_eth1_filter(ip_str, delay)
        else:
            self.add_eth1_filter(ip_str, delay)

    def add_eth_delay(self, eth_name, delay):  # eth_name-str  delay-float
        self.eth_dict[eth_name] = delay
        cmd = "docker exec -id " + self.container_name + " tc qdisc add dev " + eth_name + " root netem delay " + str(
            delay) + "s"
        do_cmd(cmd)

    def modify_eth_delay(self, eth_name, delay):
        self.eth_dict[eth_name] = delay
        cmd = "docker exec -id " + self.container_name + " tc qdisc change dev " + eth_name + "root netem delay " + str(
            delay) + "s"
        do_cmd(cmd)

    def remove_eth_delay(self, eth_name):
        del self.eth_dict[eth_name]
        cmd = "docker exec -id " + self.container_name + "tc qdisc del dev " + eth_name + " root netem"
        do_cmd(cmd)

    def add_delay(self, eth_name, delay):
        if eth_name in self.eth_dict:
            self.modify_eth_delay(eth_name, delay)
        else:
            self.add_eth_delay(eth_name, delay)

    def delete_delay(self, eth_name):
        if eth_name not in self.eth_dict:
            error = "Error!" + self.container_name + " " + eth_name + " has no delay!"
            print(error)
            return
        self.remove_eth_delay(eth_name)


container_dict = {}


class NodeType(Enum):
    Ground = 0
    Up = 1
    Down = 2
    Left = 3
    Right = 4


class DockerInterface:
    # subnet = 17
    core_subnet = 1  # 172.18.1.0/24
    gnb_subnet = 4846  # 172.(gnb_subnet // 255).(gnb_subnet % 255).0/24
    ue_subnet = 2  # 172.18.ue_subnet.0/24

    @staticmethod
    def create_container(name, image_name):
        if image_name == "firefox-ue":
            cmd = "docker run -itd --name " + name + " --shm-size=384m -e DISPLAY=$DISPLAY --device /dev/snd/controlC0 \
            --device /dev/snd/pcmC0D0p --device /dev/snd/timer --device /dev/video0  --device /dev/video1 \
            --device /dev/video2 --device /dev/video3 -v /tmp/.X11-unix:/tmp/.X11-unix -v $XAUTHORITY:/tmp/.host_Xauthority:ro -dti \
            --cap-add NET_ADMIN --device=/dev/net/tun firefox-ue"
            do_cmd(cmd)
        else:
            cmd = "docker run -itd --name=" + name + " --cap-add NET_ADMIN --device=/dev/net/tun " + image_name
            do_cmd(cmd)

    @staticmethod
    def remove_container(name):
        cmd_stop = "docker stop " + name
        cmd_rm = "docker rm " + name
        do_cmd(cmd_stop)
        do_cmd(cmd_rm)

    @staticmethod
    def config_container(name, script):
        cmd = "docker exec -id " + name + " " + script
        do_cmd(cmd)

    @staticmethod
    def create_bridge(name, subnet):
        if subnet != "":
            cmd = "docker network create " + "--subnet=" + subnet + " " + name
        else:
            cmd = "docker network create " + name
        do_cmd(cmd)

    @staticmethod
    def connect_bridge(bridge, container):
        cmd = "docker network connect " + bridge + " " + container
        do_cmd(cmd)
        # time.sleep(0.5)

    @staticmethod
    def disconnect_bridge(bridge, container):
        cmd = "docker network disconnect " + bridge + " " + container
        do_cmd(cmd)

    @staticmethod
    def remove_bridge(bridge):
        cmd = "docker network rm " + bridge
        do_cmd(cmd)

    @staticmethod
    def get_subnet_no(typ):
        # """
        result = DockerInterface.gnb_subnet // 255, DockerInterface.gnb_subnet % 255
        if typ == "core":
            result = 18, DockerInterface.core_subnet
        elif typ == "ue":
            result = 18, DockerInterface.ue_subnet
            DockerInterface.ue_subnet = DockerInterface.ue_subnet + 1
            if DockerInterface.ue_subnet > 255:
                print("error! ue_subnet out of index!")
        else:
            DockerInterface.gnb_subnet = DockerInterface.gnb_subnet + 1
        return result

        # """
        # DockerInterface.subnet = DockerInterface.subnet + 1
        # return DockerInterface.subnet, 0
        # """

    @staticmethod
    def del_des_route(des, name):
        cmd = "docker exec -id " + name + " ip route del " + des
        do_cmd(cmd)


class GroundStation:
    def __init__(self, name, loc, typ):
        self.name = name
        self.loc = loc
        self.typ = typ  # ue or core


class Node:
    def __init__(self, name, typ):
        self.name = name
        self.neighbor = dict()
        self.bridgeName = ""
        self.subnet = ""
        self.typ = typ  # ue or core or gnb

    def network_init(self):
        self.bridgeName = "b" + self.name
        subnet_no = DockerInterface.get_subnet_no(self.typ)
        self.subnet = "172.{0}.{1}.0/24".format(str(subnet_no[0]), str(subnet_no[1]))
        DockerInterface.create_bridge(self.bridgeName, self.subnet)
        DockerInterface.connect_bridge(self.bridgeName, self.name)

    def add_neighbor(self, node, type=NodeType.Ground):
        neighborNode = NodeInfo(node, type)
        if not self.neighbor.get(node.name):
            self.neighbor.update({node.name: neighborNode})

    # def add_all_neighbors(self,node_list):
    #     if len(node_list) !=4:
    #         print("error! no enough neighbor for node "+self.name)
    #         return
    #     for i in range(4):
    #         neighborNode = nodeInfo(node_list[i])

    def del_neighbor(self, node_name):
        node = self.neighbor.get(node_name)
        if node is None:
            print("no node {} to del".format(node_name))
        else:
            if node.isConnected:
                num = node.node.subnet.split('.')
                mask = num[0] + '.' + num[1] + '.' + num[2] + '.255'
                cmd = "docker exec " + node_name + " ifconfig | grep -B 1 " + mask + " | head -n 1 | awk -F: '{print $1}'"
                eth_name = subprocess.getstatusoutput(cmd)[1]
                cmd = "docker exec " + node_name + " ifconfig | grep " + mask + " | awk '{print $2}'"
                ip_str = subprocess.getstatusoutput(cmd)[1]
                container_dict[node_name].delete_delay(eth_name)
                container_dict[self.name].remove_eth1_delay(ip_str)
                DockerInterface.disconnect_bridge(self.bridgeName, node.node.name)
            self.neighbor.pop(node_name)

    def connect_special_neighbors(self):
        for node in self.neighbor.values():
            if node.type in [NodeType.Ground, NodeType.Up, NodeType.Left]:
                if not node.isConnected:
                    DockerInterface.del_des_route(self.subnet, node.node.name)
                    DockerInterface.connect_bridge(self.bridgeName, node.node.name)
                    node.connect()

    def connect_all_neighbors(self):
        for node in self.neighbor.values():
            DockerInterface.connect_bridge(self.bridgeName, node.node.name)
            node.connect()


class NodeInfo:
    def __init__(self, node, type=NodeType.Ground):
        self.node = node
        self.isConnected = False
        self.type = type

    def connect(self):
        if self.isConnected:
            print("error! node {} has been connected".format(self.node.name))
        self.isConnected = True


class SatelliteSystem:
    def __init__(self, url, gs_position, use_real_data):
        self.from_real = use_real_data  # 是否是真实数据
        self.tle_url = url if use_real_data else 'three.tle'
        self.satellites = None
        self.satellites_name_dict = None
        self.satellites_num_dict = None
        self.gs_position = gs_position
        self.gss = None
        self.gs_list = []
        self.orbit_num = None
        self.orbit_satellite = None
        self.docker_list = None
        self.satellite_num_orbit = None
        self.sim_start_time = time.time()
        self.time_acceleration = 50
        self.node_dict = dict()
        self.init()
        self.run()

    def init(self):
        """
        description: 初始化卫星和地面站信息
        :return: None
        """
        utc_time = datetime.utcfromtimestamp(self.sim_start_time).replace(tzinfo=timezone.utc)
        ts = load.timescale()
        t = ts.utc(utc_time)
        self.satellites = self.load_tle(self.tle_url)
        self.satellites_name_dict = {sat.name: sat for sat in self.satellites}
        self.satellites_num_dict = {sat.model.satnum: sat for sat in self.satellites}
        # build for gs_list
        self.gss = self.create_gs(self.gs_position)
        for i, gs in enumerate(self.gss):
            typ = "core" if i == 0 else "ue"
            self.gs_list.append(GroundStation("GroundStation-" + typ + str(i), gs, typ))
        self.node_dict = {sat.name: Node(sat.name, "gnb") for sat in self.satellites}
        self.node_dict.update({gs.name: Node(gs.name, gs.typ) for gs in self.gs_list})

        self.clean_orbits(t)
        self.node_init(t)
        return

    def node_init(self, t):
        self.create_all_containers()
        for node in self.node_dict.values():
            node.network_init()

        for node in self.node_dict.values():
            neighbours = self.get_neighbour_satellite(node.name)
            direction = [NodeType.Up, NodeType.Down, NodeType.Left, NodeType.Right]
            if neighbours is not None:
                for i in range(len(neighbours)):
                    node.add_neighbor(self.node_dict.get(neighbours[i]), direction[i])
                gs_list = self.get_connect_gs(node.name, t)
                for gs in gs_list:
                    node.add_neighbor(self.node_dict.get(gs.name))
                node.connect_special_neighbors()
                for nd in node.neighbor.values():
                    if nd.type in [NodeType.Ground, NodeType.Up, NodeType.Left]:
                        delay = 0
                        if nd.type in [NodeType.Up, NodeType.Left]:
                            delay = self.get_interlink_delay(node.name, nd.node.name, t)
                        elif nd.type == NodeType.Ground:
                            gs_new = None
                            for gs_ in self.gs_list:
                                if gs_.name == nd.node.name:
                                    gs_new = gs_
                            delay = self.get_sat_earth_link_delay(node.name, gs_new, t)
                        docker2 = node.name
                        docker1 = nd.node.name
                        num = node.subnet.split('.')
                        mask = num[0] + '.' + num[1] + '.' + num[2] + '.255'
                        # cmd = "bash test.sh " + docker1 + ' ' + mask + ' ' + docker2 + ' ' + str(delay) + 's'
                        cmd = "docker exec " + docker1 + " ifconfig | grep -B 1 " + mask + " | head -n 1 | awk -F: '{print $1}'"
                        eth_name = subprocess.getstatusoutput(cmd)[1]
                        cmd = "docker exec " + docker1 + " ifconfig | grep " + mask + " | awk '{print $2}'"
                        ip_str = subprocess.getstatusoutput(cmd)[1]
                        # print(eth_name, ip_str)
                        container_dict[docker2].add_eth1_delay(ip_str, delay)
                        container_dict[docker1].add_eth_delay(eth_name, delay)

        DockerInterface.config_container("GroundStation-core0", "./start.sh")
        time.sleep(15)
        for node in self.node_dict.values():
            if node.name != "GroundStation-core0":
                DockerInterface.config_container(node.name, "./start.sh")
                time.sleep(2)

    @staticmethod
    def load_tle(url):
        """
        description: 从tle文件获取整体卫星运行数据
        :param url: tle文件的url
        :return: tle中包含的所有卫星的列表
        """
        satellites = load.tle_file(url)
        return satellites

    @staticmethod
    def create_gs(positions):
        """
        description: 创建地面站
        :param positions: 地面站经纬度的二维列表，由多个一维列表组成，列表中第一个元素是纬度，第二个元素是经度
        :return: 用wgs84.latlon()构建的地面站列表
        """
        gss = []
        for position in positions:
            gs = wgs84.latlon(
                latitude_degrees=position[0],
                longitude_degrees=position[1],
                elevation_m=0
            )
            gss.append(gs)
        return gss

    def get_satellite_info(self, t, num=None, name=None):
        """
        description: 获取某颗卫星信息
        :param t: 时间
        :param num: 某颗卫星的编号
        :param name: 某颗卫星的名字
        :return: 信息字典
        """
        if num is not None:
            sat = self.satellites_num_dict[num]
        elif name is not None:
            sat = self.satellites_name_dict[name]
        else:
            return None
        info = {
            "name": sat.name,
            "inclination": sat.model.inclo,
            "sat_num": sat.model.satnum,
            "orbit_period": 1.0 / sat.model.no,
            "mean_motion": sat.model.no,
            "position": sat.at(t).position.km,
            "v": sat.at(t).velocity.km_per_s
        }
        return info

    def get_all_satellites_info(self, t):
        """
        获取全部卫星信息
        :param t: 时间
        :return: 所有卫星的信息列表
        """
        infos = []
        for sat in self.satellites:
            info = {
                "name": sat.name,
                "inclination": sat.model.inclo,
                "sat_num": sat.model.satnum,
                "orbit_period": 1.0 / sat.model.no,
                "mean_motion": sat.model.no,
                "position": sat.at(t).position.km,
                "v": sat.at(t).velocity.km_per_s,
                "sat": sat
            }
            infos.append(info)
        return infos

    def get_distance_2satellites(self, sat1_name, sat2_name, t):
        """
        description: 获取两颗卫星之间距离
        :param sat1_name: 卫星1名字
        :param sat2_name: 卫星2名字
        :param t: 时间
        :return: 两颗卫星之间距离
        """
        sat1 = self.satellites_name_dict[sat1_name]
        sat2 = self.satellites_name_dict[sat2_name]
        position_sat1 = sat1.at(t)
        position_sat2 = sat2.at(t)
        distance = position_sat1.distance().km - position_sat2.distance().km
        distance_abs = abs(distance)
        return distance_abs

    def get_interlink_delay(self, sat1_name, sat2_name, t):
        distance = self.get_distance_2satellites(sat1_name, sat2_name, t)
        light_vel = 3e5
        return distance / light_vel

    def get_distance_sat_gs(self, sat_name, gs, t):
        sat = self.satellites_name_dict[sat_name]
        difference = sat - gs.loc
        difference = difference.at(t)
        _, _, distance = difference.altaz()
        return distance.km

    def get_sat_earth_link_delay(self, sat_name, gs, t):
        distance = self.get_distance_sat_gs(sat_name, gs, t)
        light_vel = 3e5
        return distance / light_vel

    def get_neighbour_satellite(self, name):
        """
        获取四颗相邻卫星名
        :param name: 查询卫星名
        :return: 相邻卫星名列表
        """
        result = {
            "up": None,
            "down": None,
            "left": None,
            "right": None
        }

        # 获取当前卫星轨道编号和index
        index = self.get_orbit(name)
        if index[0] < 0:
            return
        up_index = [index[0], index[1] - 1] if index[1] - 1 >= 0 else [index[0], self.satellite_num_orbit - 1]
        down_index = [index[0], index[1] + 1] if index[1] + 1 < self.satellite_num_orbit else [index[0], 0]
        left_index = [index[0] - 1, index[1]] if index[0] - 1 >= 0 else [self.orbit_num - 1, index[1]]
        right_index = [index[0] + 1, index[1]] if index[0] + 1 < self.orbit_num else [0, index[1]]
        result["up"] = self.orbit_satellite[up_index[0]][up_index[1]]
        result["down"] = self.orbit_satellite[down_index[0]][down_index[1]]
        result["left"] = self.orbit_satellite[left_index[0]][left_index[1]]

        result["right"] = self.orbit_satellite[right_index[0]][right_index[1]]

        if self.from_real:
            # 同轨道卫星距离计算
            ts = load.timescale()
            t = ts.utc(2023, 10, 11)
            distance_same_orbit = {}
            for sat in self.orbit_satellite[index[0]]:
                if sat == name:
                    continue
                distance_same_orbit[sat] = self.get_distance_2satellites(name, sat, t)
            sorted_distance_same_orbit = sorted(distance_same_orbit.items(), key=lambda x: x[1])

            # 前后两颗卫星名添加至结果，不严谨
            result['up'] = sorted_distance_same_orbit[0][0]
            result['down'] = sorted_distance_same_orbit[1][0]

            # 获取相邻轨道index
            neighbour_orbits = [index[0] - 1, index[0] + 1]
            if index[0] == 0:
                neighbour_orbits[0] = self.orbit_num - 1
            elif index[0] == self.orbit_num - 1:
                neighbour_orbits[1] = 0

            # 使用距离计算不同轨道的相邻卫星
            left_right = ['left', 'right']
            for i in range(2):
                distance_orbit = {}
                for sat in self.orbit_satellite[neighbour_orbits[i]]:
                    distance_orbit[sat] = self.get_distance_2satellites(name, sat, t)
                sorted_distance_orbit = sorted(distance_orbit.items(), key=lambda x: x[1])
                result[left_right[i]] = sorted_distance_orbit[0][0]

        return [result["up"], result["down"], result["left"], result["right"]]

    def update_node_neighbor(self, sat_name, t):
        """
        更新当前卫星节点的邻居信息，即更新地面站与卫星节点的连接关系
        :param sat_name:
        :param t:
        :return:
        """
        node = self.node_dict.get(sat_name)
        if not node:
            print("error! The input satellite name is not existed!")
        gs_list = self.get_connect_gs(sat_name, t)
        gs_name_list = [node.name for node in gs_list]
        del_node_list = []

        for neighbor in node.neighbor:
            if node.neighbor[neighbor].type == NodeType.Ground:
                # 如果当前邻居节点不在当前时间点观测到的地面站列表中，则删除
                if neighbor not in gs_name_list:
                    del_node_list.append(neighbor)

        for del_node in del_node_list:
            node.del_neighbor(del_node)

        for gs in gs_list:
            node.add_neighbor(self.node_dict[gs.name])

        node.connect_special_neighbors()
        return

    def get_connect_gs(self, name, t):
        """
        获取卫星可以连接到的地面站列表
        :param t: load.timescale().utc(xxx)
        :param name: 卫星名
        :return: 地面站列表
        """
        gss_connected = []
        for gs in self.gs_list:
            if self.is_connect_gs(name, gs, t):
                gss_connected.append(gs)

        return gss_connected

    def is_connect_gs(self, name, gs, t):
        """
        检查卫星是否连接到地面站
        :param name: 卫星名
        :param gs: 地面站
        :param t: 时间
        :return: 卫星是否可以链接到当前地面站
        """
        sat = self.satellites_name_dict[name]
        difference = sat - gs.loc
        alt_degree, _, _ = difference.at(t).altaz()
        if float(alt_degree.degrees) >= -40:
            return True
        else:
            return False

    # def is_connect_gs(self, name, gs, t):
    #     """
    #     检查卫星是否连接到地面站
    #     :param name: 卫星名
    #     :param gs: 地面站
    #     :param t: 时间
    #     :return: 卫星是否可以链接到当前地面站
    #     """
    #     sat = self.satellites_name_dict[name]
    #     difference = sat - gs
    #     alt_degree = gs.at(t).separation_from(sat.at(t)).degrees
    #     # alt_degree, _, _ = difference.at(t).altaz()
    #     if abs(alt_degree) < 5.2:  # 根据三角关系计算 地球半径6370km,轨道高度550km，最小仰角40°
    #         return True
    #     else:
    #         return False

    def get_orbit(self, name):
        """
        获取卫星轨道编号和在轨道中的index
        :param name: 卫星名
        :return: 卫星轨道编号, 卫星在轨道中的index
        """
        index = -1, -1
        flag = False
        for orbit_ind in range(self.orbit_num):
            sat_ind = 0
            for sat in self.orbit_satellite[orbit_ind]:
                if name == sat:
                    index = orbit_ind, sat_ind
                    flag = True
                    break
                else:
                    sat_ind += 1
            if flag:
                break
        return index

    def get_satellite_num(self, ind):
        """
        获取某一轨道的卫星数量
        :param ind: 轨道编号
        :return: 轨道卫星数量
        """
        return len(self.orbit_satellite[ind])

    def get_position(self, name, t):
        """
        获取卫星位置
        :param name: 卫星名
        :param t: 当前时间
        :return: [x, y, z]位置坐标，以地心为中心
        """
        return self.satellites_name_dict[name].at(t).position.km

    # 整理所有轨道
    def clean_orbits(self, t):
        """
        轨道高度 + 轨道倾角 + 升交点的赤经
        二维列表[[卫星1名，卫星2名...]=>一个轨道, [卫星1名]]
        :return: None
        """
        focus_satellites = []
        focus_sat_dict = {}
        for sat in self.satellites:
            geocentric = sat.at(t)
            if self.from_real:
                height = wgs84.height_of(geocentric).km
                incli = sat.model.inclo * 180 / math.pi
                if height < 490 or incli < 53.15 or incli > 53.22:
                    continue
            focus_satellites.append(sat)
            focus_sat_dict[sat.name] = sat.model.nodeo * 180 / math.pi

        # 卫星按照升交点赤经排序
        sorted_focus_satellites = sorted(focus_sat_dict.items(), key=lambda x: x[1])

        clean_satellites = []
        current_degree = 0
        current_list = []
        for sat in sorted_focus_satellites:
            degree = sat[1]
            name = sat[0]
            if degree - current_degree < 2:
                current_list.append(name)
            else:
                clean_satellites.append(current_list)
                current_list = [name]
            current_degree = degree
        if self.from_real:
            for name in clean_satellites[0]:
                current_list.append(name)
            clean_satellites.append(current_list)
            clean_satellites.pop(0)
        else:
            clean_satellites.append(current_list)

        self.orbit_satellite = clean_satellites
        self.orbit_num = len(self.orbit_satellite)
        self.satellite_num_orbit = len(self.orbit_satellite[0])
        return

    # @staticmethod
    # def create_links(self,name1,name2):
    #

    def create_all_containers(self):
        for sat in self.satellites:
            DockerInterface.create_container(sat.name, "gnb_ntn3")
            container_dict[sat.name] = Container(sat.name)
        for i, gs in enumerate(self.gs_list):
            if gs.typ == "ue":
                DockerInterface.create_container(gs.name, "firefox-ue")
                container_dict[gs.name] = Container(gs.name)
            else:
                DockerInterface.create_container(gs.name, gs.typ + "_ntn3")
                container_dict[gs.name] = Container(gs.name)

    #     ## create links
    #     for sat in self.satellites:
    #         neighbours = self.get_neighbour_satellite(sat.name)
    #         DockerInterface.create_bridge("b" + sat.name, "127.0.0.1")
    #         DockerInterface.connect_bridge("b" + sat.name, sat.name)
    #         DockerInterface.connect_bridge("b" + sat.name, neighbours[0])
    #         DockerInterface.connect_bridge("b" + sat.name, neighbours[2])
    #         gs_list = self.get_connect_gs(sat.name)
    #         for gs in gs_list:
    #             DockerInterface.connect_bridge("b" + sat.name, gs.name)

    def remove(self):
        for sat in self.satellites:
            DockerInterface.remove_container(sat.name)
        for gs in self.gs_list:
            DockerInterface.remove_container(gs.name)
        for sat in self.satellites:
            DockerInterface.remove_bridge("b" + sat.name)
        for gs in self.gs_list:
            DockerInterface.remove_bridge("b" + gs.name)

    def set_routes(self):
        for gs in self.gs_list:
            print(gs.name)

    def run(self):
        current_real_time_init = time.time()
        elapsed_real_time_init = current_real_time_init - self.sim_start_time
        simulated_time_init = self.sim_start_time + elapsed_real_time_init * self.time_acceleration
        utc_time_init = datetime.utcfromtimestamp(simulated_time_init).replace(tzinfo=timezone.utc)
        ts_init = load.timescale()
        t_init = ts_init.utc(utc_time_init)
        for sat in self.satellites:
            self.update_node_neighbor(sat.name, t_init)
        while True:
            current_real_time = time.time()
            elapsed_real_time = current_real_time - self.sim_start_time
            simulated_time = self.sim_start_time + elapsed_real_time * self.time_acceleration
            utc_time = datetime.utcfromtimestamp(simulated_time).replace(tzinfo=timezone.utc)
            ts = load.timescale()
            t = ts.utc(utc_time)
            test_t = time.time()
            for sat in self.satellites:
                self.update_node_neighbor(sat.name, t)
            print(time.time() - test_t)
            time.sleep(5 - (time.time() - current_real_time))
            core = None
            for gs in self.gs_list:
                if gs.name == "GroundStation-core0":
                    core = gs
            for sat in self.satellites:
                if self.is_connect_gs(sat.name, core, t):
                    print("{}".format(sat.name), end=" ")
            print("\n")
            # print(self.node_dict["GroundStation-core0"].neighbor)


if __name__ == '__main__':
    stations_url = 'https://celestrak.org/NORAD/elements/gp.php?GROUP=starlink&FORMAT=tle'
    # The first element in gs_position list is the location of core network,
    # the following elements are the location of ue
    flag = 1
    if flag:

        station_loc = [
            [20, 20],
            [30, 30],
            [40, 40],
            [45, 45],
            [60, 60]
        ]
        system = SatelliteSystem(stations_url, station_loc, 0)
    # system.remove()
    else:
        sat_name = "starlink"
        core_name = "GroundStation-core0"
        ue_name = "GroundStation-ue"

        for i in range(1, 10):
            DockerInterface.remove_container(sat_name + str(i))
        DockerInterface.remove_container(core_name)
        for i in range(4):
            DockerInterface.remove_container(ue_name + str(i + 1))
        for i in range(1, 10):
            DockerInterface.remove_bridge("b" + sat_name + str(i))
        DockerInterface.remove_bridge("b" + core_name)
        for i in range(4):
            DockerInterface.remove_bridge("b" + ue_name + str(i + 1))

    # system.create_all_containers()
    # print(system.satellites[0])
    # print(system.get_neighbour_satellite(system.satellites[0].name))
