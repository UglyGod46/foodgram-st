from django.db.models import Sum
from django.http import HttpResponse, Http404
from django.urls import reverse

from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from rest_framework.permissions import (
    IsAuthenticated,
    AllowAny
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.exceptions import ValidationError

from django_filters.rest_framework import DjangoFilterBackend

from recipes.models import (
    Recipe,
    Ingredient,
    RecipeIngredient,
    Favorite,
    ShoppingCart,
)
from users.models import User, Follow
from .serializers import (
    RecipeSerializer,
    IngredientSerializer,
    CustomUserSerializer,
    CustomUserCreateSerializer,
    AvatarSerializer,
    SetPasswordSerializer,
    SubscriptionSerializer,
    RecipeShortSerializer
)
from .permissions import IsAuthorOrReadOnly


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'limit'
    max_page_size = 100


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [
        permissions.IsAuthenticatedOrReadOnly,
        IsAuthorOrReadOnly
    ]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['author']
    search_fields = ['name']
    pagination_class = CustomPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user

        is_favorited = self.request.query_params.get('is_favorited')
        if is_favorited == '1' and user.is_authenticated:
            queryset = queryset.filter(favorite_set__user=user)
        elif is_favorited == '0' and user.is_authenticated:
            queryset = queryset.exclude(favorite_set__user=user)

        is_in_shopping_cart = self.request.query_params.get(
            'is_in_shopping_cart'
        )
        if is_in_shopping_cart == '1' and user.is_authenticated:
            queryset = queryset.filter(shoppingcart__user=user)
        elif is_in_shopping_cart == '0' and user.is_authenticated:
            queryset = queryset.exclude(shoppingcart__user=user)

        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(
        detail=True,
        methods=['get'],
        permission_classes=[AllowAny],
        url_path='get-link',
        url_name='get-link'
    )
    def get_link(self, request, pk=None):
        recipe = self.get_object()
        short_link = request.build_absolute_uri(
            reverse('recipe-short-link', kwargs={'recipe_id': recipe.id})
        )
        return Response({'short-link': short_link}, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def favorite(self, request, pk=None):
        try:
            recipe = self.get_object()  # Проверяем существование рецепта
        except Http404:
            return Response(
                {"detail": "Рецепт не найден."},
                status=status.HTTP_404_NOT_FOUND
            )

        if request.method == 'POST':
            if Favorite.objects.filter(
                user=request.user, recipe=recipe
            ).exists():
                return Response(
                    {"errors": "Рецепт уже в избранном."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            Favorite.objects.create(user=request.user, recipe=recipe)
            serializer = RecipeShortSerializer(
                recipe,
                context={'request': request}
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:  # DELETE method
            deleted_count, _ = Favorite.objects.filter(
                user=request.user,
                recipe=recipe
            ).delete()

            if deleted_count == 0:
                return Response(
                    {"errors": "Рецепта не было в избранном."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        try:
            recipe = self.get_object()
        except Http404:
            return Response(
                {"detail": "Рецепт не найден."},
                status=status.HTTP_404_NOT_FOUND
            )

        if request.method == 'POST':
            if ShoppingCart.objects.filter(
                user=request.user,
                recipe=recipe
            ).exists():
                return Response(
                    {"errors": "Рецепт уже в корзине."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            ShoppingCart.objects.create(user=request.user, recipe=recipe)
            serializer = RecipeShortSerializer(
                recipe,
                context={'request': request}
            )
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        else:  # DELETE method
            deleted_count, _ = ShoppingCart.objects.filter(
                user=request.user,
                recipe=recipe
            ).delete()

            if deleted_count == 0:
                return Response(
                    {"errors": "Рецепт не был в корзине."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def download_shopping_cart(self, request):

        ingredients = RecipeIngredient.objects.filter(
            recipe__shoppingcart__user=request.user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        )

        content = '\n'.join([
            f"{item['ingredient__name']} "
            f"({item['ingredient__measurement_unit']}) - "
            f"{item['total_amount']}"
            for item in ingredients
        ])

        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Http404:
            return Response(
                {"detail": "Рецепт не найден."},
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST
            )


class IngredientViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    pagination_class = None
    filter_backends = [filters.SearchFilter]
    search_fields = ['^name']

    def get_queryset(self):
        queryset = super().get_queryset()
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__istartswith=name)
        return queryset


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    pagination_class = CustomPagination

    def get_permissions(self):
        if self.action == 'create':
            return [permissions.AllowAny()]
        return super().get_permissions()

    def get_serializer_class(self):
        if self.action == 'create':
            return CustomUserCreateSerializer
        return CustomUserSerializer

    @action(detail=True, methods=['post', 'delete'], permission_classes=[
        permissions.IsAuthenticated
    ])
    def subscribe(self, request, pk=None):
        user = self.get_object()

        if request.method == 'POST':
            # Проверка подписки на самого себя
            if user == request.user:
                return Response(
                    {"errors": "Нельзя подписаться на самого себя."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if Follow.objects.filter(
                user=request.user, following=user
            ).exists():
                return Response(
                    {"errors": "Вы уже подписаны на этого пользователя."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            Follow.objects.create(user=request.user, following=user)
            serializer = SubscriptionSerializer(
                user,
                context={'request': request}
            )
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        else:
            if not Follow.objects.filter(
                user=request.user, following=user
            ).exists():
                return Response(
                    {"errors": "Подписка не найдена."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            Follow.objects.filter(user=request.user, following=user).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        Follow.objects.filter(user=request.user, following=user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_queryset(self):
        queryset = super().get_queryset()
        limit = self.request.query_params.get('limit')
        if limit:
            self.paginator.page_size = int(limit)
        return queryset

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated]
    )
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['put', 'patch'],
        url_path='avatar',
        url_name='user-avatar',
        permission_classes=[IsAuthenticated],
        parser_classes=[MultiPartParser, FormParser, JSONParser]
    )
    def avatar(self, request):
        user = request.user
        if 'avatar' not in request.data:
            return Response(
                {"avatar": ["Это поле обязательно."]},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = AvatarSerializer(user, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=False,
        methods=['delete'],
        url_path='avatar',
        permission_classes=[IsAuthenticated]
    )
    def delete_avatar(self, request):
        user = request.user
        user.avatar.delete()
        user.avatar = None
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['post'],
        url_path='set_password',
        url_name='set-password',
        permission_classes=[IsAuthenticated]
    )
    def set_password(self, request):
        serializer = SetPasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
        url_path='subscriptions',
        url_name='subscriptions'
    )
    def subscriptions(self, request):
        """Получение списка подписок текущего пользователя."""
        following_users = User.objects.filter(
            following__user=request.user
        )
        page = self.paginate_queryset(following_users)
        if page is not None:
            serializer = SubscriptionSerializer(
                page,
                many=True,
                context={'request': request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = SubscriptionSerializer(
            following_users,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
