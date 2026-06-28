from .models import Company, Account


def get_current_company(request):
    company_id = request.session.get("company_id")

    if not company_id:
        return None

    return Company.objects.filter(id=company_id).first()


def create_default_accounts(company):
    accounts = [
        ("Cash in Hand", "asset", "cash"),
        ("Bank Account", "asset", "bank"),
        ("Accounts Receivable", "asset", "receivable"),
        ("Inventory", "asset", "inventory"),
        ("Furniture", "asset", "fixed_asset"),
        ("Computer", "asset", "fixed_asset"),

        ("Accounts Payable", "liability", "payable"),
        ("GST Payable", "liability", "current_liability"),

        ("Capital Account", "equity", "capital"),

        ("Sales", "income", "sales"),
        ("Service Income", "income", "service_income"),

        ("Purchase", "expense", "purchase"),
        ("Office Expense", "expense", "office_expense"),
        ("Electricity Expense", "expense", "electricity"),
        ("Internet Expense", "expense", "internet"),
        ("Salary Expense", "expense", "salary"),
        ("Depreciation", "expense", "depreciation"),
    ]

    for name, acc_type, subtype in accounts:
        Account.objects.get_or_create(
            company=company,
            name=name,
            defaults={
                "account_type": acc_type,
                "sub_type": subtype,
            },
        )