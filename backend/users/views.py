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
            'email': user.email,
            'unsubscribe_mode': user.unsubscribe_mode,
            'unsubscribe_text': user.unsubscribe_text,
        })
    elif request.method == 'POST':
        fields = []

        autopilot = request.data.get('autopilot_active')
        if autopilot is not None:
            user.autopilot_active = bool(autopilot)
            fields.append('autopilot_active')

        mode = request.data.get('unsubscribe_mode')
        if mode is not None:
            valid = {c[0] for c in user.UNSUBSCRIBE_MODE_CHOICES}
            if mode not in valid:
                return Response({'error': f'unsubscribe_mode must be one of {sorted(valid)}.'},
                                status=status.HTTP_400_BAD_REQUEST)
            user.unsubscribe_mode = mode
            fields.append('unsubscribe_mode')

        text = request.data.get('unsubscribe_text')
        if text is not None:
            if not str(text).strip():
                return Response({'error': 'unsubscribe_text cannot be empty.'},
                                status=status.HTTP_400_BAD_REQUEST)
            user.unsubscribe_text = str(text).strip()[:200]
            fields.append('unsubscribe_text')

        if not fields:
            return Response({'error': 'Invalid data'}, status=status.HTTP_400_BAD_REQUEST)

        user.save(update_fields=fields)
        return Response({
            'success': True,
            'autopilot_active': user.autopilot_active,
            'unsubscribe_mode': user.unsubscribe_mode,
            'unsubscribe_text': user.unsubscribe_text,
        })

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
