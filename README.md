# Foodgram

Foodgram — веб-приложение для публикации и обмена рецептами. Пользователи могут создавать, редактировать и просматривать рецепты, добавлять их в избранное или список покупок, а также искать ингредиенты. Проект включает бэкенд на Django REST Framework, фронтенд на React и разворачивается через Docker Compose с использованием PostgreSQL и Nginx.

## Технологии
- **Backend**: Python 3.9, Django 3.2, Django REST Framework, Gunicorn
- **Frontend**: React, Node.js 21.7
- **Database**: PostgreSQL 13
- **Infrastructure**: Docker, Docker Compose, Nginx 1.19

## Инструкция для ревьюера: запуск проекта

Следуйте этим шагам, чтобы развернуть проект локально.

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/UglyGod46/foodgram-st.git
cd foodgram-st
```

### 2. Убедитесь, что Docker и Docker Compose установлены
- Установите [Docker](https://docs.docker.com/get-docker/) и [Docker Compose](https://docs.docker.com/compose/install/) для вашей операционной системы.
- Проверьте установку:
  ```bash
  docker --version
  docker compose version
  ```

### 3. Запустите проект
1. Перейдите в папку `infra`:
   ```bash
   cd infra
   ```

2. Создайте файл `.env` с переменными окружения:
   ```bash
   DB_ENGINE=django.db.backends.postgresql
   DB_NAME=postgres
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   DB_HOST=db
   DB_PORT=5432
   SECRET_KEY=your_secret_key_here
   ```

3. Выполните команду для запуска:
   ```bash
   docker compose up -d --build
   ```
   - Флаг `--build` пересобирает образы, если вы используете локальную сборку.
   - Контейнеры `db`, `backend`, `frontend` и `nginx` будут запущены.

### 4. Проверьте работоспособность
- **Логи**: Убедитесь, что сервисы запустились корректно:
  ```bash
  docker compose logs backend
  ```
  Ожидаемый вывод включает:
  - `PostgreSQL started`
  - `Applying ... OK` (миграции)
  - `X static files copied` (сбор статики)
  - `Successfully imported X ingredients` (загрузка ингредиентов)

- **Доступ**:
  - Фронтенд: [http://localhost](http://localhost)
  - API: [http://localhost/api/](http://localhost/api/) (например, [http://localhost/api/ingredients/](http://localhost/api/ingredients/))
  - Админка: [http://localhost/admin/](http://localhost/admin/) (email: `admin`, пароль: `admin`)

### Доступ к приложению
- **Админка**:
  - Логин: `admin`
  - Пароль: `admin`
- **API**:
  - Проверьте ингредиенты и рецепты:
    ```bash
    curl http://localhost/api/ingredients/
    curl http://localhost/api/recipes/
    ```
  - Для авторизации получите токен:
    ```bash
    curl -X POST -d "username=admin&password=admin" http://localhost/api/auth/token/login/
    ```

### Замечания
- **Данные**:
  - Ингредиенты загружаются из `data/ingredients.json` через команду `load_data`.
- **Медиафайлы**:
  - Изображения рецептов сохраняются в `/app/media/` (бэкенд) и доступны через `/var/html/media/` (Nginx).
  - Если изображения не отображаются, проверьте том `media_value` в `docker-compose.yml` и `nginx.conf`.
- **Docker Hub**:
  - Образы доступны: [uglygod46/foodgram-backend](https://hub.docker.com/r/uglygod46/foodgram-backend) и [uglygod46/foodgram-frontend](https://hub.docker.com/r/uglygod46/foodgram-frontend).
- **Остановка проекта**:
  ```bash
  docker compose down --volumes
  ```
  Флаг `--volumes` очищает базу данных и медиафайлы для чистого запуска.
