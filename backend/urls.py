from django.contrib import admin
from django.urls import path
from django.http import JsonResponse

# Explicit imports to avoid conflicts
from api.views import RegisterView
from api.views import WalletView
from api.views import TransferView
from api.views import TransactionListView
from api.views import WithdrawView
from api.views import AdminAddBalanceView
from api.views import AdminRemoveBalanceView
from api.views import AdminDeleteUserView
from api.views import CustomTokenObtainPairView


# Function-based views
from api.views import admin_all_users
from api.views import admin_all_transactions
from api.views import admin_withdraw_requests
from api.views import admin_approve_withdraw
from api.views import admin_reject_withdraw

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response


def home(request):
    return JsonResponse({"message": "CrypzoPay Backend Running ✅"})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_current_user(request):
    return Response({
        "username": request.user.username,
        "email": request.user.email,
        "role": "admin" if request.user.is_staff else "user"
    })


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard(request):
    from django.contrib.auth.models import User
    from api.models import Wallet, Transaction
    import django.db.models as models

    total_users = User.objects.count()
    total_balance = Wallet.objects.aggregate(total=models.Sum('balance'))['total'] or 0
    total_tx = Transaction.objects.count()

    return Response({
        "total_users": total_users,
        "total_balance": str(total_balance),
        "total_transactions": total_tx
    })


urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),

    path('api/register/', RegisterView.as_view()),
    path('api/token/', CustomTokenObtainPairView.as_view()),
    path('api/me/', get_current_user),

    path('api/wallet/', WalletView.as_view()),
    path('api/transfer/', TransferView.as_view()),
    path('api/transactions/', TransactionListView.as_view()),
    path('api/withdraw/', WithdrawView.as_view()),

    # Admin Routes
    path('api/admin/dashboard/', admin_dashboard),
    path('api/admin/users/', admin_all_users),
    path('api/admin/transactions/', admin_all_transactions),
    path('api/admin/withdraws/', admin_withdraw_requests),

    # Admin Management
    path('api/admin/add-balance/<int:user_id>/', AdminAddBalanceView.as_view()),
    path('api/admin/remove-balance/<int:user_id>/', AdminRemoveBalanceView.as_view()),
    path('api/admin/delete-user/<int:user_id>/', AdminDeleteUserView.as_view()),

    # Approve / Reject Withdraw
    path('api/admin/approve-withdraw/<int:tx_id>/', admin_approve_withdraw),
    path('api/admin/reject-withdraw/<int:tx_id>/', admin_reject_withdraw),

    # OTP Verification
]