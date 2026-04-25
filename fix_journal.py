from core.models import Invoice, JournalEntryLine, Account

for inv in Invoice.objects.all():

    debtor = Account.objects.filter(
        company=inv.company,
        sub_type="receivable"
    ).first()

    lines = JournalEntryLine.objects.filter(
        journal_entry__invoice=inv,
        account=debtor,
        journal_entry__is_cancelled=False
    )

    debit = sum(l.debit for l in lines)
    credit = sum(l.credit for l in lines)

    outstanding = debit - credit

    inv.outstanding_amount = outstanding

    # Fix status also
    if inv.status != "cancelled":
        if outstanding <= 0:
            inv.status = "paid"
            inv.outstanding_amount = 0
        elif outstanding < inv.total_amount:
            inv.status = "partial"
        else:
            inv.status = "posted"

    inv.save()

    print(inv.invoice_number, "=>", outstanding)
