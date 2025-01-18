# Инструкция по запуску проекта

## 1. Клонирование репозитория
```bash
git clone https://github.com/impleex/foodgram-st.git
```
## 2. Запуск контейнеров
```bash
cd infra
docker-compose up -d
```
## 3. Создание суперпользователя
```bash
docker-compose exec backend python manage.py createsuperuser
```

## 4. Загрузка ингредиентов
```bash
cd infra
docker-compose exec backend bash
python manage.py load_ingredients data/ingredients.json
```
## 5. Доступ к сервису
```bash
Фронтенд доступен по адресу: http://localhost

Тестирование API можно проводить с помощью Postman.
Файл коллекции тестов находится по пути:
postman_collection/foodgram.postman_collection.json
```
