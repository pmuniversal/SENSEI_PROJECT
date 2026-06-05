VPS:
Oracle Cloud

OS:
Ubuntu 22.04

Container:
simplerllm

Start:

sudo docker exec -it simplerllm bash

python3 /app/main.py

Supervisor:

supervisord -c /etc/supervisord.conf

Container path:

/app/main.py