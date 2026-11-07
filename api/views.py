from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from rest_framework import exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from django.contrib.auth.models import User
from django.db import transaction
from decimal import Decimal
from .models import Wallet, Transaction
from .serializers import RegisterSerializer

from django.utils import timezone
from datetime import timedelta

import random
from django.core.mail import send_mail


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        username = request.data.get('username')
        email = request.data.get('email')

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.is_active = True
            user.save()
            return Response({"message": "Account created successfully! You can now login."},
                          status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = Wallet.objects.get(user=request.user)
            return Response({"balance": str(wallet.balance)})
        except Wallet.DoesNotExist:
            # Create wallet if not exists
            wallet = Wallet.objects.create(user=request.user)
            return Response({"balance": "0.00"})



class TransferView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        to_input = request.data.get('to_user')  # can be username or email
        amount = Decimal(request.data.get('amount', 0))

        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=400)

        try:
            # Try to find receiver by username first, then by email
            receiver = None
            try:
                receiver = User.objects.get(username=to_input)
            except User.DoesNotExist:
                try:
                    receiver = User.objects.get(email=to_input)
                except User.DoesNotExist:
                    return Response({"error": "Recipient not found. Please check username or email."}, status=404)

            sender_wallet = Wallet.objects.get(user=request.user)
            receiver_wallet = Wallet.objects.get(user=receiver)

            if sender_wallet.balance < amount:
                return Response({"error": "Insufficient balance"}, status=400)

            with transaction.atomic():
                sender_wallet.balance -= amount
                receiver_wallet.balance += amount
                sender_wallet.save()
                receiver_wallet.save()

                Transaction.objects.create(
                    wallet=sender_wallet,
                    type='debit',
                    amount=amount,
                    description=f"Sent to {receiver.username}",
                    to_user=receiver
                )
                Transaction.objects.create(
                    wallet=receiver_wallet,
                    type='credit',
                    amount=amount,
                    description=f"Received from {request.user.username}",
                    to_user=request.user
                )

            return Response({"message": f"Money sent successfully to {receiver.username}!"})

        except Exception as e:
            return Response({"error": "Something went wrong"}, status=400)


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet = Wallet.objects.get(user=request.user)
        txs = wallet.transactions.order_by('-timestamp')
        data = [{
            'type': t.type,
            'amount': str(t.amount),
            'description': t.description,
            'timestamp': t.timestamp.strftime("%Y-%m-%d %H:%M")
        } for t in txs]
        return Response(data)


class WithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = Decimal(request.data.get('amount', 0))

        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=400)

        wallet = Wallet.objects.get(user=request.user)

        if amount > wallet.balance:
            return Response({"error": "Insufficient balance"}, status=400)

        Transaction.objects.create(
            wallet=wallet,
            type='debit',
            amount=amount,
            description="Withdrawal Request"
        )
        wallet.balance -= amount
        wallet.save()

        return Response({"message": "Withdrawal request submitted successfully!"})


# ==================== ADMIN VIEWS ====================

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_all_users(request):
    users = []
    for user in User.objects.all():
        try:
            wallet = Wallet.objects.get(user=user)
            balance = str(wallet.balance)
        except Wallet.DoesNotExist:
            balance = "0.00"

        users.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_active': user.is_active,
            'balance': balance
        })
    return Response(users)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_all_transactions(request):
    txs = Transaction.objects.all().order_by('-timestamp')
    data = [{
        'id': t.id,
        'user': t.wallet.user.username,
        'type': t.type,
        'amount': str(t.amount),
        'description': t.description,
        'timestamp': t.timestamp.strftime("%Y-%m-%d %H:%M")
    } for t in txs]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_withdraw_requests(request):
    txs = Transaction.objects.filter(
        type='debit',
        description__contains="Withdrawal"
    ).order_by('-timestamp')

    data = [{
        'id': t.id,
        'user': t.wallet.user.username,
        'amount': str(t.amount),
        'description': t.description,
        'timestamp': t.timestamp.strftime("%Y-%m-%d %H:%M")
    } for t in txs]
    return Response(data)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_approve_withdraw(request, tx_id):
    try:
        tx = Transaction.objects.get(id=tx_id)
        tx.description = tx.description + " - APPROVED"
        tx.save()
        return Response({"message": "Withdrawal Approved Successfully"})
    except Transaction.DoesNotExist:
        return Response({"error": "Request not found"}, status=404)


@api_view(['POST'])
@permission_classes([IsAdminUser])
def admin_reject_withdraw(request, tx_id):
    try:
        tx = Transaction.objects.get(id=tx_id, type='debit', description__contains="Withdrawal")

        # Refund the amount back to user
        wallet = tx.wallet
        wallet.balance += tx.amount
        wallet.save()

        # Mark as rejected
        tx.description = tx.description + " - REJECTED & REFUNDED"
        tx.save()

        return Response({
            "message": f"Withdrawal rejected and ${tx.amount} refunded to {wallet.user.username}"
        })
    except Transaction.DoesNotExist:
        return Response({"error": "Request not found"}, status=404)


# ==================== ADMIN MANAGEMENT VIEWS ====================

class AdminAddBalanceView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        amount = Decimal(request.data.get('amount', 0))
        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=400)

        try:
            admin_wallet = Wallet.objects.get(user=request.user)
            target_user = User.objects.get(id=user_id)
            target_wallet = Wallet.objects.get(user=target_user)

            if admin_wallet.balance < amount:
                return Response({"error": "Admin has insufficient balance"}, status=400)

            with transaction.atomic():
                # Deduct from Admin
                admin_wallet.balance -= amount
                admin_wallet.save()

                # Add to Target User
                target_wallet.balance += amount
                target_wallet.save()

                # Record transactions
                Transaction.objects.create(
                    wallet=admin_wallet,
                    type='debit',
                    amount=amount,
                    description=f"Added to {target_user.username}"
                )
                Transaction.objects.create(
                    wallet=target_wallet,
                    type='credit',
                    amount=amount,
                    description=f"Added by Admin ({request.user.username})"
                )

            return Response({"message": f"Added ${amount} to {target_user.username}. Deducted from your balance."})

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


class AdminRemoveBalanceView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        amount = Decimal(request.data.get('amount', 0))
        if amount <= 0:
            return Response({"error": "Amount must be greater than 0"}, status=400)

        try:
            admin_wallet = Wallet.objects.get(user=request.user)
            target_user = User.objects.get(id=user_id)
            target_wallet = Wallet.objects.get(user=target_user)

            if target_wallet.balance < amount:
                return Response({"error": "User has insufficient balance"}, status=400)

            with transaction.atomic():
                # Remove from Target User
                target_wallet.balance -= amount
                target_wallet.save()

                # Add to Admin
                admin_wallet.balance += amount
                admin_wallet.save()

                # Record transactions
                Transaction.objects.create(
                    wallet=target_wallet,
                    type='debit',
                    amount=amount,
                    description=f"Removed by Admin ({request.user.username})"
                )
                Transaction.objects.create(
                    wallet=admin_wallet,
                    type='credit',
                    amount=amount,
                    description=f"Received from {target_user.username} (Admin Action)"
                )

            return Response({"message": f"Removed ${amount} from {target_user.username}. Added to your balance."})

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)


class AdminDeleteUserView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            if user.is_superuser:
                return Response({"error": "Cannot delete superuser"}, status=400)

            user.delete()
            return Response({"message": "User deleted successfully"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)



# login with both username and gmail
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        username_or_email = attrs.get('username')

        # Try with username first
        try:
            return super().validate(attrs)
        except:
            # Try with email
            try:
                user = User.objects.get(email=username_or_email)
                attrs['username'] = user.username
                return super().validate(attrs)
            except User.DoesNotExist:
                raise exceptions.AuthenticationFailed(
                    'No active account found with the given credentials'
                )


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# OTP Verification
