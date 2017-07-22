#!/usr/bin/env bash

#pacur/ubuntu-zesty
#pacur/fedora-25
#pacur/archlinux
#pacur/centos-7
#pacur/fedora-22
#pacur/debian-wheezy
#pacur/debian-jessie
#pacur/ubuntu-precise
#pacur/ubuntu-trusty
#pacur/fedora-24
#pacur/fedora-23
#pacur/ubuntu-yakkety
#pacur/ubuntu-xenial
#hello-world
#pacur/fedora-21

docker run --rm -t -v `pwd`:/pacur pacur/ubuntu-trusty
docker run --rm -t -v `pwd`:/pacur pacur/fedora-22
