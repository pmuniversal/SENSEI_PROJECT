# DOCKER COMMANDS

## Проверить контейнеры

docker ps

## Остановить контейнер

docker stop simplerllm

## Запустить контейнер

docker start simplerllm

## Перезапустить контейнер

docker restart simplerllm

## Посмотреть логи

docker logs simplerllm

## Войти в контейнер

docker exec -it simplerllm bash

## Запустить бота

python3 /app/main.py

## Остановить бота

pkill -f python