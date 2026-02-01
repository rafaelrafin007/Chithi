from django.contrib.auth import get_user_model
from django.db import models
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .serializers import RegisterSerializer, UserProfileSerializer, ProfileSerializer, UserSimpleSerializer, FriendRequestSerializer
from .models import Profile, FriendRequest

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


class UsersDirectoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        users = User.objects.exclude(id=request.user.id)
        data = []
        for u in users:
            status_label = "none"
            fr = FriendRequest.objects.filter(
                (models.Q(from_user=request.user, to_user=u) | models.Q(from_user=u, to_user=request.user))
            ).order_by("-created_at").first()
            if fr:
                if fr.status == FriendRequest.STATUS_ACCEPTED:
                    status_label = "friends"
                elif fr.status == FriendRequest.STATUS_PENDING:
                    status_label = "outgoing" if fr.from_user_id == request.user.id else "incoming"
                elif fr.status == FriendRequest.STATUS_DECLINED:
                    status_label = "declined"
            serialized = UserSimpleSerializer(u, context={"request": request}).data
            serialized["friend_status"] = status_label
            data.append(serialized)
        return Response(data)


class FriendRequestsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        incoming = FriendRequest.objects.filter(to_user=request.user, status=FriendRequest.STATUS_PENDING)
        outgoing = FriendRequest.objects.filter(from_user=request.user, status=FriendRequest.STATUS_PENDING)
        return Response({
            "incoming": FriendRequestSerializer(incoming, many=True, context={"request": request}).data,
            "outgoing": FriendRequestSerializer(outgoing, many=True, context={"request": request}).data,
        })

    def post(self, request):
        to_user_id = request.data.get("to_user_id")
        if not to_user_id:
            return Response({"detail": "to_user_id is required"}, status=400)
        if str(to_user_id) == str(request.user.id):
            return Response({"detail": "Cannot friend yourself"}, status=400)
        try:
            to_user = User.objects.get(pk=to_user_id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=404)

        existing = FriendRequest.objects.filter(
            (models.Q(from_user=request.user, to_user=to_user) | models.Q(from_user=to_user, to_user=request.user))
        ).order_by("-created_at").first()
        if existing:
            if existing.status == FriendRequest.STATUS_ACCEPTED:
                return Response({"detail": "Already friends"}, status=400)
            if existing.status == FriendRequest.STATUS_PENDING:
                if existing.from_user_id == request.user.id:
                    return Response({"detail": "Request already sent"}, status=400)
                # Accept incoming request automatically if user sends back
                existing.status = FriendRequest.STATUS_ACCEPTED
                existing.save(update_fields=["status", "updated_at"])
                return Response(FriendRequestSerializer(existing, context={"request": request}).data, status=200)

        fr = FriendRequest.objects.create(from_user=request.user, to_user=to_user)
        return Response(FriendRequestSerializer(fr, context={"request": request}).data, status=201)


class FriendRequestRespondView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, request_id):
        action = (request.data.get("action") or "").lower()
        if action not in ("accept", "decline"):
            return Response({"detail": "action must be accept or decline"}, status=400)
        try:
            fr = FriendRequest.objects.get(pk=request_id, to_user=request.user)
        except FriendRequest.DoesNotExist:
            return Response({"detail": "Request not found"}, status=404)

        fr.status = FriendRequest.STATUS_ACCEPTED if action == "accept" else FriendRequest.STATUS_DECLINED
        fr.save(update_fields=["status", "updated_at"])
        return Response(FriendRequestSerializer(fr, context={"request": request}).data, status=200)


class FriendRequestCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, request_id):
        try:
            fr = FriendRequest.objects.get(pk=request_id, from_user=request.user, status=FriendRequest.STATUS_PENDING)
        except FriendRequest.DoesNotExist:
            return Response({"detail": "Request not found"}, status=404)
        fr.delete()
        return Response({"detail": "Request cancelled"}, status=200)


class FriendsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        accepted = FriendRequest.objects.filter(
            status=FriendRequest.STATUS_ACCEPTED,
            from_user__in=[request.user],
        ) | FriendRequest.objects.filter(
            status=FriendRequest.STATUS_ACCEPTED,
            to_user__in=[request.user],
        )
        friends = set()
        for fr in accepted:
            if fr.from_user_id == request.user.id:
                friends.add(fr.to_user)
            else:
                friends.add(fr.from_user)
        serialized = UserSimpleSerializer(list(friends), many=True, context={"request": request}).data
        return Response(serialized)
