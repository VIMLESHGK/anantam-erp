from .models import Company

def get_current_company(request):
    company_id = request.session.get("company_id")

    if not company_id:
        return None

    return Company.objects.filter(id=company_id).first()