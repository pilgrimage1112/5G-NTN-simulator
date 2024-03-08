# Dockerfile
# name: inc
# Project: docker-firefox-ubuntu
# License: GNU GPLv3
#
# 

FROM ubuntu:focal as ueransim-builder
ARG DEBIAN_FRONTEND=noninteractive 
ENV TZ=Asia/Shanghai

RUN apt-get update -y && apt-get upgrade -y &&\
    apt install -y make gcc g++ libsctp-dev lksctp-tools\
    iproute2 wget software-properties-common git

RUN wget -O - https://apt.kitware.com/keys/kitware-archive-latest.asc 2>/dev/null\
    | gpg --dearmor - | tee /etc/apt/trusted.gpg.d/kitware.gpg >/dev/null\
    && apt-add-repository 'deb https://apt.kitware.com/ubuntu/ bionic main'\
    && apt update && apt install -y cmake && apt-get install -y vim
    
RUN cmake --version

COPY . /UERANSIM/

RUN make -C UERANSIM

FROM openhs/ubuntu-x



MAINTAINER openhs
LABEL version = "0.9.0" \
      description = "Firefox with some privacy addons."



RUN apt-get update &&\
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    apulse \
    unzip \
    bzip2 \
    wget \
    ca-certificates \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libx11-xcb1 \
    libxtst6 \
    iproute2 iputils-ping net-tools \
    iperf3 libsctp-dev lksctp-tools tcpdump&& \
    \
    rm -rf /var/lib/apt/lists/*

RUN mkdir /usr/share/doc/bird2
RUN mkdir /usr/share/doc/bird2/examples
COPY bird.conf /usr/share/doc/bird2/examples/
RUN apt-get update && apt install -y bird2
WORKDIR /ueransim/bin
COPY --from=ueransim-builder /UERANSIM/build/*  /ueransim/
COPY --from=ueransim-builder /UERANSIM/config/* /ueransim/config/
COPY bird.conf /etc/bird/
RUN mkdir /run/bird/
COPY start.sh /ueransim/bin/

ENV FF_INSTALLER_NAME=firefox-latest.tar.bz2
RUN cd /tmp && \
    wget --progress=dot:mega -O ${FF_INSTALLER_NAME} \
         'https://download.mozilla.org/?product=firefox-latest-ssl&os=linux64&lang=en-US' && \
    tar -x -C /usr/local/bin -f ${FF_INSTALLER_NAME} && \
    chown -R appuser:appuser /usr/local/bin/firefox && \
    rm -f ${FF_INSTALLER_NAME}

# Firefox addons which shall be installed (NoScript Security Suite, Cookie AutoDelete, Disconnect, Foxy Proxy
# Standard); the format is '<addon_number:addon_id> [...]' where 'addon_number' identifies addon for downloading and
# 'addon_id' is identifier for installation
ARG addons="722:{73a6fe31-595d-460b-a920-fcc0f8843232} 3971429:CookieAutoDelete@kennydo.com 464050:2.0@disconnect.me 3466053:foxyproxy@eric.h.jung"

RUN profile=docker.default && \
    addonsDir=/home/appuser/.mozilla/firefox/${profile}/extensions && \
    \
    mkdir -p ${addonsDir} && \
    \
    /bin/echo -e \
      "[General]\n\
       StartWithLastProfile=1\n\
       \n\
       [Profile0]\n\
       Name=default\n\
       IsRelative=1\n\
       Path=${profile}\n\
       Default=1" >> /home/appuser/.mozilla/firefox/profiles.ini && \
    \
    downloadAddon() { \
      wget --progress=dot:mega https://addons.mozilla.org/firefox/downloads/file/${1}/addon-${1}-latest.xpi || \
      wget --progress=dot:mega https://addons.mozilla.org/firefox/downloads/latest/${1}/addon-${1}-latest.xpi || \
      wget --progress=dot:mega \
           https://addons.mozilla.org/firefox/downloads/latest/${1}/platform:2/addon-${1}-latest.xpi; \
    } && \
    \
    addonNum() { \
      echo ${1%:*}; \
    } && \
    \
    addonId() { \
      echo ${1#*:}; \
    } && \
    \
    for addon in ${addons}; do \
      addonNum=$(addonNum ${addon}); \
      downloadAddon ${addonNum} || exit 1; \
      mv addon-${addonNum}-latest.xpi ${addonsDir}/$(addonId ${addon}).xpi; \
    done && \
    \
    chown -R appuser:appuser /home/appuser/.mozilla

COPY container_startup.sh /opt/
RUN chmod +x /opt/container_startup.sh

ENTRYPOINT ["/opt/container_startup.sh"]
