from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path("ledger/<int:account_id>/", views.account_ledger, name="ledger"),
    path("pnl/<int:company_id>/", views.profit_loss_view, name="pnl"),
    path("invoice/<int:invoice_id>/pdf/", views.invoice_pdf, name="invoice_pdf"),
    path('customers/', views.customers, name='customers'),
    path('customer/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('invoice/create/', views.create_invoice, name='create_invoice'),
    path("invoices/", views.invoice_list, name="invoice_list"),
    path("invoice/<int:invoice_id>/cancel/", views.cancel_invoice, name="cancel_invoice"),
    path("invoice/<int:invoice_id>/edit/", views.edit_invoice, name="edit_invoice"),
    path("invoice/<int:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("payments/create/", views.create_payment, name="create_payment"),
    path("payments/", views.payment_list, name="payment_list"),
    path("payments/<int:payment_id>/cancel/", views.cancel_payment, name="cancel_payment"),
    path("aging-report/", views.aging_report, name="aging_report"),
    path('ledger/customer/<int:customer_id>/', views.customer_ledger, name='customer_ledger'),
    path('payments/<int:id>/', views.payment_detail, name='payment_detail'),
    path('get-invoices/', views.get_customer_invoices, name='get_customer_invoices'),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("select-company/", views.select_company, name="select_company"),
    path("set-company/<int:company_id>/", views.set_company, name="set_company"),
    path("aging/<str:bucket>/", views.aging_detail, name="aging_detail"),
    path("customers/<int:customer_id>/edit/", views.edit_customer, name="edit_customer"),
    path("customers/<int:customer_id>/delete/", views.delete_customer, name="delete_customer"),
    path("customers/<int:customer_id>/update/", views.update_customer, name="update_customer"),
    path("receive-payment/", views.receive_payment, name="receive_payment"),
]