from django.urls import path
from .views import account_ledger,profit_loss_view,dashboard


urlpatterns = [
    path("account/<int:account_id>/ledger/", account_ledger),
    path("pnl/<int:company_id>/", profit_loss_view),
    path("dashboard/", dashboard),
]

