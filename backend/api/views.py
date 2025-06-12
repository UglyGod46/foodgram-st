from django.db.models import Sum
from django.http import HttpResponse

from rest_framework import viewsets, permissions, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

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
    AvatarSerializer
)


class RecipeViewSet(viewsets.ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['author', 'is_favorited', 'is_in_shopping_cart']
    search_fields = ['name']

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

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
    filter_backends = [filters.SearchFilter]
    search_fields = ['^name']


class CustomPagination(PageNumberPagination):
    page_size_query_param = 'limit'
    max_page_size = 100


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
            return Response({'status': 'subscribed'}, status=201)
        Follow.objects.filter(user=request.user, following=user).delete()
        return Response({'status': 'unsubscribed'})

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
        parser_classes=[MultiPartParser, FormParser]
    )
    def avatar(self, request):
        user = request.user
        serializer = AvatarSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    @avatar.mapping.delete
    def delete_avatar(self, request):
        user = request.user
        user.avatar.delete()
        user.avatar = None
        user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)
