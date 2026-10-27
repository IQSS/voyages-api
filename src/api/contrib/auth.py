from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils.crypto import constant_time_compare


def service_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        token = settings.CONTRIB_SERVICE_TOKEN
        if not token:
            return JsonResponse({'error': 'Contribution service is not configured'}, status=503)
        header = request.headers.get('Authorization', '')
        if not constant_time_compare(header, 'Bearer ' + token):
            response = JsonResponse({'error': 'Contribution service authentication required'}, status=401)
            response['WWW-Authenticate'] = 'Bearer'
            return response
        return view(request, *args, **kwargs)
    return wrapped
