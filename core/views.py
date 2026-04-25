from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from weasyprint import HTML
from datetime import date, datetime
from collections import defaultdict
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import (
    Account, Invoice, Customer, InvoiceItem,
    JournalEntryLine, Payment, Company
)
from .utils import get_current_company


# =========================
# 🏠 Home
# =========================
@login_required
def home(request):
    return render(request, 'core/home.html')


# =========================
# 📊 Dashboard
# =========================
@login_required
def dashboard(request):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    lines = JournalEntryLine.objects.filter(
        journal_entry__company=company,
        journal_entry__is_cancelled=False
    )

    assets = liabilities = income = expense = 0

    for line in lines.select_related("account"):
        acc = line.account

        if acc.account_type == "asset":
            assets += line.debit - line.credit
        elif acc.account_type == "liability":
            liabilities += line.credit - line.debit
        elif acc.account_type == "income":
            income += line.credit - line.debit
        elif acc.account_type == "expense":
            expense += line.debit - line.credit

    profit = income - expense

    recent_invoices = Invoice.objects.filter(company=company).exclude(
        status="cancelled"
    ).order_by("-date")[:5]

    recent_payments = Payment.objects.filter(company=company).exclude(
        status="cancelled"
    ).order_by("-date")[:5]

    return render(request, "core/dashboard.html", {
        "assets": assets,
        "liabilities": liabilities,
        "income": income,
        "expense": expense,
        "profit": profit,
        "recent_invoices": recent_invoices,
        "recent_payments": recent_payments,
    })


# =========================
# 📒 Account Ledger
# =========================
@login_required
def account_ledger(request, account_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    account = get_object_or_404(Account, id=account_id, company=company)
    entries = account.get_ledger_entries()

    balance = 0
    ledger_data = []

    for line in entries:
        if account.account_type in ["asset", "expense"]:
            balance += line.debit - line.credit
        else:
            balance += line.credit - line.debit

        ledger_data.append({
            "date": line.journal_entry.date,
            "account": line.account.name,
            "debit": line.debit,
            "credit": line.credit,
            "balance": balance,
            "reference": line.journal_entry.reference
        })

    return render(request, "core/ledger.html", {
        "account": account,
        "ledger_data": ledger_data,
        "balance": balance
    })


# =========================
# 📈 Profit & Loss
# =========================
@login_required
def profit_loss_view(request):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    company_accounts = Account.objects.filter(company=company)

    income = sum(acc.get_balance() for acc in company_accounts if acc.account_type == "income")
    expense = sum(acc.get_balance() for acc in company_accounts if acc.account_type == "expense")

    return render(request, "core/profit_loss.html", {
        "income": income,
        "expense": expense,
        "profit": income - expense
    })


# =========================
# 🧾 Invoice PDF
# =========================
@login_required
def invoice_pdf(request, invoice_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)

    template = get_template("core/invoice_pdf.html")
    html = template.render({
        "invoice": invoice,
        "items": invoice.items.all()
    })

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="invoice_{invoice.id}.pdf"'

    HTML(string=html).write_pdf(response)
    return response


# =========================
# 👥 Customers
# =========================
@login_required
def customers(request):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    if request.method == "POST":
        Customer.objects.create(
            name=request.POST.get("name"),
            phone=request.POST.get("phone"),
            email=request.POST.get("email"),
            gstin=request.POST.get("gstin"),
            company=company
        )
        return redirect("customers")

    customers = Customer.objects.filter(company=company)
    return render(request, "core/customers.html", {"customers": customers})


# =========================
# 👤 Customer Detail
# =========================
@login_required
def customer_detail(request, customer_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    customer = get_object_or_404(Customer, id=customer_id, company=company)

    debtor_account = Account.objects.filter(
        company=company,
        sub_type="receivable"
    ).first()

    lines = JournalEntryLine.objects.filter(
        journal_entry__customer=customer,
        account=debtor_account,
        journal_entry__is_cancelled=False
    ).select_related("journal_entry").order_by("journal_entry__date", "id")

    ledger = []
    balance = 0

    for line in lines:
        balance += line.debit - line.credit

        ledger.append({
            "date": line.journal_entry.date,
            "reference": line.journal_entry.reference,
            "debit": line.debit or "",
            "credit": line.credit or "",
            "balance": balance,
        })

    return render(request, "core/customer_detail.html", {
        "customer": customer,
        "ledger": ledger,
        "balance": balance,
    })


# =========================
# 🧾 Create Invoice
# =========================
from decimal import Decimal

@login_required
def create_invoice(request):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    customers = Customer.objects.filter(company=company)

    if request.method == "POST":
        customer = get_object_or_404(Customer, id=request.POST.get("customer"), company=company)

        invoice = Invoice.objects.create(
            company=company,
            customer=customer,
            invoice_number=f"INV-{Invoice.objects.filter(company=company).count()+1}",
            date=date.today(),
            narration=request.POST.get("narration")
        )

        descriptions = request.POST.getlist("description[]")
        quantities = request.POST.getlist("quantity[]")
        rates = request.POST.getlist("rate[]")

        for i in range(len(descriptions)):
            if descriptions[i]:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=descriptions[i],
                    quantity=Decimal(quantities[i] or "0"),
                    rate=Decimal(rates[i] or "0")
                )

        invoice.update_total()

        # ✅ POST LOGIC
        if request.POST.get("action") == "post":
            invoice.post()

            paid_amount = Decimal(request.POST.get("paid_amount") or "0")

            if paid_amount > 0:
                # safety check
                if paid_amount > invoice.outstanding_amount:
                    paid_amount = invoice.outstanding_amount

                Payment.objects.create(
                    company=company,
                    customer=customer,
                    invoice=invoice,
                    amount=paid_amount,
                    date=date.today(),
                    status="posted"
                )

                invoice.outstanding_amount = (invoice.outstanding_amount or Decimal("0")) - paid_amount

                if invoice.outstanding_amount <= 0:
                    invoice.status = "paid"
                    invoice.outstanding_amount = Decimal("0")
                else:
                    invoice.status = "partial"

                invoice.save()

        return redirect("invoice_list")

    return render(request, "core/create_invoice.html", {
        "customers": customers
    })



# =========================
# 📄 Invoice List (FINAL)
# =========================
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.db.models import Sum, Count
from .models import Invoice, Payment
from .utils import get_current_company


@login_required
def invoice_list(request):
    company = get_current_company(request)

    if not company:
        return redirect("select_company")

    status_filter = request.GET.get("status")

    # =========================
    # BASE QUERY
    # =========================
    invoices = Invoice.objects.filter(company=company)

    # =========================
    # FILTER LOGIC
    # =========================
    if status_filter == "paid":
        invoices = invoices.filter(status="paid")

    elif status_filter == "pending":
        invoices = invoices.filter(status__in=["posted", "partial"])

    elif status_filter == "cancelled":
        invoices = invoices.filter(status="cancelled")

    # =========================
    # ORDER
    # =========================
    invoices = invoices.order_by("-id")

    # =========================
    # 🔥 ATTACH PAYMENT MODE (IMPORTANT FIX)
    # =========================
    for inv in invoices:
        last_payment = Payment.objects.filter(
            invoice=inv,
            status="posted"
        ).order_by("-id").first()

        inv.last_payment_mode = last_payment.payment_mode if last_payment else None

    # =========================
    # SUMMARY (EXCLUDE CANCELLED)
    # =========================
    valid_invoices = Invoice.objects.filter(company=company).exclude(status="cancelled")

    totals = valid_invoices.aggregate(
        total_amount=Sum("total_amount"),
        total_outstanding=Sum("outstanding_amount"),
        total_count=Count("id")
    )

    total_amount = totals["total_amount"] or 0
    total_outstanding = totals["total_outstanding"] or 0
    total_paid = total_amount - total_outstanding
    total_count = totals["total_count"] or 0

    # =========================
    # RESPONSE
    # =========================
    return render(request, "core/invoice_list.html", {
        "invoices": invoices,
        "total_amount": total_amount,
        "total_outstanding": total_outstanding,
        "total_paid": total_paid,
        "total_count": total_count,
        "current_filter": status_filter or "all"
    })

    
# =========================
# ❌ Cancel Invoice
# =========================
@login_required
def cancel_invoice(request, invoice_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)
    invoice.cancel()
    return redirect("invoice_list")


# =========================
# 📄 Invoice Detail
# =========================
@login_required
def invoice_detail(request, invoice_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)

    return render(request, "core/invoice_detail.html", {
        "invoice": invoice,
        "items": invoice.items.all()
    })


# =========================
# 💳 Payments
# =========================
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

# =========================
# 💳 Payments
# =========================
@login_required
def payment_list(request):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    # ✅ Filter
    status_filter = request.GET.get("status", "all")

    payments = Payment.objects.filter(company=company)

    if status_filter == "posted":
        payments = payments.filter(status="posted")
    elif status_filter == "cancelled":
        payments = payments.filter(status="cancelled")
    elif status_filter == "draft":
        payments = payments.filter(status="draft")

    payments = payments.order_by("-id")

    # ✅ Summary (IMPORTANT)
    all_payments = Payment.objects.filter(company=company)
    total_received = all_payments.exclude(status="cancelled").aggregate(total=Sum("amount"))["total"] or 0
    total_posted = all_payments.filter(status="posted").aggregate(total=Sum("amount"))["total"] or 0
    total_cancelled = all_payments.filter(status="cancelled").count()
    
    context = {
        "payments": payments,
        "total_received": total_received,
        "total_posted": total_posted,
        "total_cancelled": total_cancelled,
        "current_filter": status_filter,
    }

    return render(request, "core/payment_list.html", context)

@login_required
def payment_detail(request, id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    payment = get_object_or_404(Payment, id=id, company=company)
    return render(request, "core/payment_detail.html", {"payment": payment})

@login_required
def cancel_payment(request, payment_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    payment = get_object_or_404(Payment, id=payment_id, company=company)
    payment.cancel()
    return redirect("payment_list")

from collections import defaultdict
from datetime import date
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

# =========================
# 📊 Aging Report
# =========================
@login_required
def aging_report(request):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    today = date.today()

    invoices = Invoice.objects.filter(
        company=company,
        status__in=["posted", "partial"]
    ).select_related("customer")

    customer_map = defaultdict(lambda: {
        "bucket_0_30": 0,
        "bucket_31_60": 0,
        "bucket_61_90": 0,
        "bucket_90_plus": 0,
        "total": 0,
        "invoices": []
    })

    # ✅ GLOBAL SUMMARY (TOP CARDS)
    summary = {
        "bucket_0_30": 0,
        "bucket_31_60": 0,
        "bucket_61_90": 0,
        "bucket_90_plus": 0,
    }

    for inv in invoices:
        days = (today - inv.date).days
        amount = inv.outstanding_amount or 0
        cust = inv.customer

        # Determine bucket
        if days <= 30:
            bucket = "bucket_0_30"
        elif days <= 60:
            bucket = "bucket_31_60"
        elif days <= 90:
            bucket = "bucket_61_90"
        else:
            bucket = "bucket_90_plus"

        # Customer-level totals
        customer_map[cust][bucket] += amount
        customer_map[cust]["total"] += amount

        # ✅ Global totals (THIS FIXES YOUR ISSUE)
        summary[bucket] += amount

        # Invoice list
        customer_map[cust]["invoices"].append({
            "invoice": inv,
            "days": days,
            "amount": amount
        })

    customer_data = [
        {
            "customer": c,
            "data": d,
            "invoices": d["invoices"]
        }
        for c, d in customer_map.items()
    ]

    return render(request, "core/aging_report.html", {
        "customer_data": customer_data,
        "summary": summary   # ✅ IMPORTANT
    })

# =========================
# 📒 Customer Ledger
# =========================
@login_required
def customer_ledger(request, customer_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    customer = get_object_or_404(Customer, id=customer_id, company=company)

    invoices = Invoice.objects.filter(customer=customer, company=company).exclude(status="cancelled")
    payments = Payment.objects.filter(customer=customer, company=company, status="posted")

    transactions = []

    for inv in invoices:
        transactions.append({
            'date': inv.date,
            'type': 'Invoice',
            'ref': inv.invoice_number,
            'debit': inv.total_amount,
            'credit': 0
        })

    for pay in payments:
        transactions.append({
            'date': pay.date,
            'type': 'Payment',
            'ref': pay.receipt_no or f"PAY-{pay.id}",
            'debit': 0,
            'credit': pay.amount
        })

    transactions = sorted(transactions, key=lambda x: x['date'])

    balance = 0
    for t in transactions:
        balance += t['debit'] - t['credit']
        t['balance'] = balance

    return render(request, 'core/customer_ledger.html', {
        'customer': customer,
        'transactions': transactions
    })



from django.contrib.auth import authenticate, login, logout
from .models import UserCompany


from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .models import UserCompany


# 🔐 LOGIN
def login_view(request):
    # If already logged in
    if request.user.is_authenticated:
        user_companies = UserCompany.objects.filter(user=request.user)

        if user_companies.count() == 1:
            request.session["company_id"] = user_companies.first().company.id
            return redirect("dashboard")

        return redirect("select_company")

    # POST (Login attempt)
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            user_companies = UserCompany.objects.filter(user=user)

            # ✅ AUTO SELECT COMPANY (Single)
            if user_companies.count() == 1:
                request.session["company_id"] = user_companies.first().company.id
                return redirect("dashboard")

            # 👉 Multiple companies
            return redirect("select_company")

        else:
            return render(request, "core/login.html", {
                "error": "Invalid username or password"
            })

    return render(request, "core/login.html")


# 🚪 LOGOUT
def logout_view(request):
    logout(request)
    request.session.flush()
    return redirect("login")


# 🏢 SELECT COMPANY
@login_required
def select_company(request):
    companies = UserCompany.objects.filter(user=request.user)

    return render(request, "core/select_company.html", {
        "companies": companies
    })


# 🔄 SET COMPANY
@login_required
def set_company(request, company_id):
    user_companies = UserCompany.objects.filter(user=request.user, company_id=company_id)

    if not user_companies.exists():
        return redirect("select_company")

    request.session["company_id"] = company_id
    request.session.modified = True

    return redirect("dashboard")

from decimal import Decimal

@login_required
def edit_invoice(request, invoice_id):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)

    if invoice.status != "draft":
        return redirect("invoice_list")

    customers = Customer.objects.filter(company=company)
    items = invoice.items.all()

    if request.method == "POST":
        invoice.customer_id = request.POST.get("customer")
        invoice.narration = request.POST.get("narration")
        invoice.save()

        # delete old items
        invoice.items.all().delete()

        descriptions = request.POST.getlist("description[]")
        quantities = request.POST.getlist("quantity[]")
        rates = request.POST.getlist("rate[]")

        for i in range(len(descriptions)):
            if descriptions[i]:
                InvoiceItem.objects.create(
                    invoice=invoice,
                    description=descriptions[i],
                    quantity=Decimal(quantities[i] or "0"),
                    rate=Decimal(rates[i] or "0")
                )

        invoice.update_total()

        # ✅ POST LOGIC
        if request.POST.get("action") == "post":
            invoice.post()

            paid_amount = Decimal(request.POST.get("paid_amount") or "0")

            if paid_amount > 0:
                if paid_amount > invoice.outstanding_amount:
                    paid_amount = invoice.outstanding_amount

                Payment.objects.create(
                    company=company,
                    customer=invoice.customer,
                    invoice=invoice,
                    amount=paid_amount,
                    date=date.today(),
                    status="posted"
                )

                invoice.outstanding_amount = (invoice.outstanding_amount or Decimal("0")) - paid_amount

                if invoice.outstanding_amount <= 0:
                    invoice.status = "paid"
                    invoice.outstanding_amount = Decimal("0")
                else:
                    invoice.status = "partial"

                invoice.save()

        return redirect("invoice_list")

    return render(request, "core/create_invoice.html", {
        "invoice": invoice,
        "customers": customers,
        "items": items
    })


from decimal import Decimal
from django.core.exceptions import ValidationError


@login_required
def create_payment(request):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    customers = Customer.objects.filter(company=company)

    if request.method == "POST":

        customer_id = request.POST.get("customer")
        amount_str = request.POST.get("amount")

        if not customer_id:
            return render(request, "core/create_payment.html", {
                "customers": customers,
                "error": "Please select a customer"
            })

        try:
            amount = Decimal(amount_str)
        except:
            return render(request, "core/create_payment.html", {
                "customers": customers,
                "error": "Invalid amount"
            })

        if amount <= 0:
            return render(request, "core/create_payment.html", {
                "customers": customers,
                "error": "Amount must be greater than 0"
            })

        customer = get_object_or_404(Customer, id=customer_id, company=company)

        payment = Payment.objects.create(
            company=company,
            customer=customer,
            amount=amount,
            date=date.today()
        )

        try:
            payment.post()
        except ValidationError as e:
            payment.delete()
            return render(request, "core/create_payment.html", {
                "customers": customers,
                "error": str(e)
            })

        return redirect("customer_ledger", customer.id)

    return render(request, "core/create_payment.html", {
        "customers": customers
    })


@login_required
def get_customer_invoices(request):
    company = get_current_company(request)
    if not company:
        return JsonResponse({"error": "No company selected"}, status=400)

    customer_id = request.GET.get("customer_id")

    invoices = Invoice.objects.filter(
        company=company,
        customer_id=customer_id,
        status__in=["posted", "partial"]
    ).exclude(outstanding_amount=0)

    data = []

    for inv in invoices:
        data.append({
            "id": inv.id,
            "invoice_number": inv.invoice_number,
            "outstanding": float(inv.outstanding_amount)
        })

    return JsonResponse(data, safe=False)



@login_required
def aging_detail(request, bucket):
    company = get_current_company(request)
    if not company:
        return redirect("select_company")

    today = date.today()

    invoices = Invoice.objects.filter(
        company=company,
        status__in=["posted", "partial"]
    ).select_related("customer")

    filtered = []

    for inv in invoices:
        days = (today - inv.date).days

        if bucket == "0_30" and days <= 30:
            match = True
        elif bucket == "31_60" and 31 <= days <= 60:
            match = True
        elif bucket == "61_90" and 61 <= days <= 90:
            match = True
        elif bucket == "90_plus" and days > 90:
            match = True
        else:
            match = False

        if match:
            filtered.append({
                "invoice": inv,
                "customer": inv.customer,
                "days": days,
                "amount": inv.outstanding_amount
            })

    return render(request, "core/aging_detail.html", {
        "invoices": filtered,
        "bucket": bucket
    })



@login_required
def edit_customer(request, customer_id):
    company = get_current_company(request)

    customer = get_object_or_404(Customer, id=customer_id, company=company)

    if request.method == "POST":
        customer.name = request.POST.get("name")
        customer.phone = request.POST.get("phone")
        customer.email = request.POST.get("email")
        customer.gstin = request.POST.get("gstin")
        customer.save()

        messages.success(request, "Customer updated successfully")
        return redirect("customers")

    return render(request, "core/edit_customer.html", {
        "customer": customer
    })


@login_required
def delete_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)

    if customer.invoice_set.exists():
        messages.error(request, "Cannot delete customer with invoices.")
        return redirect("customers")

    customer.delete()
    messages.success(request, "Customer deleted successfully.")
    return redirect("customers")




from django.http import JsonResponse

@login_required
def update_customer(request, customer_id):
    if request.method == "POST":
        customer = get_object_or_404(Customer, id=customer_id)

        customer.name = request.POST.get("name")
        customer.phone = request.POST.get("phone")
        customer.email = request.POST.get("email")
        customer.gstin = request.POST.get("gstin")

        customer.save()

        return JsonResponse({
            "status": "success",
            "message": "Customer updated successfully"
        })

    return JsonResponse({"status": "error"}, status=400)

from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from datetime import date

@login_required
def receive_payment(request):
    company = get_current_company(request)
    if not company:
        return JsonResponse({"error": "No company selected"}, status=400)

    if request.method != "POST":
        return JsonResponse({"error": "Invalid request"}, status=400)

    try:
        invoice_id = request.POST.get("invoice_id")
        amount_str = request.POST.get("amount") or "0"
        payment_mode = request.POST.get("payment_mode", "cash")

        # ✅ Safe Decimal conversion
        amount = Decimal(amount_str)

    except (InvalidOperation, TypeError):
        return JsonResponse({"error": "Invalid amount format"}, status=400)

    # ✅ Get invoice
    invoice = get_object_or_404(Invoice, id=invoice_id, company=company)

    # ✅ Validations
    if amount <= 0:
        return JsonResponse({"error": "Amount must be greater than 0"}, status=400)

    if amount > (invoice.outstanding_amount or Decimal("0")):
        return JsonResponse({"error": "Amount exceeds outstanding"}, status=400)

    # =========================
    # 💳 Create Payment
    # =========================
    Payment.objects.create(
        company=company,
        customer=invoice.customer,
        invoice=invoice,
        amount=amount,
        date=date.today(),
        status="posted",
        payment_mode=payment_mode  # ✅ NEW FIELD
    )

    # =========================
    # 📊 Update Invoice
    # =========================
    outstanding = (invoice.outstanding_amount or Decimal("0")) - amount

    if outstanding <= 0:
        invoice.status = "paid"
        invoice.outstanding_amount = Decimal("0")
    else:
        invoice.status = "partial"
        invoice.outstanding_amount = outstanding

    invoice.save()

    # =========================
    # 🔁 Response
    # =========================
    return JsonResponse({
        "success": True,
        "new_outstanding": float(invoice.outstanding_amount),
        "status": invoice.status,
        "payment_mode": payment_mode
    })