FROM ibmjava:latest
MAINTAINER Xinchun Liu <lospringliu@gmail.com>
RUN apt-get update && apt-get install -y vim python3-pip libmysqlclient-dev git libldap2-dev libsasl2-dev && pip3 install --upgrade pip && pip3 install django docutils mysqlclient pyldap django-mptt django-reversion
EXPOSE 8000
