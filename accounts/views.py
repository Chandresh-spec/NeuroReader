from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserProfileSerializer
import urllib.request
import urllib.parse
import json
from django.conf import settings
from django.http import HttpResponse


def get_tokens_for_user(user):
    """
    Generate a pair of JWT access and refresh tokens for a given user.
    Returns a dict with 'refresh' and 'access' keys.
    """
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Creates a new user account. Open to all (no auth required).

    Request Body:
        {
            "email": "user@example.com",
            "full_name": "John Doe",
            "password": "strongpass123",
            "confirm_password": "strongpass123"
        }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Account created successfully.",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.full_name,
                    },
                    "tokens": tokens,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    POST /api/auth/login/
    Authenticates a user with email + password and returns JWT tokens.

    Request Body:
        {
            "email": "user@example.com",
            "password": "strongpass123"
        }
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            user = serializer.validated_data["user"]
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Login successful.",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.full_name,
                    },
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the provided refresh token, effectively logging the user out.
    Requires a valid access token in the Authorization header.

    Request Body:
        {
            "refresh": "<refresh_token>"
        }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Logged out successfully."},
                status=status.HTTP_205_RESET_CONTENT,
            )
        except TokenError as e:
            return Response(
                {"error": f"Invalid or expired token: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class ProfileView(APIView):
    """
    GET /api/auth/profile/     — returns profile of currently authenticated user
    PATCH /api/auth/profile/   — updates name, bio, and profile picture
    """

    permission_classes = [IsAuthenticated]
    from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return Response(
            {
                "message": "Profile fetched successfully.",
                "user": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Profile updated successfully.",
                    "user": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(APIView):
    """
    POST /api/auth/google/
    Authenticates a user via Google OAuth token.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token is missing'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # First try as id_token
            url = f"https://oauth2.googleapis.com/tokeninfo?id_token={token}"
            req = urllib.request.Request(url)
            try:
                with urllib.request.urlopen(req) as response:
                    user_data = json.loads(response.read().decode())
            except Exception:
                # Fallback: Treat as access_token
                url = f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={token}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req) as response:
                    user_data = json.loads(response.read().decode())
                
            if 'error' in user_data:
                return Response({'error': 'Invalid token'}, status=status.HTTP_400_BAD_REQUEST)
                
            email = user_data.get('email')
            if not email:
                return Response({'error': 'Email not found in token'}, status=status.HTTP_400_BAD_REQUEST)
                
            full_name = user_data.get('name', email.split('@')[0])
                
            # Try to get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'full_name': full_name}
            )
            
            tokens = get_tokens_for_user(user)
            return Response(
                {
                    "message": "Google Login successful.",
                    "user": {
                        "id": user.id,
                        "email": user.email,
                        "full_name": user.full_name,
                    },
                    "tokens": tokens,
                },
                status=status.HTTP_200_OK,
            )
            
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class GoogleAuthCallbackView(APIView):
    """
    GET /api/auth/google/callback/
    Handles the OAuth 2.0 authorization code redirect from Google.
    Exchanges the code for tokens, gets user info, creates/gets user,
    and redirects to the frontend with JWT tokens stored in localStorage.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        code = request.GET.get('code')
        error = request.GET.get('error')

        if error:
            return HttpResponse(self._error_page(f"Google login error: {error}"))

        if not code:
            return HttpResponse(self._error_page("No authorization code received."))

        try:
            # Build the redirect URI (must match what was sent in the auth request)
            redirect_uri = request.build_absolute_uri('/accounts/google/login/callback/')

            # Exchange authorization code for access token
            token_data = urllib.parse.urlencode({
                'code': code,
                'client_id': settings.GOOGLE_CLIENT_ID,
                'client_secret': settings.GOOGLE_CLIENT_SECRET,
                'redirect_uri': redirect_uri,
                'grant_type': 'authorization_code',
            }).encode()

            token_req = urllib.request.Request(
                'https://oauth2.googleapis.com/token',
                data=token_data,
                method='POST'
            )
            token_req.add_header('Content-Type', 'application/x-www-form-urlencoded')

            with urllib.request.urlopen(token_req) as resp:
                token_response = json.loads(resp.read().decode())

            access_token = token_response.get('access_token')
            if not access_token:
                return HttpResponse(self._error_page("Failed to get access token from Google."))

            # Fetch user info from Google
            userinfo_req = urllib.request.Request(
                f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={access_token}"
            )
            with urllib.request.urlopen(userinfo_req) as resp:
                user_data = json.loads(resp.read().decode())

            email = user_data.get('email')
            if not email:
                return HttpResponse(self._error_page("Could not retrieve email from Google."))

            full_name = user_data.get('name', email.split('@')[0])

            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={'full_name': full_name}
            )

            # Generate JWT tokens
            tokens = get_tokens_for_user(user)

            # Return HTML that stores tokens in localStorage and redirects
            html = f"""<!DOCTYPE html>
<html><head><title>Signing in…</title>
<style>
    body {{ background: #060a12; color: #e8f0fe; font-family: 'Segoe UI', sans-serif;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
    .card {{ text-align: center; padding: 40px; }}
    .spinner {{ width: 40px; height: 40px; border: 4px solid rgba(56,189,248,0.2);
               border-top-color: #38bdf8; border-radius: 50%;
               animation: spin 0.8s linear infinite; margin: 0 auto 20px; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
    h2 {{ color: #38bdf8; margin-bottom: 8px; }}
    p {{ color: #7a91b4; }}
</style></head>
<body><div class="card">
    <div class="spinner"></div>
    <h2>Welcome, {user.full_name}!</h2>
    <p>Signing you in to NeuroRead…</p>
</div>
<script>
    localStorage.setItem('access_token', '{tokens["access"]}');
    localStorage.setItem('refresh_token', '{tokens["refresh"]}');
    localStorage.setItem('user_name', '{user.full_name}');
    setTimeout(function() {{ window.location.href = '/index.html'; }}, 1500);
</script></body></html>"""
            return HttpResponse(html)

        except Exception as e:
            return HttpResponse(self._error_page(str(e)))

    def _error_page(self, message):
        return f"""<!DOCTYPE html>
<html><head><title>Login Error</title>
<style>
    body {{ background: #060a12; color: #e8f0fe; font-family: 'Segoe UI', sans-serif;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }}
    .card {{ text-align: center; padding: 40px; max-width: 400px; }}
    h2 {{ color: #f87171; margin-bottom: 12px; }}
    p {{ color: #7a91b4; margin-bottom: 20px; }}
    a {{ color: #38bdf8; text-decoration: none; }}
</style></head>
<body><div class="card">
    <h2>Login Failed</h2>
    <p>{message}</p>
    <a href="/login.html">← Back to Login</a>
</div></body></html>"""
