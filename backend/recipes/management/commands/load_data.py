import json
import os
from django.core.management.base import BaseCommand
from recipes.models import Ingredient


class Command(BaseCommand):
    help = "Загружает ингредиенты из JSON файла"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path", nargs="?", type=str, default="/app/data/ingredients.json"
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"Файл {file_path} не существует"))
            alternate_paths = [
                "./data/ingredients.json",
                "../data/ingredients.json",
                "/app/data/ingredients.json",
            ]
            for path in alternate_paths:
                if os.path.exists(path):
                    file_path = path
                    self.stdout.write(self.style.SUCCESS(f"Найден файл по пути {path}"))
                    break
            else:
                self.stdout.write(self.style.ERROR("Файл с ингредиентами не найден"))
                return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            if Ingredient.objects.exists():
                self.stdout.write(
                    self.style.WARNING("Ингредиенты уже существуют в базе данных.")
                )
                return

            ingredient_count = 0
            for item in data:
                Ingredient.objects.get_or_create(
                    name=item["name"], measurement_unit=item["measurement_unit"]
                )
                ingredient_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Успешно импортировано {ingredient_count} ингредиентов"
                )
            )

        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR(f"Неверный формат JSON в {file_path}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ошибка во время импорта: {str(e)}"))
