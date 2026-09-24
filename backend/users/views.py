from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    user = request.user
    if request.method == 'GET':
        return Response({
            'autopilot_active': user.autopilot_active,
            'username': user.username,
            'email': user.email
        })
    elif request.method == 'POST':
        autopilot = request.data.get('autopilot_active')
        if autopilot is not None:
            user.autopilot_active = bool(autopilot)
            user.save()
            return Response({'success': True, 'autopilot_active': user.autopilot_active})
        return Response({'error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)

from rest_framework.permissions import AllowAny
from .serializers import UserRegistrationSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response({
            "message": "User created successfully",
            "username": user.username
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
