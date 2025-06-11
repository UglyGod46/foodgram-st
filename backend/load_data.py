import json
from recipes.models import Ingredient

with open('../data/ingredients.json', 'r') as f:
    data = json.load(f)
    for item in data:
        Ingredient.objects.create(
            name=item['name'], measurement_unit=item['measurement_unit']
        )
