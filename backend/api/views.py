from django.db.models import Sum
from django.http import HttpResponse
from django.urls import reverse

from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

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
    SetPasswordSerializer
)


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'limit'
    max_page_size = 100


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
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
        permission_classes=[IsAuthenticated],
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
        recipe = self.get_object()
        if request.method == 'POST':
            Favorite.objects.get_or_create(user=request.user, recipe=recipe)
            return Response({'status': 'added to favorites'}, status=201)
        Favorite.objects.filter(user=request.user, recipe=recipe).delete()
        return Response({'status': 'removed from favorites'})

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def shopping_cart(self, request, pk=None):
        recipe = self.get_object()
        if request.method == 'POST':
            ShoppingCart.objects.get_or_create(
                user=request.user, recipe=recipe
            )
            return Response({'status': 'added to shopping cart'}, status=201)
        ShoppingCart.objects.filter(user=request.user, recipe=recipe).delete()
        return Response({'status': 'removed from shopping cart'})

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[permissions.IsAuthenticated],
    )
    def download_shopping_cart(self, request):
        ingredients = RecipeIngredient.objects.filter(
            recipe__shopping_cart__user=request.user
        ).values(
            'ingredient__name', 'ingredient__measurement_unit'
        ).annotate(
            total_amount=Sum('amount')
        )

        content = '\n'.join([
            f"{item['ingredient__name']} ({
                item['ingredient__measurement_unit']
            })"
            f" — {item['total_amount']}"
            for item in ingredients
        ])
        response = HttpResponse(content, content_type='text/plain')
        response['Content-Disposition'] = (
            'attachment; filename="shopping_list.txt"'
        )
        return response


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
            Follow.objects.get_or_create(user=request.user, following=user)
            return Response(
                {'status': 'subscribed'},
                status=status.HTTP_201_CREATED
            )
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
