from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum

class Company(models.Model):
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True, null=True)
    
    gstin = models.CharField(max_length=15, unique=True)
    pan = models.CharField(max_length=10)

    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    address_line1 = models.CharField(max_length=255, blank=True, null=True)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    pincode = models.CharField(max_length=10, blank=True, null=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    



class UserCompany(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("accountant", "Accountant"),
        ("staff", "Staff"),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "company")

    def __str__(self):
        return f"{self.user.username} - {self.company.name}"
    
class Account(models.Model):
    ACCOUNT_TYPES = (
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("income", "Income"),
        ("expense", "Expense"),
    )

    company = models.ForeignKey(Company, on_delete=models.CASCADE)

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50)

    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)

    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children"
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def get_ledger_entries(self):
        from .models import JournalEntryLine

        return JournalEntryLine.objects.filter(account=self).order_by("journal_entry__date", "id")
    
    from django.db.models import Sum

    def get_balance(self):
        totals = self.get_ledger_entries().aggregate(
            debit=Sum("debit"),
            credit=Sum("credit")
        )

        total_debit = totals["debit"] or 0
        total_credit = totals["credit"] or 0

        if self.account_type.lower() in ["asset", "expense"]:
            return total_debit - total_credit
        else:
            return total_credit - total_debit
        

    def get_total_by_type(company, account_type):
        from django.db.models import Sum

        accounts = Account.objects.filter(company=company, account_type=account_type)

        total = 0
        for acc in accounts:
            total += acc.get_balance()

            return total

class JournalEntry(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    date = models.DateField()

    reference = models.CharField(max_length=100, blank=True, null=True)
    narration = models.TextField(blank=True, null=True)

    invoice = models.ForeignKey(
        "Invoice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="journal_entries"
    )

    def __str__(self):
        return f"JE-{self.id} - {self.date}"
    

class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.CASCADE,
        related_name="lines"
    )
    account = models.ForeignKey(Account, on_delete=models.CASCADE)

    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.account.name} | Dr {self.debit} Cr {self.credit}"
    
    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("Line cannot have both debit and credit")

        if self.debit == 0 and self.credit == 0:
            raise ValidationError("Either debit or credit must be greater than zero")
        


class Customer(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    gstin = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name


class Invoice(models.Model):
    company = models.ForeignKey("Company", on_delete=models.CASCADE)
    customer = models.ForeignKey("Customer", on_delete=models.CASCADE)

    invoice_number = models.CharField(max_length=50, unique=True)
    date = models.DateField()

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return self.invoice_number

    # ✅ ONLY calculation (NO save inside)
    def update_total(self):
        total = self.items.aggregate(
            total=Sum("amount")
        )["total"] or 0

        self.total_amount = total

    # ✅ ONLY journal creation (NO save inside)
    def create_journal_entry(self):
        from .models import JournalEntry, JournalEntryLine, Account

        customer_account = Account.objects.get(name="Sundry Debtors")
        sales_account = Account.objects.get(name="Sales")

        entry = JournalEntry.objects.create(
            company=self.company,
            date=self.date,
            reference=f"Invoice {self.invoice_number}",
            narration="Sales Invoice",
            invoice=self   # ✅ LINK ADDED
            )

        # Debit Customer
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=customer_account,
            debit=self.total_amount,
            credit=0
        )

        # Credit Sales
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=sales_account,
            debit=0,
            credit=self.total_amount
        )


class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)

    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.rate
        super().save(*args, **kwargs)        