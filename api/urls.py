from django.urls import path
from .views import (
    RegisterView,
    CustomTokenObtainPairView,
    UserBalanceView,
    SendMoneyView,
    WithdrawRequestView,
    AdminUserListView,
    AdminAdjustBalanceView,
    AdminWithdrawListView,
    AdminProcessWithdrawView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', CustomTokenObtainPairView.as_view(), name='login'),

    path('me/', UserBalanceView.as_view(), name='me'),
    path('send-money/', SendMoneyView.as_view(), name='send-money'),
    path('withdraw/', WithdrawRequestView.as_view(), name='withdraw'),

    # Admin Routes
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/adjust-balance/<int:user_id>/', AdminAdjustBalanceView.as_view(), name='adjust-balance'),
    path('admin/withdraws/', AdminWithdrawListView.as_view(), name='admin-withdraws'),
    path('admin/withdraws/<int:withdraw_id>/', AdminProcessWithdrawView.as_view(), name='process-withdraw'),
]