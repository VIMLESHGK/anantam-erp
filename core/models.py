from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from decimal import Decimal
from datetime import date


# =========================
# BASE MODEL (NEW 🔥)
# =========================

class BaseModel(models.Model):
    company = models.ForeignKey("Company", on_delete=models.CASCADE)

    class Meta:
        abstract = True


# =========================
# COMPANY & USER
# =========================

class Company(models.Model):
    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15, unique=True)

    def __str__(self):
        return self.name


class UserCompany(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, default="staff")

    class Meta:
        unique_together = ("user", "company")


# =========================
# ACCOUNT
# =========================

class Account(BaseModel):
    ACCOUNT_TYPES = (
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    )

    SUB_TYPES = (
        # Assets
        ("cash", "Cash"),
        ("bank", "Bank"),
        ("receivable", "Accounts Receivable"),
        ("inventory", "Inventory"),
        ("fixed_asset", "Fixed Asset"),

        # Liabilities
        ("payable", "Accounts Payable"),
        ("current_liability", "Current Liability"),

        # Equity
        ("capital", "Capital"),
        ("retained_earnings", "Retained Earnings"),

        # Income
        ("sales", "Sales"),
        ("service_income", "Service Income"),
        ("other_income", "Other Income"),

        # Expenses
        ("purchase", "Purchase"),
        ("office_expense", "Office Expense"),
        ("salary", "Salary"),
        ("electricity", "Electricity"),
        ("internet", "Internet"),
        ("rent", "Rent"),
        ("depreciation", "Depreciation"),
        ("misc", "Miscellaneous"),
    )

    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES)
    sub_type = models.CharField(max_length=20, choices=SUB_TYPES, null=True, blank=True)

    def __str__(self):
        return self.name

    def get_balance(self):
        totals = self.journalentryline_set.aggregate(
            debit=Sum("debit"),
            credit=Sum("credit")
        )

        debit = totals["debit"] or 0
        credit = totals["credit"] or 0

        if self.account_type in ["asset", "expense"]:
            return debit - credit
        return credit - debit


# =========================
# CUSTOMER (KEEP FOR NOW)
# =========================

class Customer(BaseModel):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    gstin = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.name

    def get_outstanding(self):
        debtor_account = Account.objects.filter(
            company=self.company,
            sub_type="receivable"
        ).first()

        lines = JournalEntryLine.objects.filter(
            journal_entry__customer=self,
            account=debtor_account,
            journal_entry__is_cancelled=False  # ✅ ONLY ACTIVE ENTRIES
        )

        debit = sum(line.debit for line in lines)
        credit = sum(line.credit for line in lines)

        return debit - credit


# =========================
# JOURNAL
# =========================
from django.db import models


class JournalEntry(BaseModel):
    company = models.ForeignKey("Company", on_delete=models.CASCADE)
    date = models.DateField()

    reference = models.CharField(max_length=200)
    narration = models.TextField(blank=True, null=True)

    customer = models.ForeignKey("Customer", on_delete=models.CASCADE, null=True, blank=True)
    invoice = models.ForeignKey("Invoice", on_delete=models.SET_NULL, null=True, blank=True)

    is_cancelled = models.BooleanField(default=False)  # ✅ IMPORTANT

    def __str__(self):
        return self.reference

    def reverse_entry(self):
        reverse = JournalEntry.objects.create(
            company=self.company,
            date=self.date,
            reference=f"REV-{self.reference}",
            customer=self.customer,
            invoice=self.invoice,
            is_cancelled=True
        )

        for line in self.lines.all():
            # ✅ skip zero lines safety
            if line.debit > 0:
                JournalEntryLine.objects.create(
                    journal_entry=reverse,
                    account=line.account,
                    debit=0,
                    credit=line.debit
                )
            elif line.credit > 0:
                JournalEntryLine.objects.create(
                    journal_entry=reverse,
                    account=line.account,
                    debit=line.credit,
                    credit=0
                )

        return reverse


class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(
        JournalEntry,
        related_name="lines",
        on_delete=models.CASCADE
    )

    account = models.ForeignKey("Account", on_delete=models.CASCADE)

    debit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("Cannot have both debit and credit")

        if self.debit == 0 and self.credit == 0:
            raise ValidationError("Must have debit or credit")


# =========================
# INVOICE (UPGRADED 🔥 WITH ADVANCE ADJUSTMENT)
# =========================
from decimal import Decimal
from django.db import models
from django.db.models import Sum


class Invoice(BaseModel):
    STATUS = (
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("partial", "Partially Paid"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    )

    customer = models.ForeignKey("Customer", on_delete=models.CASCADE)

    invoice_number = models.CharField(max_length=50)
    date = models.DateField()

    narration = models.TextField(blank=True, null=True)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    outstanding_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS, default="draft")

    journal_entry = models.ForeignKey(
        "JournalEntry",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice_entry"
    )

    def __str__(self):
        return self.invoice_number

    # -------------------------
    # TOTAL CALCULATION
    # -------------------------
    def update_total(self):
        total = self.items.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        self.total_amount = total
        self.save(update_fields=["total_amount"])

    # -------------------------
    # POST INVOICE
    # -------------------------
    def post(self):
        if self.status != "draft":
            return

        debtor = Account.objects.get(company=self.company, sub_type="receivable")
        sales = Account.objects.get(company=self.company, sub_type="sales")

        entry = JournalEntry.objects.create(
            company=self.company,
            date=self.date,
            reference=f"Invoice {self.invoice_number}",
            narration=self.narration,
            customer=self.customer,
            invoice=self
        )

        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=debtor,
            debit=self.total_amount
        )

        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=sales,
            credit=self.total_amount
        )

        self.journal_entry = entry

        # Default values
        self.outstanding_amount = self.total_amount
        self.status = "posted"
        self.save()

        # =========================
        # 🔥 APPLY ADVANCE PAYMENT
        # =========================
        from .models import Payment, PaymentAllocation

        advance_payments = Payment.objects.filter(
            customer=self.customer,
            status="posted"
        ).annotate(
            allocated=Sum("allocations__amount")
        )

        remaining_invoice = self.total_amount

        for payment in advance_payments:
            allocated_amount = payment.allocated or Decimal("0.00")
            available = payment.amount - allocated_amount

            if available <= 0:
                continue

            if remaining_invoice <= 0:
                break

            use_amount = min(available, remaining_invoice)

            # Create allocation
            PaymentAllocation.objects.create(
                payment=payment,
                invoice=self,
                amount=use_amount
            )

            remaining_invoice -= use_amount

        # =========================
        # UPDATE STATUS AFTER ADJUSTMENT
        # =========================
        if remaining_invoice <= 0:
            self.status = "paid"
            self.outstanding_amount = Decimal("0.00")

        elif remaining_invoice < self.total_amount:
            self.status = "partial"
            self.outstanding_amount = remaining_invoice

        else:
            self.status = "posted"
            self.outstanding_amount = self.total_amount

        self.save()

    # -------------------------
    # CANCEL INVOICE
    # -------------------------
    from django.db.models import Q

    def cancel(self):
        if self.status == "cancelled":
            return

        from .models import PaymentAllocation

        # ❗ Block ONLY if ACTIVE (POSTED) payments exist
        has_active_allocations = PaymentAllocation.objects.filter(
            invoice=self,
            payment__status="posted"
        ).exists()

        if has_active_allocations:
            raise Exception(
                f"Invoice {self.invoice_number} cannot be cancelled because payments are applied. "
                "Please cancel the payments first."
            )

        # ✅ Safe to cancel
        if self.journal_entry:
            self.journal_entry.is_cancelled = True
            self.journal_entry.save()

        self.status = "cancelled"
        self.outstanding_amount = Decimal("0.00")
        self.save()

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name="items", on_delete=models.CASCADE)

    description = models.CharField(max_length=255)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.amount = Decimal(self.quantity) * Decimal(self.rate)
        super().save(*args, **kwargs)
        self.invoice.update_total()  # ✅ FIXED


# =========================
# PAYMENT (UPGRADED 🔥)
# =========================
from django.db import models, transaction
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Sum

STATUS_CHOICES = [
    ("draft", "Draft"),
    ("posted", "Posted"),
    ("cancelled", "Cancelled"),
]

PAYMENT_MODES = [
    ("cash", "Cash"),
    ("upi", "UPI"),
    ("bank", "Bank"),
]


class Payment(BaseModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)

    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    
    payment_mode = models.CharField(
        max_length=20,
        choices=[
            ("cash", "Cash"),
            ("upi", "UPI"),
            ("bank", "Bank")
        ],
        default="cash"
    )

    # Backward compatibility
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    receipt_no = models.CharField(max_length=50, unique=True, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    journal_entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"Payment {self.id}"

    # =========================
    # VALIDATION (ONLY IF ALLOCATION EXISTS)
    # =========================
    def validate_allocations(self):
        if not self.allocations.exists():
            return

        total = self.allocations.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        if total != self.amount:
            raise ValidationError("Allocation total must match payment amount")

        for alloc in self.allocations.all():
            if alloc.amount <= 0:
                raise ValidationError("Allocation must be greater than zero")

            if alloc.amount > alloc.invoice.outstanding_amount:
                raise ValidationError(
                    f"Allocation exceeds outstanding for {alloc.invoice.invoice_number}"
                )

    # =========================
    # UPDATE INVOICE STATUS
    # =========================
    def update_invoice(self, invoice):
        total_paid = PaymentAllocation.objects.filter(
            invoice=invoice,
            payment__status="posted"
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

        outstanding = invoice.total_amount - total_paid

        if outstanding <= 0:
            invoice.status = "paid"
            invoice.outstanding_amount = Decimal("0.00")
        elif total_paid > 0:
            invoice.status = "partial"
            invoice.outstanding_amount = outstanding
        else:
            invoice.status = "posted"
            invoice.outstanding_amount = invoice.total_amount

        invoice.save()

    # =========================
    # POST PAYMENT
    # =========================
    @transaction.atomic
    def post(self):
        if self.status == "posted":
            return

        # ✅ Validate allocations only if present
        self.validate_allocations()

        # Accounts
        bank = Account.objects.get(company=self.company, sub_type="bank")
        debtor = Account.objects.get(company=self.company, sub_type="receivable")

        # ✅ Always create journal entry (even for advance)
        entry = JournalEntry.objects.create(
            company=self.company,
            date=self.date,
            reference=f"PAY-{self.id}",
            customer=self.customer,
            invoice=self.invoice  # can be None
        )

        # Debit bank
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=bank,
            debit=self.amount
        )

        # Credit receivable
        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=debtor,
            credit=self.amount
        )

        # Receipt number generation
        if not self.receipt_no:
            last = Payment.objects.exclude(receipt_no__isnull=True).order_by('-id').first()

            if last and last.receipt_no:
                last_no = int(last.receipt_no.split('-')[-1])
                new_no = last_no + 1
            else:
                new_no = 1

            self.receipt_no = f"RCPT-{new_no:04d}"

        # Update payment
        self.journal_entry = entry
        self.status = "posted"
        self.save()

        # =========================
        # UPDATE INVOICES (IF ANY)
        # =========================
        if self.allocations.exists():
            for alloc in self.allocations.all():
                self.update_invoice(alloc.invoice)

        elif self.invoice:
            self.update_invoice(self.invoice)

    # =========================
    # CANCEL PAYMENT
    # =========================
    @transaction.atomic
    def cancel(self):
        if self.status == "cancelled":
            return

        if self.journal_entry:
            self.journal_entry.is_cancelled = True
            self.journal_entry.save()

        self.status = "cancelled"
        self.save()

        # Recalculate invoices
        if self.allocations.exists():
            for alloc in self.allocations.all():
                self.update_invoice(alloc.invoice)

        elif self.invoice:
            self.update_invoice(self.invoice)


# =========================
# EXPENSE
# =========================

class Expense(BaseModel):
    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    expense_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="expenses")
    payment_account = models.ForeignKey(Account, on_delete=models.CASCADE)

    def post(self):
        entry = JournalEntry.objects.create(
            company=self.company,
            date=self.date,
            reference=f"Expense {self.id}"
        )

        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=self.expense_account,
            debit=self.amount
        )

        JournalEntryLine.objects.create(
            journal_entry=entry,
            account=self.payment_account,
            credit=self.amount
        )


# =========================
# ASSET (UNCHANGED + CLEAN)
# =========================

class Asset(BaseModel):
    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("posted", "Posted"),
        ("cancelled", "Cancelled"),
    )

    name = models.CharField(max_length=255)
    purchase_date = models.DateField(default=date.today)
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    asset_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="asset_account")
    payment_account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="asset_payment_account")

    useful_life_years = models.IntegerField(default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.amount}"

    def post(self):
        if self.status == "posted":
            return

        journal = JournalEntry.objects.create(
            company=self.company,
            date=self.purchase_date,
            reference=f"Asset Purchase {self.name}",
        )

        JournalEntryLine.objects.create(
            journal_entry=journal,
            account=self.asset_account,
            debit=self.amount
        )

        JournalEntryLine.objects.create(
            journal_entry=journal,
            account=self.payment_account,
            credit=self.amount
        )

        self.status = "posted"
        self.save()

    def cancel(self):
        if self.status != "posted":
            return

        entry = JournalEntry.objects.filter(
            reference=f"Asset Purchase {self.name}"
        ).first()

        reverse = JournalEntry.objects.create(
            company=self.company,
            date=self.purchase_date,
            reference=f"Cancel Asset {self.name}",
        )

        for line in entry.lines.all():
            JournalEntryLine.objects.create(
                journal_entry=reverse,
                account=line.account,
                debit=line.credit,
                credit=line.debit
            )

        self.status = "cancelled"
        self.save()



class PaymentAllocation(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='allocations'
    )

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE)

    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        unique_together = ("payment", "invoice")

    def __str__(self):
        return f"{self.payment} → {self.invoice} ({self.amount})"