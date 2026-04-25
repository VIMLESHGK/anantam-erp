from django.contrib import admin, messages
from django import forms
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import redirect

from .models import (
    Company, Payment, UserCompany, Account,
    JournalEntry, JournalEntryLine,
    Customer, Invoice, InvoiceItem, Expense
)


# -------------------- COMPANY --------------------
@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['name', 'gstin']
    search_fields = ("name", "gstin")


# -------------------- USER COMPANY --------------------
@admin.register(UserCompany)
class UserCompanyAdmin(admin.ModelAdmin):
    list_display = ['user', 'company', 'role']
    list_filter = ['role']


# -------------------- ACCOUNT --------------------
@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'account_type', 'sub_type', 'company']

    def view_ledger(self, obj):
        return format_html(
            f'<a href="/core/account/{obj.id}/ledger/">View Ledger</a>'
        )

    def balance_display(self, obj):
        return obj.get_balance()


# -------------------- JOURNAL ENTRY --------------------
class JournalEntryLineInline(admin.TabularInline):
    model = JournalEntryLine
    extra = 2


class JournalEntryForm(forms.ModelForm):
    class Meta:
        model = JournalEntry
        fields = "__all__"


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    form = JournalEntryForm
    list_display = ("id", "company", "date", "reference")
    inlines = [JournalEntryLineInline]

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        journal = form.instance

        total_debit = sum(line.debit for line in journal.lines.all())
        total_credit = sum(line.credit for line in journal.lines.all())

        if total_debit != total_credit:
            messages.error(request, "❌ Debit and Credit must be equal")
        else:
            messages.success(request, "✅ Journal Entry saved successfully")


# -------------------- INVOICE --------------------
class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number", "customer", "date",
        "total_amount", "status",
        "cancel_button", "view_pdf"
    )
    inlines = [InvoiceItemInline]
    exclude = ("status",)

    def view_pdf(self, obj):
        return format_html(
            f'<a target="_blank" href="/core/invoice/{obj.id}/pdf/">Print</a>'
        )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        invoice = form.instance

        if invoice.status == "draft":
            invoice.post()

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:invoice_id>/cancel/",
                self.admin_site.admin_view(self.cancel_invoice_view),
                name="cancel-invoice",
            ),
        ]
        return custom_urls + urls

    def cancel_invoice_view(self, request, invoice_id):
        invoice = Invoice.objects.get(id=invoice_id)
        invoice.refresh_from_db()

        invoice.cancel()

        messages.success(request, "Invoice cancelled successfully")
        return redirect("/admin/core/invoice/")

    def cancel_button(self, obj):
        if obj.status != "cancelled":
            return format_html(
                f'<a class="button" href="/admin/core/invoice/{obj.id}/cancel/">Cancel</a>'
            )
        return "Cancelled"

    def has_delete_permission(self, request, obj=None):
        return False


# -------------------- PAYMENT --------------------
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "date", "amount")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if not JournalEntry.objects.filter(
            reference=f"Payment {obj.id}"
        ).exists():
            obj.create_journal_entry()


# -------------------- CUSTOMER --------------------
@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "gstin", "outstanding")

    def outstanding(self, obj):
        return obj.get_outstanding()


# -------------------- EXPENSE --------------------
@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "amount", "expense_account")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        from .models import JournalEntry

        if not JournalEntry.objects.filter(
            reference=f"Expense {obj.id}"
        ).exists():
            obj.post()


# -------------------- ASSETS --------------------

from django.contrib import admin
from .models import Asset
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib import messages


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "amount", "purchase_date", "status", "action_buttons")
    exclude = ("status",)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.post()   # cleaner & safer

    def action_buttons(self, obj):
        if obj.status == "posted":
            url = reverse("admin:cancel-asset", args=[obj.id])
            return format_html(
                '<a href="{}" style="background:#dc3545;color:white;padding:6px 12px;border-radius:5px;text-decoration:none;">Cancel</a>',
                url
            )
        return "-"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:asset_id>/cancel/",
                self.admin_site.admin_view(self.cancel_asset),
                name="cancel-asset",
            ),
        ]
        return custom_urls + urls

    def cancel_asset(self, request, asset_id):
        asset = Asset.objects.get(id=asset_id)

        if asset.status != "posted":
            messages.error(request, "Only posted assets can be cancelled.")
            return redirect("/admin/core/asset/")

        asset.cancel()

        messages.success(request, "Asset cancelled successfully.")
        return redirect("/admin/core/asset/")
            

# -------------------- ADMIN BRANDING --------------------
admin.site.site_header = "Anantam AI ERP"
admin.site.site_title = "Anantam ERP"
admin.site.index_title = "Welcome to Anantam AI ERP"