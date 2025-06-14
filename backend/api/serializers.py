from rest_framework import serializers
from django.core.files.base import ContentFile
from djoser.serializers import (
    UserCreateSerializer as DjoserUserCreateSerializer
)
import base64
import os

from users.models import User
from recipes.models import Recipe, Ingredient, RecipeIngredient

MIN_AMOUNT = 1
MAX_AMOUNT = 32000
MIN_COOKING_TIME = 1
MAX_COOKING_TIME = 32000


class Base64ImageField(serializers.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs["allow_null"] = True
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        if data is None:
            return None
        if not data or (isinstance(data, str) and not data.strip()):
            raise serializers.ValidationError("Это поле не может быть пустым.")
        if isinstance(data, str) and data.startswith("data:image"):
            try:
                format, imgstr = data.split(";base64,")
                ext = format.split("/")[-1]
                if ext not in ["png", "jpg", "jpeg"]:
                    raise serializers.ValidationError(
                        "Неподдерживаемый формат изображения"
                    )
                data = ContentFile(
                    base64.b64decode(imgstr), name=f"image.{ext}"
                )
            except Exception as e:
                raise serializers.ValidationError(
                    f"Ошибка декодирования Base64: {e}"
                )
        return super().to_internal_value(data)

    def to_representation(self, value):
        if not value or not value.name:
            return None
        if not os.path.exists(value.path):
            return None
        try:
            with open(value.path, "rb") as image_file:
                encoded_string = base64.b64encode(
                    image_file.read()
                ).decode("utf-8")
                ext = value.name.split(".")[-1]
                return f"data:image/{ext};base64,{encoded_string}"
        except Exception:
            return None


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField()

    class Meta:
        model = User
        fields = ("avatar",)
        extra_kwargs = {"avatar": {"required": False}}

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.avatar and instance.avatar.file:
            try:
                with open(instance.avatar.path, "rb") as image_file:
                    encoded_string = base64.b64encode(
                        image_file.read()
                    ).decode("utf-8")
                    ext = instance.avatar.name.split(".")[-1]
                    representation["avatar"] = (
                        f"data:image/{ext};base64,{encoded_string}"
                    )
            except Exception:
                representation["avatar"] = None
        else:
            representation["avatar"] = None
        return representation


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Текущий пароль неверный.")
        return value

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password

        try:
            validate_password(value, self.context["request"].user)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return value

    def save(self):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()


class CustomUserCreateSerializer(DjoserUserCreateSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "password"
        )

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "email": instance.email,
            "username": instance.username,
            "first_name": instance.first_name,
            "last_name": instance.last_name,
        }


class CustomUserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_subscribed",
            "avatar",
        )

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        if obj == request.user:
            return False
        return request.user.followers.filter(following=obj).exists()


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ("id", "name", "measurement_unit")


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        source="ingredient.id", queryset=Ingredient.objects.all()
    )
    name = serializers.CharField(source="ingredient.name", read_only=True)
    measurement_unit = serializers.CharField(
        source="ingredient.measurement_unit", read_only=True
    )
    amount = serializers.IntegerField(
        min_value=MIN_AMOUNT,
        max_value=MAX_AMOUNT
    )

    class Meta:
        model = RecipeIngredient
        fields = ("id", "name", "measurement_unit", "amount")


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(
        many=True,
        source="recipeingredient_set"
    )
    author = CustomUserSerializer(read_only=True)
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()
    cooking_time = serializers.IntegerField(
        min_value=MIN_COOKING_TIME, max_value=MAX_COOKING_TIME
    )

    class Meta:
        model = Recipe
        fields = (
            "id",
            "name",
            "image",
            "text",
            "ingredients",
            "cooking_time",
            "author",
            "is_favorited",
            "is_in_shopping_cart",
        )

    def validate(self, data):
        if (
            self.context["request"].method in ["PATCH", "PUT"]
            and "recipeingredient_set" not in data
        ):
            raise serializers.ValidationError(
                {"ingredients": ["Это поле обязательно при обновлении."]}
            )
        return data

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                "Рецепт должен содержать хотя бы один ингредиент."
            )
        ingredient_ids = [item["ingredient"]["id"] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                "Ингредиенты не должны повторяться."
            )
        return value

    def get_is_favorited(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user.favorites.filter(recipe=obj).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return request.user.shopping_carts.filter(recipe=obj).exists()

    def _create_ingredients(self, recipe, ingredients_data):
        ingredients = [
            RecipeIngredient(
                recipe=recipe,
                ingredient=ingredient_data["ingredient"]["id"],
                amount=ingredient_data["amount"],
            )
            for ingredient_data in ingredients_data
        ]
        RecipeIngredient.objects.bulk_create(ingredients)

    def create(self, validated_data):
        ingredients_data = validated_data.pop("recipeingredient_set")
        recipe = Recipe.objects.create(**validated_data)
        self._create_ingredients(recipe, ingredients_data)
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop("recipeingredient_set")
        instance.name = validated_data.get("name", instance.name)
        instance.image = validated_data.get("image", instance.image)
        instance.text = validated_data.get("text", instance.text)
        instance.cooking_time = validated_data.get(
            "cooking_time", instance.cooking_time
        )
        instance.save()
        instance.recipeingredient_set.all().delete()
        self._create_ingredients(instance, ingredients_data)
        return instance


class RecipeShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recipe
        fields = ("id", "name", "image", "cooking_time")


class SubscriptionSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()
    recipes = serializers.SerializerMethodField()
    recipes_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_subscribed",
            "avatar",
            "recipes",
            "recipes_count",
        )

    def get_is_subscribed(self, obj):
        return True

    def get_recipes(self, obj):
        request = self.context.get("request")
        recipes = obj.recipes.all()
        recipes_limit = request.query_params.get(
            "recipes_limit"
        ) if request else None
        if recipes_limit:
            try:
                recipes = recipes[: int(recipes_limit)]
            except ValueError:
                pass
        return RecipeShortSerializer(
            recipes, many=True, context={"request": request}
        ).data

    def get_recipes_count(self, obj):
        return obj.recipes.count()
