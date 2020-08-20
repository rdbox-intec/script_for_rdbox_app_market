FROM ubuntu:focal

ENV PYTHONPATH "${PYTHONPATH}:/script_for_rdbox_app_market"
ENV DEBIAN_FRONTEND noninteractive
ENV DEBCONF_NOWARNINGS yes

RUN apt-get update && apt-get install -y \
        python3 \
        python3-pip \
        git \
        apt-transport-https \
        curl

RUN curl -s https://baltocdn.com/helm/signing.asc | APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=1 apt-key add - && \
    echo "deb https://baltocdn.com/helm/stable/debian/ all main" | tee /etc/apt/sources.list.d/helm-stable-debian.list && \
    apt-get update && apt-get install -y \
        helm

RUN mkdir -p /snap/bin && \
    ln -s /usr/sbin/helm /snap/bin/helm

COPY . /script_for_rdbox_app_market

RUN pip3 install -r /script_for_rdbox_app_market/requirements.txt

RUN mkdir -p /root/.ssh && \
    echo "Host github.com\n\tStrictHostKeyChecking no\n" >> /root/.ssh/config && \
    chmod 700 /root/.ssh && \
    chmod 600 /root/.ssh/*

CMD python3 -m rdbox_app_market