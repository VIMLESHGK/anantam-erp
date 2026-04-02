from django.shortcuts import render, get_object_or_404
from .models import Account


def account_ledger(request, account_id):
    account = get_object_or_404(Account, id=account_id)
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

    return render(request, "ledger.html", {
        "account": account,
        "ledger_data": ledger_data,
        "balance": balance
    })



def profit_loss_view(request, company_id):
    company_accounts = Account.objects.filter(company_id=company_id)

    income = sum(
        acc.get_balance() for acc in company_accounts if acc.account_type == "Income"
    )

    expense = sum(
        acc.get_balance() for acc in company_accounts if acc.account_type == "Expense"
    )

    profit = income - expense

    return render(request, "profit_loss.html", {
        "income": income,
        "expense": expense,
        "profit": profit
    })


def dashboard(request):
    company_id = 1
    accounts = Account.objects.filter(company_id=company_id)

    total_assets = 0
    total_liabilities = 0
    total_income = 0
    total_expense = 0

    for acc in accounts:
        balance = acc.get_balance()

        acc_type = acc.account_type.lower()   # 🔥 IMPORTANT

        if acc_type == "asset":
            total_assets += balance

        elif acc_type == "expense":
            total_expense += balance

        elif acc_type == "liability":
            total_liabilities += balance

        elif acc_type == "income":
            total_income += balance

    profit = total_income - total_expense

    return render(request, "dashboard.html", {
        "assets": total_assets,
        "liabilities": total_liabilities,
        "income": total_income,
        "expense": total_expense,
        "profit": profit,
    })