from django.contrib.auth import get_user_model
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .serializers import RegisterSerializer, UserProfileSerializer, ProfileSerializer
from .models import Profile

User = get_user_model()


# Accept either username or email as the "username" field.
class EmailOrUsernameTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        # If user typed an email into the username field, try to resolve username
        username_or_email = attrs.get("username")
        if username_or_email and "@" in username_or_email:
            try:
                u = User.objects.get(email__iexact=username_or_email)
                attrs["username"] = u.username
            except User.DoesNotExist:
                # leave as-is; TokenObtainPairSerializer will handle auth failure
                pass
        return super().validate(attrs)


class EmailOrUsernameTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailOrUsernameTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    queryset = User.objects.all()


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    def patch(self, request):
        """
        PATCH /api/auth/me/ :
          - Accept multipart/form-data if uploading avatar
          - Accept JSON to update profile fields
        """
        user = request.user
        profile = getattr(user, "profile", None)
        if not profile:
            profile = Profile.objects.create(user=user)

        # handle avatar upload if present
        avatar = request.FILES.get("avatar")
        if avatar is not None:
            profile.avatar = avatar

        # update simple fields if provided
        body = request.data
        if "display_name" in body:
            profile.display_name = body.get("display_name", profile.display_name)
        if "about" in body:
            profile.about = body.get("about", profile.about)
        if "phone" in body:
            profile.phone = body.get("phone", profile.phone)

        profile.save()
        serializer = UserProfileSerializer(user, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)
