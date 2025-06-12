from rest_framework import serializers
from django.core.files.base import ContentFile
from djoser.serializers import (
    UserCreateSerializer as DjoserUserCreateSerializer
)
import base64
import os

from users.models import User, Follow
from recipes.models import (
    Recipe,
    Ingredient,
    RecipeIngredient,
    Favorite,
    ShoppingCart
)


class Base64ImageField(serializers.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs['allow_null'] = True
        super().__init__(*args, **kwargs)

    def to_internal_value(self, data):
        if data is None:
            return None
        if not data or (isinstance(data, str) and not data.strip()):
            raise serializers.ValidationError("Это поле не может быть пустым.")
        if isinstance(data, str) and data.startswith('data:image'):
            try:
                format, imgstr = data.split(';base64,')
                ext = format.split('/')[-1]
                if ext not in ['png', 'jpg', 'jpeg']:
                    raise serializers.ValidationError(
                        "Неподдерживаемый формат изображения"
                    )
                data = ContentFile(
                    base64.b64decode(imgstr), name=f'image.{ext}'
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
            print(f"Image file not found: {value.path}")
            return None
        try:
            with open(value.path, 'rb') as image_file:
                encoded_string = base64.b64encode(
                    image_file.read()
                ).decode('utf-8')
                ext = value.name.split('.')[-1]
                return f"data:image/{ext};base64,{encoded_string}"
        except Exception as e:
            print(f"Error encoding image: {e}")
            return None


class AvatarSerializer(serializers.ModelSerializer):
    avatar = Base64ImageField()

    class Meta:
        model = User
        fields = ('avatar',)
        extra_kwargs = {
            'avatar': {'required': False}
        }

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance.avatar and instance.avatar.file:
            try:
                with open(instance.avatar.path, 'rb') as image_file:
                    encoded_string = base64.b64encode(
                        image_file.read()
                    ).decode('utf-8')
                    ext = instance.avatar.name.split('.')[-1]
                    representation['avatar'] = (
                        f"data:image/{ext};base64,{encoded_string}"
                    )
            except Exception as e:
                print(f"Error encoding avatar: {e}")
                representation['avatar'] = None
        else:
            representation['avatar'] = None
        return representation


class SetPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Текущий пароль неверный.")
        return value

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        try:
            validate_password(value, self.context['request'].user)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return value

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()


class CustomUserCreateSerializer(DjoserUserCreateSerializer):
    class Meta:
        model = User
        fields = (
            'id',
            'email',
            'username',
            'first_name',
            'last_name',
            'password'
        )

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user

    def to_representation(self, instance):
        return {
            'id': instance.id,
            'email': instance.email,
            'username': instance.username,
            'first_name': instance.first_name,
            'last_name': instance.last_name
        }


class CustomUserSerializer(serializers.ModelSerializer):
    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'is_subscribed',
            'avatar'
        )

    def get_is_subscribed(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if obj == request.user:
            return False
        return Follow.objects.filter(
            user=request.user,
            following=obj
        ).exists()


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ('id', 'name', 'measurement_unit')


class RecipeIngredientSerializer(serializers.ModelSerializer):
    id = serializers.PrimaryKeyRelatedField(
        source='ingredient.id',
        queryset=Ingredient.objects.all()
    )
    name = serializers.CharField(
        source='ingredient.name',
        read_only=True
    )
    measurement_unit = serializers.CharField(
        source='ingredient.measurement_unit',
        read_only=True
    )

    class Meta:
        model = RecipeIngredient
        fields = ('id', 'name', 'measurement_unit', 'amount')


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = RecipeIngredientSerializer(
        many=True,
        source='recipeingredient_set'
    )
    author = CustomUserSerializer(read_only=True)
    image = Base64ImageField()
    is_favorited = serializers.SerializerMethodField()
    is_in_shopping_cart = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'name',
            'image',
            'text',
            'ingredients',
            'cooking_time',
            'author',
            'is_favorited',
            'is_in_shopping_cart'
        )

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError(
                "Рецепт должен содержать хотя бы один ингредиент."
            )
        ingredient_ids = [item['ingredient']['id'] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError(
                "Ингредиенты не должны повторяться."
            )
        for item in value:
            if item['amount'] <= 0:
                raise serializers.ValidationError(
                    "Количество ингредиента должно быть больше 0."
                )
        return value

    def get_is_favorited(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return Favorite.objects.filter(
            user=request.user,
            recipe=obj
        ).exists()

    def get_is_in_shopping_cart(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return ShoppingCart.objects.filter(
            user=request.user,
            recipe=obj
        ).exists()

    def create(self, validated_data):
        ingredients_data = validated_data.pop('recipeingredient_set')
        recipe = Recipe.objects.create(**validated_data)
        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient_data['ingredient']['id'],
                amount=ingredient_data['amount']
            )
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop('recipeingredient_set')
        instance.name = validated_data.get('name', instance.name)
        instance.image = validated_data.get('image', instance.image)
        instance.text = validated_data.get('text', instance.text)
        instance.cooking_time = validated_data.get(
            'cooking_time',
            instance.cooking_time
        )
        instance.save()
        instance.recipeingredient_set.all().delete()
        for ingredient_data in ingredients_data:
            RecipeIngredient.objects.create(
                recipe=instance,
                ingredient=ingredient_data['ingredient']['id'],
                amount=ingredient_data['amount']
            )
        return instance
