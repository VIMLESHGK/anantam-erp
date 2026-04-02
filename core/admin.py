from django.contrib import admin
from django import forms
from django.utils.html import format_html
from .models import Company, UserCompany, Account, JournalEntry, JournalEntryLine, Customer, Invoice, InvoiceItem

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "gstin", "phone", "is_active")
    search_fields = ("name", "gstin")


@admin.register(UserCompany)
class UserCompanyAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "role", "is_active")
    list_filter = ("role", "is_active")
    
    
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "account_type", "company", "parent", "balance_display", "view_ledger")

    def view_ledger(self, obj):
        return format_html(
            f'<a href="/core/account/{obj.id}/ledger/">View Ledger</a>'
        )
    view_ledger.short_description = "Ledger"

    def balance_display(self, obj):
        return obj.get_balance()
    balance_display.short_description = "Balance"

class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2


class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()

        total_debit = 0
        total_credit = 0

    # Try to read from inline form data if available
        if hasattr(self, 'instance') and self.instance:
            for line in self.instance.lines.all():
                total_debit += line.debit
                total_credit += line.credit

        if total_debit != total_credit:
            raise forms.ValidationError(
                f"Debit ({total_debit}) must equal Credit ({total_credit})"
            )

        return cleaned_data
    


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    form = JournalEntryForm
    list_display = ("id", "company", "date", "reference")
    inlines = [JournalEntryLineInline]



@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "gstin")


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "customer", "date", "total_amount")
    inlines = [InvoiceItemInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        invoice = form.instance

        # ✅ Step 1: Calculate total
        invoice.update_total()
        invoice.save(update_fields=["total_amount"])

        # ✅ Step 2: Prevent duplicate journal
        from .models import JournalEntry

        if not JournalEntry.objects.filter(
            reference=f"Invoice {invoice.invoice_number}"
        ).exists():
            invoice.create_journal_entry()